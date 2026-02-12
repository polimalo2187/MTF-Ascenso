from datetime import datetime
from app.db.connection import get_db


async def get_user(telegram_id: int):
    db = get_db()
    return await db.users.find_one({"telegram_id": telegram_id})


async def create_user(user_data: dict):
    db = get_db()
    await db.users.insert_one(user_data)


async def update_user(telegram_id: int, update_data: dict):
    db = get_db()
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": update_data}
    )
