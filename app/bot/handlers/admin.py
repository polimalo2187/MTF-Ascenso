from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.services.admin_service import (
    is_admin,
    get_pending_claims,
    approve_share_claim,
    reject_share_claim,
)
from app.services.redeem_service import (
    activate_plus_by_points,
    activate_premium_by_points,
)
from app.bot.keyboards.admin_menu import (
    admin_home_kb,
    admin_pending_list_kb,
    admin_claim_actions_kb,
    admin_user_actions_kb,
)

router = Router()

PAGE_SIZE = 5


def _short(s: str, n: int = 60) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ No tienes acceso al panel admin.")
        return

    await message.answer(
        "🛠 <b>Panel Admin</b>\n\n"
        "Selecciona una opción:",
        reply_markup=admin_home_kb(),
    )


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠 <b>Panel Admin</b>\n\n"
        "Selecciona una opción:",
        reply_markup=admin_home_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:redeem_help")
async def admin_redeem_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛒 <b>Activar Plan (Manual)</b>\n\n"
        "Para activar un plan a un usuario:\n"
        "1) Obtén el <b>Telegram ID</b> del usuario.\n"
        "2) Envíame este comando:\n\n"
        "<code>/user_ID</code>\n\n"
        "Ejemplo:\n"
        "<code>/user_123456789</code>\n\n"
        "Luego verás los botones para activar Plus o Premium.\n",
        reply_markup=admin_home_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:pending:"))
async def admin_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[-1])
    except Exception:
        page = 0

    skip = page * PAGE_SIZE
    claims = await get_pending_claims(limit=PAGE_SIZE + 1, skip=skip)
    has_more = len(claims) > PAGE_SIZE
    claims = claims[:PAGE_SIZE]

    if not claims:
        await callback.message.edit_text(
            "📥 <b>Pendientes</b>\n\nNo hay evidencias pendientes.",
            reply_markup=admin_pending_list_kb(page=0, has_more=False),
        )
        await callback.answer()
        return

    lines = ["📥 <b>Pendientes (Compartir publicación)</b>\n"]
    for idx, c in enumerate(claims, start=1):
        cid = str(c["_id"])
        uid = c.get("telegram_id")
        code = (c.get("meta") or {}).get("weekly_code", "—")
        caption = _short((c.get("meta") or {}).get("caption", ""), 45)
        lines.append(
            f"{idx}) <b>ID:</b> <code>{cid}</code>\n"
            f"   • Usuario: <code>{uid}</code>\n"
            f"   • Código: <code>{code}</code>\n"
            f"   • Nota: {caption}\n"
            f"   • Abrir: /claim_{cid}\n"
        )

    lines.append("📌 Para ver un claim, envía el comando: <code>/claim_ID</code> (sin espacios).")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_pending_list_kb(page=page, has_more=has_more),
    )
    await callback.answer()


@router.message(F.text.startswith("/claim_"))
async def admin_open_claim(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sin acceso.")
        return

    claim_id = message.text.replace("/claim_", "").strip()
    if not claim_id:
        await message.answer("Uso: /claim_ID")
        return

    await message.answer(
        "🧾 <b>Claim seleccionado</b>\n\n"
        f"ID: <code>{claim_id}</code>\n\n"
        "Selecciona una acción:",
        reply_markup=admin_claim_actions_kb(claim_id),
    )


@router.callback_query(F.data.startswith("admin:approve:"))
async def admin_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    claim_id = callback.data.split("admin:approve:", 1)[1].strip()
    ok, msg = await approve_share_claim(claim_id=claim_id, admin_id=callback.from_user.id)

    await callback.answer(msg, show_alert=True)
    await callback.message.edit_text(
        "✅ Acción procesada.\n\nRegresa a pendientes para seguir.",
        reply_markup=admin_home_kb(),
    )


@router.callback_query(F.data.startswith("admin:reject:"))
async def admin_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    claim_id = callback.data.split("admin:reject:", 1)[1].strip()
    ok, msg = await reject_share_claim(claim_id=claim_id, admin_id=callback.from_user.id, note="Rechazado")

    await callback.answer(msg, show_alert=True)
    await callback.message.edit_text(
        "✅ Acción procesada.\n\nRegresa a pendientes para seguir.",
        reply_markup=admin_home_kb(),
    )


@router.message(F.text.startswith("/user_"))
async def admin_user_actions(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sin acceso.")
        return

    raw = message.text.replace("/user_", "").strip()
    try:
        user_id = int(raw)
    except Exception:
        await message.answer("Formato inválido. Ejemplo: <code>/user_123456789</code>")
        return

    await message.answer(
        "🛒 <b>Activación Manual</b>\n\n"
        f"Usuario: <code>{user_id}</code>\n\n"
        "Selecciona el plan a activar (descuenta puntos automáticamente):",
        reply_markup=admin_user_actions_kb(user_id),
    )


@router.callback_query(F.data.startswith("admin:actplus:"))
async def admin_activate_plus(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    raw = callback.data.split("admin:actplus:", 1)[1].strip()
    try:
        user_id = int(raw)
    except Exception:
        await callback.answer("ID inválido.", show_alert=True)
        return

    ok, msg = await activate_plus_by_points(user_telegram_id=user_id, admin_id=callback.from_user.id)
    await callback.answer(msg, show_alert=True)
    await callback.message.edit_text(
        f"✅ Proceso terminado para usuario <code>{user_id}</code>.\n\n{msg}",
        reply_markup=admin_home_kb(),
    )


@router.callback_query(F.data.startswith("admin:actprem:"))
async def admin_activate_premium(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    raw = callback.data.split("admin:actprem:", 1)[1].strip()
    try:
        user_id = int(raw)
    except Exception:
        await callback.answer("ID inválido.", show_alert=True)
        return

    ok, msg = await activate_premium_by_points(user_telegram_id=user_id, admin_id=callback.from_user.id)
    await callback.answer(msg, show_alert=True)
    await callback.message.edit_text(
        f"✅ Proceso terminado para usuario <code>{user_id}</code>.\n\n{msg}",
        reply_markup=admin_home_kb(),
  )
