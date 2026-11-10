"""Add manually managed sleds to the Rozetka feed without changing supplier offers."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET


MANUAL_FILE = (
    Path(__file__).resolve().parents[2]
    / "data" / "manual" / "epicentr_manual_products.xml"
)


def _value(item: ET.Element, defaults: ET.Element, tag: str) -> str:
    return (item.findtext(tag) or defaults.findtext(tag) or "").strip()


def _positive_price(value: str, article: str, field: str) -> None:
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Manual sled {article}: invalid {field}") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"Manual sled {article}: invalid {field}")


def append_manual_sleds(
    root: ET.Element,
    manual_file: Path = MANUAL_FILE,
) -> int:
    """Append the same manually maintained sled SKUs, prices and stock as Epicentr.

    Validation happens before changing the output tree so a malformed manual
    source cannot silently generate partial or conflicting Rozetka offers.
    """
    manual_root = ET.parse(manual_file).getroot()
    defaults = manual_root.find("defaults")
    if defaults is None:
        raise ValueError("Manual sled XML is missing <defaults>")

    manual_offers = manual_root.findall("offer")
    if not manual_offers:
        raise ValueError("Manual sled XML contains no offers")

    category_id = (defaults.findtext("categoryId") or "").strip()
    category_name = (defaults.findtext("category_name") or "").strip()
    if category_id != "76" or not category_name:
        raise ValueError("Unexpected manual sled category")

    categories = root.find("./shop/categories")
    offers = root.find("./shop/offers")
    if categories is None or offers is None:
        raise ValueError("Rozetka XML has no categories or offers element")

    existing_ids = {offer.get("id") for offer in offers.findall("offer")}
    existing_articles = {
        (offer.findtext("article") or "").strip().casefold()
        for offer in offers.findall("offer")
    }

    prepared: list[ET.Element] = []
    seen_ids: set[str] = set()
    seen_articles: set[str] = set()

    for source in manual_offers:
        product_id = (source.get("id") or "").strip()
        article = _value(source, defaults, "article")
        available = (source.get("available") or "").strip().lower()
        if not product_id or not article:
            raise ValueError("Manual sled must have id and article")
        if available not in ("true", "false"):
            raise ValueError(f"Manual sled {product_id}: invalid available")
        if (product_id in existing_ids or product_id in seen_ids
                or article.casefold() in existing_articles
                or article.casefold() in seen_articles):
            raise ValueError(f"Duplicate manual sled: {product_id}/{article}")

        values = {
            tag: _value(source, defaults, tag)
            for tag in ("price", "price_old", "currencyId", "categoryId",
                        "vendor", "name_ua", "description_ua")
        }
        if values["categoryId"] != category_id:
            raise ValueError(f"Manual sled {product_id}: category mismatch")
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"Manual sled {product_id}: missing {', '.join(missing)}")
        _positive_price(values["price"], article, "price")
        _positive_price(values["price_old"], article, "price_old")
        pictures = [
            (picture.text or "").strip()
            for picture in source.findall("picture")
            if (picture.text or "").strip()
        ]
        if not pictures:
            raise ValueError(f"Manual sled {product_id}: missing picture")

        offer = ET.Element("offer", id=product_id, available=available)
        for tag in ("price", "price_old", "currencyId", "categoryId", "vendor"):
            ET.SubElement(offer, tag).text = values[tag]
        ET.SubElement(offer, "article").text = article
        ET.SubElement(offer, "stock_quantity").text = (
            "10" if available == "true" else "0"
        )
        for tag in ("name", "name_ua"):
            ET.SubElement(offer, tag).text = values["name_ua"]
        for tag in ("description", "description_ua"):
            ET.SubElement(offer, tag).text = values["description_ua"]
        for url in pictures:
            ET.SubElement(offer, "picture").text = url
        for source_params in (defaults.find("params"), source.find("params")):
            if source_params is None:
                continue
            for param in source_params.findall("param"):
                name = (param.get("name") or "").strip()
                value = (param.text or "").strip()
                if name and value:
                    ET.SubElement(offer, "param", name=name).text = value

        prepared.append(offer)
        seen_ids.add(product_id)
        seen_articles.add(article.casefold())

    if not any(category.get("id") == category_id
               for category in categories.findall("category")):
        ET.SubElement(categories, "category", id=category_id).text = category_name

    offers.extend(prepared)
    return len(prepared)
