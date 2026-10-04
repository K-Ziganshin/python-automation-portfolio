"""Monitors a classifieds search page and sends new listings to Telegram.

Controlled from Telegram: /stop pauses the search, /start resumes it.
For personal use only - respect the target site's terms of service.
"""

import os
import random
import threading
import time

import requests
import undetected_chromedriver as uc
from avito_filters import is_blacklisted, parse_blacklist
from dotenv import load_dotenv
from selenium.webdriver.common.by import By

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEARCH_URL = os.environ["SEARCH_URL"]
BLACKLIST = parse_blacklist(os.getenv("BLACKLIST_METRO", ""))
SEEN_FILE = "seen_ids.txt"
PROFILE_DIR = os.path.join(os.getcwd(), "chrome_profile")

is_running = True
last_update_id = 0


def send_telegram(text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text},
            timeout=15,
        ).raise_for_status()
    except requests.RequestException as exc:
        print(f"Telegram error: {type(exc).__name__}")


def poll_commands() -> None:
    """Background thread: reads /start and /stop from the owner's chat only."""
    global is_running, last_update_id
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=40,
            ).json()
            for update in resp.get("result", []):
                last_update_id = update["update_id"]
                message = update.get("message", {})
                if str(message.get("chat", {}).get("id")) != CHAT_ID:
                    continue  # ignore everyone except the owner
                command = message.get("text", "").lower()
                if command == "/stop":
                    is_running = False
                    send_telegram("Search paused")
                elif command == "/start":
                    is_running = True
                    send_telegram("Search resumed")
        except requests.RequestException:
            time.sleep(5)


def load_seen() -> set[str]:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, encoding="utf-8") as f:
        return set(f.read().splitlines())


def save_seen(ad_id: str) -> None:
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ad_id}\n")


def check_listings() -> None:
    print(f"[{time.strftime('%H:%M:%S')}] Checking...")
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--disable-notifications")
    driver = uc.Chrome(options=options)
    try:
        driver.get(SEARCH_URL)
        time.sleep(random.randint(7, 12))
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)

        seen = load_seen()
        new_count = 0
        for item in driver.find_elements(By.CSS_SELECTOR, '[data-marker="item"]'):
            ad_id = item.get_attribute("data-item-id")
            if not ad_id or ad_id in seen:
                continue
            try:
                location = item.find_element(By.CSS_SELECTOR, '[data-marker="item-location"]').text
                if is_blacklisted(location, BLACKLIST):
                    continue
                link = item.find_element(By.CSS_SELECTOR, '[data-marker="item-title"]').get_attribute("href")
                price = item.find_element(By.CSS_SELECTOR, '[data-marker="item-price"]').text
            except Exception:  # markup changed or partial card: skip it
                continue
            send_telegram(f"New listing\n{location}\n{price}\n\n{link}")
            save_seen(ad_id)
            new_count += 1
            time.sleep(random.uniform(0.5, 1.5))
        print(f"Done. New: {new_count}")
    finally:
        driver.quit()


def main() -> None:
    threading.Thread(target=poll_commands, daemon=True).start()
    send_telegram("Search started. Send /stop to pause.")
    while True:
        if is_running:
            try:
                check_listings()
            except Exception as exc:
                print(f"Cycle error: {type(exc).__name__}: {exc}")
        time.sleep(random.randint(150, 250))


if __name__ == "__main__":
    main()
