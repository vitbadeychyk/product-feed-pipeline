# Epicentr unified feed

Run `python -m scripts.rozetka.export_feed`, then
`python -m scripts.epicentr.export_feed`. The workflow enforces this order.
The standalone Epicentr command consumes the existing Rozetka output; regenerate
Rozetka first after changing the raw supplier feed.

Canonical output: `data/output/epicentr/epicentr_feed.xml`.
`epicentr_updates.xml` is an identical compatibility copy for existing subscribers.
The old updates CLI also invokes the unified exporter.

Product descriptions come from the prepared Rozetka catalog (Supabase
`sku,description` lookup). Parameters are exactly the prepared Rozetka parameters:
raw supplier `<param>` values selected by `scripts/rozetka/category_params.py`,
including that directory's fixed/default values and language handling.
This does not export every raw supplier parameter.

Epicentr IDs remain supplier vendorCode / manual offer ID. Epicentr pricing,
manual prices and manual availability retain the existing rules. Duplicate supplier
SKUs use the last occurrence, matching the previous updates generator.
Supplier quantity availability is taken from the prepared Rozetka catalog where
available. Manual content and default parameters come from
`data/manual/epicentr_manual_products.xml`; per-offer values override defaults.
Category IDs are supplier IDs for mapping during the YML import, not Epicentr
API taxonomy codes.

History now saves full cards when available. Removed products retain their last
full content and become out_of_stock. Legacy records and products without a
prepared full description still have update-only entries in the same file:
they can update an existing card but cannot create a complete new card.
No product descriptions are invented to fill these gaps.

Checks: `python -m unittest discover -s tests -v`.
