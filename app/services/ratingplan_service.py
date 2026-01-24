from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value, get_client, rollback_sequence_value
from pymongo.errors import PyMongoError
from app.schemas.ratingplan import RatingPlanCreateSchema, RatingPlanUpdateSchema, RatingPlanResponseSchema
from app.services.company_service import company_service
from app.services.lob_service import lob_service
from app.services.state_service import state_service
from app.services.product_service import product_service
from app.services.algorithm_service import algorithm_service
import logging

logger = logging.getLogger(__name__)

class RatingPlanService:
    def __init__(self):
        self.collection_name = "ratingplans"
        self._transactions_supported: Optional[bool] = None

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_ratingplan_id(self) -> int:
        """Generate auto-incrementing rating plan ID"""
        return await get_next_sequence_value("ratingplan_id")
    
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

    async def _validate_associations(self, company: int, lob: int, state: int, product: int, algorithm: int):
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
        
        if not isinstance(algorithm, int) or algorithm <= 0:
            raise ValueError("Rating algorithm must be a positive integer ID")
        algorithm_obj = await algorithm_service.get_algorithm(algorithm)
        if not algorithm_obj:
            raise ValueError(f"Rating algorithm with id {algorithm} does not exist")

    def _serialize_datetime(self, obj: Any) -> Any:
        """Recursively convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(elem) for elem in obj]
        return obj

    def _compare_algorithm(self, existing_algorithm: int, new_algorithm: int) -> Dict[str, Any]:
        """Compare rating algorithm IDs and return comparison result"""
        has_changes = existing_algorithm != new_algorithm
        
        return {
            "has_changes": has_changes,
            "existing_algorithm": existing_algorithm,
            "new_algorithm": new_algorithm
        }

    async def create_ratingplan(self, ratingplan_data: RatingPlanCreateSchema) -> Dict[str, Any]:
        """Create a new rating plan with algorithm comparison using transaction if available"""
        collection = await self.get_collection()
        
        # Validate associations first
        await self._validate_associations(
            ratingplan_data.company,
            ratingplan_data.lob,
            ratingplan_data.state,
            ratingplan_data.product,
            ratingplan_data.algorithm
        )
        
        now = datetime.now(timezone.utc)
        
        # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
        if ratingplan_data.effective_date is not None:
            effective_date = ratingplan_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Auto-generate ID
        id_was_auto_generated = True
        ratingplan_id = await self._generate_ratingplan_id()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        # Initialize variables
        existing_manual = None
        algorithm_comparison = None
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
                                existing_manual, algorithm_comparison, new_version, result = await self._create_ratingplan_in_transaction(
                                    collection, ratingplan_data, effective_date, ratingplan_id, now, session
                                )
                        except PyMongoError as e:
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode")
                                self._transactions_supported = False
                                use_transactions = False
                                existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                                    collection, ratingplan_data, effective_date, ratingplan_id, now
                                )
                            else:
                                logger.error(f"Database error in create_ratingplan transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in create_ratingplan transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode")
                        self._transactions_supported = False
                        existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                            collection, ratingplan_data, effective_date, ratingplan_id, now
                        )
                    else:
                        raise
            else:
                existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                    collection, ratingplan_data, effective_date, ratingplan_id, now
                )
                
        except Exception as e:
            # Rollback counter sequence if ID was auto-generated and record creation failed
            if id_was_auto_generated:
                try:
                    await rollback_sequence_value("ratingplan_id")
                    logger.info(f"Rolled back ratingplan_id sequence due to error: {e}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback ratingplan_id sequence: {rollback_error}")
            
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
                    logger.info(f"Rolled back expiration of rating plan with id {expired_id}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback expiration: {rollback_error}")
            raise
        
        if result is None:
            return {
                "message": "No changes found in algorithm field. Record with same combination already exists.",
                "id": existing_manual["id"] if existing_manual else None,
                "existing_version": existing_manual.get("version", 1.0) if existing_manual else None,
                "algorithm_comparison": algorithm_comparison
            }

        # Fetch the created record
        created_manual = await collection.find_one({"_id": result.inserted_id})
        if not created_manual:
            raise ValueError("Failed to retrieve created rating plan after insertion.")

        normalized_created = self._normalize_plan_document(created_manual)
        created_manual_schema = RatingPlanResponseSchema(**normalized_created)
        rating_manual_dict = created_manual_schema.dict()
        rating_manual_dict = self._serialize_datetime(rating_manual_dict)
        
        had_existing = existing_manual is not None
        
        return {
            "message": "Rating plan created successfully with algorithm changes" if had_existing else "Rating plan created successfully",
            "rating_manual": rating_manual_dict,
            "algorithm_comparison": algorithm_comparison,
            "version": new_version
        }
    
    async def _create_ratingplan_in_transaction(self, collection, ratingplan_data, effective_date, ratingplan_id, now, session):
        """Helper method for transactional create operation"""
        # Check for existing record with same combination (excluding algorithm)
        existing_manual = await collection.find_one(
            {
                "plan_name": ratingplan_data.plan_name,
                "company": ratingplan_data.company,
                "lob": ratingplan_data.lob,
                "product": ratingplan_data.product,
                "state": ratingplan_data.state,
                "effective_date": effective_date,
                "active": True
            },
            session=session
        )
        
        if existing_manual:
            existing_algorithm = existing_manual.get("algorithm")
            new_algorithm = ratingplan_data.algorithm
            algorithm_comparison = self._compare_algorithm(existing_algorithm, new_algorithm)
            
            if not algorithm_comparison["has_changes"]:
                await session.abort_transaction()
                return existing_manual, algorithm_comparison, None, None
            
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
            logger.info(f"Expired existing rating plan with id {existing_manual['id']} due to algorithm changes")
            new_version = existing_manual.get("version", 1.0) + 1.0
        else:
            new_version = ratingplan_data.version if ratingplan_data.version is not None else 1.0
            algorithm_comparison = {
                "has_changes": True,
                "existing_algorithm": None,
                "new_algorithm": ratingplan_data.algorithm
            }
        
        id_check = await collection.find_one({"id": ratingplan_id}, session=session)
        if id_check:
            await session.abort_transaction()
            raise ValueError("Rating manual with same ID already exists")
        
        ratingplan_dict = ratingplan_data.dict(exclude={'version'})
        ratingplan_dict["effective_date"] = effective_date
        ratingplan_dict.update({
            "id": ratingplan_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingplan_dict, session=session)
        return existing_manual, algorithm_comparison, new_version, result
    
    async def _create_ratingplan_without_transaction(self, collection, ratingplan_data, effective_date, ratingplan_id, now):
        """Helper method for non-transactional create operation with error handling"""
        # Check for existing record with same combination (excluding algorithm)
        existing_manual = await collection.find_one({
            "plan_name": ratingplan_data.plan_name,
            "company": ratingplan_data.company,
            "lob": ratingplan_data.lob,
            "product": ratingplan_data.product,
            "state": ratingplan_data.state,
            "effective_date": effective_date,
            "active": True
        })
        
        expired_id = None
        
        if existing_manual:
            existing_algorithm = existing_manual.get("algorithm")
            new_algorithm = ratingplan_data.algorithm
            algorithm_comparison = self._compare_algorithm(existing_algorithm, new_algorithm)
            
            if not algorithm_comparison["has_changes"]:
                return existing_manual, algorithm_comparison, None, None, None
            
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
            logger.info(f"Expired existing rating plan with id {expired_id} due to algorithm changes")
            new_version = existing_manual.get("version", 1.0) + 1.0
        else:
            new_version = ratingplan_data.version if ratingplan_data.version is not None else 1.0
            algorithm_comparison = {
                "has_changes": True,
                "existing_algorithm": None,
                "new_algorithm": ratingplan_data.algorithm
            }
        
        id_check = await collection.find_one({"id": ratingplan_id})
        if id_check:
            raise ValueError("Rating manual with same ID already exists")
        
        ratingplan_dict = ratingplan_data.dict(exclude={'version'})
        ratingplan_dict["effective_date"] = effective_date
        ratingplan_dict.update({
            "id": ratingplan_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(ratingplan_dict)
        return existing_manual, algorithm_comparison, new_version, result, expired_id

    def _normalize_plan_document(self, plan: dict) -> dict:
        """Normalize MongoDB document to match schema expectations"""
        # Remove MongoDB _id field if present
        plan = {k: v for k, v in plan.items() if k != "_id"}
        
        # Handle algorithm field - convert from old format if needed
        if "algorithm" not in plan:
            # If algorithm is missing, try to find it under old field names
            if "ratingalgorithm" in plan:
                # Old format might have been ratingalgorithm, convert to algorithm
                plan["algorithm"] = plan["ratingalgorithm"]
                logger.warning(f"Rating plan {plan.get('id')} has old 'ratingalgorithm' field, converting to 'algorithm'")
            else:
                # Default to 0 if field is completely missing (will cause validation error, but better than crash)
                logger.warning(f"Rating plan {plan.get('id')} is missing algorithm field, defaulting to 0")
                plan["algorithm"] = 0
        
        return plan

    async def get_ratingplan(self, ratingplan_id: int) -> Optional[RatingPlanResponseSchema]:
        """Get a rating plan by ID"""
        collection = await self.get_collection()
        manual = await collection.find_one({"id": ratingplan_id})
        if not manual:
            return None
        normalized_plan = self._normalize_plan_document(manual)
        return RatingPlanResponseSchema(**normalized_plan)

    async def get_ratingplans(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[RatingPlanResponseSchema]:
        """Get all rating plans with pagination, filtering and sorting"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "plan_name" in filter_by:
                query["plan_name"] = {"$regex": filter_by["plan_name"], "$options": "i"}
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "algorithm_id" in filter_by:
                # Filter by algorithm_id - MongoDB will check if the value is in the algorithm array
                query["algorithm"] = filter_by["algorithm_id"]
            if "effective_date" in filter_by:
                query["effective_date"] = filter_by["effective_date"]
        
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        manuals = await cursor.to_list(length=limit)
        normalized_plans = [self._normalize_plan_document(plan) for plan in manuals]
        return [RatingPlanResponseSchema(**plan) for plan in normalized_plans]

    async def update_ratingplan(self, ratingplan_id: int, update_data: RatingPlanUpdateSchema) -> Optional[RatingPlanResponseSchema]:
        """Update a rating plan using transaction if available"""
        collection = await self.get_collection()
        
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                existing_manual = await collection.find_one({"id": ratingplan_id}, session=session)
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
                                    normalized_existing = self._normalize_plan_document(existing_manual)
                                    return RatingPlanResponseSchema(**normalized_existing)
                                    
                                update_dict["updated_at"] = datetime.now(timezone.utc)
                                
                                result = await collection.update_one(
                                    {"id": ratingplan_id},
                                    {"$set": update_dict},
                                    session=session
                                )
                                
                                if result.modified_count == 0:
                                    await session.abort_transaction()
                                    normalized_existing = self._normalize_plan_document(existing_manual)
                                    return RatingPlanResponseSchema(**normalized_existing)
                        except PyMongoError as e:
                            logger.error(f"Database error in update_ratingplan transaction: {e}")
                            raise
                        except Exception as e:
                            logger.error(f"Error in update_ratingplan transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for update")
                        self._transactions_supported = False
                        existing_manual = await collection.find_one({"id": ratingplan_id})
                        if not existing_manual:
                            return None
                        
                        effective_date = update_data.effective_date if update_data.effective_date is not None else existing_manual.get("effective_date")
                        expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_manual.get("expiration_date")
                        
                        if effective_date and expiration_date:
                            if expiration_date < effective_date:
                                raise ValueError("expiration_date cannot be less than effective_date")
                        
                        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                        if not update_dict:
                            normalized_existing = self._normalize_plan_document(existing_manual)
                            return RatingPlanResponseSchema(**normalized_existing)
                            
                        update_dict["updated_at"] = datetime.now(timezone.utc)
                        
                        result = await collection.update_one(
                            {"id": ratingplan_id},
                            {"$set": update_dict}
                        )
                        
                        if result.modified_count == 0:
                            normalized_existing = self._normalize_plan_document(existing_manual)
                            return RatingPlanResponseSchema(**normalized_existing)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error updating rating plan: {e}")
                    raise
            else:
                existing_manual = await collection.find_one({"id": ratingplan_id})
                if not existing_manual:
                    return None
                
                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_manual.get("effective_date")
                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_manual.get("expiration_date")
                
                if effective_date and expiration_date:
                    if expiration_date < effective_date:
                        raise ValueError("expiration_date cannot be less than effective_date")
                
                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                if not update_dict:
                    normalized_existing = self._normalize_plan_document(existing_manual)
                    return RatingPlanResponseSchema(**normalized_existing)
                    
                update_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.update_one(
                    {"id": ratingplan_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    normalized_existing = self._normalize_plan_document(existing_manual)
                    return RatingPlanResponseSchema(**normalized_existing)
                    
        except Exception as e:
            logger.error(f"Error updating rating plan: {e}")
            raise
        
        updated_manual = await collection.find_one({"id": ratingplan_id})
        if updated_manual:
            normalized_updated = self._normalize_plan_document(updated_manual)
            return RatingPlanResponseSchema(**normalized_updated)
        return None

    async def delete_ratingplan(self, ratingplan_id: int) -> bool:
        """Delete a rating plan using transaction if available"""
        collection = await self.get_collection()
        
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                result = await collection.delete_one({"id": ratingplan_id}, session=session)
                                return result.deleted_count > 0
                        except PyMongoError as e:
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                                self._transactions_supported = False
                                result = await collection.delete_one({"id": ratingplan_id})
                                return result.deleted_count > 0
                            else:
                                logger.error(f"Database error in delete_ratingplan transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in delete_ratingplan transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                        self._transactions_supported = False
                        result = await collection.delete_one({"id": ratingplan_id})
                        return result.deleted_count > 0
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error deleting rating plan: {e}")
                    raise
            else:
                result = await collection.delete_one({"id": ratingplan_id})
                return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting rating plan: {e}")
            raise

    async def count_ratingplans(self, filter_by: Optional[Dict] = None) -> int:
        """Count rating plans with optional filters"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "plan_name" in filter_by:
                query["plan_name"] = {"$regex": filter_by["plan_name"], "$options": "i"}
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
            if "algorithm_id" in filter_by:
                # Filter by algorithm_id - MongoDB will check if the value is in the algorithm array
                query["algorithm"] = filter_by["algorithm_id"]
            if "effective_date" in filter_by:
                query["effective_date"] = filter_by["effective_date"]
        
        return await collection.count_documents(query)

    async def bulk_create_ratingplans(self, ratingplans_data: List[RatingPlanCreateSchema]) -> List[Dict[str, Any]]:
        """Bulk create rating plans with algorithm comparison using transactions if available"""
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        
        results = []
        use_transactions = await self._check_transactions_supported()

        for ratingplan_data in ratingplans_data:
            existing_manual = None
            algorithm_comparison = None
            new_version = None
            result = None
            expired_id = None
            
            try:
                await self._validate_associations(
                    ratingplan_data.company,
                    ratingplan_data.lob,
                    ratingplan_data.state,
                    ratingplan_data.product,
                    ratingplan_data.algorithm
                )
                
                if ratingplan_data.effective_date is not None:
                    effective_date = ratingplan_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Auto-generate ID
                ratingplan_id = await self._generate_ratingplan_id()
                id_was_auto_generated = True
                
                if use_transactions:
                    client = await get_client()
                    try:
                        async with await client.start_session() as session:
                            try:
                                async with session.start_transaction():
                                    existing_manual, algorithm_comparison, new_version, result = await self._create_ratingplan_in_transaction(
                                        collection, ratingplan_data, effective_date, ratingplan_id, now, session
                                    )
                            except PyMongoError as e:
                                if e.code == 20:  # IllegalOperation
                                    logger.warning(f"Transactions not supported for record (ID: {ratingplan_id}), falling back to non-transactional mode")
                                    self._transactions_supported = False
                                    use_transactions = False
                                    existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                                        collection, ratingplan_data, effective_date, ratingplan_id, now
                                    )
                                else:
                                    logger.error(f"Database error in bulk_create_ratingplans transaction for record (ID: {ratingplan_id}): {e}")
                                    raise
                            except Exception as e:
                                logger.error(f"Error in bulk_create_ratingplans transaction for record (ID: {ratingplan_id}): {str(e)}")
                                raise
                    except PyMongoError as e:
                        if e.code == 20:  # IllegalOperation
                            logger.warning(f"Transactions not supported for record (ID: {ratingplan_id}), falling back to non-transactional mode")
                            self._transactions_supported = False
                            use_transactions = False
                            existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                                collection, ratingplan_data, effective_date, ratingplan_id, now
                            )
                        else:
                            raise
                    except Exception as e:
                        logger.error(f"Error processing rating plan (ID: {ratingplan_id}): {e}")
                        raise
                else:
                    existing_manual, algorithm_comparison, new_version, result, expired_id = await self._create_ratingplan_without_transaction(
                        collection, ratingplan_data, effective_date, ratingplan_id, now
                    )
                    
            except Exception as e:
                # Rollback counter sequence if ID was auto-generated and record creation failed
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("ratingplan_id")
                        logger.info(f"Rolled back ratingplan_id sequence for record (ID: {ratingplan_id}) due to error: {e}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback ratingplan_id sequence: {rollback_error}")
                
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
                        logger.info(f"Rolled back expiration of rating plan with id {expired_id}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback expiration: {rollback_error}")
                results.append({
                    "message": f"Error processing record (ID: {ratingplan_id}): {str(e)}",
                    "error": True
                })
                continue
            
            if result is None:
                # Rollback counter sequence if ID was auto-generated but no record was created
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("ratingplan_id")
                        logger.info(f"Rolled back ratingplan_id sequence - no changes found for record (ID: {ratingplan_id})")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback ratingplan_id sequence: {rollback_error}")
                
                results.append({
                    "message": "No changes found in algorithm field. Record with same combination already exists.",
                    "id": existing_manual["id"],
                    "existing_version": existing_manual.get("version", 1.0),
                    "algorithm_comparison": algorithm_comparison,
                    "skipped": True
                })
                continue

            created_manual = await collection.find_one({"_id": result.inserted_id})
            if not created_manual:
                results.append({
                    "message": f"Error: Failed to retrieve created rating plan (ID: {ratingplan_id}) after insertion.",
                    "error": True
                })
                continue

            normalized_created = self._normalize_plan_document(created_manual)
            created_manual_schema = RatingPlanResponseSchema(**normalized_created)
            rating_manual_dict = created_manual_schema.dict()
            rating_manual_dict = self._serialize_datetime(rating_manual_dict)
            
            results.append({
                "message": "Rating manual created successfully with algorithm changes" if existing_manual else "Rating manual created successfully",
                "rating_manual": rating_manual_dict,
                "algorithm_comparison": algorithm_comparison,
                "version": new_version,
                "created": True
            })
        
        return results

    async def get_last_ratingplan_id(self) -> Optional[int]:
        """Get the last used rating plan ID"""
        collection = await self.get_collection()
        last_manual = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_manual["id"] if last_manual else None

ratingplan_service = RatingPlanService()

