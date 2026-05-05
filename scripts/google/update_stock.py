from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import gspread
from oauth2client.service_account import ServiceAccountCredentials


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_FILE = BASE_DIR / "data" / "raw" / "supplier_feed.xml"

SHEET_ID = "1ulL_H1YBezBijlUw8LPCe-2Bl9ay3imao_RPKfeQDMA"
TARGET_CATEGORY_ID = "77"


def round_to_100(value: float) -> int:
    return int((value + 99) // 100 * 100)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def detect_type(name_ua: str, base_price: float) -> str:
    name = normalize_spaces(name_ua).lower()

    if "мотоцикл" in name:
        return "Мотоцикли"
    if "электрокарт" in name or "електрокарт" in name or "карт" in name:
        return "Електрокарти"
    if "квадроцикл" in name:
        return "Квадроцикли"
    if "трактор" in name:
        return "Трактори"
    if "баггі" in name or "багги" in name:
        return "Баггі"
    if "джип" in name:
        return "Джипи"
    if "вантажівка" in name or "грузовик" in name:
        return "Вантажівки"

    if "машина" in name or "електромобіль" in name or "электромобиль" in name:
        if base_price < 5000:
            return "Толокари"
        return "Автомобілі"

    return ""


def safe_text(element: ET.Element, tag: str, default: str = "") -> str:
    value = element.findtext(tag, default=default)
    return value.strip() if isinstance(value, str) else default


def parse_float(value: str) -> float:
    try:
        return float(value.replace(",", ".").strip())
    except Exception:
        return 0.0


def parse_int(value: str) -> int:
    try:
        return int(float(value.replace(",", ".").strip()))
    except Exception:
        return 0


def read_xml_products() -> tuple[dict, dict]:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"XML файл не знайдено: {RAW_FILE}")

    tree = ET.parse(RAW_FILE)
    root = tree.getroot()

    xml_products = {}
    category_77_products = {}

    for item in root.findall(".//item"):
        vendor_code = safe_text(item, "vendorCode")
        if not vendor_code:
            continue

        quantity = parse_int(safe_text(item, "quantity_in_stock", "0"))
        base_price = parse_float(safe_text(item, "price", "0"))
        category_id = safe_text(item, "categoryId")
        name_ua = safe_text(item, "name_ua")
        description_ua = safe_text(item, "description_ua")

        images = [
            img.text.strip()
            for img in item.findall("image")
            if img.text and img.text.strip()
        ]

        product_data = {
            "vendor_code": vendor_code,
            "quantity": quantity,
            "price": round_to_100(base_price),
            "old_price": round_to_100(base_price * 1.3),
            "category_id": category_id,
            "name_ua": name_ua,
            "image": ";".join(images),
            "description_ua": description_ua,
            "type": detect_type(name_ua, base_price),
        }

        xml_products[vendor_code] = product_data

        if category_id == TARGET_CATEGORY_ID:
            category_77_products[vendor_code] = product_data

    return xml_products, category_77_products


def main() -> None:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "service_account.json", scope
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1

    print("✅ Підключено до Google Таблиці")
    print(f"✅ Читаю локальний XML: {RAW_FILE}")

    xml_products, category_77_products = read_xml_products()

    print(f"✅ Знайдено {len(xml_products)} товарів у XML")
    print(f"✅ Знайдено {len(category_77_products)} товарів у категорії {TARGET_CATEGORY_ID}")

    data = sheet.get_all_records()
    headers = sheet.row_values(1)
    all_values = sheet.get_all_values()

    col_sku = headers.index("Артикул")
    col_name = headers.index("Назва")
    col_name_ua = headers.index("Назва (укр)")
    col_type = headers.index("Тип")
    col_image = headers.index("Зображення")
    col_description_ua = headers.index("Повний опис (UA)")
    col_stock = headers.index("Залишки")
    col_status = headers.index("Наявність")
    col_price = headers.index("Ціна")
    col_old_price = headers.index("Стара ціна")

    existing_skus = set()
    updated_count = 0

    for i, row in enumerate(data):
        sku_sheet = str(row.get("Артикул", "")).strip()
        row_index = i + 1

        if sku_sheet:
            existing_skus.add(sku_sheet)

        if sku_sheet in xml_products:
            product = xml_products[sku_sheet]

            quantity = product["quantity"]
            availability = "В наявності" if quantity > 0 else "Не в наявності"

            all_values[row_index][col_stock] = str(quantity)
            all_values[row_index][col_status] = availability
            all_values[row_index][col_price] = str(product["price"])
            all_values[row_index][col_old_price] = str(product["old_price"])

            updated_count += 1

    added_count = 0

    for sku, product in category_77_products.items():
        if sku in existing_skus:
            continue

        quantity = product["quantity"]
        availability = "В наявності" if quantity > 0 else "Не в наявності"

        new_row = [""] * len(headers)

        new_row[col_sku] = sku
        new_row[col_name] = product["name_ua"]
        new_row[col_name_ua] = product["name_ua"]
        new_row[col_type] = product["type"]
        new_row[col_image] = product["image"]
        new_row[col_description_ua] = product["description_ua"]
        new_row[col_stock] = str(quantity)
        new_row[col_status] = availability
        new_row[col_price] = str(product["price"])
        new_row[col_old_price] = str(product["old_price"])

        all_values.append(new_row)
        existing_skus.add(sku)
        added_count += 1

    print(f"🔄 Оновлено існуючих артикулів: {updated_count}")
    print(f"➕ Додано нових артикулів: {added_count}")

    sheet.update("A1", all_values)

    print("🎉 Синхронізація Google Таблиці завершена!")


if __name__ == "__main__":
    main()
