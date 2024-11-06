import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from token_data import TOKEN
from recipes_handler import router


logging.basicConfig(level=logging.INFO)


bot = Bot(token=TOKEN)
dp = Dispatcher()


dp.include_router(router)


@dp.message(Command("start"))
async def command_start_handler(message: Message):
    await message.answer("Привет! Я готов помочь с рецептами! Используй /category_search_random для поиска рецептов.")


async def main():
    # Запуск polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


