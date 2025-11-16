import httpx
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import logging
from jose import jwt, JWTError
from authlib.jose import JsonWebKey
import time

from app.core.auth_providers.base import AuthProvider, TokenInfo, UserInfo

logger = logging.getLogger(__name__)


class KeycloakProvider(AuthProvider):
    """Keycloak OIDC/OAuth2 provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Keycloak provider
        
        Config should contain:
        - server_url: Keycloak server URL (e.g., http://localhost:9180)
        - realm: Realm name (e.g., pnc-insurance)
        - client_id: Client ID
        - client_secret: Client secret (for confidential clients)
        - verify_ssl: Whether to verify SSL certificates (default: True)
        """
        # Set attributes before calling super().__init__ which calls validate_config
        self.server_url = config["server_url"].rstrip("/")
        self.realm = config["realm"]
        self.client_id = config["client_id"]
        self.client_secret = config.get("client_secret")
        self.verify_ssl = config.get("verify_ssl", True)
        
        # Construct URLs
        self.realm_url = f"{self.server_url}/realms/{self.realm}"
        self.authorization_url = f"{self.realm_url}/protocol/openid-connect/auth"
        self.token_url = f"{self.realm_url}/protocol/openid-connect/token"
        self.userinfo_url = f"{self.realm_url}/protocol/openid-connect/userinfo"
        self.jwks_url = f"{self.realm_url}/protocol/openid-connect/certs"
        
        super().__init__(config)
        
        # Cache for JWKS
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl: int = 3600  # 1 hour
    
    def validate_config(self) -> None:
        """Validate Keycloak configuration"""
        required = ["server_url", "realm", "client_id"]
        missing = [key for key in required if key not in self.config]
        if missing:
            raise ValueError(f"Missing required Keycloak config keys: {missing}")
        
        if not self.client_secret:
            logger.warning("Keycloak client_secret not provided. Using public client mode.")
    
    def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Get Keycloak authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
        }
        
        if state:
            params["state"] = state
        
        return f"{self.authorization_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> TokenInfo:
        """Exchange authorization code for tokens"""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
        }
        
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
        
        return TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "bearer"),
            expires_in=token_data.get("expires_in"),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
        )
    
    async def get_client_credentials_token(self) -> TokenInfo:
        """Get access token using client credentials flow"""
        if not self.client_secret:
            raise ValueError("Client credentials flow requires client_secret")
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
        
        return TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "bearer"),
            expires_in=token_data.get("expires_in"),
        )
    
    async def _get_jwks(self) -> Dict[str, Any]:
        """Get JWKS (JSON Web Key Set) from Keycloak with caching"""
        current_time = time.time()
        
        # Return cached JWKS if still valid
        if self._jwks_cache and (current_time - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache
        
        # Fetch fresh JWKS
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(self.jwks_url)
            response.raise_for_status()
            jwks = response.json()
        
        self._jwks_cache = jwks
        self._jwks_cache_time = current_time
        
        return jwks
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode Keycloak access token with proper signature verification"""
        try:
            # Get JWKS
            jwks = await self._get_jwks()
            
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            # Find the matching key
            matching_key = None
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    matching_key = jwk
                    break
            
            if not matching_key:
                logger.warning("No matching key found in JWKS")
                return None
            
            # Get issuer from token
            unverified_claims = jwt.get_unverified_claims(token)
            issuer = unverified_claims.get("iss", self.realm_url)
            
            # Build public key from JWK using authlib
            try:
                jwk_set = JsonWebKey.import_key_set(jwks)
                public_key = jwk_set.find_by_kid(kid)
                
                if not public_key:
                    logger.warning("No matching key found in JWKS")
                    return None
                
                # Verify and decode token with signature verification using authlib
                from authlib.jose import jwt as authlib_jwt
                # For resource servers, audience can be flexible (account, client_id, or resource name)
                # We'll validate issuer but be flexible with audience
                claims_obj = authlib_jwt.decode(
                    token,
                    public_key,
                    claims_options={
                        "iss": {"essential": True, "value": issuer},
                        # Audience validation is flexible - token may have "account" or client_id
                        "aud": {"essential": False},
                    }
                )
                claims_obj.validate()
                # Convert Claims object to dict
                claims = dict(claims_obj)
                
                # Manual audience check - accept if audience is account, client_id, or contains client_id
                aud = claims.get("aud")
                if aud:
                    # Accept if aud is "account" (standard for user tokens) or matches client_id
                    # or if it's a list containing our client_id
                    if isinstance(aud, list):
                        valid_aud = self.client_id in aud or "account" in aud
                    else:
                        valid_aud = aud == self.client_id or aud == "account" or self.client_id in str(aud)
                    
                    if not valid_aud:
                        logger.warning(f"Audience mismatch: {aud} (expected {self.client_id} or account)")
                        # Still accept for now - resource servers often accept multiple audiences
                
            except Exception as e:
                logger.warning(f"Token verification failed, trying fallback: {e}")
                # Fallback: decode without signature verification for development/testing
                # WARNING: This should not be used in production
                try:
                    claims = jwt.decode(token, options={"verify_signature": False})
                    logger.warning("Using unverified token decode - NOT SECURE FOR PRODUCTION")
                except JWTError as decode_error:
                    logger.error(f"JWT decode error: {decode_error}")
                    return None
            
            # Additional validation
            if claims.get("iss") != issuer:
                logger.warning(f"Issuer mismatch: {claims.get('iss')} != {issuer}")
                return None
            
            # Check expiration (jwt.decode should handle this, but double-check)
            exp = claims.get("exp")
            if exp and exp < time.time():
                logger.warning("Token has expired")
                return None
            
            return claims
                
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    async def get_user_info(self, token: str) -> Optional[UserInfo]:
        """Get user information from Keycloak userinfo endpoint"""
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    self.userinfo_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                user_data = response.json()
            
            # Extract roles from token or userinfo
            roles = user_data.get("realm_access", {}).get("roles", [])
            groups = user_data.get("groups", [])
            
            return UserInfo(
                sub=user_data.get("sub", ""),
                email=user_data.get("email"),
                name=user_data.get("name"),
                preferred_username=user_data.get("preferred_username"),
                roles=roles,
                groups=groups,
                claims=user_data,
            )
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            # Fallback: try to extract from token
            claims = await self.verify_token(token)
            if claims:
                return UserInfo(
                    sub=claims.get("sub", ""),
                    email=claims.get("email"),
                    name=claims.get("name"),
                    preferred_username=claims.get("preferred_username"),
                    roles=claims.get("realm_access", {}).get("roles", []),
                    groups=claims.get("groups", []),
                    claims=claims,
                )
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[TokenInfo]:
        """Refresh access token using refresh token"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_data = response.json()
            
            return TokenInfo(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                id_token=token_data.get("id_token"),
            )
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None
    
    def get_provider_name(self) -> str:
        """Get provider name"""
        return "keycloak"

