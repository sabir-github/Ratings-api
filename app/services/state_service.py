from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.state import StateCreateSchema, StateUpdateSchema
from app.models.state import StateResponse
import logging

logger = logging.getLogger(__name__)

class StateService:
    def __init__(self):
        self.collection_name = "states"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_state_id(self) -> int:
        """Generate auto-incrementing state ID"""
        return await get_next_sequence_value("state_id")

    async def create_state(self, state_data: StateCreateSchema) -> StateResponse:
        collection = await self.get_collection()
        
        # Auto-generate ID
        state_id = await self._generate_state_id()
        
        # Check if state with same ID or code exists
        existing_state = await collection.find_one({
            "$or": [
                {"id": state_id},
                {"state_code": state_data.state_code}
            ]
        })
        
        if existing_state:
            raise ValueError("State with same ID or code already exists")
        
        now = datetime.now(timezone.utc)
        state_dict = state_data.dict()
        state_dict.update({
            "id": state_id,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(state_dict)
        created_state = await collection.find_one({"_id": result.inserted_id})
        return StateResponse(**created_state)

    async def get_state(self, state_id: int) -> Optional[StateResponse]:
        collection = await self.get_collection()
        state = await collection.find_one({"id": state_id})
        return StateResponse(**state) if state else None

    async def get_states(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[StateResponse]:
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "state_name" in filter_by:
                query["state_name"] = {"$regex": filter_by["state_name"], "$options": "i"}
            if "state_code" in filter_by:
                query["state_code"] = {"$regex": filter_by["state_code"], "$options": "i"}
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        states = await cursor.to_list(length=limit)
        return [StateResponse(**state) for state in states]

    async def update_state(self, state_id: int, update_data: StateUpdateSchema) -> Optional[StateResponse]:
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
            
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": state_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_state = await collection.find_one({"id": state_id})
        return StateResponse(**updated_state) if updated_state else None

    async def delete_state(self, state_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": state_id})
        return result.deleted_count > 0

    async def count_states(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "state_name" in filter_by:
                query["state_name"] = {"$regex": filter_by["state_name"], "$options": "i"}
        
        return await collection.count_documents(query)

    async def bulk_create_states(self, states_data: List[StateCreateSchema]) -> List[StateResponse]:
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        states_to_insert = []
        for state_data in states_data:
            # Auto-generate ID
            state_id = await self._generate_state_id()
            
            state_dict = state_data.dict()
            state_dict.update({
                "id": state_id,
                "created_at": now,
                "updated_at": now
            })
            states_to_insert.append(state_dict)
        
        #try:
        #    for row in states_to_insert: 
        #        filter_query = {'id': row['id']}
        #        update_data = {
        #            '$set': {
        #            'state_code': row['state_code'],
        #            'state_name': row['state_name'],
        #            'active': row['active'],
        #            'created_at': now,
        #            'updated_at':now
        #            }
        #        }
        #       result = await collection.update_one(filter_query, update_data, upsert=True)
        #        created_ids = result.upserted_id
        try:
            result = await collection.insert_many(states_to_insert, ordered=False)
            created_ids = result.inserted_ids
            
            cursor = collection.find({"_id": {"$in": created_ids}})
            created_states = await cursor.to_list(length=len(created_ids))
            return [StateResponse(**state) for state in created_states]
            
        except Exception as e:
            logger.error(f"Bulk insert failed: {str(e)}")
            raise

    async def get_last_state_id(self) -> Optional[int]:
        """Get the last used state ID"""
        collection = await self.get_collection()
        last_state = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_state["id"] if last_state else None

state_service = StateService()