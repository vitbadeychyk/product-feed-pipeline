from __future__ import annotations


ROZETKA_CATEGORY_MAP: dict[str, str] = {
    "45": "100077",       # Стільчики для годування
    "46": "83687",        # Автокрісла
    "81": "100194",       # Парти, столики, полиці
    "83": "101909",       # Ліжка та манежі
    "122": "4674145",     # Гойдалки і шезлонги
    "42": "4674202",      # Ходунки
    "43": "100389",       # Коляски
    "78": "4674199",      # Толокари
    "491": "4674205",     # Біговели
    "77": "91143",        # Електромобілі
    "39": "197325",       # Ваночки та горщики
}


def get_rozetka_category_id(supplier_category_id: str) -> str:
    """
    Якщо є окремий ID Rozetka — повертаємо його.
    Якщо немає — залишаємо ID постачальника.
    """
    supplier_category_id = str(supplier_category_id or "").strip()
    return ROZETKA_CATEGORY_MAP.get(
        supplier_category_id,
        supplier_category_id,
    )
