from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from parse_local_feed import parse_local_feed
from pricing import calculate_price
from pricing import calculate_old_price

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "output" / "epicentr_feed.xml"


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

    for product in products:
        vendor_code = safe_text(product.get("vendor_code"))
        product_id = safe_text(product.get("id"))
        available = normalize_available(product.get("available"))
        category_id = safe_text(product.get("category_id"))
        original_price = float(product.get("price", 0) or 0)

        final_price = calculate_price(
            original_price=original_price,
            category_id=category_id,
        )

        offer = ET.SubElement(offers, "offer")
        offer.set("id", vendor_code if vendor_code else product_id)
        offer.set("available", available)

        ET.SubElement(offer, "price").text = str(int(final_price))
        old_price = calculate_old_price(final_price)
        ET.SubElement(offer, "price_old").text = str(int(old_price))
        

        category = ET.SubElement(offer, "category")
        category.set("code", category_id)
        category.text = category_id

        name_ru = ET.SubElement(offer, "name")
        name_ru.set("lang", "ru")
        name_ru.text = safe_text(product.get("name"))

        name_ua = ET.SubElement(offer, "name")
        name_ua.set("lang", "ua")
        name_ua.text = safe_text(product.get("name_ua")) or safe_text(product.get("name"))

        for image_url in product.get("images", []):
            image_url = safe_text(image_url)
            if image_url:
                ET.SubElement(offer, "picture").text = image_url

        description_ru = ET.SubElement(offer, "description")
        description_ru.set("lang", "ru")
        description_ru.text = safe_text(product.get("description"))

        description_ua = ET.SubElement(offer, "description")
        description_ua.set("lang", "ua")
        description_ua.text = safe_text(product.get("description_ua")) or safe_text(product.get("description"))

        vendor_name = safe_text(product.get("vendor"))
        vendor = ET.SubElement(offer, "vendor")
        vendor.set("code", vendor_name if vendor_name else "unknown")
        vendor.text = vendor_name

        sku_param = ET.SubElement(offer, "param")
        sku_param.set("name", "Артикул")
        sku_param.text = vendor_code if vendor_code else product_id

        barcode = safe_text(product.get("barcode"))
        if barcode:
            barcode_param = ET.SubElement(offer, "param")
            barcode_param.set("name", "Штрихкод")
            barcode_param.text = barcode

        quantity_in_stock = safe_text(product.get("quantity_in_stock"))
        if quantity_in_stock:
            quantity_param = ET.SubElement(offer, "param")
            quantity_param.set("name", "Кількість на складі")
            quantity_param.text = quantity_in_stock

        url = safe_text(product.get("url"))
        if url:
            url_param = ET.SubElement(offer, "param")
            url_param.set("name", "Посилання")
            url_param.text = url

    return root


def export_feed() -> None:
    products = parse_local_feed()
    print(f"Знайдено товарів для експорту: {len(products)}")

    root = build_feed(products)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Готовий файл збережено: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_feed()
