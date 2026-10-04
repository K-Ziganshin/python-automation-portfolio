"""Reads a shared Google Sheet (CSV export) and sends one person's schedule to Telegram."""

import csv
import io
import os

import requests
from dotenv import load_dotenv


def find_row(rows: list[list[str]], name: str) -> list[str] | None:
    """Return the first row containing `name` in any cell."""
    return next((row for row in rows if any(name in cell for cell in row)), None)


def build_schedule(header: list[str], row: list[str]) -> list[str]:
    """Pair each date in the header with the person's non-empty mark."""
    return [f"{date} - {mark}" for date, mark in zip(header, row, strict=False) if mark.strip()]


def fetch_rows(sheet_id: str) -> list[list[str]]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return list(csv.reader(io.StringIO(response.content.decode("utf-8"))))


def main() -> None:
    load_dotenv()
    sheet_id = os.environ["SHEET_ID"]
    name = os.environ["TARGET_NAME"]
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    rows = fetch_rows(sheet_id)
    row = find_row(rows, name)
    if row is None:
        raise SystemExit(f"'{name}' not found in the sheet")

    lines = build_schedule(rows[1], row)  # dates are in the second row of the sheet
    text = f"Schedule for {name}:\n" + "\n".join(lines)
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=15,
    ).raise_for_status()
    print("Sent.")


if __name__ == "__main__":
    main()
