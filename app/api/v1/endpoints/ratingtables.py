from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
from app.services.ratingtable_service import ratingtable_service
from app.schemas.ratingtable import RatingTableCreateSchema, RatingTableUpdateSchema, RatingTableResponseSchema
from app.core.security import get_current_user
from app.models.user import UserBase
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ratingtable(
    ratingtable: RatingTableCreateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Create a new rating table (ID auto-generated if not provided)
    Returns message if no data changes found, or creates new record with data comparison if changes exist"""
    try:
        result = await ratingtable_service.create_ratingtable(ratingtable)
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
        logger.error(f"Error creating rating table: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk_ratingtables", status_code=status.HTTP_201_CREATED)
async def create_bulk_ratingtables(
    ratingtables: List[RatingTableCreateSchema],
    current_user: UserBase = Depends(get_current_user)
):
    """Bulk create rating tables (ID auto-generated if not provided)
    Returns list of results with data comparison for each record"""
    try:
        results = await ratingtable_service.bulk_create_ratingtables(ratingtables)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"results": results, "total": len(results)}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating rating tables: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[RatingTableResponseSchema])
async def get_ratingtables(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    table_name: Optional[str] = Query(None, description="Filter by table name (partial match)"),
    table_type: Optional[str] = Query(None, description="Filter by table type"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by state ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    context_id: Optional[int] = Query(None, description="Filter by context ID"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: int = Query(1, ge=-1, le=1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get all rating tables with pagination, filtering and sorting"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if table_name:
        filter_by["table_name"] = table_name
    if table_type:
        filter_by["table_type"] = table_type
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if context_id is not None:
        filter_by["context_id"] = context_id
    
    return await ratingtable_service.get_ratingtables(
        skip=skip,
        limit=limit,
        filter_by=filter_by,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.get("/info/sequence")
async def get_sequence_info(
    current_user: UserBase = Depends(get_current_user)
):
    """Get information about the current ID sequence"""
    last_id = await ratingtable_service.get_last_ratingtable_id()
    return {
        "last_ratingtable_id": last_id,
        "next_ratingtable_id": last_id + 1 if last_id else 100000000
    }

@router.get("/info/count")
async def get_ratingtables_count(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    table_name: Optional[str] = Query(None, description="Filter by table name (partial match)"),
    table_type: Optional[str] = Query(None, description="Filter by table type"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    lob_id: Optional[int] = Query(None, description="Filter by LOB ID"),
    state_id: Optional[int] = Query(None, description="Filter by state ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    context_id: Optional[int] = Query(None, description="Filter by context ID"),
    current_user: UserBase = Depends(get_current_user)
):
    """Get count of rating tables with optional filters"""
    filter_by = {}
    if active is not None:
        filter_by["active"] = active
    if table_name:
        filter_by["table_name"] = table_name
    if table_type:
        filter_by["table_type"] = table_type
    if company_id is not None:
        filter_by["company_id"] = company_id
    if lob_id is not None:
        filter_by["lob_id"] = lob_id
    if state_id is not None:
        filter_by["state_id"] = state_id
    if product_id is not None:
        filter_by["product_id"] = product_id
    if context_id is not None:
        filter_by["context_id"] = context_id
    
    count = await ratingtable_service.count_ratingtables(filter_by=filter_by)
    return {"count": count}

@router.get("/{ratingtable_id}/exists")
async def check_ratingtable_exists(
    ratingtable_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Check if a rating table exists"""
    ratingtable = await ratingtable_service.get_ratingtable(ratingtable_id)
    return {"exists": ratingtable is not None}

@router.get("/{ratingtable_id}", response_model=RatingTableResponseSchema)
async def get_ratingtable(
    ratingtable_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Get a rating table by ID"""
    ratingtable = await ratingtable_service.get_ratingtable(ratingtable_id)
    if not ratingtable:
        raise HTTPException(status_code=404, detail="Rating table not found")
    return ratingtable

@router.put("/{ratingtable_id}", response_model=RatingTableResponseSchema)
async def update_ratingtable(
    ratingtable_id: int,
    ratingtable_update: RatingTableUpdateSchema,
    current_user: UserBase = Depends(get_current_user)
):
    """Update a rating table"""
    updated_ratingtable = await ratingtable_service.update_ratingtable(ratingtable_id, ratingtable_update)
    if not updated_ratingtable:
        raise HTTPException(status_code=404, detail="Rating table not found")
    return updated_ratingtable

@router.delete("/{ratingtable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ratingtable(
    ratingtable_id: int,
    current_user: UserBase = Depends(get_current_user)
):
    """Delete a rating table"""
    success = await ratingtable_service.delete_ratingtable(ratingtable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rating table not found")

@router.post("/import/excel", status_code=status.HTTP_200_OK)
async def import_ratingtables_from_excel(
    file: UploadFile = File(..., description="Excel file (.xlsx or .xls) with rating table data. Each sheet represents a rating table."),
    company: int = Form(..., description="Company ID (mandatory)"),
    lob: int = Form(..., description="LOB ID (mandatory)"),
    state: int = Form(..., description="State ID (mandatory)"),
    product: int = Form(..., description="Product ID (mandatory)"),
    context: Optional[str] = Form(None, description="Context ID (optional)"),
    table_type: Optional[str] = Form(None, description="Table type (optional)"),
    effective_date: Optional[str] = Form(None, description="Effective date in ISO format (optional, defaults to current date at midnight UTC)"),
    current_user: UserBase = Depends(get_current_user)
):
    """
    Import rating tables from Excel file.
    
    - Each sheet in the Excel file represents a new rating table record
    - Sheet name is used as the table_name
    - Sheet data is converted to JSON and stored in the data field
    - Validates record existence before creating (checks for same combination)
    - Uses transactions for data integrity
    - Returns detailed results for each sheet processed
    
    **Required Parameters:**
    - file: Excel file (.xlsx or .xls)
    - company: Company ID
    - lob: LOB ID
    - state: State ID
    - product: Product ID
    
    **Optional Parameters:**
    - context: Context ID (optional)
    - table_type: Table type (optional)
    - effective_date: Effective date in ISO format (optional, defaults to current date at midnight UTC if not provided)
    
    **Returns:**
    - total_sheets: Total number of sheets processed
    - created: Number of rating tables created
    - skipped: Number of sheets skipped (no changes found)
    - errors: Number of errors encountered
    - details: List of results for each sheet
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files (.xlsx or .xls) are allowed"
        )
    
    try:
        # Read file content
        contents = await file.read()
        
        if not contents or len(contents) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Handle empty strings for optional fields (form data sends "" instead of None)
        parsed_context = None
        if context is not None:
            # Convert empty string to None
            if isinstance(context, str) and context.strip() == "":
                parsed_context = None
            else:
                try:
                    parsed_context = int(context)
                except (ValueError, TypeError):
                    raise HTTPException(status_code=400, detail="Context ID must be a valid integer")
        
        parsed_table_type = None
        if table_type is not None and isinstance(table_type, str) and table_type.strip() != "":
            parsed_table_type = table_type.strip()
        
        # Parse effective_date if provided
        parsed_effective_date = None
        if effective_date and isinstance(effective_date, str) and effective_date.strip() != "":
            try:
                # Try parsing ISO format first
                if 'T' in effective_date:
                    parsed_effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
                else:
                    # Try date only format
                    parsed_effective_date = datetime.strptime(effective_date, '%Y-%m-%d')
                    parsed_effective_date = parsed_effective_date.replace(tzinfo=timezone.utc)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid effective_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS): {str(e)}"
                )
        
        # Validate required IDs are positive integers
        if company <= 0:
            raise HTTPException(status_code=400, detail="Company ID must be a positive integer")
        if lob <= 0:
            raise HTTPException(status_code=400, detail="LOB ID must be a positive integer")
        if state <= 0:
            raise HTTPException(status_code=400, detail="State ID must be a positive integer")
        if product <= 0:
            raise HTTPException(status_code=400, detail="Product ID must be a positive integer")
        if parsed_context is not None and parsed_context <= 0:
            raise HTTPException(status_code=400, detail="Context ID must be a positive integer if provided")
        
        # Import rating tables from Excel
        import_result = await ratingtable_service.import_from_excel(
            file_content=contents,
            company=company,
            lob=lob,
            state=state,
            product=product,
            context=parsed_context,
            table_type=parsed_table_type,
            effective_date=parsed_effective_date
        )
        
        # Determine HTTP status code based on results
        if import_result["errors"] > 0 and import_result["created"] == 0:
            status_code = status.HTTP_400_BAD_REQUEST
        elif import_result["created"] > 0:
            status_code = status.HTTP_201_CREATED
        else:
            status_code = status.HTTP_200_OK
        
        return JSONResponse(
            status_code=status_code,
            content=import_result
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error importing Excel file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing Excel file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error importing Excel file: {str(e)}"
        )



