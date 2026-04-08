
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from parse_local_feed import parse_local_feed
from pricing import calculate_price


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "epicentr_updates.xml"


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_available(value: object) -> str:
    value_str = safe_text(value).lower()
    return "true" if value_str == "true" else "false"


def build_feed(products: list[dict]) -> ET.Element:
    root = ET.Element("yml_catalog")
    root.set("date", datetime.now().strftime("%Y-%m-%d %H:%M"))

    offers = ET.SubElement(root, "offers")

    exported_count = 0

    for product in products:
        vendor_code = safe_text(product.get("vendor_code"))
        available = normalize_available(product.get("available"))
        category_id = safe_text(product.get("category_id"))
        original_price = float(product.get("price", 0) or 0)

        if not vendor_code:
            continue

        if original_price <= 0:
            continue

        final_price = calculate_price(
            original_price=original_price,
            category_id=category_id,
        )

        offer = ET.SubElement(offers, "offer")
        offer.set("id", vendor_code)
        offer.set("available", available)

        ET.SubElement(offer, "price").text = str(int(final_price))

        exported_count += 1

    print(f"Експортовано товарів для оновлення: {exported_count}")
    return root


def export_feed() -> None:
    products = parse_local_feed()
    print(f"Знайдено товарів для оновлення: {len(products)}")

    root = build_feed(products)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Готовий файл збережено: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_feed()
