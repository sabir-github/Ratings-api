from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.context import ContextCreateSchema, ContextUpdateSchema
from app.models.context import ContextResponse
import logging

logger = logging.getLogger(__name__)

class contextservice:
    def __init__(self):
        self.collection_name = "contexts"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_context_id(self) -> int:
        """Generate auto-incrementing context ID"""
        return await get_next_sequence_value("context_id")

    async def create_context(self, context_data: ContextCreateSchema) -> ContextResponse:
        collection = await self.get_collection()
        
        # Auto-generate ID if not provided
        print("context_data",context_data.id)
        if context_data.id is None or context_data.id == 0:
            context_id = await self._generate_context_id()
        else:
            context_id = context_data.id
        print("context_id",context_id)
        # Check if context with same ID or code exists
        existing_context = await collection.find_one({
            "$or": [
                {"id": context_id},
                {"context_code": context_data.context_code}
            ]
        })
        
        if existing_context:
            raise ValueError("Context with same ID or code already exists")
        
        now = datetime.now(timezone.utc)
        context_dict = context_data.dict(exclude={'id'})
        context_dict.update({
            "id": context_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(context_dict)
        created_context = await collection.find_one({"_id": result.inserted_id})
        return ContextResponse(**created_context)

    async def get_context(self, context_id: int) -> Optional[ContextResponse]:
        collection = await self.get_collection()
        context = await collection.find_one({"id": context_id})
        return ContextResponse(**context) if context else None

    async def get_contexts(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[ContextResponse]:
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "context_name" in filter_by:
                query["context_name"] = {"$regex": filter_by["context_name"], "$options": "i"}
            if "context_code" in filter_by:
                query["context_code"] = {"$regex": filter_by["context_code"], "$options": "i"}
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        contexts = await cursor.to_list(length=limit)
        return [ContextResponse(**context) for context in contexts]

    async def update_context(self, context_id: int, update_data: ContextUpdateSchema) -> Optional[ContextResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": context_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_context = await collection.find_one({"id": context_id})
        return ContextResponse(**updated_context) if updated_context else None

    async def delete_context(self, context_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": context_id})
        return result.deleted_count > 0

    async def count_contexts(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "context_name" in filter_by:
                query["context_name"] = {"$regex": filter_by["context_name"], "$options": "i"}
        
        return await collection.count_documents(query)

    async def bulk_create_contexts(self, contexts_data: List[ContextCreateSchema]) -> List[ContextResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        contexts_to_insert = []
        for context_data in contexts_data:
            # Auto-generate ID if not provided
            #print(context_data.id)
            if context_data.id is None or context_data.id == 0:
                context_id = await self._generate_context_id()
            else:
                context_id = context_data.id
            
            context_dict = context_data.dict(exclude={'id'})
            context_dict.update({
                "id": context_id,
                "created_at": now,
                "updated_at": now
            })
            contexts_to_insert.append(context_dict)
        
        #try:
        #    for row in contexts_to_insert: 
        #        filter_query = {'id': row['id']}
        #        update_data = {
        #            '$set': {
        #            'context_code': row['context_code'],
        #            'context_name': row['context_name'],
        #            'active': row['active'],
        #            'created_at': now,
        #            'updated_at':now
        #            }
        #        }
        #       result = await collection.update_one(filter_query, update_data, upsert=True)
        #        created_ids = result.upserted_id
        try:
            result = await collection.insert_many(contexts_to_insert, ordered=False)
            created_ids = result.inserted_ids
            
            cursor = collection.find({"_id": {"$in": created_ids}})
            created_contexts = await cursor.to_list(length=len(created_ids))
            return [ContextResponse(**context) for context in created_contexts]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_context_id(self) -> Optional[int]:
        """Get the last used context ID"""
        collection = await self.get_collection()
        last_context = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_context["id"] if last_context else None

context_service = contextservice()