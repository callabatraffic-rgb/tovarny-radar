import os
from pathlib import Path
import pandas as pd
import streamlit as st
from scoring import analyze_products, REQUIRED_COLUMNS

ROOT = Path(__file__).parent
st.set_page_config(page_title="Товарный радар", page_icon="📊", layout="wide")
st.title("📊 Товарный радар")
st.caption("Облачный MVP: рейтинг товарных гипотез + ежедневные индикаторы поискового интереса. Индекс Google Trends — не количество продаж.")

with st.sidebar:
    st.header("Фильтры рейтинга")
    min_margin = st.slider("Минимальная маржа после расходов, %", 0, 60, 15)
    max_budget = st.number_input("Максимальный бюджет теста партии, ₽", min_value=0, value=150000, step=10000)
    min_data_quality = st.slider("Минимальное качество данных, %", 0, 100, 35)
    st.divider()
    st.caption("Показатели закупки, доставки, комиссии и рекламы должны быть подтверждены отдельно.")

uploaded = st.file_uploader("Загрузить собственные данные CSV/XLSX", type=["csv", "xlsx"])
if uploaded:
    try:
        source_df = pd.read_excel(uploaded) if uploaded.name.lower().endswith(".xlsx") else pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Не удалось прочитать файл: {exc}")
        st.stop()
else:
    latest = ROOT / "products_latest.csv"
    demo = ROOT / "demo_products.csv"
    source_path = latest if latest.exists() else demo
    source_df = pd.read_csv(source_path)
    if source_path.name == "products_latest.csv":
        st.success("Загружен файл продуктов из репозитория.")
    else:
        st.warning("Пока показаны синтетические учебные товары. Это не рыночные предложения и не основание для закупки.")

missing = [c for c in REQUIRED_COLUMNS if c not in source_df.columns]
if missing:
    st.error("В файле не хватает обязательных столбцов: " + ", ".join(missing))
    st.stop()

results = analyze_products(source_df)
eligible = results[
    (results["margin_pct"] >= min_margin) &
    (results["test_budget_rub"] <= max_budget) &
    (results["data_quality_pct"] >= min_data_quality)
].sort_values("score", ascending=False).copy()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Товаров в анализе", len(results))
m2.metric("Прошли фильтры", len(eligible))
m3.metric("Медианная маржа", f"{results['margin_pct'].median():.1f}%" if len(results) else "—")
m4.metric("С положительной прибылью", int((results["unit_profit_rub"] > 0).sum()))

st.subheader("Рейтинг товарных гипотез")
display_cols = ["product_name", "category", "score", "decision", "sale_price_rub",
                "unit_profit_rub", "margin_pct", "demand_growth_pct", "competition_count",
                "test_budget_rub", "data_quality_pct", "main_reason"]
if len(eligible):
    st.dataframe(eligible[display_cols].rename(columns={
        "product_name":"Товар", "category":"Категория", "score":"Балл / 100",
        "decision":"Статус", "sale_price_rub":"Цена продажи, ₽",
        "unit_profit_rub":"Прибыль/шт., ₽", "margin_pct":"Маржа, %",
        "demand_growth_pct":"Изменение индикатора спроса, %", "competition_count":"Конкуренты",
        "test_budget_rub":"Бюджет теста, ₽", "data_quality_pct":"Качество данных, %",
        "main_reason":"Обоснование"
    }), use_container_width=True, hide_index=True)
else:
    st.warning("Нет товаров, прошедших фильтры. Ослабьте фильтры или проверьте данные.")

st.subheader("Ежедневный мониторинг поискового интереса")
trend_file = ROOT / "data" / "trends_latest.csv"
if trend_file.exists():
    trends = pd.read_csv(trend_file)
    if not trends.empty:
        st.caption("Источник: Google Trends через неофициальную библиотеку pytrends. Индекс относительный (0–100), не продажи и не абсолютный объём поиска.")
        st.dataframe(trends.sort_values("trend_index", ascending=False), use_container_width=True, hide_index=True)
        hist_file = ROOT / "data" / "trends_history.csv"
        if hist_file.exists():
            hist = pd.read_csv(hist_file)
            if not hist.empty and "keyword" in hist.columns and "date" in hist.columns:
                choice = st.selectbox("История интереса по запросу", sorted(hist["keyword"].dropna().unique()))
                one = hist[hist["keyword"] == choice].copy()
                one["date"] = pd.to_datetime(one["date"], errors="coerce")
                st.line_chart(one.set_index("date")["trend_index"])
    else:
        st.info("История ещё не собрана.")
else:
    st.info("Автоматический сбор начнётся после первого запуска GitHub Actions. Google Trends может ограничивать автоматические запросы.")

with st.expander("Разбор экономики выбранного товара"):
    selected = st.selectbox("Товар", results["product_name"].tolist())
    row = results.loc[results["product_name"] == selected].iloc[0]
    a, b, c, d = st.columns(4)
    a.metric("Прибыль/шт.", f"{row['unit_profit_rub']:,.0f} ₽")
    b.metric("Маржа", f"{row['margin_pct']:.1f}%")
    c.metric("Размер теста", f"{int(row['test_units'])} шт.")
    d.metric("Бюджет теста", f"{row['test_budget_rub']:,.0f} ₽")
    st.write("**Почему такой балл:**", row["explanation"])
    st.write("**Что проверить:**", row["validation_tasks"])

st.download_button("Скачать рейтинг CSV", results.to_csv(index=False).encode("utf-8-sig"),
                   "product_ranking.csv", "text/csv")
st.caption("Скоринг — эвристика, не гарантия прибыли. Перед закупкой проверьте цены поставщика, MOQ, доставку, таможню, сертификацию и реальные тарифы.")
