from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging
import asyncio
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    database = None
    connected: bool = False

mongodb = MongoDB()

async def verify_connection(max_retries: int = 5, retry_delay: float = 2.0) -> bool:
    """Verify MongoDB connection with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            # Ping the database to verify connection
            await mongodb.client.admin.command('ping')
            mongodb.connected = True
            logger.info(f"Successfully connected to MongoDB at {settings.MONGODB_URL}")
            return True
        except (ServerSelectionTimeoutError, ConnectionFailure, Exception) as e:
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                logger.warning(
                    f"MongoDB connection attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                mongodb.connected = False
                logger.error(
                    f"Failed to connect to MongoDB after {max_retries} attempts. "
                    f"Error: {e}. Please ensure MongoDB is running at {settings.MONGODB_URL}"
                )
                raise ConnectionFailure(
                    f"Cannot connect to MongoDB at {settings.MONGODB_URL}. "
                    f"Please start MongoDB or check your connection settings."
                ) from e
    return False

async def connect_to_mongo():
    """Connect to MongoDB with retry logic and setup indexes"""
    try:
        # Create client with connection timeout settings
        mongodb.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,  # 5 second timeout per attempt
            connectTimeoutMS=5000
        )
        mongodb.database = mongodb.client[settings.MONGODB_DB_NAME]
        
        # Verify connection before proceeding
        await verify_connection()
        
        # Only create indexes if connection is successful
        if mongodb.connected:
            await create_indexes_and_validations()
            await create_counter_collection()
            logger.info("MongoDB indexes and counters initialized successfully")
    except Exception as e:
        mongodb.connected = False
        logger.error(f"Failed to initialize MongoDB connection: {e}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection"""
    if mongodb.client:
        mongodb.client.close()
        mongodb.connected = False
        logger.info("MongoDB connection closed")

async def get_database() -> AsyncIOMotorClient:
    """Get database instance, raising error if not connected"""
    if not mongodb.connected or mongodb.database is None:
        raise ConnectionFailure(
            "Database not connected. Please ensure MongoDB is running and the connection was established."
        )
    return mongodb.database

async def get_client() -> AsyncIOMotorClient:
    """Get MongoDB client instance for transactions, raising error if not connected"""
    if not mongodb.connected or mongodb.client is None:
        raise ConnectionFailure(
            "Database not connected. Please ensure MongoDB is running and the connection was established."
        )
    return mongodb.client

async def create_counter_collection():
    """Create counter collection for auto-incrementing IDs"""
    try:
        db = mongodb.database
        counter_collection = db["counters"]
        
        # Create counter for companies if it doesn't exist
        existing_company_counter = await counter_collection.find_one({"_id": "company_id"})
        if not existing_company_counter:
            await counter_collection.insert_one({
                "_id": "company_id",
                "sequence_value": 100000000
        })
        logger.info("Created company_id counter with initial value 100000000")
        
        # Create counter for lobs if it doesn't exist
        existing_lob_counter = await counter_collection.find_one({"_id": "lob_id"})
        if not existing_lob_counter:
            await counter_collection.insert_one({
                "_id": "lob_id",
                "sequence_value": 100000000
        })
        logger.info("Created lob_id counter with initial value 100000000")

        # Create counter for products if it doesn't exist
        existing_product_counter = await counter_collection.find_one({"_id": "product_id"})
        if not existing_product_counter:
            await counter_collection.insert_one({
                "_id": "product_id",
                "sequence_value": 100000000
        })
        logger.info("Created product_id counter with initial value 100000000")

        # Create counter for states if it doesn't exist
        existing_state_counter = await counter_collection.find_one({"_id": "state_id"})
        if not existing_state_counter:
            await counter_collection.insert_one({
                "_id": "state_id",
                "sequence_value": 100000000
        })
        logger.info("Created state_id counter with initial value 100000000")

        # Create counter for contexts if it doesn't exist
        existing_context_counter = await counter_collection.find_one({"_id": "context_id"})
        if not existing_context_counter:
            await counter_collection.insert_one({
                "_id": "context_id",
                "sequence_value": 100000000
        })
        logger.info("Created context_id counter with initial value 100000000")

        # Create counter for users if it doesn't exist
        existing_user_counter = await counter_collection.find_one({"_id": "user_id"})
        if not existing_user_counter:
            await counter_collection.insert_one({
                "_id": "user_id",
                "sequence_value": 1000
        })
        logger.info("Created user_id counter with initial value 1000")

        # Create counter for ratingtables if it doesn't exist
        existing_ratingtable_counter = await counter_collection.find_one({"_id": "ratingtable_id"})
        if not existing_ratingtable_counter:
            await counter_collection.insert_one({
                "_id": "ratingtable_id",
                "sequence_value": 100000000
        })
        logger.info("Created ratingtable_id counter with initial value 100000000")

        # Create counter for algorithms if it doesn't exist
        existing_algorithm_counter = await counter_collection.find_one({"_id": "algorithm_id"})
        if not existing_algorithm_counter:
            await counter_collection.insert_one({
                "_id": "algorithm_id",
                "sequence_value": 100000000
        })
        logger.info("Created algorithm_id counter with initial value 100000000")

        # Create counter for ratingmanuals if it doesn't exist
        existing_ratingmanual_counter = await counter_collection.find_one({"_id": "ratingmanual_id"})
        if not existing_ratingmanual_counter:
            await counter_collection.insert_one({
                "_id": "ratingmanual_id",
                "sequence_value": 100000000
            })
            logger.info("Created ratingmanual_id counter with initial value 100000000")
    except Exception as e:
        logger.error(f"Error creating counter collection: {e}")

async def get_next_sequence_value(sequence_name: str) -> int:
    """Get next auto-increment value for the specified sequence"""
    db = await get_database()
    counter_collection = db["counters"]
    
    result = await counter_collection.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"sequence_value": 1}},
        return_document=True
    )
    
    if not result:
        raise ValueError(f"Sequence {sequence_name} not found")
    
    return result["sequence_value"]

async def rollback_sequence_value(sequence_name: str) -> bool:
    """Rollback (decrement) the sequence value for the specified sequence"""
    try:
        db = await get_database()
        counter_collection = db["counters"]
        
        result = await counter_collection.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": -1}},
            return_document=True
        )
        
        if not result:
            logger.warning(f"Could not rollback sequence {sequence_name}: sequence not found")
            return False
        
        logger.info(f"Rolled back sequence {sequence_name} to {result['sequence_value']}")
        return True
    except Exception as e:
        logger.error(f"Error rolling back sequence {sequence_name}: {e}")
        return False

async def create_indexes_and_validations():
    """Create indexes and validation schemas for all collections"""
    if not mongodb.connected:
        raise ConnectionFailure("Cannot create indexes: MongoDB not connected")
    
    db = mongodb.database
    
    # Company collection indexes and validations
    company_collection = db["companies"]
      
    # Create indexes
    await company_collection.create_index("id", unique=True)
    await company_collection.create_index("company_code", unique=True)
    await company_collection.create_index("company_name")
    await company_collection.create_index("active")
    
    # Create validation schema (updated to make id optional for auto-generation)
    await db.command({
        "collMod": "companies",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["company_code", "company_name", "active", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be a long"
                    },
                    "company_code": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "company_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })
    # Company collection indexes and validations
    lob_collection = db["lobs"]
      
    # Create indexes
    await lob_collection.create_index("id", unique=True)
    await lob_collection.create_index("lob_code", unique=True)
    await lob_collection.create_index("lob_name")
    await lob_collection.create_index("active")
    
    # Create validation schema (updated to make id optional for auto-generation)
    await db.command({
        "collMod": "lobs",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["lob_code", "lob_name", "active", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be a long"
                    },
                    "lob_code": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "lob_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })    
    # Product collection indexes and validations
    product_collection = db["products"]
      
    # Create indexes
    await product_collection.create_index("id", unique=True)
    await product_collection.create_index("product_code", unique=True)
    await product_collection.create_index("product_name")
    await product_collection.create_index("lob_id")
    await product_collection.create_index("active")
    
    # Create validation schema (updated to make id optional for auto-generation)
    await db.command({
        "collMod": "products",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["product_code", "product_name", "lob_id", "active", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be a integer"
                    },
                    "product_code": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "product_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "lob_id": {
                        "bsonType": "int",
                        "description": "must be a integer and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })        
    # States collection indexes and validations
    state_collection = db["states"]
      
    # Create indexes
    await state_collection.create_index("id", unique=True)
    await state_collection.create_index("state_code", unique=True)
    await state_collection.create_index("state_name")
    await state_collection.create_index("active")
    
    # Create validation schema (updated to make id optional for auto-generation)
    await db.command({
        "collMod": "states",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["state_code", "state_name", "active", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be a long"
                    },
                    "state_code": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "state_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })

    # Context collection indexes and validations
    context_collection = db["contexts"]
      
    # Create indexes
    await context_collection.create_index("id", unique=True)
    await context_collection.create_index("context_code", unique=True)
    await context_collection.create_index("context_name")
    await context_collection.create_index("active")
    
    # Create validation schema (updated to make id optional for auto-generation)
    await db.command({
        "collMod": "contexts",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["context_code", "context_name", "active", "questions","created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be a long"
                    },
                    "context_code": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "context_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },

                    "questions": {
                        "bsonType": "array",
                        "description": "must be a boolean and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })

    # RatingTable collection indexes and validations
    ratingtable_collection = db["ratingtables"]
    
    # Create indexes
    await ratingtable_collection.create_index("id", unique=True)
    await ratingtable_collection.create_index("table_name")
    await ratingtable_collection.create_index("table_type")
    await ratingtable_collection.create_index("active")
    await ratingtable_collection.create_index("company")
    await ratingtable_collection.create_index("lob")
    await ratingtable_collection.create_index("state")
    await ratingtable_collection.create_index("product")
    await ratingtable_collection.create_index("context")
    await ratingtable_collection.create_index("effective_date")
    await ratingtable_collection.create_index("expiration_date")
    
    # Create compound unique index for primary unique combination
    # table_name + company + lob + state + product + effective_date
    # Partial index: only applies to active records (active: true)
    try:
        # Drop existing index with the same name if it exists (to handle specification changes)
        try:
            await ratingtable_collection.drop_index("unique_combination_idx")
            logger.info("Dropped existing unique_combination_idx index to recreate with updated specification")
        except Exception as drop_error:
            # Index doesn't exist or couldn't be dropped, that's fine
            logger.debug(f"Could not drop existing unique_combination_idx index (may not exist): {drop_error}")
        
        # Create the new index with partial filter expression
        await ratingtable_collection.create_index(
            [("table_name", 1), ("company", 1), ("lob", 1), ("state", 1), ("product", 1), ("effective_date", 1)],
            unique=True,
            partialFilterExpression={"active": True},
            name="unique_combination_idx"
        )
        logger.info("Created compound unique partial index for table_name+company+lob+state+product+effective_date (active records only)")
    except Exception as e:
        # Index might already exist or have conflicts, log and continue
        logger.warning(f"Could not create compound unique index: {e}")
    
    # Create validation schema
    await db.command({
        "collMod": "ratingtables",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["table_name", "company", "lob", "state", "product", "active", "version", "effective_date", "data", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be an integer"
                    },
                    "table_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "table_type": {
                        "bsonType": ["string", "null"],
                        "description": "must be a string or null (optional)"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "version": {
                        "bsonType": "double",
                        "description": "must be a float and is required"
                    },
                    "effective_date": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "expiration_date": {
                        "bsonType": ["date", "null"],
                        "description": "must be a date or null (optional)"
                    },
                    "data": {
                        "bsonType": "array",
                        "description": "must be an array and is required"
                    },
                    "company": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "lob": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "state": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "product": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "context": {
                        "bsonType": ["int", "null"],
                        "description": "must be an integer ID or null (optional)"
                    },
                    "lookup_config": {
                        "bsonType": "object",
                        "description": "must be an object"
                    },
                    "ai_metadata": {
                        "bsonType": "object",
                        "description": "must be an object"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })

    # Algorithm collection indexes and validations
    algorithm_collection = db["algorithms"]
    
    # Create indexes
    await algorithm_collection.create_index("id", unique=True)
    await algorithm_collection.create_index("algorithm_name")
    await algorithm_collection.create_index("algorithm_type")
    await algorithm_collection.create_index("active")
    await algorithm_collection.create_index("company")
    await algorithm_collection.create_index("lob")
    await algorithm_collection.create_index("state")
    await algorithm_collection.create_index("product")
    await algorithm_collection.create_index("effective_date")
    await algorithm_collection.create_index("expiration_date")
    await algorithm_collection.create_index("required_tables")
    
    # Create compound unique index for primary unique combination
    # algorithm_name + company + lob + state + product + effective_date
    # Partial index: only applies to active records (active: true)
    try:
        # Drop existing index with the same name if it exists (to handle specification changes)
        try:
            await algorithm_collection.drop_index("unique_combination_idx")
            logger.info("Dropped existing unique_combination_idx index for algorithms to recreate with updated specification")
        except Exception as drop_error:
            # Index doesn't exist or couldn't be dropped, that's fine
            logger.debug(f"Could not drop existing unique_combination_idx index for algorithms (may not exist): {drop_error}")
        
        # Create the new index with partial filter expression
        await algorithm_collection.create_index(
            [("algorithm_name", 1), ("company", 1), ("lob", 1), ("state", 1), ("product", 1), ("effective_date", 1)],
            unique=True,
            partialFilterExpression={"active": True},
            name="unique_combination_idx"
        )
        logger.info("Created compound unique partial index for algorithm_name+company+lob+state+product+effective_date (active records only)")
    except Exception as e:
        # Index might already exist or have conflicts, log and continue
        logger.warning(f"Could not create compound unique index for algorithms: {e}")
    
    # Create validation schema
    await db.command({
        "collMod": "algorithms",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["algorithm_name", "company", "lob", "state", "product", "active", "version", "effective_date", "required_tables", "formula", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be an integer"
                    },
                    "algorithm_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "algorithm_type": {
                        "bsonType": ["string", "null"],
                        "description": "must be a string or null (optional)"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "version": {
                        "bsonType": "double",
                        "description": "must be a float and is required"
                    },
                    "effective_date": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "expiration_date": {
                        "bsonType": ["date", "null"],
                        "description": "must be a date or null (optional)"
                    },
                    "required_tables": {
                        "bsonType": "array",
                        "description": "must be an array of integers and is required"
                    },
                    "formula": {
                        "bsonType": "object",
                        "description": "must be an object and is required"
                    },
                    "calculation_steps": {
                        "bsonType": ["array", "null"],
                        "description": "must be an array or null (optional)"
                    },
                    "variables": {
                        "bsonType": ["object", "null"],
                        "description": "must be an object or null (optional)"
                    },
                    "company": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "lob": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "state": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "product": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })

    # RatingManual collection indexes and validations
    ratingmanual_collection = db["ratingmanuals"]
    
    # Create indexes
    await ratingmanual_collection.create_index("id", unique=True)
    await ratingmanual_collection.create_index("manual_name")
    await ratingmanual_collection.create_index("active")
    await ratingmanual_collection.create_index("company")
    await ratingmanual_collection.create_index("lob")
    await ratingmanual_collection.create_index("state")
    await ratingmanual_collection.create_index("product")
    await ratingmanual_collection.create_index("ratingtable")
    await ratingmanual_collection.create_index("effective_date")
    await ratingmanual_collection.create_index("expiration_date")
    await ratingmanual_collection.create_index("priority")
    
    # Create compound unique index for primary unique combination
    # manual_name + company + lob + product + state + effective_date (ratingtable excluded to allow versioning on ratingtable changes)
    # Partial index: only applies to active records (active: true)
    try:
        # Drop existing index with the same name if it exists (to handle specification changes)
        try:
            await ratingmanual_collection.drop_index("unique_ratingmanual_combination_idx")
            logger.info("Dropped existing unique_ratingmanual_combination_idx index to recreate with updated specification")
        except Exception as drop_error:
            # Index doesn't exist or couldn't be dropped, that's fine
            logger.debug(f"Could not drop existing unique_ratingmanual_combination_idx index (may not exist): {drop_error}")
        
        # Before creating unique index, handle any duplicate records
        # Find all active records grouped by the unique combination
        from datetime import datetime, timezone, timedelta
        pipeline = [
            {"$match": {"active": True}},
            {
                "$group": {
                    "_id": {
                        "manual_name": "$manual_name",
                        "company": "$company",
                        "lob": "$lob",
                        "product": "$product",
                        "state": "$state",
                        "effective_date": "$effective_date"
                    },
                    "records": {
                        "$push": {
                            "id": "$id",
                            "version": "$version",
                            "created_at": "$created_at"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        duplicate_groups = await ratingmanual_collection.aggregate(pipeline).to_list(length=None)
        
        if duplicate_groups:
            logger.warning(f"Found {len(duplicate_groups)} duplicate groups in ratingmanuals collection. Cleaning up duplicates...")
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_minus_one = today - timedelta(days=1)
            now = datetime.now(timezone.utc)
            
            total_expired = 0
            for group in duplicate_groups:
                records = group["records"]
                # Sort by version (descending) and created_at (descending) to keep the most recent/highest version
                # Handle datetime objects properly - MongoDB returns datetime objects
                def sort_key(record):
                    version = record.get("version", 1.0)
                    created_at = record.get("created_at")
                    # If created_at is a datetime, use it; otherwise use min datetime
                    if isinstance(created_at, datetime):
                        created_at_val = created_at
                    else:
                        created_at_val = datetime.min.replace(tzinfo=timezone.utc)
                    return (version, created_at_val)
                
                records.sort(key=sort_key, reverse=True)
                
                # Keep the first record (highest version, most recent), expire the rest
                keep_id = records[0]["id"]
                expire_ids = [r["id"] for r in records[1:]]
                
                if expire_ids:
                    result = await ratingmanual_collection.update_many(
                        {"id": {"$in": expire_ids}},
                        {
                            "$set": {
                                "active": False,
                                "expiration_date": today_minus_one,
                                "updated_at": now
                            }
                        }
                    )
                    total_expired += result.modified_count
                    logger.info(f"Expired {len(expire_ids)} duplicate rating manual records (keeping id {keep_id})")
            
            logger.info(f"Cleaned up duplicate rating manual records. Kept {len(duplicate_groups)} records, expired {total_expired} duplicates")
        
        # Create the new index with partial filter expression (ratingtable excluded to allow versioning)
        await ratingmanual_collection.create_index(
            [("manual_name", 1), ("company", 1), ("lob", 1), ("product", 1), ("state", 1), ("effective_date", 1)],
            unique=True,
            partialFilterExpression={"active": True},
            name="unique_ratingmanual_combination_idx"
        )
        logger.info("Created compound unique partial index for manual_name+company+lob+product+state+effective_date (active records only, ratingtable excluded for versioning)")
    except Exception as e:
        # Check if it's a duplicate key error and try to clean up
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            logger.warning(f"Duplicate key error when creating index. Attempting to clean up duplicates and retry...")
            try:
                # Try to clean up duplicates more aggressively
                from datetime import datetime, timezone, timedelta
                today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                today_minus_one = today - timedelta(days=1)
                
                # Find and expire all but the most recent record for each combination
                pipeline = [
                    {"$match": {"active": True}},
                    {
                        "$group": {
                            "_id": {
                                "manual_name": "$manual_name",
                                "company": "$company",
                                "lob": "$lob",
                                "product": "$product",
                                "state": "$state",
                                "effective_date": "$effective_date"
                            },
                            "records": {"$push": {"id": "$id", "version": "$version", "created_at": "$created_at"}},
                            "count": {"$sum": 1}
                        }
                    },
                    {"$match": {"count": {"$gt": 1}}}
                ]
                
                duplicate_groups = await ratingmanual_collection.aggregate(pipeline).to_list(length=None)
                
                total_expired = 0
                for group in duplicate_groups:
                    records = group["records"]
                    # Sort by version (descending) and created_at (descending)
                    def sort_key(record):
                        version = record.get("version", 1.0)
                        created_at = record.get("created_at")
                        # If created_at is a datetime, use it; otherwise use min datetime
                        if isinstance(created_at, datetime):
                            created_at_val = created_at
                        else:
                            created_at_val = datetime.min.replace(tzinfo=timezone.utc)
                        return (version, created_at_val)
                    
                    records.sort(key=sort_key, reverse=True)
                    
                    # Keep the first record, expire the rest
                    keep_id = records[0]["id"]
                    expire_ids = [r["id"] for r in records[1:]]
                    
                    if expire_ids:
                        result = await ratingmanual_collection.update_many(
                            {"id": {"$in": expire_ids}},
                            {
                                "$set": {
                                    "active": False,
                                    "expiration_date": today_minus_one,
                                    "updated_at": datetime.now(timezone.utc)
                                }
                            }
                        )
                        total_expired += result.modified_count
                        logger.info(f"Expired {len(expire_ids)} duplicate rating manual records (keeping id {keep_id})")
                
                logger.info(f"Retry cleanup: Expired {total_expired} duplicate rating manual records")
                
                # Retry creating the index
                await ratingmanual_collection.create_index(
                    [("manual_name", 1), ("company", 1), ("lob", 1), ("product", 1), ("state", 1), ("effective_date", 1)],
                    unique=True,
                    partialFilterExpression={"active": True},
                    name="unique_ratingmanual_combination_idx"
                )
                logger.info("Successfully created compound unique partial index for ratingmanuals after cleaning duplicates")
            except Exception as retry_error:
                logger.error(f"Failed to create compound unique index for ratingmanuals even after cleanup: {retry_error}")
                logger.warning(f"Index creation failed. Manual cleanup may be required. Error: {e}")
        else:
            # Index might already exist or have other conflicts, log and continue
            logger.warning(f"Could not create compound unique index for ratingmanuals: {e}")
    
    # Create validation schema
    await db.command({
        "collMod": "ratingmanuals",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["manual_name", "company", "lob", "state", "product", "ratingtable", "active", "version", "effective_date", "priority", "created_at", "updated_at"],
                "properties": {
                    "id": {
                        "bsonType": "int",
                        "description": "must be an integer"
                    },
                    "manual_name": {
                        "bsonType": "string",
                        "description": "must be a string and is required"
                    },
                    "active": {
                        "bsonType": "bool",
                        "description": "must be a boolean and is required"
                    },
                    "version": {
                        "bsonType": "double",
                        "description": "must be a float and is required"
                    },
                    "effective_date": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "expiration_date": {
                        "bsonType": ["date", "null"],
                        "description": "must be a date or null (optional)"
                    },
                    "company": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "lob": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "state": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "product": {
                        "bsonType": "int",
                        "description": "must be an integer ID and is required"
                    },
                    "ratingtable": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "int"
                        },
                        "description": "must be an array of integer IDs and is required"
                    },
                    "priority": {
                        "bsonType": "int",
                        "description": "must be an integer and is required"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "must be a date and is required"
                    }
                }
            }
        },
        "validationLevel": "strict"
    })