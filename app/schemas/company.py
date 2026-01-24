from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class CompanyCreateSchema(BaseModel):
    company_code: str = Field(..., description="Company code")
    company_name: str = Field(..., description="Company name")
    active: bool = Field(True, description="Active status")

    @validator('company_code')
    def validate_company_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Company code cannot be empty')
        if len(v) > 10:
            raise ValueError('Company code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('company_name')
    def validate_company_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Company name cannot be empty')
        if len(v) > 100:
            raise ValueError('Company name cannot exceed 100 characters')
        return v.strip()

class CompanyUpdateSchema(BaseModel):
    company_name: Optional[str] = None
    active: Optional[bool] = None

    @validator('company_name')
    def validate_company_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Company name cannot be empty')
            if len(v) > 100:
                raise ValueError('Company name cannot exceed 100 characters')
        return v

class CompanyResponseSchema(BaseModel):
    id: int
    company_code: str
    company_name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True