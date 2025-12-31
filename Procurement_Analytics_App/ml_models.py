import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier

def _build_risk_label(df: pd.DataFrame) -> pd.Series:
    """
    Proxy label because the dataset doesn't contain an explicit 'risk' field.
    We consider an order "at risk" if any of these hold:
      - defect_rate > 5%
      - compliance == "No"
      - lead_time_days > supplier-specific 75th percentile
    """
    d = df.copy()
    delivered = d["Order_Status"].astype(str).str.lower().eq("delivered")
    d = d[delivered].copy()

    # supplier 75th percentile lead time threshold
    thr = d.groupby("Supplier")["Lead_Time_Days"].quantile(0.75).to_dict()
    d["LT_Thr"] = d["Supplier"].map(thr)

    at_risk = (
        (d["Defect_Rate"] > 0.05) |
        (d["Compliance"].astype(str).str.lower().eq("no")) |
        (d["Lead_Time_Days"] > d["LT_Thr"])
    ).astype(int)

    # Align back to original index (non-delivered become 0 by default)
    y = pd.Series(0, index=df.index, dtype=int)
    y.loc[d.index] = at_risk
    return y

def train_supplier_risk_model(df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42):
    d = df.copy()

    y = _build_risk_label(d)

    feature_cols = ["Item_Category","Quantity","Unit_Price","Negotiated_Price","Lead_Time_Days","Defect_Rate","Savings_Pct","Compliance"]
    X = d[feature_cols].copy()

    cat_cols = ["Item_Category","Compliance"]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    pre = ColumnTransformer(
        transformers=[
            ("cat", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", OneHotEncoder(handle_unknown="ignore"))
            ]), cat_cols),
            ("num", Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="median"))
            ]), num_cols)
        ],
        remainder="drop"
    )

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=random_state,
        class_weight="balanced_subsample",
        max_depth=None
    )

    clf = Pipeline(steps=[("pre", pre), ("model", model)])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    report = classification_report(y_test, y_pred, digits=3)

    feature_info = {"feature_cols": feature_cols}
    return clf, report, feature_info

def predict_supplier_risk(model, df: pd.DataFrame, feature_info: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(df.columns) + ["Risk_Label","Risk_Prob"])

    X = df[feature_info["feature_cols"]].copy()
    prob = model.predict_proba(X)[:,1]
    label = (prob >= 0.5).astype(int)

    out = df.copy()
    out["Risk_Prob"] = prob
    out["Risk_Label"] = label
    return out

def forecast_category_prices(df: pd.DataFrame, category: str, months: int = 6):
    """
    Returns:
      - hist: DataFrame(ds, y) monthly avg unit price
      - fcst: DataFrame(ds, yhat) forecast
    Uses Prophet if available; otherwise seasonal naive baseline.
    """
    d = df.copy()
    d = d[d["Item_Category"] == category].copy()
    d = d.dropna(subset=["Order_Date","Unit_Price"])
    if d.empty:
        hist = pd.DataFrame(columns=["ds","y"])
        fcst = pd.DataFrame(columns=["ds","yhat"])
        return hist, fcst

    d["month"] = d["Order_Date"].dt.to_period("M").dt.to_timestamp()
    hist = d.groupby("month")["Unit_Price"].mean().reset_index()
    hist.columns = ["ds","y"]
    hist = hist.sort_values("ds")

    # Try Prophet
    try:
        from prophet import Prophet
        m = Prophet()
        m.fit(hist)
        future = m.make_future_dataframe(periods=months, freq="MS")
        forecast = m.predict(future)
        fcst = forecast[["ds","yhat"]].copy()
        return hist, fcst
    except Exception:
        # Seasonal naive (repeat last 12 months pattern if possible, else repeat last value)
        if len(hist) >= 12:
            season = hist["y"].tail(12).to_numpy()
        else:
            season = np.array([hist["y"].iloc[-1]])

        last_date = hist["ds"].max()
        future_dates = pd.date_range(last_date + pd.offsets.MonthBegin(1), periods=months, freq="MS")
        yhat = []
        for i in range(months):
            yhat.append(float(season[i % len(season)]))
        fcst = pd.DataFrame({"ds": future_dates, "yhat": yhat})
        return hist, pd.concat([hist.rename(columns={"y":"yhat"}), fcst], ignore_index=True)
