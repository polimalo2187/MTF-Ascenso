from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from app.bot.keyboards.tasks_menu import tasks_menu_kb, share_actions_kb
from app.services.tasks_service import (
    claim_daily_checkin,
    award_lesson_quiz,
    submit_share_post_evidence,
    share_post_text,
)

router = Router()


class LessonQuizState(StatesGroup):
    waiting_answer = State()


class ShareEvidenceState(StatesGroup):
    waiting_photo = State()


@router.callback_query(F.data == "tasks:home")
async def tasks_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Centro de Tareas</b>\n\n"
        "Completa tareas para ganar puntos y activar planes.\n"
        "Selecciona una opción:",
        reply_markup=tasks_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "tasks:checkin")
async def tasks_checkin(callback: CallbackQuery):
    ok, msg = await claim_daily_checkin(callback.from_user.id)
    await callback.answer(msg, show_alert=True)
    # No cambiamos pantalla; se queda en donde esté
    # (si el usuario quiere ver saldo, va a Mis puntos)
    return


@router.callback_query(F.data == "tasks:lesson")
async def tasks_lesson_start(callback: CallbackQuery, state: FSMContext):
    # Mini lección + quiz simple V1
    await state.clear()
    await state.set_state(LessonQuizState.waiting_answer)

    await callback.message.edit_text(
        "🎓 <b>Mini Lección (V1)</b>\n\n"
        "Una señal LONG significa:\n\n"
        "A) Vender (apostar a la baja)\n"
        "B) Comprar (apostar a la subida)\n\n"
        "Responde escribiendo: <b>A</b> o <b>B</b>",
    )
    await callback.answer()


@router.message(LessonQuizState.waiting_answer)
async def tasks_lesson_answer(message: Message, state: FSMContext):
    ans = (message.text or "").strip().upper()

    if ans not in ("A", "B"):
        await message.answer("Responde con <b>A</b> o <b>B</b>.")
        return

    if ans != "B":
        await state.clear()
        await message.answer(
            "❌ Respuesta incorrecta.\n\n"
            "Tip: LONG normalmente es apostar a la subida.\n"
            "Vuelve a intentarlo mañana.",
            reply_markup=tasks_menu_kb(),
        )
        return

    ok, msg = await award_lesson_quiz(message.from_user.id)
    await state.clear()
    await message.answer(msg, reply_markup=tasks_menu_kb())


@router.callback_query(F.data == "tasks:share")
async def tasks_share(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = share_post_text(callback.from_user.id)

    await callback.message.edit_text(
        "📤 <b>Compartir Publicación (+6)</b>\n\n"
        "1) Copia el texto oficial y compártelo en grupos (Telegram/WhatsApp/Facebook).\n"
        "2) Luego envía aquí una <b>captura</b> como evidencia.\n\n"
        "<b>Texto oficial:</b>\n"
        f"<code>{text}</code>\n\n"
        "Cuando estés listo, toca <b>📋 Copiar texto</b> o envía la captura.",
        reply_markup=share_actions_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "tasks:share_text")
async def tasks_share_text(callback: CallbackQuery, state: FSMContext):
    # Activamos modo espera de foto
    await state.set_state(ShareEvidenceState.waiting_photo)
    await callback.message.answer(
        "📸 Ahora envíame la <b>captura</b> como evidencia (una foto).\n\n"
        "Opcional: escribe una descripción en el caption (nombre del grupo, plataforma, etc.)."
    )
    await callback.answer()


@router.message(ShareEvidenceState.waiting_photo)
async def tasks_share_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Necesito que envíes una <b>foto</b> (captura) como evidencia.")
        return

    photo = message.photo[-1]
    file_id = photo.file_id
    caption = message.caption or ""

    ok, msg = await submit_share_post_evidence(
        telegram_id=message.from_user.id,
        photo_file_id=file_id,
        caption=caption,
    )
    await state.clear()
    await message.answer(msg, reply_markup=tasks_menu_kb())
