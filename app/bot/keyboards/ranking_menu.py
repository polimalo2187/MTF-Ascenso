from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ranking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Actualizar", callback_data="rank:home")],
            [InlineKeyboardButton(text="⬅️ Volver", callback_data="menu:home")],
        ]
    )
