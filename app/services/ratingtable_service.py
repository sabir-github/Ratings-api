from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value, get_client, rollback_sequence_value
from pymongo.errors import PyMongoError
from app.schemas.ratingtable import RatingTableCreateSchema, RatingTableUpdateSchema, RatingTableResponseSchema
from app.models.ratingtable import RatingTableResponse
from app.services.company_service import company_service
from app.services.lob_service import lob_service
from app.services.state_service import state_service
from app.services.product_service import product_service
from app.services.context_service import context_service
from app.services.legal_entity_service import legal_entity_service
import logging
import pandas as pd
import io
import json
import re

logger = logging.getLogger(__name__)

class RatingTableService:
    def __init__(self):
        self.collection_name = "ratingtables"
        self._transactions_supported = None

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_ratingtable_id(self) -> int:
        """Generate auto-incrementing rating table ID"""
        return await get_next_sequence_value("ratingtable_id")
    
    async def _check_transactions_supported(self) -> bool:
        """Check if MongoDB supports transactions (replica set or mongos)"""
        if self._transactions_supported is not None:
            return self._transactions_supported
        
        try:
            client = await get_client()
            # Check server status to see if it's a replica set or mongos
            server_status = await client.admin.command("isMaster")
            # Transactions are supported on replica sets (has 'setName') or mongos (has 'msg' == 'isdbgrid')
            if 'setName' in server_status or server_status.get('msg') == 'isdbgrid':
                self._transactions_supported = True
                return True
            else:
                self._transactions_supported = False
                logger.warning("MongoDB transactions not supported (standalone instance). Using non-transactional operations with error handling.")
                return False
        except Exception as e:
            # On any error, assume not supported for safety
            self._transactions_supported = False
            logger.warning(f"Could not determine transaction support, assuming not supported: {e}")
            return False

    async def _validate_associations(self, company: int, lob: int, state: int, product: int, context: Optional[int] = None, entity: Optional[int] = None):
        """Validate that all associated entities exist by id"""
        # Validate company
        if not isinstance(company, int) or company <= 0:
            raise ValueError("Company must be a positive integer ID")
        company_obj = await company_service.get_company(company)
        if not company_obj:
            raise ValueError(f"Company with id {company} does not exist")
        
        # Validate LOB
        if not isinstance(lob, int) or lob <= 0:
            raise ValueError("Lob must be a positive integer ID")
        lob_obj = await lob_service.get_lob(lob)
        if not lob_obj:
            raise ValueError(f"Lob with id {lob} does not exist")
        
        # Validate state
        if not isinstance(state, int) or state <= 0:
            raise ValueError("State must be a positive integer ID")
        state_obj = await state_service.get_state(state)
        if not state_obj:
            raise ValueError(f"State with id {state} does not exist")
        
        # Validate product
        if not isinstance(product, int) or product <= 0:
            raise ValueError("Product must be a positive integer ID")
        product_obj = await product_service.get_product(product)
        if not product_obj:
            raise ValueError(f"Product with id {product} does not exist")
        
        # Validate context (optional)
        if context is not None:
            if not isinstance(context, int) or context <= 0:
                raise ValueError("Context must be a positive integer ID")
            context_obj = await context_service.get_context(context)
            if not context_obj:
                raise ValueError(f"Context with id {context} does not exist")

        # Validate entity (required)
        if entity is not None:
            if not isinstance(entity, int) or entity <= 0:
                raise ValueError("Entity must be a positive integer ID")
            entity_obj = await legal_entity_service.get_legal_entity(entity)
            if not entity_obj:
                raise ValueError(f"Legal entity with id {entity} does not exist")

    def _serialize_datetime(self, obj: Any) -> Any:
        """Recursively convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_datetime(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(item) for item in obj]
        else:
            return obj

    def _compare_data(self, existing_data: list, new_data: list) -> Dict[str, Any]:
        """Compare two data arrays and return changes and additions"""
        import json
        
        # Normalize data for comparison (convert to JSON strings for deep comparison)
        existing_data_normalized = [json.dumps(item, sort_keys=True) if isinstance(item, dict) else json.dumps(item) for item in existing_data]
        new_data_normalized = [json.dumps(item, sort_keys=True) if isinstance(item, dict) else json.dumps(item) for item in new_data]
        
        existing_data_set = set(existing_data_normalized)
        new_data_set = set(new_data_normalized)
        
        # Find additions (items in new_data but not in existing_data)
        additions_indices = [i for i, item in enumerate(new_data_normalized) if item not in existing_data_set]
        additions = [new_data[i] for i in additions_indices]
        
        # Find removals (items in existing_data but not in new_data)
        removals_indices = [i for i, item in enumerate(existing_data_normalized) if item not in new_data_set]
        removals = [existing_data[i] for i in removals_indices]
        
        # Check if there are any changes
        has_changes = len(additions) > 0 or len(removals) > 0
        
        return {
            "has_changes": has_changes,
            "additions": additions,
            "removals": removals,
            "additions_count": len(additions),
            "removals_count": len(removals),
            "total_existing": len(existing_data),
            "total_new": len(new_data)
        }

    async def create_ratingtable(self, ratingtable_data: RatingTableCreateSchema) -> Dict[str, Any]:
        """Create a new rating table with data comparison using transaction if available"""
        collection = await self.get_collection()
        
        # Validate associations first
        await self._validate_associations(
            ratingtable_data.company,
            ratingtable_data.lob,
            ratingtable_data.state,
            ratingtable_data.product,
            ratingtable_data.context,
            ratingtable_data.entity
        )
        
        now = datetime.now(timezone.utc)
        
        # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
        if ratingtable_data.effective_date is not None:
            effective_date = ratingtable_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Auto-generate ID
        id_was_auto_generated = True
        ratingtable_id = await self._generate_ratingtable_id()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        # Initialize variables
        existing_table = None
        data_comparison = None
        new_version = None
        result = None
        expired_id = None
        
        try:
            if use_transactions:
                # Use transaction for all database write operations
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                existing_table, data_comparison, new_version, result = await self._create_ratingtable_in_transaction(
                                    collection, ratingtable_data, effective_date, ratingtable_id, now, session
                                )
                        except PyMongoError as e:
                            # If transaction not supported, fall back to non-transactional
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode")
                                self._transactions_supported = False
                                use_transactions = False
                                # Retry without transaction
                                existing_table, data_comparison, new_version, result, expired_id = await self._create_ratingtable_without_transaction(
                                    collection, ratingtable_data, effective_date, ratingtable_id, now
                                )
                            else:
                                logger.error(f"Database error in create_ratingtable transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in create_ratingtable transaction: {e}")
                            raise
                except PyMongoError as e:
                    # If session creation fails with transaction error, fall back
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode")
                        self._transactions_supported = False
                        existing_table, data_comparison, new_version, result, expired_id = await self._create_ratingtable_without_transaction(
                            collection, ratingtable_data, effective_date, ratingtable_id, now
                        )
                    else:
                        raise
            else:
                # Non-transactional path with manual error handling
                existing_table, data_comparison, new_version, result, expired_id = await self._create_ratingtable_without_transaction(
                    collection, ratingtable_data, effective_date, ratingtable_id, now
                )
                
        except Exception as e:
            # Rollback counter sequence if ID was auto-generated and record creation failed
            if id_was_auto_generated:
                try:
                    await rollback_sequence_value("ratingtable_id")
                    logger.info(f"Rolled back ratingtable_id sequence due to error: {e}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback ratingtable_id sequence: {rollback_error}")
            
            # Rollback expiration if record was expired but creation failed
            if expired_id and not use_transactions:
                try:
                    await collection.update_one(
                        {"id": expired_id},
                        {
                            "$set": {
                                "active": True,
                                "expiration_date": None
                            }
                        }
                    )
                    logger.info(f"Rolled back expiration of rating table with id {expired_id}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback expiration: {rollback_error}")
            raise
        
        # Check if result is None (transaction was aborted or no changes found)
        if result is None:
            # This means no changes were found, return early with appropriate message
            return {
                "message": "No changes found in data field. Record with same combination already exists.",
                "id": existing_table["id"] if existing_table else None,
                "existing_version": existing_table.get("version", 1.0) if existing_table else None,
                "data_comparison": data_comparison
            }
        
        # Fetch the created record
        created_table = await collection.find_one({"_id": result.inserted_id})
        if not created_table:
            raise ValueError("Failed to retrieve created rating table")
            
        normalized_created = self._normalize_table_document(created_table)
        created_table_schema = RatingTableResponseSchema(**normalized_created)
        
        # Convert to dict and serialize datetime objects for JSON compatibility
        rating_table_dict = created_table_schema.dict()
        rating_table_dict = self._serialize_datetime(rating_table_dict)
        
        # Determine if this was an update of existing record (had changes)
        had_existing = existing_table is not None
        
        return {
            "message": "Rating table created successfully with data changes" if had_existing else "Rating table created successfully",
            "rating_table": rating_table_dict,
            "data_comparison": data_comparison,
            "version": new_version
        }
    
    async def _create_ratingtable_in_transaction(self, collection, ratingtable_data, effective_date, ratingtable_id, now, session):
        """Helper method for transactional create operation"""
        # Check for existing record with same combination
        existing_table = await collection.find_one(
            {
                "table_name": ratingtable_data.table_name,
                "company": ratingtable_data.company,
                "lob": ratingtable_data.lob,
                "product": ratingtable_data.product,
                "state": ratingtable_data.state,
                "effective_date": effective_date,
                "active": True
            },
            session=session
        )
        
        # If existing record found, compare data
        if existing_table:
            existing_data = existing_table.get("data", [])
            new_data = ratingtable_data.data if ratingtable_data.data else []
            data_comparison = self._compare_data(existing_data, new_data)
            
            if not data_comparison["has_changes"]:
                await session.abort_transaction()
                return existing_table, data_comparison, None, None
            
            # Expire existing record
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_table["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                },
                session=session
            )
            logger.info(f"Expired existing rating table with id {existing_table['id']} due to data changes")
            new_version = existing_table.get("version", 1.0) + 1.0
        else:
            new_version = ratingtable_data.version if ratingtable_data.version is not None else 1.0
            new_data = ratingtable_data.data if ratingtable_data.data else []
            data_comparison = {
                "has_changes": True,
                "additions": new_data,
                "removals": [],
                "additions_count": len(new_data),
                "removals_count": 0,
                "total_existing": 0,
                "total_new": len(new_data)
            }
        
        # Check if rating table with same ID exists
        id_check = await collection.find_one({"id": ratingtable_id}, session=session)
        if id_check:
            await session.abort_transaction()
            raise ValueError("Rating table with same ID already exists")
        
        # Create new record
        ratingtable_dict = ratingtable_data.dict(exclude={'version'})
        ratingtable_dict["effective_date"] = effective_date
        ratingtable_dict.update({
            "id": ratingtable_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingtable_dict, session=session)
        return existing_table, data_comparison, new_version, result
    
    async def _create_ratingtable_without_transaction(self, collection, ratingtable_data, effective_date, ratingtable_id, now):
        """Helper method for non-transactional create operation with error handling"""
        # Check for existing record
        existing_table = await collection.find_one({
            "table_name": ratingtable_data.table_name,
            "company": ratingtable_data.company,
            "lob": ratingtable_data.lob,
            "product": ratingtable_data.product,
            "state": ratingtable_data.state,
            "effective_date": effective_date,
            "active": True
        })
        
        expired_id = None
        
        if existing_table:
            existing_data = existing_table.get("data", [])
            new_data = ratingtable_data.data if ratingtable_data.data else []
            data_comparison = self._compare_data(existing_data, new_data)
            
            if not data_comparison["has_changes"]:
                return existing_table, data_comparison, None, None, None
            
            # Expire existing record
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_table["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                }
            )
            expired_id = existing_table["id"]
            logger.info(f"Expired existing rating table with id {expired_id} due to data changes")
            new_version = existing_table.get("version", 1.0) + 1.0
        else:
            new_version = ratingtable_data.version if ratingtable_data.version is not None else 1.0
            new_data = ratingtable_data.data if ratingtable_data.data else []
            data_comparison = {
                "has_changes": True,
                "additions": new_data,
                "removals": [],
                "additions_count": len(new_data),
                "removals_count": 0,
                "total_existing": 0,
                "total_new": len(new_data)
            }
        
        # Check if rating table with same ID exists
        id_check = await collection.find_one({"id": ratingtable_id})
        if id_check:
            raise ValueError("Rating table with same ID already exists")
        
        # Create new record
        ratingtable_dict = ratingtable_data.dict(exclude={'version'})
        ratingtable_dict["effective_date"] = effective_date
        ratingtable_dict.update({
            "id": ratingtable_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingtable_dict)
        return existing_table, data_comparison, new_version, result, expired_id

    def _normalize_table_document(self, table: dict) -> dict:
        """Normalize MongoDB document to match schema expectations"""
        # Remove MongoDB _id field if present
        table = {k: v for k, v in table.items() if k != "_id"}
        
        # Handle data field - ensure it's a list
        if "data" not in table:
            logger.warning(f"Rating table {table.get('id')} is missing data field, defaulting to empty list")
            table["data"] = []
        elif not isinstance(table["data"], list):
            logger.warning(f"Rating table {table.get('id')} has invalid data type, converting to list")
            table["data"] = []
        
        # Handle lookup_config field - ensure it's a dict
        if "lookup_config" not in table:
            logger.warning(f"Rating table {table.get('id')} is missing lookup_config field, defaulting to empty dict")
            table["lookup_config"] = {}
        elif not isinstance(table["lookup_config"], dict):
            logger.warning(f"Rating table {table.get('id')} has invalid lookup_config type, converting to dict")
            table["lookup_config"] = {}
        
        # Handle ai_metadata field - ensure it's a dict
        if "ai_metadata" not in table:
            logger.warning(f"Rating table {table.get('id')} is missing ai_metadata field, defaulting to empty dict")
            table["ai_metadata"] = {}
        elif not isinstance(table["ai_metadata"], dict):
            logger.warning(f"Rating table {table.get('id')} has invalid ai_metadata type, converting to dict")
            table["ai_metadata"] = {}
        
        # Handle entity field - required; default 0 for legacy documents without it
        if "entity" not in table:
            table["entity"] = 0
        
        return table

    async def get_ratingtable(self, ratingtable_id: int) -> Optional[RatingTableResponseSchema]:
        """Get a rating table by ID"""
        collection = await self.get_collection()
        table = await collection.find_one({"id": ratingtable_id})
        if not table:
            return None
        normalized_table = self._normalize_table_document(table)
        return RatingTableResponseSchema(**normalized_table)

    async def get_ratingtables(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[RatingTableResponseSchema]:
        """Get all rating tables with pagination, filtering and sorting"""
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "table_name" in filter_by:
                query["table_name"] = {"$regex": filter_by["table_name"], "$options": "i"}
            if "table_type" in filter_by:
                query["table_type"] = filter_by["table_type"]
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "context_id" in filter_by:
                query["context"] = filter_by["context_id"]
            if "entity_id" in filter_by:
                query["entity"] = filter_by["entity_id"]
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        tables = await cursor.to_list(length=limit)
        normalized_tables = [self._normalize_table_document(table) for table in tables]
        return [RatingTableResponseSchema(**table) for table in normalized_tables]

    async def update_ratingtable(self, ratingtable_id: int, update_data: RatingTableUpdateSchema) -> Optional[RatingTableResponseSchema]:
        """Update a rating table using transaction if available"""
        collection = await self.get_collection()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                async with await client.start_session() as session:
                    try:
                        async with session.start_transaction():
                            existing_table = await collection.find_one({"id": ratingtable_id}, session=session)
                            if not existing_table:
                                await session.abort_transaction()
                                return None
                            
                            # Validate expiration_date >= effective_date
                            effective_date = update_data.effective_date if update_data.effective_date is not None else existing_table.get("effective_date")
                            expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_table.get("expiration_date")
                            
                            if effective_date and expiration_date:
                                if expiration_date < effective_date:
                                    await session.abort_transaction()
                                    raise ValueError("expiration_date cannot be less than effective_date")
                            
                            # Validate context and entity if being updated
                            if update_data.context is not None or getattr(update_data, 'entity', None) is not None:
                                await self._validate_associations(
                                    existing_table.get("company"),
                                    existing_table.get("lob"),
                                    existing_table.get("state"),
                                    existing_table.get("product"),
                                    update_data.context,
                                    getattr(update_data, 'entity', None)
                                )
                            
                            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                            if not update_dict:
                                await session.abort_transaction()
                                normalized_existing = self._normalize_table_document(existing_table)
                                return RatingTableResponseSchema(**normalized_existing)
                                
                            update_dict["updated_at"] = datetime.now(timezone.utc)
                            
                            result = await collection.update_one(
                                {"id": ratingtable_id},
                                {"$set": update_dict},
                                session=session
                            )
                            
                            if result.modified_count == 0:
                                await session.abort_transaction()
                                normalized_existing = self._normalize_table_document(existing_table)
                                return RatingTableResponseSchema(**normalized_existing)
                    except PyMongoError as e:
                        logger.error(f"Database error in update_ratingtable transaction: {e}")
                        raise
                    except Exception as e:
                        logger.error(f"Error in update_ratingtable transaction: {e}")
                        raise
            else:
                # Non-transactional path
                existing_table = await collection.find_one({"id": ratingtable_id})
                if not existing_table:
                    return None
                
                # Validate expiration_date >= effective_date
                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_table.get("effective_date")
                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_table.get("expiration_date")
                
                if effective_date and expiration_date:
                    if expiration_date < effective_date:
                        raise ValueError("expiration_date cannot be less than effective_date")
                
                # Validate context and entity if being updated
                if update_data.context is not None or getattr(update_data, 'entity', None) is not None:
                    await self._validate_associations(
                        existing_table.get("company"),
                        existing_table.get("lob"),
                        existing_table.get("state"),
                        existing_table.get("product"),
                        update_data.context,
                        getattr(update_data, 'entity', None)
                    )
                
                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                if not update_dict:
                    normalized_existing = self._normalize_table_document(existing_table)
                    return RatingTableResponseSchema(**normalized_existing)
                    
                update_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.update_one(
                    {"id": ratingtable_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    normalized_existing = self._normalize_table_document(existing_table)
                    return RatingTableResponseSchema(**normalized_existing)
        except Exception as e:
            logger.error(f"Error updating rating table: {e}")
            raise
        
        # Fetch the updated record
        updated_table = await collection.find_one({"id": ratingtable_id})
        if updated_table:
            normalized_updated = self._normalize_table_document(updated_table)
            return RatingTableResponseSchema(**normalized_updated)
        return None

    async def delete_ratingtable(self, ratingtable_id: int) -> bool:
        """Delete a rating table using transaction if available"""
        collection = await self.get_collection()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                async with await client.start_session() as session:
                    try:
                        async with session.start_transaction():
                            result = await collection.delete_one({"id": ratingtable_id}, session=session)
                            return result.deleted_count > 0
                    except PyMongoError as e:
                        logger.error(f"Database error in delete_ratingtable transaction: {e}")
                        raise
                    except Exception as e:
                        logger.error(f"Error in delete_ratingtable transaction: {e}")
                        raise
            else:
                # Non-transactional path
                result = await collection.delete_one({"id": ratingtable_id})
                return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting rating table: {e}")
            raise

    async def count_ratingtables(self, filter_by: Optional[Dict] = None) -> int:
        """Count rating tables with optional filters"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "table_name" in filter_by:
                query["table_name"] = {"$regex": filter_by["table_name"], "$options": "i"}
            if "table_type" in filter_by:
                query["table_type"] = filter_by["table_type"]
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "context_id" in filter_by:
                query["context"] = filter_by["context_id"]
            if "entity_id" in filter_by:
                query["entity"] = filter_by["entity_id"]
        
        return await collection.count_documents(query)

    async def bulk_create_ratingtables(self, ratingtables_data: List[RatingTableCreateSchema]) -> List[Dict[str, Any]]:
        """Bulk create rating tables with data comparison using transactions if available"""
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_minus_one = today - timedelta(days=1)
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        results = []
        
        for ratingtable_data in ratingtables_data:
            id_was_auto_generated = False
            try:
                # Validate associations first (outside transaction)
                await self._validate_associations(
                    ratingtable_data.company,
                    ratingtable_data.lob,
                    ratingtable_data.state,
                    ratingtable_data.product,
                    ratingtable_data.context
                )
                
                # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
                if ratingtable_data.effective_date is not None:
                    effective_date = ratingtable_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Auto-generate ID
                ratingtable_id = await self._generate_ratingtable_id()
                id_was_auto_generated = True
            
                existing_table = None
                data_comparison = None
                new_version = None
                result = None
                expired_id = None
                
                try:
                    if use_transactions:
                        # Use transaction for each record's database write operations
                        client = await get_client()
                        async with await client.start_session() as session:
                            try:
                                async with session.start_transaction():
                                    # Check for existing record with same combination
                                    existing_table = await collection.find_one(
                                        {
                                            "table_name": ratingtable_data.table_name,
                                            "company": ratingtable_data.company,
                                            "lob": ratingtable_data.lob,
                                            "product": ratingtable_data.product,
                                            "state": ratingtable_data.state,
                                            "effective_date": effective_date,
                                            "active": True
                                        },
                                        session=session
                                    )
                                    
                                    # If existing record found, compare data
                                    if existing_table:
                                        existing_data = existing_table.get("data", [])
                                        new_data = ratingtable_data.data if ratingtable_data.data else []
                                        data_comparison = self._compare_data(existing_data, new_data)
                                        
                                        if not data_comparison["has_changes"]:
                                            await session.abort_transaction()
                                            results.append({
                                                "message": "No changes found in data field. Record with same combination already exists.",
                                                "id": existing_table["id"],
                                                "existing_version": existing_table.get("version", 1.0),
                                                "data_comparison": data_comparison,
                                                "skipped": True
                                            })
                                            continue
                                        
                                        # Expire existing record
                                        await collection.update_one(
                                            {"id": existing_table["id"]},
                                            {
                                                "$set": {
                                                    "expiration_date": today_minus_one,
                                                    "active": False,
                                                    "updated_at": now
                                                }
                                            },
                                            session=session
                                        )
                                        logger.info(f"Expired existing rating table with id {existing_table['id']} due to data changes")
                                        new_version = existing_table.get("version", 1.0) + 1.0
                                    else:
                                        new_version = ratingtable_data.version if ratingtable_data.version is not None else 1.0
                                        new_data = ratingtable_data.data if ratingtable_data.data else []
                                        data_comparison = {
                                            "has_changes": True,
                                            "additions": new_data,
                                            "removals": [],
                                            "additions_count": len(new_data),
                                            "removals_count": 0,
                                            "total_existing": 0,
                                            "total_new": len(new_data)
                                        }
                                    
                                    # Check if rating table with same ID exists
                                    id_check = await collection.find_one({"id": ratingtable_id}, session=session)
                                    if id_check:
                                        await session.abort_transaction()
                                        # Rollback counter sequence if ID was auto-generated but duplicate found
                                        if id_was_auto_generated:
                                            try:
                                                await rollback_sequence_value("ratingtable_id")
                                                logger.info(f"Rolled back ratingtable_id sequence - duplicate ID {ratingtable_id}")
                                            except Exception as rollback_error:
                                                logger.error(f"Failed to rollback ratingtable_id sequence: {rollback_error}")
                                        logger.warning(f"Skipping rating table with duplicate ID {ratingtable_id}")
                                        results.append({
                                            "message": f"Skipped: Rating table with ID {ratingtable_id} already exists",
                                            "skipped": True
                                        })
                                        continue
                                    
                                    # Create new record
                                    ratingtable_dict = ratingtable_data.dict(exclude={'id', 'version'})
                                    ratingtable_dict["effective_date"] = effective_date
                                    ratingtable_dict.update({
                "id": ratingtable_id,
                                        "version": new_version,
                "created_at": now,
                "updated_at": now
            })
                                    
                                    result = await collection.insert_one(ratingtable_dict, session=session)
                            except PyMongoError as e:
                                logger.error(f"Database error in bulk_create_ratingtables transaction: {e}")
                                raise
                            except Exception as e:
                                logger.error(f"Error in bulk_create_ratingtables transaction: {str(e)}")
                                raise
                    else:
                        # Non-transactional path
                        existing_table, data_comparison, new_version, result, expired_id = await self._create_ratingtable_without_transaction(
                            collection, ratingtable_data, effective_date, ratingtable_id, now
                        )
                        
                except Exception as e:
                    # Rollback counter sequence if ID was auto-generated and record creation failed
                    if id_was_auto_generated:
                        try:
                            await rollback_sequence_value("ratingtable_id")
                            logger.info(f"Rolled back ratingtable_id sequence for record (ID: {ratingtable_id}) due to error: {e}")
                        except Exception as rollback_error:
                            logger.error(f"Failed to rollback ratingtable_id sequence: {rollback_error}")
                    
                    # If we expired a record but failed to create new one, try to rollback
                    if expired_id and not use_transactions:
                        try:
                            await collection.update_one(
                                {"id": expired_id},
                                {
                                    "$set": {
                                        "active": True,
                                        "expiration_date": None
                                    }
                                }
                            )
                            logger.info(f"Rolled back expiration of rating table with id {expired_id}")
                        except Exception as rollback_error:
                            logger.error(f"Failed to rollback expiration: {rollback_error}")
                    results.append({
                        "message": f"Error: {str(e)}",
                        "error": True
                    })
                    continue
                
                # Fetch the created record
                created_table = await collection.find_one({"_id": result.inserted_id})
                
                if created_table:
                    normalized_created = self._normalize_table_document(created_table)
                    created_table_schema = RatingTableResponseSchema(**normalized_created)
                    # Convert to dict and serialize datetime objects for JSON compatibility
                    rating_table_dict = created_table_schema.dict()
                    rating_table_dict = self._serialize_datetime(rating_table_dict)
                    
                    results.append({
                        "message": "Rating table created successfully with data changes" if existing_table else "Rating table created successfully",
                        "rating_table": rating_table_dict,
                        "data_comparison": data_comparison,
                        "version": new_version,
                        "created": True
                    })
                else:
                    results.append({
                        "message": f"Error: Failed to retrieve created rating table after insertion.",
                        "error": True
                    })
            except Exception as e:
                # Outer exception handler for validation errors before transaction
                logger.error(f"Error processing rating table (outside transaction): {str(e)}")
                # Rollback counter sequence if ID was auto-generated
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("ratingtable_id")
                        logger.info(f"Rolled back ratingtable_id sequence due to outer error: {e}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback ratingtable_id sequence: {rollback_error}")
                results.append({
                    "message": f"Error: {str(e)}",
                    "error": True
                })
        
        return results

    async def get_last_ratingtable_id(self) -> Optional[int]:
        """Get the last used rating table ID"""
        collection = await self.get_collection()
        last_table = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_table["id"] if last_table else None

    def _detect_table_type(self, df: pd.DataFrame, sheet_data: List[Dict[str, Any]]) -> str:
        """
        Detect table type based on the structure and content of the Excel data.
        
        Args:
            df: pandas DataFrame from Excel sheet
            sheet_data: List of dictionaries representing the data
        
        Returns:
            Detected table type: 'lookup', 'range', 'matrix', 'formula', or 'custom'
        """
        if df.empty or len(sheet_data) == 0:
            return "lookup"  # Default to lookup if no data
        
        # Get column names (case-insensitive)
        columns_lower = [col.lower().strip() for col in df.columns]
        
        # Check for range type indicators
        range_indicators = ['min', 'max', 'from', 'to', 'start', 'end', 'lower', 'upper', 
                           'minimum', 'maximum', 'range_min', 'range_max']
        has_range_columns = any(indicator in columns_lower for indicator in range_indicators)
        
        # Check if we have numeric columns that could represent ranges
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        has_numeric_pairs = len(numeric_cols) >= 2
        
        # Check for matrix/2D structure (multiple key columns and value columns)
        non_numeric_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        has_multiple_keys = len(non_numeric_cols) >= 2
        
        # Check for formula indicators (cells containing formulas, references, etc.)
        # This is harder to detect from pandas, but we can check for common patterns
        has_formula_indicators = False
        for col in df.columns:
            col_str = str(df[col].astype(str))
            if any(indicator in col_str.lower() for indicator in ['=', 'sum(', 'if(', 'vlookup', 'index(', 'match(']):
                has_formula_indicators = True
                break
        
        # Determine table type based on detected patterns
        if has_range_columns or (has_numeric_pairs and len(numeric_cols) == 2):
            return "range"
        elif has_formula_indicators:
            return "formula"
        elif has_multiple_keys and len(df.columns) > 3:
            return "matrix"
        else:
            # Default to lookup for simple key-value structures
            return "lookup"

    def _transform_data_by_type(self, sheet_data: List[Dict[str, Any]], table_type: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Transform data based on the detected table type.
        For range type, ensure min/max fields exist.
        
        Args:
            sheet_data: Original data as list of dictionaries
            table_type: Detected or provided table type
            df: Original pandas DataFrame
        
        Returns:
            Transformed data list
        """
        if not sheet_data:
            return sheet_data
        
        if table_type == "range":
            # Transform data for range type
            transformed_data = []
            
            for record in sheet_data:
                transformed_record = record.copy()
                
                # Get column names (case-insensitive mapping)
                col_mapping = {col.lower().strip(): col for col in df.columns}
                
                # Try to identify min/max columns
                min_col = None
                max_col = None
                
                # Check for explicit min/max columns
                for key_lower, original_key in col_mapping.items():
                    if key_lower in ['min', 'minimum', 'range_min', 'from', 'start', 'lower']:
                        min_col = original_key
                    elif key_lower in ['max', 'maximum', 'range_max', 'to', 'end', 'upper']:
                        max_col = original_key
                
                # If no explicit min/max, try to infer from numeric columns
                if not min_col or not max_col:
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    if len(numeric_cols) >= 2:
                        # Assume first two numeric columns are min/max
                        min_col = numeric_cols[0]
                        max_col = numeric_cols[1]
                    elif len(numeric_cols) == 1:
                        # Single numeric column - use it for both min and max
                        min_col = numeric_cols[0]
                        max_col = numeric_cols[0]
                
                # Extract min/max values
                min_value = transformed_record.get(min_col) if min_col else None
                max_value = transformed_record.get(max_col) if max_col else None
                
                # If we have values but they're not in min/max format, create them
                if min_value is not None or max_value is not None:
                    # Ensure min/max fields exist
                    if 'min' not in transformed_record and min_value is not None:
                        transformed_record['min'] = min_value
                    if 'max' not in transformed_record and max_value is not None:
                        transformed_record['max'] = max_value
                    
                    # If only one value exists, use it for both
                    if transformed_record.get('min') is not None and transformed_record.get('max') is None:
                        transformed_record['max'] = transformed_record['min']
                    elif transformed_record.get('max') is not None and transformed_record.get('min') is None:
                        transformed_record['min'] = transformed_record['max']
                else:
                    # No numeric values found, set defaults
                    transformed_record['min'] = None
                    transformed_record['max'] = None
                
                transformed_data.append(transformed_record)
            
            return transformed_data
        
        elif table_type == "matrix":
            # For matrix type, ensure we have proper structure
            # Keep data as-is but could add validation/transformation here
            return sheet_data
        
        elif table_type == "formula":
            # For formula type, keep data as-is
            # Formulas are typically stored as strings
            return sheet_data
        
        else:
            # For lookup and other types, return as-is
            return sheet_data

    async def import_from_excel(
        self,
        file_content: bytes,
        company: int,
        lob: int,
        state: int,
        product: int,
        entity: int,
        context: Optional[int] = None,
        table_type: Optional[str] = None,
        effective_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Import rating tables from Excel file.
        Each sheet in the Excel file represents a new rating table record.
        Sheet name is used as table_name.
        Sheet data is converted to JSON and stored in the data field.
        
        Args:
            file_content: Excel file content as bytes
            company: Company ID (mandatory)
            lob: LOB ID (mandatory)
            state: State ID (mandatory)
            product: Product ID (mandatory)
            entity: Legal entity ID (mandatory)
            context: Context ID (optional)
            table_type: Table type (optional)
            effective_date: Effective date (optional, defaults to current date)
        
        Returns:
            Dictionary with import results including created, skipped, and error counts
        """
        results = {
            "total_sheets": 0,
            "created": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        try:
            # Validate associations first (outside transaction)
            await self._validate_associations(company, lob, state, product, context, entity)
            
            # Read Excel file
            excel_file = io.BytesIO(file_content)
            excel_reader = pd.ExcelFile(excel_file, engine='openpyxl')
            
            results["total_sheets"] = len(excel_reader.sheet_names)
            
            # Process each sheet
            for sheet_name in excel_reader.sheet_names:
                try:
                    # Skip empty sheet names
                    if not sheet_name or not sheet_name.strip():
                        logger.warning(f"Skipping sheet with empty name")
                        results["skipped"] += 1
                        results["details"].append({
                            "sheet_name": sheet_name or "(empty)",
                            "status": "skipped",
                            "message": "Sheet name is empty"
                        })
                        continue
                    
                    # Read sheet data using the ExcelFile object
                    df = excel_reader.parse(sheet_name=sheet_name)
                    
                    # Convert DataFrame to list of dictionaries (JSON-compatible)
                    # Replace NaN values with None for JSON serialization
                    df = df.where(pd.notnull(df), None)
                    sheet_data = df.to_dict('records')
                    
                    # Validate sheet has data
                    if not sheet_data or len(sheet_data) == 0:
                        logger.warning(f"Sheet '{sheet_name}' has no data")
                        results["skipped"] += 1
                        results["details"].append({
                            "sheet_name": sheet_name,
                            "status": "skipped",
                            "message": "Sheet has no data"
                        })
                        continue
                    
                    # Detect table_type if not provided
                    detected_table_type = table_type
                    if not table_type or table_type.strip() == "":
                        detected_table_type = self._detect_table_type(df, sheet_data)
                        logger.info(f"Detected table_type '{detected_table_type}' for sheet '{sheet_name}'")
                    
                    # Transform data based on detected/provided table_type
                    transformed_data = self._transform_data_by_type(sheet_data, detected_table_type, df)
                    
                    # Create rating table schema
                    ratingtable_data = RatingTableCreateSchema(
                        table_name=sheet_name.strip(),
                        company=company,
                        lob=lob,
                        state=state,
                        product=product,
                        entity=entity,
                        context=context,
                        table_type=detected_table_type,
                        effective_date=effective_date,
                        data=transformed_data,
                        active=True
                    )
                    
                    # Create rating table (this will handle validation, existence check, and transactions)
                    try:
                        create_result = await self.create_ratingtable(ratingtable_data)
                        
                        # Check if record was created or skipped
                        if "message" in create_result and "No changes found" in create_result.get("message", ""):
                            results["skipped"] += 1
                            results["details"].append({
                                "sheet_name": sheet_name,
                                "status": "skipped",
                                "message": create_result.get("message", "No changes found"),
                                "id": create_result.get("id"),
                                "data_comparison": create_result.get("data_comparison", {})
                            })
                        else:
                            results["created"] += 1
                            results["details"].append({
                                "sheet_name": sheet_name,
                                "status": "created",
                                "message": create_result.get("message", "Rating table created successfully"),
                                "rating_table_id": create_result.get("rating_table", {}).get("id"),
                                "version": create_result.get("version"),
                                "data_comparison": create_result.get("data_comparison", {})
                            })
                            
                    except ValueError as e:
                        # Validation errors
                        error_msg = str(e)
                        logger.error(f"Validation error for sheet '{sheet_name}': {error_msg}")
                        results["errors"] += 1
                        results["details"].append({
                            "sheet_name": sheet_name,
                            "status": "error",
                            "message": f"Validation error: {error_msg}"
                        })
                    except Exception as e:
                        # Other errors
                        error_msg = str(e)
                        logger.error(f"Error creating rating table for sheet '{sheet_name}': {error_msg}")
                        results["errors"] += 1
                        results["details"].append({
                            "sheet_name": sheet_name,
                            "status": "error",
                            "message": f"Error: {error_msg}"
                        })
                        
                except Exception as e:
                    # Error reading or processing sheet
                    error_msg = str(e)
                    logger.error(f"Error processing sheet '{sheet_name}': {error_msg}")
                    results["errors"] += 1
                    results["details"].append({
                        "sheet_name": sheet_name,
                        "status": "error",
                        "message": f"Error processing sheet: {error_msg}"
                    })
                    continue
            
            # Set overall status message
            if results["errors"] == 0 and results["created"] > 0:
                results["message"] = f"Successfully imported {results['created']} rating table(s)"
            elif results["skipped"] > 0 and results["created"] == 0:
                results["message"] = f"All {results['skipped']} sheet(s) were skipped (no changes found)"
            elif results["errors"] > 0:
                results["message"] = f"Import completed with {results['errors']} error(s)"
            else:
                results["message"] = "Import completed"
            
            return results
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error importing Excel file: {error_msg}")
            results["message"] = f"Error importing Excel file: {error_msg}"
            results["errors"] = results["total_sheets"]
            raise ValueError(f"Failed to import Excel file: {error_msg}")

ratingtable_service = RatingTableService()
