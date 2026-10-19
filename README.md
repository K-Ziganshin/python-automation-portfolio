# Python Automation Portfolio

Small automation tools I built for real everyday tasks: Telegram bots, inbox processing, web monitoring and Google Sheets integration.
Each project lives in its own repository with tests, CI and setup instructions.
Author: [Kirill Ziganshin](https://ziganshinkirill.pro/)

| Project | What it does | Stack | Tests |
|---|---|---|---|
| [**gmail-telegram-bot**](https://github.com/K-Ziganshin/gmail-telegram-bot) | Watches a Gmail inbox: important mail goes to Telegram, promo mail to Trash, replies can be sent from the chat. Handled about 150 e-mails a day. | Python, aiogram 3, Gmail API (OAuth 2.0), asyncio | 27, Gmail mocked |
| [**avito-apartment-monitor**](https://github.com/K-Ziganshin/avito-apartment-monitor) | Checks a rental search every 2.5–4 min and sends new listings to Telegram, skipping blacklisted metro stations. | Python, Selenium, undetected-chromedriver, Telegram Bot API | 11, no browser needed |
| [**sheet-schedule-notifier**](https://github.com/K-Ziganshin/sheet-schedule-notifier) | Finds one person's shifts in a shared Google Sheet and sends them to Telegram. | Python, requests, CSV export | 6 |
| [**industrial-cobot-cell-design**](https://github.com/K-Ziganshin/industrial-cobot-cell-design) | Feasibility study of a screw-driving cobot cell: layout, 2D vision, ISO 10218-2 safety, FMEA, ROI. | Engineering documentation | — |

## Common engineering practices
- **No secrets in git.** Tokens and ids come from `.env` (see each `.env.example`); `.env`, `credentials.json`, `token.json` are git-ignored.
- **Pure logic separated from I/O**, so the core is unit-tested without network, browser or credentials.
- **Owner-only bots.** Telegram commands from any other chat are ignored.
- **Safe by default.** Unwanted mail goes to Trash (recoverable), nothing is deleted permanently.
- **Resilient API usage.** Timeouts on every request, exponential backoff on Gmail quota errors.
- **Logging, not prints;** tokens and e-mail contents never reach the logs.
- **CI** on every push: `ruff` lint + format check and `pytest` with coverage on Python 3.11–3.13; Dependabot keeps dependencies current.

## About
I'm a fourth-year information security student (Chelyabinsk Radio Engineering College) working on Python automation and AI integrations.
More about me, my other projects and contacts: **[ziganshinkirill.pro](https://ziganshinkirill.pro/)**.
