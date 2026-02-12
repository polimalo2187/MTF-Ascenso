from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson import ObjectId
from app.db.connection import get_db


async def create_task_claim(doc: Dict[str, Any]) -> str:
    db = get_db()
    res = await db.task_claims.insert_one(doc)
    return str(res.inserted_id)


async def find_task_claim_by_id(claim_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        oid = ObjectId(claim_id)
    except Exception:
        return None
    return await db.task_claims.find_one({"_id": oid})


async def find_user_claim_for_day(
    telegram_id: int,
    task_code: str,
    day_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Para tareas diarias tipo CHECKIN/LESSON: evita duplicar en el mismo día.
    """
    db = get_db()
    return await db.task_claims.find_one(
        {
            "telegram_id": telegram_id,
            "task_code": task_code,
            "day_key": day_key,
        }
    )


async def list_pending_claims(limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = (
        db.task_claims.find({"status": "pending"})
        .sort("created_at", 1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def update_claim_status(
    claim_id: str,
    status: str,
    admin_id: int,
    note: str = "",
) -> bool:
    """
    status: approved | rejected
    """
    db = get_db()
    try:
        oid = ObjectId(claim_id)
    except Exception:
        return False

    res = await db.task_claims.update_one(
        {"_id": oid, "status": "pending"},
        {
            "$set": {
                "status": status,
                "approved_at": __import__("datetime").datetime.utcnow(),
                "meta.admin_id": admin_id,
                "meta.admin_note": note,
            }
        },
    )
    return res.modified_count == 1
