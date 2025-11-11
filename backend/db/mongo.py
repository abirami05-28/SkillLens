# db/mongo.py
import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "skilllens")

client = None
datab = None
candidates_collection = None
users_collection = None

async def init_mongo():
    global client, datab, candidates_collection, users_collection
    if not MONGO_URI:
        print("❌ MONGO_URI is not set in your .env. Please add it and restart the app.")
        return None

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    datab = client[MONGO_DB]
    candidates_collection = datab["candidates"]
    users_collection = datab["users"]

    try:
        await client.admin.command("ping")
        print("✅ MongoDB connection successful")
    except Exception as e:
        print("❌ MongoDB connection failed:", e)
        return None
    return datab

def get_database():
    global datab
    """Return the motor database object or None if not initialized."""
    if datab is not None:
        return datab
    return None

def get_collection(name):
    """Convenience helper: returns a collection object or None if DB not initialized."""
    if datab is None:
        return None
    return datab.get_collection(name)
