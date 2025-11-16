from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.services.product_service import product_service
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema, ProductResponseSchema
from app.core.security import get_current_user
#from app.models.user import User
from app.models.user import UserBase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new product (ID auto-generated if not provided)"""
    try:
        return await product_service.create_product(product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_products", response_model=List[ProductResponseSchema], status_code=status.HTTP_201_CREATED)
async def create_bulk_products(
    products: List[ProductCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new products (ID auto-generated if not provided)"""
    try:
        return await product_service.bulk_create_products(products)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating lobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{product_id}", response_model=ProductResponseSchema)
async def get_product(
    product_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a product by ID"""
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="ob not found")
    return product

@router.get("/", response_model=List[ProductResponseSchema])
async def get_products(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    product_name: Optional[str] = Query(None, description="Filter by product name (partial match)"),
    product_code: Optional[str] = Query(None, description="Filter by product code (partial match)"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all companies with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if product_name:
        filter_by["product_name"] = product_name
    if product_code:
        filter_by["product_code"] = product_code
    
    return await product_service.get_products(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.put("/{product_id}", response_model=ProductResponseSchema)
async def update_product(
    product_id: int,
    product_update: ProductUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a product"""
    updated_product = await product_service.update_product(product_id, product_update)
    if not updated_product:
        raise HTTPException(status_code=404, detail="product not found")
    return updated_product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a product"""
    success = await product_service.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=404, detail="product not found")

@router.get("/{product_id}/exists")
async def check_product_exists(
    product_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a product exists"""
    product = await product_service.get_product(product_id)
    return {"exists": product is not None}

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await product_service.get_last_product_id()
    return {
        "last_product_id": last_id,
        "next_product_id": last_id + 1 if last_id else 100000000
    }