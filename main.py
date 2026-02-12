import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.bot.handlers.start import router as start_router
from app.bot.handlers.policy import router as policy_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.tasks import router as tasks_router
from app.db.connection import init_db


async def main():
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN not found in environment variables")

    bot = Bot(token=bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    await init_db()

    dp.include_router(start_router)
    dp.include_router(policy_router)
    dp.include_router(menu_router)
    dp.include_router(tasks_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
