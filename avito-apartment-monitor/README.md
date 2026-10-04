# Listing monitor

Selenium (undetected-chromedriver) polls a search URL every 2.5-4 min, skips blacklisted
metro stations and sends new listings to Telegram. `/stop` and `/start` control it from the chat.

Required env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SEARCH_URL`; optional `BLACKLIST_METRO`.
