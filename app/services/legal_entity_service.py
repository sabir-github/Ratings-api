from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.legal_entity import LegalEntityCreateSchema, LegalEntityUpdateSchema
from app.models.legal_entity import LegalEntityResponse
from app.services.company_service import company_service
import logging
import re

logger = logging.getLogger(__name__)


class LegalEntityService:
    def __init__(self):
        self.collection_name = "legal_entities"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_legal_entity_id(self) -> int:
        return await get_next_sequence_value("legal_entity_id")

    async def _validate_company_exists(self, company_id: int):
        company = await company_service.get_company(company_id)
        if not company:
            raise ValueError(f"Company with id {company_id} does not exist")

    async def create_legal_entity(self, data: LegalEntityCreateSchema) -> LegalEntityResponse:
        await self._validate_company_exists(data.company_id)
        collection = await self.get_collection()
        entity_id = await self._generate_legal_entity_id()

        existing = await collection.find_one({"id": entity_id})
        if existing:
            raise ValueError("Legal entity with same ID already exists")

        now = datetime.now(timezone.utc)
        entity_dict = data.dict()
        entity_dict.update({"id": entity_id, "created_at": now, "updated_at": now})

        result = await collection.insert_one(entity_dict)
        created = await collection.find_one({"_id": result.inserted_id})
        return LegalEntityResponse(**created)

    async def get_legal_entity(self, entity_id: int) -> Optional[LegalEntityResponse]:
        collection = await self.get_collection()
        entity = await collection.find_one({"id": entity_id})
        return LegalEntityResponse(**entity) if entity else None

    async def get_legal_entities(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1,
    ) -> List[LegalEntityResponse]:
        collection = await self.get_collection()
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "company_id" in filter_by:
                query["company_id"] = filter_by["company_id"]
            if "legal_name" in filter_by:
                escaped = re.escape(filter_by["legal_name"])
                query["legal_name"] = {"$regex": f"^{escaped}", "$options": "i"}
            if "entity_type" in filter_by:
                escaped = re.escape(filter_by["entity_type"])
                query["entity_type"] = {"$regex": f"^{escaped}", "$options": "i"}
            if "identifier" in filter_by:
                escaped = re.escape(filter_by["identifier"])
                query["identifier"] = {"$regex": f"^{escaped}", "$options": "i"}
            if "jurisdiction" in filter_by:
                escaped = re.escape(filter_by["jurisdiction"])
                query["jurisdiction"] = {"$regex": f"^{escaped}", "$options": "i"}

        sort = [(sort_by, sort_order)] if sort_by else [("id", 1)]
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        entities = await cursor.to_list(length=limit)
        return [LegalEntityResponse(**e) for e in entities]

    async def update_legal_entity(
        self, entity_id: int, update_data: LegalEntityUpdateSchema
    ) -> Optional[LegalEntityResponse]:
        collection = await self.get_collection()
        update_dict = update_data.dict(exclude_unset=True)
        if not update_dict:
            return None
        update_dict["updated_at"] = datetime.now(timezone.utc)

        result = await collection.update_one({"id": entity_id}, {"$set": update_dict})
        if result.modified_count == 0:
            return None
        updated = await collection.find_one({"id": entity_id})
        return LegalEntityResponse(**updated) if updated else None

    async def delete_legal_entity(self, entity_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": entity_id})
        return result.deleted_count > 0

    async def count_legal_entities(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "company_id" in filter_by:
                query["company_id"] = filter_by["company_id"]
            if "legal_name" in filter_by:
                escaped = re.escape(filter_by["legal_name"])
                query["legal_name"] = {"$regex": f"^{escaped}", "$options": "i"}
        return await collection.count_documents(query)

    async def get_last_legal_entity_id(self) -> Optional[int]:
        collection = await self.get_collection()
        last = await collection.find_one({}, sort=[("id", -1)])
        return last["id"] if last else None


legal_entity_service = LegalEntityService()
