# Epicentr unified feed — independent sources

Run `python -m scripts.epicentr.export_feed` with SUPABASE_URL and SUPABASE_KEY.
No Rozetka XML, export module or execution order is required.

Sources:
- `data/raw/supplier_feed.xml`: products, vendorCode IDs, titles, images, brand,
  barcode, URL, currency, category IDs/names, stock and ALL supplied parameters.
- Supabase `products.sku,description`: independent paginated REST lookup, matched
  by trimmed case-insensitive SKU without removing internal spaces. Description
  formatting follows the existing Rozetka logic, implemented in the independent
  `scripts/common/product_descriptions.py` client.
- `scripts/pricing/epicentr_pricing.py`: existing Epicentr selling-price formula.
- `data/manual/epicentr_manual_products.xml`: manual content/prices/defaults.
- `state/epicentr_known_products.json`: price/stock and cached full-card history.

Parameters are not filtered by Rozetka category rules. All raw per-item `<param>`
values are copied, retaining names, units and languages. Nested multilingual values
are flattened to separate simple YML params; uk is normalized to ua. No fixed
Rozetka warranty, delivery or country defaults are injected.

Canonical output: `data/output/epicentr/epicentr_feed.xml`.
`epicentr_feed.xml` contains complete import cards only: each offer must have a
nonempty name and categoryId referencing the category directory. Complete
out_of_stock cards stay in the import. Minimal legacy records are excluded.
`epicentr_updates.xml` retains ALL IDs, including minimal historical out_of_stock
records, for automatic price/stock updates. Configure this URL for stock updates
when old cards must be disabled. Both files are built by the same exporter.
The full history is preserved in state; no product data is invented.

Removed products become out_of_stock and retain cached full content when present.
Description priority: nonempty Supabase description, then nonempty supplier
`description_ua`, then supplier `description`. If all are empty, retain cached
content or update-only entries. An empty successful DB lookup permits the
supplier fallback; connection/API errors still fail without overwriting output. Category IDs are supplier IDs for mapping
in the import UI, not Epicentr API taxonomy codes.

Checks: `python -m unittest discover -s tests -v`.
