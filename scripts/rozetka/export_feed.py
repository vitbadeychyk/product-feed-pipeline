from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "raw"
    / "supplier_feed.xml"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "rozetka"
    / "rozetka_feed.xml"
)


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()


# ============================================================
# HELPERS
# ============================================================

def safe_text(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def get_text(
    element: ET.Element | None,
    tag_name: str,
    default: str = "",
) -> str:

    if element is None:
        return default

    child = element.find(tag_name)

    if child is None or child.text is None:
        return default

    return child.text.strip()


def get_images(element: ET.Element) -> list[str]:
    return [
        img.text.strip()
        for img in element.findall("image")
        if img.text
    ]


def get_params(element: ET.Element) -> list[ET.Element]:
    return element.findall("param")


def parse_price(value: str) -> str:
    value = safe_text(value).replace(",", ".")

    try:
        return str(int(round(float(value))))

    except ValueError:
        return "0"


def normalize_available(value: str) -> str:
    return (
        "true"
        if safe_text(value).lower() == "true"
        else "false"
    )


def convert_stock_quantity(
    quantity_in_stock: str,
) -> tuple[str, str]:

    try:
        qty = int(
            float(
                safe_text(quantity_in_stock)
                .replace(",", ".")
            )
        )

    except ValueError:
        qty = 0

    if qty > 0:
        return "10", "true"

    return "0", "false"


# ============================================================
# SKU NORMALIZATION
# ============================================================

def normalize_sku(value: object) -> str:
    """
    Нормалізація артикулу для порівняння.

    Наприклад:
        "M 4259EBLR-1"
        "m 4259eblr-1"

    будуть вважатися однаковими.

    Пробіли всередині SKU НЕ видаляємо,
    щоб випадково не об'єднати різні артикули.
    """

    return safe_text(value).casefold()


# ============================================================
# LOAD DESCRIPTIONS FROM SUPABASE
# ============================================================

def load_supabase_descriptions() -> dict[str, str]:
    """
    Завантажує з Supabase:

        products.sku
        products.description

    Повертає словник:

        normalized_sku -> full_description
    """

    if not SUPABASE_URL:
        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_URL"
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_KEY"
        )

    url = f"{SUPABASE_URL}/rest/v1/products"

    headers = {
        "apikey": SUPABASE_KEY,
    }

    descriptions: dict[str, str] = {}

    page_size = 1000
    offset = 0
    total_rows = 0

    print()
    print("========================================")
    print("Завантаження описів із Supabase")
    print("========================================")

    while True:

        params = {
            "select": "sku,description",
            "order": "sku.asc",
            "limit": str(page_size),
            "offset": str(offset),
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=60,
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            raise RuntimeError(
                f"Помилка підключення до Supabase: {exc}"
            ) from exc

        try:
            rows = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "Supabase повернув некоректну JSON-відповідь"
            ) from exc

        if not isinstance(rows, list):
            raise RuntimeError(
                f"Неочікувана відповідь Supabase: {rows}"
            )

        if not rows:
            break

        total_rows += len(rows)

        for row in rows:

            if not isinstance(row, dict):
                continue

            sku = normalize_sku(
                row.get("sku")
            )

            description = safe_text(
                row.get("description")
            )

            # SKU немає
            if not sku:
                continue

            # Опис NULL або пустий
            if not description:
                continue

            descriptions[sku] = description

        print(
            f"Оброблено рядків Supabase: {total_rows}"
        )

        if len(rows) < page_size:
            break

        offset += page_size

    print(
        f"Товарів з повним description: "
        f"{len(descriptions)}"
    )

    if not descriptions:
        raise RuntimeError(
            "У Supabase не знайдено жодного товару "
            "з непорожнім description. "
            "Rozetka XML не буде перезаписаний."
        )

    return descriptions


# ============================================================
# BUILD ROOT
# ============================================================

def build_root(
    source_root: ET.Element,
) -> tuple[ET.Element, ET.Element]:

    root = ET.Element("yml_catalog")

    root.set(
        "date",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),
    )

    shop = ET.SubElement(
        root,
        "shop",
    )

    ET.SubElement(
        shop,
        "name",
    ).text = "Rozetka Feed"

    ET.SubElement(
        shop,
        "company",
    ).text = "Rozetka Feed"

    ET.SubElement(
        shop,
        "url",
    ).text = "https://example.com/"

    currencies = ET.SubElement(
        shop,
        "currencies",
    )

    currency = ET.SubElement(
        currencies,
        "currency",
    )

    currency.set(
        "id",
        "UAH",
    )

    currency.set(
        "rate",
        "1",
    )

    categories = ET.SubElement(
        shop,
        "categories",
    )

    for source_category in source_root.findall(
        ".//catalog/category"
    ):

        category_id = safe_text(
            source_category.get("id")
        )

        category_name = safe_text(
            source_category.text
        )

        if not category_id or not category_name:
            continue

        category = ET.SubElement(
            categories,
            "category",
        )

        category.set(
            "id",
            category_id,
        )

        category.text = category_name

    offers = ET.SubElement(
        shop,
        "offers",
    )

    return root, offers


# ============================================================
# PARAMS
# ============================================================

def append_param_with_multilang(
    offer: ET.Element,
    source_param: ET.Element,
) -> None:

    param_name = safe_text(
        source_param.get("name")
    )

    if not param_name:
        return

    values = source_param.findall(
        "value"
    )

    if values:

        for value_el in values:

            value_text = safe_text(
                value_el.text
            )

            if not value_text:
                continue

            new_param = ET.SubElement(
                offer,
                "param",
            )

            new_param.set(
                "name",
                param_name,
            )

            lang = safe_text(
                value_el.get("lang")
            )

            if lang == "uk":

                new_param.set(
                    "lang",
                    "ua",
                )

            elif lang:

                new_param.set(
                    "lang",
                    lang,
                )

            new_param.text = value_text

        return

    text_value = safe_text(
        source_param.text
    )

    if text_value:

        new_param = ET.SubElement(
            offer,
            "param",
        )

        new_param.set(
            "name",
            param_name,
        )

        new_param.text = text_value


# ============================================================
# BUILD OFFER
# ============================================================

def build_offer(
    item: ET.Element,
    offers: ET.Element,
    descriptions: dict[str, str],
) -> bool:

    # --------------------------------------------------------
    # ARTIKUL
    # --------------------------------------------------------

    vendor_code = get_text(
        item,
        "vendorCode"
    )

    # Якщо vendorCode відсутній,
    # ми не можемо знайти товар у Supabase
    if not vendor_code:
        return False

    normalized_vendor_code = normalize_sku(
        vendor_code
    )

    # --------------------------------------------------------
    # DESCRIPTION FROM SUPABASE
    # --------------------------------------------------------

    full_description = safe_text(
        descriptions.get(
            normalized_vendor_code,
            ""
        )
    )

    # ========================================================
    # ГОЛОВНЕ ПРАВИЛО:
    #
    # якщо повного description у Supabase немає,
    # товар НЕ потрапляє у Rozetka feed
    # ========================================================

    if not full_description:
        return False

    # --------------------------------------------------------
    # Далі практично весь твій старий код без змін
    # --------------------------------------------------------

    product_id = safe_text(
        item.get("id")
    )

    name = get_text(
        item,
        "name"
    )

    name_ua = get_text(
        item,
        "name_ua"
    )

    vendor = get_text(
        item,
        "vendor"
    )

    url = get_text(
        item,
        "url"
    )

    currency_id = get_text(
        item,
        "currencyId",
        "UAH"
    )

    category_id = get_text(
        item,
        "categoryId"
    )

    raw_price = get_text(
        item,
        "price"
    )

    barcode = get_text(
        item,
        "barcode"
    )

    quantity_in_stock = get_text(
        item,
        "quantity_in_stock"
    )

    supplier_available = normalize_available(
        get_text(
            item,
            "available"
        )
    )

    # --------------------------------------------------------
    # STOCK
    # --------------------------------------------------------

    stock_quantity, stock_available = (
        convert_stock_quantity(
            quantity_in_stock
        )
    )

    if supplier_available == "false":
        stock_quantity = "0"
        stock_available = "false"

    # --------------------------------------------------------
    # OFFER
    # --------------------------------------------------------

    offer = ET.SubElement(
        offers,
        "offer"
    )

    offer.set(
        "id",
        product_id
    )

    offer.set(
        "available",
        stock_available
    )

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "price"
    ).text = parse_price(
        raw_price
    )

    # --------------------------------------------------------
    # CURRENCY
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "currencyId"
    ).text = (
        currency_id
        or "UAH"
    )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    if category_id:

        ET.SubElement(
            offer,
            "categoryId"
        ).text = category_id

    # --------------------------------------------------------
    # VENDOR
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "vendor"
    ).text = vendor

    # --------------------------------------------------------
    # ARTICLE
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "article"
    ).text = vendor_code

    # --------------------------------------------------------
    # STOCK QUANTITY
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "stock_quantity"
    ).text = stock_quantity

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if name:

        ET.SubElement(
            offer,
            "name"
        ).text = name

    if name_ua:

        ET.SubElement(
            offer,
            "name_ua"
        ).text = name_ua

    # ========================================================
    # DESCRIPTION
    #
    # Короткий description постачальника
    # більше НЕ використовується.
    #
    # Беремо повний опис тільки із Supabase.
    # ========================================================

    ET.SubElement(
        offer,
        "description"
    ).text = full_description

    ET.SubElement(
        offer,
        "description_ua"
    ).text = full_description

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if url:

        ET.SubElement(
            offer,
            "url"
        ).text = url

    # --------------------------------------------------------
    # BARCODE
    # --------------------------------------------------------

    if barcode:

        ET.SubElement(
            offer,
            "barcode"
        ).text = barcode

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    for image_url in get_images(
        item
    ):

        ET.SubElement(
            offer,
            "picture"
        ).text = image_url

    # --------------------------------------------------------
    # PARAMETERS
    # --------------------------------------------------------

    for source_param in get_params(
        item
    ):

        append_param_with_multilang(
            offer,
            source_param
        )

    return True


# ============================================================
# EXPORT ROZETKA FEED
# ============================================================

def export_rozetka_feed() -> None:

    print()
    print(
        "========================================"
    )
    print(
        "ROZETKA FEED GENERATION"
    )
    print(
        "========================================"
    )

    # --------------------------------------------------------
    # CHECK INPUT
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Файл не знайдено: {INPUT_FILE}"
        )

    # --------------------------------------------------------
    # LOAD SUPABASE
    # --------------------------------------------------------

    descriptions = (
        load_supabase_descriptions()
    )

    # --------------------------------------------------------
    # READ SUPPLIER XML
    # --------------------------------------------------------

    tree = ET.parse(
        INPUT_FILE
    )

    source_root = tree.getroot()

    source_items = source_root.findall(
        ".//items/item"
    )

    print()
    print(
        f"Знайдено товарів у фіді "
        f"постачальника: "
        f"{len(source_items)}"
    )

    # --------------------------------------------------------
    # BUILD XML
    # --------------------------------------------------------

    root, offers_el = build_root(
        source_root
    )

    exported_count = 0
    skipped_count = 0

    for item in source_items:

        exported = build_offer(
            item,
            offers_el,
            descriptions
        )

        if exported:
            exported_count += 1
        else:
            skipped_count += 1

    # ========================================================
    # ЗАХИСТ
    #
    # Якщо жодного SKU не співпало,
    # не перезаписуємо нормальний XML порожнім.
    # ========================================================

    if exported_count == 0:

        raise RuntimeError(
            "Не експортовано жодного товару. "
            "Перевір SUPABASE_URL, SUPABASE_KEY "
            "та відповідність vendorCode = products.sku. "
            "Існуючий rozetka_feed.xml не перезаписано."
        )

    # --------------------------------------------------------
    # SAVE XML
    # --------------------------------------------------------

    result_tree = ET.ElementTree(
        root
    )

    ET.indent(
        result_tree,
        space="  ",
        level=0
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result_tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print()
    print(
        "========================================"
    )
    print(
        "ГОТОВО"
    )
    print(
        "========================================"
    )

    print(
        f"Всього товарів постачальника: "
        f"{len(source_items)}"
    )

    print(
        f"Експортовано для Rozetka: "
        f"{exported_count}"
    )

    print(
        f"Пропущено через відсутність "
        f"повного опису: "
        f"{skipped_count}"
    )

    print()
    print(
        f"Готовий XML:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    export_rozetka_feed()
