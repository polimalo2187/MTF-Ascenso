from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from datetime import datetime
from app.db.models.user_model import update_user

router = Router()


@router.message(Command("policy"))
async def policy_handler(message: Message):
    text = (
        "📜 <b>Políticas de MTF Ascenso</b>\n\n"
        "1️⃣ Los puntos no tienen valor monetario.\n"
        "2️⃣ Solo pueden usarse para activar planes internos.\n"
        "3️⃣ Prohibido cuentas múltiples.\n"
        "4️⃣ Prohibido manipular capturas.\n"
        "5️⃣ Prohibido explotar errores.\n\n"
        "Escribe /accept para aceptar las políticas."
    )

    await message.answer(text)


@router.message(Command("accept"))
async def accept_policy_handler(message: Message):
    await update_user(
        message.from_user.id,
        {
            "policy.accepted": True,
            "policy.accepted_at": datetime.utcnow()
        }
    )

    await message.answer(
        "✅ Has aceptado las políticas.\n\n"
        "Ahora puedes comenzar a usar MTF Ascenso."
    )
