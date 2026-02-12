from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from datetime import datetime

from app.services.admin_service import is_admin
from app.services.winners_service import (
    build_winners_public_text,
    build_winners_admin_text,
    upsert_winner,
    clear_winners,
)

router = Router()


@router.callback_query(F.data == "wins:home")
async def winners_home(callback: CallbackQuery):
    text = await build_winners_public_text()
    from app.bot.keyboards.winners_menu import winners_kb  # import local para evitar ciclos
    await callback.message.edit_text(text, reply_markup=winners_kb())
    await callback.answer()


@router.message(Command("winners"))
async def winners_cmd(message: Message):
    """
    /winners -> público para todos, pero si es admin muestra comandos
    """
    if is_admin(message.from_user.id):
        text = await build_winners_admin_text()
    else:
        text = await build_winners_public_text()
    await message.answer(text)


@router.message(F.text.startswith("/win_"))
async def winners_set_cmd(message: Message):
    """
    /win_POS_ID [nota...]
    Ej: /win_1_123456789
        /win_2_123456789 Excelente mes
    Solo admin.
    """
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sin acceso.")
        return

    parts = (message.text or "").strip().split(" ", 1)
    head = parts[0]
    note = parts[1].strip() if len(parts) > 1 else ""

    # head = /win_1_123
    try:
        _, pos_str, id_str = head.split("_", 2)
        pos = int(pos_str)
        user_id = int(id_str)
    except Exception:
        await message.answer(
            "Formato inválido.\n\n"
            "Uso: <code>/win_POS_ID</code>\n"
            "Ej: <code>/win_1_123456789</code>"
        )
        return

    mk = datetime.utcnow().strftime("%Y-%m")
    ok, msg = await upsert_winner(
        month_key=mk,
        position=pos,
        telegram_id=user_id,
        admin_id=message.from_user.id,
        note=note,
    )
    await message.answer(msg)


@router.message(Command("wins_clear"))
async def winners_clear_cmd(message: Message):
    """
    /wins_clear -> borra ganadores del mes actual (solo admin)
    """
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sin acceso.")
        return

    mk = datetime.utcnow().strftime("%Y-%m")
    ok, msg = await clear_winners(month_key=mk, admin_id=message.from_user.id)
    await message.answer(msg)
