from __future__ import annotations

import math

from scripts.eva.category_map import get_eva_category_id


# Тарифи взято з довідника відкритих категорій EVA.
# Для робочої ціни використовується безпечний базовий тариф.
EVA_BASE_COMMISSION_MAP: dict[str, float] = {
    "121858": 0.15,
    "121861": 0.15,
    "121859": 0.15,
    "116256": 0.12,
    "121862": 0.15,
    "116257": 0.12,
    "116264": 0.12,
    "116253": 0.10,
    "101197": 0.15,
    "116263": 0.10,
    "116269": 0.10,
    "100378": 0.10,
    "116265": 0.10,
    "116266": 0.10,
    "116267": 0.10,
    "116268": 0.10,
    "105921": 0.10,
    "101230": 0.15,
    "120710": 0.15,
    "116259": 0.12,
    "116260": 0.12,
    "110052": 0.12,
    "105920": 0.12,
    "121814": 0.08,
    "121815": 0.08,
    "121811": 0.08,
}

EVA_PROMO_COMMISSION_MAP: dict[str, float] = {
    "121858": 0.12,
    "121861": 0.12,
    "121859": 0.13,
    "116256": 0.13,
    "121862": 0.10,
    "116257": 0.10,
    "116264": 0.10,
    "116253": 0.10,
    "101197": 0.15,
    "116263": 0.08,
    "116269": 0.10,
    "100378": 0.10,
    "116265": 0.08,
    "116266": 0.08,
    "116267": 0.08,
    "116268": 0.08,
    "105921": 0.08,
    "101230": 0.13,
    "120710": 0.13,
    "116259": 0.13,
    "116260": 0.13,
    "110052": 0.10,
    "105920": 0.10,
    "121814": 0.05,
    "121815": 0.05,
    "121811": 0.05,
}


def round_up_to_100(price: float) -> float:
    if price <= 0:
        return 0.0
    return float(math.ceil(price / 100.0) * 100)


def get_commission(supplier_category_id: str, promo: bool = False) -> float:
    eva_category_id = get_eva_category_id(supplier_category_id)
    if not eva_category_id:
        raise ValueError(f"Категорія {supplier_category_id} не прив'язана до EVA")

    commission_map = EVA_PROMO_COMMISSION_MAP if promo else EVA_BASE_COMMISSION_MAP
    return commission_map[eva_category_id]


def get_markup(price: float) -> float:
    if price <= 4999:
        return 1000.0
    if price <= 9999:
        return 1500.0
    if price <= 19999:
        return 2000.0
    return 2500.0


def calculate_price(original_price: float, category_id: str) -> float:
    """Ціна EVA: закупівельна база, націнка та компенсація базового тарифу."""
    if original_price <= 0:
        return 0.0

    commission = get_commission(category_id)
    supplier_net_price = original_price * 0.79
    target_amount = supplier_net_price + get_markup(original_price)
    return round_up_to_100(target_amount / (1.0 - commission))


def calculate_old_price(final_price: float) -> float:
    if final_price <= 0:
        return 0.0
    return round_up_to_100(final_price * 1.30)
