from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from app.db.models.month_snapshots_model import create_month_snapshot_if_missing


SYSTEM_STATE_ID = "monthly_reset"


def current_month_key(now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    return now.strftime("%Y-%m")


async def ensure_monthly_rollover() -> Tuple[bool, str]:
    """
    Detecta cambio de mes y ejecuta el reset mensual UNA sola vez (global):
    - Guarda snapshot del mes anterior (top3 + stats) en month_snapshots
    - Resetea rank.earned_this_month a 0 y rank.month_key al mes actual
      para los usuarios que aún estén en el mes anterior.

    Retorna (changed, msg)
    """
    db = get_db()
    now = datetime.utcnow()
    cur_mk = current_month_key(now)

    state = await db.system_state.find_one({"_id": SYSTEM_STATE_ID})
    if not state:
        # Primera vez: inicializa el mes actual, no hace reset
        await db.system_state.update_one(
            {"_id": SYSTEM_STATE_ID},
            {"$set": {"month_key": cur_mk, "last_run_at": now}},
            upsert=True,
        )
        return False, "Initialized"

    prev_mk = (state.get("month_key") or "").strip()
    if not prev_mk:
        await db.system_state.update_one(
            {"_id": SYSTEM_STATE_ID},
            {"$set": {"month_key": cur_mk, "last_run_at": now}},
        )
        return False, "State fixed"

    if prev_mk == cur_mk:
        # No cambió el mes
        return False, "No rollover"

    # ---- 1) Construir TOP 3 del mes anterior ----
    pipeline = [
        {"$match": {"rank.month_key": prev_mk}},
        {
            "$project": {
                "_id": 0,
                "telegram_id": 1,
                "username": 1,
                "first_name": 1,
                "earned": {"$ifNull": ["$rank.earned_this_month", 0]},
            }
        },
        {"$sort": {"earned": -1, "telegram_id": 1}},
        {"$limit": 3},
    ]
    top3: List[Dict[str, Any]] = await db.users.aggregate(pipeline).to_list(length=3)

    # ---- 2) Stats del mes anterior ----
    stats_pipeline = [
        {"$match": {"rank.month_key": prev_mk}},
        {
            "$group": {
                "_id": None,
                "users_count": {"$sum": 1},
                "total_earned": {"$sum": {"$ifNull": ["$rank.earned_this_month", 0]}},
                "max_earned": {"$max": {"$ifNull": ["$rank.earned_this_month", 0]}},
            }
        },
    ]
    stats_rows = await db.users.aggregate(stats_pipeline).to_list(length=1)
    stats = stats_rows[0] if stats_rows else {"users_count": 0, "total_earned": 0, "max_earned": 0}
    stats.pop("_id", None)

    # ---- 3) Guardar snapshot (si no existe ya) ----
    await create_month_snapshot_if_missing(
        month_key=prev_mk,
        top3=top3,
        stats=stats,
        created_at=now,
    )

    # ---- 4) Resetear ranking mensual para los usuarios del mes anterior ----
    # IMPORTANT: No tocamos balance_cached ni ledger.
    result = await db.users.update_many(
        {"rank.month_key": prev_mk},
        {
            "$set": {
                "rank.month_key": cur_mk,
                "rank.earned_this_month": 0,
                "rank.last_reset_at": now,
            }
        },
    )

    # ---- 5) Actualizar system_state ----
    await db.system_state.update_one(
        {"_id": SYSTEM_STATE_ID},
        {"$set": {"month_key": cur_mk, "last_run_at": now, "prev_month_key": prev_mk}},
    )

    return True, f"Rolled over {prev_mk} -> {cur_mk}, reset_users={getattr(result, 'modified_count', 0)}"
