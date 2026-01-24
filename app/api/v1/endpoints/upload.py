import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from app.services.company_service import company_service
from app.services.lob_service import lob_service
from app.services.state_service import state_service
from app.services.product_service import product_service
from app.schemas.company import CompanyCreateSchema
from app.schemas.state import StateCreateSchema
from app.schemas.lob import LobCreateSchema
from app.schemas.product import ProductCreateSchema
from app.core.security import get_current_user
from app.models.user import UserBase
import io
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/companies/csv", status_code=status.HTTP_201_CREATED)
async def upload_companies_csv(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload companies from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        #print(df)
        # Validate required columns
        required_columns = ['company_code', 'company_name', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        companies_data = []
        for _, row in df.iterrows():
            try:
                company_data = CompanyCreateSchema(
                    company_code=str(row['company_code']),
                    company_name=str(row['company_name']),
                    active=bool(row['active'])
                )
                companies_data.append(company_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not companies_data:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")
        
        created_companies = await company_service.bulk_create_companies(companies_data)
        return {
            "message": f"Successfully created {len(created_companies)} companies",
            "companies": created_companies
        }
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing CSV file")

@router.post("/companies/excel", status_code=status.HTTP_201_CREATED)
async def upload_companies_excel(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload companies from Excel file"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        print(df)
        # Validate required columns
        required_columns = ['company_code', 'company_name', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"Excel must contain columns: {required_columns}"
            )
        
        companies_data = []
        for _, row in df.iterrows():
            try:
                company_data = CompanyCreateSchema(
                    company_code=str(row['company_code']),
                    company_name=str(row['company_name']),
                    active=bool(row['active'])
                )
                companies_data.append(company_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not companies_data:
            raise HTTPException(status_code=400, detail="No valid data found in Excel")
        
        created_companies = await company_service.bulk_create_companies(companies_data)
        return {
            "message": f"Successfully created {len(created_companies)} companies",
            "companies": created_companies
        }
        
    except Exception as e:
        logger.error(f"Error processing Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing Excel file")
    
@router.post("/lobs/csv", status_code=status.HTTP_201_CREATED)
async def upload_lobs_csv(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload lobs from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['lob_code', 'lob_name', 'lob_abbreviation', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        lobs_data = []
        for _, row in df.iterrows():
            try:
                lob_data = LobCreateSchema(
                    lob_code=str(row['lob_code']),
                    lob_name=str(row['lob_name']),
                    lob_abbreviation=bool(row['lob_abbreviation']),
                    active=bool(row['active'])
                )
                lobs_data.append(lob_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not lobs_data:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")
        
        created_lobs = await lob_service.bulk_create_lobs(lobs_data)
        return {
            "message": f"Successfully created {len(created_lobs)} lobs_data",
            "lobs": created_lobs
        }
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing CSV file")

@router.post("/lobs/excel", status_code=status.HTTP_201_CREATED)
async def upload_lobs_excel(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload lobs from Excel file"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['lob_code', 'lob_name', 'lob_abbreviation', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"Excel must contain columns: {required_columns}"
            )
        
        lobs_data = []
        for _, row in df.iterrows():
            try:
                lob_data = LobCreateSchema(
                    lob_code=str(row['lob_code']),
                    lob_name=str(row['lob_name']),
                    lob_abbreviation=str(row['lob_abbreviation']),
                    active=bool(row['active'])
                )
                lobs_data.append(lob_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not lobs_data:
            raise HTTPException(status_code=400, detail="No valid data found in Excel")
        
        created_lobs = await lob_service.bulk_create_lobs(lobs_data)
        return {
            "message": f"Successfully created {len(created_lobs)} lobs",
            "lobs": created_lobs
        }
        
    except Exception as e:
        logger.error(f"Error processing Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing Excel file")    
    
@router.post("/states/csv", status_code=status.HTTP_201_CREATED)
async def upload_states_csv(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload lobs from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['state_code', 'state_name', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        states_data = []
        for _, row in df.iterrows():
            try:
                state_data = StateCreateSchema(
                    state_code=str(row['state_code']),
                    state_name=str(row['state_name']),
                    active=bool(row['active'])
                )
                states_data.append(state_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not states_data:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")
        
        created_states = await state_service.bulk_create_states(states_data)
        return {
            "message": f"Successfully created {len(created_states)} states_data",
            "lobs": created_states
        }
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing CSV file")

@router.post("/states/excel", status_code=status.HTTP_201_CREATED)
async def upload_states_excel(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload lobs from Excel file"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['state_code', 'state_name', 'active']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"Excel must contain columns: {required_columns}"
            )
        
        states_data = []
        for _, row in df.iterrows():
            try:
                state_data = StateCreateSchema(
                    state_code=str(row['state_code']),
                    state_name=str(row['state_name']),
                    active=bool(row['active'])
                )
                states_data.append(state_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not states_data:
            raise HTTPException(status_code=400, detail="No valid data found in Excel")
        
        created_states = await state_service.bulk_create_states(states_data)
        return {
            "message": f"Successfully created {len(created_states)} lobs",
            "lobs": created_states
        }
        
    except Exception as e:
        logger.error(f"Error processing Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing Excel file")
    

@router.post("/products/csv", status_code=status.HTTP_201_CREATED)
async def upload_products_csv(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload products from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['product_code', 'product_name', 'active','lob_id']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns}"
            )
        
        products_data = []
        for _, row in df.iterrows():
            try:
                product_data = ProductCreateSchema(
                    product_code=str(row['product_code']),
                    product_name=str(row['product_name']),
                    lob_id      =int(row['lob_id']),
                    active=bool(row['active'])
                )
                products_data.append(product_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not products_data:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")
        
        created_products = await product_service.bulk_create_products(products_data)
        return {
            "message": f"Successfully created {len(created_products)} states_data",
            "lobs": created_products
        }
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing CSV file")

@router.post("/products/excel", status_code=status.HTTP_201_CREATED)
async def upload_states_excel(
    file: UploadFile = File(...),
    current_user: UserBase = Depends(get_current_user)
):
    """Upload products from Excel file"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['product_code', 'product_name', 'active','lob_id']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400, 
                detail=f"Excel must contain columns: {required_columns}"
            )
        
        products_data = []
        for _, row in df.iterrows():
            try:
                product_data = ProductCreateSchema(
                    product_code=str(row['product_code']),
                    product_name=str(row['product_name']),
                    lob_id=int(row['lob_id']),
                    active=bool(row['active'])
                )
                products_data.append(product_data)
            except Exception as e:
                logger.error(f"Error parsing row {_}: {str(e)}")
                continue
        
        if not products_data:
            raise HTTPException(status_code=400, detail="No valid data found in Excel")
        
        created_products = await product_service.bulk_create_products(products_data)
        return {
            "message": f"Successfully created {len(created_products)} lobs",
            "lobs": created_products
        }
        
    except Exception as e:
        logger.error(f"Error processing Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing Excel file")