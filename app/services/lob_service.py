from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.lob import LobCreateSchema, LobUpdateSchema
from app.models.lob import LobResponse
import logging

logger = logging.getLogger(__name__)

class LobService:
    def __init__(self):
        self.collection_name = "lobs"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_lob_id(self) -> int:
        """Generate auto-incrementing lob ID"""
        return await get_next_sequence_value("lob_id")

    async def create_lob(self, lob_data: LobCreateSchema) -> LobResponse:
        collection = await self.get_collection()
        
        # Auto-generate ID
        lob_id = await self._generate_lob_id()
        
        # Check if lob with same ID or code exists
        existing_lob = await collection.find_one({
            "$or": [
                {"id": lob_id},
                {"lob_code": lob_data.lob_code}
            ]
        })
        
        if existing_lob:
            raise ValueError("Lob with same ID or code already exists")
        
        now = datetime.now(timezone.utc)
        lob_dict = lob_data.dict()
        lob_dict.update({
            "id": lob_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(lob_dict)
        created_lob = await collection.find_one({"_id": result.inserted_id})
        return LobResponse(**created_lob)

    async def get_lob(self, lob_id: int) -> Optional[LobResponse]:
        collection = await self.get_collection()
        lob = await collection.find_one({"id": lob_id})
        return LobResponse(**lob) if lob else None

    async def get_lobs(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[LobResponse]:
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "lob_name" in filter_by:
                query["lob_name"] = {"$regex": filter_by["lob_name"], "$options": "i"}
            if "lob_code" in filter_by:
                query["lob_code"] = {"$regex": filter_by["lob_code"], "$options": "i"}
            if "lob_abbreviation" in filter_by:
                query["lob_abbreviation"] = {"$regex": filter_by["lob_abbreviation"], "$options": "i"}
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        lobs = await cursor.to_list(length=limit)
        return [LobResponse(**lob) for lob in lobs]

    async def update_lob(self, lob_id: int, update_data: LobUpdateSchema) -> Optional[LobResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": lob_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_lob = await collection.find_one({"id": lob_id})
        return LobResponse(**updated_lob) if updated_lob else None

    async def delete_lob(self, lob_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": lob_id})
        return result.deleted_count > 0

    async def count_lobs(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "lob_name" in filter_by:
                query["lob_name"] = {"$regex": filter_by["lob_name"], "$options": "i"}
            if "lob_code" in filter_by:
                query["lob_code"] = {"$regex": filter_by["lob_code"], "$options": "i"}
        
        return await collection.count_documents(query)

    async def bulk_create_lobs(self, lobs_data: List[LobCreateSchema]) -> List[LobResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        lobs_to_insert = []
        for lob_data in lobs_data:
            # Auto-generate ID
            lob_id = await self._generate_lob_id()
            
            lob_dict = lob_data.dict()
            lob_dict.update({
                "id": lob_id,
                "created_at": now,
                "updated_at": now
            })
            lobs_to_insert.append(lob_dict)
        """
        try:
            for row in lobs_to_insert: 
                filter_query = {'id': row['id']}
                update_data = {
                    '$set': {
                    'lob_code': row['lob_code'],
                    'lob_name': row['lob_name'],
                    'lob_abbreviation': row['lob_abbreviation'],
                    'active': row['active'],
                    'created_at': now,
                    'updated_at': now
                    }
                }
                result = await collection.update_one(filter_query, update_data, upsert=True)
                created_ids = result.upserted_id
        """
        try:
            result = await collection.insert_many(lobs_to_insert, ordered=False)
            
            created_ids = result.inserted_ids
            
            cursor = collection.find({"_id": {"$in": created_ids}})
            created_lobs = await cursor.to_list(length=len(created_ids))
            return [LobResponse(**lob) for lob in created_lobs]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_lob_id(self) -> Optional[int]:
        """Get the last used lob ID"""
        collection = await self.get_collection()
        last_lob = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_lob["id"] if last_lob else None

lob_service = LobService()