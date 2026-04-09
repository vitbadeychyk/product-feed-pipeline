from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"


def get_text(element: ET.Element | None, tag_name: str, default: str = "") -> str:
    if element is None:
        return default

    child = element.find(tag_name)
    if child is None or child.text is None:
        return default

    return child.text.strip()


def get_images(element: ET.Element) -> list[str]:
    return [img.text.strip() for img in element.findall("image") if img.text]


def parse_price(value: str) -> float:
    try:
        return float(value.replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0


def parse_local_feed() -> list[dict]:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Файл не знайдено: {RAW_FILE}")

    tree = ET.parse(RAW_FILE)
    root = tree.getroot()

    products: list[dict] = []

    for item in root.findall(".//items/item"):
        product = {
            "id": item.get("id", "").strip(),
            "selling_type": item.get("selling_type", "").strip(),
            "vendor_code": get_text(item, "vendorCode"),
            "name": get_text(item, "name"),
            "name_ua": get_text(item, "name_ua"),
            "price": parse_price(get_text(item, "price")),
            "category_id": get_text(item, "categoryId"),
            "url": get_text(item, "url"),
            "quantity_in_stock": get_text(item, "quantity_in_stock"),
            "currency_id": get_text(item, "currencyId"),
            "available": get_text(item, "available"),
            "vendor": get_text(item, "vendor"),
            "barcode": get_text(item, "barcode"),
            "description": get_text(item, "description"),
            "description_ua": get_text(item, "description_ua"),
            "images": get_images(item),
        }
        products.append(product)

    return products


if __name__ == "__main__":
    items = parse_local_feed()
    print(f"Знайдено товарів: {len(items)}")
    for item in items[:5]:
        print(item)
if __name__ == "__main__":
    items = parse_local_feed()
    print(f"Знайдено товарів: {len(items)}")

    category_ids = sorted({item["category_id"] for item in items if item["category_id"]})
    print("Категорії:")
    for category_id in category_ids:
        print(category_id)
