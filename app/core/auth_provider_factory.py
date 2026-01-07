from typing import Optional
import logging

from app.core.config import settings
from app.core.auth_providers import AuthProvider, KeycloakProvider, EntraProvider

logger = logging.getLogger(__name__)


def get_auth_provider() -> Optional[AuthProvider]:
    """
    Factory function to get the configured authentication provider
    
    Returns:
        AuthProvider instance or None if no provider is configured
    """
    provider_name = settings.AUTH_PROVIDER.lower()
    
    if provider_name == "none":
        return None
    
    if provider_name == "keycloak":
        config = {
            "server_url": settings.KEYCLOAK_SERVER_URL,
            "realm": settings.KEYCLOAK_REALM,
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "verify_ssl": settings.KEYCLOAK_VERIFY_SSL,
        }
        return KeycloakProvider(config)
    
    elif provider_name == "entra":
        if not settings.ENTRA_TENANT_ID or not settings.ENTRA_CLIENT_ID:
            logger.error("Entra provider requires ENTRA_TENANT_ID and ENTRA_CLIENT_ID")
            return None
        
        config = {
            "tenant_id": settings.ENTRA_TENANT_ID,
            "client_id": settings.ENTRA_CLIENT_ID,
            "client_secret": settings.ENTRA_CLIENT_SECRET,
            "verify_ssl": settings.ENTRA_VERIFY_SSL,
        }
        return EntraProvider(config)
    
    else:
        logger.warning(f"Unknown auth provider: {provider_name}")
        return None

