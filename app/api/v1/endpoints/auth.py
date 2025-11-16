from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel
import secrets
import logging

from app.schemas.user import UserLoginSchema, UserCreateSchema
from app.services.user_service import user_service
from app.core.security import (
    create_access_token, 
    create_refresh_token, 
    verify_token, 
    get_password_hash
)
from app.core.config import settings
from app.models.user import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    try:
        # Authenticate user
        user = await user_service.authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is not active",
            )
        
        # Update last login
        await user_service.update_last_login(user["id"])
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": user["username"], "user_id": user["id"], "role": user["role"]}
        )
        refresh_token = create_refresh_token(
            data={"sub": user["username"], "user_id": user["id"]}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/register", response_model=dict)
async def register(
    user_data: UserCreateSchema
):
    """
    Register a new user
    """
    try:
        # Check if registration is open to public (or only admins can register)
        # For now, we'll allow public registration but you can modify this logic
        
        # Create user
        user = await user_service.create_user(user_data)
        
        return {
            "message": "User registered successfully",
            "user_id": user["id"]
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str
):
    """
    Refresh access token using refresh token
    """
    try:
        # Verify refresh token
        payload = verify_token(refresh_token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        username = payload.get("sub")
        user_id = payload.get("user_id")
        
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if user is active
        if user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is not active"
            )
        
        # Create new access token
        access_token = create_access_token(
            data={"sub": user["username"], "user_id": user["id"], "role": user["role"]}
        )
        
        new_refresh_token = create_refresh_token(
            data={"sub": user["username"], "user_id": user["id"]}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )

@router.post("/logout")
async def logout(
    current_user: dict = Depends(oauth2_scheme)
):
    """
    Logout user (client should discard tokens)
    """
    # In a stateless JWT system, logout is handled client-side
    # by discarding the tokens. For server-side invalidation,
    # you would need a token blacklist.
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: dict = Depends(oauth2_scheme)
):
    """
    Get current user information
    """
    try:
        # Verify token and get user data
        payload = verify_token(current_user)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove sensitive data
        user.pop("hashed_password", None)
        
        return user
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/forgot-password")
async def forgot_password(
    email: str
):
    """
    Initiate password reset process
    """
    try:
        # Check if user exists
        user = await user_service.get_user_by_email(email)
        if not user:
            # Don't reveal whether email exists or not
            return {"message": "If the email exists, a reset link has been sent"}
        
        # In a real application, you would:
        # 1. Generate a reset token
        # 2. Send email with reset link
        # 3. Store reset token in database with expiration
        
        # For now, we'll just return a success message
        return {"message": "If the email exists, a reset link has been sent"}
    
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str
):
    """
    Reset password using reset token
    """
    try:
        # Verify reset token (you would have a separate verification for this)
        # For now, this is a placeholder implementation
        
        return {"message": "Password reset successfully"}
    except Exception:
        return None

@router.get("/verify-email")
async def verify_email(
    token: str
):
    """
    Verify email address using verification token
    """
    try:
        # In a real application, you would:
        # 1. Verify the token
        # 2. Update user's email verification status
        
        return {"message": "Email verified successfully"}
    
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )

# Password strength validation endpoint
@router.post("/validate-password")
async def validate_password(
    password: str
):
    """
    Validate password strength
    """
    try:
        # Check minimum length only (no maximum length)
        if len(password) < 8:
            return {
                "valid": False,
                "message": "Password must be at least 8 characters long"
            }
        
        # Check for uppercase
        if not any(c.isupper() for c in password):
            return {
                "valid": False,
                "message": "Password must contain at least one uppercase letter"
            }
        
        # Check for lowercase
        if not any(c.islower() for c in password):
            return {
                "valid": False,
                "message": "Password must contain at least one lowercase letter"
            }
        
        # Check for numbers
        if not any(c.isdigit() for c in password):
            return {
                "valid": False,
                "message": "Password must contain at least one number"
            }
        
        # Check for special characters
        if not any(not c.isalnum() for c in password):
            return {
                "valid": False,
                "message": "Password must contain at least one special character"
            }
        
        return {
            "valid": True,
            "message": "Password meets security requirements"
            }
    
    except Exception as e:
        logger.error(f"Password validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Health check endpoint for auth service
@router.get("/health")
async def auth_health():
    """
    Health check for authentication service
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }