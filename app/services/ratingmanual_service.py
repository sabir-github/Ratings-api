from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value, get_client, rollback_sequence_value
from pymongo.errors import PyMongoError
from app.schemas.ratingmanual import RatingManualCreateSchema, RatingManualUpdateSchema, RatingManualResponseSchema
from app.services.company_service import company_service
from app.services.lob_service import lob_service
from app.services.state_service import state_service
from app.services.product_service import product_service
from app.services.ratingtable_service import ratingtable_service
from app.services.legal_entity_service import legal_entity_service
import logging

logger = logging.getLogger(__name__)

class RatingManualService:
    def __init__(self):
        self.collection_name = "ratingmanuals"
        self._transactions_supported: Optional[bool] = None

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_ratingmanual_id(self) -> int:
        """Generate auto-incrementing rating manual ID"""
        return await get_next_sequence_value("ratingmanual_id")
    
    async def _check_transactions_supported(self) -> bool:
        """Check if MongoDB supports transactions (replica set or mongos)"""
        if self._transactions_supported is not None:
            return self._transactions_supported
        
        try:
            client = await get_client()
            server_status = await client.admin.command("isMaster")
            if 'setName' in server_status or server_status.get('msg') == 'isdbgrid':
                self._transactions_supported = True
                return True
            else:
                self._transactions_supported = False
                logger.warning("MongoDB transactions not supported (standalone instance). Using non-transactional operations with error handling.")
                return False
        except Exception as e:
            self._transactions_supported = False
            logger.warning(f"Could not determine transaction support, assuming not supported: {e}")
            return False

    async def _validate_associations(self, company: int, lob: int, state: int, product: int, ratingtables: List[int], entity: Optional[int] = None):
        """Validate that all associated entities exist by id"""
        if not isinstance(company, int) or company <= 0:
            raise ValueError("Company must be a positive integer ID")
        company_obj = await company_service.get_company(company)
        if not company_obj:
            raise ValueError(f"Company with id {company} does not exist")
        
        if not isinstance(lob, int) or lob <= 0:
            raise ValueError("Lob must be a positive integer ID")
        lob_obj = await lob_service.get_lob(lob)
        if not lob_obj:
            raise ValueError(f"Lob with id {lob} does not exist")
        
        if not isinstance(state, int) or state <= 0:
            raise ValueError("State must be a positive integer ID")
        state_obj = await state_service.get_state(state)
        if not state_obj:
            raise ValueError(f"State with id {state} does not exist")
        
        if not isinstance(product, int) or product <= 0:
            raise ValueError("Product must be a positive integer ID")
        product_obj = await product_service.get_product(product)
        if not product_obj:
            raise ValueError(f"Product with id {product} does not exist")
        
        if not isinstance(ratingtables, list) or len(ratingtables) == 0:
            raise ValueError("Rating tables must be a non-empty list")
        for ratingtable_id in ratingtables:
            if not isinstance(ratingtable_id, int) or ratingtable_id <= 0:
                raise ValueError(f"Rating table ID {ratingtable_id} must be a positive integer")
            ratingtable_obj = await ratingtable_service.get_ratingtable(ratingtable_id)
            if not ratingtable_obj:
                raise ValueError(f"Rating table with id {ratingtable_id} does not exist")

        # Validate entity (required for create)
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
            return {k: self._serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(elem) for elem in obj]
        return obj

    def _compare_ratingtable(self, existing_ratingtables: List[int], new_ratingtables: List[int]) -> Dict[str, Any]:
        """Compare rating table ID lists and return comparison result"""
        # Sort lists for comparison to handle order differences
        existing_sorted = sorted(existing_ratingtables) if existing_ratingtables else []
        new_sorted = sorted(new_ratingtables) if new_ratingtables else []
        has_changes = existing_sorted != new_sorted
        
        return {
            "has_changes": has_changes,
            "existing_ratingtable": existing_ratingtables,
            "new_ratingtable": new_ratingtables
        }

    async def create_ratingmanual(self, ratingmanual_data: RatingManualCreateSchema) -> Dict[str, Any]:
        """Create a new rating manual with ratingtable comparison using transaction if available"""
        collection = await self.get_collection()
        
        # Validate associations first
        await self._validate_associations(
            ratingmanual_data.company,
            ratingmanual_data.lob,
            ratingmanual_data.state,
            ratingmanual_data.product,
            ratingmanual_data.ratingtable,
            ratingmanual_data.entity
        )
        
        now = datetime.now(timezone.utc)
        
        # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
        if ratingmanual_data.effective_date is not None:
            effective_date = ratingmanual_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Auto-generate ID
        id_was_auto_generated = True
        ratingmanual_id = await self._generate_ratingmanual_id()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        # Initialize variables
        existing_manual = None
        ratingtable_comparison = None
        new_version = None
        result = None
        expired_id = None
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                existing_manual, ratingtable_comparison, new_version, result = await self._create_ratingmanual_in_transaction(
                                    collection, ratingmanual_data, effective_date, ratingmanual_id, now, session
                                )
                        except PyMongoError as e:
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode")
                                self._transactions_supported = False
                                use_transactions = False
                                existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                                    collection, ratingmanual_data, effective_date, ratingmanual_id, now
                                )
                            else:
                                logger.error(f"Database error in create_ratingmanual transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in create_ratingmanual transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode")
                        self._transactions_supported = False
                        existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                            collection, ratingmanual_data, effective_date, ratingmanual_id, now
                        )
                    else:
                        raise
            else:
                existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                    collection, ratingmanual_data, effective_date, ratingmanual_id, now
                )
                
        except Exception as e:
            # Rollback counter sequence if ID was auto-generated and record creation failed
            if id_was_auto_generated:
                try:
                    await rollback_sequence_value("ratingmanual_id")
                    logger.info(f"Rolled back ratingmanual_id sequence due to error: {e}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback ratingmanual_id sequence: {rollback_error}")
            
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
                    logger.info(f"Rolled back expiration of rating manual with id {expired_id}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback expiration: {rollback_error}")
            raise
        
        if result is None:
            return {
                "message": "No changes found in ratingtable field. Record with same combination already exists.",
                "id": existing_manual["id"] if existing_manual else None,
                "existing_version": existing_manual.get("version", 1.0) if existing_manual else None,
                "ratingtable_comparison": ratingtable_comparison
            }

        # Fetch the created record
        created_manual = await collection.find_one({"_id": result.inserted_id})
        if not created_manual:
            raise ValueError("Failed to retrieve created rating manual after insertion.")

        normalized_manual = self._normalize_manual_document(created_manual)
        created_manual_schema = RatingManualResponseSchema(**normalized_manual)
        rating_manual_dict = created_manual_schema.dict()
        rating_manual_dict = self._serialize_datetime(rating_manual_dict)
        
        had_existing = existing_manual is not None
        
        return {
            "message": "Rating manual created successfully with ratingtable changes" if had_existing else "Rating manual created successfully",
            "rating_manual": rating_manual_dict,
            "ratingtable_comparison": ratingtable_comparison,
            "version": new_version
        }
    
    async def _create_ratingmanual_in_transaction(self, collection, ratingmanual_data, effective_date, ratingmanual_id, now, session):
        """Helper method for transactional create operation"""
        # Check for existing record with same combination (excluding ratingtable)
        existing_manual = await collection.find_one(
            {
                "manual_name": ratingmanual_data.manual_name,
                "company": ratingmanual_data.company,
                "lob": ratingmanual_data.lob,
                "product": ratingmanual_data.product,
                "state": ratingmanual_data.state,
                "effective_date": effective_date,
                "active": True
            },
            session=session
        )
        
        if existing_manual:
            existing_ratingtable = existing_manual.get("ratingtable")
            new_ratingtable = ratingmanual_data.ratingtable
            ratingtable_comparison = self._compare_ratingtable(existing_ratingtable, new_ratingtable)
            
            if not ratingtable_comparison["has_changes"]:
                await session.abort_transaction()
                return existing_manual, ratingtable_comparison, None, None
            
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_manual["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                },
                session=session
            )
            logger.info(f"Expired existing rating manual with id {existing_manual['id']} due to ratingtable changes")
            new_version = existing_manual.get("version", 1.0) + 1.0
        else:
            new_version = ratingmanual_data.version if ratingmanual_data.version is not None else 1.0
            ratingtable_comparison = {
                "has_changes": True,
                "existing_ratingtable": None,
                "new_ratingtable": ratingmanual_data.ratingtable
            }
        
        id_check = await collection.find_one({"id": ratingmanual_id}, session=session)
        if id_check:
            await session.abort_transaction()
            raise ValueError("Rating manual with same ID already exists")
        
        ratingmanual_dict = ratingmanual_data.dict(exclude={'version'})
        ratingmanual_dict["effective_date"] = effective_date
        ratingmanual_dict.update({
            "id": ratingmanual_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingmanual_dict, session=session)
        return existing_manual, ratingtable_comparison, new_version, result
    
    async def _create_ratingmanual_without_transaction(self, collection, ratingmanual_data, effective_date, ratingmanual_id, now):
        """Helper method for non-transactional create operation with error handling"""
        # Check for existing record with same combination (excluding ratingtable)
        existing_manual = await collection.find_one({
            "manual_name": ratingmanual_data.manual_name,
            "company": ratingmanual_data.company,
            "lob": ratingmanual_data.lob,
            "product": ratingmanual_data.product,
            "state": ratingmanual_data.state,
            "effective_date": effective_date,
            "active": True
        })
        
        expired_id = None
        
        if existing_manual:
            existing_ratingtable = existing_manual.get("ratingtable")
            new_ratingtable = ratingmanual_data.ratingtable
            ratingtable_comparison = self._compare_ratingtable(existing_ratingtable, new_ratingtable)
            
            if not ratingtable_comparison["has_changes"]:
                return existing_manual, ratingtable_comparison, None, None, None
            
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_manual["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                }
            )
            expired_id = existing_manual["id"]
            logger.info(f"Expired existing rating manual with id {expired_id} due to ratingtable changes")
            new_version = existing_manual.get("version", 1.0) + 1.0
        else:
            new_version = ratingmanual_data.version if ratingmanual_data.version is not None else 1.0
            ratingtable_comparison = {
                "has_changes": True,
                "existing_ratingtable": None,
                "new_ratingtable": ratingmanual_data.ratingtable
            }
        
        id_check = await collection.find_one({"id": ratingmanual_id})
        if id_check:
            raise ValueError("Rating manual with same ID already exists")
        
        ratingmanual_dict = ratingmanual_data.dict(exclude={'version'})
        ratingmanual_dict["effective_date"] = effective_date
        ratingmanual_dict.update({
            "id": ratingmanual_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingmanual_dict)
        return existing_manual, ratingtable_comparison, new_version, result, expired_id

    def _normalize_manual_document(self, manual: dict) -> dict:
        """Normalize MongoDB document to match schema expectations"""
        # Remove MongoDB _id field if present
        manual = {k: v for k, v in manual.items() if k != "_id"}
        
        # Handle ratingtable field - convert from old format if needed
        if "ratingtable" not in manual:
            # If ratingtable is missing, try to find it under old field names or set default
            if "algorithm" in manual:
                # Old format might have been algorithm (single int), convert to list
                algorithm_value = manual.get("algorithm")
                if isinstance(algorithm_value, int):
                    manual["ratingtable"] = [algorithm_value]
                elif isinstance(algorithm_value, list):
                    manual["ratingtable"] = algorithm_value
                else:
                    manual["ratingtable"] = []
            else:
                # Default to empty list if field is completely missing
                logger.warning(f"Rating manual {manual.get('id')} is missing ratingtable field, defaulting to empty list")
                manual["ratingtable"] = []
        elif not isinstance(manual["ratingtable"], list):
            # If ratingtable exists but is not a list, convert it
            if isinstance(manual["ratingtable"], int):
                manual["ratingtable"] = [manual["ratingtable"]]
            else:
                logger.warning(f"Rating manual {manual.get('id')} has invalid ratingtable type, converting to list")
                manual["ratingtable"] = []
        
        # Handle entity field - required; default 0 for legacy documents without it
        if "entity" not in manual:
            manual["entity"] = 0
        
        return manual

    async def get_ratingmanual(self, ratingmanual_id: int) -> Optional[RatingManualResponseSchema]:
        """Get a rating manual by ID"""
        collection = await self.get_collection()
        manual = await collection.find_one({"id": ratingmanual_id})
        if not manual:
            return None
        normalized_manual = self._normalize_manual_document(manual)
        return RatingManualResponseSchema(**normalized_manual)

    async def get_ratingmanuals(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[RatingManualResponseSchema]:
        """Get all rating manuals with pagination, filtering and sorting"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "manual_name" in filter_by:
                query["manual_name"] = {"$regex": filter_by["manual_name"], "$options": "i"}
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "entity_id" in filter_by:
                query["entity"] = filter_by["entity_id"]
            if "ratingtable_id" in filter_by:
                # Filter by ratingtable_id - MongoDB will check if the value is in the ratingtable array
                query["ratingtable"] = filter_by["ratingtable_id"]
            if "effective_date" in filter_by:
                query["effective_date"] = filter_by["effective_date"]
        
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        manuals = await cursor.to_list(length=limit)
        normalized_manuals = [self._normalize_manual_document(manual) for manual in manuals]
        return [RatingManualResponseSchema(**manual) for manual in normalized_manuals]

    async def update_ratingmanual(self, ratingmanual_id: int, update_data: RatingManualUpdateSchema) -> Optional[RatingManualResponseSchema]:
        """Update a rating manual using transaction if available"""
        collection = await self.get_collection()
        
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                existing_manual = await collection.find_one({"id": ratingmanual_id}, session=session)
                                if not existing_manual:
                                    await session.abort_transaction()
                                    return None
                                
                                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_manual.get("effective_date")
                                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_manual.get("expiration_date")
                                
                                if effective_date and expiration_date:
                                    if expiration_date < effective_date:
                                        await session.abort_transaction()
                                        raise ValueError("expiration_date cannot be less than effective_date")
                                
                                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                                if not update_dict:
                                    await session.abort_transaction()
                                    normalized_existing = self._normalize_manual_document(existing_manual)
                                    return RatingManualResponseSchema(**normalized_existing)
                                    
                                update_dict["updated_at"] = datetime.now(timezone.utc)
                                
                                result = await collection.update_one(
                                    {"id": ratingmanual_id},
                                    {"$set": update_dict},
                                    session=session
                                )
                                
                                if result.modified_count == 0:
                                    await session.abort_transaction()
                                    normalized_existing = self._normalize_manual_document(existing_manual)
                                    return RatingManualResponseSchema(**normalized_existing)
                        except PyMongoError as e:
                            logger.error(f"Database error in update_ratingmanual transaction: {e}")
                            raise
                        except Exception as e:
                            logger.error(f"Error in update_ratingmanual transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for update")
                        self._transactions_supported = False
                        existing_manual = await collection.find_one({"id": ratingmanual_id})
                        if not existing_manual:
                            return None
                        
                        effective_date = update_data.effective_date if update_data.effective_date is not None else existing_manual.get("effective_date")
                        expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_manual.get("expiration_date")
                        
                        if effective_date and expiration_date:
                            if expiration_date < effective_date:
                                raise ValueError("expiration_date cannot be less than effective_date")
                        
                        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                        if not update_dict:
                            normalized_existing = self._normalize_manual_document(existing_manual)
                            return RatingManualResponseSchema(**normalized_existing)
                            
                        update_dict["updated_at"] = datetime.now(timezone.utc)
                        
                        result = await collection.update_one(
                            {"id": ratingmanual_id},
                            {"$set": update_dict}
                        )
                        
                        if result.modified_count == 0:
                            normalized_existing = self._normalize_manual_document(existing_manual)
                            return RatingManualResponseSchema(**normalized_existing)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error updating rating manual: {e}")
                    raise
            else:
                existing_manual = await collection.find_one({"id": ratingmanual_id})
                if not existing_manual:
                    return None
                
                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_manual.get("effective_date")
                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_manual.get("expiration_date")
                
                if effective_date and expiration_date:
                    if expiration_date < effective_date:
                        raise ValueError("expiration_date cannot be less than effective_date")
                
                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                if not update_dict:
                    normalized_existing = self._normalize_manual_document(existing_manual)
                    return RatingManualResponseSchema(**normalized_existing)
                    
                update_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.update_one(
                    {"id": ratingmanual_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    normalized_existing = self._normalize_manual_document(existing_manual)
                    return RatingManualResponseSchema(**normalized_existing)
                    
        except Exception as e:
            logger.error(f"Error updating rating manual: {e}")
            raise
        
        updated_manual = await collection.find_one({"id": ratingmanual_id})
        if updated_manual:
            normalized_updated = self._normalize_manual_document(updated_manual)
            return RatingManualResponseSchema(**normalized_updated)
        return None

    async def delete_ratingmanual(self, ratingmanual_id: int) -> bool:
        """Delete a rating manual using transaction if available"""
        collection = await self.get_collection()
        
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                result = await collection.delete_one({"id": ratingmanual_id}, session=session)
                                return result.deleted_count > 0
                        except PyMongoError as e:
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                                self._transactions_supported = False
                                result = await collection.delete_one({"id": ratingmanual_id})
                                return result.deleted_count > 0
                            else:
                                logger.error(f"Database error in delete_ratingmanual transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in delete_ratingmanual transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                        self._transactions_supported = False
                        result = await collection.delete_one({"id": ratingmanual_id})
                        return result.deleted_count > 0
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error deleting rating manual: {e}")
                    raise
            else:
                result = await collection.delete_one({"id": ratingmanual_id})
                return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting rating manual: {e}")
            raise

    async def count_ratingmanuals(self, filter_by: Optional[Dict] = None) -> int:
        """Count rating manuals with optional filters"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "manual_name" in filter_by:
                query["manual_name"] = {"$regex": filter_by["manual_name"], "$options": "i"}
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "entity_id" in filter_by:
                query["entity"] = filter_by["entity_id"]
            if "ratingtable_id" in filter_by:
                # Filter by ratingtable_id - MongoDB will check if the value is in the ratingtable array
                query["ratingtable"] = filter_by["ratingtable_id"]
            if "effective_date" in filter_by:
                query["effective_date"] = filter_by["effective_date"]
        
        return await collection.count_documents(query)

    async def bulk_create_ratingmanuals(self, ratingmanuals_data: List[RatingManualCreateSchema]) -> List[Dict[str, Any]]:
        """Bulk create rating manuals with ratingtable comparison using transactions if available"""
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        results = []
        use_transactions = await self._check_transactions_supported()

        for ratingmanual_data in ratingmanuals_data:
            existing_manual = None
            ratingtable_comparison = None
            new_version = None
            result = None
            expired_id = None
            
            try:
                await self._validate_associations(
                    ratingmanual_data.company,
                    ratingmanual_data.lob,
                    ratingmanual_data.state,
                    ratingmanual_data.product,
                    ratingmanual_data.ratingtable,
                    ratingmanual_data.entity
                )
                
                if ratingmanual_data.effective_date is not None:
                    effective_date = ratingmanual_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Auto-generate ID
                ratingmanual_id = await self._generate_ratingmanual_id()
                id_was_auto_generated = True
                
                if use_transactions:
                    client = await get_client()
                    try:
                        async with await client.start_session() as session:
                            try:
                                async with session.start_transaction():
                                    existing_manual, ratingtable_comparison, new_version, result = await self._create_ratingmanual_in_transaction(
                                        collection, ratingmanual_data, effective_date, ratingmanual_id, now, session
                                    )
                            except PyMongoError as e:
                                if e.code == 20:  # IllegalOperation
                                    logger.warning(f"Transactions not supported for record (ID: {ratingmanual_id}), falling back to non-transactional mode")
                                    self._transactions_supported = False
                                    use_transactions = False
                                    existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                                        collection, ratingmanual_data, effective_date, ratingmanual_id, now
                                    )
                                else:
                                    logger.error(f"Database error in bulk_create_ratingmanuals transaction for record (ID: {ratingmanual_id}): {e}")
                                    raise
                            except Exception as e:
                                logger.error(f"Error in bulk_create_ratingmanuals transaction for record (ID: {ratingmanual_id}): {str(e)}")
                                raise
                    except PyMongoError as e:
                        if e.code == 20:  # IllegalOperation
                            logger.warning(f"Transactions not supported for record (ID: {ratingmanual_id}), falling back to non-transactional mode")
                            self._transactions_supported = False
                            use_transactions = False
                            existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                                collection, ratingmanual_data, effective_date, ratingmanual_id, now
                            )
                        else:
                            raise
                    except Exception as e:
                        logger.error(f"Error processing rating manual (ID: {ratingmanual_id}): {e}")
                        raise
                else:
                    existing_manual, ratingtable_comparison, new_version, result, expired_id = await self._create_ratingmanual_without_transaction(
                        collection, ratingmanual_data, effective_date, ratingmanual_id, now
                    )
                    
            except Exception as e:
                # Rollback counter sequence if ID was auto-generated and record creation failed
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("ratingmanual_id")
                        logger.info(f"Rolled back ratingmanual_id sequence for record (ID: {ratingmanual_id}) due to error: {e}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback ratingmanual_id sequence: {rollback_error}")
                
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
                        logger.info(f"Rolled back expiration of rating manual with id {expired_id}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback expiration: {rollback_error}")
                results.append({
                    "message": f"Error processing record (ID: {ratingmanual_id}): {str(e)}",
                    "error": True
                })
                continue
            
            if result is None:
                # Rollback counter sequence if ID was auto-generated but no record was created
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("ratingmanual_id")
                        logger.info(f"Rolled back ratingmanual_id sequence - no changes found for record (ID: {ratingmanual_id})")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback ratingmanual_id sequence: {rollback_error}")
                
                results.append({
                    "message": "No changes found in ratingtable field. Record with same combination already exists.",
                    "id": existing_manual["id"],
                    "existing_version": existing_manual.get("version", 1.0),
                    "ratingtable_comparison": ratingtable_comparison,
                    "skipped": True
                })
                continue

            created_manual = await collection.find_one({"_id": result.inserted_id})
            if not created_manual:
                results.append({
                    "message": f"Error: Failed to retrieve created rating manual (ID: {ratingmanual_id}) after insertion.",
                    "error": True
                })
                continue

            normalized_created = self._normalize_manual_document(created_manual)
            created_manual_schema = RatingManualResponseSchema(**normalized_created)
            rating_manual_dict = created_manual_schema.dict()
            rating_manual_dict = self._serialize_datetime(rating_manual_dict)
            
            results.append({
                "message": "Rating manual created successfully with ratingtable changes" if existing_manual else "Rating manual created successfully",
                "rating_manual": rating_manual_dict,
                "ratingtable_comparison": ratingtable_comparison,
                "version": new_version,
                "created": True
            })
        
        return results

    async def get_last_ratingmanual_id(self) -> Optional[int]:
        """Get the last used rating manual ID"""
        collection = await self.get_collection()
        last_manual = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_manual["id"] if last_manual else None

ratingmanual_service = RatingManualService()

