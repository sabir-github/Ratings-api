from pydantic import BaseModel, Field
from typing import Dict, Any, Union, Optional

class CalculationRequest(BaseModel):
    """
    Schema for calculation request.
    Allows passing variables as top-level keys in the JSON payload.
    The 'expression' key is mandatory.
    """
    model_config = {"extra": "allow"}
    
    expression: str = Field(..., description="The mathematical expression to evaluate (e.g., 'x + y * 2')")

class CalculationResponse(BaseModel):
    """
    Schema for calculation response.
    """
    result: Union[int, float]
    expression: str
    variables: Dict[str, Any]
    status: str = "success"
    message: Optional[str] = None

