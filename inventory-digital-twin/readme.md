# Inventory Digital Twin — Simulation & Optimization (s, S)

An interactive **decision-support simulation** that models a warehouse inventory system under uncertainty and identifies cost-effective inventory policies using **Monte Carlo simulation** and **policy optimization**.

This project demonstrates **end-to-end systems thinking**: from problem definition and modeling assumptions to experimentation, optimization, and visualization via a **Streamlit app**.

---

## Project Overview

Inventory decisions are made under uncertainty: fluctuating demand, variable lead times, and cost trade-offs between service level and holding inventory.

Instead of relying on static formulas or averages, this project builds a **digital twin** of a warehouse inventory system using **discrete-event simulation** to answer questions such as:

- What happens if demand increases by 30%?
- How do lead-time disruptions affect service levels?
- What (s, S) policy achieves a ≥98% service level at minimum cost?

The result is an **interactive simulation tool** that allows users to test scenarios and identify optimal inventory policies.

---

## System Description

### Modeled System

- Single warehouse
- Single SKU
- One upstream supplier
- Continuous review inventory policy *(s, S)*

### Inventory Policy

- **Reorder Point (s):** trigger reorder when inventory position ≤ s
- **Order-Up-To Level (S):** replenish inventory up to S

This is a standard policy used in real-world supply chains and spare-parts systems.

---

## Modeling Assumptions

| Component     | Assumption                                     |
| ------------- | ---------------------------------------------- |
| Demand        | Poisson process (stochastic arrivals)          |
| Demand size   | 1 unit per arrival                             |
| Lead time     | Random (Uniform or Normal)                     |
| Review policy | Continuous                                     |
| Stockouts     | Backorders or lost sales (configurable)        |
| Orders        | One outstanding order at a time                |
| Costs         | Holding, stockout penalty, fixed ordering cost |

All assumptions are explicitly documented and adjustable in the app.

---

## Key Performance Metrics

The simulation tracks:

- **Service level (fill rate)**
- **Total system cost**
  - Holding cost
  - Stockout penalty
  - Fixed ordering cost
- Average inventory level
- Number of orders placed

Results are reported as:

- Mean values
- **95% confidence intervals** from Monte Carlo simulation

---

## What the App Does

The Streamlit app provides three core capabilities:

### 1️⃣ Run Simulation

- Select an *(s, S)* policy
- Run Monte Carlo simulation
- View service level & cost with confidence intervals
- Download run-level results as CSV

### 2️⃣ Scenario Analysis

Compare the same policy under:

- Baseline conditions
- Demand spike (+30%)
- Lead-time disruption (scaled mean/variance)

Results are visualized with uncertainty bounds.

### 3️⃣ Policy Optimization

- Grid search over feasible *(s, S)* policies
- Objective: **minimize total cost**
- Constraint: **service level ≥ user-defined threshold**
- Visualizes **cost vs service trade-off**
- Highlights optimal feasible policy

---

## Methodology

- **Discrete-event simulation** (event-driven inventory dynamics)
- **Monte Carlo simulation** (replicated runs under randomness)
- **Constrained optimization** via policy grid search
- Statistical reporting using confidence intervals
- Interactive visualization and CSV export

This approach mirrors how simulation is used in real operational decision-making.

---

## Tech Stack

- Python
- NumPy
- Pandas
- Matplotlib
- Streamlit

---

## ▶How to Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py

inventory-digital-twin/
│
├── app.py               # Streamlit application
├── requirements.txt     # Dependencies
├── README.md            # Project documentation

