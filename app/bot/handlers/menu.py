from __future__ import annotations

import os
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.db.connection import get_db
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.keyboards.tasks_menu import tasks_menu_kb


router = Router()


def _fmt_dt(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M UTC")


@router.callback_query(F.data.startswith("menu:"))
async def menu_router(callback: CallbackQuery):
    db = get_db()
    telegram_id = callback.from_user.id

    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"last_seen_at": datetime.utcnow()}},
        upsert=True,
    )

    action = callback.data.split(":", 1)[1]

    if action == "points":
        user = await db.users.find_one(
            {"telegram_id": telegram_id},
            {
                "points": 1,
                "ascenso_plan": 1,
                "elite": 1,
                "titan": 1,
                "rank": 1,
                "status": 1,
            },
        )

        if not user:
            await callback.answer("Usuario no encontrado. Escribe /start.", show_alert=True)
            return

        state = (user.get("status") or {}).get("state", "active")
        if state == "blocked":
            blocked_until = (user.get("status") or {}).get("blocked_until")
            await callback.answer(
                f"⛔ Estás bloqueado hasta: {_fmt_dt(blocked_until)}",
                show_alert=True,
            )
            return
        if state == "banned":
            await callback.answer("🚫 Estás expulsado del sistema.", show_alert=True)
            return

        balance = int(((user.get("points") or {}).get("balance_cached")) or 0)
        lifetime_earned = int(((user.get("points") or {}).get("lifetime_earned")) or 0)
        lifetime_spent = int(((user.get("points") or {}).get("lifetime_spent")) or 0)

        plan_type = ((user.get("ascenso_plan") or {}).get("type")) or "FREE"
        plan_exp = (user.get("ascenso_plan") or {}).get("expires_at")

        elite_active = bool(((user.get("elite") or {}).get("active")) or False)
        elite_until = (user.get("elite") or {}).get("active_until")

        titan_active = bool(((user.get("titan") or {}).get("active")) or False)
        titan_until = (user.get("titan") or {}).get("active_until")

        month_key = ((user.get("rank") or {}).get("month_key")) or datetime.utcnow().strftime("%Y-%m")
        earned_month = int(((user.get("rank") or {}).get("earned_this_month")) or 0)

        level_badge = "FREE"
        if titan_active:
            level_badge = "💎 TITAN"
        elif elite_active:
            level_badge = "🏆 ELITE"

        text = (
            "🎯 <b>Mis Puntos</b>\n\n"
            f"• Saldo: <b>{balance}</b> pts\n"
            f"• Ganado total: <b>{lifetime_earned}</b> pts\n"
            f"• Gastado total: <b>{lifetime_spent}</b> pts\n\n"
            f"🏷️ Plan en Ascenso: <b>{plan_type}</b>\n"
            f"⏳ Vence: <b>{_fmt_dt(plan_exp)}</b>\n\n"
            f"⭐ Nivel: <b>{level_badge}</b>\n"
        )

        if elite_active and not titan_active:
            text += f"🏆 Elite hasta: <b>{_fmt_dt(elite_until)}</b>\n"
        if titan_active:
            text += f"💎 Titan hasta: <b>{_fmt_dt(titan_until)}</b>\n"

        text += (
            "\n"
            f"📊 Ranking {month_key}:\n"
            f"• Puntos ganados este mes: <b>{earned_month}</b>\n"
        )

        await callback.message.edit_text(text, reply_markup=main_menu_kb())
        await callback.answer()
        return

    if action == "tasks":
        await callback.message.edit_text(
            "✅ <b>Centro de Tareas</b>\n\n"
            "Selecciona una opción:",
            reply_markup=tasks_menu_kb(),
        )
        await callback.answer()
        return

    if action == "redeem":
        await callback.message.edit_text(
            "🛒 <b>Canjear plan</b>\n\n"
            "Cuando tengas los puntos necesarios, envía una solicitud al admin.\n"
            "El admin activará Plus/Premium y el sistema descontará tus puntos.",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    if action == "policy":
        await callback.message.edit_text(
            "📜 <b>Políticas</b>\n\n"
            "1️⃣ Los puntos no tienen valor monetario.\n"
            "2️⃣ Solo pueden usarse para activar planes internos.\n"
            "3️⃣ Prohibido cuentas múltiples.\n"
            "4️⃣ Prohibido manipular capturas.\n"
            "5️⃣ Prohibido explotar errores.\n\n"
            "⚖ Penalizaciones:\n"
            "• 1ra: eliminación de puntos + advertencia\n"
            "• 2da: bloqueo temporal\n"
            "• 3ra: expulsión definitiva\n",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    if action == "admin":
        whatsapp_url = os.getenv("ADMIN_WHATSAPP_URL", "").strip()
        if not whatsapp_url:
            await callback.answer("Admin WhatsApp no configurado.", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📲 Abrir WhatsApp", url=whatsapp_url)],
                [InlineKeyboardButton(text="⬅️ Volver", callback_data="menu:home")],
            ]
        )

        await callback.message.edit_text(
            "📲 <b>Contactar Admin</b>\n\n"
            "Usa este enlace para solicitar activación o soporte:",
            reply_markup=kb,
        )
        await callback.answer()
        return

    if action == "home":
        await callback.message.edit_text(
            "🏠 <b>MTF Ascenso</b>\n\n"
            "Selecciona una opción:",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    await callback.answer("Opción no disponible.", show_alert=True)
