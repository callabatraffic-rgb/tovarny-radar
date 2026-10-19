import pandas as pd
import numpy as np

REQUIRED_COLUMNS = [
    "product_name", "category", "sale_price_rub", "supplier_price_rub",
    "shipping_per_unit_rub", "marketplace_fee_pct", "fulfillment_per_unit_rub",
    "ad_cost_per_unit_rub", "returns_cost_per_unit_rub", "packaging_per_unit_rub",
    "tax_pct", "demand_now", "demand_prev", "competition_count",
    "moq_units", "data_quality_pct"
]
TEMPLATE_COLUMNS = REQUIRED_COLUMNS + ["source_url", "source_date", "notes"]

def _num(df, col, default=0):
    return pd.to_numeric(df[col], errors="coerce").fillna(default)

def analyze_products(source):
    df = source.copy()
    for col in REQUIRED_COLUMNS:
        if col not in df:
            df[col] = np.nan
    for col in REQUIRED_COLUMNS:
        if col not in ("product_name", "category"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    defaults = {
        "shipping_per_unit_rub": 0, "marketplace_fee_pct": 0,
        "fulfillment_per_unit_rub": 0, "ad_cost_per_unit_rub": 0,
        "returns_cost_per_unit_rub": 0, "packaging_per_unit_rub": 0,
        "tax_pct": 0, "demand_now": 0, "demand_prev": 0,
        "competition_count": 0, "moq_units": 1, "data_quality_pct": 0
    }
    for c, v in defaults.items():
        df[c] = _num(df, c, v)
    df["sale_price_rub"] = _num(df, "sale_price_rub", 0)
    df["supplier_price_rub"] = _num(df, "supplier_price_rub", 0)
    df["marketplace_fee_rub"] = df["sale_price_rub"] * df["marketplace_fee_pct"].clip(0,100) / 100
    df["tax_rub"] = df["sale_price_rub"] * df["tax_pct"].clip(0,100) / 100
    df["unit_cost_rub"] = (
        df["supplier_price_rub"] + df["shipping_per_unit_rub"] +
        df["marketplace_fee_rub"] + df["fulfillment_per_unit_rub"] +
        df["ad_cost_per_unit_rub"] + df["returns_cost_per_unit_rub"] +
        df["packaging_per_unit_rub"] + df["tax_rub"]
    )
    df["unit_profit_rub"] = df["sale_price_rub"] - df["unit_cost_rub"]
    df["margin_pct"] = np.where(df["sale_price_rub"] > 0, 100 * df["unit_profit_rub"] / df["sale_price_rub"], 0)
    df["demand_growth_pct"] = np.where(
        df["demand_prev"] > 0, 100 * (df["demand_now"] - df["demand_prev"]) / df["demand_prev"],
        np.where(df["demand_now"] > 0, 100, 0))
    df["test_units"] = np.maximum(df["moq_units"], 1).astype(int)
    df["test_budget_rub"] = (df["supplier_price_rub"] + df["shipping_per_unit_rub"] + df["packaging_per_unit_rub"]) * df["test_units"]
    profit_score = np.clip((df["margin_pct"] + 5) / 35 * 100, 0, 100)
    growth_score = np.clip((df["demand_growth_pct"] + 20) / 80 * 100, 0, 100)
    competition_score = 100 / (1 + np.maximum(df["competition_count"], 0) / 100)
    sourcing_score = np.clip(100 - (df["test_budget_rub"] / 300000 * 100), 0, 100)
    data_score = df["data_quality_pct"].clip(0, 100)
    df["score"] = (0.30 * profit_score + 0.25 * growth_score + 0.15 * competition_score + 0.10 * sourcing_score + 0.20 * data_score).round(1)
    def decision(r):
        if r["unit_profit_rub"] <= 0: return "Отклонить: минусовая экономика"
        if r["data_quality_pct"] < 35: return "Гипотеза: мало данных"
        if r["margin_pct"] < 15: return "Проверить расходы и цену"
        if r["score"] >= 70: return "Приоритетный кандидат"
        if r["score"] >= 50: return "Проверить дополнительно"
        return "Низкий приоритет"
    def reason(r):
        return f"маржа {r['margin_pct']:.1f}%; изменение индикатора спроса {r['demand_growth_pct']:.1f}%; конкурентов по источнику: {int(r['competition_count'])}; качество данных {r['data_quality_pct']:.0f}%"
    def tasks(r):
        todo = []
        if r["data_quality_pct"] < 70: todo.append("подтвердить источник спроса и дату")
        if r["supplier_price_rub"] <= 0: todo.append("получить котировку поставщика")
        if r["shipping_per_unit_rub"] <= 0: todo.append("уточнить доставку, таможню и посредника")
        if r["competition_count"] <= 0: todo.append("проверить конкурентную выдачу")
        if r["demand_prev"] <= 0: todo.append("собрать сопоставимую историю спроса")
        return "; ".join(todo) if todo else "проверить MOQ, образец, сроки поставки и фактические тарифы"
    df["decision"] = df.apply(decision, axis=1)
    df["main_reason"] = df.apply(reason, axis=1)
    df["explanation"] = df.apply(lambda r: f"Итоговый балл {r['score']}/100 складывается из прибыли (30%), динамики спроса (25%), конкуренции (15%), бюджета теста (10%) и качества данных (20%). Это эвристика, не вероятность успеха.", axis=1)
    df["validation_tasks"] = df.apply(tasks, axis=1)
    return df
