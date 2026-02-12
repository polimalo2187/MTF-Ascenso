from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Any, Tuple

from app.db.connection import get_db

COST_PLUS = 250
COST_PREMIUM = 400


def _fmt(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M UTC")


async def build_redeem_request_text(telegram_id: int, plan: str) -> Tuple[bool, str]:
    """
    Genera un texto para WhatsApp con ID + saldo + plan solicitado.
    """
    db = get_db()
    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"points": 1, "ascenso_plan": 1},
    )
    if not user:
        return False, "Usuario no encontrado. Escribe /start."

    balance = int(((user.get("points") or {}).get("balance_cached")) or 0)
    current_plan = ((user.get("ascenso_plan") or {}).get("type")) or "FREE"
    expires_at = (user.get("ascenso_plan") or {}).get("expires_at")

    if plan not in ("PLUS", "PREMIUM"):
        return False, "Plan inválido."

    cost = COST_PLUS if plan == "PLUS" else COST_PREMIUM
    ok_text = "SI" if balance >= cost else "NO"

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    text = (
        "📌 SOLICITUD MTF ASCENSO\n"
        "------------------------\n"
        f"🆔 ID Telegram: {telegram_id}\n"
        f"💰 Saldo actual: {balance} pts\n"
        f"🎯 Plan solicitado: {plan} (costo {cost} pts)\n"
        f"✅ Saldo suficiente: {ok_text}\n"
        f"🏷️ Plan actual (Ascenso): {current_plan}\n"
        f"⏳ Vence (Ascenso): {_fmt(expires_at)}\n"
        f"🕒 Fecha: {now}\n"
        "------------------------\n"
        "✅ Envío esta solicitud para activar mi plan.\n"
    )

    return True, text


def get_admin_whatsapp_url() -> str:
    return os.getenv("ADMIN_WHATSAPP_URL", "").strip()
