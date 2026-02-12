from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Tuple

from app.db.connection import get_db


def _get_float_env(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)).strip())
    except Exception:
        return default


def _get_int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except Exception:
        return default


def _tier_days() -> int:
    return max(1, _get_int_env("TIER_DAYS", 30))


def elite_mult() -> float:
    return max(1.0, _get_float_env("ELITE_MULT", 1.2))


def titan_mult() -> float:
    return max(1.0, _get_float_env("TITAN_MULT", 1.5))


def elite_threshold() -> int:
    return max(1, _get_int_env("ELITE_THRESHOLD", 200))


def titan_threshold() -> int:
    return max(1, _get_int_env("TITAN_THRESHOLD", 400))


def titan_premium_redeems_required() -> int:
    return max(1, _get_int_env("TITAN_PREMIUM_REDEEMS", 3))


async def refresh_tiers(telegram_id: int) -> None:
    """
    Apaga Elite/Titan si ya expiraron.
    """
    db = get_db()
    now = datetime.utcnow()

    user = await db.users.find_one({"telegram_id": telegram_id}, {"elite": 1, "titan": 1})
    if not user:
        return

    elite = user.get("elite") or {}
    titan = user.get("titan") or {}

    updates = {}

    if bool(elite.get("active")):
        until = elite.get("active_until")
        if until and isinstance(until, datetime) and until <= now:
            updates["elite.active"] = False
            updates["elite.active_until"] = None
            updates["elite.forced"] = False
            updates["elite.forced_by_admin_id"] = None
            updates["elite.forced_note"] = None

    if bool(titan.get("active")):
        until = titan.get("active_until")
        if until and isinstance(until, datetime) and until <= now:
            updates["titan.active"] = False
            updates["titan.active_until"] = None
            updates["titan.forced"] = False
            updates["titan.forced_by_admin_id"] = None
            updates["titan.forced_note"] = None

    if updates:
        await db.users.update_one({"telegram_id": telegram_id}, {"$set": updates})


async def get_multiplier(telegram_id: int) -> float:
    await refresh_tiers(telegram_id)

    db = get_db()
    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"elite": 1, "titan": 1, "status": 1},
    )
    if not user:
        return 1.0

    state = ((user.get("status") or {}).get("state")) or "active"
    if state in ("blocked", "banned"):
        return 1.0

    if bool(((user.get("titan") or {}).get("active"))):
        return titan_mult()
    if bool(((user.get("elite") or {}).get("active"))):
        return elite_mult()
    return 1.0


async def ensure_auto_tier_by_month_points(telegram_id: int) -> Tuple[bool, str]:
    """
    Promoción automática por puntos del mes:
    - >= TITAN_THRESHOLD => Titan 30d
    - >= ELITE_THRESHOLD => Elite 30d
    """
    db = get_db()
    await refresh_tiers(telegram_id)

    now = datetime.utcnow()
    mk = now.strftime("%Y-%m")

    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"rank": 1, "elite": 1, "titan": 1, "status": 1},
    )
    if not user:
        return False, "Usuario no encontrado."

    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "Usuario baneado."

    user_mk = ((user.get("rank") or {}).get("month_key")) or mk
    if user_mk != mk:
        return False, "Mes distinto."

    earned = int(((user.get("rank") or {}).get("earned_this_month")) or 0)

    # Titan por puntos del mes
    if earned >= titan_threshold():
        if not bool(((user.get("titan") or {}).get("active"))):
            until = now + timedelta(days=_tier_days())
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"titan.active": True, "titan.active_until": until, "titan.forced": False}},
            )
            return True, "Promovido a TITAN"
        return False, "Ya TITAN"

    # Elite por puntos del mes
    if earned >= elite_threshold():
        if bool(((user.get("titan") or {}).get("active"))):
            return False, "Ya TITAN"
        if not bool(((user.get("elite") or {}).get("active"))):
            until = now + timedelta(days=_tier_days())
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"elite.active": True, "elite.active_until": until, "elite.forced": False}},
            )
            return True, "Promovido a ELITE"
        return False, "Ya ELITE"

    return False, "No aplica"


async def ensure_titan_by_premium_redeems(telegram_id: int) -> Tuple[bool, str]:
    """
    Titan automático si el usuario alcanza X canjes Premium (acumulado).
    """
    db = get_db()
    await refresh_tiers(telegram_id)

    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"titan": 1, "status": 1},
    )
    if not user:
        return False, "Usuario no encontrado."
    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "Usuario baneado."

    count = int(((user.get("titan") or {}).get("premium_redeems_count")) or 0)
    need = titan_premium_redeems_required()

    if count >= need and not bool(((user.get("titan") or {}).get("active"))):
        now = datetime.utcnow()
        until = now + timedelta(days=_tier_days())
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"titan.active": True, "titan.active_until": until, "titan.forced": False}},
        )
        return True, "Titan por Premium redeems"
    return False, "No aplica"


# =========================
#  ADMIN: FORZAR TIER
# =========================

def _valid_days(days: int) -> int:
    # Solo permitimos 7/15/30 por simplicidad del panel
    if days in (7, 15, 30):
        return days
    return 30


async def admin_set_elite(telegram_id: int, admin_id: int, days: int = 30, note: str = "") -> Tuple[bool, str]:
    db = get_db()
    await refresh_tiers(telegram_id)

    user = await db.users.find_one({"telegram_id": telegram_id}, {"status": 1})
    if not user:
        return False, "Usuario no encontrado."
    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "Usuario baneado."

    now = datetime.utcnow()
    until = now + timedelta(days=_valid_days(days))

    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "elite.active": True,
                "elite.active_until": until,
                "elite.forced": True,
                "elite.forced_by_admin_id": admin_id,
                "elite.forced_note": note or "Forzado por admin",
            }
        },
    )
    return True, f"🏆 Elite activado por {days} días (hasta {until.strftime('%Y-%m-%d %H:%M UTC')})."


async def admin_set_titan(telegram_id: int, admin_id: int, days: int = 30, note: str = "") -> Tuple[bool, str]:
    db = get_db()
    await refresh_tiers(telegram_id)

    user = await db.users.find_one({"telegram_id": telegram_id}, {"status": 1})
    if not user:
        return False, "Usuario no encontrado."
    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "Usuario baneado."

    now = datetime.utcnow()
    until = now + timedelta(days=_valid_days(days))

    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "titan.active": True,
                "titan.active_until": until,
                "titan.forced": True,
                "titan.forced_by_admin_id": admin_id,
                "titan.forced_note": note or "Forzado por admin",
            }
        },
    )
    return True, f"💎 Titan activado por {days} días (hasta {until.strftime('%Y-%m-%d %H:%M UTC')})."


async def admin_unset_elite(telegram_id: int, admin_id: int) -> Tuple[bool, str]:
    db = get_db()
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "elite.active": False,
                "elite.active_until": None,
                "elite.forced": True,
                "elite.forced_by_admin_id": admin_id,
                "elite.forced_note": "Elite removido por admin",
            }
        },
    )
    return True, "🏆 Elite removido."


async def admin_unset_titan(telegram_id: int, admin_id: int) -> Tuple[bool, str]:
    db = get_db()
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "titan.active": False,
                "titan.active_until": None,
                "titan.forced": True,
                "titan.forced_by_admin_id": admin_id,
                "titan.forced_note": "Titan removido por admin",
            }
        },
    )
    return True, "💎 Titan removido."
