from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "rozetka" / "rozetka_feed.xml"


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def get_text(element: ET.Element | None, tag_name: str, default: str = "") -> str:
    if element is None:
        return default

    child = element.find(tag_name)
    if child is None or child.text is None:
        return default

    return child.text.strip()


def get_images(element: ET.Element) -> list[str]:
    return [img.text.strip() for img in element.findall("image") if img.text]


def get_params(element: ET.Element) -> list[ET.Element]:
    return element.findall("param")


def parse_price(value: str) -> str:
    value = safe_text(value).replace(",", ".")
    try:
        return str(int(round(float(value))))
    except ValueError:
        return "0"


def normalize_available(value: str) -> str:
    return "true" if safe_text(value).lower() == "true" else "false"


def convert_stock_quantity(quantity_in_stock: str) -> tuple[str, str]:
    try:
        qty = int(float(safe_text(quantity_in_stock).replace(",", ".")))
    except ValueError:
        qty = 0

    if qty > 0:
        return "10", "true"
    return "0", "false"


def build_root() -> tuple[ET.Element, ET.Element]:
    root = ET.Element("yml_catalog")
    root.set("date", datetime.now().strftime("%Y-%m-%d %H:%M"))

    shop = ET.SubElement(root, "shop")

    ET.SubElement(shop, "name").text = "Rozetka Feed"
    ET.SubElement(shop, "company").text = "Rozetka Feed"
    ET.SubElement(shop, "url").text = "https://example.com/"

    currencies = ET.SubElement(shop, "currencies")
    currency = ET.SubElement(currencies, "currency")
    currency.set("id", "UAH")
    currency.set("rate", "1")

    offers = ET.SubElement(shop, "offers")

    return root, offers


def append_param_with_multilang(offer: ET.Element, source_param: ET.Element) -> None:
    param_name = safe_text(source_param.get("name"))
    if not param_name:
        return

    values = source_param.findall("value")
    if values:
        for value_el in values:
            value_text = safe_text(value_el.text)
            if not value_text:
                continue

            new_param = ET.SubElement(offer, "param")
            new_param.set("name", param_name)

            lang = safe_text(value_el.get("lang"))
            if lang == "uk":
                new_param.set("lang", "ua")
            elif lang:
                new_param.set("lang", lang)

            new_param.text = value_text
        return

    text_value = safe_text(source_param.text)
    if text_value:
        new_param = ET.SubElement(offer, "param")
        new_param.set("name", param_name)
        new_param.text = text_value


def build_offer(item: ET.Element, offers: ET.Element) -> None:
    vendor_code = get_text(item, "vendorCode")
    product_id = safe_text(item.get("id"))
    name = get_text(item, "name")
    name_ua = get_text(item, "name_ua")
    description = get_text(item, "description")
    description_ua = get_text(item, "description_ua")
    vendor = get_text(item, "vendor")
    url = get_text(item, "url")
    currency_id = get_text(item, "currencyId", "UAH")
    raw_price = get_text(item, "price")
    barcode = get_text(item, "barcode")
    quantity_in_stock = get_text(item, "quantity_in_stock")
    supplier_available = normalize_available(get_text(item, "available"))

    stock_quantity, stock_available = convert_stock_quantity(quantity_in_stock)

    if supplier_available == "false":
        stock_quantity = "0"
        stock_available = "false"

    offer = ET.SubElement(offers, "offer")
    offer.set("id", vendor_code if vendor_code else product_id)
    offer.set("available", stock_available)

    ET.SubElement(offer, "price").text = parse_price(raw_price)
    ET.SubElement(offer, "currencyId").text = currency_id or "UAH"
    ET.SubElement(offer, "vendor").text = vendor
    ET.SubElement(offer, "article").text = vendor_code
    ET.SubElement(offer, "stock_quantity").text = stock_quantity

    if name:
        ET.SubElement(offer, "name").text = name

    if name_ua:
        ET.SubElement(offer, "name_ua").text = name_ua

    if description:
        ET.SubElement(offer, "description").text = description

    if description_ua:
        ET.SubElement(offer, "description_ua").text = description_ua

    if url:
        ET.SubElement(offer, "url").text = url

    if barcode:
        ET.SubElement(offer, "barcode").text = barcode

    for image_url in get_images(item):
        ET.SubElement(offer, "picture").text = image_url

    for source_param in get_params(item):
        append_param_with_multilang(offer, source_param)


def export_rozetka_feed() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Файл не знайдено: {INPUT_FILE}")

    tree = ET.parse(INPUT_FILE)
    source_root = tree.getroot()

    source_items = source_root.findall(".//items/item")
    print(f"Знайдено товарів у фіді постачальника: {len(source_items)}")

    root, offers_el = build_root()

    exported_count = 0
    for item in source_items:
        build_offer(item, offers_el)
        exported_count += 1

    result_tree = ET.ElementTree(root)
    ET.indent(result_tree, space="  ", level=0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result_tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Експортовано товарів для Rozetka: {exported_count}")
    print(f"Готовий файл збережено: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_rozetka_feed()