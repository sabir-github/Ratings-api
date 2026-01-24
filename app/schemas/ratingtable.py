from pydantic import BaseModel, validator, model_validator, Field
from typing import Optional
from datetime import datetime

class RatingTableCreateSchema(BaseModel):
    table_name: str = Field(..., description="Table name (mandatory)")
    table_type: Optional[str] = Field(None, description="Table type (optional)")
    active: bool = Field(True, description="Active status")
    version: Optional[float] = Field(None, description="Version (optional, defaults to 1.0, auto-increments if record with same combination exists)")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional, defaults to current datetime if not provided)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    data: list = Field(default_factory=list, description="Table Data")
    company: int = Field(..., description="Company ID (mandatory)")
    lob: int = Field(..., description="Lob ID (mandatory)")
    state: int = Field(..., description="State ID (mandatory)")
    product: int = Field(..., description="Product ID (mandatory)")
    context: Optional[int] = Field(None, description="Context ID (optional)")
    lookup_config: dict = Field(default_factory=dict, description="Lookup config")
    ai_metadata: dict = Field(default_factory=dict, description="AI Metadata")

    @validator('table_name')
    def validate_table_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Table name cannot be empty')
        if len(v) > 100:
            raise ValueError('Table name cannot exceed 100 characters')
        return v.strip()
    
    @validator('company')
    def validate_company(cls, v):
        if not isinstance(v, int):
            raise ValueError('Company must be an integer ID')
        if v <= 0:
            raise ValueError('Company ID must be a positive integer')
        return v
    
    @validator('lob')
    def validate_lob(cls, v):
        if not isinstance(v, int):
            raise ValueError('Lob must be an integer ID')
        if v <= 0:
            raise ValueError('Lob ID must be a positive integer')
        return v
    
    @validator('state')
    def validate_state(cls, v):
        if not isinstance(v, int):
            raise ValueError('State must be an integer ID')
        if v <= 0:
            raise ValueError('State ID must be a positive integer')
        return v
    
    @validator('product')
    def validate_product(cls, v):
        if not isinstance(v, int):
            raise ValueError('Product must be an integer ID')
        if v <= 0:
            raise ValueError('Product ID must be a positive integer')
        return v
    
    @validator('context')
    def validate_context(cls, v):
        if v is not None:
            if not isinstance(v, int):
                raise ValueError('Context must be an integer ID')
            if v <= 0:
                raise ValueError('Context ID must be a positive integer')
        return v
    
    @model_validator(mode='after')
    def validate_expiration_date(self):
        # Only validate if both dates are provided
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class RatingTableUpdateSchema(BaseModel):
    """Only these fields can be updated: table_type, context, effective_date, expiration_date, active, lookup_config, ai_metadata"""
    table_type: Optional[str] = None
    active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    context: Optional[int] = None
    lookup_config: Optional[dict] = None
    ai_metadata: Optional[dict] = None

    @validator('context')
    def validate_context(cls, v):
        if v is not None:
            if not isinstance(v, int):
                raise ValueError('Context must be an integer ID')
            if v <= 0:
                raise ValueError('Context ID must be a positive integer')
        return v
    
    @model_validator(mode='after')
    def validate_expiration_date(self):
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class RatingTableResponseSchema(BaseModel):
    id: int
    table_name: str
    table_type: Optional[str]
    active: bool
    version: float
    effective_date: datetime
    expiration_date: Optional[datetime]
    data: list
    company: int
    lob: int
    state: int
    product: int
    context: Optional[int]
    lookup_config: dict
    ai_metadata: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True