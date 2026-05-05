import os
import re
import requests
import xml.etree.ElementTree as ET
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================
# НАЛАШТУВАННЯ
# ==========================

SHEET_ID = "1ulL_H1YBezBijlUw8LPCe-2Bl9ay3imao_RPKfeQDMA"
XML_URL = os.environ.get("XML_URL")

if not XML_URL:
    raise ValueError("Не знайдено секрет XML_URL")

TARGET_CATEGORY_ID = "77"

# ==========================
# ФУНКЦІЇ
# ==========================

def round_to_100(value):
    return int((value + 99) // 100 * 100)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def detect_type(name_ua: str, base_price: float) -> str:
    """
    Визначає Тип на основі name_ua.
    Спецправило:
    якщо назва загальна ("електромобіль" / "машина") і ціна < 5000,
    то це Толокари, інакше Автомобілі.
    """
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


def safe_text(element, tag, default=""):
    value = element.findtext(tag, default=default)
    return value.strip() if isinstance(value, str) else default


# ==========================
# GOOGLE
# ==========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "service_account.json", scope
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

print("✅ Підключено до Google Таблиці")

# ==========================
# ЧИТАЄМО XML
# ==========================

response = requests.get(XML_URL, timeout=30)
response.raise_for_status()

root = ET.fromstring(response.content)

xml_products = {}
category_77_products = {}

for item in root.findall(".//item"):
    vendor_code = safe_text(item, "vendorCode")
    quantity_text = safe_text(item, "quantity_in_stock", "0")
    price_text = safe_text(item, "price", "0")
    category_id = safe_text(item, "categoryId", "")
    name_ua = safe_text(item, "name_ua")
    description_ua = safe_text(item, "description_ua")

    # ЗБИРАЄМО ВСІ ФОТО
    images = [img.text.strip() for img in item.findall("image") if img.text and img.text.strip()]
    image_url = ";".join(images)

    if not vendor_code:
        continue

    try:
        quantity = int(quantity_text)
    except Exception:
        quantity = 0

    try:
        base_price = float(price_text.replace(",", "."))
    except Exception:
        base_price = 0

    price = round_to_100(base_price)
    old_price = round_to_100(base_price * 1.3)
    product_type = detect_type(name_ua, base_price)

    product_data = {
        "vendor_code": vendor_code,
        "quantity": quantity,
        "price": price,
        "old_price": old_price,
        "category_id": category_id,
        "name_ua": name_ua,
        "image": image_url,
        "description_ua": description_ua,
        "type": product_type,
    }

    xml_products[vendor_code] = product_data

    if category_id == TARGET_CATEGORY_ID:
        category_77_products[vendor_code] = product_data

print(f"✅ Знайдено {len(xml_products)} товарів у XML")
print(f"✅ Знайдено {len(category_77_products)} товарів у категорії {TARGET_CATEGORY_ID}")

# ==========================
# ОНОВЛЕННЯ ТАБЛИЦІ
# ==========================

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

# Оновлення існуючих рядків
for i, row in enumerate(data):
    sku_sheet = str(row.get("Артикул", "")).strip()
    row_index = i + 1

    if sku_sheet:
        existing_skus.add(sku_sheet)

    if sku_sheet in xml_products:
        product = xml_products[sku_sheet]

        quantity = product["quantity"]
        price = product["price"]
        old_price = product["old_price"]
        availability = "В наявності" if quantity > 0 else "Не в наявності"

        all_values[row_index][col_stock] = str(quantity)
        all_values[row_index][col_status] = availability
        all_values[row_index][col_price] = str(price)
        all_values[row_index][col_old_price] = str(old_price)

# ==========================
# ДОДАЄМО НОВІ АРТИКУЛИ З categoryId = 77
# ==========================

added_count = 0

for sku, product in category_77_products.items():
    if sku in existing_skus:
        continue

    quantity = product["quantity"]
    price = product["price"]
    old_price = product["old_price"]
    availability = "В наявності" if quantity > 0 else "Не в наявності"

    name_ua = product["name_ua"]
    image_url = product["image"]
    description_ua = product["description_ua"]
    product_type = product["type"]

    new_row = [""] * len(headers)

    new_row[col_sku] = sku
    new_row[col_name] = name_ua
    new_row[col_name_ua] = name_ua
    new_row[col_type] = product_type
    new_row[col_image] = image_url
    new_row[col_description_ua] = description_ua
    new_row[col_stock] = str(quantity)
    new_row[col_status] = availability
    new_row[col_price] = str(price)
    new_row[col_old_price] = str(old_price)

    all_values.append(new_row)
    existing_skus.add(sku)
    added_count += 1

print(f"➕ Додано нових артикулів у таблицю: {added_count}")

# ==========================
# ЗАПИС У ТАБЛИЦЮ
# ==========================

print("🔄 Масове оновлення...")

sheet.update("A1", all_values)

print("🎉 Синхронізація завершена!")
