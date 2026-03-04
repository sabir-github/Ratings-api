from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
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

class AlgorithmBase(BaseModel):
    algorithm_name: str = Field(..., description="Algorithm name (mandatory)")
    algorithm_type: Optional[str] = Field(None, description="Algorithm type (optional)")
    company: int = Field(..., description="Company ID")
    lob: int = Field(..., description="Lob ID")
    state: int = Field(..., description="State ID")
    product: int = Field(..., description="Product ID")
    entity: int = Field(..., description="Legal entity ID (mandatory)")
    version: Optional[float] = Field(None, description="Version")
    effective_date: Optional[datetime] = Field(None, description="Effective Date (optional)")
    expiration_date: Optional[datetime] = Field(None, description="Expiration Date (optional)")
    active: bool = Field(..., description="Active status")
    required_tables: List[int] = Field(..., description="List of Rating Table IDs (mandatory)")
    formula: Dict[str, Any] = Field(..., description="Formula object (mandatory)")
    calculation_steps: Optional[List[Dict[str, Any]]] = Field(None, description="Calculation steps (optional)")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables object (optional)")

class AlgorithmCreate(AlgorithmBase):
    pass

class AlgorithmUpdate(BaseModel):
    """Fields that can be updated: algorithm_type, active, effective_date, expiration_date, calculation_steps, variables"""
    algorithm_type: Optional[str] = None
    active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    calculation_steps: Optional[List[Dict[str, Any]]] = None
    variables: Optional[Dict[str, Any]] = None

class AlgorithmInDB(AlgorithmBase):
    id: int = Field(..., description="Algorithm ID")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {ObjectId: str}
        from_attributes = True

class AlgorithmResponse(AlgorithmInDB):
    pass

