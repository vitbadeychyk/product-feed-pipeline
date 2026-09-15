from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.eva.category_map import EVA_CATEGORY_NAMES
from scripts.eva.category_map import get_eva_category_id
from scripts.eva.category_map import is_ignored_category
from scripts.pricing.eva_pricing import calculate_old_price
from scripts.pricing.eva_pricing import calculate_price
from scripts.rozetka import export_feed as rozetka


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_FILE = BASE_DIR / "data" / "output" / "eva" / "eva_feed.xml"


def replace_categories_with_eva(
    root: ET.Element,
    supplier_category_ids: set[str],
) -> None:
    shop = root.find("./shop")
    if shop is None:
        raise RuntimeError("У сформованому XML не знайдено блок shop")

    name = shop.find("name")
    company = shop.find("company")
    url = shop.find("url")
    if name is not None:
        name.text = "KidsRide EVA Feed"
    if company is not None:
        company.text = "KidsRide"
    if url is not None:
        url.text = "https://www.kidsride.com.ua/"

    categories = root.find("./shop/categories")
    if categories is None:
        raise RuntimeError("У сформованому XML не знайдено блок categories")

    categories.clear()
    added: set[str] = set()

    for supplier_category_id in sorted(supplier_category_ids):
        eva_category_id = get_eva_category_id(supplier_category_id)
        if not eva_category_id or eva_category_id in added:
            continue

        category = ET.SubElement(categories, "category")
        category.set("id", eva_category_id)
        category.text = EVA_CATEGORY_NAMES[eva_category_id]
        added.add(eva_category_id)

    for offer in root.findall("./shop/offers/offer"):
        category_element = offer.find("categoryId")
        if category_element is None:
            continue

        supplier_category_id = (category_element.text or "").strip()
        eva_category_id = get_eva_category_id(supplier_category_id)
        if not eva_category_id:
            raise RuntimeError(
                f"Товар {offer.get('id')} має категорію без відповідності EVA: "
                f"{supplier_category_id}"
            )
        category_element.text = eva_category_id


def can_map_item_to_eva(item: ET.Element, supplier_category_id: str) -> bool:
    """Відсікає товар, якщо спільна категорія постачальника неоднозначна."""
    if supplier_category_id != "84":
        return True

    # Категорія 84 містить і гірки, і батути. EVA зараз відкрила гірки,
    # тому передаємо лише товари, які справді є гірками.
    name = " ".join((
        rozetka.get_text(item, "name"),
        rozetka.get_text(item, "name_ua"),
    )).casefold()
    return "гірк" in name or "горк" in name


def export_eva_feed() -> None:
    print("\n========================================")
    print("EVA FEED GENERATION")
    print("========================================")

    if not rozetka.INPUT_FILE.exists():
        raise FileNotFoundError(f"Файл не знайдено: {rozetka.INPUT_FILE}")

    descriptions = rozetka.load_supabase_descriptions()
    source_root = ET.parse(rozetka.INPUT_FILE).getroot()
    source_items = source_root.findall(".//items/item")

    export_items: list[ET.Element] = []
    used_supplier_category_ids: set[str] = set()
    ignored_count = 0
    unsupported_count = 0
    description_count = 0

    for item in source_items:
        supplier_category_id = rozetka.get_text(item, "categoryId")

        if is_ignored_category(supplier_category_id):
            ignored_count += 1
            continue

        if not get_eva_category_id(supplier_category_id):
            unsupported_count += 1
            continue

        if not can_map_item_to_eva(item, supplier_category_id):
            unsupported_count += 1
            continue

        if not rozetka.can_export_item(item, descriptions):
            description_count += 1
            continue

        export_items.append(item)
        used_supplier_category_ids.add(supplier_category_id)

    if not export_items:
        raise RuntimeError(
            "Не знайдено жодного товару для EVA. Існуючий eva_feed.xml "
            "не буде перезаписаний."
        )

    root, offers = rozetka.build_root(source_root, used_supplier_category_ids)

    original_calculate_price = rozetka.calculate_price
    original_calculate_old_price = rozetka.calculate_old_price
    rozetka.calculate_price = calculate_price
    rozetka.calculate_old_price = calculate_old_price

    try:
        exported_count = sum(
            1 for item in export_items
            if rozetka.build_offer(item, offers, descriptions)
        )
    finally:
        rozetka.calculate_price = original_calculate_price
        rozetka.calculate_old_price = original_calculate_old_price

    if exported_count == 0:
        raise RuntimeError("Не експортовано жодного товару для EVA")

    replace_categories_with_eva(root, used_supplier_category_ids)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Всього товарів постачальника: {len(source_items)}")
    print(f"Експортовано для EVA: {exported_count}")
    print(f"Пропущено погоджених категорій: {ignored_count}")
    print(f"Пропущено невідкритих категорій: {unsupported_count}")
    print(f"Пропущено без повного опису: {description_count}")
    print(f"Категорій EVA у XML: {len(root.findall('./shop/categories/category'))}")
    print(f"Готовий XML: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_eva_feed()
