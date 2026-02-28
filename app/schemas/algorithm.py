from pydantic import BaseModel, validator, model_validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AlgorithmCreateSchema(BaseModel):
    algorithm_name: str = Field(..., description="Algorithm name (mandatory)")
    algorithm_type: Optional[str] = Field(None, description="Algorithm type (optional)")
    company: int = Field(..., description="Company ID (mandatory)")
    lob: int = Field(..., description="Lob ID (mandatory)")
    state: int = Field(..., description="State ID (mandatory)")
    product: int = Field(..., description="Product ID (mandatory)")
    entity: int = Field(..., description="Legal entity ID (mandatory)")
    version: Optional[float] = Field(None, description="Version (optional, defaults to 1.0)")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional, defaults to current datetime if not provided)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    active: bool = Field(True, description="Active status")
    required_tables: List[int] = Field(..., description="List of Rating Table IDs associated to this record (mandatory)")
    formula: Dict[str, Any] = Field(..., description="Formula object with expression, description, and components (mandatory)")
    calculation_steps: Optional[List[Dict[str, Any]]] = Field(None, description="List of calculation step objects (optional)")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables object with input_variables, intermediate_variables, and output_variables (optional)")

    @validator('algorithm_name')
    def validate_algorithm_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Algorithm name cannot be empty')
        if len(v) > 200:
            raise ValueError('Algorithm name cannot exceed 200 characters')
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
    
    @validator('required_tables', pre=True)
    def coerce_required_tables(cls, v):
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

    @validator('required_tables')
    def validate_required_tables(cls, v):
        if v is None:
            raise ValueError('Required tables cannot be None')
        if not isinstance(v, list):
            raise ValueError('Required tables must be a list')
        for table_id in v:
            if not isinstance(table_id, int) or table_id <= 0:
                raise ValueError('All required table IDs must be positive integers')
        return v
    
    @validator('formula')
    def validate_formula(cls, v):
        if v is None:
            raise ValueError('Formula cannot be None')
        if not isinstance(v, dict):
            raise ValueError('Formula must be a dictionary')
        return v
    
    @model_validator(mode='after')
    def validate_expiration_date(self):
        # Only validate if both dates are provided
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class AlgorithmUpdateSchema(BaseModel):
    """Fields that can be updated: algorithm_type, active, effective_date, expiration_date, calculation_steps, variables"""
    algorithm_type: Optional[str] = None
    active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    calculation_steps: Optional[List[Dict[str, Any]]] = None
    variables: Optional[Dict[str, Any]] = None

    @model_validator(mode='after')
    def validate_expiration_date(self):
        if self.effective_date is not None and self.expiration_date is not None:
            if self.expiration_date < self.effective_date:
                raise ValueError('expiration_date cannot be less than effective_date')
        return self

class AlgorithmResponseSchema(BaseModel):
    id: int
    algorithm_name: str
    algorithm_type: Optional[str]
    company: int
    lob: int
    state: int
    product: int
    entity: int
    version: float
    effective_date: datetime
    expiration_date: Optional[datetime]
    active: bool
    required_tables: List[int]
    formula: Dict[str, Any]
    calculation_steps: List[Dict[str, Any]]
    variables: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

