from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    database = None

mongodb = MongoDB()

async def connect_to_mongo():
    mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL)
    mongodb.database = mongodb.client[settings.MONGODB_DB_NAME]
    await create_indexes_and_validations()
    await create_counter_collection()

async def close_mongo_connection():
    mongodb.client.close()

async def get_database() -> AsyncIOMotorClient:
    return mongodb.database

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

async def create_indexes_and_validations():
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