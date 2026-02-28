from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime


class LegalEntityCreateSchema(BaseModel):
    company_id: int = Field(..., description="Links to parent Companies record")
    legal_name: str = Field(..., description="Full official name used in legal filings")
    entity_type: Optional[str] = Field(None, description="Category: Corporation, Partnership, Trust, etc.")
    identifier: Optional[str] = Field(None, description="Legal Entity Identifier (20-character LEI code)")
    jurisdiction: Optional[str] = Field(None, description="State or country where entity is legally registered")
    registration_number: Optional[str] = Field(None, description="Official ID issued by government registrar")
    active: bool = Field(True, description="Status of Legal Entity")

    @validator("company_id")
    def validate_company_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError("company_id must be a positive integer")
        return v

    @validator("legal_name")
    def validate_legal_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Legal name cannot be empty")
        if len(v.strip()) > 200:
            raise ValueError("Legal name cannot exceed 200 characters")
        return v.strip()

class LegalEntityUpdateSchema(BaseModel):
    legal_name: Optional[str] = None
    entity_type: Optional[str] = None
    identifier: Optional[str] = None
    jurisdiction: Optional[str] = None
    registration_number: Optional[str] = None
    active: Optional[bool] = None


class LegalEntityResponseSchema(BaseModel):
    id: int
    company_id: int
    legal_name: str
    entity_type: Optional[str] = None
    identifier: Optional[str] = None
    jurisdiction: Optional[str] = None
    registration_number: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
