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


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _extend_from(until, now: datetime, days: int) -> datetime:
    """
    Extiende desde el vencimiento actual si aún está en el futuro.
    Si ya venció o no existe, extiende desde ahora.
    """
    if until and isinstance(until, datetime) and until > now:
        return until + timedelta(days=days)
    return now + timedelta(days=days)


async def refresh_tiers(telegram_id: int) -> None:
    """
    1) Apaga Elite/Titan si ya expiraron.
    2) Si expiraron y el usuario sigue cumpliendo umbral del MES actual,
       se reactivan automáticamente al instante (encadenado).
    """
    db = get_db()
    now = datetime.utcnow()
    mk = _month_key(now)

    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"elite": 1, "titan": 1, "rank": 1, "status": 1},
    )
    if not user:
        return

    state = ((user.get("status") or {}).get("state")) or "active"
    if state == "banned":
        return

    elite = user.get("elite") or {}
    titan = user.get("titan") or {}
    rank = user.get("rank") or {}

    updates = {}

    # 1) Expiración: si venció, apagar
    elite_expired = False
    if bool(elite.get("active")):
        until = elite.get("active_until")
        if until and isinstance(until, datetime) and until <= now:
            elite_expired = True
            updates["elite.active"] = False
            updates["elite.active_until"] = None
            updates["elite.forced"] = False
            updates["elite.forced_by_admin_id"] = None
            updates["elite.forced_note"] = None

    titan_expired = False
    if bool(titan.get("active")):
        until = titan.get("active_until")
        if until and isinstance(until, datetime) and until <= now:
            titan_expired = True
            updates["titan.active"] = False
            updates["titan.active_until"] = None
            updates["titan.forced"] = False
            updates["titan.forced_by_admin_id"] = None
            updates["titan.forced_note"] = None

    if updates:
        await db.users.update_one({"telegram_id": telegram_id}, {"$set": updates})

    # 2) Reactivación automática "encadenada" si expiró y sigue cumpliendo umbral
    user_mk = (rank.get("month_key") or mk)
    earned = int(rank.get("earned_this_month") or 0)

    # Solo aplica si estamos en el mes actual
    if user_mk != mk:
        return

    # Si Titan expiró y sigue en umbral → reactivar Titan 30 días
    if titan_expired and earned >= titan_threshold():
        until = now + timedelta(days=_tier_days())
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"titan.active": True, "titan.active_until": until, "titan.forced": False}},
        )
        return

    # Si Elite expiró y sigue en umbral → reactivar Elite 30 días
    # (si Titan ya aplica, Titan manda)
    if elite_expired and earned >= elite_threshold():
        until = now + timedelta(days=_tier_days())
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"elite.active": True, "elite.active_until": until, "elite.forced": False}},
        )


async def get_multiplier(telegram_id: int) -> float:
    """
    Retorna multiplicador según nivel.
    """
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
    Promoción/renovación automática por puntos del mes:
    - >= TITAN_THRESHOLD:
        - si NO tiene Titan => Titan 30d desde ahora
        - si YA tiene Titan => extiende +30d desde su vencimiento actual (encadenado)
    - >= ELITE_THRESHOLD (si no aplica Titan):
        - si NO tiene Elite => Elite 30d desde ahora
        - si YA tiene Elite => extiende +30d desde su vencimiento actual (encadenado)
    """
    db = get_db()
    await refresh_tiers(telegram_id)

    now = datetime.utcnow()
    mk = _month_key(now)

    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"rank": 1, "elite": 1, "titan": 1, "status": 1},
    )
    if not user:
        return False, "Usuario no encontrado."

    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "Usuario baneado."

    rank = user.get("rank") or {}
    user_mk = (rank.get("month_key") or mk)
    if user_mk != mk:
        return False, "Mes distinto."

    earned = int(rank.get("earned_this_month") or 0)

    # ---- TITAN (manda sobre ELITE) ----
    if earned >= titan_threshold():
        titan = user.get("titan") or {}
        active = bool(titan.get("active"))
        until = titan.get("active_until")

        new_until = _extend_from(until, now, _tier_days())
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"titan.active": True, "titan.active_until": new_until, "titan.forced": False}},
        )

        if active:
            return True, f"TITAN extendido hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"
        return True, f"TITAN activado hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"

    # ---- ELITE ----
    if earned >= elite_threshold():
        # Si por alguna razón Titan está activo, no tocamos Elite
        if bool(((user.get("titan") or {}).get("active"))):
            return False, "Ya TITAN"

        elite = user.get("elite") or {}
        active = bool(elite.get("active"))
        until = elite.get("active_until")

        new_until = _extend_from(until, now, _tier_days())
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"elite.active": True, "elite.active_until": new_until, "elite.forced": False}},
        )

        if active:
            return True, f"ELITE extendido hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"
        return True, f"ELITE activado hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"

    return False, "No aplica"


async def ensure_titan_by_premium_redeems(telegram_id: int) -> Tuple[bool, str]:
    """
    Titan automático si el usuario alcanza X canjes Premium (acumulado).
    - Si ya es Titan => extiende +30d desde vencimiento (encadenado)
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

    titan = user.get("titan") or {}
    count = int(titan.get("premium_redeems_count") or 0)
    need = titan_premium_redeems_required()

    if count < need:
        return False, "No aplica"

    now = datetime.utcnow()
    active = bool(titan.get("active"))
    until = titan.get("active_until")
    new_until = _extend_from(until, now, _tier_days())

    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"titan.active": True, "titan.active_until": new_until, "titan.forced": False}},
    )

    if active:
        return True, f"Titan extendido por Premium hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"
    return True, f"Titan activado por Premium hasta {new_until.strftime('%Y-%m-%d %H:%M UTC')}"



# =========================
#  ADMIN: FORZAR TIER
# =========================

def _valid_days(days: int) -> int:
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
