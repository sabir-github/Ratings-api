from pydantic_settings import BaseSettings
from typing import Optional, Literal
import os

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ratings API"
    VERSION: str = "1.0"
    
    # Security Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth2/OIDC Settings
    ENABLE_OIDC_SECURITY: bool = False  # Toggle to enable/disable OIDC security
    AUTH_PROVIDER: Literal["keycloak", "entra", "none"] = "keycloak"
    
    # Keycloak Settings
    KEYCLOAK_SERVER_URL: str = "http://localhost:9180"
    KEYCLOAK_REALM: str = "pnc-insurance"
    KEYCLOAK_CLIENT_ID: str = "pnc-insurance-ui"
    KEYCLOAK_CLIENT_SECRET: Optional[str] = None
    KEYCLOAK_VERIFY_SSL: bool = False
    
    # Entra (Azure AD) Settings
    ENTRA_TENANT_ID: Optional[str] = None
    ENTRA_CLIENT_ID: Optional[str] = None
    ENTRA_CLIENT_SECRET: Optional[str] = None
    ENTRA_VERIFY_SSL: bool = True
    
    # Database Settings
    # Default connects to MongoDB from Ratings-api docker-compose
    # Override via MONGODB_URL environment variable if needed
    MONGODB_URL: str = "mongodb://admin:password@localhost:37017/?authSource=admin"
    MONGODB_DB_NAME: str = "ratings_db"
    DATABASE_NAME: str = "motor_management"
    
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
    CORS_ALLOW_ALL_ORIGINS: bool = True  # Set to True for development
    
    # Email Settings (for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    
    # AI/Chat Assistant Settings
    GEMINI_API_KEY: Optional[str] = "AIzaSyC2nzsj2lvX8wB_pWqVzHOH3M-31y6soSg"
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash-lite"
    GEMINI_MAX_ITERATIONS: int = 5
    MCP_BASE_URL: str = "http://localhost:8000/api/v1/mcp"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()