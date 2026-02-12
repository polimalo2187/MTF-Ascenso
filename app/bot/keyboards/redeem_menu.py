from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def redeem_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🥈 Solicitar PLUS", callback_data="redeem:req:PLUS"),
                InlineKeyboardButton(text="🥇 Solicitar PREMIUM", callback_data="redeem:req:PREMIUM"),
            ],
            [
                InlineKeyboardButton(text="📲 Abrir WhatsApp Admin", callback_data="redeem:whatsapp"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Volver", callback_data="menu:home"),
            ],
        ]
    )
