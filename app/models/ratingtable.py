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

class RatingTableBase(BaseModel):
    table_code: str = Field(..., description="Table code")
    table_name: str = Field(..., description="Table name")
    table_type: str = Field(..., description="Table type")
    active: bool = Field(..., description="Active status")
    version: float = Field(..., description="Version")
    effective_date:datetime = Field(..., description="Effective Date")
    expiration_date:datetime = Field(..., description="Expiration Date")
    data:list = Field(..., description="Table Data")
    company: dict =  Field(..., description="Company")
    lob: dict     =  Field(..., description="Lob")
    state: dict   = Field(..., description="State")
    product: dict =  Field(..., description="Product")
    context: dict = Field(..., description="Context")
    lookup_config: dict = Field(..., description="Lookup config")
    ai_metadata: dict = Field(..., description="AI Metadata")

class RatingTableCreate(RatingTableBase):
    id: Optional[int] = Field(None, description="Rating ID (auto-generated if not provided)")

class RatingUpdate(BaseModel):
    table_name: Optional[str] = None
    table_type: Optional[str] = None
    active: Optional[bool] = None
    #version: Optional[float] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    #data: Optional[list] = None
    company: Optional[dict] = None
    lob: Optional[dict] = None
    state: Optional[dict] = None
    product: Optional[dict] = None
    context: Optional[dict] = None
    lookup_config: Optional[dict] = None
    ai_metadata: Optional[dict] = None

class RatingTableInDB(RatingTableBase):
    id: int = Field(..., description="Table ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class RatingTableResponse(RatingTableInDB):
    pass