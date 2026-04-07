
from __future__ import annotations


CATEGORY_COMMISSION_MAP = {
    "default": 0.20,
    # Приклад:
    # "1001": 0.10,
    # "1002": 0.15,
}


def get_commission(category_id: str) -> float:
    return CATEGORY_COMMISSION_MAP.get(category_id, CATEGORY_COMMISSION_MAP["default"])


def get_markup(price: float) -> float:
    if price <= 4999:
        return 700.0
    if price <= 9999:
        return 1000.0
    if price <= 19999:
        return 1500.0
    return 2000.0


def calculate_price(original_price: float, category_id: str) -> float:
    if original_price <= 0:
        return 0.0

    discounted_price = original_price * (1 - 0.22)
    commission = get_commission(category_id)
    price_with_commission = discounted_price * (1 + commission)
    final_price = price_with_commission + get_markup(original_price)

    return round(final_price, 2)


if __name__ == "__main__":
    examples = [
        (3000, "1001"),
        (7000, "1002"),
        (15000, "2001"),
    ]

    for original_price, category_id in examples:
        result = calculate_price(original_price, category_id)
        print(
            f"original_price={original_price}, "
            f"category_id={category_id}, final_price={result}"
        )
