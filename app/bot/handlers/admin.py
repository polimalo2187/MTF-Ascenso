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
from app.services.security_service import (
    get_user_security_snapshot,
    apply_next_infraction,
)
from app.bot.keyboards.admin_menu import (
    admin_home_kb,
    admin_pending_list_kb,
    admin_claim_actions_kb,
    admin_user_actions_kb,
    admin_infraction_confirm_kb,
)

router = Router()

PAGE_SIZE = 5


def _short(s: str, n: int = 60) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _fmt_dt(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M UTC")


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


@router.callback_query(F.data == "admin:winners_help")
async def admin_winners_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    await callback.message.edit_text(
        "🏆 <b>Ganadores del Mes (Top 3)</b>\n\n"
        "Comandos para publicar ganadores (manual):\n"
        "• <code>/win_1_ID</code>  (Top 1)\n"
        "• <code>/win_2_ID</code>  (Top 2)\n"
        "• <code>/win_3_ID</code>  (Top 3)\n\n"
        "Con nota opcional:\n"
        "• <code>/win_1_ID Nota</code>\n\n"
        "Borrar ganadores del mes actual:\n"
        "• <code>/wins_clear</code>\n\n"
        "Ver ganadores:\n"
        "• <code>/winners</code>\n",
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

    ok, _, snap = await get_user_security_snapshot(user_id)
    if not ok or not snap:
        await message.answer("Usuario no encontrado.")
        return

    inf_count = int(((snap.get("infractions") or {}).get("count")) or 0)
    state = ((snap.get("status") or {}).get("state")) or "active"
    blocked_until = (snap.get("status") or {}).get("blocked_until")
    bal = int(((snap.get("points") or {}).get("balance_cached")) or 0)

    await message.answer(
        "🛒 <b>Acciones Admin</b>\n\n"
        f"Usuario: <code>{user_id}</code>\n"
        f"Saldo: <b>{bal}</b> pts\n"
        f"Infracciones: <b>{inf_count}</b>\n"
        f"Estado: <b>{state}</b>\n"
        f"Bloqueado hasta: <b>{_fmt_dt(blocked_until)}</b>\n\n"
        "Selecciona una acción:",
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


@router.callback_query(F.data.startswith("admin:infraction:"))
async def admin_infraction_preview(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    raw = callback.data.split("admin:infraction:", 1)[1].strip()
    try:
        user_id = int(raw)
    except Exception:
        await callback.answer("ID inválido.", show_alert=True)
        return

    ok, _, snap = await get_user_security_snapshot(user_id)
    if not ok or not snap:
        await callback.answer("Usuario no encontrado.", show_alert=True)
        return

    inf_count = int(((snap.get("infractions") or {}).get("count")) or 0)
    state = ((snap.get("status") or {}).get("state")) or "active"
    blocked_until = (snap.get("status") or {}).get("blocked_until")
    bal = int(((snap.get("points") or {}).get("balance_cached")) or 0)

    next_action = "1ra: eliminar puntos + advertencia"
    if inf_count == 1:
        next_action = "2da: bloqueo temporal"
    elif inf_count >= 2:
        next_action = "3ra: expulsión definitiva"

    await callback.message.edit_text(
        "⚖️ <b>Sanción escalonada</b>\n\n"
        f"Usuario: <code>{user_id}</code>\n"
        f"Saldo: <b>{bal}</b> pts\n"
        f"Infracciones actuales: <b>{inf_count}</b>\n"
        f"Estado: <b>{state}</b>\n"
        f"Bloqueado hasta: <b>{_fmt_dt(blocked_until)}</b>\n\n"
        f"➡️ Próxima sanción: <b>{next_action}</b>\n\n"
        "¿Confirmas aplicar la siguiente sanción?",
        reply_markup=admin_infraction_confirm_kb(user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:applyinf:"))
async def admin_infraction_apply(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    raw = callback.data.split("admin:applyinf:", 1)[1].strip()
    try:
        user_id = int(raw)
    except Exception:
        await callback.answer("ID inválido.", show_alert=True)
        return

    ok, msg = await apply_next_infraction(user_telegram_id=user_id, admin_id=callback.from_user.id, note="Violación de políticas")
    await callback.answer(msg, show_alert=True)
    await callback.message.edit_text(
        f"✅ Sanción aplicada a <code>{user_id}</code>.\n\n{msg}",
        reply_markup=admin_home_kb(),
    )


@router.callback_query(F.data.startswith("admin:cancelinf:"))
async def admin_infraction_cancel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Sin acceso.", show_alert=True)
        return

    raw = callback.data.split("admin:cancelinf:", 1)[1].strip()
    await callback.message.edit_text(
        f"❎ Operación cancelada para usuario <code>{raw}</code>.",
        reply_markup=admin_home_kb(),
    )
    await callback.answer()
