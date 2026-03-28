#!/usr/bin/env python3
"""
Non-interactive script to create .env template file.
This creates a .env file with empty values that you can fill in.
"""
import secrets
from pathlib import Path

def create_env_template():
    """Create .env template file with Gemini configurations"""
    env_file = Path(".env")
    
    if env_file.exists():
        print("⚠️  .env file already exists. Skipping creation.")
        print("   If you want to recreate it, delete the existing file first.")
        return
    
    # Generate a secure SECRET_KEY
    secret_key = secrets.token_urlsafe(32)
    
    env_content = f"""# ============================================
# Ratings API - Environment Configuration
# ============================================
# IMPORTANT: This file contains sensitive information
# DO NOT commit this file to version control
# ============================================

# ============================================
# Security Settings (REQUIRED)
# ============================================
# A secure SECRET_KEY has been generated for you
# You can regenerate: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY={secret_key}

# ============================================
# Database Settings
# ============================================
# For local development (no auth):
MONGODB_URL=mongodb://localhost:27017
# For production (with auth):
# MONGODB_URL=mongodb://username:password@host:port/?authSource=admin
MONGODB_DB_NAME=ratings_db
DATABASE_NAME=motor_management

# ============================================
# CORS Settings
# ============================================
# Set to "true" only for development - NEVER in production!
CORS_ALLOW_ALL_ORIGINS=false
# Or specify specific origins (comma-separated):
# BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ============================================
# AI/Chat Assistant Settings (Gemini)
# ============================================
# Get your API key from: https://makersuite.google.com/app/apikey
# IMPORTANT: Rotate the old exposed key immediately!
# The old key "AIzaSyC2nzsj2lvX8wB_pWqVzHOH3M-31y6soSg" must be revoked
GEMINI_API_KEY=
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_MAX_ITERATIONS=5
MCP_BASE_URL=http://localhost:8000/api/v1/mcp

# ============================================
# Environment
# ============================================
# Set to "production" for production deployments
ENVIRONMENT=development

# ============================================
# OAuth2/OIDC Settings (Optional)
# ============================================
ENABLE_OIDC_SECURITY=false
AUTH_PROVIDER=keycloak

# Keycloak Settings (if using OIDC)
KEYCLOAK_SERVER_URL=http://localhost:9180
KEYCLOAK_REALM=pnc-insurance
KEYCLOAK_CLIENT_ID=pnc-insurance-ui
KEYCLOAK_CLIENT_SECRET=
KEYCLOAK_VERIFY_SSL=true

# Entra (Azure AD) Settings (if using)
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_VERIFY_SSL=true

# ============================================
# Email Settings (Optional)
# ============================================
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=

# ============================================
# Logging Settings (Optional)
# ============================================
LOG_LEVEL=INFO
# LOG_FILE=logs/app.log
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
        print(f"   Location: {env_file.absolute()}")
        print("\n📝 Next steps:")
        print("   1. Add your GEMINI_API_KEY (get it from https://makersuite.google.com/app/apikey)")
        print("   2. Rotate the old exposed key: AIzaSyC2nzsj2lvX8wB_pWqVzHOH3M-31y6soSg")
        print("   3. Update MONGODB_URL if needed")
        print("   4. Set CORS_ALLOW_ALL_ORIGINS=true for development if needed")
        print("\n⚠️  Remember:")
        print("   - .env file is in .gitignore and will NOT be committed")
        print("   - Keep this file secure and never share it publicly")
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

if __name__ == "__main__":
    create_env_template()

