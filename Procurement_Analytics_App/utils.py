import pandas as pd
import numpy as np
import plotly.express as px

def kpi_overview(df: pd.DataFrame) -> dict:
    if df.empty:
        return dict(orders=0, spend_actual=0.0, savings_total=0.0, avg_lead_time=0.0)

    return {
        "orders": int(len(df)),
        "spend_actual": float(df["Line_Total_Actual"].sum()),
        "savings_total": float(df["Savings_Total"].sum()),
        "avg_lead_time": float(df["Lead_Time_Days"].mean()),
    }

def supplier_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Supplier","Orders","Spend_Actual","Avg_Lead_Time","Defect_Rate","Compliance_Rate","Savings_Total"])

    g = df.groupby("Supplier", dropna=False).agg(
        Orders=("PO_ID","count"),
        Spend_Actual=("Line_Total_Actual","sum"),
        Avg_Lead_Time=("Lead_Time_Days","mean"),
        Defect_Rate=("Defect_Rate","mean"),
        Compliance_Rate=("Compliance", lambda s: (s.astype(str).str.lower()=="yes").mean()),
        Savings_Total=("Savings_Total","sum")
    ).reset_index()

    # Simple score (0-100): you can refine this later
    # High compliance + low defects + low lead time + high savings
    g["Score"] = (
        35*(g["Compliance_Rate"]) +
        25*(1 - g["Defect_Rate"].clip(0,1)) +
        20*(1 - (g["Avg_Lead_Time"] / (g["Avg_Lead_Time"].max() + 1e-9))) +
        20*(g["Savings_Total"] / (g["Savings_Total"].max() + 1e-9))
    ) * 100

    return g.sort_values("Score", ascending=False)

def spend_sunburst(df: pd.DataFrame):
    if df.empty:
        return px.sunburst(names=["No data"])
    # Dataset lacks item-level info, so we use PO_ID as leaf
    return px.sunburst(
        df,
        path=["Item_Category","Supplier","PO_ID"],
        values="Line_Total_Actual"
    )

def savings_opportunities_table(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["PO_ID","Supplier","Item_Category","Order_Date","Quantity","Unit_Price","Negotiated_Price","Savings_Total","Savings_Pct"])

    cols = ["PO_ID","Supplier","Item_Category","Order_Date","Quantity","Unit_Price","Negotiated_Price","Savings_Total","Savings_Pct","Compliance","Order_Status"]
    out = df[cols].copy()
    out["Order_Date"] = out["Order_Date"].dt.strftime("%Y-%m-%d")
    return out.sort_values("Savings_Total", ascending=False).head(top_n)

def generate_insights(df: pd.DataFrame) -> list[str]:
    insights = []
    if df.empty:
        return ["No data in the current filter. Try widening the date range or removing filters."]

    # 1) Defect spike
    by_supp = df.groupby("Supplier").agg(
        defect=("Defect_Rate","mean"),
        orders=("PO_ID","count"),
        lead=("Lead_Time_Days","mean"),
        compliance=("Compliance", lambda s: (s.astype(str).str.lower()=="yes").mean())
    ).reset_index()

    worst_def = by_supp.sort_values("defect", ascending=False).head(1)
    if not worst_def.empty and worst_def.iloc[0]["defect"] > 0.05:
        s = worst_def.iloc[0]["Supplier"]
        pct = worst_def.iloc[0]["defect"]*100
        insights.append(f"Supplier **{s}** has a high average defect rate ({pct:.1f}%). Consider a quality audit or tighter incoming inspection.")

    # 2) Compliance gaps
    low_comp = by_supp.sort_values("compliance", ascending=True).head(1)
    if not low_comp.empty and low_comp.iloc[0]["compliance"] < 0.9:
        s = low_comp.iloc[0]["Supplier"]
        pct = low_comp.iloc[0]["compliance"]*100
        insights.append(f"Supplier **{s}** shows low compliance ({pct:.0f}% 'Yes'). Consider enforcing contract terms or switching to compliant suppliers.")

    # 3) Lead time issues
    slow = by_supp.sort_values("lead", ascending=False).head(1)
    if not slow.empty and slow.iloc[0]["lead"] > df["Lead_Time_Days"].median():
        s = slow.iloc[0]["Supplier"]
        days = slow.iloc[0]["lead"]
        insights.append(f"Supplier **{s}** has the longest average lead time ({days:.1f} days). Consider safety stock, earlier ordering, or alternate suppliers.")

    # 4) Savings opportunity concentration
    top_cat = (df.groupby("Item_Category")["Savings_Total"].sum().sort_values(ascending=False).head(1))
    if len(top_cat) > 0:
        cat = top_cat.index[0]
        val = float(top_cat.iloc[0])
        insights.append(f"Category **{cat}** contributes the most negotiated savings (${val:,.0f}). Prioritize negotiation playbooks here.")

    # Always include a generic operational insight
    insights.append("Review orders with **high savings but low compliance**: they may represent policy exceptions or maverick buying.")
    return insights

def what_if_otd_impact(df: pd.DataFrame, target_otd: float = 0.95, sla_quantile: float = 0.75) -> dict:
    """
    Proxy OTD: lead time <= SLA (quantile) per category.
    If you later have promised delivery dates, replace this with true OTD.
    """
    d = df.copy()
    delivered = d["Order_Status"].astype(str).str.lower().eq("delivered")
    d = d[delivered & d["Lead_Time_Days"].notna()].copy()

    if d.empty:
        return {"current_otd": 0.0, "supplier_count": 0, "suppliers_meeting_target": 0,
                "potential_savings": 0.0, "below_target": pd.DataFrame()}

    sla = d.groupby("Item_Category")["Lead_Time_Days"].quantile(sla_quantile).to_dict()
    d["SLA_Days"] = d["Item_Category"].map(sla)
    d["On_Time"] = (d["Lead_Time_Days"] <= d["SLA_Days"]).astype(int)

    # Current OTD
    current_otd = float(d["On_Time"].mean())

    # Supplier OTD
    s_otd = d.groupby("Supplier").agg(
        Orders=("PO_ID","count"),
        OTD=("On_Time","mean"),
        Spend=("Line_Total_Actual","sum"),
        Savings=("Savings_Total","sum"),
        Avg_Lead=("Lead_Time_Days","mean"),
        Defect=("Defect_Rate","mean"),
        Compliance=("Compliance", lambda s: (s.astype(str).str.lower()=="yes").mean())
    ).reset_index()

    supplier_count = int(len(s_otd))
    meeting = s_otd[s_otd["OTD"] >= target_otd]
    below = s_otd[s_otd["OTD"] < target_otd].sort_values("OTD")

    # Potential savings proxy: assume dropping below-target suppliers shifts to median savings rate in that category
    # This is a placeholder business assumption for the demo.
    baseline_savings_rate = float(d["Savings_Pct"].median())
    potential_savings = float(below["Spend"].sum() * baseline_savings_rate)

    return {
        "current_otd": current_otd,
        "supplier_count": supplier_count,
        "suppliers_meeting_target": int(len(meeting)),
        "potential_savings": potential_savings,
        "below_target": below
    }
