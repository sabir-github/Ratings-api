from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.state_service import state_service
from app.schemas.state import StateCreateSchema, StateUpdateSchema, StateResponseSchema
from app.core.security import get_current_user
#from app.models.user import User
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=StateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_state(
    state: StateCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new state (ID auto-generated if not provided)"""
    try:
        return await state_service.create_state(state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating state: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_states", response_model=List[StateResponseSchema], status_code=status.HTTP_201_CREATED)
async def create_bulk_states(
    states: List[StateCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new state (ID auto-generated if not provided)"""
    try:
        return await state_service.bulk_create_state(states)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating states: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{state_id}", response_model=StateResponseSchema)
async def get_state(
    state_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a state by ID"""
    state = await state_service.get_state(state_id)
    if not state:
        raise HTTPException(status_code=404, detail="state not found")
    return state

@router.get("/", response_model=List[StateResponseSchema])
async def get_states(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    state_name: Optional[str] = Query(None, description="Filter by state name (partial match)"),
    state_code: Optional[str] = Query(None, description="Filter by state code (partial match)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all states with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if state_name:
        filter_by["state_name"] = state_name
    if state_code:
        filter_by["state_code"] = state_code
    
    return await state_service.get_states(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{state_id}", response_model=StateResponseSchema)
async def update_state(
    state_id: int,
    state_update: StateUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a state"""
    updated_state = await state_service.update_state(state_id, state_update)
    if not updated_state:
        raise HTTPException(status_code=404, detail="state not found")
    return updated_state

@router.delete("/{state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_state(
    state_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a state"""
    success = await state_service.delete_state(state_id)
    if not success:
        raise HTTPException(status_code=404, detail="state not found")

@router.get("/{state_id}/exists")
async def check_state_exists(
    state_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a state exists"""
    state = await state_service.get_state(state_id)
    return {"exists": state is not None}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await state_service.get_last_state_id()
    return {
        "last_state_id": last_id,
        "next_state_id": last_id + 1 if last_id else 100000000
    }