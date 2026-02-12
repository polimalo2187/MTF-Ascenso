from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from app.db.models.task_claim_model import (
    list_pending_claims,
    find_task_claim_by_id,
    update_claim_status,
)
from app.services.ledger_service import create_points_entry, TYPE_EARN, CAT_TASK


TASK_SHARE = "TASK_SHARE_POST"  # reason_code del ledger para compartir


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


async def approve_share_claim(claim_id: str, admin_id: int) -> Tuple[bool, str]:
    """
    Aprueba un claim pendiente (share post):
    - Cambia status -> approved
    - Acredita puntos via ledger (+6)
    """
    claim = await find_task_claim_by_id(claim_id)
    if not claim:
        return False, "Claim no encontrado."

    if claim.get("status") != "pending":
        return False, "Este claim ya fue procesado."

    task_code = claim.get("task_code")
    if task_code != TASK_SHARE:
        return False, "Este claim no corresponde a 'Compartir publicación'."

    telegram_id = int(claim["telegram_id"])
    points = int(claim.get("points") or 0)
    if points <= 0:
        return False, "Puntos inválidos en el claim."

    ok = await update_claim_status(claim_id=claim_id, status="approved", admin_id=admin_id, note="Aprobado")
    if not ok:
        return False, "No se pudo aprobar (quizás ya fue aprobado por otro admin)."

    # Acreditar puntos en ledger
    await create_points_entry(
        telegram_id=telegram_id,
        entry_type=TYPE_EARN,
        category=CAT_TASK,
        reason_code=TASK_SHARE,
        points=points,
        meta={"claim_id": claim_id, "approved_by": admin_id},
    )

    return True, f"✅ Aprobado y acreditado: +{points} pts al usuario {telegram_id}."


async def reject_share_claim(claim_id: str, admin_id: int, note: str = "Rechazado") -> Tuple[bool, str]:
    """
    Rechaza un claim pendiente (share post):
    - Cambia status -> rejected
    - NO acredita puntos
    """
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
