from __future__ import annotations


CATEGORY_COMMISSION_MAP = {
    "491": 0.10,
    "125": 0.10,
    "66": 0.10,
    "75": 0.10,
    "77": 0.15,
    "78": 0.15,
    "122": 0.15,
    "173": 0.10,
    "79": 0.10,
    "45": 0.15,
    "84": 0.15,
    "80": 0.15,
    "95": 0.15,
    "61": 0.15,
    "99": 0.15,
    "39": 0.15,
    "40": 0.15,
    "21": 0.15,
    "81": 0.15,
    "83": 0.15,
    "82": 0.15,
    "42": 0.15,
    "46": 0.15,
    "43": 0.10,
    "41": 0.15,
    "282840": 0.15,
    "44": 0.15,
    "13": 0.15,
    "38": 0.15,
    "47": 0.15,
    "123": 0.15,
    "599": 0.15,
    "195": 0.15,
    "543": 0.15,
    "556": 0.15,
    "494": 0.15,
    "default": 0.20,
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

def round_up_to_100(price: float) -> float:
    return math.ceil(price / 100) * 100

def calculate_price(original_price: float, category_id: str) -> float:
    if original_price <= 0:
        return 0.0

    discounted_price = original_price * (1 - 0.22)
    commission = get_commission(category_id)
    markup = get_markup(original_price)

    target_amount = discounted_price + markup
    final_price = target_amount / (1 - commission)

    return round(final_price, 2)


if __name__ == "__main__":
    examples = [
        (3000, "491"),
        (7000, "494"),
        (15000, "195"),
    ]

    for original_price, category_id in examples:
        result = calculate_price(original_price, category_id)
        print(
            f"original_price={original_price}, "
            f"category_id={category_id}, final_price={result}"
        )
