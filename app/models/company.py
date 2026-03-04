from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class HQAddress(BaseModel):
    """Structured HQ address for the main corporate office."""
    Street1: Optional[str] = Field(None, description="Primary street info (e.g., 123 Business Way)")
    Street2: Optional[str] = Field(None, description="Suite, Floor, or Unit number")
    City: Optional[str] = Field(None, description="Official city name")
    State_Province: Optional[str] = Field(None, description="State or Province code (e.g., NY, KA)")
    PostalCode: Optional[str] = Field(None, description="ZIP or PIN code")
    CountryCode: Optional[str] = Field(None, description="ISO Alpha-2 code (e.g., US, IN, GB)")

    class Config:
        extra = "ignore"  # Ignore extra fields from DB


class CompanyBase(BaseModel):
    company_code: str = Field(..., description="Company code")
    company_name: str = Field(..., description="Company name")
    active: bool = Field(..., description="Active status")
    hq_address: Optional[HQAddress] = Field(None, description="Location of the main corporate office (structured)")
    tax_id: Optional[str] = Field(None, description="The primary tax identification number for the parent group")

    @validator("hq_address", pre=True)
    def coerce_hq_address(cls, v):
        """Coerce legacy string hq_address to None (migrated from flat string)."""
        if v is None:
            return None
        if isinstance(v, str):
            return None  # Legacy string format - treat as None
        return v

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    active: Optional[bool] = None
    hq_address: Optional[HQAddress] = None
    tax_id: Optional[str] = None

class CompanyInDB(CompanyBase):
    id: int = Field(..., description="Company ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class CompanyResponse(CompanyInDB):
    pass