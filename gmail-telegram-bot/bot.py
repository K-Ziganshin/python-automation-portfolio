import asyncio
import base64
import html
import os
import time
from datetime import datetime
from email.mime.text import MIMEText

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mail_filter import IMPORTANT_KEYWORDS, UNWANTED_KEYWORDS, classify

# --- ОПРЕДЕЛЕНИЕ ПУТЕЙ И ЗАГРУЗКА .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

load_dotenv(dotenv_path=ENV_PATH)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])

CHECK_INTERVAL = 60
IS_MONITORING_ACTIVE = True

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Only the owner's chat may control the bot
dp.message.filter(F.chat.id == TELEGRAM_CHAT_ID)
dp.callback_query.filter(F.message.chat.id == TELEGRAM_CHAT_ID)


# --- FSM (Машина состояний) ---
class SendEmailState(StatesGroup):
    waiting_for_to = State()
    waiting_for_subject = State()
    waiting_for_body = State()
    confirm_send = State()


# --- АВТОРИЗАЦИЯ GMAIL ---
def authenticate_gmail():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(f"Файл {CREDENTIALS_PATH} не найден! Загрузите credentials.json.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


gmail_service = None  # initialised in main()


# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    # Динамическая кнопка переключения мониторинга
    toggle_btn_text = "⏸ Приостановить автопроверку" if IS_MONITORING_ACTIVE else "▶️ Возобновить автопроверку"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Проверить сейчас", callback_data="check_mail"),
                InlineKeyboardButton(text="📊 Статус", callback_data="status_info"),
            ],
            [InlineKeyboardButton(text=toggle_btn_text, callback_data="toggle_monitoring")],
            [InlineKeyboardButton(text="✉️ Написать письмо", callback_data="send_email_start")],
        ]
    )


def get_confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Отправить", callback_data="confirm_send"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_send"),
            ]
        ]
    )


def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_send")]])


# --- ОБОРАЧИВАНИЕ ЗАПРОСОВ К GMAIL С ЗАДЕРЖКОЙ И ПОВТОРАМИ (EXPONENTIAL BACKOFF) ---
def execute_with_backoff(request_func, max_retries=5):
    """Выполняет запрос к Gmail API с автоматической паузой при превышении квоты (403/429)."""
    for attempt in range(max_retries):
        try:
            return request_func()
        except HttpError as error:
            if error.resp.status in [403, 429]:
                sleep_time = (2**attempt) + 1  # 2s, 5s, 9s, 17s...
                print(
                    f"[Quota Exceeded] Превышение лимита запросов. Ожидание {sleep_time} сек (попытка {attempt + 1}/{max_retries})..."
                )
                time.sleep(sleep_time)  # runs in a worker thread, so blocking is fine
            else:
                raise error
    raise Exception("Не удалось выполнить запрос к Gmail API из-за превышения лимитов квоты.")


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ОТПРАВКИ ПИСЬМА С ЗАДЕРЖКОЙ ---
def _send_gmail_sync(to, subject, body):
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    def send_req():
        return gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()

    return execute_with_backoff(send_req)


async def send_gmail_message(to, subject, body):
    return await asyncio.to_thread(_send_gmail_sync, to, subject, body)


# --- ЛОГИКА ОБРАБОТКИ ВХОДЯЩИХ ПИСЕМ С ПАУЗАМИ МЕЖДУ ЗАПРОСАМИ ---
def _fetch_and_process_sync():
    def list_req():
        return gmail_service.users().messages().list(userId="me", q="is:unread").execute()

    results = execute_with_backoff(list_req)
    messages = results.get("messages", [])
    if not messages:
        return []

    processed = []
    for msg in messages:
        msg_id = msg["id"]
        # Небольшая пауза между обработкой отдельных писем для распределения нагрузки
        time.sleep(0.5)

        def get_req():
            return gmail_service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        msg_data = execute_with_backoff(get_req)
        headers = msg_data.get("payload", {}).get("headers", [])

        subject = ""
        sender = ""
        for header in headers:
            if header["name"].lower() == "subject":
                subject = header["value"]
            if header["name"].lower() == "from":
                sender = header["value"]

        snippet = msg_data.get("snippet", "")
        category = classify(subject, snippet)

        if category == "important":

            def modify_req():
                return (
                    gmail_service.users()
                    .messages()
                    .batchModify(userId="me", body={"removeLabelIds": ["UNREAD"], "ids": [msg_id]})
                    .execute()
                )

            execute_with_backoff(modify_req)
            processed.append({"type": "important", "sender": sender, "subject": subject, "snippet": snippet})
        elif category == "unwanted":
            # Move to Trash (recoverable for 30 days) instead of permanent delete
            def trash_req():
                return gmail_service.users().messages().trash(userId="me", id=msg_id).execute()

            execute_with_backoff(trash_req)
            processed.append({"type": "deleted"})
        else:
            processed.append({"type": "ignored"})

    return processed


async def check_and_process_emails():
    try:
        items = await asyncio.to_thread(_fetch_and_process_sync)
        if not items:
            return 0, 0, 0

        total = len(items)
        important_count = 0
        deleted_count = 0

        for item in items:
            if item["type"] == "important":
                important_count += 1
                text = (
                    f"🚨 <b>Важное письмо в Gmail!</b>\n\n"
                    f"<b>От:</b> {html.escape(item['sender'])}\n"
                    f"<b>Тема:</b> {html.escape(item['subject'])}\n\n"
                    f"<b>Краткое содержание:</b> {html.escape(item['snippet'])}"
                )
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", reply_markup=get_main_keyboard()
                )
            elif item["type"] == "deleted":
                deleted_count += 1

        return total, important_count, deleted_count

    except Exception as e:
        print(f"Ошибка при обработке почты: {e}")
        return 0, 0, 0


# --- ХЭНДЛЕРЫ МЕНЮ И УПРАВЛЕНИЯ ---


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    status_str = "🟢 Включена" if IS_MONITORING_ACTIVE else "🔴 Приостановлена"
    await message.answer(
        f"👋 <b>Панель управления Gmail Ботом</b>\n\n"
        f"Статус автопроверки: <b>{status_str}</b>\n"
        f"Бот опрашивает ящик каждые {CHECK_INTERVAL} сек. Вы также можете управлять работой кнопками ниже.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@dp.callback_query(F.data == "toggle_monitoring")
async def callback_toggle_monitoring(callback: types.CallbackQuery):
    global IS_MONITORING_ACTIVE
    IS_MONITORING_ACTIVE = not IS_MONITORING_ACTIVE

    if IS_MONITORING_ACTIVE:
        status_text = "🟢 <b>Автопроверка почты ВОЗОБНОВЛЕНА!</b>"
    else:
        status_text = "⏸ <b>Автопроверка почты ПРИОСТАНОВЛЕНА!</b>"

    await callback.answer("Статус мониторинга изменён")
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard())
    await callback.message.answer(status_text, parse_mode="HTML")


@dp.callback_query(F.data == "check_mail")
async def callback_check_mail(callback: types.CallbackQuery):
    try:
        await callback.answer("Сканирую ящик...")
    except Exception:
        pass

    status_msg = await callback.message.answer("⏳ Сканирую почтовый ящик, подождите...")
    total, important, deleted = await check_and_process_emails()

    response = (
        f"✅ <b>Ручная проверка завершена!</b>\n\n"
        f"• Найдено непрочитанных: <b>{total}</b>\n"
        f"• Обработано важных: <b>{important}</b>\n"
        f"• Удалено ненужных: <b>{deleted}</b>"
    )

    await status_msg.delete()
    await callback.message.answer(response, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.callback_query(F.data == "status_info")
async def callback_status_info(callback: types.CallbackQuery):
    await callback.answer()

    def _get_unread_count():
        def list_req():
            return gmail_service.users().messages().list(userId="me", q="is:unread").execute()

        results = execute_with_backoff(list_req)
        return len(results.get("messages", []))

    unread_count = await asyncio.to_thread(_get_unread_count)
    now = datetime.now().strftime("%H:%M:%S")
    status_str = "🟢 Активен (24/7)" if IS_MONITORING_ACTIVE else "⏸ Пауза (Приостановлен)"

    info_text = (
        f"📊 <b>Состояние мониторинга Gmail</b>\n\n"
        f"<b>Статус:</b> {status_str}\n"
        f"🕒 <b>Время проверки:</b> {now}\n"
        f"📩 <b>Непрочитанных в ящике:</b> {unread_count}\n\n"
        f"🔑 <b>Важные слова:</b> {', '.join(IMPORTANT_KEYWORDS[:5])}...\n"
        f"🗑 <b>Фильтр спама:</b> {', '.join(UNWANTED_KEYWORDS[:5])}..."
    )
    await callback.message.answer(info_text, parse_mode="HTML", reply_markup=get_main_keyboard())


@dp.callback_query(F.data == "send_email_start")
async def start_email_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SendEmailState.waiting_for_to)
    await callback.message.answer(
        "✉️ <b>Ввод получателя</b>\n\nВведите email адрес получателя (например, <code>example@gmail.com</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )


@dp.callback_query(F.data == "cancel_send")
async def cancel_email_form(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Отменено")
    await state.clear()
    await callback.message.answer("❌ Ввод и отправка письма отменены.", reply_markup=get_main_keyboard())


@dp.message(SendEmailState.waiting_for_to)
async def process_to(message: types.Message, state: FSMContext):
    email_to = message.text.strip()
    if "@" not in email_to or "." not in email_to:
        await message.answer("⚠️ Непохоже на корректный Email. Попробуйте еще раз:", reply_markup=get_cancel_keyboard())
        return

    await state.update_data(to=email_to)
    await state.set_state(SendEmailState.waiting_for_subject)
    await message.answer("📌 Теперь введите <b>тему письма</b>:", parse_mode="HTML", reply_markup=get_cancel_keyboard())


@dp.message(SendEmailState.waiting_for_subject)
async def process_subject(message: types.Message, state: FSMContext):
    await state.update_data(subject=message.text.strip())
    await state.set_state(SendEmailState.waiting_for_body)
    await message.answer("📝 Введите <b>текст сообщения</b>:", parse_mode="HTML", reply_markup=get_cancel_keyboard())


@dp.message(SendEmailState.waiting_for_body)
async def process_body(message: types.Message, state: FSMContext):
    await state.update_data(body=message.text.strip())
    await state.set_state(SendEmailState.confirm_send)

    data = await state.get_data()

    preview_text = (
        f"📋 <b>Проверьте данные перед отправкой:</b>\n\n"
        f"<b>Кому:</b> <code>{html.escape(data['to'])}</code>\n"
        f"<b>Тема:</b> {html.escape(data['subject'])}\n"
        f"<b>Текст:</b>\n{html.escape(data['body'])}\n"
    )

    await message.answer(preview_text, parse_mode="HTML", reply_markup=get_confirm_keyboard())


@dp.callback_query(SendEmailState.confirm_send, F.data == "confirm_send")
async def confirm_and_send(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Отправка...")
    data = await state.get_data()

    try:
        await send_gmail_message(data["to"], data["subject"], data["body"])
        await state.clear()
        await callback.message.answer(
            "🚀 <b>Письмо успешно отправлено!</b>", parse_mode="HTML", reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке письма: {e}", reply_markup=get_main_keyboard())
        await state.clear()


async def auto_check_loop():
    while True:
        if IS_MONITORING_ACTIVE:
            await check_and_process_emails()
        await asyncio.sleep(CHECK_INTERVAL)


async def main():
    global gmail_service
    gmail_service = await asyncio.to_thread(authenticate_gmail)
    print("Успешное подключение к Gmail API!")
    print("Запуск бота...")

    asyncio.create_task(auto_check_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
