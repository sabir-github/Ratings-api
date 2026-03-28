from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class LobCreateSchema(BaseModel):
    lob_code: str = Field(..., description="Lob code")
    lob_name: str = Field(..., description="Lob name")
    lob_abbreviation: str = Field(..., description="Lob abbreviation")
    active: bool = Field(True, description="Active status")

    @validator('lob_code')
    def validate_lob_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Lob code cannot be empty')
        if len(v) > 10:
            raise ValueError('Lob code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('lob_name')
    def validate_lob_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Lob name cannot be empty')
        if len(v) > 100:
            raise ValueError('Lob name cannot exceed 100 characters')
        return v.strip()

class LobUpdateSchema(BaseModel):
    lob_name: Optional[str] = None
    active: Optional[bool] = None

    @validator('lob_name')
    def validate_lob_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Lob name cannot be empty')
            if len(v) > 100:
                raise ValueError('Lob name cannot exceed 100 characters')
        return v

class LobResponseSchema(BaseModel):
    id: int
    lob_code: str
    lob_name: str
    lob_abbreviation: str
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True