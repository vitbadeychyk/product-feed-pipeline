
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from parse_local_feed import parse_local_feed
from pricing import calculate_price


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "processed_feed.xml"


def build_feed(products: list[dict]) -> ET.Element:
    root = ET.Element("items")

    for product in products:
        item = ET.SubElement(root, "item")

        ET.SubElement(item, "id").text = str(product["id"])
        ET.SubElement(item, "vendorCode").text = product["vendor_code"]
        ET.SubElement(item, "name").text = product["name"]
        ET.SubElement(item, "categoryId").text = product["category_id"]
        ET.SubElement(item, "available").text = product["available"]

        recalculated_price = calculate_price(
            original_price=product["price"],
            category_id=product["category_id"],
        )
        ET.SubElement(item, "price").text = str(recalculated_price)

    return root


def export_feed() -> None:
    products = parse_local_feed()
    root = build_feed(products)

    tree = ET.ElementTree(root)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"✅ Готовий фід збережено: {OUTPUT_FILE}")
    print(f"📦 Кількість товарів: {len(products)}")


if __name__ == "__main__":
    export_feed()
