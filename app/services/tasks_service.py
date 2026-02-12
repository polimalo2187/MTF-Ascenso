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
    # Código semanal: ASC-YYYYWW (semana ISO)
    iso_year, iso_week, _ = dt.isocalendar()
    return f"ASC-{iso_year}{iso_week:02d}"


def share_post_text(telegram_id: int) -> str:
    """
    Texto oficial a compartir. Incluye referencia simple (telegram_id).
    Si luego quieres usar un deep-link real, lo cambias aquí.
    """
    now = datetime.utcnow()
    code = weekly_code_utc(now)

    bot_signals_url = os.getenv("SIGNALS_BOT_URL", "").strip()
    if not bot_signals_url:
        bot_signals_url = "https://t.me/MTFSignsls_bot"

    # Si quieres forzar tu start=ref_ID, puedes construirlo aquí:
    # referral_url = f"{bot_signals_url}?start=ref_{telegram_id}"
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

    state = (user.get("status") or {}).get("state", "active")
    if state == "blocked":
        return False, "⛔ Estás bloqueado temporalmente."
    if state == "banned":
        return False, "🚫 Estás expulsado del sistema."

    return True, "OK"


async def claim_daily_checkin(telegram_id: int) -> Tuple[bool, str]:
    """
    Reclamo de check-in diario (+2). Solo 1 vez por día (UTC).
    """
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    dk = day_key_utc(now)

    existing = await find_user_claim_for_day(telegram_id, TASK_CHECKIN, dk)
    if existing:
        return False, "✅ Ya reclamaste tu check-in de hoy."

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_CHECKIN,
        "points": PTS_CHECKIN,
        "status": "approved",  # check-in se aprueba automático
        "day_key": dk,
        "created_at": now,
        "approved_at": now,
        "meta": {},
    }
    await create_task_claim(claim_doc)

    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_CHECKIN,
        points=PTS_CHECKIN,
        meta={"day_key": dk},
    )

    return True, f"✅ Check-in reclamado: +{PTS_CHECKIN} puntos."


async def award_lesson_quiz(telegram_id: int) -> Tuple[bool, str]:
    """
    Otorga puntos por completar mini lección + quiz (+3). 1 vez por día (UTC).
    """
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    dk = day_key_utc(now)

    existing = await find_user_claim_for_day(telegram_id, TASK_LESSON, dk)
    if existing:
        return False, "✅ Ya completaste la mini lección de hoy."

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_LESSON,
        "points": PTS_LESSON_QUIZ,
        "status": "approved",
        "day_key": dk,
        "created_at": now,
        "approved_at": now,
        "meta": {"quiz": "v1"},
    }
    await create_task_claim(claim_doc)

    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_LESSON,
        points=PTS_LESSON_QUIZ,
        meta={"day_key": dk, "quiz": "v1"},
    )

    return True, f"✅ Lección completada: +{PTS_LESSON_QUIZ} puntos."


async def submit_share_post_evidence(
    telegram_id: int,
    photo_file_id: str,
    caption: Optional[str],
) -> Tuple[bool, str]:
    """
    Crea un claim pendiente por compartir publicación (+6).
    No otorga puntos hasta aprobación admin (Paso 3).
    """
    ok, msg = await _ensure_user_ok(telegram_id)
    if not ok:
        return False, msg

    now = datetime.utcnow()
    code = weekly_code_utc(now)

    claim_doc: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "task_code": TASK_SHARE,
        "points": PTS_SHARE_POST,
        "status": "pending",
        "day_key": None,
        "created_at": now,
        "approved_at": None,
        "meta": {
            "weekly_code": code,
            "photo_file_id": photo_file_id,
            "caption": caption or "",
        },
    }
    await create_task_claim(claim_doc)

    return True, (
        "✅ Evidencia enviada.\n\n"
        "⏳ Estado: <b>PENDIENTE</b>\n"
        "Cuando el admin la apruebe se acreditarán los puntos."
  )
