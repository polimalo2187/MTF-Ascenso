from datetime import datetime
from app.db.models.user_model import get_user, create_user


async def get_or_create_user(tg_user):
    user = await get_user(tg_user.id)

    if user:
        return user

    new_user = {
        "telegram_id": tg_user.id,
        "username": tg_user.username,
        "first_name": tg_user.first_name,
        "last_name": tg_user.last_name,
        "created_at": datetime.utcnow(),
        "policy": {
            "accepted": False,
            "accepted_at": None,
            "version": "1.0"
        },
        "status": {
            "state": "active",
            "blocked_until": None,
            "ban_reason": None
        },
        "infractions": {
            "count": 0,
            "last_at": None
        },
        "points": {
            "balance_cached": 0,
            "lifetime_earned": 0,
            "lifetime_spent": 0
        },
        "ascenso_plan": {
            "type": "FREE",
            "expires_at": None
        },
        "elite": {
            "active": False,
            "active_until": None
        },
        "titan": {
            "active": False,
            "active_until": None,
            "premium_redeems_count": 0
        }
    }

    await create_user(new_user)
    return new_user
