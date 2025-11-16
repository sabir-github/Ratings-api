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

class ProductBase(BaseModel):
    product_code: str = Field(..., description="Product code")
    product_name: str = Field(..., description="Product name")
    lob_id: int = Field(..., description="Lob ID")
    active: bool = Field(..., description="Active status")

class ProductCreate(ProductBase):
    id: Optional[int] = Field(None, description="Product ID (auto-generated if not provided)")

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    active: Optional[bool] = None

class ProductInDB(ProductBase):
    id: int = Field(..., description="Product ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class ProductResponse(ProductInDB):
    pass