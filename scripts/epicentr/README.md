# Epicentr: one native XML URL

Run `python -m scripts.epicentr.export_feed` with SUPABASE_URL/SUPABASE_KEY.
No prepared Rozetka XML is consumed.

Canonical URL path: `data/output/epicentr/epicentr_feed.xml`.
This is now full native Epicentr XML (`yml_catalog/offers/offer`), not Prom YML.
Use normal Import -> Link -> Update all for new cards and content updates.
Save the SAME URL under Automatic stock updates for scheduled price/availability.
Scheduled price/stock updates do not create new products automatically.
Enable the marketplace option to mark products missing from the URL unavailable:
legacy history without content cannot appear in the complete import catalog.

`epicentr_attributes.xml` is an identical compatibility alias of the main native
catalog. `epicentr_updates.xml` is a native minimal price/stock feed preserving
all historical IDs; existing consumers can keep using it, but it is not required
for the new single-URL workflow.

Sources: raw supplier XML for names, pictures, brands, barcode/source data,
category IDs, availability and per-product parameters. Independent Supabase SKU
lookup for descriptions, then supplier description_ua, then description.
Pricing remains scripts/pricing/epicentr_pricing.py. Manual items/defaults remain
in data/manual/epicentr_manual_products.xml. Full source cards remain in history.

Native output includes price, price_old, availability, mapped category and
attribute_set, pictures, brand, localized name/description, country, measure_pcs
and ratio=1. No Prom-only shop/categoryId/name_ua/stock_quantity or priceOld tags.
Supplier parameter names alone are not valid Epicentr attribute codes: unencoded
parameters are retained in source/history and listed for mapping, not submitted
as fabricated attributes.

Category/attribute_set code/name mappings follow the supplied Epicentr workbook
and native XML guide. Mixed groups use title rules. Category 195 applies SKU
rules, title/description exceptions, then approved fallback 7153. Car-seat and
stroller accessories go to 847. Fallback and unresolved assignments are audited.

`data/manual/epicentr_brand_map.json`: optional supplier brand -> object with
verified `code` and `name`. Keys match case-insensitively. No codes are invented.
Real brand names without a mapping are preserved as text; the rejected placeholder
"Без бренду" is omitted unless a verified option is configured. These cards may
still need brand selection before publication.

`epicentr_taxonomy_report.json` lists unresolved categories, fallback assignments,
brands lacking reference codes and supplier parameters needing attribute mapping.

After merging, run Actions on main to regenerate the URL. Start with a small
native import and inspect its report before importing the complete catalog.
Tests: `python -m unittest discover -s tests -v`.

### Бренд за відсутності даних постачальника

Для порожнього бренду або «Без бренду»/«Без бренда»/«no brand»/«unknown»
передаємо Bambi Racer у категорії Епіцентру 854 (дитячі електромобілі),
для решти товарів — Інше. Наявний справжній бренд не замінюємо.
Коди vendor беруться з data/manual/epicentr_brand_map.json, зіставленого
за точними назвами з експорту AttributeSet 646 від 17.10.2026 (колонки E/G).
Відсутність коду для справжнього бренду потребує окремого зіставлення.
