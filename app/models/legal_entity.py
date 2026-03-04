from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class LegalEntityBase(BaseModel):
    company_id: int = Field(..., description="Links to parent Companies record")
    legal_name: str = Field(..., description="Full official name used in legal filings")
    entity_type: Optional[str] = Field(None, description="Category: Corporation, Partnership, Trust, etc.")
    identifier: Optional[str] = Field(None, description="Legal Entity Identifier (20-character LEI code)")
    jurisdiction: Optional[str] = Field(None, description="State or country where entity is legally registered")
    registration_number: Optional[str] = Field(None, description="Official ID issued by government registrar")
    active: bool = Field(True, description="Status of Legal Entity")


class LegalEntityCreate(LegalEntityBase):
    pass


class LegalEntityUpdate(BaseModel):
    legal_name: Optional[str] = None
    entity_type: Optional[str] = None
    identifier: Optional[str] = None
    jurisdiction: Optional[str] = None
    registration_number: Optional[str] = None
    active: Optional[bool] = None


class LegalEntityInDB(LegalEntityBase):
    id: int = Field(..., description="Legal Entity ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True


class LegalEntityResponse(LegalEntityInDB):
    pass
