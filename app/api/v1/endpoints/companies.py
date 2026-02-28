from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.company_service import company_service
from app.schemas.company import CompanyCreateSchema, CompanyUpdateSchema, CompanyResponseSchema
from app.core.security import get_current_user
#from app.models.user import User
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=CompanyResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_company(
    company: CompanyCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new company (ID auto-generated if not provided)"""
    try:
        return await company_service.create_company(company)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_companies", response_model=List[CompanyResponseSchema], status_code=status.HTTP_201_CREATED)
async def create_bulk_companies(
    companies: List[CompanyCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new company (ID auto-generated if not provided)"""
    try:
        return await company_service.bulk_create_companies(companies)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating companies: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{company_id}", response_model=CompanyResponseSchema)
async def get_company(
    company_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a company by ID"""
    company = await company_service.get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.get("/", response_model=List[CompanyResponseSchema])
async def get_companies(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    company_name: Optional[str] = Query(None, description="Filter by company name (partial match)"),
    company_code: Optional[str] = Query(None, description="Filter by company code (partial match)"),
    tax_id: Optional[str] = Query(None, description="Filter by tax ID (partial match)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all companies with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if company_name:
        filter_by["company_name"] = company_name
    if company_code:
        filter_by["company_code"] = company_code
    if tax_id:
        filter_by["tax_id"] = tax_id
    
    return await company_service.get_companies(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{company_id}", response_model=CompanyResponseSchema)
async def update_company(
    company_id: int,
    company_update: CompanyUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a company"""
    updated_company = await company_service.update_company(company_id, company_update)
    if not updated_company:
        raise HTTPException(status_code=404, detail="Company not found")
    return updated_company

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a company. Idempotent: returns 204 whether the resource was deleted or already absent."""
    await company_service.delete_company(company_id)

@router.get("/{company_id}/exists")
async def check_company_exists(
    company_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a company exists"""
    company = await company_service.get_company(company_id)
    return {"exists": company is not None}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await company_service.get_last_company_id()
    return {
        "last_company_id": last_id,
        "next_company_id": last_id + 1 if last_id else 100000000
    }