#!/usr/bin/env python3
"""Test MongoDB connection"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_connection():
    client = AsyncIOMotorClient(
        'mongodb://admin:password@localhost:27017/?authSource=admin',
        serverSelectionTimeoutMS=5000
    )
    try:
        await client.admin.command('ping')
        print('✅ MongoDB connection successful!')
        
        # Test database access
        db = client['ratings_db']
        collections = await db.list_collection_names()
        print(f'✅ Database "ratings_db" accessible. Collections: {collections}')
        
        return True
    except Exception as e:
        print(f'❌ Connection failed: {e}')
        return False
    finally:
        client.close()

if __name__ == '__main__':
    asyncio.run(test_connection())

