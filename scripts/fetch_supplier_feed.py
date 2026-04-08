
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state" / "fetch_meta.json"
RAW_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"

# ⚠️ ВСТАВ СЮДИ СВОЄ ПОСИЛАННЯ ПОСТАЧАЛЬНИКА
SUPPLIER_FEED_URL = os.getenv("SUPPLIER_FEED_URL")

FETCH_INTERVAL = timedelta(hours=2)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"last_fetch_at": None}

    with STATE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def can_fetch(last_fetch_at: datetime | None) -> bool:
    if last_fetch_at is None:
        return True

    now = datetime.now(timezone.utc)
    return now - last_fetch_at >= FETCH_INTERVAL


def fetch_supplier_feed() -> None:
    state = load_state()
    last_fetch_at = parse_timestamp(state.get("last_fetch_at"))

    if not can_fetch(last_fetch_at):
        next_allowed_at = last_fetch_at + FETCH_INTERVAL
        print(f"⏱ Пропуск. Наступний дозволений запит: {next_allowed_at.isoformat()}")
        return

    print("⬇️ Завантаження фіда постачальника...")
    response = requests.get(SUPPLIER_FEED_URL, timeout=120)
    response.raise_for_status()

    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_bytes(response.content)

    now = datetime.now(timezone.utc)
    save_state({"last_fetch_at": now.isoformat()})

    print(f"✅ Фід збережено: {RAW_FILE}")
    print(f"🕒 Час: {now.isoformat()}")


if __name__ == "__main__":
    fetch_supplier_feed()
