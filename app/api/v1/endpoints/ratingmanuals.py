from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.services.ratingmanual_service import ratingmanual_service
from app.schemas.ratingmanual import RatingManualCreateSchema, RatingManualUpdateSchema, RatingManualResponseSchema
from app.core.security import get_current_user
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ratingmanual(
    ratingmanual: RatingManualCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new rating manual (ID auto-generated if not provided)
    Returns message if no ratingtable changes found, or creates new record with ratingtable comparison if changes exist"""
    try:
        result = await ratingmanual_service.create_ratingmanual(ratingmanual)
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
        logger.error(f"Error creating rating manual: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_ratingmanuals", status_code=status.HTTP_201_CREATED)
async def create_bulk_ratingmanuals(
    ratingmanuals: List[RatingManualCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Bulk create new rating manuals (IDs auto-generated if not provided)
    Returns list of results with ratingtable comparison for each record"""
    try:
        results = await ratingmanual_service.bulk_create_ratingmanuals(ratingmanuals)
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
        logger.error(f"Error creating rating manuals: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[RatingManualResponseSchema])
async def get_ratingmanuals(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    manual_name: Optional[str] = Query(None, description="Filter by manual name (partial match)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    ratingtable_id: Optional[int] = Query(None, description="Filter by Rating Table ID"),
    effective_date: Optional[datetime] = Query(None, description="Filter by effective date (matches records with this exact date)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all rating manuals with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if manual_name:
        filter_by["manual_name"] = manual_name
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if ratingtable_id is not None:
        filter_by["ratingtable_id"] = ratingtable_id
    if effective_date is not None:
        # Normalize to start of day (midnight) to match how dates are stored
        normalized_date = effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if normalized_date.tzinfo is None:
            normalized_date = normalized_date.replace(tzinfo=timezone.utc)
        filter_by["effective_date"] = normalized_date
    
    return await ratingmanual_service.get_ratingmanuals(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.get("/info/sequence")
async def get_ratingmanual_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence for rating manuals"""
    last_id = await ratingmanual_service.get_last_ratingmanual_id()
    return {
        "last_ratingmanual_id": last_id,
        "next_ratingmanual_id": last_id + 1 if last_id else 100000000
    }

@router.get("/info/count")
async def get_ratingmanuals_count(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    manual_name: Optional[str] = Query(None, description="Filter by manual name (partial match)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    ratingtable_id: Optional[int] = Query(None, description="Filter by Rating Table ID"),
    effective_date: Optional[datetime] = Query(None, description="Filter by effective date (matches records with this exact date)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get count of rating manuals with optional filters"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if manual_name:
        filter_by["manual_name"] = manual_name
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if ratingtable_id is not None:
        filter_by["ratingtable_id"] = ratingtable_id
    if effective_date is not None:
        # Normalize to start of day (midnight) to match how dates are stored
        normalized_date = effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if normalized_date.tzinfo is None:
            normalized_date = normalized_date.replace(tzinfo=timezone.utc)
        filter_by["effective_date"] = normalized_date
    
    count = await ratingmanual_service.count_ratingmanuals(filter_by=filter_by)
    return {"count": count}

@router.get("/{ratingmanual_id}/exists")
async def check_ratingmanual_exists(
    ratingmanual_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a rating manual exists"""
    ratingmanual = await ratingmanual_service.get_ratingmanual(ratingmanual_id)
    return {"exists": ratingmanual is not None}

@router.get("/{ratingmanual_id}", response_model=RatingManualResponseSchema)
async def get_ratingmanual(
    ratingmanual_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a rating manual by ID"""
    ratingmanual = await ratingmanual_service.get_ratingmanual(ratingmanual_id)
    if not ratingmanual:
        raise HTTPException(status_code=404, detail="Rating manual not found")
    return ratingmanual

@router.put("/{ratingmanual_id}", response_model=RatingManualResponseSchema)
async def update_ratingmanual(
    ratingmanual_id: int,
    ratingmanual_update: RatingManualUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a rating manual"""
    try:
        updated_ratingmanual = await ratingmanual_service.update_ratingmanual(ratingmanual_id, ratingmanual_update)
        if not updated_ratingmanual:
            raise HTTPException(status_code=404, detail="Rating manual not found")
        return updated_ratingmanual
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating rating manual: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{ratingmanual_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ratingmanual(
    ratingmanual_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a rating manual"""
    try:
        success = await ratingmanual_service.delete_ratingmanual(ratingmanual_id)
        if not success:
            raise HTTPException(status_code=404, detail="Rating manual not found")
    except Exception as e:
        logger.error(f"Error deleting rating manual: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

