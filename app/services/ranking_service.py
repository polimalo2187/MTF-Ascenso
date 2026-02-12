from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db

MIN_POINTS_TO_QUALIFY = 80
TOP_LIMIT = 10


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _safe_username(u: Dict[str, Any]) -> str:
    username = (u.get("username") or "").strip()
    if username:
        return f"@{username}"
    # fallback
    first = (u.get("first_name") or "").strip()
    if first:
        return first
    return f"ID:{u.get('telegram_id')}"


def _badge(u: Dict[str, Any]) -> str:
    titan_active = bool(((u.get("titan") or {}).get("active")) or False)
    elite_active = bool(((u.get("elite") or {}).get("active")) or False)
    if titan_active:
        return "💎"
    if elite_active:
        return "🏆"
    return "•"


async def get_top_ranking(month_key: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Retorna (month_key, top_users)
    """
    db = get_db()
    mk = month_key or _month_key(datetime.utcnow())

    cursor = (
        db.users.find(
            {
                "rank.month_key": mk,
                "rank.earned_this_month": {"$gte": MIN_POINTS_TO_QUALIFY},
                "status.state": {"$ne": "banned"},
            },
            {
                "telegram_id": 1,
                "username": 1,
                "first_name": 1,
                "rank": 1,
                "elite": 1,
                "titan": 1,
            },
        )
        .sort("rank.earned_this_month", -1)
        .limit(TOP_LIMIT)
    )

    top_users = await cursor.to_list(length=TOP_LIMIT)
    return mk, top_users


async def get_user_month_points(telegram_id: int, month_key: Optional[str] = None) -> Tuple[str, int]:
    db = get_db()
    mk = month_key or _month_key(datetime.utcnow())

    u = await db.users.find_one(
        {"telegram_id": telegram_id},
        {"rank": 1, "status": 1},
    )
    if not u:
        return mk, 0

    # Si el usuario está baneado, da 0
    if ((u.get("status") or {}).get("state")) == "banned":
        return mk, 0

    user_mk = ((u.get("rank") or {}).get("month_key")) or mk
    if user_mk != mk:
        return mk, 0

    pts = int(((u.get("rank") or {}).get("earned_this_month")) or 0)
    return mk, pts


async def get_user_position_if_qualified(telegram_id: int, month_key: Optional[str] = None) -> Tuple[str, Optional[int]]:
    """
    Retorna (month_key, position) si el usuario califica (>=80), si no, (month_key, None).
    Position es 1-based.
    """
    db = get_db()
    mk, my_pts = await get_user_month_points(telegram_id, month_key=month_key)
    if my_pts < MIN_POINTS_TO_QUALIFY:
        return mk, None

    # Cuenta cuántos usuarios tienen MÁS puntos que el usuario (para calcular posición)
    # Excluye banned y requiere >=80 para estar en ranking
    higher = await db.users.count_documents(
        {
            "rank.month_key": mk,
            "rank.earned_this_month": {"$gt": my_pts},
            "rank.earned_this_month": {"$gte": MIN_POINTS_TO_QUALIFY},
            "status.state": {"$ne": "banned"},
        }
    )
    return mk, int(higher) + 1


async def build_ranking_text(telegram_id: int) -> str:
    db = get_db()

    # Validación básica: usuario existe y aceptó políticas
    user = await db.users.find_one({"telegram_id": telegram_id}, {"policy": 1, "status": 1})
    if not user:
        return "Usuario no encontrado. Escribe /start."

    if not ((user.get("policy") or {}).get("accepted")):
        return "Debes aceptar las políticas primero. Usa /policy y /accept."

    state = (user.get("status") or {}).get("state", "active")
    if state == "banned":
        return "🚫 Estás expulsado del sistema."

    mk, top = await get_top_ranking()
    _, my_pts = await get_user_month_points(telegram_id, month_key=mk)
    _, my_pos = await get_user_position_if_qualified(telegram_id, month_key=mk)

    lines: List[str] = []
    lines.append("📈 <b>Ranking del Mes</b>")
    lines.append(f"🗓️ Mes: <b>{mk}</b>")
    lines.append(f"✅ Para calificar: <b>{MIN_POINTS_TO_QUALIFY}</b> pts en el mes\n")

    if not top:
        lines.append("Aún no hay usuarios calificados este mes.\n")
    else:
        lines.append("<b>🏆 Top 10</b>")
        for i, u in enumerate(top, start=1):
            pts = int(((u.get("rank") or {}).get("earned_this_month")) or 0)
            name = _safe_username(u)
            badge = _badge(u)
            lines.append(f"{i}) {badge} <b>{name}</b> — <b>{pts}</b> pts")

        lines.append("")

    # Estado del usuario actual
    lines.append("<b>👤 Tu estado</b>")
    lines.append(f"• Puntos ganados este mes: <b>{my_pts}</b>")

    if my_pts < MIN_POINTS_TO_QUALIFY:
        faltan = MIN_POINTS_TO_QUALIFY - my_pts
        lines.append(f"• Te faltan: <b>{faltan}</b> pts para entrar al ranking")
    else:
        if my_pos is not None:
            lines.append(f"• Tu posición: <b>#{my_pos}</b> ✅")
        else:
            lines.append("• Tu posición: —")

    lines.append("\n💡 Tip: Las tareas fuertes (Compartir + Reto semanal) empujan el ranking.")

    return "\n".join(lines)
