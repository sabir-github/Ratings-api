# Security Vulnerability Report
**Date:** 2024-12-19  
**Project:** Ratings API  
**Severity Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

---

## 🔴 CRITICAL VULNERABILITIES

### 1. Hardcoded API Keys and Secrets in Source Code
**Location:** `app/core/config.py:71`
```python
GEMINI_API_KEY: Optional[str] = "AIzaSyC2nzsj2lvX8wB_pWqVzHOH3M-31y6soSg"
```
**Risk:** Exposed API key in source code. This key is publicly visible and can be abused.
**Impact:** 
- Unauthorized API usage leading to cost overruns
- Potential data exposure if API has access to sensitive data
- Key compromise requiring immediate rotation

**Recommendation:**
- Remove hardcoded API key immediately
- Use environment variables only: `GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")`
- Rotate the exposed key immediately
- Add `.env` to `.gitignore` (currently tracked)

---

### 2. Hardcoded Database Credentials
**Location:** `app/core/config.py:37`
```python
MONGODB_URL: str = "mongodb://admin:password@localhost:37017/?authSource=admin"
```
**Risk:** Default credentials in source code
**Impact:**
- Database compromise if code is exposed
- Unauthorized database access

**Recommendation:**
- Remove default credentials
- Use environment variables: `MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")`
- Require credentials to be set via environment variables

---

### 3. Weak Default Secret Key
**Location:** `app/core/config.py:12`
```python
SECRET_KEY: str = "your-secret-key-change-in-production"
```
**Risk:** Weak default secret key used for JWT signing
**Impact:**
- Token forgery
- Authentication bypass
- Session hijacking

**Recommendation:**
- Remove default secret key
- Require strong secret key via environment variable
- Generate cryptographically secure random key: `secrets.token_urlsafe(32)`
- Add validation to ensure secret key is changed in production

---

### 4. Insecure eval() Usage
**Location:** `app/services/evaluate_expression.py:66`
```python
result = eval(expression, {"__builtins__": {}}, safe_dict)
```
**Risk:** Code injection vulnerability despite restrictions
**Impact:**
- Remote code execution if restrictions are bypassed
- Potential for malicious code execution

**Recommendation:**
- Consider using `ast.literal_eval()` for simple expressions
- Use a proper expression parser library (e.g., `simpleeval`, `pyparsing`)
- Implement stricter input validation and sanitization
- Add rate limiting to prevent abuse
- Log all expressions for security monitoring

---

## 🟠 HIGH VULNERABILITIES

### 5. CORS Misconfiguration - Allow All Origins
**Location:** `app/core/config.py:61`, `app/main.py:61`
```python
CORS_ALLOW_ALL_ORIGINS: bool = True  # Set to True for development
allow_origins=["*"]
```
**Risk:** Allows requests from any origin
**Impact:**
- Cross-site request forgery (CSRF) attacks
- Unauthorized API access from malicious websites
- Data exfiltration

**Recommendation:**
- Set `CORS_ALLOW_ALL_ORIGINS: bool = False` by default
- Use environment variable to enable only in development
- Configure specific allowed origins for production
- Remove wildcard `["*"]` from production code

---

### 6. Insecure Token Verification Fallback
**Location:** `app/core/auth_providers/keycloak.py:217-218`
```python
claims = jwt.decode(token, options={"verify_signature": False})
logger.warning("Using unverified token decode - NOT SECURE FOR PRODUCTION")
```
**Risk:** Token verification bypass in fallback code
**Impact:**
- Authentication bypass
- Unauthorized access to protected resources
- Token forgery acceptance

**Recommendation:**
- Remove fallback that skips signature verification
- Fail securely instead of accepting unverified tokens
- Only allow unverified decode in development with explicit flag
- Add production check to prevent this code path

---

### 7. Missing Input Validation on File Uploads
**Location:** `app/api/v1/endpoints/upload.py`
**Risk:** File upload vulnerabilities
**Issues:**
- Only checks file extension, not actual file type
- No file size limits
- No virus/malware scanning
- Excel files can contain malicious macros

**Recommendation:**
- Validate file MIME type, not just extension
- Implement file size limits (e.g., max 10MB)
- Scan uploaded files for malware
- Disable macro execution in Excel files
- Use whitelist of allowed file types
- Store uploaded files outside web root

---

### 8. .env File Not in .gitignore
**Location:** `.gitignore:33`
```python
# Environment variables - .env is tracked (remove sensitive data before committing)
```
**Risk:** `.env` files may be committed to version control
**Impact:**
- Exposure of secrets, API keys, and credentials
- Database connection strings exposed

**Recommendation:**
- Add `.env` to `.gitignore`
- Add `.env.*` pattern to ignore all env files
- Audit git history for committed secrets
- Use tools like `git-secrets` or `truffleHog` to scan

---

## 🟡 MEDIUM VULNERABILITIES

### 9. NoSQL Injection Risk
**Location:** Multiple service files using MongoDB queries
**Risk:** User input directly used in MongoDB queries without sanitization
**Example:** `app/services/company_service.py` - filter_by parameters

**Recommendation:**
- Validate and sanitize all user inputs
- Use parameterized queries where possible
- Implement input validation schemas
- Escape special MongoDB operators ($where, $regex, etc.)

---

### 10. Missing Rate Limiting
**Location:** All API endpoints
**Risk:** API abuse, DoS attacks, brute force attacks
**Impact:**
- Resource exhaustion
- Cost overruns (especially with AI API calls)
- Service unavailability

**Recommendation:**
- Implement rate limiting middleware (e.g., `slowapi`, `fastapi-limiter`)
- Set different limits for different endpoints
- Implement IP-based and user-based rate limiting
- Add rate limiting to `evaluate_expression` endpoint

---

### 11. Information Disclosure in Error Messages
**Location:** Multiple endpoints
**Risk:** Detailed error messages may leak system information
**Example:** Stack traces, database errors, file paths

**Recommendation:**
- Use generic error messages in production
- Log detailed errors server-side only
- Implement custom exception handlers
- Don't expose internal system details

---

### 12. Missing Security Headers
**Location:** `app/main.py`
**Risk:** Missing security headers
**Impact:**
- XSS attacks
- Clickjacking
- MIME type sniffing

**Recommendation:**
- Add security headers middleware:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security` (for HTTPS)
  - `Content-Security-Policy`

---

### 13. SSL Verification Disabled
**Location:** `app/core/config.py:26, 32`
```python
KEYCLOAK_VERIFY_SSL: bool = False
ENTRA_VERIFY_SSL: bool = True  # Good, but Keycloak is False
```
**Risk:** Man-in-the-middle attacks
**Impact:**
- Interception of authentication tokens
- Credential theft

**Recommendation:**
- Enable SSL verification by default
- Only disable in development with explicit flag
- Use proper certificate validation

---

## 🟢 LOW VULNERABILITIES / BEST PRACTICES

### 14. Weak Password Requirements
**Location:** `app/schemas/user.py:26-30`
**Risk:** Only requires 8 characters minimum
**Recommendation:**
- Enforce stronger password policy (12+ chars, mixed case, numbers, symbols)
- Implement password strength meter
- Check against common password lists

### 15. Missing Request Size Limits
**Location:** FastAPI application
**Risk:** Large request DoS
**Recommendation:**
- Set maximum request body size
- Configure FastAPI with `max_request_size`

### 16. Logging Sensitive Information
**Location:** `app/services/evaluate_expression.py:23-24`
**Risk:** Variables may contain sensitive data
**Recommendation:**
- Sanitize logs to remove sensitive data
- Use log masking for PII/sensitive values
- Implement log rotation and retention policies

### 17. Missing Dependency Vulnerability Scanning
**Location:** `requirements.txt`
**Risk:** Using packages with known vulnerabilities
**Recommendation:**
- Use `safety` or `pip-audit` to scan dependencies
- Keep dependencies updated
- Review security advisories regularly

### 18. No API Versioning Security
**Location:** API endpoints
**Risk:** Breaking changes without proper versioning
**Recommendation:**
- Implement proper API versioning strategy
- Deprecate old versions gracefully
- Document version changes

---

## IMMEDIATE ACTION ITEMS (Priority Order)

1. **🔴 URGENT:** Remove hardcoded Gemini API key and rotate it
2. **🔴 URGENT:** Remove hardcoded database credentials
3. **🔴 URGENT:** Change default SECRET_KEY and require environment variable
4. **🟠 HIGH:** Fix CORS configuration for production
5. **🟠 HIGH:** Remove insecure token verification fallback
6. **🟠 HIGH:** Add `.env` to `.gitignore`
7. **🟡 MEDIUM:** Implement rate limiting
8. **🟡 MEDIUM:** Add security headers
9. **🟡 MEDIUM:** Improve file upload validation
10. **🟡 MEDIUM:** Enable SSL verification by default

---

## Security Best Practices Checklist

- [ ] All secrets in environment variables only
- [ ] `.env` file in `.gitignore`
- [ ] Strong secret keys (32+ characters, random)
- [ ] CORS properly configured for production
- [ ] Rate limiting implemented
- [ ] Security headers added
- [ ] Input validation on all endpoints
- [ ] SQL/NoSQL injection protection
- [ ] File upload security
- [ ] Error handling without information disclosure
- [ ] SSL/TLS verification enabled
- [ ] Dependency vulnerability scanning
- [ ] Regular security audits
- [ ] Security testing in CI/CD

---

## Tools for Security Scanning

1. **Dependency Scanning:**
   - `pip-audit` - Scan Python dependencies
   - `safety` - Check for known vulnerabilities

2. **Secret Scanning:**
   - `git-secrets` - Prevent committing secrets
   - `truffleHog` - Find secrets in git history

3. **Code Analysis:**
   - `bandit` - Python security linter
   - `semgrep` - Security-focused static analysis

4. **Runtime Security:**
   - `OWASP ZAP` - API security testing
   - `Burp Suite` - Web application security testing

---

**Report Generated:** 2024-12-19  
**Next Review:** After implementing critical fixes

