from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def winners_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Actualizar", callback_data="wins:home")],
            [InlineKeyboardButton(text="⬅️ Volver", callback_data="menu:home")],
        ]
    )
