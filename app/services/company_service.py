from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.company import CompanyCreateSchema, CompanyUpdateSchema
from app.models.company import CompanyResponse
import logging
import re

logger = logging.getLogger(__name__)

class CompanyService:
    def __init__(self):
        self.collection_name = "companies"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_company_id(self) -> int:
        """Generate auto-incrementing company ID"""
        return await get_next_sequence_value("company_id")

    async def create_company(self, company_data: CompanyCreateSchema) -> CompanyResponse:
        collection = await self.get_collection()
        
        # Auto-generate ID
        company_id = await self._generate_company_id()
        
        # Check if company with same ID or code exists
        existing_company = await collection.find_one({
            "$or": [
                {"id": company_id},
                {"company_code": company_data.company_code}
            ]
        })
        
        if existing_company:
            raise ValueError("Company with same ID or code already exists")
        
        now = datetime.now(timezone.utc)
        company_dict = company_data.dict()
        company_dict.update({
            "id": company_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(company_dict)
        created_company = await collection.find_one({"_id": result.inserted_id})
        return CompanyResponse(**created_company)

    async def get_company(self, company_id: int) -> Optional[CompanyResponse]:
        collection = await self.get_collection()
        company = await collection.find_one({"id": company_id})
        return CompanyResponse(**company) if company else None

    async def get_companies(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[CompanyResponse]:
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "company_name" in filter_by:
                # Use anchored regex (^) for better index utilization
                # This allows MongoDB to use the company_name index efficiently
                company_name_filter = filter_by["company_name"]
                # Escape special regex characters to prevent injection
                escaped_name = re.escape(company_name_filter)
                query["company_name"] = {"$regex": f"^{escaped_name}", "$options": "i"}
            if "company_code" in filter_by:
                # Use anchored regex (^) for better index utilization
                company_code_filter = filter_by["company_code"]
                escaped_code = re.escape(company_code_filter)
                query["company_code"] = {"$regex": f"^{escaped_code}", "$options": "i"}
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        companies = await cursor.to_list(length=limit)
        return [CompanyResponse(**company) for company in companies]

    async def update_company(self, company_id: int, update_data: CompanyUpdateSchema) -> Optional[CompanyResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": company_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_company = await collection.find_one({"id": company_id})
        return CompanyResponse(**updated_company) if updated_company else None

    async def delete_company(self, company_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": company_id})
        return result.deleted_count > 0

    async def count_companies(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "company_name" in filter_by:
                # Use anchored regex (^) for better index utilization
                company_name_filter = filter_by["company_name"]
                escaped_name = re.escape(company_name_filter)
                query["company_name"] = {"$regex": f"^{escaped_name}", "$options": "i"}
        
        return await collection.count_documents(query)

    async def bulk_create_companies(self, companies_data: List[CompanyCreateSchema]) -> List[CompanyResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        companies_to_insert = []
        for company_data in companies_data:
            # Auto-generate ID
            company_id = await self._generate_company_id()
            
            company_dict = company_data.dict()
            company_dict.update({
                "id": company_id,
                "created_at": now,
                "updated_at": now
            })
            companies_to_insert.append(company_dict)
        
        #try:
        #    for row in companies_to_insert: 
        #        filter_query = {'id': row['id']}
        #        update_data = {
        #            '$set': {
        #            'company_code': row['company_code'],
        #            'company_name': row['company_name'],
        #            'active': row['active'],
        #            'created_at': now,
        #            'updated_at':now
        #            }
        #        }
        #       result = await collection.update_one(filter_query, update_data, upsert=True)
        #        created_ids = result.upserted_id
        try:
            result = await collection.insert_many(companies_to_insert, ordered=False)
            created_ids = result.inserted_ids
            
            cursor = collection.find({"_id": {"$in": created_ids}})
            created_companies = await cursor.to_list(length=len(created_ids))
            return [CompanyResponse(**company) for company in created_companies]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_company_id(self) -> Optional[int]:
        """Get the last used company ID"""
        collection = await self.get_collection()
        last_company = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_company["id"] if last_company else None

company_service = CompanyService()