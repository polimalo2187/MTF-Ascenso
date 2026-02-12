from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from app.db.models.task_claim_model import (
    list_pending_claims,
    find_task_claim_by_id,
    update_claim_status,
)
from app.services.ledger_service import create_points_entry, TYPE_EARN, CAT_TASK
from app.services.tiers_service import get_multiplier, ensure_auto_tier_by_month_points, refresh_tiers

TASK_SHARE = "TASK_SHARE_POST"


def _parse_admin_ids() -> List[int]:
    raw = os.getenv("ADMIN_IDS", "").strip()
    if not raw:
        return []
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except Exception:
            continue
    return ids


def is_admin(telegram_id: int) -> bool:
    return telegram_id in _parse_admin_ids()


async def get_pending_claims(limit: int = 10, skip: int = 0) -> List[Dict[str, Any]]:
    return await list_pending_claims(limit=limit, skip=skip)


def _apply_multiplier(base_points: int, mult: float) -> int:
    v = int((base_points * mult) + 0.999999)
    return max(1, v)


async def approve_share_claim(claim_id: str, admin_id: int) -> Tuple[bool, str]:
    claim = await find_task_claim_by_id(claim_id)
    if not claim:
        return False, "Claim no encontrado."

    if claim.get("status") != "pending":
        return False, "Este claim ya fue procesado."

    task_code = claim.get("task_code")
    if task_code != TASK_SHARE:
        return False, "Este claim no corresponde a 'Compartir publicación'."

    telegram_id = int(claim["telegram_id"])
    base_points = int(claim.get("points") or 0)
    if base_points <= 0:
        return False, "Puntos inválidos en el claim."

    ok = await update_claim_status(claim_id=claim_id, status="approved", admin_id=admin_id, note="Aprobado")
    if not ok:
        return False, "No se pudo aprobar (quizás ya fue aprobado por otro admin)."

    await refresh_tiers(telegram_id)
    mult = await get_multiplier(telegram_id)
    pts = _apply_multiplier(base_points, mult)

    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_SHARE,
        points=pts,
        meta={"claim_id": claim_id, "approved_by": admin_id, "mult": mult, "base": base_points},
    )

    await ensure_auto_tier_by_month_points(telegram_id)

    return True, f"✅ Aprobado y acreditado: +{pts} pts (base {base_points}, x{mult}) al usuario {telegram_id}."


async def reject_share_claim(claim_id: str, admin_id: int, note: str = "Rechazado") -> Tuple[bool, str]:
    claim = await find_task_claim_by_id(claim_id)
    if not claim:
        return False, "Claim no encontrado."

    if claim.get("status") != "pending":
        return False, "Este claim ya fue procesado."

    task_code = claim.get("task_code")
    if task_code != TASK_SHARE:
        return False, "Este claim no corresponde a 'Compartir publicación'."

    ok = await update_claim_status(claim_id=claim_id, status="rejected", admin_id=admin_id, note=note)
    if not ok:
        return False, "No se pudo rechazar (quizás ya fue procesado)."

    telegram_id = int(claim["telegram_id"])
    return True, f"🚫 Rechazado. Usuario: {telegram_id}."
