from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.db.connection import get_db
from app.db.models.task_claim_model import create_task_claim, find_user_claim_for_day
from app.services.ledger_service import (
    create_points_entry,
    CAT_TASK,
    TYPE_EARN,
)

from app.services.tiers_service import get_multiplier, ensure_auto_tier_by_month_points, refresh_tiers

# ---- Configuración de puntos (V1) ----
PTS_CHECKIN = 2
PTS_LESSON_QUIZ = 3
PTS_SHARE_POST = 6  # (pendiente de aprobación, NO se otorga inmediato)

TASK_CHECKIN = "TASK_DAILY_CHECKIN"
TASK_LESSON = "TASK_LESSON_QUIZ"
TASK_SHARE = "TASK_SHARE_POST"


def day_key_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def weekly_code_utc(dt: datetime) -> str:
    iso_year, iso_week, _ = dt.isocalendar()
    return f"ASC-{iso_year}{iso_week:02d}"


def share_post_text(telegram_id: int) -> str:
    now = datetime.utcnow()
    code = weekly_code_utc(now)

    bot_signals_url = os.getenv("SIGNALS_BOT_URL", "").strip()
    if not bot_signals_url:
        bot_signals_url = "https://t.me/MTFSignsls_bot"

    referral_url = f"{bot_signals_url}?start=ref_{telegram_id}"

    return (
        "🚀 Estoy usando el bot de señales y está durísimo.\n\n"
        f"✅ Únete aquí: {referral_url}\n\n"
        "💡 Tip: Empieza en Free y asciende a Plus/Premium.\n"
        f"🔐 Código semanal: {code}"
    )


async def _ensure_user_ok(telegram_id: int) -> Tuple[bool, str]:
    db = get_db()
    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"policy": 1, "status": 1},
    )
    if not user:
        return False, "Usuario no encontrado. Escribe /start."

    if not ((user.get("policy") or {}).get("accepted")):
        return False, "Debes aceptar las políticas primero. Usa /policy y /accept."

    # refresca tiers para apagar expirados
    await refresh_tiers(telegram_id)

    state = (user.get("status") or {}).get("state", "active")
    if state == "blocked":
        return False, "⛔ Estás bloqueado temporalmente."
    if state == "banned":
        return False, "🚫 Estás expulsado del sistema."

    return True, "OK"


def _apply_multiplier(base_points: int, mult: float) -> int:
    # Redondeo hacia arriba “justo” para motivar
    # Ej: 2 * 1.2 = 2.4 => 3
    v = int((base_points * mult) + 0.999999)
    return max(1, v)


async def claim_daily_checkin(telegram_id: int) -> Tuple[bool, str]:
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    dk = day_key_utc(now)

    existing = await find_user_claim_for_day(telegram_id, TASK_CHECKIN, dk)
    if existing:
        return False, "✅ Ya reclamaste tu check-in de hoy."

    mult = await get_multiplier(telegram_id)
    pts = _apply_multiplier(PTS_CHECKIN, mult)

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_CHECKIN,
        "points": pts,
        "status": "approved",
        "day_key": dk,
        "created_at": now,
        "approved_at": now,
        "meta": {"mult": mult, "base": PTS_CHECKIN},
    }
    await create_task_claim(claim_doc)

    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_CHECKIN,
        points=pts,
        meta={"day_key": dk, "mult": mult, "base": PTS_CHECKIN},
    )

    # Evaluar ascenso automático por puntos del mes
    await ensure_auto_tier_by_month_points(telegram_id)

    return True, f"✅ Check-in reclamado: +{pts} puntos. (x{mult})"


async def award_lesson_quiz(telegram_id: int) -> Tuple[bool, str]:
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    dk = day_key_utc(now)

    existing = await find_user_claim_for_day(telegram_id, TASK_LESSON, dk)
    if existing:
        return False, "✅ Ya completaste la mini lección de hoy."

    mult = await get_multiplier(telegram_id)
    pts = _apply_multiplier(PTS_LESSON_QUIZ, mult)

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_LESSON,
        "points": pts,
        "status": "approved",
        "day_key": dk,
        "created_at": now,
        "approved_at": now,
        "meta": {"quiz": "v1", "mult": mult, "base": PTS_LESSON_QUIZ},
    }
    await create_task_claim(claim_doc)

    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_LESSON,
        points=pts,
        meta={"day_key": dk, "quiz": "v1", "mult": mult, "base": PTS_LESSON_QUIZ},
    )

    await ensure_auto_tier_by_month_points(telegram_id)

    return True, f"✅ Lección completada: +{pts} puntos. (x{mult})"


async def submit_share_post_evidence(
    telegram_id: int,
    photo_file_id: str,
    caption: Optional[str],
) -> Tuple[bool, str]:
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    code = weekly_code_utc(now)

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_SHARE,
        "points": PTS_SHARE_POST,  # base guardado, multiplicador se aplica al aprobar
        "status": "pending",
        "day_key": None,
        "created_at": now,
        "approved_at": None,
        "meta": {
            "weekly_code": code,
            "photo_file_id": photo_file_id,
            "caption": caption or "",
            "base": PTS_SHARE_POST,
        },
    }
    await create_task_claim(claim_doc)

    return True, (
        "✅ Evidencia enviada.\n\n"
        "⏳ Estado: <b>PENDIENTE</b>\n"
        "Cuando el admin la apruebe se acreditarán los puntos."
  )
