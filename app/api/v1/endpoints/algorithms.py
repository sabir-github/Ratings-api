from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from app.services.algorithm_service import algorithm_service
from app.schemas.algorithm import AlgorithmCreateSchema, AlgorithmUpdateSchema, AlgorithmResponseSchema
from app.core.security import get_current_user
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_algorithm(
    algorithm: AlgorithmCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new algorithm (ID auto-generated if not provided)
    Returns message if no content changes found, or creates new record with content comparison if changes exist"""
    try:
        result = await algorithm_service.create_algorithm(algorithm)
        # If no changes found, return 200 with message
        if "message" in result and "No changes found" in result["message"]:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=result
            )
        # Otherwise return 201 with created record
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=result
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating algorithm: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_algorithms", status_code=status.HTTP_201_CREATED)
async def create_bulk_algorithms(
    algorithms: List[AlgorithmCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Bulk create algorithms (IDs auto-generated if not provided)
    Returns list of results with content comparison for each record"""
    try:
        results = await algorithm_service.bulk_create_algorithms(algorithms)
        # Determine overall status code
        if any(r.get("error") for r in results):
            status_code = status.HTTP_400_BAD_REQUEST
        elif all(r.get("skipped") for r in results):
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_201_CREATED
        
        return JSONResponse(
            status_code=status_code,
            content=results
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating algorithms: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{algorithm_id}", response_model=AlgorithmResponseSchema)
async def get_algorithm(
    algorithm_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get an algorithm by ID"""
    algorithm = await algorithm_service.get_algorithm(algorithm_id)
    if not algorithm:
        raise HTTPException(status_code=404, detail="Algorithm not found")
    return algorithm

@router.get("/", response_model=List[AlgorithmResponseSchema])
async def get_algorithms(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    algorithm_name: Optional[str] = Query(None, description="Filter by algorithm name (partial match)"),
    algorithm_type: Optional[str] = Query(None, description="Filter by algorithm type"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all algorithms with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if algorithm_name:
        filter_by["algorithm_name"] = algorithm_name
    if algorithm_type:
        filter_by["algorithm_type"] = algorithm_type
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    
    return await algorithm_service.get_algorithms(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{algorithm_id}", response_model=AlgorithmResponseSchema)
async def update_algorithm(
    algorithm_id: int,
    algorithm_update: AlgorithmUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update an algorithm"""
    try:
        updated_algorithm = await algorithm_service.update_algorithm(algorithm_id, algorithm_update)
        if not updated_algorithm:
            raise HTTPException(status_code=404, detail="Algorithm not found")
        return updated_algorithm
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating algorithm: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{algorithm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_algorithm(
    algorithm_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete an algorithm"""
    try:
        success = await algorithm_service.delete_algorithm(algorithm_id)
        if not success:
            raise HTTPException(status_code=404, detail="Algorithm not found")
    except Exception as e:
        logger.error(f"Error deleting algorithm: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{algorithm_id}/exists")
async def check_algorithm_exists(
    algorithm_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if an algorithm exists"""
    algorithm = await algorithm_service.get_algorithm(algorithm_id)
    return {"exists": algorithm is not None}

@router.get("/info/count")
async def get_algorithms_count(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    algorithm_name: Optional[str] = Query(None, description="Filter by algorithm name (partial match)"),
    algorithm_type: Optional[str] = Query(None, description="Filter by algorithm type"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get count of algorithms with optional filters"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if algorithm_name:
        filter_by["algorithm_name"] = algorithm_name
    if algorithm_type:
        filter_by["algorithm_type"] = algorithm_type
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    
    count = await algorithm_service.count_algorithms(filter_by=filter_by)
    return {"count": count}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await algorithm_service.get_last_algorithm_id()
    return {
        "last_algorithm_id": last_id,
        "next_algorithm_id": last_id + 1 if last_id else 100000000
    }

