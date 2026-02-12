from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def tasks_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Check-in diario (+2)", callback_data="tasks:checkin"),
            ],
            [
                InlineKeyboardButton(text="🎓 Mini lección (+3)", callback_data="tasks:lesson"),
            ],
            [
                InlineKeyboardButton(text="📤 Compartir publicación (+6)", callback_data="tasks:share"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Volver", callback_data="menu:home"),
            ],
        ]
    )


def share_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Copiar texto", callback_data="tasks:share_text")],
            [InlineKeyboardButton(text="⬅️ Volver a Tareas", callback_data="tasks:home")],
        ]
    )
