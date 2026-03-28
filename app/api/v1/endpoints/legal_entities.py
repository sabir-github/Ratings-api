from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.legal_entity_service import legal_entity_service
from app.schemas.legal_entity import (
    LegalEntityCreateSchema,
    LegalEntityUpdateSchema,
    LegalEntityResponseSchema,
)
from app.core.security import get_current_user
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=LegalEntityResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_legal_entity(
    entity: LegalEntityCreateSchema,
    current_user: UserBase = Depends(get_current_user),
):
    """Create a new legal entity"""
    try:
        return await legal_entity_service.create_legal_entity(entity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating legal entity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/info/sequence")
async def get_legal_entity_sequence_info(current_user: UserBase = Depends(get_current_user)):
    """Get information about the current ID sequence for legal entities"""
    last_id = await legal_entity_service.get_last_legal_entity_id()
    return {
        "last_legal_entity_id": last_id,
        "next_legal_entity_id": last_id + 1 if last_id else 100000000,
    }


@router.get("/info/count")
async def get_legal_entities_count(
    active: Optional[bool] = Query(None),
    company_id: Optional[int] = Query(None),
    legal_name: Optional[str] = Query(None),
    current_user: UserBase = Depends(get_current_user),
):
    """Get count of legal entities with optional filters"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if company_id is not None:
        filter_by["company_id"] = company_id
    if legal_name:
        filter_by["legal_name"] = legal_name
    count = await legal_entity_service.count_legal_entities(filter_by=filter_by)
    return {"count": count}


@router.get("/{entity_id}/exists")
async def check_legal_entity_exists(
    entity_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Check if a legal entity exists"""
    entity = await legal_entity_service.get_legal_entity(entity_id)
    return {"exists": entity is not None}


@router.get("/{entity_id}", response_model=LegalEntityResponseSchema)
async def get_legal_entity(
    entity_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Get a legal entity by ID"""
    entity = await legal_entity_service.get_legal_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Legal entity not found")
    return entity


@router.get("/", response_model=List[LegalEntityResponseSchema])
async def get_legal_entities(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active: Optional[bool] = Query(None),
    company_id: Optional[int] = Query(None),
    legal_name: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    jurisdiction: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: int = Query(1, ge=-1, le=1),
    current_user: UserBase = Depends(get_current_user),
):
    """Get all legal entities with pagination and filtering"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if company_id is not None:
        filter_by["company_id"] = company_id
    if legal_name:
        filter_by["legal_name"] = legal_name
    if entity_type:
        filter_by["entity_type"] = entity_type
    if jurisdiction:
        filter_by["jurisdiction"] = jurisdiction
    return await legal_entity_service.get_legal_entities(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.put("/{entity_id}", response_model=LegalEntityResponseSchema)
async def update_legal_entity(
    entity_id: int,
    update: LegalEntityUpdateSchema,
    current_user: UserBase = Depends(get_current_user),
):
    """Update a legal entity"""
    try:
        updated = await legal_entity_service.update_legal_entity(entity_id, update)
        if not updated:
            raise HTTPException(status_code=404, detail="Legal entity not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating legal entity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_legal_entity(
    entity_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Delete a legal entity. Idempotent: returns 204 whether the resource was deleted or already absent."""
    await legal_entity_service.delete_legal_entity(entity_id)
