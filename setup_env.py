#!/usr/bin/env python3
"""
Script to generate .env file with Gemini configurations and other required settings.
Run this script to create a .env file with proper configuration.
"""
import secrets
import os
from pathlib import Path

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_urlsafe(32)

def create_env_file():
    """Create .env file with default configurations"""
    env_file = Path(".env")
    
    if env_file.exists():
        response = input(".env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted. Existing .env file preserved.")
            return
    
    # Get Gemini API key from user
    print("\n" + "="*60)
    print("Gemini API Configuration")
    print("="*60)
    print("Get your API key from: https://makersuite.google.com/app/apikey")
    print("IMPORTANT: Rotate the old exposed key immediately!")
    gemini_key = input("\nEnter your Gemini API key (or press Enter to skip): ").strip()
    
    # Get SECRET_KEY
    print("\n" + "="*60)
    print("Security Configuration")
    print("="*60)
    generate_key = input("Generate a new SECRET_KEY? (Y/n): ").strip().lower()
    if generate_key != 'n':
        secret_key = generate_secret_key()
        print(f"Generated SECRET_KEY: {secret_key}")
    else:
        secret_key = input("Enter your SECRET_KEY (or press Enter to skip): ").strip()
    
    # Get MongoDB URL
    print("\n" + "="*60)
    print("Database Configuration")
    print("="*60)
    mongodb_url = input("Enter MongoDB URL (default: mongodb://localhost:27017): ").strip()
    if not mongodb_url:
        mongodb_url = "mongodb://localhost:27017"
    
    # Get CORS setting
    print("\n" + "="*60)
    print("CORS Configuration")
    print("="*60)
    cors_all = input("Allow all CORS origins? (y/N) [Only for development]: ").strip().lower()
    cors_all_value = "true" if cors_all == 'y' else "false"
    
    # Get environment
    print("\n" + "="*60)
    print("Environment")
    print("="*60)
    environment = input("Environment (development/production) [default: development]: ").strip()
    if not environment:
        environment = "development"
    
    # Build .env content
    env_content = f"""# ============================================
# Ratings API - Environment Configuration
# ============================================
# IMPORTANT: This file contains sensitive information
# DO NOT commit this file to version control
# ============================================

# ============================================
# Security Settings (REQUIRED)
# ============================================
# Generate a secure key: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY={secret_key}

# ============================================
# Database Settings
# ============================================
# For local development (no auth):
MONGODB_URL={mongodb_url}
# For production (with auth):
# MONGODB_URL=mongodb://username:password@host:port/?authSource=admin
MONGODB_DB_NAME=ratings_db
DATABASE_NAME=motor_management

# ============================================
# CORS Settings
# ============================================
# Set to "true" only for development - NEVER in production!
CORS_ALLOW_ALL_ORIGINS={cors_all_value}
# Or specify specific origins (comma-separated):
# BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ============================================
# AI/Chat Assistant Settings (Gemini)
# ============================================
# Get your API key from: https://makersuite.google.com/app/apikey
# IMPORTANT: Rotate the old exposed key immediately!
GEMINI_API_KEY={gemini_key}
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_MAX_ITERATIONS=5
MCP_BASE_URL=http://localhost:8000/api/v1/mcp

# ============================================
# Environment
# ============================================
# Set to "production" for production deployments
ENVIRONMENT={environment}

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
    
    # Write .env file
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("\n" + "="*60)
        print("✅ .env file created successfully!")
        print("="*60)
        print(f"Location: {env_file.absolute()}")
        print("\n⚠️  IMPORTANT:")
        print("1. The .env file is now in .gitignore and will NOT be committed")
        print("2. If you entered a Gemini API key, make sure to rotate the old exposed key")
        print("3. Keep this file secure and never share it publicly")
        print("4. For production, ensure all required values are set")
    except Exception as e:
        print(f"\n❌ Error creating .env file: {e}")

if __name__ == "__main__":
    create_env_file()

