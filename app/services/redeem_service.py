from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

from app.db.connection import get_db
from app.services.ledger_service import (
    create_points_entry,
    ensure_user_has_points,
    TYPE_SPEND,
    TYPE_BONUS,
    CAT_REDEEM,
    CAT_BONUS,
)

COST_PLUS = 250
COST_PREMIUM = 400

REASON_REDEEM_PLUS = "REDEEM_PLUS"
REASON_REDEEM_PREMIUM = "REDEEM_PREMIUM"
REASON_BONUS_FIRST = "BONUS_FIRST_REDEEM"

BONUS_FIRST_POINTS = 20


def _expires_in_30_days(now: datetime) -> datetime:
    return now + timedelta(days=30)


async def _user_exists(telegram_id: int) -> bool:
    db = get_db()
    u = await db.users.find_one({"telegram_id": telegram_id}, {"_id": 1})
    return bool(u)


async def _has_any_redeem(telegram_id: int) -> bool:
    """
    Detecta si el usuario ya canjeó antes (Plus o Premium) vía puntos.
    """
    db = get_db()
    return bool(
        await db.ledger.find_one(
            {
                "telegram_id": telegram_id,
                "reason_code": {"$in": [REASON_REDEEM_PLUS, REASON_REDEEM_PREMIUM]},
            },
            {"_id": 1},
        )
    )


async def _has_first_bonus(telegram_id: int) -> bool:
    db = get_db()
    return bool(
        await db.ledger.find_one(
            {"telegram_id": telegram_id, "reason_code": REASON_BONUS_FIRST},
            {"_id": 1},
        )
    )


async def activate_plus_by_points(user_telegram_id: int, admin_id: int) -> Tuple[bool, str]:
    return await _redeem_plan(
        user_telegram_id=user_telegram_id,
        admin_id=admin_id,
        plan_type="PLUS",
        cost=COST_PLUS,
        reason_code=REASON_REDEEM_PLUS,
    )


async def activate_premium_by_points(user_telegram_id: int, admin_id: int) -> Tuple[bool, str]:
    return await _redeem_plan(
        user_telegram_id=user_telegram_id,
        admin_id=admin_id,
        plan_type="PREMIUM",
        cost=COST_PREMIUM,
        reason_code=REASON_REDEEM_PREMIUM,
    )


async def _redeem_plan(
    user_telegram_id: int,
    admin_id: int,
    plan_type: str,
    cost: int,
    reason_code: str,
) -> Tuple[bool, str]:
    db = get_db()

    if not await _user_exists(user_telegram_id):
        return False, "Usuario no encontrado."

    # Validación de saldo (usa cache)
    if not await ensure_user_has_points(user_telegram_id, cost):
        return False, "Saldo insuficiente o usuario bloqueado/expulsado."

    now = datetime.utcnow()
    expires_at = _expires_in_30_days(now)

    # 1) Descontar puntos (ledger SPEND)
    await create_points_entry(
        telegram_id=user_telegram_id,
        entry_type=TYPE_SPEND,
        category=CAT_REDEEM,
        reason_code=reason_code,
        points=cost,
        meta={"admin_id": admin_id, "plan_type": plan_type, "expires_at": expires_at.isoformat()},
    )

    # 2) Activar plan en Ascenso (30 días)
    await db.users.update_one(
        {"telegram_id": user_telegram_id},
        {
            "$set": {
                "ascenso_plan.type": plan_type,
                "ascenso_plan.expires_at": expires_at,
                "last_seen_at": now,
            }
        },
    )

    # 3) Bonus primer logro (+20) SOLO la primera vez que canjea (Plus o Premium)
    already_redeemed = await _has_any_redeem(user_telegram_id)
    already_bonus = await _has_first_bonus(user_telegram_id)

    # OJO: como acabamos de crear el canje, _has_any_redeem dará True.
    # Por eso la lógica correcta es:
    # - Si NO existía bonus y el usuario NO tenía canjes antes del actual, entonces bono.
    # Solución: verificamos "tenía canje antes" buscando uno anterior al momento actual.
    had_redeem_before = bool(
        await db.ledger.find_one(
            {
                "telegram_id": user_telegram_id,
                "reason_code": {"$in": [REASON_REDEEM_PLUS, REASON_REDEEM_PREMIUM]},
                "created_at": {"$lt": now},
            },
            {"_id": 1},
        )
    )

    if (not had_redeem_before) and (not already_bonus):
        await create_points_entry(
            telegram_id=user_telegram_id,
            entry_type=TYPE_BONUS,
            category=CAT_BONUS,
            reason_code=REASON_BONUS_FIRST,
            points=BONUS_FIRST_POINTS,
            meta={"admin_id": admin_id, "note": "Bono primer logro"},
        )

    return True, f"✅ Plan {plan_type} activado (30 días) y descontados {cost} pts."
