from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.ratingtable import RatingTableCreateSchema, RatingTableUpdateSchema
from app.models.ratingtable import RatingTableResponse
from app.models.company import CompanyResponse
from app.models.lob import LobResponse
from app.models.state import StateResponse
from app.models.product import ProductResponse
from app.services.company_service import CompanyService
from app.services.lob_service import LobService
from app.services.state_service import StateService
from app.services.product_service import ProductService
import logging

logger = logging.getLogger(__name__)

class RatingTableService(LobService):
    def __init__(self):
        self.collection_name = "ratingtables"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_ratingtable_id(self) -> int:
        """Generate auto-incrementing table ID"""
        return await get_next_sequence_value("table_id")

    async def create_ratingtable(self, ratingtable_data: RatingTableCreateSchema) -> RatingTableResponse:
        collection = await self.get_collection()
        #collection_lob = await LobService.get_collection(self)
        #print(collection_lob)
        # Auto-generate ID if not provided
        #print("ratingtable_data",ratingtable_data.id)
        if ratingtable_data.id is None or ratingtable_data.id == 0:
            ratingtable_id = await self._generate_ratingtable_id()
        else:
            ratingtable_id = ratingtable_data.id
        
        #print("ratingtable_id",ratingtable_id)
        # Check if product with same ID or code exists
    #data: Optional[list] = None
        existing_product = await collection.find_one({
            "$and": [
                #{"id": ratingtable_id},
                #{"table_code": ratingtable_data.table_code},
                #{"table_name": ratingtable_data.table_name},
                #{"company": ratingtable_data.company},
                {"company": ratingtable_data.company},
                {"lob": ratingtable_data.lob},
                {"state": ratingtable_data.state},
                {"product": ratingtable_data.product},
                {"data": ratingtable_data.data}
            ]
        })
        
        if existing_product:
            id = existing_product.id
            #raise ValueError("Rating Table already exists")
        
        #Check LOB exist
        existing_lob = False
        if not ratingtable_data.lob_id is None:
            lobresponse = await LobService.get_lob(LobService(),ratingtable_data.lob_id)
            if lobresponse:
                existing_lob = True        
        if not existing_lob:
            raise ValueError("Invalid Lob or Lob does not exist")
        now = datetime.now(timezone.utc)
        product_dict = ratingtable_data.dict(exclude={'id'})
        product_dict.update({
            "id": ratingtable_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(product_dict)
        created_product = await collection.find_one({"_id": result.inserted_id})
        return RatingTableResponse(**created_product)

    async def get_product(self, ratingtable_id: int) -> Optional[RatingTableResponse]:
        collection = await self.get_collection()
        #collection_lob = await LobService.get_collection()
        product = await collection.find_one({"id": ratingtable_id})
        return RatingTableResponse(**product) if product else None

    async def get_products(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[RatingTableResponse]:
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "product_name" in filter_by:
                query["product_name"] = {"$regex": filter_by["product_name"], "$options": "i"}
            if "product_code" in filter_by:
                query["product_code"] = {"$regex": filter_by["product_code"], "$options": "i"}
            if "lob_id" in filter_by:
                query["lob_id"] = {"$regex": filter_by["lob_id"], "$options": "i"}
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        products = await cursor.to_list(length=limit)
        return [RatingTableResponse(**product) for product in products]

    async def update_product(self, ratingtable_id: int, update_data: RatingTableUpdateSchema) -> Optional[RatingTableResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": ratingtable_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_product = await collection.find_one({"id": ratingtable_id})
        return RatingTableResponse(**updated_product) if updated_product else None

    async def delete_product(self, ratingtable_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": ratingtable_id})
        return result.deleted_count > 0

    async def count_products(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "product_name" in filter_by:
                query["product_name"] = {"$regex": filter_by["product_name"], "$options": "i"}
            if "lob_id" in filter_by:
                query["lob_id"] = {"$regex": filter_by["lob_id"], "$options": "i"}
        
        return await collection.count_documents(query)

    async def bulk_create_products(self, products_data: List[RatingTableCreateSchema]) -> List[RatingTableResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        products_to_insert = []
        for ratingtable_data in products_data:
            # Auto-generate ID if not provided
            print(ratingtable_data.id)
            if ratingtable_data.id is None or ratingtable_data.id == 0:
                ratingtable_id = await self._generate_ratingtable_id()
            else:
                ratingtable_id = ratingtable_data.id
            
            product_dict = ratingtable_data.dict(exclude={'id'})
            product_dict.update({
                "id": ratingtable_id,
                "created_at": now,
                "updated_at": now
            })
            products_to_insert.append(product_dict)
        """
        try:
            for row in products_to_insert: 
                filter_query = {'id': row['id']}
                update_data = {
                    '$set': {
                    'product_code': row['product_code'],
                    'product_name': row['product_name'],
                    'active': row['active'],
                    'created_at': now,
                    'updated_at':now
                    }
                }
                result = await collection.update_one(filter_query, update_data, upsert=True)
                created_ids = result.upserted_id
        """
        try:
            result = await collection.insert_many(products_to_insert, ordered=False)
            
            created_ids = result.inserted_ids
            
            cursor = collection.find({"_id": {"$in": created_ids}})
            created_products = await cursor.to_list(length=len(created_ids))
            return [RatingTableResponse(**product) for product in created_products]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_ratingtable_id(self) -> Optional[int]:
        """Get the last used product ID"""
        collection = await self.get_collection()
        last_product = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_product["id"] if last_product else None

product_service = ProductService()