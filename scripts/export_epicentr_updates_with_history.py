
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from parse_local_feed import parse_local_feed
from pricing import calculate_price


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "epicentr_updates.xml"
STATE_FILE = BASE_DIR / "state" / "known_products.json"


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_available(value: object) -> str:
    value_str = safe_text(value).lower()
    return "true" if value_str == "true" else "false"

def convert_availability(value: str) -> str:
    if value == "true":
        return "in_stock"
    return "out_of_stock"


def calculate_old_price(price: int) -> int:
    return int(price * 1.3)

def load_known_products() -> dict:
    if not STATE_FILE.exists():
        return {"products": {}}

    with STATE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_known_products(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_current_products(products: list[dict]) -> dict[str, dict]:
    current_products: dict[str, dict] = {}

    for product in products:
        vendor_code = safe_text(product.get("vendor_code"))
        if not vendor_code:
            continue

        original_price = float(product.get("price", 0) or 0)
        if original_price <= 0:
            continue

        category_id = safe_text(product.get("category_id"))
        final_price = calculate_price(
            original_price=original_price,
            category_id=category_id,
        )

        current_products[vendor_code] = {
            "id": vendor_code,
            "available": normalize_available(product.get("available")),
            "price": int(final_price),
            "category_id": category_id,
            "last_seen_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    return current_products


def merge_with_history(current_products: dict[str, dict], known_state: dict) -> dict[str, dict]:
    known_products = known_state.get("products", {})

    # 1. Оновлюємо / додаємо поточні товари
    for product_id, product_data in current_products.items():
        known_products[product_id] = product_data

    # 2. Якщо товар був раніше, але зараз зник — ставимо available=false
    current_ids = set(current_products.keys())

    for product_id, product_data in known_products.items():
        if product_id not in current_ids:
            product_data["available"] = "false"

    return known_products


def build_feed(all_products: dict[str, dict]) -> ET.Element:
    root = ET.Element("yml_catalog")
    root.set("date", datetime.now().strftime("%Y-%m-%d %H:%M"))

    offers = ET.SubElement(root, "offers")

    exported_count = 0

    for product_id, product_data in sorted(all_products.items()):
        available_value = normalize_available(product_data.get("available"))
        availability_value = convert_availability(available_value)
        price_value = int(product_data.get("price", 0))
        old_price_value = calculate_old_price(price_value)

        offer = ET.SubElement(offers, "offer")
        offer.set("id", safe_text(product_data.get("id")))
        offer.set("available", available_value)

        ET.SubElement(offer, "price").text = str(price_value)
        ET.SubElement(offer, "price_old").text = str(old_price_value)
        ET.SubElement(offer, "availability").text = availability_value

        exported_count += 1

    print(f"Експортовано товарів для оновлення: {exported_count}")
    return root


def export_feed() -> None:
    products = parse_local_feed()
    print(f"Знайдено товарів у поточному фіді: {len(products)}")

    known_state = load_known_products()
    current_products = build_current_products(products)
    merged_products = merge_with_history(current_products, known_state)

    save_known_products({"products": merged_products})

    root = build_feed(merged_products)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Готовий файл збережено: {OUTPUT_FILE}")
    print(f"Активних зараз у фіді постачальника: {len(current_products)}")
    print(f"Усього відомих товарів: {len(merged_products)}")


if __name__ == "__main__":
    export_feed()
