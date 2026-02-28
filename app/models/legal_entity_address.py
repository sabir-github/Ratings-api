from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class LegalEntityAddressBase(BaseModel):
    legal_entity_id: int = Field(..., description="Links to LegalEntity")
    address_type: str = Field(..., description="e.g., Registered, Physical, Mailing")
    full_address: Optional[str] = Field(None, description="Complete address as string")
    street1: Optional[str] = Field(None, description="Street line 1")
    street2: Optional[str] = Field(None, description="Street line 2")
    city: Optional[str] = Field(None, description="City")
    state_province: Optional[str] = Field(None, description="State or Province")
    postal_code: Optional[str] = Field(None, description="ZIP or PIN")
    country_code: Optional[str] = Field(None, description="ISO Alpha-2 country code")


class LegalEntityAddressCreate(LegalEntityAddressBase):
    pass


class LegalEntityAddressUpdate(BaseModel):
    address_type: Optional[str] = None
    full_address: Optional[str] = None
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None


class LegalEntityAddressInDB(LegalEntityAddressBase):
    id: int = Field(..., description="Address ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True


class LegalEntityAddressResponse(LegalEntityAddressInDB):
    pass
