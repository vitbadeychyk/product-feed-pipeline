"""Unified YML: Rozetka product content, Epicentr SKU/pricing and stock history.

Run after scripts.rozetka.export_feed. Never copy Rozetka selling prices or IDs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.common.parse_local_feed import parse_local_feed
from scripts.epicentr.export_updates_with_history import (
    load_known_products, save_known_products, build_current_products,
    load_manual_products, merge_with_history,
)

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_FILE = BASE_DIR / "data/output/epicentr/epicentr_feed.xml"
ROZETKA_FILE = BASE_DIR / "data/output/rozetka/rozetka_feed.xml"
MANUAL_FILE = BASE_DIR / "data/manual/epicentr_manual_products.xml"


def set_text(node: ET.Element, tag: str, value: object) -> None:
    child = node.find(tag)
    if child is None:
        child = ET.SubElement(node, tag)
    child.text = str(value)


def build_feed(source: ET.Element, manual: ET.Element, products: dict) -> ET.Element:
    root = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop = ET.SubElement(root, "shop")
    for tag, value in (("name", "KidsRide Epicentr Feed"), ("company", "KidsRide"),
                       ("url", "https://kidsride.com.ua/")):
        set_text(shop, tag, value)
    ET.SubElement(ET.SubElement(shop, "currencies"), "currency", id="UAH", rate="1")
    categories = ET.SubElement(shop, "categories")
    category_names = {c.get("id"): c.text for c in source.findall("./shop/categories/category")}
    defaults = manual.find("defaults")
    if defaults is None:
        raise ValueError("Manual XML is missing defaults")
    category_names[defaults.findtext("categoryId")] = defaults.findtext("category_name")

    content = {}
    for offer in source.findall("./shop/offers/offer"):
        sku = (offer.findtext("article") or "").strip()
        if not sku:
            raise ValueError("Missing Rozetka article")
        if sku in content:
            print(f"Duplicate supplier SKU {sku}: using last item, as in existing Epicentr updates")
        content[sku] = deepcopy(offer)

    manual_ids = set()
    for item in manual.findall("offer"):
        sku = (item.get("id") or "").strip()
        if not sku or sku in manual_ids:
            raise ValueError(f"Missing or duplicate manual ID: {sku}")
        manual_ids.add(sku)
        offer = ET.Element("offer", id=sku)
        for tag in ("url", "currencyId", "categoryId", "vendor", "article", "name",
                    "name_ua", "description", "description_ua", "barcode"):
            value = item.findtext(tag) or defaults.findtext(tag)
            if value:
                set_text(offer, tag, value)
        for tag, fallback in (("name", "name_ua"), ("description", "description_ua")):
            if not offer.findtext(tag):
                set_text(offer, tag, offer.findtext(fallback) or "")
        for picture in item.findall("picture"):
            offer.append(deepcopy(picture))
        params = {p.get("name"): deepcopy(p) for p in defaults.findall("./params/param")}
        params.update({p.get("name"): deepcopy(p) for p in item.findall("./params/param") + item.findall("param")})
        offer.extend(params.values())
        content[sku] = offer

    offers = ET.SubElement(shop, "offers")
    used_categories = set()
    for sku, data in sorted(products.items()):
        # Preserve full content for products removed from the supplier in later runs.
        offer = content.get(sku)
        if offer is None and data.get("offer_xml"):
            offer = ET.fromstring(data["offer_xml"])
        if offer is None:
            # Legacy history has prices only. Keep these update-only entries so
            # existing marketplace cards can still be disabled.
            offer = ET.Element("offer")
        available = data.get("available") == "true"
        offer.set("id", sku)
        offer.set("available", "true" if available else "false")
        set_text(offer, "price", data["price"])
        set_text(offer, "price_old", data.get("price_old") or int(float(data["price"]) * 1.3))
        set_text(offer, "availability", "in_stock" if available else "out_of_stock")
        set_text(offer, "stock_quantity", "10" if available else "0")
        if offer.findtext("name_ua"):
            for tag in ("categoryId", "description_ua", "picture"):
                if not offer.findtext(tag):
                    raise ValueError(f"Incomplete product {sku}: {tag}")
            if offer.findtext("currencyId") != "UAH":
                raise ValueError(f"Non-UAH product: {sku}")
            used_categories.add(offer.findtext("categoryId"))
            data["offer_xml"] = ET.tostring(offer, encoding="unicode")
            data["category_name"] = category_names.get(offer.findtext("categoryId")) or data.get("category_name")
        offers.append(offer)
    for category_id in sorted(used_categories):
        name = category_names.get(category_id) or next((d.get("category_name") for d in products.values()
            if d.get("offer_xml") and ET.fromstring(d["offer_xml"]).findtext("categoryId") == category_id), None)
        if not name:
            raise ValueError(f"Missing category name: {category_id}")
        ET.SubElement(categories, "category", id=category_id).text = name
    return root


def export_feed() -> None:
    source = ET.parse(ROZETKA_FILE).getroot()
    if not source.findall("./shop/offers/offer"):
        raise ValueError("Rozetka feed is empty; generate it first")
    supplier = build_current_products(parse_local_feed())
    manual = load_manual_products()
    # Rozetka also checks quantity_in_stock; keep that stock decision.
    for offer in source.findall("./shop/offers/offer"):
        sku = (offer.findtext("article") or "").strip()
        if sku in supplier:
            supplier[sku]["available"] = offer.get("available", "false")
    current = {**supplier, **manual}
    # Enrich existing history before its current price/stock records are replaced.
    state = load_known_products()
    previous = state.get("products", {})
    for sku, data in current.items():
        for key in ("offer_xml", "category_name"):
            if key in previous.get(sku, {}):
                data[key] = previous[sku][key]
    products = merge_with_history(current, state)
    root = build_feed(source, ET.parse(MANUAL_FILE).getroot(), products)
    ET.indent(root, space="  ")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT_FILE.with_suffix(".tmp")
    ET.ElementTree(root).write(temp, encoding="utf-8", xml_declaration=True)
    ET.parse(temp)
    temp.replace(OUTPUT_FILE)
    # Compatibility URL: same unified feed, no separate stock-only generation.
    OUTPUT_FILE.with_name("epicentr_updates.xml").write_bytes(OUTPUT_FILE.read_bytes())
    save_known_products({"products": products})
    full = sum(bool(o.findtext("name_ua")) for o in root.findall("./shop/offers/offer"))
    print(f"Epicentr: {full} full products; {len(products) - full} legacy update-only entries")


if __name__ == "__main__":
    export_feed()
