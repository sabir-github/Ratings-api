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

class StateBase(BaseModel):
    state_code: str = Field(..., description="State code")
    state_name: str = Field(..., description="State name")
    active: bool = Field(..., description="Active status")

class StateCreate(StateBase):
    id: Optional[int] = Field(None, description="State ID (auto-generated if not provided)")

class StateUpdate(BaseModel):
    state_name: Optional[str] = None
    active: Optional[bool] = None

class StateInDB(StateBase):
    id: int = Field(..., description="State ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class StateResponse(StateInDB):
    pass