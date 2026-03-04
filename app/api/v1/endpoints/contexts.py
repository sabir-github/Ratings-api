from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.context_service import context_service
from app.schemas.context import ContextCreateSchema, ContextUpdateSchema, ContextResponseSchema
from app.core.security import get_current_user
#from app.models.user import User
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ContextResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_context(
    context: ContextCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new context (ID auto-generated if not provided)"""
    try:
        return await context_service.create_context(context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating context: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_contexts", response_model=List[ContextResponseSchema], status_code=status.HTTP_201_CREATED)
async def create_bulk_contexts(
    contexts: List[ContextCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new context (ID auto-generated if not provided)"""
    try:
        return await context_service.bulk_create_contexts(contexts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating contexts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{context_id}", response_model=ContextResponseSchema)
async def get_context(
    context_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a context by ID"""
    context = await context_service.get_context(context_id)
    if not context:
        raise HTTPException(status_code=404, detail="context not found")
    return context

@router.get("/", response_model=List[ContextResponseSchema])
async def get_contexts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    context_name: Optional[str] = Query(None, description="Filter by context name (partial match)"),
    context_code: Optional[str] = Query(None, description="Filter by context code (partial match)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all contexts with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if context_name:
        filter_by["context_name"] = context_name
    if context_code:
        filter_by["context_code"] = context_code
    
    return await context_service.get_contexts(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{context_id}", response_model=ContextResponseSchema)
async def update_context(
    context_id: int,
    context_update: ContextUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a context"""
    updated_context = await context_service.update_context(context_id, context_update)
    if not updated_context:
        raise HTTPException(status_code=404, detail="context not found")
    return updated_context

@router.delete("/{context_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context(
    context_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a context. Idempotent: returns 204 whether the resource was deleted or already absent."""
    await context_service.delete_context(context_id)

@router.get("/{context_id}/exists")
async def check_context_exists(
    context_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a context exists"""
    context = await context_service.get_context(context_id)
    return {"exists": context is not None}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await context_service.get_last_context_id()
    return {
        "last_context_id": last_id,
        "next_context_id": last_id + 1 if last_id else 100000000
    }