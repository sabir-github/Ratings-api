from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from passlib.context import CryptContext
from app.core.database import get_database, get_next_sequence_value
from app.schemas.user import UserCreateSchema, UserUpdateSchema, UserPasswordUpdateSchema
from app.models.user import UserRole, UserStatus
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    def __init__(self):
        self.collection_name = "users"

    async def get_collection(self):
        db = await get_database()
        return db[self.collection_name]

    async def _generate_user_id(self) -> int:
        """Generate auto-incrementing user ID"""
        try:
            return await get_next_sequence_value("user_id")
        except Exception as e:
            logger.error(f"Error generating user ID: {e}")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    async def create_user(self, user_data: UserCreateSchema):
        collection = await self.get_collection()
        
        # Check if username or email already exists
        existing_user = await collection.find_one({
            "$or": [
                {"username": user_data.username},
                {"email": user_data.email}
            ]
        })
        
        if existing_user:
            if existing_user["username"] == user_data.username:
                raise ValueError("Username already exists")
            else:
                raise ValueError("Email already exists")
        
        # Generate user ID
        user_id = await self._generate_user_id()
        
        now = datetime.now(timezone.utc)
        user_dict = {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "hashed_password": self.get_password_hash(user_data.password),
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "role": user_data.role.value,
            "status": user_data.status.value,
            "company_id": user_data.company_id,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }
        
        try:
            result = await collection.insert_one(user_dict)
            created_user = await collection.find_one({"_id": result.inserted_id})
            return created_user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user(self, user_id: int):
        collection = await self.get_collection()
        user = await collection.find_one({"id": user_id})
        return user

    async def get_user_by_username(self, username: str):
        collection = await self.get_collection()
        user = await collection.find_one({"username": username})
        return user

    async def get_user_by_email(self, email: str):
        collection = await self.get_collection()
        user = await collection.find_one({"email": email})
        return user

    async def authenticate_user(self, username: str, password: str):
        """Authenticate user by username/email and password"""
        # Try username first
        user = await self.get_user_by_username(username)
        
        # If not found by username, try email
        if not user:
            user = await self.get_user_by_email(username)
        
        if not user:
            return None
        
        if not self.verify_password(password, user["hashed_password"]):
            return None
        
        return user

    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        collection = await self.get_collection()
        await collection.update_one(
            {"id": user_id},
            {"$set": {"last_login": datetime.now(timezone.utc)}})
        return True

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        filter_by: Optional[Dict] = None,
        sort_by: Optional[str] = None,
        sort_order: int = 1
    ):
        collection = await self.get_collection()
        
        # Build query
        query = {}
        if filter_by:
            if "status" in filter_by:
                query["status"] = filter_by["status"]
            if "role" in filter_by:
                query["role"] = filter_by["role"]
            if "username" in filter_by:
                query["username"] = {"$regex": filter_by["username"], "$options": "i"}
            if "email" in filter_by:
                query["email"] = {"$regex": filter_by["email"], "$options": "i"}
            if "company_id" in filter_by:
                query["company_id"] = filter_by["company_id"]
        
        # Build sort
        sort = []
        if sort_by:
            sort.append((sort_by, sort_order))
        else:
            sort.append(("id", 1))
        
        # Exclude password from results
        projection = {"hashed_password": 0}
        
        cursor = collection.find(query, projection).skip(skip).limit(limit).sort(sort)
        users = await cursor.to_list(length=limit)
        return users

    async def update_user(self, user_id: int, update_data: UserUpdateSchema):
        collection = await self.get_collection()
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None
        
        # Convert enum values to strings
        if "role" in update_dict and update_dict["role"]:
            update_dict["role"] = update_dict["role"].value
        if "status" in update_dict and update_dict["status"]:
            update_dict["status"] = update_dict["status"].value
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await collection.update_one(
            {"id": user_id},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            return None
            
        updated_user = await collection.find_one({"id": user_id}, {"hashed_password": 0})
        return updated_user

    async def update_user_password(self, user_id: int, password_data: UserPasswordUpdateSchema):
        """Update user password with current password verification"""
        collection = await self.get_collection()
        
        user = await collection.find_one({"id": user_id})
        if not user:
            return False
        
        # Verify current password
        if not self.verify_password(password_data.current_password, user["hashed_password"]):
            raise ValueError("Current password is incorrect")
        
        # Hash new password
        new_hashed_password = self.get_password_hash(password_data.new_password)
        
        result = await collection.update_one(
            {"id": user_id},
            {"$set": {
                "hashed_password": new_hashed_password,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return result.modified_count > 0

    async def delete_user(self, user_id: int) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"id": user_id})
        return result.deleted_count > 0

    async def count_users(self, filter_by: Optional[Dict] = None) -> int:
        collection = await self.get_collection()
        
        query = {}
        if filter_by:
            if "status" in filter_by:
                query["status"] = filter_by["status"]
            if "role" in filter_by:
                query["role"] = filter_by["role"]
        
        return await collection.count_documents(query)

    async def get_users_by_company(self, company_id: int, skip: int = 0, limit: int = 100):
        """Get users by company ID"""
        return await self.get_users(
            skip=skip,
            limit=limit,
            filter_by={"company_id": company_id}
        )
    async def update_user_status(self, user_id: int, status: str) -> bool:
        """Update user status"""
        collection = await self.get_collection()
        result = await collection.update_one(
            {"id": user_id},
            {"$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc)
        }})
        return result.modified_count > 0

    async def get_user_stats(self) -> Dict[str, int]:
        """Get user statistics"""
        collection = await self.get_collection()
    
        total_users = await collection.count_documents({})
        active_users = await collection.count_documents({"status": "active"})
        admin_users = await collection.count_documents({"role": "admin"})
        manager_users = await collection.count_documents({"role": "manager"})
    
        return {
            "total_users": total_users,
            "active_users": active_users,
            "admin_users": admin_users,
            manager_users: manager_users}
user_service = UserService()