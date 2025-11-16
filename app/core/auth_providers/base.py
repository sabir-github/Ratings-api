from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class TokenInfo(BaseModel):
    """Standardized token information"""
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None


class UserInfo(BaseModel):
    """Standardized user information from OIDC provider"""
    sub: str  # Subject identifier
    email: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    roles: list[str] = []
    groups: list[str] = []
    claims: Dict[str, Any] = {}  # Additional claims


class AuthProvider(ABC):
    """Base class for OAuth2/OIDC authentication providers"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
        self.validate_config()
    
    @abstractmethod
    def validate_config(self) -> None:
        """Validate provider configuration"""
        pass
    
    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get authorization URL for OAuth2 authorization code flow
        
        Args:
            redirect_uri: Redirect URI after authorization
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_token(
        self, 
        code: str, 
        redirect_uri: str
    ) -> TokenInfo:
        """
        Exchange authorization code for tokens
        
        Args:
            code: Authorization code from callback
            redirect_uri: Redirect URI used in authorization
            
        Returns:
            TokenInfo with access token and optional refresh token
        """
        pass
    
    @abstractmethod
    async def get_client_credentials_token(self) -> TokenInfo:
        """
        Get access token using client credentials flow (for service-to-service)
        
        Returns:
            TokenInfo with access token
        """
        pass
    
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode an access token
        
        Args:
            token: Access token to verify
            
        Returns:
            Decoded token claims or None if invalid
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, token: str) -> Optional[UserInfo]:
        """
        Get user information from access token or userinfo endpoint
        
        Args:
            token: Access token
            
        Returns:
            UserInfo or None if unable to retrieve
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Optional[TokenInfo]:
        """
        Refresh an access token using refresh token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New TokenInfo or None if refresh failed
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the provider"""
        pass

