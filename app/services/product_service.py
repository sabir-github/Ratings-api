from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.product import ProductCreateSchema, ProductUpdateSchema
from app.models.product import ProductResponse
from app.models.lob import LobResponse
from app.services.lob_service import LobService
import logging

logger = logging.getLogger(__name__)

class ProductService(LobService):
    def __init__(self):
        self.collection_name = "products"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_product_id(self) -> int:
        """Generate auto-incrementing product ID"""
        return await get_next_sequence_value("product_id")

    async def create_product(self, product_data: ProductCreateSchema) -> ProductResponse:
        collection = await self.get_collection()
        #collection_lob = await LobService.get_collection(self)
        #print(collection_lob)
        # Auto-generate ID
        product_id = await self._generate_product_id()
        
        # Check if product with same ID or code exists
        existing_product = await collection.find_one({
            "$or": [
                {"id": product_id},
                {"product_code": product_data.product_code}
            ]
        })
        
        if existing_product:
            raise ValueError("Product with same ID or code already exists")
        
        #Check LOB exist
        existing_lob = False
        if not product_data.lob_id is None:
            lobresponse = await LobService.get_lob(LobService(),product_data.lob_id)
            if lobresponse:
                existing_lob = True        
        if not existing_lob:
            raise ValueError("Invalid Lob or Lob does not exist")
        now = datetime.now(timezone.utc)
        product_dict = product_data.dict()
        product_dict.update({
            "id": product_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(product_dict)
        created_product = await collection.find_one({"_id": result.inserted_id})
        return ProductResponse(**created_product)

    async def get_product(self, product_id: int) -> Optional[ProductResponse]:
        collection = await self.get_collection()
        #collection_lob = await LobService.get_collection()
        product = await collection.find_one({"id": product_id})
        return ProductResponse(**product) if product else None

    async def get_products(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[ProductResponse]:
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
        return [ProductResponse(**product) for product in products]

    async def update_product(self, product_id: int, update_data: ProductUpdateSchema) -> Optional[ProductResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": product_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_product = await collection.find_one({"id": product_id})
        return ProductResponse(**updated_product) if updated_product else None

    async def delete_product(self, product_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": product_id})
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

    async def bulk_create_products(self, products_data: List[ProductCreateSchema]) -> List[ProductResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        products_to_insert = []
        for product_data in products_data:
            # Auto-generate ID
            product_id = await self._generate_product_id()
            
            product_dict = product_data.dict()
            product_dict.update({
                "id": product_id,
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
            return [ProductResponse(**product) for product in created_products]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_product_id(self) -> Optional[int]:
        """Get the last used product ID"""
        collection = await self.get_collection()
        last_product = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_product["id"] if last_product else None

product_service = ProductService()