from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Pendientes (Compartir)", callback_data="admin:pending:0")],
            [InlineKeyboardButton(text="🛒 Activar Plan (por ID)", callback_data="admin:redeem_help")],
        ]
    )


def admin_pending_list_kb(page: int, has_more: bool) -> InlineKeyboardMarkup:
    buttons = []

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"admin:pending:{page-1}"))
    if has_more:
        nav_row.append(InlineKeyboardButton(text="➡️ Siguiente", callback_data=f"admin:pending:{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🏠 Admin Home", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_claim_actions_kb(claim_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Aprobar", callback_data=f"admin:approve:{claim_id}"),
                InlineKeyboardButton(text="🚫 Rechazar", callback_data=f"admin:reject:{claim_id}"),
            ],
            [InlineKeyboardButton(text="⬅️ Volver", callback_data="admin:pending:0")],
        ]
    )


def admin_user_actions_kb(user_telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🥈 Activar PLUS (250)", callback_data=f"admin:actplus:{user_telegram_id}"),
                InlineKeyboardButton(text="🥇 Activar PREMIUM (400)", callback_data=f"admin:actprem:{user_telegram_id}"),
            ],
            [InlineKeyboardButton(text="🏠 Admin Home", callback_data="admin:home")],
        ]
    )
