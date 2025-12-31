# Procurement Intelligence & KPI Dashboard with Predictive Analytics

A Streamlit web app that turns a procurement CSV into:
- Interactive KPI dashboard (supplier scorecards, spend analysis, savings tracker)
- Supplier risk predictor (Random Forest) using engineered proxy labels
- Category price forecasting (Prophet if available, otherwise seasonal-naive)
- What-if analysis on an on-time-delivery proxy
- Automated insight generator (rule-based narrative insights)

> Note: The provided dataset does not include promised delivery dates or payment terms.
> This app uses **proxy logic** (lead time SLA quantiles, defects, compliance) to demonstrate the idea.


## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

## 2) Run

Place your CSV beside `app.py` or pass the full path in the app.

```bash
streamlit run app.py
```

Default CSV name expected: `Procurement KPI Analysis Dataset.csv`

## 3) Project structure

```
Procurement_Analytics_App/
├── app.py
├── requirements.txt
├── data_preprocessing.py
├── ml_models.py
├── utils.py
└── README.md
```


