import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from data_preprocessing import load_and_prepare_data
from utils import (
    kpi_overview,
    supplier_scorecard,
    spend_sunburst,
    savings_opportunities_table,
    generate_insights,
    what_if_otd_impact,
)
from ml_models import train_supplier_risk_model, predict_supplier_risk, forecast_category_prices

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False

st.set_page_config(page_title="Procurement Intelligence", page_icon="📦", layout="wide")

@st.cache_data(show_spinner=False)
def get_data(csv_path: str) -> pd.DataFrame:
    return load_and_prepare_data(csv_path)

def aggrid(df: pd.DataFrame, height: int = 360):
    if not HAS_AGGRID:
        st.dataframe(df, use_container_width=True, height=height)
        return
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=True)
    gridOptions = gb.build()
    AgGrid(df, gridOptions=gridOptions, height=height, fit_columns_on_grid_load=True)

st.title("📦 Procurement Intelligence & KPI Dashboard")
st.caption("Interactive procurement KPIs + predictive analytics on a Kaggle-style procurement dataset.")

with st.sidebar:
    st.header("Data")
    csv_path = st.text_input("CSV path", value="Procurement KPI Analysis Dataset.csv")
    st.divider()
    page = st.radio(
        "Navigate",
        ["1) KPI Dashboard", "2) Supplier Risk Predictor", "3) Price Forecasting", "4) What‑If Analysis", "5) Automated Insights"],
        index=0
    )

df = get_data(csv_path)

# Global filters
with st.sidebar:
    st.header("Filters")
    delivered_only = st.checkbox("Delivered only", value=True)
    cat_options = ["(All)"] + sorted(df["Item_Category"].dropna().unique().tolist())
    supplier_options = ["(All)"] + sorted(df["Supplier"].dropna().unique().tolist())
    category = st.selectbox("Category", cat_options, index=0)
    supplier = st.selectbox("Supplier", supplier_options, index=0)
    date_min, date_max = df["Order_Date"].min(), df["Order_Date"].max()
    start, end = st.date_input("Order date range", (date_min, date_max))

f = df.copy()
f = f[(f["Order_Date"] >= pd.to_datetime(start)) & (f["Order_Date"] <= pd.to_datetime(end))]
if delivered_only:
    f = f[f["Order_Status"].str.lower().eq("delivered")]
if category != "(All)":
    f = f[f["Item_Category"] == category]
if supplier != "(All)":
    f = f[f["Supplier"] == supplier]

if page.startswith("1"):
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("KPI Overview")
        metrics = kpi_overview(f)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Orders", f"{metrics['orders']:,}")
        c2.metric("Spend (Actual)", f"${metrics['spend_actual']:,.0f}")
        c3.metric("Savings (vs list)", f"${metrics['savings_total']:,.0f}")
        c4.metric("Avg Lead Time", f"{metrics['avg_lead_time']:.1f} days")

        st.markdown("#### Spend by Category")
        spend_cat = (f.groupby("Item_Category", dropna=False)["Line_Total_Actual"].sum()
                       .sort_values(ascending=False)
                       .reset_index())
        fig = px.bar(spend_cat, x="Item_Category", y="Line_Total_Actual")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Savings Opportunities")
        opp = savings_opportunities_table(f)
        aggrid(opp, height=320)

    with right:
        st.subheader("Supplier Performance Scorecard")
        sc = supplier_scorecard(f)
        aggrid(sc, height=320)

        st.markdown("#### Spend Breakdown (Sunburst)")
        fig2 = spend_sunburst(f)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### Sample Rows")
    aggrid(f.sort_values("Order_Date", ascending=False).head(25), height=280)

elif page.startswith("2"):
    st.subheader("Supplier Risk Predictor (Random Forest)")
    st.write("This model flags **at‑risk orders** (proxy for supplier risk) using engineered signals: lead time, defect rate, compliance, and savings volatility.")
    with st.expander("Train / Re-train model", expanded=True):
        test_size = st.slider("Test split", 0.1, 0.4, 0.2, 0.05)
        random_state = st.number_input("Random seed", 0, 9999, 42)
        model, report, feature_info = train_supplier_risk_model(df, test_size=float(test_size), random_state=int(random_state))
        st.code(report)

    st.markdown("#### Predict risk for filtered data")
    preds = predict_supplier_risk(model, f, feature_info)
    aggrid(preds.sort_values("Risk_Prob", ascending=False).head(50), height=380)

    st.info("Tip: Use filters on the left to narrow to a supplier/category and see the highest risk rows.")

elif page.startswith("3"):
    st.subheader("Price Forecasting (per Category)")
    cats = sorted(df["Item_Category"].dropna().unique().tolist())
    cat = st.selectbox("Choose category", cats, index=0)
    horizon = st.slider("Forecast months", 3, 12, 6, 1)

    hist, fcst = forecast_category_prices(df, cat, months=int(horizon))

    col1, col2 = st.columns([1,1])
    with col1:
        st.markdown("#### Historical Monthly Avg Unit Price")
        fig = px.line(hist, x="ds", y="y")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("#### Forecast")
        fig2 = px.line(fcst, x="ds", y="yhat")
        st.plotly_chart(fig2, use_container_width=True)

    st.caption("Forecast uses Prophet when available; otherwise a lightweight seasonal-naive baseline.")

elif page.startswith("4"):
    st.subheader("What‑If Analysis (OTD proxy)")
    st.write("Because the dataset has no promised date, we use a **lead-time SLA proxy**: an order is considered on-time if lead time ≤ SLA (default = 75th percentile lead time per category).")

    target_otd = st.slider("Target OTD (%)", 80, 99, 95, 1)
    sla_quantile = st.slider("SLA quantile used as baseline", 0.50, 0.95, 0.75, 0.05)
    result = what_if_otd_impact(df, target_otd=float(target_otd)/100.0, sla_quantile=float(sla_quantile))

    c1, c2, c3 = st.columns(3)
    c1.metric("Current OTD (proxy)", f"{result['current_otd']*100:.1f}%")
    c2.metric("Suppliers meeting target", f"{result['suppliers_meeting_target']:,} / {result['supplier_count']:,}")
    c3.metric("Potential savings (proxy)", f"${result['potential_savings']:,.0f}")

    st.markdown("#### Suppliers to review (below target)")
    aggrid(result["below_target"].head(50), height=380)

elif page.startswith("5"):
    st.subheader("Automated Insights Generator")
    st.write("Rule-based insights + simple NLP phrasing. Use filters on the left to focus on a supplier or category.")
    insights = generate_insights(f)
    for i, item in enumerate(insights, 1):
        st.write(f"**{i}.** {item}")

    st.markdown("#### Evidence snapshot")
    snap = f.sort_values("Order_Date", ascending=False).head(15)[
        ["PO_ID","Supplier","Item_Category","Order_Date","Delivery_Date","Lead_Time_Days","Defect_Rate","Compliance","Savings_Total"]
    ]
    aggrid(snap, height=300)
