from __future__ import annotations

import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

from knowledge_base import KnowledgeBase
from notifier import send_to_operator, send_to_support_webhook
from storage import TicketStorage


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parents[1]
FAQ_PATH = PROJECT_DIR / "data" / "faq.csv"
TICKETS_PATH = PROJECT_DIR / "data" / "support_tickets.csv"

kb = KnowledgeBase(FAQ_PATH)
storage = TicketStorage(TICKETS_PATH)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Оплата"), KeyboardButton(text="Доставка")],
            [KeyboardButton(text="Документы"), KeyboardButton(text="Режим работы")],
            [KeyboardButton(text="Связаться с оператором")],
        ],
        resize_keyboard=True,
    )


async def start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Я бот поддержки.\n\n"
        "Могу ответить на вопросы про оплату, доставку, документы, режим работы "
        "или передать сложный вопрос оператору.",
        reply_markup=main_keyboard(),
    )


async def handle_question(message: Message) -> None:
    question = message.text or ""

    if question.lower() == "связаться с оператором":
        result = {
            "intent": "operator_request",
            "answer": "Передаю вопрос оператору. Напишите, пожалуйста, что случилось.",
            "need_operator": True,
        }
    else:
        result = kb.find_answer(question)

    ticket = storage.create_ticket(
        client_name=message.from_user.full_name if message.from_user else "Клиент",
        question=question,
        detected_intent=result["intent"],
        need_operator=result["need_operator"],
        channel="telegram",
    )

    await send_to_support_webhook(ticket)

    if result["need_operator"]:
        await send_to_operator(ticket)
        await message.answer(result["answer"] + "\n\nОператор подключится в ближайшее время.")
    else:
        await message.answer(result["answer"])


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(handle_question)
    return dp


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN. Скопируйте .env.example в .env и заполните токен.")

    bot = Bot(token=token)
    dp = build_dispatcher()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
