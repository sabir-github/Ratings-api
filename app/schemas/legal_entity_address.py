from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime


class LegalEntityAddressCreateSchema(BaseModel):
    legal_entity_id: int = Field(..., description="Links to LegalEntity")
    address_type: str = Field(..., description="e.g., Registered, Physical, Mailing")
    full_address: Optional[str] = Field(None, description="Complete address as string")
    street1: Optional[str] = Field(None, description="Street line 1")
    street2: Optional[str] = Field(None, description="Street line 2")
    city: Optional[str] = Field(None, description="City")
    state_province: Optional[str] = Field(None, description="State or Province")
    postal_code: Optional[str] = Field(None, description="ZIP or PIN")
    country_code: Optional[str] = Field(None, description="ISO Alpha-2 country code")

    @validator("legal_entity_id")
    def validate_legal_entity_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError("legal_entity_id must be a positive integer")
        return v

    @validator("address_type")
    def validate_address_type(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Address type cannot be empty")
        if len(v.strip()) > 50:
            raise ValueError("Address type cannot exceed 50 characters")
        return v.strip()


class LegalEntityAddressUpdateSchema(BaseModel):
    address_type: Optional[str] = None
    full_address: Optional[str] = None
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None


class LegalEntityAddressResponseSchema(BaseModel):
    id: int
    legal_entity_id: int
    address_type: str
    full_address: Optional[str] = None
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
