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
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ratings_db"
    DATABASE_NAME: str = "motor_management"
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # Email Settings (for password reset)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()