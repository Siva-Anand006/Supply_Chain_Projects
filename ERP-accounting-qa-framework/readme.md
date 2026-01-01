# ERP Accounting QA Validation Framework

This project is a lightweight ERP-style simulation built to **validate accounting postings for supply-chain transactions**. It focuses on how business events (POs, receipts, shipments, invoices) translate into **general ledger (GL) entries**, and how those postings can be **systematically tested and validated** from a QA perspective.

The goal is not to recreate a full ERP system, but to model the **critical accounting logic and testability concerns** that QA analysts encounter when working with ERP, finance, or supply-chain platforms.

## What This Project Demonstrates

### Accounting Concepts
- **Double-entry accounting** - Every transaction maintains debit = credit balance
- **Accrual accounting** - GRNI (Goods Received Not Invoiced) clearing process
- **Inventory valuation** - Perpetual inventory tracking and COGS recognition
- **Matching principle** - Expenses matched to related revenue
- **3-Way Matching** - PO, Goods Receipt, and Invoice alignment

### QA & Testing Concepts
- **End-to-end functional testing** of complete business flows
- **Validation of expected vs actual GL postings**
- **Integration testing** across multiple transaction types
- **Acceptance criteria definition** for financial correctness
- **Defect reproduction** and root-cause analysis for accounting errors

## Business Flows Covered

### Procure-to-Pay (P2P)
1. **Purchase Order** → Inventory accrual posting
2. **Goods Receipt** → Inventory capitalization, GR/IR account update
3. **Vendor Invoice** → Accounts payable recognition, GR/IR clearing

### Order-to-Cash (O2C)
1. **Sales Order** → Revenue accrual, A/R recognition
2. **Shipment** → Inventory relief, COGS recognition
3. **Customer Invoice** → Revenue realization

### Returns & Adjustments
- **Sales Returns** with restocking fees
- **Inventory adjustments** (shrinkage/gains)
- **Partial refunds** and credit memos

## Interactive Dashboard

This project includes a **Streamlit dashboard** that provides:
- **Visual transaction flow** through supply chain processes
- **Real-time GL posting validation**
- **Accounting rule compliance checks**
- **Test execution results** with pass/fail status
- **Defect analysis examples** showing common accounting errors

### Quick Start: Run the Dashboard
```bash
# Install requirements
pip install -r requirements.txt

# Launch the interactive dashboard
streamlit run app.py