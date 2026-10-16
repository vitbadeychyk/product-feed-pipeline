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


def resolve_category(category_id: str, title: str) -> tuple[str, str] | None:
    """Return a verified leaf candidate; leave ambiguous products unresolved."""
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
