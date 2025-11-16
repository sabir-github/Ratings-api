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

class LobBase(BaseModel):
    lob_code: str = Field(..., description="Lob code")
    lob_name: str = Field(..., description="Lob name")
    lob_abbreviation: str = Field(..., description="Lob abbreviation")
    active: bool = Field(..., description="Active status")

class LobCreate(LobBase):
    id: Optional[int] = Field(None, description="Lob ID (auto-generated if not provided)")

class LobUpdate(BaseModel):
    lob_name: Optional[str] = None
    lob_abbreviation: Optional[str] = None
    active: Optional[bool] = None

class LobInDB(LobBase):
    id: int = Field(..., description="Lob ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class LobResponse(LobInDB):
    pass