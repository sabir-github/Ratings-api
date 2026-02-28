from pydantic import BaseModel, validator, model_validator, Field
from typing import Optional, List
from datetime import datetime

class RatingManualCreateSchema(BaseModel):
    manual_name: str = Field(..., description="Manual name (mandatory)")
    active: bool = Field(True, description="Active status")
    version: Optional[float] = Field(None, description="Version (optional, defaults to 1.0, auto-increments if record with same combination exists)")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional, defaults to current datetime if not provided)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    company: int = Field(..., description="Company ID (mandatory)")
    lob: int = Field(..., description="Lob ID (mandatory)")
    state: int = Field(..., description="State ID (mandatory)")
    product: int = Field(..., description="Product ID (mandatory)")
    entity: int = Field(..., description="Legal entity ID (mandatory)")
    ratingtable: List[int] = Field(..., description="List of Rating Table IDs (mandatory)")
    priority: int = Field(..., description="Priority (mandatory)")

    @validator('manual_name')
    def validate_manual_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Manual name cannot be empty')
        if len(v) > 200:
            raise ValueError('Manual name cannot exceed 200 characters')
        return v.strip()

    @validator('company', 'lob', 'state', 'product', 'entity', pre=True)
    def coerce_id_to_int(cls, v):
        """Accept string IDs (e.g. from Gemini/API) and coerce to int."""
        if v is None:
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                pass
        return v

    @validator('company', 'lob', 'state', 'product', 'entity')
    def validate_required_id_fields(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('ID must be a positive integer')
        return v

    @validator('ratingtable', pre=True)
    def coerce_ratingtable_ids(cls, v):
        """Accept list of string or int IDs and coerce to list of int."""
        if v is None:
            return v
        if not isinstance(v, list):
            return v
        out = []
        for item in v:
            if isinstance(item, int):
                out.append(item)
            elif isinstance(item, str):
                try:
                    out.append(int(item.strip()))
                except ValueError:
                    out.append(item)
            else:
                out.append(item)
        return out

    @validator('ratingtable')
    def validate_ratingtable(cls, v):
        if v is None:
            raise ValueError('Rating tables cannot be None')
        if not isinstance(v, list):
            raise ValueError('Rating tables must be a list')
        if len(v) == 0:
            raise ValueError('Rating tables list cannot be empty')
        for table_id in v:
            if not isinstance(table_id, int) or table_id <= 0:
                raise ValueError('All rating table IDs must be positive integers')
        return v
    
    @validator('priority', pre=True)
    def coerce_priority(cls, v):
        """Accept string numbers and coerce to int."""
        if v is None:
            return v
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                pass
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if not isinstance(v, int):
            raise ValueError('Priority must be an integer')
        if v < 0:
            raise ValueError('Priority must be a non-negative integer')
        return v
    
    @model_validator(mode='after')
    def validate_expiration_date(self):
        # Only validate if both dates are provided
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class RatingManualUpdateSchema(BaseModel):
    """Only these fields can be updated: active, effective_date, expiration_date, priority"""
    active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    priority: Optional[int] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None:
            if not isinstance(v, int):
                raise ValueError('Priority must be an integer')
            if v < 0:
                raise ValueError('Priority must be a non-negative integer')
        return v
    
    @model_validator(mode='after')
    def validate_expiration_date(self):
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class RatingManualResponseSchema(BaseModel):
    id: int
    manual_name: str
    active: bool
    version: float
    effective_date: datetime
    expiration_date: Optional[datetime]
    company: int
    lob: int
    state: int
    product: int
    entity: int
    ratingtable: List[int]
    priority: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

