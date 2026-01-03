---

# Supply Chain Data Integrity & Procurement KPI Dashboard

This project demonstrates how procurement data quality directly impacts performance reporting, and how SQL-based validation combined with lightweight analytics can make procurement KPIs reliable and actionable.

The goal was not just to build charts, but to **simulate a real ERP-style procurement environment**, audit the data for common integrity issues, and then report meaningful KPIs only after the data is validated.

---

## What this project does

At a high level, the project does three things:

1. **Audits procurement master and transactional data**
2. **Identifies and logs data quality issues using SQL rules**
3. **Visualizes clean procurement KPIs in an interactive Streamlit dashboard**

The dashboard is designed so that a first-time viewer can quickly understand:

* whether there are data quality problems,
* which suppliers are underperforming,
* where costs are deviating from standards,
* and which materials are at risk of stockouts.

---

## Data used

The dataset is **synthetically generated** and stored in a local SQLite database.

It is intentionally designed to look like data from a typical ERP procurement module (e.g., SAP MM / Oracle Procurement), including:

* suppliers and lead times,
* materials and units of measure,
* purchase orders and PO lines,
* inventory and safety stock,
* standard material prices.

Several records intentionally contain errors (negative lead times, missing receipt dates, invalid prices, etc.) to simulate real-world data quality problems and test the audit rules.

No real or proprietary company data is used.

---

## Data quality audit

Before any KPIs are calculated, the project applies explicit **data quality rules** in SQL, such as:

* Supplier lead time must be greater than zero
* Units of measure cannot be missing
* Purchase order quantities must be positive
* Unit prices cannot be negative
* Purchase orders marked as “RECEIVED” must have a receipt date

Each violation is logged into a dedicated `dq_issues` table with:

* rule name,
* severity level,
* affected table,
* record identifier,
* issue description,
* detection timestamp.

This provides traceability and mimics how data governance and QA checks are handled in real analytics pipelines.

---

## KPIs implemented

Once the data quality checks are applied, the project calculates the following procurement KPIs using SQL views:

### On-Time Delivery (OTD)

Measures supplier delivery performance by checking whether goods were received on or before the promised delivery date.

### Purchase Price Variance (PPV)

Compares actual purchase prices against standard prices to identify cost overruns or savings.

### Material Availability

Compares on-hand inventory against safety stock levels to highlight potential stockout risks.

All KPIs are computed in SQL and then visualized, keeping the logic transparent and auditable.

---

## Dashboard overview

The Streamlit dashboard is organized into clear sections:

* **Overview** – executive summary with key metrics and problem areas
* **Data Quality** – audit findings with severity breakdowns
* **Supplier Performance** – on-time delivery analysis by supplier
* **Cost (PPV)** – materials driving the highest price variance
* **Inventory Risk** – items below safety stock thresholds

The layout is designed to guide a first-time user from data integrity → performance insights → operational risks.

---

## Tech stack

* Python
* SQLite
* SQL (data quality rules and KPI logic)
* Streamlit
* Pandas
* Plotly

---

## How to run the project locally

```bash
# create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# install dependencies
pip install -r requirements.txt

# run the app
streamlit run app.py
```

Once the app opens:

1. Click **“Initialize / Reset Demo Database”** in the sidebar
2. Navigate through the tabs starting from **Overview**

---

