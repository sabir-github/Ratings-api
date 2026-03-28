from fastapi import APIRouter, HTTPException, status
from app.schemas.calculation import CalculationRequest, CalculationResponse
from app.services.evaluate_expression import evaluate_expression as service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=CalculationResponse)
async def evaluate_expression_api(request: CalculationRequest):
    """
    Evaluate a mathematical expression using variables provided in the payload.
    
    Example payload:
    ```json
    {
        "x": 10,
        "y": 20,
        "expression": "x + y * 1.5"
    }
    ```
    """
    try:
        # Extract variables (all extra fields from the request)
        data = request.model_dump()
        expression = data.pop("expression")
        variables = data
        
        logger.info(f"Evaluating expression: {expression} with variables: {variables}")
        
        result = service.evaluate(expression, variables)
        
        return CalculationResponse(
            result=result,
            expression=expression,
            variables=variables
        )
    except ValueError as e:
        logger.error(f"Calculation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error during calculation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during calculation"
        )

