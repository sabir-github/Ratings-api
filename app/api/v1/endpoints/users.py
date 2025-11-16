from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.user_service import user_service
from app.schemas.user import (
    UserCreateSchema, 
    UserUpdateSchema, 
    UserResponseSchema, 
    UserProfileUpdateSchema,
    UserPasswordUpdateSchema,
    UserListResponseSchema
)
from app.core.security import get_current_user
from app.models.user import UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def verify_admin_access(current_user: dict):
    """Verify that current user has admin access"""
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

@router.post("/", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreateSchema,
    current_user: dict = Depends(get_current_user)
):
    """Create a new user"""
    try:
        # Only admins can create users with admin role
        if user.role == UserRole.ADMIN and current_user.get("role") != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create admin user"
            )
        
        result = await user_service.create_user(user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=UserListResponseSchema)
async def get_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    username: Optional[str] = Query(None, description="Filter by username (partial match)"),
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order"),
    current_user: dict = Depends(get_current_user)
):
    """Get all users with pagination, filtering and sorting"""
    filter_by = {}
    if status:
        filter_by["status"] = status
    if role:
        filter_by["role"] = role
    if username:
        filter_by["username"] = username
    if email:
        filter_by["email"] = email
    if company_id is not None:
        filter_by["company_id"] = company_id
    
    users = await user_service.get_users(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total = await user_service.count_users(filter_by)
    total_pages = (total + limit - 1) // limit
    
    return UserListResponseSchema(
        users=users,
        total=total,
        page=(skip // limit) + 1,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get a user by ID"""
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/username/{username}", response_model=UserResponseSchema)
async def get_user_by_username(
    username: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a user by username"""
    user = await user_service.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/email/{email}", response_model=UserResponseSchema)
async def get_user_by_email(
    email: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a user by email"""
    user = await user_service.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_id: int,
    user_update: UserUpdateSchema,
    current_user: dict = Depends(get_current_user)
):
    """Update a user"""
    # Regular users can only update their own profile
    if current_user.get("role") not in [UserRole.ADMIN.value, UserRole.MANAGER.value]:
        if user_id != current_user.get("id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own profile"
        )
    
    updated_user = await user_service.update_user(user_id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.patch("/{user_id}/profile", response_model=UserResponseSchema)
async def update_user_profile(
    user_id: int,
    profile_update: UserProfileUpdateSchema,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile (for regular users)"""
    # Users can only update their own profile
    if user_id != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
        detail="Can only update your own profile"
    )
    
    updated_user = await user_service.update_user(
        user_id, 
        UserUpdateSchema(**profile_update.dict())
    )
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.patch("/{user_id}/password", status_code=status.HTTP_200_OK)
async def update_user_password(
    user_id: int,
    password_update: UserPasswordUpdateSchema,
    current_user: dict = Depends(get_current_user)
):
    """Update user password"""
    # Users can only update their own password
    if user_id != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
        detail="Can only update your own password"
    )
    
    try:
        success = await user_service.update_user_password(user_id, password_update)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "Password updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a user"""
    # Only admins can delete users
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete users"
        )
    
    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

@router.get("/{user_id}/exists")
async def check_user_exists(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Check if a user exists"""
    user = await user_service.get_user(user_id)
    return {"exists": user is not None}

@router.get("/company/{company_id}", response_model=List[UserResponseSchema])
async def get_users_by_company(
    company_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """Get users by company ID"""
    users = await user_service.get_users_by_company(company_id, skip, limit)
    return users