from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.database import get_database, get_next_sequence_value, get_client, rollback_sequence_value
from pymongo.errors import PyMongoError
from app.schemas.algorithm import AlgorithmCreateSchema, AlgorithmUpdateSchema, AlgorithmResponseSchema
from app.services.company_service import company_service
from app.services.lob_service import lob_service
from app.services.state_service import state_service
from app.services.product_service import product_service
from app.services.ratingtable_service import ratingtable_service
import logging
import json

logger = logging.getLogger(__name__)

class AlgorithmService:
    def __init__(self):
        self.collection_name = "algorithms"
        self._transactions_supported = None

    async def get_collection(self) -> AsyncIOMotorCollection:
        db = await get_database()
        return db[self.collection_name]

    async def _generate_algorithm_id(self) -> int:
        """Generate auto-incrementing algorithm ID"""
        return await get_next_sequence_value("algorithm_id")

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

    async def _validate_associations(self, company: int, lob: int, state: int, product: int, required_tables: Optional[List[int]] = None):
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
        
        # Validate required_tables (optional)
        if required_tables:
            for table_id in required_tables:
                if not isinstance(table_id, int) or table_id <= 0:
                    raise ValueError(f"Required table ID {table_id} must be a positive integer")
                table_obj = await ratingtable_service.get_ratingtable(table_id)
                if not table_obj:
                    raise ValueError(f"Rating table with id {table_id} does not exist")

    def _serialize_datetime(self, obj: Any) -> Any:
        """Recursively convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_datetime(elem) for elem in obj]
        return obj

    def _compare_algorithm_content(self, existing_algorithm: Dict[str, Any], new_algorithm: AlgorithmCreateSchema) -> Dict[str, Any]:
        """Compare algorithm content (formula and required_tables) and return changes"""
        existing_formula = existing_algorithm.get("formula", {})
        existing_required_tables = existing_algorithm.get("required_tables", [])
        
        new_formula = new_algorithm.formula if new_algorithm.formula else {}
        new_required_tables = new_algorithm.required_tables if new_algorithm.required_tables else []
        
        # Normalize for comparison (convert to JSON strings for deep comparison)
        existing_formula_str = json.dumps(self._serialize_datetime(existing_formula), sort_keys=True)
        new_formula_str = json.dumps(self._serialize_datetime(new_formula), sort_keys=True)
        
        # Sort required_tables lists for comparison
        existing_required_tables_sorted = sorted(existing_required_tables)
        new_required_tables_sorted = sorted(new_required_tables)
        
        # Check for changes
        formula_changed = existing_formula_str != new_formula_str
        required_tables_changed = existing_required_tables_sorted != new_required_tables_sorted
        
        has_changes = formula_changed or required_tables_changed
        
        return {
            "has_changes": has_changes,
            "formula_changed": formula_changed,
            "required_tables_changed": required_tables_changed,
            "existing_formula": existing_formula,
            "new_formula": new_formula,
            "existing_required_tables": existing_required_tables,
            "new_required_tables": new_required_tables
        }

    async def create_algorithm(self, algorithm_data: AlgorithmCreateSchema) -> Dict[str, Any]:
        """Create a new algorithm with content comparison using transaction if available"""
        collection = await self.get_collection()
        
        # Validate associations first
        await self._validate_associations(
            algorithm_data.company,
            algorithm_data.lob,
            algorithm_data.state,
            algorithm_data.product,
            algorithm_data.required_tables
        )
        
        now = datetime.now(timezone.utc)
        
        # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
        if algorithm_data.effective_date is not None:
            effective_date = algorithm_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Auto-generate ID if not provided
        id_was_auto_generated = False
        if algorithm_data.id is None or algorithm_data.id == 0:
            algorithm_id = await self._generate_algorithm_id()
            id_was_auto_generated = True
        else:
            algorithm_id = algorithm_data.id
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        # Initialize variables
        existing_algorithm = None
        content_comparison = None
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
                                existing_algorithm, content_comparison, new_version, result = await self._create_algorithm_in_transaction(
                                    collection, algorithm_data, effective_date, algorithm_id, now, session
                                )
                        except PyMongoError as e:
                            # If transaction not supported, fall back to non-transactional
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode")
                                self._transactions_supported = False
                                use_transactions = False
                                # Retry without transaction
                                existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                                    collection, algorithm_data, effective_date, algorithm_id, now
                                )
                            else:
                                logger.error(f"Database error in create_algorithm transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in create_algorithm transaction: {e}")
                            raise
                except PyMongoError as e:
                    # If session creation fails with transaction error, fall back
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode")
                        self._transactions_supported = False
                        existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                            collection, algorithm_data, effective_date, algorithm_id, now
                        )
                    else:
                        raise
            else:
                # Non-transactional path with manual error handling
                existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                    collection, algorithm_data, effective_date, algorithm_id, now
                )
                
        except Exception as e:
            # Rollback counter sequence if ID was auto-generated and record creation failed
            if id_was_auto_generated:
                try:
                    await rollback_sequence_value("algorithm_id")
                    logger.info(f"Rolled back algorithm_id sequence due to error: {e}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback algorithm_id sequence: {rollback_error}")
            
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
                    logger.info(f"Rolled back expiration of algorithm with id {expired_id}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback expiration: {rollback_error}")
            raise
        
        # If result is None, it means no changes were found and transaction was aborted
        if result is None:
            # Rollback counter sequence if ID was auto-generated but no record was created
            if id_was_auto_generated:
                try:
                    await rollback_sequence_value("algorithm_id")
                    logger.info(f"Rolled back algorithm_id sequence - no changes found, record not created")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback algorithm_id sequence: {rollback_error}")
            
            return {
                "message": "No changes found in algorithm content. Record with same combination already exists.",
                "id": existing_algorithm["id"],
                "existing_version": existing_algorithm.get("version", 1.0),
                "content_comparison": content_comparison
            }

        # Fetch the created record
        created_algorithm = await collection.find_one({"_id": result.inserted_id})
        if not created_algorithm:
            raise ValueError("Failed to retrieve created algorithm after insertion.")

        normalized_created = self._normalize_algorithm_document(created_algorithm)
        created_algorithm_schema = AlgorithmResponseSchema(**normalized_created)
        
        # Convert to dict and serialize datetime objects for JSON compatibility
        algorithm_dict = created_algorithm_schema.dict()
        algorithm_dict = self._serialize_datetime(algorithm_dict)
        
        # Determine if this was an update of existing record (had changes)
        had_existing = existing_algorithm is not None
        
        return {
            "message": "Algorithm created successfully with content changes" if had_existing else "Algorithm created successfully",
            "algorithm": algorithm_dict,
            "content_comparison": content_comparison,
            "version": new_version
        }
    
    async def _create_algorithm_in_transaction(self, collection, algorithm_data, effective_date, algorithm_id, now, session):
        """Helper method for transactional create operation"""
        # Check for existing record with same combination
        existing_algorithm = await collection.find_one(
            {
                "algorithm_name": algorithm_data.algorithm_name,
                "company": algorithm_data.company,
                "lob": algorithm_data.lob,
                "product": algorithm_data.product,
                "state": algorithm_data.state,
                "effective_date": effective_date,
                "active": True
            },
            session=session
        )
        
        # If existing record found, compare content
        if existing_algorithm:
            content_comparison = self._compare_algorithm_content(existing_algorithm, algorithm_data)
            
            if not content_comparison["has_changes"]:
                await session.abort_transaction()
                return existing_algorithm, content_comparison, None, None
            
            # Expire existing record
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_algorithm["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                },
                session=session
            )
            logger.info(f"Expired existing algorithm with id {existing_algorithm['id']} due to content changes")
            new_version = existing_algorithm.get("version", 1.0) + 1.0
        else:
            new_version = algorithm_data.version if algorithm_data.version is not None else 1.0
            content_comparison = {
                "has_changes": True,
                "formula_changed": True,
                "required_tables_changed": True,
                "existing_formula": {},
                "new_formula": algorithm_data.formula,
                "existing_required_tables": [],
                "new_required_tables": algorithm_data.required_tables
            }
        
        # Check if algorithm with same ID exists
        id_check = await collection.find_one({"id": algorithm_id}, session=session)
        if id_check:
            await session.abort_transaction()
            raise ValueError("Algorithm with same ID already exists")
        
        # Create new record
        algorithm_dict = algorithm_data.dict(exclude={'id', 'version', 'effective_date'})
        # Set default values for optional fields if None
        if algorithm_dict.get("calculation_steps") is None:
            algorithm_dict["calculation_steps"] = []
        if algorithm_dict.get("variables") is None:
            algorithm_dict["variables"] = {}
        algorithm_dict["effective_date"] = effective_date
        algorithm_dict.update({
            "id": algorithm_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(algorithm_dict, session=session)
        return existing_algorithm, content_comparison, new_version, result
    
    async def _create_algorithm_without_transaction(self, collection, algorithm_data, effective_date, algorithm_id, now):
        """Helper method for non-transactional create operation with error handling"""
        # Check for existing record
        existing_algorithm = await collection.find_one({
            "algorithm_name": algorithm_data.algorithm_name,
            "company": algorithm_data.company,
            "lob": algorithm_data.lob,
            "product": algorithm_data.product,
            "state": algorithm_data.state,
            "effective_date": effective_date,
            "active": True
        })
        
        expired_id = None
        
        if existing_algorithm:
            content_comparison = self._compare_algorithm_content(existing_algorithm, algorithm_data)
            
            if not content_comparison["has_changes"]:
                return existing_algorithm, content_comparison, None, None, None
            
            # Expire existing record
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            await collection.update_one(
                {"id": existing_algorithm["id"]},
                {
                    "$set": {
                        "expiration_date": today_minus_one,
                        "active": False,
                        "updated_at": now
                    }
                }
            )
            expired_id = existing_algorithm["id"]
            logger.info(f"Expired existing algorithm with id {expired_id} due to content changes")
            new_version = existing_algorithm.get("version", 1.0) + 1.0
        else:
            new_version = algorithm_data.version if algorithm_data.version is not None else 1.0
            content_comparison = {
                "has_changes": True,
                "formula_changed": True,
                "required_tables_changed": True,
                "existing_formula": {},
                "new_formula": algorithm_data.formula,
                "existing_required_tables": [],
                "new_required_tables": algorithm_data.required_tables
            }
        
        # Check if algorithm with same ID exists
        id_check = await collection.find_one({"id": algorithm_id})
        if id_check:
            raise ValueError("Algorithm with same ID already exists")
        
        # Create new record
        algorithm_dict = algorithm_data.dict(exclude={'id', 'version', 'effective_date'})
        # Set default values for optional fields if None
        if algorithm_dict.get("calculation_steps") is None:
            algorithm_dict["calculation_steps"] = []
        if algorithm_dict.get("variables") is None:
            algorithm_dict["variables"] = {}
        algorithm_dict["effective_date"] = effective_date
        algorithm_dict.update({
            "id": algorithm_id,
            "version": new_version,
            "created_at": now,
            "updated_at": now
        })
        
        result = await collection.insert_one(algorithm_dict)
        return existing_algorithm, content_comparison, new_version, result, expired_id

    def _normalize_algorithm_document(self, algorithm: dict) -> dict:
        """Normalize MongoDB document to match schema expectations"""
        # Remove MongoDB _id field if present
        algorithm = {k: v for k, v in algorithm.items() if k != "_id"}
        
        # Handle required_tables field - ensure it's a list
        if "required_tables" not in algorithm:
            logger.warning(f"Algorithm {algorithm.get('id')} is missing required_tables field, defaulting to empty list")
            algorithm["required_tables"] = []
        elif not isinstance(algorithm["required_tables"], list):
            # If required_tables exists but is not a list, convert it
            if isinstance(algorithm["required_tables"], int):
                algorithm["required_tables"] = [algorithm["required_tables"]]
            else:
                logger.warning(f"Algorithm {algorithm.get('id')} has invalid required_tables type, converting to list")
                algorithm["required_tables"] = []
        
        # Handle formula field - ensure it's a dict
        if "formula" not in algorithm:
            logger.warning(f"Algorithm {algorithm.get('id')} is missing formula field, defaulting to empty dict")
            algorithm["formula"] = {}
        elif not isinstance(algorithm["formula"], dict):
            logger.warning(f"Algorithm {algorithm.get('id')} has invalid formula type, converting to dict")
            algorithm["formula"] = {}
        
        # Handle calculation_steps field - ensure it's a list (optional field)
        if "calculation_steps" not in algorithm:
            algorithm["calculation_steps"] = []
        elif not isinstance(algorithm["calculation_steps"], list):
            logger.warning(f"Algorithm {algorithm.get('id')} has invalid calculation_steps type, converting to list")
            algorithm["calculation_steps"] = []
        
        # Handle variables field - ensure it's a dict (optional field)
        if "variables" not in algorithm:
            algorithm["variables"] = {}
        elif not isinstance(algorithm["variables"], dict):
            logger.warning(f"Algorithm {algorithm.get('id')} has invalid variables type, converting to dict")
            algorithm["variables"] = {}
        
        return algorithm

    async def get_algorithm(self, algorithm_id: int) -> Optional[AlgorithmResponseSchema]:
        """Get an algorithm by ID"""
        collection = await self.get_collection()
        algorithm = await collection.find_one({"id": algorithm_id})
        if not algorithm:
            return None
        normalized_algorithm = self._normalize_algorithm_document(algorithm)
        return AlgorithmResponseSchema(**normalized_algorithm)

    async def get_algorithms(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ) -> List[AlgorithmResponseSchema]:
        """Get all algorithms with pagination, filtering and sorting"""
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "algorithm_name" in filter_by:
                query["algorithm_name"] = {"$regex": filter_by["algorithm_name"], "$options": "i"}
            if "algorithm_type" in filter_by:
                query["algorithm_type"] = filter_by["algorithm_type"]
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        cursor = collection.find(query).skip(skip).limit(limit).sort(sort)
        algorithms = await cursor.to_list(length=limit)
        normalized_algorithms = [self._normalize_algorithm_document(algorithm) for algorithm in algorithms]
        return [AlgorithmResponseSchema(**algorithm) for algorithm in normalized_algorithms]

    async def update_algorithm(self, algorithm_id: int, update_data: AlgorithmUpdateSchema) -> Optional[AlgorithmResponseSchema]:
        """Update an algorithm using transaction if available"""
        collection = await self.get_collection()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                existing_algorithm = await collection.find_one({"id": algorithm_id}, session=session)
                                if not existing_algorithm:
                                    await session.abort_transaction()
                                    return None
                                
                                # Validate expiration_date >= effective_date
                                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_algorithm.get("effective_date")
                                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_algorithm.get("expiration_date")
                                
                                if effective_date and expiration_date:
                                    if expiration_date < effective_date:
                                        await session.abort_transaction()
                                        raise ValueError("expiration_date cannot be less than effective_date")
                                
                                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                                if not update_dict:
                                    await session.abort_transaction()
                                    normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                                    return AlgorithmResponseSchema(**normalized_existing)
                                    
                                update_dict["updated_at"] = datetime.now(timezone.utc)
                                
                                result = await collection.update_one(
                                    {"id": algorithm_id},
                                    {"$set": update_dict},
                                    session=session
                                )
                                
                                if result.modified_count == 0:
                                    await session.abort_transaction()
                                    normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                                    return AlgorithmResponseSchema(**normalized_existing)
                        except PyMongoError as e:
                            logger.error(f"Database error in update_algorithm transaction: {e}")
                            raise
                        except Exception as e:
                            logger.error(f"Error in update_algorithm transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for update")
                        self._transactions_supported = False
                        # Fallback to non-transactional
                        existing_algorithm = await collection.find_one({"id": algorithm_id})
                        if not existing_algorithm:
                            return None
                        
                        effective_date = update_data.effective_date if update_data.effective_date is not None else existing_algorithm.get("effective_date")
                        expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_algorithm.get("expiration_date")
                        
                        if effective_date and expiration_date:
                            if expiration_date < effective_date:
                                raise ValueError("expiration_date cannot be less than effective_date")
                        
                        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                        if not update_dict:
                            normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                            return AlgorithmResponseSchema(**normalized_existing)
                            
                        update_dict["updated_at"] = datetime.now(timezone.utc)
                        
                        result = await collection.update_one(
                            {"id": algorithm_id},
                            {"$set": update_dict}
                        )
                        
                        if result.modified_count == 0:
                            normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                            return AlgorithmResponseSchema(**normalized_existing)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error updating algorithm: {e}")
                    raise
            else:
                # Non-transactional path
                existing_algorithm = await collection.find_one({"id": algorithm_id})
                if not existing_algorithm:
                    return None
                
                # Validate expiration_date >= effective_date
                effective_date = update_data.effective_date if update_data.effective_date is not None else existing_algorithm.get("effective_date")
                expiration_date = update_data.expiration_date if update_data.expiration_date is not None else existing_algorithm.get("expiration_date")
                
                if effective_date and expiration_date:
                    if expiration_date < effective_date:
                        raise ValueError("expiration_date cannot be less than effective_date")
                
                update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
                if not update_dict:
                    normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                    return AlgorithmResponseSchema(**normalized_existing)
                    
                update_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.update_one(
                    {"id": algorithm_id},
                    {"$set": update_dict}
                )
                
                if result.modified_count == 0:
                    normalized_existing = self._normalize_algorithm_document(existing_algorithm)
                    return AlgorithmResponseSchema(**normalized_existing)
                    
        except Exception as e:
            logger.error(f"Error updating algorithm: {e}")
            raise
        
        # Fetch the updated record
        updated_algorithm = await collection.find_one({"id": algorithm_id})
        if updated_algorithm:
            normalized_updated = self._normalize_algorithm_document(updated_algorithm)
            return AlgorithmResponseSchema(**normalized_updated)
        return None

    async def delete_algorithm(self, algorithm_id: int) -> bool:
        """Delete an algorithm using transaction if available"""
        collection = await self.get_collection()
        
        # Check if transactions are supported
        use_transactions = await self._check_transactions_supported()
        
        try:
            if use_transactions:
                client = await get_client()
                try:
                    async with await client.start_session() as session:
                        try:
                            async with session.start_transaction():
                                result = await collection.delete_one({"id": algorithm_id}, session=session)
                                return result.deleted_count > 0
                        except PyMongoError as e:
                            if e.code == 20:  # IllegalOperation
                                logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                                self._transactions_supported = False
                                # Fallback to non-transactional
                                result = await collection.delete_one({"id": algorithm_id})
                                return result.deleted_count > 0
                            else:
                                logger.error(f"Database error in delete_algorithm transaction: {e}")
                                raise
                        except Exception as e:
                            logger.error(f"Error in delete_algorithm transaction: {e}")
                            raise
                except PyMongoError as e:
                    if e.code == 20:  # IllegalOperation
                        logger.warning("Transactions not supported, falling back to non-transactional mode for delete")
                        self._transactions_supported = False
                        result = await collection.delete_one({"id": algorithm_id})
                        return result.deleted_count > 0
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error deleting algorithm: {e}")
                    raise
            else:
                # Non-transactional path
                result = await collection.delete_one({"id": algorithm_id})
                return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting algorithm: {e}")
            raise

    async def count_algorithms(self, filter_by: Optional[Dict] = None) -> int:
        """Count algorithms with optional filters"""
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "active" in filter_by:
                query["active"] = filter_by["active"]
            if "algorithm_name" in filter_by:
                query["algorithm_name"] = {"$regex": filter_by["algorithm_name"], "$options": "i"}
            if "algorithm_type" in filter_by:
                query["algorithm_type"] = filter_by["algorithm_type"]
            if "company_id" in filter_by:
                query["company"] = filter_by["company_id"]
            if "lob_id" in filter_by:
                query["lob"] = filter_by["lob_id"]
            if "state_id" in filter_by:
                query["state"] = filter_by["state_id"]
            if "product_id" in filter_by:
                query["product"] = filter_by["product_id"]
        
        return await collection.count_documents(query)

    async def bulk_create_algorithms(self, algorithms_data: List[AlgorithmCreateSchema]) -> List[Dict[str, Any]]:
        """Bulk create algorithms with content comparison using transactions if available"""
        collection = await self.get_collection()
        now = datetime.now(timezone.utc)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_minus_one = today - timedelta(days=1)
        
        results = []
        
        # Check if transactions are supported once for the bulk operation
        use_transactions = await self._check_transactions_supported()

        for algorithm_data in algorithms_data:
            # Initialize variables for each record
            existing_algorithm = None
            content_comparison = None
            new_version = None
            result = None
            expired_id = None
            
            try:
                # Validate associations first (outside transaction)
                await self._validate_associations(
                    algorithm_data.company,
                    algorithm_data.lob,
                    algorithm_data.state,
                    algorithm_data.product,
                    algorithm_data.required_tables
                )
                
                # Set effective_date to start of current day (midnight) if not provided, or normalize provided date to start of day
                if algorithm_data.effective_date is not None:
                    effective_date = algorithm_data.effective_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    effective_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Auto-generate ID if not provided (outside transaction for sequence)
                id_was_auto_generated = False
                if algorithm_data.id is None or algorithm_data.id == 0:
                    algorithm_id = await self._generate_algorithm_id()
                    id_was_auto_generated = True
                else:
                    algorithm_id = algorithm_data.id
                
                if use_transactions:
                    # Use transaction for each record's database write operations
                    client = await get_client()
                    try:
                        async with await client.start_session() as session:
                            try:
                                async with session.start_transaction():
                                    existing_algorithm, content_comparison, new_version, result = await self._create_algorithm_in_transaction(
                                        collection, algorithm_data, effective_date, algorithm_id, now, session
                                    )
                            except PyMongoError as e:
                                if e.code == 20:  # IllegalOperation
                                    logger.warning(f"Transactions not supported for record (ID: {algorithm_id}), falling back to non-transactional mode")
                                    self._transactions_supported = False
                                    use_transactions = False
                                    # Fallback to non-transactional
                                    existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                                        collection, algorithm_data, effective_date, algorithm_id, now
                                    )
                                else:
                                    logger.error(f"Database error in bulk_create_algorithms transaction for record (ID: {algorithm_id}): {e}")
                                    raise
                            except Exception as e:
                                logger.error(f"Error in bulk_create_algorithms transaction for record (ID: {algorithm_id}): {str(e)}")
                                raise
                    except PyMongoError as e:
                        if e.code == 20:  # IllegalOperation
                            logger.warning(f"Transactions not supported for record (ID: {algorithm_id}), falling back to non-transactional mode")
                            self._transactions_supported = False
                            use_transactions = False
                            existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                                collection, algorithm_data, effective_date, algorithm_id, now
                            )
                        else:
                            raise
                    except Exception as e:
                        logger.error(f"Error processing algorithm (ID: {algorithm_id}): {e}")
                        raise
                else:
                    # Non-transactional path
                    existing_algorithm, content_comparison, new_version, result, expired_id = await self._create_algorithm_without_transaction(
                        collection, algorithm_data, effective_date, algorithm_id, now
                    )
                    
            except Exception as e:
                # Rollback counter sequence if ID was auto-generated and record creation failed
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("algorithm_id")
                        logger.info(f"Rolled back algorithm_id sequence for record (ID: {algorithm_id}) due to error: {e}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback algorithm_id sequence: {rollback_error}")
                
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
                        logger.info(f"Rolled back expiration of algorithm with id {expired_id}")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback expiration: {rollback_error}")
                results.append({
                    "message": f"Error processing record (ID: {algorithm_id}): {str(e)}",
                    "error": True
                })
                continue
            
            # If result is None, it means no changes were found and transaction was aborted
            if result is None:
                # Rollback counter sequence if ID was auto-generated but no record was created
                if id_was_auto_generated:
                    try:
                        await rollback_sequence_value("algorithm_id")
                        logger.info(f"Rolled back algorithm_id sequence - no changes found for record (ID: {algorithm_id})")
                    except Exception as rollback_error:
                        logger.error(f"Failed to rollback algorithm_id sequence: {rollback_error}")
                
                results.append({
                    "message": "No changes found in algorithm content. Record with same combination already exists.",
                    "id": existing_algorithm["id"],
                    "existing_version": existing_algorithm.get("version", 1.0),
                    "content_comparison": content_comparison,
                    "skipped": True
                })
                continue

            # Fetch the created record
            created_algorithm = await collection.find_one({"_id": result.inserted_id})
            if not created_algorithm:
                results.append({
                    "message": f"Error: Failed to retrieve created algorithm (ID: {algorithm_id}) after insertion.",
                    "error": True
                })
                continue

            normalized_created = self._normalize_algorithm_document(created_algorithm)
            created_algorithm_schema = AlgorithmResponseSchema(**normalized_created)
            # Convert to dict and serialize datetime objects for JSON compatibility
            algorithm_dict = created_algorithm_schema.dict()
            algorithm_dict = self._serialize_datetime(algorithm_dict)
            
            results.append({
                "message": "Algorithm created successfully with content changes" if existing_algorithm else "Algorithm created successfully",
                "algorithm": algorithm_dict,
                "content_comparison": content_comparison,
                "version": new_version,
                "created": True
            })
        
        return results

    async def get_last_algorithm_id(self) -> Optional[int]:
        """Get the last used algorithm ID"""
        collection = await self.get_collection()
        last_algorithm = await collection.find_one(
            {},
            sort=[("id", -1)]
        )
        return last_algorithm["id"] if last_algorithm else None

algorithm_service = AlgorithmService()
