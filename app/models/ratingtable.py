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
    table_name: str = Field(..., description="Table name (mandatory)")
    table_type: Optional[str] = Field(None, description="Table type (optional)")
    active: bool = Field(..., description="Active status")
    version: float = Field(..., description="Version")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    data: list = Field(default_factory=list, description="Table Data")
    company: int = Field(..., description="Company ID")
    lob: int = Field(..., description="Lob ID")
    state: int = Field(..., description="State ID")
    product: int = Field(..., description="Product ID")
    context: Optional[int] = Field(None, description="Context ID (optional)")
    lookup_config: dict = Field(default_factory=dict, description="Lookup config")
    ai_metadata: dict = Field(default_factory=dict, description="AI Metadata")

class RatingTableCreate(RatingTableBase):
    pass

class RatingUpdate(BaseModel):
    table_name: Optional[str] = None
    table_type: Optional[str] = None
    active: Optional[bool] = None
    #version: Optional[float] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    #data: Optional[list] = None
    company: Optional[int] = None
    lob: Optional[int] = None
    state: Optional[int] = None
    product: Optional[int] = None
    context: Optional[int] = None
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