# Environment Variables Setup Guide

This guide explains how to set up environment variables for the Ratings API securely.

## Critical Security Variables

### SECRET_KEY (REQUIRED)
**Generate a secure key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Set in environment:**
```bash
export SECRET_KEY="your-generated-secret-key-here"
```

**Or in .env file:**
```
SECRET_KEY=your-generated-secret-key-here
```

⚠️ **IMPORTANT:** Never commit the SECRET_KEY to version control!

---

### MONGODB_URL (REQUIRED)
**For local development (no authentication):**
```bash
export MONGODB_URL="mongodb://localhost:27017"
```

**For production (with authentication):**
```bash
export MONGODB_URL="mongodb://username:password@host:port/?authSource=admin"
```

**Or in .env file:**
```
MONGODB_URL=mongodb://localhost:27017
```

---

### GEMINI_API_KEY (Optional - for chat features)
**Get your API key from:** https://makersuite.google.com/app/apikey

**Set in environment:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Or in .env file:**
```
GEMINI_API_KEY=your-api-key-here
```

---

## CORS Configuration

### CORS_ALLOW_ALL_ORIGINS
**For development:**
```bash
export CORS_ALLOW_ALL_ORIGINS="true"
```

**For production (REQUIRED):**
```bash
export CORS_ALLOW_ALL_ORIGINS="false"
```

⚠️ **SECURITY WARNING:** Never set this to `true` in production!

**Or in .env file:**
```
CORS_ALLOW_ALL_ORIGINS=false
```

---

## Complete .env File Example

Create a `.env` file in the project root with the following:

```bash
# Security Settings
SECRET_KEY=your-secret-key-here-change-this-in-production

# Database Settings
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ratings_db
DATABASE_NAME=motor_management

# CORS Settings
CORS_ALLOW_ALL_ORIGINS=false

# AI/Chat Assistant Settings
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_MAX_ITERATIONS=5

# Environment
ENVIRONMENT=development

# OAuth2/OIDC Settings (optional)
ENABLE_OIDC_SECURITY=false
AUTH_PROVIDER=keycloak

# Keycloak Settings (if using OIDC)
KEYCLOAK_SERVER_URL=http://localhost:9180
KEYCLOAK_REALM=pnc-insurance
KEYCLOAK_CLIENT_ID=pnc-insurance-ui
KEYCLOAK_CLIENT_SECRET=your-keycloak-client-secret
KEYCLOAK_VERIFY_SSL=true
```

---

## Quick Setup Script

**For Linux/Mac:**
```bash
# Generate and set SECRET_KEY
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "SECRET_KEY=$SECRET_KEY" >> .env

# Set other required variables
echo "MONGODB_URL=mongodb://localhost:27017" >> .env
echo "CORS_ALLOW_ALL_ORIGINS=false" >> .env
```

**For Windows (PowerShell):**
```powershell
# Generate and set SECRET_KEY
$secretKey = python -c "import secrets; print(secrets.token_urlsafe(32))"
Add-Content -Path .env -Value "SECRET_KEY=$secretKey"

# Set other required variables
Add-Content -Path .env -Value "MONGODB_URL=mongodb://localhost:27017"
Add-Content -Path .env -Value "CORS_ALLOW_ALL_ORIGINS=false"
```

---

## Production Deployment Checklist

- [ ] SECRET_KEY is set and is at least 32 characters
- [ ] MONGODB_URL uses authenticated connection
- [ ] CORS_ALLOW_ALL_ORIGINS is set to `false`
- [ ] BACKEND_CORS_ORIGINS lists only specific allowed origins
- [ ] GEMINI_API_KEY is set (if using chat features)
- [ ] ENVIRONMENT is set to `production`
- [ ] KEYCLOAK_VERIFY_SSL is set to `true` (if using Keycloak)
- [ ] .env file is NOT committed to version control
- [ ] All secrets are stored in secure secret management system

---

## Security Notes

1. **Never commit .env files** - They are now in .gitignore
2. **Rotate exposed keys** - If any keys were exposed, rotate them immediately
3. **Use strong SECRET_KEY** - At least 32 characters, randomly generated
4. **Restrict CORS in production** - Only allow specific origins
5. **Use environment variables** - Never hardcode secrets in source code

