from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import pandas as pd
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv

from notifier import send_to_telegram, send_to_webhook
from storage import LeadStorage


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parents[1]
SERVICES_PATH = PROJECT_DIR / "data" / "services.csv"
LEADS_PATH = PROJECT_DIR / "data" / "leads.csv"

storage = LeadStorage(LEADS_PATH)


class LeadForm(StatesGroup):
    service = State()
    budget = State()
    name = State()
    phone = State()
    email = State()
    comment = State()


def load_services() -> list[str]:
    services = pd.read_csv(SERVICES_PATH)
    return services["service_name"].tolist()


def services_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=service)] for service in load_services()],
        resize_keyboard=True,
    )


def budget_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="до 50 тыс ₽")],
            [KeyboardButton(text="50–100 тыс ₽")],
            [KeyboardButton(text="100–200 тыс ₽")],
            [KeyboardButton(text="по договоренности")],
        ],
        resize_keyboard=True,
    )


def is_phone(value: str) -> bool:
    return len(re.sub(r"\D+", "", value)) in {10, 11}


def is_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip().lower()))


async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Здравствуйте! Я помогу оформить заявку.\n\nВыберите услугу:",
        reply_markup=services_keyboard(),
    )
    await state.set_state(LeadForm.service)


async def choose_service(message: Message, state: FSMContext) -> None:
    if message.text not in load_services():
        await message.answer("Выберите услугу из списка кнопок.")
        return

    await state.update_data(service=message.text)
    await message.answer("Какой ориентировочный бюджет проекта?", reply_markup=budget_keyboard())
    await state.set_state(LeadForm.budget)


async def choose_budget(message: Message, state: FSMContext) -> None:
    await state.update_data(budget=message.text)
    await message.answer("Как вас зовут?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LeadForm.name)


async def enter_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await message.answer("Оставьте телефон для связи.")
    await state.set_state(LeadForm.phone)


async def enter_phone(message: Message, state: FSMContext) -> None:
    if not is_phone(message.text):
        await message.answer("Похоже, телефон некорректный. Пример: +79991234567")
        return

    await state.update_data(phone=message.text)
    await message.answer("Оставьте email.")
    await state.set_state(LeadForm.email)


async def enter_email(message: Message, state: FSMContext) -> None:
    if not is_email(message.text):
        await message.answer("Похоже, email некорректный. Пример: name@example.com")
        return

    await state.update_data(email=message.text)
    await message.answer("Коротко опишите задачу.")
    await state.set_state(LeadForm.comment)


async def enter_comment(message: Message, state: FSMContext) -> None:
    await state.update_data(comment=message.text)
    data = await state.get_data()

    lead = storage.create_lead(
        name=data["name"],
        phone=data["phone"],
        email=data["email"],
        service=data["service"],
        budget=data["budget"],
        comment=data["comment"],
        manager=os.getenv("DEFAULT_MANAGER", "Мария"),
    )

    await send_to_telegram(lead)
    await send_to_webhook(lead)

    await message.answer(
        "Спасибо! Заявка принята.\n\n"
        f"Номер заявки: {lead.lead_id}\n"
        "Менеджер свяжется с вами в ближайшее время.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.clear()


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(start, CommandStart())
    dp.message.register(choose_service, LeadForm.service)
    dp.message.register(choose_budget, LeadForm.budget)
    dp.message.register(enter_name, LeadForm.name)
    dp.message.register(enter_phone, LeadForm.phone)
    dp.message.register(enter_email, LeadForm.email)
    dp.message.register(enter_comment, LeadForm.comment)
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
