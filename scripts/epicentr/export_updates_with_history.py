from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from scripts.common.parse_local_feed import parse_local_feed
from scripts.pricing.epicentr_pricing import calculate_price


BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "epicentr"
    / "epicentr_updates.xml"
)

STATE_FILE = (
    BASE_DIR
    / "state"
    / "epicentr_known_products.json"
)

MANUAL_FILE = (
    BASE_DIR
    / "data"
    / "manual"
    / "epicentr_manual_products.xml"
)


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_available(value: object) -> str:
    value_str = safe_text(value).lower()
    return "true" if value_str == "true" else "false"


def convert_availability(value: str) -> str:
    if value == "true":
        return "in_stock"
    return "out_of_stock"


def calculate_old_price(price: int) -> int:
    return int(price * 1.3)


# =========================================================
# ІСТОРІЯ ТОВАРІВ
# =========================================================

def load_known_products() -> dict:
    if not STATE_FILE.exists():
        return {"products": {}}

    with STATE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_known_products(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# ТОВАРИ ПОСТАЧАЛЬНИКА
# =========================================================

def build_current_products(products: list[dict]) -> dict[str, dict]:
    current_products: dict[str, dict] = {}

    for product in products:
        vendor_code = safe_text(product.get("vendor_code"))

        if not vendor_code:
            continue

        original_price = float(
            product.get("price", 0) or 0
        )

        if original_price <= 0:
            continue

        category_id = safe_text(
            product.get("category_id")
        )

        final_price = calculate_price(
            original_price=original_price,
            category_id=category_id,
        )

        final_price = int(final_price)

        current_products[vendor_code] = {
            "id": vendor_code,
            "available": normalize_available(
                product.get("available")
            ),
            "price": final_price,
            "price_old": calculate_old_price(
                final_price
            ),
            "category_id": category_id,
            "source": "supplier",
            "last_seen_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    return current_products


# =========================================================
# РУЧНІ ТОВАРИ
# data/manual/epicentr_manual_products.xml
# =========================================================

def load_manual_products() -> dict[str, dict]:
    manual_products: dict[str, dict] = {}

    if not MANUAL_FILE.exists():
        print(
            f"Ручний XML не знайдено: {MANUAL_FILE}"
        )
        return manual_products

    try:
        tree = ET.parse(MANUAL_FILE)
        root = tree.getroot()
        defaults = root.find("defaults")

    except ET.ParseError as error:
        print(
            f"Помилка читання ручного XML: {error}"
        )
        return manual_products

    for offer in root.findall(".//offer"):
        product_id = safe_text(
            offer.get("id")
        )

        if not product_id:
            print(
                "Пропущено ручний товар без ID"
            )
            continue

        available = normalize_available(
            offer.get("available")
        )

        # -------------------------
        # PRICE
        # -------------------------

        price_node = offer.find("price")
        if price_node is None and defaults is not None:
            price_node = defaults.find("price")

        if (
            price_node is None
            or not safe_text(price_node.text)
        ):
            print(
                f"Пропущено ручний товар "
                f"{product_id}: не вказана ціна"
            )
            continue

        try:
            price = int(
                float(
                    safe_text(price_node.text)
                )
            )

        except ValueError:
            print(
                f"Пропущено ручний товар "
                f"{product_id}: некоректна ціна"
            )
            continue

        if price <= 0:
            print(
                f"Пропущено ручний товар "
                f"{product_id}: ціна <= 0"
            )
            continue

        # -------------------------
        # PRICE OLD
        # -------------------------

        price_old_node = offer.find("price_old")
        if price_old_node is None and defaults is not None:
            price_old_node = defaults.find("price_old")

        price_old = 0

        if (
            price_old_node is not None
            and safe_text(price_old_node.text)
        ):
            try:
                price_old = int(
                    float(
                        safe_text(
                            price_old_node.text
                        )
                    )
                )
            except ValueError:
                price_old = 0

        # Якщо стару ціну вручну не вказали —
        # рахуємо +30%
        if price_old <= 0:
            price_old = calculate_old_price(
                price
            )

        manual_products[product_id] = {
            "id": product_id,
            "available": available,
            "price": price,
            "price_old": price_old,
            "category_id": "manual",
            "source": "manual",
            "last_seen_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    print(
        f"Знайдено ручних товарів: "
        f"{len(manual_products)}"
    )

    return manual_products


# =========================================================
# ОБ'ЄДНАННЯ З ІСТОРІЄЮ
# =========================================================

def merge_with_history(
    current_products: dict[str, dict],
    known_state: dict,
) -> dict[str, dict]:

    known_products = known_state.get(
        "products",
        {},
    )

    # Оновлюємо або додаємо всі товари,
    # які присутні зараз
    for product_id, product_data in current_products.items():
        known_products[product_id] = (
            product_data
        )

    current_ids = set(
        current_products.keys()
    )

    # Якщо товар був відомий раніше,
    # але зараз його немає ні у постачальника,
    # ні в ручному XML —
    # ставимо out_of_stock
    for product_id, product_data in known_products.items():
        if product_id not in current_ids:
            product_data[
                "available"
            ] = "false"

    return known_products


# =========================================================
# ФОРМУВАННЯ ФІНАЛЬНОГО XML
# =========================================================

def build_feed(
    all_products: dict[str, dict],
) -> ET.Element:

    root = ET.Element(
        "yml_catalog"
    )

    root.set(
        "date",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),
    )

    offers = ET.SubElement(
        root,
        "offers",
    )

    exported_count = 0

    for product_id, product_data in sorted(
        all_products.items()
    ):
        available_value = normalize_available(
            product_data.get(
                "available"
            )
        )

        availability_value = (
            convert_availability(
                available_value
            )
        )

        price_value = int(
            product_data.get(
                "price",
                0,
            ) or 0
        )

        if price_value <= 0:
            continue

        old_price_value = int(
            product_data.get(
                "price_old",
                0,
            ) or 0
        )

        if old_price_value <= 0:
            old_price_value = (
                calculate_old_price(
                    price_value
                )
            )

        offer = ET.SubElement(
            offers,
            "offer",
        )

        offer.set(
            "id",
            safe_text(
                product_data.get("id")
            ),
        )

        offer.set(
            "available",
            available_value,
        )

        ET.SubElement(
            offer,
            "price",
        ).text = str(
            price_value
        )

        ET.SubElement(
            offer,
            "price_old",
        ).text = str(
            old_price_value
        )

        ET.SubElement(
            offer,
            "availability",
        ).text = (
            availability_value
        )

        exported_count += 1

    print(
        f"Експортовано товарів "
        f"для оновлення: "
        f"{exported_count}"
    )

    return root


# =========================================================
# ОСНОВНИЙ ПРОЦЕС
# =========================================================

def export_feed() -> None:

    # 1. Читаємо поточний XML постачальника
    products = parse_local_feed()

    print(
        f"Знайдено товарів "
        f"у поточному фіді постачальника: "
        f"{len(products)}"
    )

    # 2. Читаємо історію
    known_state = load_known_products()

    # 3. Формуємо товари постачальника
    supplier_products = (
        build_current_products(
            products
        )
    )

    print(
        f"Товарів постачальника "
        f"після обробки: "
        f"{len(supplier_products)}"
    )

    # 4. Читаємо наш ручний XML
    manual_products = (
        load_manual_products()
    )

    # 5. Об'єднуємо
    #
    # Спочатку товари постачальника,
    # потім ручні.
    #
    # Якщо однаковий ID є в обох джерелах,
    # ручний XML має пріоритет.
    current_products = (
        supplier_products.copy()
    )

    current_products.update(
        manual_products
    )

    print(
        f"Активних товарів "
        f"після об'єднання: "
        f"{len(current_products)}"
    )

    # 6. Додаємо історичні товари
    merged_products = (
        merge_with_history(
            current_products,
            known_state,
        )
    )

    # 7. Зберігаємо оновлений state
    save_known_products(
        {
            "products":
                merged_products
        }
    )

    # 8. Формуємо XML
    root = build_feed(
        merged_products
    )

    tree = ET.ElementTree(
        root
    )

    ET.indent(
        tree,
        space="  ",
        level=0,
    )

    # 9. Записуємо фінальний файл
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    print()
    print(
        "========================================"
    )
    print(
        "EPICENTR UPDATE FEED ГОТОВИЙ"
    )
    print(
        "========================================"
    )

    print(
        f"Товарів постачальника: "
        f"{len(supplier_products)}"
    )

    print(
        f"Ручних товарів: "
        f"{len(manual_products)}"
    )

    print(
        f"Поточних товарів разом: "
        f"{len(current_products)}"
    )

    print(
        f"Товарів разом з історією: "
        f"{len(merged_products)}"
    )

    print(
        f"Файл: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    export_feed()
