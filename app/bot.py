import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from app.config import BOT_TOKEN, WEBAPP_URL


async def cmd_start(message: Message):
    if not WEBAPP_URL:
        await message.answer(
            "⚠️ WEBAPP_URL не задан в .env — сначала задеплойте app/main.py по HTTPS "
            "и укажите его адрес."
        )
        return

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="🎯 Открыть Pick'em", web_app=WebAppInfo(url=WEBAPP_URL)
        )
    )
    text = (
        "👋 Привет, Выбеси | 24/7!\n\n"
        "🏆 S2 Pick'em\n"
        "Предсказывай результаты матчей Standoff 2 и получай очки!\n\n"
        "Система очков:\n"
        "🥇 Победитель → +10 pts\n"
        "📊 Счёт → +15 pts\n"
        "🎖 MVP → +20 pts"
    )
    await message.answer(text, reply_markup=b.as_markup())


async def main():
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
