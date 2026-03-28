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

class ContextBase(BaseModel):
    context_code: str = Field(..., description="Context code")
    context_name: str = Field(..., description="Context name")
    active: bool = Field(..., description="Active status")
    questions: list = Field(..., description="Questions")
    data_type: str = Field(..., description="data type")
    validation_rules: dict = Field(..., description="Validation rules")
    ai_metadata: dict = Field(..., description="AI Metadata")
    

class ContextCreate(ContextBase):
    pass

class ContextUpdate(BaseModel):
    state_name: Optional[str] = None
    active: Optional[bool] = None
    context_name: Optional[str] = None
    questions: Optional[list] = None
    data_type: Optional[str] = None
    validation_rules: Optional[dict] = None
    ai_metadata: Optional[dict] = None

class ContextInDB(ContextBase):
    id: int = Field(..., description="Context ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class ContextResponse(ContextInDB):
    pass