from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _safe_username(u: Dict[str, Any]) -> str:
    username = (u.get("username") or "").strip()
    if username:
        return f"@{username}"
    first = (u.get("first_name") or "").strip()
    if first:
        return first
    return f"ID:{u.get('telegram_id')}"


async def get_user_month_points(telegram_id: int, month_key: str) -> int:
    db = get_db()
    u = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"rank": 1, "status": 1},
    )
    if not u:
        return 0
    if ((u.get("status") or {}).get("state")) == "banned":
        return 0

    mk = ((u.get("rank") or {}).get("month_key")) or month_key
    if mk != month_key:
        return 0

    return int(((u.get("rank") or {}).get("earned_this_month")) or 0)


async def upsert_winner(
    month_key: str,
    position: int,
    telegram_id: int,
    admin_id: int,
    note: str = "",
) -> Tuple[bool, str]:
    if position not in (1, 2, 3):
        return False, "Posición inválida (solo 1, 2 o 3)."

    db = get_db()

    user = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"telegram_id": 1, "username": 1, "first_name": 1, "last_name": 1, "status": 1},
    )
    if not user:
        return False, "Usuario no encontrado."
    if ((user.get("status") or {}).get("state")) == "banned":
        return False, "El usuario está expulsado (banned). No puede ser ganador."

    pts = await get_user_month_points(telegram_id, month_key)

    winner_obj = {
        "position": position,
        "telegram_id": telegram_id,
        "display": _safe_username(user),
        "points_month": pts,
        "note": note.strip(),
        "set_by_admin_id": admin_id,
        "set_at": datetime.utcnow(),
    }

    # Upsert del documento del mes
    now = datetime.utcnow()
    doc = await db.monthly_winners.find_one({"month_key": month_key})
    if not doc:
        await db.monthly_winners.insert_one(
            {
                "month_key": month_key,
                "winners": [winner_obj],
                "created_at": now,
                "updated_at": now,
            }
        )
        return True, f"✅ Ganador #{position} guardado para {month_key}."

    winners: List[Dict[str, Any]] = doc.get("winners") or []
    # Reemplazar si ya existía esa posición
    winners = [w for w in winners if int(w.get("position", 0)) != position]
    winners.append(winner_obj)
    winners.sort(key=lambda x: int(x.get("position", 99)))

    await db.monthly_winners.update_one(
        {"month_key": month_key},
        {"$set": {"winners": winners, "updated_at": now}},
    )

    return True, f"✅ Ganador #{position} actualizado para {month_key}."


async def clear_winners(month_key: str, admin_id: int) -> Tuple[bool, str]:
    db = get_db()
    res = await db.monthly_winners.delete_one({"month_key": month_key})
    if res.deleted_count == 0:
        return False, "No había ganadores guardados para este mes."
    return True, f"🗑️ Ganadores del mes {month_key} eliminados."


async def get_winners(month_key: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    db = get_db()
    mk = month_key or _month_key(datetime.utcnow())

    doc = await db.monthly_winners.find_one({"month_key": mk})
    if not doc:
        return mk, []

    winners = doc.get("winners") or []
    winners.sort(key=lambda x: int(x.get("position", 99)))
    return mk, winners


async def build_winners_public_text() -> str:
    mk, winners = await get_winners()

    lines: List[str] = []
    lines.append("🏆 <b>Ganadores del Mes</b>")
    lines.append(f"🗓️ Mes: <b>{mk}</b>\n")

    if not winners:
        lines.append("Aún no hay ganadores publicados para este mes.")
        return "\n".join(lines)

    # Mapeo por posición
    pos_map = {int(w.get("position")): w for w in winners}

    def line_for(pos: int, medal: str) -> str:
        w = pos_map.get(pos)
        if not w:
            return f"{medal} <b>Top {pos}</b>: —"
        name = w.get("display") or f"ID:{w.get('telegram_id')}"
        pts = int(w.get("points_month") or 0)
        note = (w.get("note") or "").strip()
        base = f"{medal} <b>Top {pos}</b>: <b>{name}</b> — <b>{pts}</b> pts"
        if note:
            base += f"\n   📝 {note}"
        return base

    lines.append(line_for(1, "🥇"))
    lines.append(line_for(2, "🥈"))
    lines.append(line_for(3, "🥉"))

    lines.append("\n📌 Premio: señales privadas + asesoría según el puesto (Top 3).")
    return "\n".join(lines)


async def build_winners_admin_text() -> str:
    mk, winners = await get_winners()
    public = await build_winners_public_text()
    # Admin: agrega comandos rápidos
    admin_help = (
        "\n\n🛠 <b>Admin comandos</b>\n"
        "• Definir ganador: <code>/win_POS_ID</code>\n"
        "  Ej: <code>/win_1_123456789</code>\n"
        "• Con nota: <code>/win_POS_ID Nota</code>\n"
        "  Ej: <code>/win_2_123456789 Excelente mes</code>\n"
        "• Borrar ganadores del mes: <code>/wins_clear</code>\n"
    )
    return public + admin_help
