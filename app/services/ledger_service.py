from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.db.connection import get_db
from app.db.models.ledger_model import create_ledger_entry, get_ledger_entry_by_entry_id


# Tipos permitidos
TYPE_EARN = "EARN"        # gana puntos por tareas
TYPE_BONUS = "BONUS"      # bonus (primer logro, bonus mensual)
TYPE_ADJUST = "ADJUST"    # ajuste manual (+) o (-) por admin (usaremos signed_points)
TYPE_SPEND = "SPEND"      # gasta puntos (canje)
TYPE_PENALTY = "PENALTY"  # penalización (quita puntos)

# Categorías sugeridas
CAT_TASK = "TASK"
CAT_REDEEM = "REDEEM"
CAT_BONUS = "BONUS"
CAT_SECURITY = "SECURITY"
CAT_ADMIN = "ADMIN"


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _make_entry_id(dt: datetime) -> str:
    # Ejemplo: LED-20260212-A1B2C3
    ymd = dt.strftime("%Y%m%d")
    token = secrets.token_hex(3).upper()  # 6 chars
    return f"LED-{ymd}-{token}"


def _compute_signed_and_month_earned(entry_type: str, points: int) -> Tuple[int, int]:
    """
    signed_points: afecta el balance total
    month_earned_points: solo suma para ranking mensual (ganancias), nunca resta
    """
    if points <= 0:
        raise ValueError("points must be > 0")

    if entry_type in (TYPE_EARN, TYPE_BONUS):
        return points, points
    if entry_type in (TYPE_SPEND, TYPE_PENALTY):
        return -points, 0
    if entry_type == TYPE_ADJUST:
        # Para ADJUST, se decide por meta.signed (True) o meta.delta (negativo/positivo).
        # En esta V1, ADJUST debe venir con meta.delta_signed (int).
        # month_earned_points solo suma si delta_signed > 0
        raise ValueError("TYPE_ADJUST requires meta.delta_signed; use create_adjust()")
    raise ValueError(f"Unknown entry_type: {entry_type}")


async def _update_user_points_cache(
    telegram_id: int,
    signed_delta: int,
    month_earned_delta: int,
    now: datetime,
) -> None:
    """
    Actualiza cache del usuario (balance_cached + lifetime + earned_this_month).
    Maneja rollover mensual: si cambia month_key, reinicia earned_this_month a 0 antes de sumar.
    """
    db = get_db()
    mk = _month_key(now)

    user = await db.users.find_one({"telegram_id": telegram_id}, {"rank": 1, "points": 1})
    if not user:
        # Si no existe usuario, no deberíamos llegar aquí (porque /start crea user).
        # Pero por seguridad, lo creamos mínimo.
        await db.users.insert_one(
            {
                "telegram_id": telegram_id,
                "created_at": now,
                "policy": {"accepted": False, "accepted_at": None, "version": "1.0"},
                "status": {"state": "active", "blocked_until": None, "ban_reason": None},
                "infractions": {"count": 0, "last_at": None},
                "points": {
                    "balance_cached": 0,
                    "lifetime_earned": 0,
                    "lifetime_spent": 0,
                    "updated_at": now,
                },
                "rank": {"month_key": mk, "earned_this_month": 0},
                "ascenso_plan": {"type": "FREE", "expires_at": None},
                "elite": {"active": False, "active_until": None},
                "titan": {"active": False, "active_until": None, "premium_redeems_count": 0},
                "admin": {"notes": ""},
            }
        )
        current_month_key = mk
    else:
        current_month_key = (user.get("rank") or {}).get("month_key") or mk

    # Si cambió el mes, reseteamos earned_this_month.
    reset_rank = current_month_key != mk

    update_doc: Dict[str, Any] = {
        "$inc": {
            "points.balance_cached": signed_delta,
            "points.lifetime_earned": max(0, signed_delta),
            "points.lifetime_spent": max(0, -signed_delta),
        },
        "$set": {
            "points.updated_at": now,
            "last_seen_at": now,
        },
    }

    if reset_rank:
        update_doc["$set"]["rank.month_key"] = mk
        update_doc["$set"]["rank.earned_this_month"] = 0

    if month_earned_delta > 0:
        update_doc.setdefault("$inc", {})
        update_doc["$inc"]["rank.earned_this_month"] = month_earned_delta

    await db.users.update_one({"telegram_id": telegram_id}, update_doc)


async def create_points_entry(
    telegram_id: int,
    entry_type: str,
    category: str,
    reason_code: str,
    points: int,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Crea un movimiento estándar (EARN/BONUS/SPEND/PENALTY).
    - Inserta en ledger
    - Actualiza balance_cached y earned_this_month
    Retorna entry_id.
    """
    now = datetime.utcnow()
    entry_id = _make_entry_id(now)

    # Evita duplicados por entry_id (muy raro, pero por seguridad)
    existing = await get_ledger_entry_by_entry_id(entry_id)
    if existing:
        # si colisiona, generamos otro
        entry_id = _make_entry_id(now)

    signed_points, month_earned_points = _compute_signed_and_month_earned(entry_type, points)

    entry = {
        "entry_id": entry_id,
        "telegram_id": telegram_id,
        "type": entry_type,
        "category": category,
        "reason_code": reason_code,
        "points": int(points),
        "signed_points": int(signed_points),
        "month_earned_points": int(month_earned_points),
        "meta": meta or {},
        "month_key": _month_key(now),
        "created_at": now,
    }

    # Inserta ledger y actualiza cache (orden importante: ledger primero, luego cache)
    await create_ledger_entry(entry)
    await _update_user_points_cache(
        telegram_id=telegram_id,
        signed_delta=signed_points,
        month_earned_delta=month_earned_points,
        now=now,
    )
    return entry_id


async def create_adjust(
    telegram_id: int,
    delta_signed: int,
    reason_code: str,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Ajuste manual por admin (+ o -). delta_signed puede ser positivo o negativo.
    Para ranking mensual, solo suma si es positivo.
    """
    if delta_signed == 0:
        raise ValueError("delta_signed cannot be 0")

    now = datetime.utcnow()
    entry_id = _make_entry_id(now)

    month_earned = delta_signed if delta_signed > 0 else 0

    entry = {
        "entry_id": entry_id,
        "telegram_id": telegram_id,
        "type": TYPE_ADJUST,
        "category": CAT_ADMIN,
        "reason_code": reason_code,
        "points": abs(int(delta_signed)),
        "signed_points": int(delta_signed),
        "month_earned_points": int(month_earned),
        "meta": {**(meta or {}), "delta_signed": int(delta_signed)},
        "month_key": _month_key(now),
        "created_at": now,
    }

    await create_ledger_entry(entry)
    await _update_user_points_cache(
        telegram_id=telegram_id,
        signed_delta=int(delta_signed),
        month_earned_delta=int(month_earned),
        now=now,
    )
    return entry_id


async def ensure_user_has_points(telegram_id: int, cost_points: int) -> bool:
    """
    Verifica si el usuario tiene saldo suficiente (usa balance_cached).
    """
    db = get_db()
    user = await db.users.find_one({"telegram_id": telegram_id}, {"points.balance_cached": 1, "status": 1})
    if not user:
        return False

    state = (user.get("status") or {}).get("state", "active")
    if state in ("blocked", "banned"):
        return False

    bal = int(((user.get("points") or {}).get("balance_cached")) or 0)
    return bal >= int(cost_points)
