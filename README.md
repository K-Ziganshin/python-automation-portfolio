# Python Automation Portfolio

Small, working automation projects: Telegram bots, web monitoring and API integrations.
Author: [Kirill Ziganshin](https://ziganshinkirill.pro/)

![CI](https://github.com/K-Ziganshin/python-automation-portfolio/actions/workflows/ci.yml/badge.svg)

| Project | Stack | What it does |
|---|---|---|
| [`gmail-telegram-bot`](gmail-telegram-bot) | Python, aiogram 3, Gmail API (OAuth2) | Watches a mailbox, forwards important mail to Telegram, trashes promo mail, sends mail from the bot |
| [`avito-apartment-monitor`](avito-apartment-monitor) | Python, Selenium, Telegram Bot API | Polls a classifieds search, filters by blacklist, notifies about new listings |
| [`sheet-schedule-notifier`](sheet-schedule-notifier) | Python, requests, Google Sheets (CSV export) | Extracts one person's schedule from a shared sheet and sends it to Telegram |

## Project descriptions

<!-- TODO (author): add a short description and screenshots for each project here -->

## Engineering notes

- **No secrets in the repo.** All tokens and IDs come from environment variables (`.env`, see each `.env.example`); `.gitignore` blocks `.env`, `credentials.json`, `token.json`.
- **Owner-only bot.** Telegram handlers ignore any chat except the configured owner.
- **Safe by default.** Unwanted mail is moved to Trash (recoverable), not permanently deleted.
- **Resilient API usage.** Exponential backoff on Gmail quota errors (403/429); request timeouts everywhere.
- **Tested logic.** Pure logic is separated from I/O and unit-tested with pytest.
- **CI.** GitHub Actions runs `ruff` and `pytest` on every push/PR; Dependabot keeps dependencies current.

## Run

```bash
cd <project-folder>
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
copy .env.example .env                             # fill in your own values
python bot.py                                      # or monitor.py / schedule_notifier.py
```

Gmail bot additionally needs your own `credentials.json` (Google Cloud Console, OAuth client of type "Desktop app") placed next to `bot.py`.

## Develop

```bash
pip install -r requirements-dev.txt
ruff check . && pytest
```

## Disclaimer

The listing monitor is for personal use; follow the terms of service of any site you query.

License: MIT
