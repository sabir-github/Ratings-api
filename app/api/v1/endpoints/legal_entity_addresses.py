from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.legal_entity_address_service import legal_entity_address_service
from app.schemas.legal_entity_address import (
    LegalEntityAddressCreateSchema,
    LegalEntityAddressUpdateSchema,
    LegalEntityAddressResponseSchema,
)
from app.core.security import get_current_user
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=LegalEntityAddressResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_legal_entity_address(
    address: LegalEntityAddressCreateSchema,
    current_user: UserBase = Depends(get_current_user),
):
    """Create a new legal entity address"""
    try:
        return await legal_entity_address_service.create_address(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating legal entity address: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/info/sequence")
async def get_address_sequence_info(current_user: UserBase = Depends(get_current_user)):
    """Get information about the current ID sequence for legal entity addresses"""
    last_id = await legal_entity_address_service.get_last_address_id()
    return {
        "last_address_id": last_id,
        "next_address_id": last_id + 1 if last_id else 100000000,
    }


@router.get("/info/count")
async def get_addresses_count(
    legal_entity_id: Optional[int] = Query(None),
    address_type: Optional[str] = Query(None),
    current_user: UserBase = Depends(get_current_user),
):
    """Get count of legal entity addresses with optional filters"""
    filter_by = {}
    if legal_entity_id is not None:
        filter_by["legal_entity_id"] = legal_entity_id
    if address_type:
        filter_by["address_type"] = address_type
    count = await legal_entity_address_service.count_addresses(filter_by=filter_by)
    return {"count": count}


@router.get("/{address_id}/exists")
async def check_address_exists(
    address_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Check if a legal entity address exists"""
    addr = await legal_entity_address_service.get_address(address_id)
    return {"exists": addr is not None}


@router.get("/{address_id}", response_model=LegalEntityAddressResponseSchema)
async def get_legal_entity_address(
    address_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Get a legal entity address by ID"""
    addr = await legal_entity_address_service.get_address(address_id)
    if not addr:
        raise HTTPException(status_code=404, detail="Legal entity address not found")
    return addr


@router.get("/", response_model=List[LegalEntityAddressResponseSchema])
async def get_legal_entity_addresses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    legal_entity_id: Optional[int] = Query(None),
    address_type: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: int = Query(1, ge=-1, le=1),
    current_user: UserBase = Depends(get_current_user),
):
    """Get all legal entity addresses with pagination and filtering"""
    filter_by = {}
    if legal_entity_id is not None:
        filter_by["legal_entity_id"] = legal_entity_id
    if address_type:
        filter_by["address_type"] = address_type
    if city:
        filter_by["city"] = city
    if country_code:
        filter_by["country_code"] = country_code
    return await legal_entity_address_service.get_addresses(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.put("/{address_id}", response_model=LegalEntityAddressResponseSchema)
async def update_legal_entity_address(
    address_id: int,
    update: LegalEntityAddressUpdateSchema,
    current_user: UserBase = Depends(get_current_user),
):
    """Update a legal entity address"""
    try:
        updated = await legal_entity_address_service.update_address(address_id, update)
        if not updated:
            raise HTTPException(status_code=404, detail="Legal entity address not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating legal entity address: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_legal_entity_address(
    address_id: int,
    current_user: UserBase = Depends(get_current_user),
):
    """Delete a legal entity address. Idempotent: returns 204 whether the resource was deleted or already absent."""
    await legal_entity_address_service.delete_address(address_id)
