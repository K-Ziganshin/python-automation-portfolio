# Gmail → Telegram bot

Async bot (aiogram 3) that checks Gmail every 60 s, classifies unread mail by keywords
(`mail_filter.py`), pushes important messages to Telegram, moves promo mail to Trash and lets
the owner compose and send mail through a confirmation dialog (FSM).

Setup: see the root README. Required env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
