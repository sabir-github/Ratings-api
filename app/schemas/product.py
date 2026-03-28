from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class ProductCreateSchema(BaseModel):
    product_code: str = Field(..., description="product code")
    product_name: str = Field(..., description="product name")
    lob_id: int = Field(..., description="Lob ID")
    active: bool = Field(True, description="Active status")

    @validator('product_code')
    def validate_product_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Product code cannot be empty')
        if len(v) > 10:
            raise ValueError('Product code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('product_name')
    def validate_product_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Product name cannot be empty')
        if len(v) > 100:
            raise ValueError('Product name cannot exceed 100 characters')
        return v.strip()

    @validator('lob_id')
    def validate_lob_id(cls, v):
        if not v or v == 0:
            raise ValueError('Lob ID cannot be empty')
        return v

class ProductUpdateSchema(BaseModel):
    product_name: Optional[str] = None
    active: Optional[bool] = None

    @validator('product_name')
    def validate_lob_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Product name cannot be empty')
            if len(v) > 100:
                raise ValueError('Product name cannot exceed 100 characters')
        return v

class ProductResponseSchema(BaseModel):
    id: int
    product_code: str
    product_name: str
    active: bool
    lob_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True