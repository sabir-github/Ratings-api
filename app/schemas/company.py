from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime


class HQAddressSchema(BaseModel):
    """Structured HQ address for the main corporate office."""
    Street1: Optional[str] = Field(None, description="Primary street info (e.g., 123 Business Way)")
    Street2: Optional[str] = Field(None, description="Suite, Floor, or Unit number")
    City: Optional[str] = Field(None, description="Official city name")
    State_Province: Optional[str] = Field(None, description="State or Province code (e.g., NY, KA)")
    PostalCode: Optional[str] = Field(None, description="ZIP or PIN code")
    CountryCode: Optional[str] = Field(None, description="ISO Alpha-2 code (e.g., US, IN, GB)")

    class Config:
        extra = "ignore"


class CompanyCreateSchema(BaseModel):
    company_code: str = Field(..., description="Company code")
    company_name: str = Field(..., description="Company name")
    active: bool = Field(True, description="Active status")
    hq_address: Optional[HQAddressSchema] = Field(None, description="Location of the main corporate office (structured address)")
    tax_id: Optional[str] = Field(None, description="The primary tax identification number for the parent group")

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

    @validator('hq_address', pre=True)
    def validate_hq_address_create(cls, v):
        if v is None:
            return None
        if isinstance(v, dict) and not any(x for x in v.values() if x is not None and x != ''):
            return None
        return v

    @validator('tax_id')
    def validate_tax_id(cls, v):
        if v is not None and v.strip():
            if len(v.strip()) > 50:
                raise ValueError('Tax ID cannot exceed 50 characters')
            return v.strip()
        return None

class CompanyUpdateSchema(BaseModel):
    company_name: Optional[str] = None
    active: Optional[bool] = None
    hq_address: Optional[HQAddressSchema] = None
    tax_id: Optional[str] = None

    @validator('hq_address', pre=True)
    def validate_hq_address_update(cls, v):
        if v is None:
            return None
        if isinstance(v, dict) and not any(x for x in v.values() if x is not None and x != ''):
            return None
        return v

    @validator('company_name')
    def validate_company_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Company name cannot be empty')
            if len(v) > 100:
                raise ValueError('Company name cannot exceed 100 characters')
        return v

    @validator('tax_id')
    def validate_tax_id(cls, v):
        if v is not None and v.strip():
            if len(v.strip()) > 50:
                raise ValueError('Tax ID cannot exceed 50 characters')
            return v.strip()
        return None

class CompanyResponseSchema(BaseModel):
    id: int
    company_code: str
    company_name: str
    active: bool
    hq_address: Optional[HQAddressSchema] = None
    tax_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @validator("hq_address", pre=True)
    def coerce_hq_address_response(cls, v):
        """Coerce legacy string hq_address to None."""
        if v is None or isinstance(v, str):
            return None
        return v

    class Config:
        from_attributes = True