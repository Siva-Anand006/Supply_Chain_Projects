import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_conn, run_script

st.set_page_config(page_title="Procurement Data Quality & KPIs", layout="wide")

@st.cache_data
def load_df(query: str) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(query, conn)

def init_db():
    run_script("sql/schema.sql")
    run_script("sql/seed.sql")
    run_script("sql/dq_rules.sql")
    run_script("sql/kpis.sql")

# ---------- Sidebar ----------
st.sidebar.title("Controls")
if st.sidebar.button("Initialize / Reset Demo Database"):
    init_db()
    st.sidebar.success("Database reset complete ✅")

st.sidebar.markdown("---")
st.sidebar.caption("Tip: Start in **Overview** to understand the story.")

# ---------- Title / Context ----------
st.title("Procurement Data Integrity & Performance Dashboard")
st.caption(
    "This dashboard audits procurement data quality (master + transactions) and reports reliable KPIs: "
    "**On-Time Delivery**, **Purchase Price Variance**, and **Material Availability**."
)

# ---------- Load reference tables ----------
suppliers = load_df("SELECT supplier_id, supplier_name FROM suppliers ORDER BY supplier_name;")
materials = load_df("SELECT material_id, material_name FROM materials ORDER BY material_name;")

# ---------- Tabs ----------
tab_overview, tab_dq, tab_supplier, tab_cost, tab_inventory = st.tabs(
    ["Overview", "Data Quality", "Supplier Performance", "Cost (PPV)", "Inventory Risk"]
)

# =========================================================
# OVERVIEW
# =========================================================
with tab_overview:
    # KPI datasets (join names)
    issues = load_df("SELECT * FROM dq_issues;")

    otd = load_df("""
        SELECT s.supplier_name, k.received_pos, k.otd_rate
        FROM kpi_otd_by_supplier k
        JOIN suppliers s ON s.supplier_id = k.supplier_id
        ORDER BY k.otd_rate ASC;
    """)

    ppv = load_df("""
        SELECT m.material_name, k.total_ppv
        FROM kpi_ppv k
        JOIN materials m ON m.material_id = k.material_id
        ORDER BY ABS(k.total_ppv) DESC;
    """)

    avail = load_df("""
        SELECT m.material_name, a.on_hand_qty, a.safety_stock_qty, a.coverage_ratio
        FROM kpi_material_availability a
        JOIN materials m ON m.material_id = a.material_id
        ORDER BY a.coverage_ratio ASC;
    """)

    # ---- Executive KPIs ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Data Quality Issues", len(issues))
    c2.metric("High Severity Issues", int((issues["severity"] == "HIGH").sum()) if len(issues) else 0)
    c3.metric("Avg On-Time Delivery", f"{(otd['otd_rate'].mean()*100):.1f}%" if len(otd) else "—")
    c4.metric("Materials at Risk", int((avail["coverage_ratio"] < 1).sum()) if len(avail) else 0)

    st.markdown("### What to look at first")
    left, right = st.columns(2)
    with left:
        st.write("**Worst supplier OTD** (where delivery performance needs attention)")
        if len(otd):
            st.dataframe(otd.head(5).assign(otd_pct=lambda d: (d.otd_rate*100).round(2)).drop(columns=["otd_rate"]),
                         use_container_width=True)
        else:
            st.info("Initialize DB to see metrics.")
    with right:
        st.write("**Top PPV drivers** (materials causing most cost variance)")
        if len(ppv):
            st.dataframe(ppv.head(5), use_container_width=True)
        else:
            st.info("Initialize DB to see metrics.")

# =========================================================
# DATA QUALITY TAB
# =========================================================
with tab_dq:
    st.subheader("Data Quality Audit Findings")

    issues = load_df("SELECT * FROM dq_issues ORDER BY detected_at DESC;")
    if len(issues) == 0:
        st.info("No issues found. Click **Initialize / Reset Demo Database** to generate demo data.")
    else:
        sev = st.multiselect(
            "Severity filter",
            options=sorted(issues["severity"].unique()),
            default=sorted(issues["severity"].unique())
        )
        issues_f = issues[issues["severity"].isin(sev)]

        # Group summary
        s1, s2 = st.columns(2)
        with s1:
            st.write("Issues by rule")
            by_rule = issues_f.groupby("rule_name", as_index=False).size().sort_values("size", ascending=False)
            st.plotly_chart(px.bar(by_rule, x="rule_name", y="size"), use_container_width=True)
        with s2:
            st.write("Issues by table")
            by_tbl = issues_f.groupby("table_name", as_index=False).size().sort_values("size", ascending=False)
            st.plotly_chart(px.bar(by_tbl, x="table_name", y="size"), use_container_width=True)

        st.write("Issue log (drill-down)")
        st.dataframe(issues_f, use_container_width=True)

# =========================================================
# SUPPLIER PERFORMANCE TAB
# =========================================================
with tab_supplier:
    st.subheader("Supplier On-Time Delivery (OTD)")

    otd = load_df("""
        SELECT s.supplier_id, s.supplier_name, k.received_pos, k.otd_rate
        FROM kpi_otd_by_supplier k
        JOIN suppliers s ON s.supplier_id = k.supplier_id
        ORDER BY k.otd_rate ASC;
    """)

    if len(otd) == 0:
        st.info("Initialize DB first.")
    else:
        supplier_choice = st.selectbox("Focus supplier", options=["All suppliers"] + otd["supplier_name"].tolist())

        view = otd.copy()
        if supplier_choice != "All suppliers":
            view = view[view["supplier_name"] == supplier_choice]

        view["otd_pct"] = (view["otd_rate"] * 100).round(2)

        st.plotly_chart(px.bar(view, x="supplier_name", y="otd_pct"), use_container_width=True)
        st.dataframe(view[["supplier_name", "received_pos", "otd_pct"]], use_container_width=True)

# =========================================================
# COST (PPV) TAB
# =========================================================
with tab_cost:
    st.subheader("Purchase Price Variance (PPV)")
    st.caption("PPV shows which materials are costing more (or less) than the standard price baseline.")

    ppv = load_df("""
        SELECT m.material_id, m.material_name, k.total_ppv
        FROM kpi_ppv k
        JOIN materials m ON m.material_id = k.material_id
        ORDER BY ABS(k.total_ppv) DESC;
    """)

    if len(ppv) == 0:
        st.info("Initialize DB first.")
    else:
        top_n = st.slider("Show top N materials", 5, 50, 10)
        view = ppv.head(top_n)

        st.plotly_chart(px.bar(view, x="material_name", y="total_ppv"), use_container_width=True)
        st.dataframe(view, use_container_width=True)

# =========================================================
# INVENTORY TAB
# =========================================================
with tab_inventory:
    st.subheader("Material Availability / Stock Risk")
    st.caption("Coverage ratio < 1 means on-hand stock is below safety stock (risk of shortage).")

    avail = load_df("""
        SELECT m.material_name, a.on_hand_qty, a.safety_stock_qty, a.coverage_ratio
        FROM kpi_material_availability a
        JOIN materials m ON m.material_id = a.material_id
        ORDER BY a.coverage_ratio ASC;
    """)

    if len(avail) == 0:
        st.info("Initialize DB first.")
    else:
        risk_only = st.checkbox("Show only at-risk materials (coverage < 1)", value=True)
        view = avail.copy()
        if risk_only:
            view = view[view["coverage_ratio"] < 1]

        st.plotly_chart(px.scatter(view, x="material_name", y="coverage_ratio", size="on_hand_qty"), use_container_width=True)
        st.dataframe(view, use_container_width=True)
