from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole, UserStatus

class UserCreateSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    role: UserRole = Field(UserRole.USER, description="User role")
    status: UserStatus = Field(UserStatus.ACTIVE, description="User status")
    company_id: Optional[int] = Field(None, description="Associated company ID")

    @validator('username')
    def validate_username(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Username cannot be empty')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain alphanumeric characters, underscores, and hyphens')
        return v
        
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        # Add more password validation rules as needed
        return v

class UserUpdateSchema(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    company_id: Optional[int] = None

    @validator('first_name')
    def validate_first_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('First name cannot be empty')
        return v

    @validator('last_name')
    def validate_last_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Last name cannot be empty')
        return v

class UserProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None

class UserPasswordUpdateSchema(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('New password must be at least 8 characters long')
        return v

class UserLoginSchema(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")

class UserResponseSchema(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    company_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class UserListResponseSchema(BaseModel):
    users: list[UserResponseSchema]
    total: int
    page: int
    limit: int
    total_pages: int