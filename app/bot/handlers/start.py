from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from app.services.user_service import get_or_create_user

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    user = await get_or_create_user(message.from_user)

    if not user["policy"]["accepted"]:
        await message.answer(
            "📜 Bienvenido a <b>MTF Ascenso</b>\n\n"
            "Antes de continuar debes aceptar las políticas del sistema.\n\n"
            "Escribe /policy para leerlas."
        )
        return

    await message.answer(
        "🚀 Bienvenido nuevamente a <b>MTF Ascenso</b>\n\n"
        "Pronto activaremos el menú principal."
    )
