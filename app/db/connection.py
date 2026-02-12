import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

client = None
db = None


async def init_db():
    global client, db
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "mtf_ascenso")

    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]


def get_db():
    return db
