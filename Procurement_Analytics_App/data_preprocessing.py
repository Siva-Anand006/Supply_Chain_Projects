import pandas as pd
import numpy as np

NUM_COLS = ["Quantity", "Unit_Price", "Negotiated_Price", "Defective_Units"]

def load_and_prepare_data(csv_path: str) -> pd.DataFrame:
    """
    Loads the provided procurement CSV and engineers consistent features:
    - Lead_Time_Days
    - Defect_Rate
    - Line totals and savings
    - Basic data quality fixes
    """
    df = pd.read_csv(csv_path).copy()

    # Dates
    df["Order_Date"] = pd.to_datetime(df["Order_Date"], errors="coerce")
    df["Delivery_Date"] = pd.to_datetime(df["Delivery_Date"], errors="coerce")

    # Numerics
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Fill missing defective units as 0 when delivered, otherwise NaN is okay
    delivered = df["Order_Status"].astype(str).str.lower().eq("delivered")
    df.loc[delivered & df["Defective_Units"].isna(), "Defective_Units"] = 0.0

    # Lead time (days)
    df["Lead_Time_Days"] = (df["Delivery_Date"] - df["Order_Date"]).dt.days
    df["Lead_Time_Days"] = df["Lead_Time_Days"].clip(lower=0)

    # Defect rate
    df["Defect_Rate"] = (df["Defective_Units"] / df["Quantity"]).replace([np.inf, -np.inf], np.nan)
    df["Defect_Rate"] = df["Defect_Rate"].fillna(0.0).clip(lower=0)

    # Line totals
    df["Line_Total_List"] = df["Quantity"] * df["Unit_Price"]
    df["Line_Total_Actual"] = df["Quantity"] * df["Negotiated_Price"]

    # Savings
    df["Savings_Per_Unit"] = (df["Unit_Price"] - df["Negotiated_Price"]).fillna(0.0)
    df["Savings_Total"] = df["Savings_Per_Unit"] * df["Quantity"]
    df["Savings_Pct"] = (df["Savings_Per_Unit"] / df["Unit_Price"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Light normalization
    df["Compliance"] = df["Compliance"].astype(str).str.strip()
    df["Supplier"] = df["Supplier"].astype(str).str.strip()
    df["Item_Category"] = df["Item_Category"].astype(str).str.strip()
    df["Order_Status"] = df["Order_Status"].astype(str).str.strip()

    return df
