from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class StateCreateSchema(BaseModel):
    id: Optional[int] = Field(None, description="State ID (optional, auto-generated if not provided)")
    state_code: str = Field(..., description="State code")
    state_name: str = Field(..., description="State name")
    active: bool = Field(True, description="Active status")

    @validator('state_code')
    def validate_state_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('State code cannot be empty')
        if len(v) > 10:
            raise ValueError('State code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('state_name')
    def validate_state_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('State name cannot be empty')
        if len(v) > 100:
            raise ValueError('State name cannot exceed 100 characters')
        return v.strip()

class StateUpdateSchema(BaseModel):
    state_name: Optional[str] = None
    active: Optional[bool] = None

    @validator('state_name')
    def validate_state_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('State name cannot be empty')
            if len(v) > 100:
                raise ValueError('State name cannot exceed 100 characters')
        return v

class StateResponseSchema(BaseModel):
    id: int
    state_code: str
    state_name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True