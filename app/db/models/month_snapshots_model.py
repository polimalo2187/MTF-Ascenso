from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.connection import get_db


async def create_month_snapshot_if_missing(
    month_key: str,
    top3: List[Dict[str, Any]],
    stats: Dict[str, Any],
    created_at: Optional[datetime] = None,
) -> bool:
    """
    Crea un snapshot mensual si no existe.
    Retorna True si lo creó, False si ya existía.
    """
    db = get_db()
    created_at = created_at or datetime.utcnow()

    existing = await db.month_snapshots.find_one({"month_key": month_key}, {"_id": 1})
    if existing:
        return False

    doc = {
        "month_key": month_key,
        "created_at": created_at,
        "top3": top3,
        "stats": stats,
    }
    await db.month_snapshots.insert_one(doc)
    return True


async def get_month_snapshot(month_key: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db.month_snapshots.find_one({"month_key": month_key}, {"_id": 0})
