from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Mis puntos", callback_data="menu:points"),
                InlineKeyboardButton(text="✅ Tareas", callback_data="menu:tasks"),
            ],
            [
                InlineKeyboardButton(text="📈 Ranking del mes", callback_data="rank:home"),
                InlineKeyboardButton(text="🏆 Ganadores", callback_data="wins:home"),
            ],
            [
                InlineKeyboardButton(text="🛒 Canjear plan", callback_data="menu:redeem"),
            ],
            [
                InlineKeyboardButton(text="📜 Políticas", callback_data="menu:policy"),
                InlineKeyboardButton(text="📲 Admin (WhatsApp)", callback_data="menu:admin"),
            ],
        ]
    )
