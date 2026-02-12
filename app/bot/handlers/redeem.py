from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.bot.keyboards.redeem_menu import redeem_menu_kb
from app.services.redeem_request_service import build_redeem_request_text, get_admin_whatsapp_url

router = Router()


@router.callback_query(F.data == "redeem:home")
async def redeem_home(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛒 <b>Canjear plan</b>\n\n"
        "Costos:\n"
        "• 🥈 PLUS: <b>250</b> pts\n"
        "• 🥇 PREMIUM: <b>400</b> pts\n\n"
        "Selecciona el plan que deseas solicitar al admin.",
        reply_markup=redeem_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("redeem:req:"))
async def redeem_request(callback: CallbackQuery):
    plan = callback.data.split("redeem:req:", 1)[1].strip().upper()
    ok, text = await build_redeem_request_text(callback.from_user.id, plan)

    if not ok:
        await callback.answer(text, show_alert=True)
        return

    await callback.message.edit_text(
        "📲 <b>Solicitud lista</b>\n\n"
        "Copia y pega este mensaje al admin por WhatsApp:\n\n"
        f"<code>{text}</code>\n\n"
        "Luego el admin activará el plan y se descontarán los puntos automáticamente.",
        reply_markup=redeem_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "redeem:whatsapp")
async def redeem_open_whatsapp(callback: CallbackQuery):
    url = get_admin_whatsapp_url()
    if not url:
        await callback.answer("WhatsApp del admin no está configurado.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Abrir WhatsApp", url=url)],
            [InlineKeyboardButton(text="⬅️ Volver", callback_data="redeem:home")],
        ]
    )

    await callback.message.edit_text(
        "📲 <b>WhatsApp del Admin</b>\n\n"
        "Abre el enlace y envía tu solicitud:",
        reply_markup=kb,
    )
    await callback.answer()
