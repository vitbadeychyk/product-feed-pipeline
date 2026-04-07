
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"


def get_text(element: ET.Element | None, tag_name: str, default: str = "") -> str:
    if element is None:
        return default

    child = element.find(tag_name)
    if child is None or child.text is None:
        return default

    return child.text.strip()


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

    for offer in root.findall(".//offer"):
        product = {
            "id": offer.get("id", "").strip(),
            "vendor_code": get_text(offer, "vendorCode"),
            "name": get_text(offer, "name"),
            "price": parse_price(get_text(offer, "price")),
            "category_id": get_text(offer, "categoryId"),
            "available": offer.get("available", "").strip(),
        }
        products.append(product)

    return products


if __name__ == "__main__":
    items = parse_local_feed()
    print(f"Знайдено товарів: {len(items)}")

    for item in items[:5]:
        print(item)
