from pydantic import BaseModel, Field
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

class RatingManualBase(BaseModel):
    manual_name: str = Field(..., description="Manual name (mandatory)")
    active: bool = Field(..., description="Active status")
    version: Optional[float] = Field(None, description="Version")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    company: int = Field(..., description="Company ID")
    lob: int = Field(..., description="Lob ID")
    state: int = Field(..., description="State ID")
    product: int = Field(..., description="Product ID")
    entity: int = Field(..., description="Legal entity ID (mandatory)")
    priority: int = Field(..., description="Priority")

class RatingManualCreate(RatingManualBase):
    pass

class RatingManualUpdate(BaseModel):
    """Only these fields can be updated: active, effective_date, expiration_date, priority"""
    active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    priority: Optional[int] = None

class RatingManualInDB(RatingManualBase):
    id: int = Field(..., description="Manual ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class RatingManualResponse(RatingManualInDB):
    pass

