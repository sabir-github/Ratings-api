from pydantic_settings import BaseSettings
from typing import Optional, Literal
import os

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ratings API"
    VERSION: str = "1.0"
    
    # Security Settings
    # SECRET_KEY must be set via environment variable for security
    # Generate a secure key: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth2/OIDC Settings
    ENABLE_OIDC_SECURITY: bool = False  # Toggle to enable/disable OIDC security
    AUTH_PROVIDER: Literal["keycloak", "entra", "none"] = "keycloak"
    
    # Keycloak Settings
    KEYCLOAK_SERVER_URL: str = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:9180")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "pnc-insurance")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "pnc-insurance-ui")
    KEYCLOAK_CLIENT_SECRET: Optional[str] = os.getenv("KEYCLOAK_CLIENT_SECRET")
    # SSL verification should be True in production - only disable for development
    KEYCLOAK_VERIFY_SSL: bool = os.getenv("KEYCLOAK_VERIFY_SSL", "True").lower() == "true"
    
    # Entra (Azure AD) Settings
    ENTRA_TENANT_ID: Optional[str] = None
    ENTRA_CLIENT_ID: Optional[str] = None
    ENTRA_CLIENT_SECRET: Optional[str] = None
    ENTRA_VERIFY_SSL: bool = True
    
    # Database Settings
    # MONGODB_URL must be set via environment variable for security
    # Format: mongodb://username:password@host:port/?authSource=admin
    # For local development: mongodb://localhost:27017 (no auth)
    # For production: mongodb://user:pass@host:port/?authSource=admin
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:37017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "ratings_db")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "motor_management")
    
    # CORS Settings
    # List of allowed origins. For development, include common frontend ports
    # For production, specify exact origins (e.g., ["https://yourdomain.com"])
    # Set to ["*"] to allow all origins (not recommended for production)
    # Can be overridden via BACKEND_CORS_ORIGINS environment variable (comma-separated list)
    BACKEND_CORS_ORIGINS: list = [
        "http://localhost:5173",  # Vite default port
        "http://localhost:3000",  # React default port
        "http://localhost:5174",  # Alternative Vite port
        "http://localhost:8080",  # Vue CLI default port
        "http://localhost:8000",  # Common dev server port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
    ]
    
    # Allow all origins for development (set to True to enable, overrides BACKEND_CORS_ORIGINS)
    # WARNING: Only use in development! Set via CORS_ALLOW_ALL_ORIGINS environment variable
    # Default is False for security - must explicitly enable via environment variable
    CORS_ALLOW_ALL_ORIGINS: bool = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False").lower() == "true"
    
    # Email Settings (for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    
    # AI/Chat Assistant Settings
    # GEMINI_API_KEY must be set via environment variable for security
    # Get your API key from: https://makersuite.google.com/app/apikey
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-lite")
    GEMINI_MAX_ITERATIONS: int = int(os.getenv("GEMINI_MAX_ITERATIONS", "5"))
    MCP_BASE_URL: str = os.getenv("MCP_BASE_URL", "http://localhost:8000/api/v1/mcp")
    
    # Environment Settings
    # Set to "production" for production deployments, "development" for development
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging Settings
    # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # Optional log file path (e.g., "logs/app.log")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    
    class Config:
        case_sensitive = True
        env_file = ".env"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validate critical security settings
        self._validate_security_settings()
    
    def _validate_security_settings(self):
        """Validate that critical security settings are properly configured"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Check SECRET_KEY
        if not self.SECRET_KEY or self.SECRET_KEY == "":
            error_msg = (
                "SECRET_KEY is not set! This is required for security. "
                "Set it via environment variable: export SECRET_KEY='your-secret-key'\n"
                "Generate a secure key: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
            logger.error(error_msg)
            # In production, we should raise an error, but for development allow it with warning
            if self.ENVIRONMENT.lower() == "production":
                raise ValueError(error_msg)
            else:
                logger.warning("SECRET_KEY not set - using empty string (NOT SECURE FOR PRODUCTION)")
        
        # Warn if using weak SECRET_KEY
        if self.SECRET_KEY and len(self.SECRET_KEY) < 32:
            logger.warning(
                f"SECRET_KEY is too short ({len(self.SECRET_KEY)} chars). "
                "Recommend at least 32 characters for security."
            )
        
        # Warn about CORS_ALLOW_ALL_ORIGINS in production
        if self.CORS_ALLOW_ALL_ORIGINS and self.ENVIRONMENT.lower() == "production":
            logger.error(
                "CORS_ALLOW_ALL_ORIGINS is True in production! "
                "This is a security risk. Set CORS_ALLOW_ALL_ORIGINS=False"
            )

settings = Settings()