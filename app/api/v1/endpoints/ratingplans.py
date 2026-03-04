from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from app.services.ratingplan_service import ratingplan_service
from app.schemas.ratingplan import RatingPlanCreateSchema, RatingPlanUpdateSchema, RatingPlanResponseSchema
from app.core.security import get_current_user
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ratingplan(
    ratingplan: RatingPlanCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new rating plan (ID auto-generated if not provided)
    Returns message if no algorithm changes found, or creates new record with algorithm comparison if changes exist"""
    try:
        result = await ratingplan_service.create_ratingplan(ratingplan)
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
        logger.error(f"Error creating rating plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_ratingplans", status_code=status.HTTP_201_CREATED)
async def create_bulk_ratingplans(
    ratingplans: List[RatingPlanCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Bulk create new rating plans (IDs auto-generated if not provided)
    Returns list of results with algorithm comparison for each record"""
    try:
        results = await ratingplan_service.bulk_create_ratingplans(ratingplans)
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
        logger.error(f"Error creating rating plans: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[RatingPlanResponseSchema])
async def get_ratingplans(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    plan_name: Optional[str] = Query(None, description="Filter by manual name (partial match)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    algorithm_id: Optional[int] = Query(None, description="Filter by Algorithm ID"),
    entity_id: Optional[int] = Query(None, description="Filter by legal entity ID"),
    effective_date: Optional[Union[datetime, str]] = Query(None, description="Filter by effective date (matches records with this exact date). Can be ISO format string or datetime."),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all rating plans with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if plan_name:
        filter_by["plan_name"] = plan_name
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if algorithm_id is not None:
        filter_by["algorithm_id"] = algorithm_id
    if entity_id is not None:
        filter_by["entity_id"] = entity_id
    if effective_date is not None:
        try:
            # Handle empty string case
            if isinstance(effective_date, str) and effective_date.strip() == "":
                # Skip filter if empty string
                pass
            else:
                # Parse string to datetime if needed
                if isinstance(effective_date, str):
                    effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
                
                # Normalize to start of day (midnight) to match how dates are stored
                normalized_date = effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                if normalized_date.tzinfo is None:
                    normalized_date = normalized_date.replace(tzinfo=timezone.utc)
                filter_by["effective_date"] = normalized_date
        except (AttributeError, TypeError, ValueError) as e:
            # If effective_date is not a valid datetime object, skip the filter
            logger.warning(f"Invalid effective_date value: {effective_date}, skipping filter. Error: {e}")
            pass
    
    return await ratingplan_service.get_ratingplans(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.get("/info/sequence")
async def get_ratingplan_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence for rating plans"""
    last_id = await ratingplan_service.get_last_ratingplan_id()
    return {
        "last_ratingplan_id": last_id,
        "next_ratingplan_id": last_id + 1 if last_id else 100000000
    }

@router.get("/info/count")
async def get_ratingplans_count(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    plan_name: Optional[str] = Query(None, description="Filter by manual name (partial match)"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by State ID"),
    product_id: Optional[int] = Query(None, description="Filter by Product ID"),
    algorithm_id: Optional[int] = Query(None, description="Filter by Rating Table ID"),
    effective_date: Optional[Union[datetime, str]] = Query(None, description="Filter by effective date (matches records with this exact date). Can be ISO format string or datetime."),
    current_user: UserBase = Depends(get_current_user)
):
    """Get count of rating plans with optional filters"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if plan_name:
        filter_by["plan_name"] = plan_name
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if algorithm_id is not None:
        filter_by["algorithm_id"] = algorithm_id
    if effective_date is not None:
        try:
            # Handle empty string case
            if isinstance(effective_date, str) and effective_date.strip() == "":
                # Skip filter if empty string
                pass
            else:
                # Parse string to datetime if needed
                if isinstance(effective_date, str):
                    effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
                
                # Normalize to start of day (midnight) to match how dates are stored
                normalized_date = effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                if normalized_date.tzinfo is None:
                    normalized_date = normalized_date.replace(tzinfo=timezone.utc)
                filter_by["effective_date"] = normalized_date
        except (AttributeError, TypeError, ValueError) as e:
            # If effective_date is not a valid datetime object, skip the filter
            logger.warning(f"Invalid effective_date value: {effective_date}, skipping filter. Error: {e}")
            pass
    
    count = await ratingplan_service.count_ratingplans(filter_by=filter_by)
    return {"count": count}

@router.get("/{ratingplan_id}/exists")
async def check_ratingplan_exists(
    ratingplan_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a rating plan exists"""
    ratingplan = await ratingplan_service.get_ratingplan(ratingplan_id)
    return {"exists": ratingplan is not None}

@router.get("/{ratingplan_id}", response_model=RatingPlanResponseSchema)
async def get_ratingplan(
    ratingplan_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a rating plan by ID"""
    ratingplan = await ratingplan_service.get_ratingplan(ratingplan_id)
    if not ratingplan:
        raise HTTPException(status_code=404, detail="Rating manual not found")
    return ratingplan

@router.put("/{ratingplan_id}", response_model=RatingPlanResponseSchema)
async def update_ratingplan(
    ratingplan_id: int,
    ratingplan_update: RatingPlanUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a rating plan"""
    try:
        updated_ratingplan = await ratingplan_service.update_ratingplan(ratingplan_id, ratingplan_update)
        if not updated_ratingplan:
            raise HTTPException(status_code=404, detail="Rating manual not found")
        return updated_ratingplan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating rating plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{ratingplan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ratingplan(
    ratingplan_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a rating plan. Idempotent: returns 204 whether the resource was deleted or already absent."""
    try:
        await ratingplan_service.delete_ratingplan(ratingplan_id)
    except Exception as e:
        logger.error(f"Error deleting rating plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

