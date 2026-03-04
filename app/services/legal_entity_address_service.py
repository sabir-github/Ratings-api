from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value
from app.schemas.legal_entity_address import (
    LegalEntityAddressCreateSchema,
    LegalEntityAddressUpdateSchema,
)
from app.models.legal_entity_address import LegalEntityAddressResponse
from app.services.legal_entity_service import legal_entity_service
import logging
import re

logger = logging.getLogger(__name__)


class LegalEntityAddressService:
    def __init__(self):
        self.collection_name = "legal_entity_addresses"

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_address_id(self) -> int:
        return await get_next_sequence_value("legal_entity_address_id")

    async def _validate_legal_entity_exists(self, legal_entity_id: int):
        entity = await legal_entity_service.get_legal_entity(legal_entity_id)
        if not entity:
            raise ValueError(f"Legal entity with id {legal_entity_id} does not exist")

    async def create_address(
        self, data: LegalEntityAddressCreateSchema
    ) -> LegalEntityAddressResponse:
        await self._validate_legal_entity_exists(data.legal_entity_id)
        collection = await self.get_collection()
        address_id = await self._generate_address_id()

        existing = await collection.find_one({"id": address_id})
        if existing:
            raise ValueError("Address with same ID already exists")

        now = datetime.now(timezone.utc)
        addr_dict = data.dict()
        addr_dict.update({"id": address_id, "created_at": now, "updated_at": now})

        result = await collection.insert_one(addr_dict)
        created = await collection.find_one({"_id": result.inserted_id})
        return LegalEntityAddressResponse(**created)

    async def get_address(self, address_id: int) -> Optional[LegalEntityAddressResponse]:
        collection = await self.get_collection()
        addr = await collection.find_one({"id": address_id})
        return LegalEntityAddressResponse(**addr) if addr else None

    async def get_addresses(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1,
    ) -> List[LegalEntityAddressResponse]:
        collection = await self.get_collection()
        query = {}
        if filter_by:
            if "legal_entity_id" in filter_by:
                query["legal_entity_id"] = filter_by["legal_entity_id"]
            if "address_type" in filter_by:
                escaped = re.escape(filter_by["address_type"])
                query["address_type"] = {"$regex": f"^{escaped}", "$options": "i"}
            if "city" in filter_by:
                escaped = re.escape(filter_by["city"])
                query["city"] = {"$regex": f"^{escaped}", "$options": "i"}
            if "country_code" in filter_by:
                escaped = re.escape(filter_by["country_code"])
                query["country_code"] = {"$regex": f"^{escaped}", "$options": "i"}

        sort = [(sort_by, sort_order)] if sort_by else [("id", 1)]
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        addrs = await cursor.to_list(length=limit)
        return [LegalEntityAddressResponse(**a) for a in addrs]

    async def update_address(
        self, address_id: int, update_data: LegalEntityAddressUpdateSchema
    ) -> Optional[LegalEntityAddressResponse]:
        collection = await self.get_collection()
        update_dict = update_data.dict(exclude_unset=True)
        if not update_dict:
            return None
        update_dict["updated_at"] = datetime.now(timezone.utc)

        result = await collection.update_one({"id": address_id}, {"$set": update_dict})
        if result.modified_count == 0:
            return None
        updated = await collection.find_one({"id": address_id})
        return LegalEntityAddressResponse(**updated) if updated else None

    async def delete_address(self, address_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": address_id})
        return result.deleted_count > 0

    async def count_addresses(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        query = {}
        if filter_by:
            if "legal_entity_id" in filter_by:
                query["legal_entity_id"] = filter_by["legal_entity_id"]
            if "address_type" in filter_by:
                escaped = re.escape(filter_by["address_type"])
                query["address_type"] = {"$regex": f"^{escaped}", "$options": "i"}
        return await collection.count_documents(query)

    async def get_last_address_id(self) -> Optional[int]:
        collection = await self.get_collection()
        last = await collection.find_one({}, sort=[("id", -1)])
        return last["id"] if last else None


legal_entity_address_service = LegalEntityAddressService()
