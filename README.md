# product-feed-pipeline

Автоматичне формування товарних XML-фідів для Rozetka, Epicentr та EVA.

Готовий фід EVA: `data/output/eva/eva_feed.xml`.

Документація EVA: `scripts/eva/EVA_DOCUMENTATION.md`.

Ручні товари для Epicentr та EVA зберігаються в одному файлі:
`data/manual/epicentr_manual_products.xml`.

Щоб змінити наявність ручного товару на обох маркетплейсах, змініть лише
`available="true"` або `available="false"` у відповідному `offer`.
Значення `availability` для Epicentr і `stock_quantity` для EVA
генеруються автоматично.
