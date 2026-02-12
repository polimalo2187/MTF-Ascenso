from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from app.services.user_service import get_or_create_user
from app.bot.keyboards.main_menu import main_menu_kb

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    user = await get_or_create_user(message.from_user)

    if not user["policy"]["accepted"]:
        await message.answer(
            "📜 Bienvenido a <b>MTF Ascenso</b>\n\n"
            "Antes de continuar debes aceptar las políticas del sistema.\n\n"
            "Usa /policy para leerlas y /accept para aceptar."
        )
        return

    await message.answer(
        "🏠 <b>MTF Ascenso</b>\n\n"
        "Selecciona una opción:",
        reply_markup=main_menu_kb(),
    )
