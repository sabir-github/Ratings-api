from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import logging
import httpx

from app.core.auth_provider_factory import get_auth_provider
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)  # Don't auto-raise error, handle manually


class UserInfoResponse(BaseModel):
    """User information response"""
    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    roles: list[str] = []
    groups: list[str] = []


# Health check endpoint for auth service
@router.get("/health")
async def auth_health():
    """
    Health check for authentication service
    """
    provider = get_auth_provider()
    return {
        "status": "healthy",
        "service": "authentication",
        "oidc_enabled": settings.ENABLE_OIDC_SECURITY,
        "provider": provider.get_provider_name() if provider else "none",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get current user information from validated access token
    
    This endpoint validates the Bearer token and returns user information.
    The token is validated using the configured OIDC provider (Keycloak).
    If OIDC security is disabled, returns anonymous user info.
    """
    # If OIDC security is disabled, return anonymous user
    if not settings.ENABLE_OIDC_SECURITY:
        return UserInfoResponse(
            sub="anonymous",
            email=None,
            name=None,
            preferred_username="anonymous",
            roles=[],
            groups=[],
        )
    
    provider = get_auth_provider()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No authentication provider configured"
        )
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    token = credentials.credentials
    
    try:
        # Verify token first
        claims = await provider.verify_token(token)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Get user info from token or userinfo endpoint
        user_info = await provider.get_user_info(token)
        if not user_info:
            # Fallback: extract from token claims
            user_info = {
                "sub": claims.get("sub", ""),
                "email": claims.get("email"),
                "name": claims.get("name"),
                "preferred_username": claims.get("preferred_username"),
                "roles": claims.get("realm_access", {}).get("roles", []),
                "groups": claims.get("groups", []),
            }
        
        return UserInfoResponse(
            sub=user_info.sub if hasattr(user_info, 'sub') else user_info.get("sub", ""),
            email=user_info.email if hasattr(user_info, 'email') else user_info.get("email"),
            name=user_info.name if hasattr(user_info, 'name') else user_info.get("name"),
            preferred_username=user_info.preferred_username if hasattr(user_info, 'preferred_username') else user_info.get("preferred_username"),
            roles=user_info.roles if hasattr(user_info, 'roles') else user_info.get("roles", []),
            groups=user_info.groups if hasattr(user_info, 'groups') else user_info.get("groups", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )
