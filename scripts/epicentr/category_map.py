"""Native XML taxonomy from the merchant-provided Epicentr category workbook.

Per the supplied native XML guide, category and attribute_set share code/name.
Do not use supplier IDs as Epicentr codes. Mixed groups require title rules.
"""
from __future__ import annotations

# Supplier ID -> (Epicentr code, exact leaf name from category workbook).
CATEGORY_MAP = {
    '45': ('745', 'Стільчики для годування'),
    '46': ('843', 'Автокрісла'),
    '81': ('873', 'Дитячі меблі'),
    '42': ('869', 'Ходунки'),
    '43': ('846', 'Коляски'),
    '78': ('4917', 'Дитячі каталки, гойдалки'),
    '491': ('853', 'Біговели'),
    '66': ('4991', 'Дитячі велосипеди'),
    '75': ('4991', 'Дитячі велосипеди'),
    '125': ('1441', 'Велосипеди'),
    '77': ('854', 'Дитячі електромобілі'),
    '105': ('1446', 'Батути'),
    '92': ('527', 'Басейни'),
    '126': ('527', 'Басейни'),
    '347037': ('854', 'Дитячі електромобілі'),  # battery-powered children's ride-ons, not motor vehicles
    '494': ('9042', 'Квадроцикли'),
    '343943': ('9042', 'Квадроцикли'),
}


# Exact SKU assignments take precedence over text rules. Keys are casefolded.
SKU_CATEGORY_OVERRIDES: dict[str, tuple[str, str]] = {}


def resolve_spare_category(title: str, *, sku: str = "", description: str = "") -> tuple[tuple[str, str], str]:
    """Return category and an auditable rule for supplier spare-parts group 195."""
    override = SKU_CATEGORY_OVERRIDES.get(sku.strip().casefold())
    if override:
        return override, "sku_override"
    # Use title first. A generic description must not override a specific title.
    for text, source in ((title.casefold(), "title"), (description.casefold(), "description")):
        if any(word in text for word in ("автокрісл", "автокресл", "коляск", "візоч")):
            return ("847", "Аксесуари для колясок та автокрісел"), source + ":stroller_or_car_seat"
        if "скейт" in text:
            return ("8477", "Запчастини для скейтбордів"), source + ":skateboard"
        if "самокат" in text:
            if "електр" in text or "электр" in text:
                return ("7153", "Запчастини для електротранспорту"), source + ":electric_scooter"
            return ("8823", "Запчастини для самокатів"), source + ":scooter"
        if any(word in text for word in ("електромоб", "электромоб", "електротранспорт", "электротранспорт")):
            return ("7153", "Запчастини для електротранспорту"), source + ":electric_transport"
    # Explicit merchant-approved fallback. Always list these offers for review.
    return ("7153", "Запчастини для електротранспорту"), "fallback_195"


def resolve_category(category_id: str, title: str, *, sku: str = "", description: str = "") -> tuple[str, str] | None:
    """Return a verified leaf candidate; leave ambiguous products unresolved."""
    if category_id == '195':
        return resolve_spare_category(title, sku=sku, description=description)[0]
    text = title.casefold()
    if category_id == '76':
        # Supplier group also contains snow racers/ice sleds; don't lump them in.
        if ('санк' in text or 'санчат' in text) and not any(x in text for x in ('снігокат', 'снегокат', 'ледян', 'льодян')):
            return '5048', 'Санки'
        return None
    if category_id == '79':
        if 'скейт' in text:
            return '1438', 'Скейтборди'
        if 'самокат' in text:
            return ('7202', 'Електросамокати') if 'електр' in text or 'электр' in text else ('1437', 'Самокати')
    if category_id == '63' and 'ролик' in text and not ('захист' in text or 'защит' in text):
        return '1436', 'Роликові ковзани'
    if category_id == '83':
        if 'ліж' in text or 'кроват' in text:
            return '868', 'Дитячі ліжечка'
        if 'манеж' in text:
            return '871', 'Манежі'
    if category_id == '122' and ('шезлонг' in text):
        return '872', 'Дитячі шезлонги'
    if category_id == '39':
        if 'ванн' in text:
            return '897', 'Дитячі ванночки'
        if 'горщик' in text or 'горшок' in text:
            return '756', 'Горщики та накладки на унітаз'
    if category_id == '99' and ('килим' in text or 'коврик' in text):
        return '2409', 'Розвиваючі килимки'
    if category_id == '80' and ('намет' in text or 'палатк' in text or 'тунел' in text or 'тоннел' in text):
        return '4866', 'Дитячі намети та тунелі'
    if category_id == '103' and ('човен' in text or 'човни' in text or 'лодк' in text):
        return '3663', 'Надувні човни'
    if category_id == '345906':
        if 'самокат' in text:
            return '7202', 'Електросамокати'
        if 'скутер' in text:
            return '7207', 'Електроскутери'
    return CATEGORY_MAP.get(category_id)
