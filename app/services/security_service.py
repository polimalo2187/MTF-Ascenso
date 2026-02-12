from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional

from app.db.connection import get_db
from app.services.ledger_service import (
    create_points_entry,
    TYPE_PENALTY,
    CAT_SECURITY,
)

REASON_PENALTY_POINTS_REMOVED = "PENALTY_POINTS_REMOVED"
REASON_SECURITY_BLOCK = "SECURITY_BLOCK"
REASON_SECURITY_BAN = "SECURITY_BAN"


def _get_first_penalty_points() -> int:
    try:
        v = int(os.getenv("PENALTY_FIRST_POINTS", "50").strip())
        return max(1, v)
    except Exception:
        return 50


def _get_block_days() -> int:
    try:
        v = int(os.getenv("BLOCK_DAYS", "7").strip())
        return max(1, v)
    except Exception:
        return 7


async def get_user_security_snapshot(telegram_id: int) -> Tuple[bool, str, Optional[dict]]:
    db = get_db()
    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"status": 1, "infractions": 1, "points.balance_cached": 1},
    )
    if not user:
        return False, "Usuario no encontrado.", None
    return True, "OK", user


async def apply_next_infraction(user_telegram_id: int, admin_id: int, note: str = "") -> Tuple[bool, str]:
    """
    Aplica sanción escalonada:
    - count=0 => 1ra: quita puntos (penalty ledger) + warning
    - count=1 => 2da: bloqueo temporal
    - count>=2 => 3ra: expulsión definitiva
    """
    db = get_db()
    user = await db.users.find_one(
        {"telegram_id": user_telegram_id},
        {"infractions": 1, "status": 1, "points.balance_cached": 1},
    )
    if not user:
        return False, "Usuario no encontrado."

    now = datetime.utcnow()
    infra = user.get("infractions") or {}
    count = int(infra.get("count") or 0)

    status = user.get("status") or {}
    state = status.get("state", "active")

    # Si ya está baneado, no hacemos nada
    if state == "banned":
        return False, "El usuario ya está expulsado (banned)."

    # 1ra infracción: quitar puntos
    if count == 0:
        penalty_points = _get_first_penalty_points()
        # No puede quedar negativo: quitamos hasta el balance disponible
        balance = int(((user.get("points") or {}).get("balance_cached")) or 0)
        to_remove = min(penalty_points, max(0, balance))

        if to_remove > 0:
            await create_points_entry(
                telegram_id=user_telegram_id,
                entry_type=TYPE_PENALTY,
                category=CAT_SECURITY,
                reason_code=REASON_PENALTY_POINTS_REMOVED,
                points=to_remove,
                meta={"admin_id": admin_id, "note": note or "Primera infracción"},
            )

        await db.users.update_one(
            {"telegram_id": user_telegram_id},
            {
                "$set": {
                    "infractions.last_at": now,
                    "last_seen_at": now,
                },
                "$inc": {"infractions.count": 1},
            },
        )

        return True, f"⚠ 1ra infracción aplicada. Puntos eliminados: {to_remove}."

    # 2da infracción: bloqueo
    if count == 1:
        days = _get_block_days()
        blocked_until = now + timedelta(days=days)

        await db.users.update_one(
            {"telegram_id": user_telegram_id},
            {
                "$set": {
                    "status.state": "blocked",
                    "status.blocked_until": blocked_until,
                    "status.ban_reason": None,
                    "infractions.last_at": now,
                    "last_seen_at": now,
                },
                "$inc": {"infractions.count": 1},
            },
        )

        return True, f"⛔ 2da infracción aplicada. Bloqueo temporal por {days} días (hasta {blocked_until.strftime('%Y-%m-%d %H:%M UTC')})."

    # 3ra infracción: expulsión definitiva
    await db.users.update_one(
        {"telegram_id": user_telegram_id},
        {
            "$set": {
                "status.state": "banned",
                "status.blocked_until": None,
                "status.ban_reason": note or "Tercera infracción",
                "infractions.last_at": now,
                "last_seen_at": now,
            },
            "$inc": {"infractions.count": 1},
        },
    )

    return True, "🚫 3ra infracción aplicada. Usuario expulsado definitivamente (banned)."
