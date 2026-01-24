from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime

class ContextCreateSchema(BaseModel):
    context_code: str = Field(..., description="Context code")
    context_name: str = Field(..., description="Context name")
    active: bool = Field(..., description="Active status")
    questions: list = Field(..., description="Questions")
    data_type: str = Field(..., description="data type")
    validation_rules: dict = Field(..., description="Validation rules")
    ai_metadata: dict = Field(..., description="AI Metadata")

    @validator('context_code')
    def validate_context_code(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Context code cannot be empty')
        if len(v) > 10:
            raise ValueError('Context code cannot exceed 10 characters')
        return v.strip().upper()

    @validator('context_name')
    def validate_context_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Context name cannot be empty')
        if len(v) > 100:
            raise ValueError('Context name cannot exceed 100 characters')
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
class ContextUpdateSchema(BaseModel):
    context_name: Optional[str] = None
    active: Optional[bool] = None
    questions: Optional[list] = None
    data_type: Optional[str] = None
    validation_rules: Optional[dict] = None
    ai_metadata: Optional[dict] = None

    @validator('context_name')
    def validate_context_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError('Context name cannot be empty')
            if len(v) > 100:
                raise ValueError('Context name cannot exceed 100 characters')
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
    context_code: str
    context_name: str
    active: bool
    questions: list
    data_type: str
    validation_rules: dict
    ai_metadata: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True