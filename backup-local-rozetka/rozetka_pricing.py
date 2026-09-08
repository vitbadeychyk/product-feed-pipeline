from __future__ import annotations

import math
from collections.abc import Callable


def round_up_to_100(price: float) -> float:
    """Округлення ціни вгору до найближчих 100 грн."""
    if price <= 0:
        return 0.0
    return float(math.ceil(price / 100.0) * 100)


# ============================================================
# ROZETKA PRICING RULES
# ============================================================

# 1. Автокрісла
def avtokrisla(price: float) -> float:
    price *= 0.78

    if price <= 4999:
        price *= 1.10
        price += 700
    elif price <= 9999:
        price *= 1.07
        price += 1000
    elif price <= 19999:
        price *= 1.07
        price += 1200
    elif price <= 29999:
        price *= 1.05
        price += 1500
    else:
        price *= 1.05
        price += 2000

    return price


# 2. Транспорт: біговели, велосипеди, толокари,
#    електромобілі, квадроцикли, педальні машинки тощо
def transport(price: float) -> float:
    price *= 0.78

    if price <= 4999:
        price *= 1.13
        price += 700
    elif price <= 9999:
        price *= 1.07
        price += 1000
    elif price <= 19999:
        price *= 1.07
        price += 1200
    elif price <= 29999:
        price *= 1.05
        price += 1500
    else:
        price *= 1.05
        price += 2000

    return price


# 3. Ванночки
def vannochky(price: float) -> float:
    return price * 0.78 * 1.07 + 300


# 4. Коляски
def kalyasky(price: float) -> float:
    price *= 0.78

    if price <= 4999:
        price *= 1.10
        price += 700
    elif price <= 9999:
        price *= 1.07
        price += 1000
    elif price <= 19999:
        price *= 1.07
        price += 1200
    elif price <= 29999:
        price *= 1.05
        price += 1500
    else:
        price *= 1.05
        price += 2000

    return price


# 5. Ліжечка / манежі
def maneghi(price: float) -> float:
    price *= 0.78

    if price <= 9999:
        price *= 1.18
    elif price <= 24999:
        price *= 1.12
    else:
        price *= 1.07

    if price <= 4999:
        price += 700
    elif price <= 9999:
        price += 1000
    elif price <= 19999:
        price += 1200
    elif price <= 29999:
        price += 1500
    else:
        price += 2000

    return price


# 6. Парти
def party(price: float) -> float:
    return maneghi(price)


# 7. Стільчики для годування
def stilchiki(price: float) -> float:
    return price * 0.78 * 1.075 + 700


# 8. Шезлонги / гойдалки
def shezlongi(price: float) -> float:
    return price * 0.78 * 1.18 + 700


# 9. Санки / снігокати
def snigokaty(price: float) -> float:
    price *= 0.78

    if price <= 9999:
        price *= 1.18
        price += 800
    else:
        price *= 1.10
        price += 2000

    return price


# 10. Басейни
def baseyny(price: float) -> float:
    price *= 0.78

    if price <= 15999:
        price *= 1.10
        price += 1200
    else:
        price *= 1.05
        price += 1700

    return price


# ============================================================
# CATEGORY -> PRICING RULE
# ============================================================
#
# ID взяті з категорій, які вже присутні у вашому XML.
# Для категорій, яких тут немає, діє безпечний fallback:
# ціна постачальника просто округлюється вгору до 100 грн.
#
# Це дозволяє не ламати фід, поки ми поступово прив'яжемо
# решту категорій до потрібних правил.
# ============================================================

CATEGORY_PRICING_RULES: dict[str, Callable[[float], float]] = {
    # Автокрісла
    "46": avtokrisla,

    # Транспорт
    "491": transport,     # Біговелики
    "125": transport,     # Велосипеди спортивні
    "66": transport,      # Велосипеди 2х колісні
    "75": transport,      # Велосипеди 3х колісні
    "77": transport,      # Електромобілі
    "78": transport,      # Толокари
    "173": transport,     # Карти / педальні машинки
    "79": transport,      # Самокати та скейти
    "345906": transport,  # Електротранспорт
    "347037": transport,  # Квадроцикли
    "494": transport,     # Квадроцикли метал
    "349343": transport,  # Бензинові квадроцикли

    # Ванночки / купання
    "39": vannochky,      # Ванночки та горщики
    "40": vannochky,      # Все для купання

    # Коляски
    "43": kalyasky,

    # Ліжечка / манежі
    "83": maneghi,

    # Парти / столики
    "81": party,

    # Стільчики для годування
    "45": stilchiki,

    # Гойдалки / шезлонги
    "122": shezlongi,

    # Басейни
    "92": baseyny,        # Басейни надувні
    "126": baseyny,       # Басейни каркасні

    # Санки / снігокати:
    # Додайте сюди ID категорії, коли визначимо її точно.
    # "ID": snigokaty,
}


def get_pricing_rule(category_id: str) -> Callable[[float], float] | None:
    return CATEGORY_PRICING_RULES.get(str(category_id).strip())


def calculate_price(
    original_price: float,
    category_id: str,
) -> float:
    """
    Розрахунок фінальної ціни Rozetka.

    1. Якщо категорія має власне правило — застосовуємо його.
    2. Якщо категорія ще не прив'язана — додаємо 500 грн
       до ціни постачальника.
    3. Фінальну ціну завжди округлюємо ВГОРУ до 100 грн.
    """
    if original_price <= 0:
        return 0.0

    rule = get_pricing_rule(category_id)

    if rule is None:
        # Категорія ще не прив'язана до окремого правила:
        # додаємо 500 грн до ціни постачальника.
        calculated_price = original_price + 500
    else:
        calculated_price = rule(original_price)

    return round_up_to_100(calculated_price)


def calculate_old_price(final_price: float) -> float:
    """
    Стара ціна = фінальна ціна +30%.
    Також округлюється ВГОРУ до 100 грн.
    """
    if final_price <= 0:
        return 0.0

    return round_up_to_100(final_price * 1.30)


if __name__ == "__main__":
    examples = [
        (3000, "46"),
        (7000, "77"),
        (3000, "39"),
        (7000, "43"),
        (15000, "83"),
        (5000, "45"),
        (5000, "122"),
        (8000, "126"),
    ]

    for original_price, category_id in examples:
        final_price = calculate_price(
            original_price=original_price,
            category_id=category_id,
        )
        old_price = calculate_old_price(final_price)

        print(
            f"original={original_price}, "
            f"category={category_id}, "
            f"price={final_price}, "
            f"oldprice={old_price}"
        )
