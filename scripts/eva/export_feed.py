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
MANUAL_FILE = BASE_DIR / "data" / "manual" / "epicentr_manual_products.xml"


def text_or_default(
    offer: ET.Element,
    defaults: ET.Element,
    tag: str,
) -> str:
    value = (offer.findtext(tag) or "").strip()
    if value:
        return value
    return (defaults.findtext(tag) or "").strip()


def load_manual_offers() -> tuple[ET.Element, list[ET.Element]]:
    """Читає спільний ручний XML для Epicentr та EVA."""
    if not MANUAL_FILE.exists():
        raise FileNotFoundError(f"Ручний XML не знайдено: {MANUAL_FILE}")

    root = ET.parse(MANUAL_FILE).getroot()
    defaults = root.find("defaults")
    if defaults is None:
        raise RuntimeError("У ручному XML не знайдено блок defaults")

    offers = root.findall("offer")
    if not offers:
        raise RuntimeError("У ручному XML не знайдено товари")

    ids = [str(offer.get("id") or "").strip() for offer in offers]
    if any(not product_id for product_id in ids):
        raise RuntimeError("У ручному XML є товар без id")
    if len(ids) != len(set(ids)):
        raise RuntimeError("У ручному XML знайдено дублікати id")

    return defaults, offers


def add_manual_offer_to_eva(
    source_offer: ET.Element,
    defaults: ET.Element,
    offers: ET.Element,
) -> None:
    product_id = str(source_offer.get("id") or "").strip()
    available = str(source_offer.get("available") or "").strip().lower() == "true"

    required = {
        "name_ua": text_or_default(source_offer, defaults, "name_ua"),
        "vendor": text_or_default(source_offer, defaults, "vendor"),
        "article": text_or_default(source_offer, defaults, "article"),
        "picture": text_or_default(source_offer, defaults, "picture"),
        "price": text_or_default(source_offer, defaults, "price"),
        "price_old": text_or_default(source_offer, defaults, "price_old"),
        "currencyId": text_or_default(source_offer, defaults, "currencyId"),
        "categoryId": text_or_default(source_offer, defaults, "categoryId"),
        "description_ua": text_or_default(source_offer, defaults, "description_ua"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Ручний товар {product_id}: відсутні поля {', '.join(missing)}"
        )

    offer = ET.SubElement(offers, "offer")
    offer.set("id", product_id)
    offer.set("available", "true" if available else "false")

    for tag in ("price", "price_old", "currencyId", "categoryId", "vendor", "article"):
        ET.SubElement(offer, tag).text = required[tag]

    ET.SubElement(offer, "stock_quantity").text = "10" if available else "0"
    ET.SubElement(offer, "name").text = required["name_ua"]
    ET.SubElement(offer, "name_ua").text = required["name_ua"]
    ET.SubElement(offer, "description").text = required["description_ua"]
    ET.SubElement(offer, "description_ua").text = required["description_ua"]

    for picture in source_offer.findall("picture"):
        value = (picture.text or "").strip()
        if value:
            ET.SubElement(offer, "picture").text = value

    params = defaults.find("params")
    if params is not None:
        for source_param in params.findall("param"):
            name = str(source_param.get("name") or "").strip()
            value = (source_param.text or "").strip()
            if not name or not value:
                continue
            param = ET.SubElement(offer, "param")
            param.set("name", name)
            localized_value = ET.SubElement(param, "value")
            localized_value.set("lang", "uk")
            localized_value.text = value


def apply_eva_categories(
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
    for supplier_category_id in sorted(supplier_category_ids):
        eva_category_id = get_eva_category_id(supplier_category_id)
        if not eva_category_id:
            continue

        category = ET.SubElement(categories, "category")
        category.set("id", supplier_category_id)
        category.set("eva_id", eva_category_id)
        category.text = EVA_CATEGORY_NAMES[eva_category_id]


def write_xml_with_cdata(tree: ET.ElementTree, output_file: Path) -> None:
    """Записує HTML-описи у CDATA, як вимагає EVA."""
    root = tree.getroot()
    replacements: list[tuple[str, str]] = []

    for index, description in enumerate(
        root.findall("./shop/offers/offer/description")
        + root.findall("./shop/offers/offer/description_ua")
    ):
        token = f"__EVA_CDATA_{index:08d}__"
        value = description.text or ""
        safe_cdata = value.replace("]]>", "]]]]><![CDATA[>")
        replacements.append((token, safe_cdata))
        description.text = token

    xml_text = ET.tostring(root, encoding="unicode", short_empty_elements=True)

    for token, value in replacements:
        xml_text = xml_text.replace(
            f">{token}<",
            f"><![CDATA[{value}]]><",
            1,
        )

    output_file.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n" + xml_text,
        encoding="utf-8",
    )


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


def normalize_multilang_params(root: ET.Element) -> None:
    """Переносить мову з param у підтримувані EVA вкладені value."""
    for offer in root.findall("./shop/offers/offer"):
        localized: dict[str, dict[str, str]] = {}
        localized_elements: list[ET.Element] = []

        for param in offer.findall("param"):
            language = (param.get("lang") or "").strip().lower()
            if not language:
                continue

            name = (param.get("name") or "").strip()
            value = (param.text or "").strip()
            if not name or not value:
                continue

            eva_language = "uk" if language in {"ua", "uk"} else language
            localized.setdefault(name, {})[eva_language] = value
            localized_elements.append(param)

        for param in localized_elements:
            offer.remove(param)

        for name, values in localized.items():
            param = ET.SubElement(offer, "param")
            param.set("name", name)

            for language in ("uk", "ru"):
                value = values.get(language)
                if not value:
                    continue
                value_element = ET.SubElement(param, "value")
                value_element.set("lang", language)
                value_element.text = value


def export_eva_feed() -> None:
    print("\n========================================")
    print("EVA FEED GENERATION")
    print("========================================")

    if not rozetka.INPUT_FILE.exists():
        raise FileNotFoundError(f"Файл не знайдено: {rozetka.INPUT_FILE}")

    descriptions = rozetka.load_supabase_descriptions()
    source_root = ET.parse(rozetka.INPUT_FILE).getroot()
    source_items = source_root.findall(".//items/item")
    manual_defaults, manual_offers = load_manual_offers()

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

    manual_category_id = text_or_default(
        manual_defaults,
        manual_defaults,
        "categoryId",
    )
    if not get_eva_category_id(manual_category_id):
        raise RuntimeError(
            f"Ручна категорія {manual_category_id} не прив'язана до EVA"
        )
    used_supplier_category_ids.add(manual_category_id)

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

    for manual_offer in manual_offers:
        add_manual_offer_to_eva(manual_offer, manual_defaults, offers)

    if exported_count == 0 and not manual_offers:
        raise RuntimeError("Не експортовано жодного товару для EVA")

    normalize_multilang_params(root)
    apply_eva_categories(root, used_supplier_category_ids)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_xml_with_cdata(tree, OUTPUT_FILE)

    print(f"Всього товарів постачальника: {len(source_items)}")
    print(f"Експортовано для EVA: {exported_count}")
    print(f"Додано ручних товарів для EVA: {len(manual_offers)}")
    print(f"Пропущено погоджених категорій: {ignored_count}")
    print(f"Пропущено невідкритих категорій: {unsupported_count}")
    print(f"Пропущено без повного опису: {description_count}")
    print(f"Категорій EVA у XML: {len(root.findall('./shop/categories/category'))}")
    print(f"Готовий XML: {OUTPUT_FILE}")


if __name__ == "__main__":
    export_eva_feed()
