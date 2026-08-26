from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# PATHS
# ============================================================

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

SUPABASE_URL = (
    os.getenv("SUPABASE_URL", "")
    .strip()
    .rstrip("/")
)

SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY", "")
    .strip()
)


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


def get_images(
    element: ET.Element,
) -> list[str]:

    return [
        img.text.strip()
        for img in element.findall("image")
        if img.text
    ]


def get_params(
    element: ET.Element,
) -> list[ET.Element]:

    return element.findall("param")


def parse_price(
    value: str,
) -> str:

    value = (
        safe_text(value)
        .replace(",", ".")
    )

    try:
        return str(
            int(
                round(
                    float(value)
                )
            )
        )

    except ValueError:
        return "0"


def normalize_available(
    value: str,
) -> str:

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

def normalize_sku(
    value: object,
) -> str:
    """
    Нормалізує SKU для порівняння.

    Наприклад:

        M 4259EBLR-1
        m 4259eblr-1

    будуть вважатися однаковими.

    Пробіли всередині SKU не видаляємо.
    """

    return safe_text(value).casefold()


# ============================================================
# DESCRIPTION FORMATTER
# ============================================================

def format_description(
    value: object,
) -> str:
    """
    Форматує description для Rozetka.

    Було:

        Текст товару. Характеристики товару:
        • Матеріал...
        • Розмір...

    Якщо все записано одним рядком,
    функція додає нормальні переноси.

    Сам текст опису НЕ змінюється.
    """

    text = safe_text(value)

    if not text:
        return ""

    # --------------------------------------------------------
    # Нормалізуємо переноси рядків
    # --------------------------------------------------------

    text = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    # --------------------------------------------------------
    # Зайві пробіли/табуляції замінюємо одним пробілом.
    #
    # ВАЖЛИВО:
    # символи нового рядка тут не видаляються.
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # --------------------------------------------------------
    # Перед блоком "Характеристики..."
    # додаємо порожній рядок.
    #
    # Спрацює для:
    #
    # Характеристики:
    # Характеристики товару:
    # Характеристики гірки Bambi WM19003:
    # Характеристики моделі M 4259:
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]*(Характеристики[^:\n]*:)",
        r"\n\n\1",
        text,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Кожен символ • переносимо на новий рядок
    #
    # Було:
    # Матеріал... • Розмір... • Вага...
    #
    # Стане:
    # Матеріал...
    # • Розмір...
    # • Вага...
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]*•[ \t]*",
        "\n• ",
        text,
    )

    # --------------------------------------------------------
    # Якщо перед • уже був перенос,
    # прибираємо надлишкові порожні рядки
    # --------------------------------------------------------

    text = re.sub(
        r"\n+\s*•",
        "\n•",
        text,
    )

    # --------------------------------------------------------
    # Максимум один порожній рядок між абзацами
    # --------------------------------------------------------

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# LOAD DESCRIPTIONS FROM SUPABASE
# ============================================================

def load_supabase_descriptions() -> dict[str, str]:
    """
    Завантажує:

        products.sku
        products.description

    з Supabase.

    Повертає:

        normalized_sku -> formatted_description
    """

    if not SUPABASE_URL:
        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_URL"
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "Не задано GitHub Secret / env SUPABASE_KEY"
        )

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/products"
    )

    headers = {
        "apikey": SUPABASE_KEY,
    }

    descriptions: dict[str, str] = {}

    page_size = 1000
    offset = 0
    total_rows = 0

    print()
    print(
        "========================================"
    )
    print(
        "Завантаження описів із Supabase"
    )
    print(
        "========================================"
    )

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
                "Помилка підключення до Supabase: "
                f"{exc}"
            ) from exc

        try:

            rows = response.json()

        except ValueError as exc:

            raise RuntimeError(
                "Supabase повернув "
                "некоректну JSON-відповідь"
            ) from exc

        if not isinstance(rows, list):

            raise RuntimeError(
                "Неочікувана відповідь Supabase: "
                f"{rows}"
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

            # =================================================
            # ПОВНИЙ ОПИС ІЗ SUPABASE
            # + форматування переносів
            # =================================================

            description = format_description(
                row.get("description")
            )

            # SKU відсутній
            if not sku:
                continue

            # description NULL / пустий
            if not description:
                continue

            descriptions[sku] = description

        print(
            f"Оброблено рядків Supabase: "
            f"{total_rows}"
        )

        if len(rows) < page_size:
            break

        offset += page_size

    print()
    print(
        f"Товарів з повним description: "
        f"{len(descriptions)}"
    )

    # ========================================================
    # ЗАХИСТ
    #
    # Якщо Supabase повернув 0 описів,
    # старий робочий XML не перезаписуємо.
    # ========================================================

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

    root = ET.Element(
        "yml_catalog"
    )

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

    # --------------------------------------------------------
    # CURRENCIES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CATEGORIES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OFFERS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MULTILANGUAGE PARAM
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # NORMAL PARAM
    # --------------------------------------------------------

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
    # ARTICLE / SKU
    # --------------------------------------------------------

    vendor_code = get_text(
        item,
        "vendorCode",
    )

    # Без vendorCode не можемо
    # знайти товар у Supabase
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
            "",
        )
    )

    # ========================================================
    # ГОЛОВНЕ ПРАВИЛО
    #
    # Якщо description у Supabase відсутній,
    # товар НЕ додаємо у Rozetka XML.
    # ========================================================

    if not full_description:
        return False

    # --------------------------------------------------------
    # SOURCE PRODUCT DATA
    # --------------------------------------------------------

    product_id = safe_text(
        item.get("id")
    )

    name = get_text(
        item,
        "name",
    )

    name_ua = get_text(
        item,
        "name_ua",
    )

    vendor = get_text(
        item,
        "vendor",
    )

    url = get_text(
        item,
        "url",
    )

    currency_id = get_text(
        item,
        "currencyId",
        "UAH",
    )

    category_id = get_text(
        item,
        "categoryId",
    )

    raw_price = get_text(
        item,
        "price",
    )

    barcode = get_text(
        item,
        "barcode",
    )

    quantity_in_stock = get_text(
        item,
        "quantity_in_stock",
    )

    supplier_available = normalize_available(
        get_text(
            item,
            "available",
        )
    )

    # --------------------------------------------------------
    # STOCK
    # --------------------------------------------------------

    (
        stock_quantity,
        stock_available,
    ) = convert_stock_quantity(
        quantity_in_stock
    )

    if supplier_available == "false":

        stock_quantity = "0"
        stock_available = "false"

    # --------------------------------------------------------
    # CREATE OFFER
    # --------------------------------------------------------

    offer = ET.SubElement(
        offers,
        "offer",
    )

    offer.set(
        "id",
        product_id,
    )

    offer.set(
        "available",
        stock_available,
    )

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "price",
    ).text = parse_price(
        raw_price
    )

    # --------------------------------------------------------
    # CURRENCY
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "currencyId",
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
            "categoryId",
        ).text = category_id

    # --------------------------------------------------------
    # VENDOR
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "vendor",
    ).text = vendor

    # --------------------------------------------------------
    # ARTICLE
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "article",
    ).text = vendor_code

    # --------------------------------------------------------
    # STOCK QUANTITY
    # --------------------------------------------------------

    ET.SubElement(
        offer,
        "stock_quantity",
    ).text = stock_quantity

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if name:

        ET.SubElement(
            offer,
            "name",
        ).text = name

    if name_ua:

        ET.SubElement(
            offer,
            "name_ua",
        ).text = name_ua

    # ========================================================
    # DESCRIPTION
    #
    # Короткі description / description_ua
    # постачальника НЕ використовуємо.
    #
    # Беремо тільки повний description із Supabase.
    # Він уже відформатований функцією
    # format_description().
    # ========================================================

    ET.SubElement(
        offer,
        "description",
    ).text = full_description

    ET.SubElement(
        offer,
        "description_ua",
    ).text = full_description

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if url:

        ET.SubElement(
            offer,
            "url",
        ).text = url

    # --------------------------------------------------------
    # BARCODE
    # --------------------------------------------------------

    if barcode:

        ET.SubElement(
            offer,
            "barcode",
        ).text = barcode

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    for image_url in get_images(
        item
    ):

        ET.SubElement(
            offer,
            "picture",
        ).text = image_url

    # --------------------------------------------------------
    # PARAMETERS
    # --------------------------------------------------------

    for source_param in get_params(
        item
    ):

        append_param_with_multilang(
            offer,
            source_param,
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
            f"Файл не знайдено: "
            f"{INPUT_FILE}"
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

    print()
    print(
        "Читання supplier_feed.xml..."
    )

    tree = ET.parse(
        INPUT_FILE
    )

    source_root = tree.getroot()

    source_items = source_root.findall(
        ".//items/item"
    )

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
            descriptions,
        )

        if exported:
            exported_count += 1

        else:
            skipped_count += 1

    # ========================================================
    # SAFETY
    #
    # Якщо збігів не знайшли взагалі,
    # не перезаписуємо існуючий XML.
    # ========================================================

    if exported_count == 0:

        raise RuntimeError(
            "Не експортовано жодного товару. "
            "Перевір SUPABASE_URL, SUPABASE_KEY "
            "та відповідність "
            "vendorCode = products.sku. "
            "Існуючий rozetka_feed.xml "
            "не перезаписано."
        )

    # --------------------------------------------------------
    # CREATE XML TREE
    # --------------------------------------------------------

    result_tree = ET.ElementTree(
        root
    )

    ET.indent(
        result_tree,
        space="  ",
        level=0,
    )

    # --------------------------------------------------------
    # SAVE XML
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
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
        "Готовий XML:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    export_rozetka_feed()
