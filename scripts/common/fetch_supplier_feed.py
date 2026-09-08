from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[2]
STATE_FILE = BASE_DIR / "state" / "fetch_meta.json"
RAW_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"

# Посилання на фід постачальника
SUPPLIER_FEED_URL = "https://metr-plus.com.ua/export.php?token=0333b5177032408cdc24c96ec2962f4d&action=4&udepartment=992&issingle=1&isrrc=0&tofile=1&lang=uk"

FETCH_INTERVAL = timedelta(hours=4)


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


def validate_xml_response(response: requests.Response) -> None:
    """Перевіряє, що сервер повернув саме коректний XML, а не HTML/сторінку помилки."""
    content = response.content
    content_type = response.headers.get("Content-Type", "").lower()

    if not content or not content.strip():
        raise RuntimeError("Supplier feed is empty")

    # HTML інколи приходить навіть зі статусом HTTP 200, тому Content-Type недостатньо.
    head = content[:4096].lstrip().lower()
    html_markers = (
        b"<!doctype html",
        b"<html",
        b"<head",
        b"<body",
    )

    # Не довіряємо Content-Type: деякі сервери помилково віддають XML як text/html.
    # Блокуємо тільки тоді, коли сам вміст справді схожий на HTML.
    if any(marker in head for marker in html_markers):
        preview = content[:300].decode(response.encoding or "utf-8", errors="replace")
        preview = " ".join(preview.split())
        raise RuntimeError(
            "Supplier returned HTML instead of XML. "
            f"Content-Type: {content_type or 'unknown'}. "
            f"Response preview: {preview}"
        )

    # Фінальна перевірка: документ повинен реально парситися як XML.
    try:
        root = ET.fromstring(content)
        if root.tag.lower().split("}")[-1] != "shop":
            raise RuntimeError(
                f"Unexpected XML root element: <{root.tag}>. Expected <shop>."
            )
    except ET.ParseError as exc:
        preview = content[:300].decode(response.encoding or "utf-8", errors="replace")
        preview = " ".join(preview.split())
        raise RuntimeError(
            "Supplier response is not valid XML. "
            f"XML parse error: {exc}. "
            f"Response preview: {preview}"
        ) from exc


def fetch_supplier_feed() -> None:
    state = load_state()
    last_fetch_at = parse_timestamp(state.get("last_fetch_at"))

    if not can_fetch(last_fetch_at):
        next_allowed_at = last_fetch_at + FETCH_INTERVAL
        print(f"Skip. Next allowed fetch: {next_allowed_at.isoformat()}")
        return

    print("Downloading supplier feed...")
    response = requests.get(SUPPLIER_FEED_URL, timeout=120)
    response.raise_for_status()

    # ВАЖЛИВО: спочатку перевіряємо відповідь, і лише після цього перезаписуємо XML.
    # Якщо тут помилка, програма завершується з кодом 1, BAT переходить у :error,
    # а git add/commit/push не виконуються.
    validate_xml_response(response)

    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_bytes(response.content)

    now = datetime.now(timezone.utc)
    save_state({"last_fetch_at": now.isoformat()})

    print(f"OK Feed saved: {RAW_FILE}")
    print(f"Time: {now.isoformat()}")


if __name__ == "__main__":
    try:
        fetch_supplier_feed()
    except Exception as exc:
        print(f"ERROR: Supplier feed was NOT updated: {exc}")
        raise SystemExit(1)
