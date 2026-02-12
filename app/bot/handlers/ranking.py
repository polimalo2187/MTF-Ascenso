from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.services.ranking_service import build_ranking_text
from app.bot.keyboards.ranking_menu import ranking_kb

router = Router()


@router.callback_query(F.data == "rank:home")
async def ranking_home(callback: CallbackQuery):
    text = await build_ranking_text(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=ranking_kb())
    await callback.answer()
