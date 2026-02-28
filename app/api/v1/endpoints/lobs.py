from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.lob_service import lob_service
from app.schemas.lob import LobCreateSchema, LobUpdateSchema, LobResponseSchema
from app.core.security import get_current_user
#from app.models.user import User
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=LobResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_lob(
    lob: LobCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new lob (ID auto-generated if not provided)"""
    try:
        return await lob_service.create_lob(lob)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating lob: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_lobs", response_model=List[LobResponseSchema], status_code=status.HTTP_201_CREATED)
async def create_bulk_lobs(
    lobs: List[LobCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new lobs (ID auto-generated if not provided)"""
    try:
        return await lob_service.bulk_create_lobs(lobs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating lobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{lob_id}", response_model=LobResponseSchema)
async def get_lob(
    lob_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a lob by ID"""
    lob = await lob_service.get_lob(lob_id)
    if not lob:
        raise HTTPException(status_code=404, detail="ob not found")
    return lob

@router.get("/", response_model=List[LobResponseSchema])
async def get_lobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    lob_name: Optional[str] = Query(None, description="Filter by lob name (partial match)"),
    lob_code: Optional[str] = Query(None, description="Filter by lob code (partial match)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all companies with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if lob_name:
        filter_by["lob_name"] = lob_name
    if lob_code:
        filter_by["lob_code"] = lob_code
    
    return await lob_service.get_lobs(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{lob_id}", response_model=LobResponseSchema)
async def update_lob(
    lob_id: int,
    lob_update: LobUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a lob"""
    updated_lob = await lob_service.update_lob(lob_id, lob_update)
    if not updated_lob:
        raise HTTPException(status_code=404, detail="lob not found")
    return updated_lob

@router.delete("/{lob_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lob(
    lob_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a lob. Idempotent: returns 204 whether the resource was deleted or already absent."""
    await lob_service.delete_lob(lob_id)

@router.get("/{lob_id}/exists")
async def check_lob_exists(
    lob_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a lob exists"""
    lob = await lob_service.get_lob(lob_id)
    return {"exists": lob is not None}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await lob_service.get_last_lob_id()
    return {
        "last_lob_id": last_id,
        "next_lob_id": last_id + 1 if last_id else 100000000
    }