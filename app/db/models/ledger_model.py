from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.connection import get_db


async def create_ledger_entry(entry: Dict[str, Any]) -> str:
    """
    Inserta un movimiento (ledger entry). Retorna el _id insertado como string.
    """
    db = get_db()
    res = await db.ledger.insert_one(entry)
    return str(res.inserted_id)


async def get_ledger_entry_by_entry_id(entry_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db.ledger.find_one({"entry_id": entry_id})


async def list_user_ledger_entries(
    telegram_id: int,
    limit: int = 50,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    db = get_db()
    cursor = (
        db.ledger.find({"telegram_id": telegram_id})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def sum_user_ledger_points(
    telegram_id: int,
) -> int:
    """
    Recalcula saldo desde ledger (costoso). Útil para auditoría.
    """
    db = get_db()
    pipeline = [
        {"$match": {"telegram_id": telegram_id}},
        {
            "$group": {
                "_id": "$telegram_id",
                "sum": {"$sum": "$signed_points"},
            }
        },
    ]
    rows = await db.ledger.aggregate(pipeline).to_list(length=1)
    if not rows:
        return 0
    return int(rows[0]["sum"])


async def sum_user_month_earned_points(
    telegram_id: int,
    month_key: str,
) -> int:
    """
    Suma SOLO puntos ganados en el mes (EARN/BONUS/ADJUST positivos), para ranking mensual.
    """
    db = get_db()
    pipeline = [
        {
            "$match": {
                "telegram_id": telegram_id,
                "month_key": month_key,
                "month_earned_points": {"$exists": True},
            }
        },
        {
            "$group": {
                "_id": "$telegram_id",
                "sum": {"$sum": "$month_earned_points"},
            }
        },
    ]
    rows = await db.ledger.aggregate(pipeline).to_list(length=1)
    if not rows:
        return 0
    return int(rows[0]["sum"])
