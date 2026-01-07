from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import logging

from app.core.config import settings
from app.core.auth_provider_factory import get_auth_provider

logger = logging.getLogger(__name__)

# Password hashing (kept for backward compatibility if needed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Bearer token scheme
security = HTTPBearer(auto_error=False)  # Don't auto-raise error, handle manually

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a token (OIDC or local JWT)
    Tries OIDC provider first, falls back to local JWT if no provider configured
    """
    # If OIDC security is disabled, skip verification
    if not settings.ENABLE_OIDC_SECURITY:
        logger.debug("OIDC security disabled, skipping token verification")
        return None
    
    # Try OIDC provider first
    provider = get_auth_provider()
    if provider:
        try:
            claims = await provider.verify_token(token)
            if claims:
                return claims
        except Exception as e:
            logger.warning(f"OIDC token verification failed: {e}")
    
    # Fallback to local JWT verification (for backward compatibility)
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Get current user from OIDC or local JWT token.
    If OIDC security is disabled, returns a default anonymous user.
    """
    # If OIDC security is disabled, return anonymous user
    if not settings.ENABLE_OIDC_SECURITY:
        logger.debug("OIDC security disabled, returning anonymous user")
        return {
            "sub": "anonymous",
            "username": "anonymous",
            "id": "anonymous",
            "user_id": None,
            "email": None,
            "roles": [],
            "role": None,
            "claims": {},
        }
    
    # OIDC security is enabled - require authentication
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    token = credentials.credentials
    payload = await verify_token(token)
    
    if payload is None:
        raise credentials_exception
    
    # Extract user information from token
    # OIDC tokens use 'sub' for subject, local JWT might use 'user_id'
    sub = payload.get("sub")
    user_id = payload.get("user_id")
    username = payload.get("preferred_username") or payload.get("username") or sub
    email = payload.get("email")
    
    # Extract roles - OIDC might have roles in different places
    roles = []
    if "realm_access" in payload and "roles" in payload["realm_access"]:
        roles = payload["realm_access"]["roles"]
    elif "roles" in payload:
        roles = payload["roles"]
    elif "role" in payload:
        roles = [payload["role"]]
    
    # For OIDC, we use 'sub' as the identifier
    # For local JWT, we use 'user_id'
    identifier = user_id if user_id else sub
    
    if not identifier:
        raise credentials_exception
    
    return {
        "sub": sub or identifier,
        "username": username or identifier,
        "id": identifier,
        "user_id": user_id,
        "email": email,
        "roles": roles,
        "role": roles[0] if roles else None,  # Backward compatibility
        "claims": payload,  # Include all claims for advanced use cases
    }

async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current active user
    In a real implementation, you would check if the user is active
    For now, we assume all users with valid tokens are active
    """
    return current_user

def generate_reset_token() -> str:
    """Generate a password reset token"""
    return secrets.token_urlsafe(32)

def generate_email_verification_token() -> str:
    """Generate an email verification token"""
    return secrets.token_urlsafe(32)