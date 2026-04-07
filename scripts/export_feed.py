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
        ET.SubElement(item, "name_ua").text = product["name_ua"]
        ET.SubElement(item, "categoryId").text = product["category_id"]
        ET.SubElement(item, "available").text = product["available"]
        ET.SubElement(item, "url").text = product["url"]
        ET.SubElement(item, "vendor").text = product["vendor"]
        ET.SubElement(item, "barcode").text = product["barcode"]
        ET.SubElement(item, "quantity_in_stock").text = product["quantity_in_stock"]
        ET.SubElement(item, "currencyId").text = product["currency_id"]
        ET.SubElement(item, "description").text = product["description"]
        ET.SubElement(item, "description_ua").text = product["description_ua"]

        recalculated_price = calculate_price(
            original_price=product["price"],
            category_id=product["category_id"],
        )
        ET.SubElement(item, "price").text = str(recalculated_price)

        for image_url in product["images"]:
            ET.SubElement(item, "image").text = image_url

    return root


def export_feed() -> None:
    products = parse_local_feed()
    print(f"Знайдено товарів для експорту: {len(products)}")

    root = build_feed(products)

    tree = ET.ElementTree(root)
    ET.indent(tree, space=" ", level=0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Готовий фід збережено: {OUTPUT_FILE}")
    print(f"Кількість товарів: {len(products)}")


if __name__ == "__main__":
    export_feed()
