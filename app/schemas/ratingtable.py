from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class RatingTableCreateSchema(BaseModel):
    id: int = Field(None, description="Table ID (optional, auto-generated if not provided)")
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

    @validator('table_code')
    def validate_table_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Table code cannot be empty')
        if len(v) > 10:
            raise ValueError('Table code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('table_name')
    def validate_table_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Table name cannot be empty')
        if len(v) > 100:
            raise ValueError('Table name cannot exceed 100 characters')
        return v.strip()
    """
    @validator('context_questions')
    def validate_context_questkions(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Context questions cannot be empty')
        if len(v) > 100:
            raise ValueError('Context questions cannot exceed 100 characters')
        return v
    """
class RatingTableUpdateSchema(BaseModel):
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

    @validator('table_name')
    def validate_table_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Table name cannot be empty')
            if len(v) > 100:
                raise ValueError('Table name cannot exceed 100 characters')
        return v
    """
    @validator('context_questions')
    def validate_context_questions(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Context questions cannot be empty')
        if len(v) > 100:
            raise ValueError('Context questions cannot exceed 100 characters')
        return v
    """
    
class ContextResponseSchema(BaseModel):
    id: int
    table_name: str
    table_type: str
    active: bool
    version: float
    effective_date: datetime
    expiration_date: datetime
    data: list
    company: dict
    lob: dict
    state: dict
    product: dict
    context: dict
    lookup_config: dict
    ai_metadata: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True