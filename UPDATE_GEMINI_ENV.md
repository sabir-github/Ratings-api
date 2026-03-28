# Update .env File for Gemini Configurations

## Quick Setup

### Option 1: Use the Setup Script (Recommended)

Run the automated script to create/update your .env file:

```bash
python create_env_template.py
```

This will:
- ✅ Create a `.env` file if it doesn't exist
- ✅ Generate a secure SECRET_KEY automatically
- ✅ Set up all Gemini configuration placeholders
- ✅ Include all other required settings

### Option 2: Manual Setup

If you prefer to create/update the `.env` file manually:

1. **Create or edit `.env` file** in the project root

2. **Add/Update Gemini configurations:**

```bash
# AI/Chat Assistant Settings (Gemini)
# Get your API key from: https://makersuite.google.com/app/apikey
# IMPORTANT: Rotate the old exposed key immediately!
GEMINI_API_KEY=your-new-api-key-here
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_MAX_ITERATIONS=5
MCP_BASE_URL=http://localhost:8000/api/v1/mcp
```

3. **Ensure SECRET_KEY is set:**

```bash
# Generate a secure key first:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Then add to .env:
SECRET_KEY=your-generated-secret-key-here
```

## Complete .env Template

Here's a complete `.env` file template with Gemini configurations:

```bash
# ============================================
# Security Settings (REQUIRED)
# ============================================
SECRET_KEY=your-secret-key-here

# ============================================
# Database Settings
# ============================================
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ratings_db
DATABASE_NAME=motor_management

# ============================================
# CORS Settings
# ============================================
CORS_ALLOW_ALL_ORIGINS=false

# ============================================
# AI/Chat Assistant Settings (Gemini)
# ============================================
# Get your API key from: https://makersuite.google.com/app/apikey
# IMPORTANT: Rotate the old exposed key immediately!
GEMINI_API_KEY=your-new-gemini-api-key-here
GEMINI_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_MAX_ITERATIONS=5
MCP_BASE_URL=http://localhost:8000/api/v1/mcp

# ============================================
# Environment
# ============================================
ENVIRONMENT=development
```

## Gemini API Key Setup Steps

### 1. Get a New API Key

1. Go to: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key" or "Get API Key"
4. Copy the new API key

### 2. Rotate the Old Key (CRITICAL)

**The old exposed key must be revoked:**

1. Go to: https://makersuite.google.com/app/apikey
2. Find the key: `AIzaSyC2nzsj2lvX8wB_pWqVzHOH3M-31y6soSg`
3. Click "Delete" or "Revoke" to disable it
4. This prevents unauthorized usage

### 3. Update .env File

Add your new key to the `.env` file:

```bash
GEMINI_API_KEY=your-new-api-key-from-step-1
```

### 4. Verify Configuration

Test that the configuration is loaded:

```bash
python -c "from app.core.config import settings; print('GEMINI_API_KEY set:', bool(settings.GEMINI_API_KEY))"
```

Expected output: `GEMINI_API_KEY set: True`

## Gemini Configuration Options

### GEMINI_API_KEY
- **Required:** Yes (for chat features)
- **Description:** Your Google Gemini API key
- **Get it from:** https://makersuite.google.com/app/apikey
- **Format:** String starting with "AIza..."

### GEMINI_MODEL_NAME
- **Required:** No (has default)
- **Default:** `gemini-2.0-flash-lite`
- **Description:** The Gemini model to use
- **Options:** 
  - `gemini-2.0-flash-lite` (default, fast)
  - `gemini-2.0-flash-exp` (experimental)
  - `gemini-1.5-pro` (more capable)
  - `gemini-1.5-flash` (faster)

### GEMINI_MAX_ITERATIONS
- **Required:** No (has default)
- **Default:** `5`
- **Description:** Maximum number of tool-calling iterations
- **Range:** 1-10 (recommended: 3-5)

### MCP_BASE_URL
- **Required:** No (has default)
- **Default:** `http://localhost:8000/api/v1/mcp`
- **Description:** Base URL for MCP server
- **Change if:** Running on different host/port

## Verification Checklist

After updating `.env`:

- [ ] GEMINI_API_KEY is set (not empty)
- [ ] Old exposed key has been revoked
- [ ] SECRET_KEY is set and at least 32 characters
- [ ] MONGODB_URL is configured correctly
- [ ] CORS_ALLOW_ALL_ORIGINS is set appropriately
- [ ] `.env` file is NOT committed to git (it's in .gitignore)

## Troubleshooting

### Issue: "GEMINI_API_KEY not configured"
**Solution:** Make sure `.env` file exists and contains `GEMINI_API_KEY=your-key`

### Issue: API key not working
**Solution:** 
1. Verify the key is correct (no extra spaces)
2. Check if the old key was properly revoked
3. Verify you have access to Gemini API

### Issue: Configuration not loading
**Solution:**
1. Ensure `.env` file is in project root (same directory as `app/`)
2. Restart the application after changing `.env`
3. Check for typos in variable names

## Security Reminders

⚠️ **IMPORTANT:**
- Never commit `.env` file to git (it's in .gitignore)
- Rotate the old exposed API key immediately
- Keep your API key secure and don't share it
- Use different keys for development and production
- Monitor API usage for unexpected activity

---

**Need help?** See `ENV_SETUP.md` for complete environment setup guide.

