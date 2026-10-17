"""Unified Epicentr feed built directly from supplier XML and Supabase."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import json
from scripts.common.product_images import marketplace_picture_url

from scripts.epicentr.category_map import resolve_category, resolve_spare_category

from scripts.common.parse_local_feed import parse_local_feed
from scripts.common.product_descriptions import load_supabase_descriptions, normalize_sku
from scripts.epicentr.export_updates_with_history import (
    load_known_products, save_known_products, build_current_products,
    load_manual_products, merge_with_history,
)

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_FILE = BASE_DIR / "data/output/epicentr/epicentr_feed.xml"
INPUT_FILE = BASE_DIR / "data/raw/supplier_feed.xml"
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
            raise ValueError("Missing supplier article")
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
        old_price = data.get("price_old") or int(float(data["price"]) * 1.3)
        set_text(offer, "price_old", old_price)
        # Epicentr rejects priceOld. Remove cached copies from historical cards too.
        for legacy_price in list(offer.findall("priceOld")):
            offer.remove(legacy_price)
        set_text(offer, "availability", "in_stock" if available else "out_of_stock")
        set_text(offer, "stock_quantity", "10" if available else "0")
        if offer.findtext("name_ua"):
            for tag in ("categoryId", "description_ua", "picture"):
                if not offer.findtext(tag):
                    raise ValueError(f"Incomplete product {sku}: {tag}")
            if offer.findtext("currencyId") != "UAH":
                raise ValueError(f"Non-UAH product: {sku}")
            # Merchant-defined origin policy for the Prom import template.
            country = "Україна" if offer.findtext("categoryId") == "76" else "Китай"
            set_text(offer, "country_of_origin", country)
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


def build_supplier_content(raw: ET.Element, descriptions: dict[str, str]) -> ET.Element:
    """Build content solely from raw supplier data and an independent DB lookup."""
    root = ET.Element("yml_catalog")
    shop = ET.SubElement(root, "shop")
    categories = ET.SubElement(shop, "categories")
    for category in raw.findall(".//catalog/category"):
        categories.append(deepcopy(category))
    offers = ET.SubElement(shop, "offers")
    for item in raw.findall(".//items/item"):
        sku = (item.findtext("vendorCode") or "").strip()
        description = (descriptions.get(normalize_sku(sku)) or "").strip()
        if not description:
            description = (item.findtext("description_ua") or "").strip()
        if not description:
            description = (item.findtext("description") or "").strip()
        if not sku or not description:
            continue
        offer = ET.SubElement(offers, "offer", id=sku)
        set_text(offer, "article", sku)
        for tag in ("url", "currencyId", "categoryId", "vendor", "barcode", "name", "name_ua"):
            value = (item.findtext(tag) or "").strip()
            if value:
                set_text(offer, tag, value)
        if not offer.findtext("currencyId"):
            set_text(offer, "currencyId", "UAH")
        if not offer.findtext("name_ua"):
            set_text(offer, "name_ua", offer.findtext("name") or "")
        for tag in ("description", "description_ua"):
            set_text(offer, tag, description)
        for picture in item.findall("image"):
            if picture.text and picture.text.strip():
                set_picture = ET.SubElement(offer, "picture")
                set_picture.text = picture.text.strip()
        # Preserve every supplied parameter, including unit and language attributes.
        # Flatten multilingual <value> nodes as simple YML <param> values.
        for param in item.findall("param"):
            values = param.findall("value")
            for value in values or [param]:
                text = (value.text or "").strip()
                if not text:
                    continue
                attrs = dict(param.attrib)
                attrs.update(value.attrib)
                if attrs.get("lang") == "uk":
                    attrs["lang"] = "ua"
                ET.SubElement(offer, "param", attrs).text = text
    return root


def build_import_feed(all_products: ET.Element) -> ET.Element:
    """Prom importer requires name and categoryId even for unavailable offers."""
    root = deepcopy(all_products)
    offers = root.find("./shop/offers")
    if offers is None:
        raise ValueError("Missing offers block")
    categories = {c.get("id") for c in root.findall("./shop/categories/category")}
    for offer in list(offers):
        if not (offer.findtext("name") or "").strip() and (offer.findtext("name_ua") or "").strip():
            set_text(offer, "name", offer.findtext("name_ua"))
        if any(not (offer.findtext(tag) or "").strip() for tag in ("name", "categoryId")):
            offers.remove(offer)
            continue
        if offer.findtext("categoryId") not in categories:
            raise ValueError(f"Unknown category for {offer.get('id')}")
    if not list(offers):
        raise ValueError("No complete products for import; existing files will not be overwritten")
    return root


def build_attributes_feed(import_root: ET.Element, brand_map: dict | None = None) -> ET.Element:
    """Native Epicentr XML for updating measurement fields on existing cards.

    This is imported via File / Update all, not the Prom import parser.
    Taxonomy uses the verified Epicentr workbook, never supplier IDs as codes.
    Unresolved mixed products retain their current category in the cabinet.
    """
    brand_map = brand_map or {}
    root = ET.Element("yml_catalog", date=import_root.get("date", ""))
    offers = ET.SubElement(root, "offers")
    for source in import_root.findall("./shop/offers/offer"):
        offer = ET.SubElement(offers, "offer", id=source.get("id"), available=source.get("available", "false"))
        for tag in ("price", "price_old", "availability"):
            if source.findtext(tag):
                set_text(offer, tag, source.findtext(tag))
        taxonomy = resolve_category(source.findtext("categoryId") or "", source.findtext("name_ua") or source.findtext("name") or "", sku=source.get("id") or "", description=source.findtext("description_ua") or "")
        if taxonomy:
            code, title = taxonomy
            ET.SubElement(offer, "category", code=code).text = title
            ET.SubElement(offer, "attribute_set", code=code).text = title
        for picture in source.findall("picture"):
            output_picture = deepcopy(picture)
            output_picture.text = marketplace_picture_url(picture.text or "")
            offer.append(output_picture)
        vendor = (source.findtext("vendor") or "").strip()
        if vendor.casefold() in {"", "без бренду", "без бренда", "no brand", "unknown"}:
            # The fallback applies only to missing brands, never to real brands
            # that have not yet been matched to an Epicentr option.
            vendor = "Bambi Racer" if taxonomy and taxonomy[0] == "854" else "Інше"
        brand = brand_map.get(vendor.casefold())
        if brand and brand.get("code") and brand.get("name"):
            ET.SubElement(offer, "vendor", code=str(brand["code"])).text = brand["name"]
        else:
            ET.SubElement(offer, "vendor").text = vendor
        name = ET.SubElement(offer, "name", lang="ua")
        name.text = source.findtext("name_ua") or source.findtext("name")
        description = source.findtext("description_ua") or source.findtext("description")
        if description:
            ET.SubElement(offer, "description", lang="ua").text = description
        country = source.findtext("country_of_origin")
        if country:
            country_codes = {"Китай": "chn", "Україна": "ukr"}
            attrs = {"code": country_codes[country]} if country in country_codes else {}
            ET.SubElement(offer, "country_of_origin", attrs).text = country
        ET.SubElement(offer, "param", name="Міра виміру", paramcode="measure", valuecode="measure_pcs").text = "шт."
        ET.SubElement(offer, "param", name="Мінімальна кратність товару", paramcode="ratio").text = "1"
    # Match the supplied native template's field order.
    order = {tag: index for index, tag in enumerate(("price", "price_old", "availability", "category", "attribute_set", "name", "picture", "description", "vendor", "country_of_origin", "param", "width", "height", "weight", "length"))}
    for offer in offers:
        offer[:] = sorted(offer, key=lambda child: order.get(child.tag, len(order)))
    return root


def write_xml_atomic(root: ET.Element, path: Path) -> None:
    ET.indent(root, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    ET.ElementTree(root).write(temp, encoding="utf-8", xml_declaration=True)
    ET.parse(temp)
    temp.replace(path)


def export_feed() -> None:
    raw = ET.parse(INPUT_FILE).getroot()
    items = raw.findall(".//items/item")
    if not items:
        raise ValueError("Supplier feed is empty; existing output will not be overwritten")
    descriptions = load_supabase_descriptions(allow_empty=True)
    source = build_supplier_content(raw, descriptions)
    supplier = build_current_products(parse_local_feed())
    manual = load_manual_products()
    for item in items:
        sku = (item.findtext("vendorCode") or "").strip()
        if sku not in supplier:
            continue
        try:
            qty = float((item.findtext("quantity_in_stock") or "0").replace(",", "."))
        except ValueError:
            qty = 0
        supplier[sku]["available"] = "true" if qty > 0 and (item.findtext("available") or "").strip().lower() == "true" else "false"
    current = {**supplier, **manual}
    # Enrich existing history before its current price/stock records are replaced.
    state = load_known_products()
    previous = state.get("products", {})
    for sku, data in current.items():
        for key in ("offer_xml", "category_name"):
            if key in previous.get(sku, {}):
                data[key] = previous[sku][key]
    products = merge_with_history(current, state)
    updates_root = build_feed(source, ET.parse(MANUAL_FILE).getroot(), products)
    root = build_import_feed(updates_root)
    brand_file = BASE_DIR / "data/manual/epicentr_brand_map.json"
    brand_map = json.loads(brand_file.read_text(encoding="utf-8")) if brand_file.exists() else {}
    brand_map = {key.strip().casefold(): value for key, value in brand_map.items()}
    native_root = build_attributes_feed(root, brand_map)
    # Canonical URL now uses the full native format for both URL import and
    # auto-updates. No Prom parser or second content import is required.
    write_xml_atomic(native_root, OUTPUT_FILE)
    # Historical minimal records remain in a native updates-only compatibility URL.
    native_updates = ET.Element("yml_catalog", date=native_root.get("date", ""))
    native_update_offers = ET.SubElement(native_updates, "offers")
    for old_offer in updates_root.findall("./shop/offers/offer"):
        update = ET.SubElement(native_update_offers, "offer", dict(old_offer.attrib))
        for tag in ("price", "price_old", "availability"):
            set_text(update, tag, old_offer.findtext(tag))
    write_xml_atomic(native_updates, OUTPUT_FILE.with_name("epicentr_updates.xml"))
    # Old content URL becomes an alias of the complete native catalog.
    write_xml_atomic(deepcopy(native_root), OUTPUT_FILE.with_name("epicentr_attributes.xml"))
    unresolved = []
    fallback_assignments = []
    brands_needing_reference = {}
    parameters_needing_reference = {}
    for offer in root.findall("./shop/offers/offer"):
        title = offer.findtext("name_ua") or offer.findtext("name") or ""
        category_id = offer.findtext("categoryId") or ""
        sku = offer.get("id") or ""
        description = offer.findtext("description_ua") or ""
        vendor = (offer.findtext("vendor") or "").strip()
        if vendor.casefold() not in brand_map:
            brands_needing_reference.setdefault(vendor or "<empty>", []).append(sku)
        for parameter in offer.findall("param"):
            if not parameter.get("paramcode"):
                parameters_needing_reference.setdefault(parameter.get("name") or "<empty>", 0)
                parameters_needing_reference[parameter.get("name") or "<empty>"] += 1
        if category_id == "195":
            category, rule = resolve_spare_category(title, sku=sku, description=description)
            if rule == "fallback_195":
                fallback_assignments.append({"sku": sku, "supplier_category_id": category_id, "name": title, "epicentr_category_code": category[0], "rule": rule})
        if not resolve_category(category_id, title, sku=sku, description=description):
            unresolved.append({"sku": offer.get("id"), "supplier_category_id": offer.findtext("categoryId"), "name": title})
    report = {"total": len(root.findall("./shop/offers/offer")), "unresolved_count": len(unresolved), "unresolved": unresolved, "fallback_count": len(fallback_assignments), "fallback_assignments": fallback_assignments, "brands_needing_reference": brands_needing_reference, "parameters_needing_reference": parameters_needing_reference, "packaging_dimensions_missing": [o.get("id") for o in root.findall("./shop/offers/offer") if not all(o.findtext(tag) for tag in ("width", "height", "length", "weight"))]}
    OUTPUT_FILE.with_name("epicentr_taxonomy_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    save_known_products({"products": products})
    full = len(root.findall("./shop/offers/offer"))
    print(f"Epicentr import: {full} complete products")
    print(f"Epicentr updates: {len(products)} products, including {len(products) - full} legacy update-only entries")


if __name__ == "__main__":
    export_feed()
