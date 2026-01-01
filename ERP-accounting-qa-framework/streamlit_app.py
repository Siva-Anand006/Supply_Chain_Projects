import streamlit as st
import pandas as pd
from pathlib import Path

from scaqa.db import connect, init_db, seed
from scaqa.engine import (
    create_po, receive_goods, post_vendor_invoice,
    create_so, ship_goods, post_customer_invoice,
    inventory_adjust
)
from scaqa.validator import validate_posting

# -----------------------------
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@st.cache_resource
def get_conn():
    conn = connect()
    init_db(conn, str(Path(__file__).resolve().parent / "schema.sql"))
    seed(conn)
    return conn


def fetch_gl(conn) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT h.created_at, h.source_type, h.source_id, h.memo, l.acct, l.dr, l.cr
        FROM gl_header h
        JOIN gl_line l ON h.je_id = l.je_id
        ORDER BY h.created_at DESC, h.je_id, l.acct
        """
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def fetch_recent_sources(conn, limit=50) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT created_at, source_type, source_id, memo
        FROM gl_header
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def reset_demo(conn):
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.executescript(
            """
            DELETE FROM gl_line;
            DELETE FROM gl_header;

            DELETE FROM customer_invoice;
            DELETE FROM shipment;
            DELETE FROM sales_order;

            DELETE FROM vendor_invoice;
            DELETE FROM goods_receipt;
            DELETE FROM purchase_order;

            -- Restore starting inventory
            UPDATE inventory_balance SET qty_on_hand=100 WHERE item_id='ITEM-001';
            """
        )
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")


def on_hand(conn) -> float:
    r = conn.execute("SELECT qty_on_hand FROM inventory_balance WHERE item_id='ITEM-001'").fetchone()
    return float(r["qty_on_hand"])

def expected_for(conn, source_type: str, source_id: str) -> list[dict]:
    if source_type == "GR":
        r = conn.execute(
            """
            SELECT gr.qty_received AS qty, po.unit_price AS price
            FROM goods_receipt gr
            JOIN purchase_order po ON po.po_id = gr.po_id
            WHERE gr.gr_id=?
            """,
            (source_id,),
        ).fetchone()
        value = float(r["qty"]) * float(r["price"])
        return [{"acct": "INV", "dr": value, "cr": 0.0}, {"acct": "GRNI", "dr": 0.0, "cr": value}]

    if source_type == "VINV":
        r = conn.execute("SELECT amount FROM vendor_invoice WHERE inv_id=?", (source_id,)).fetchone()
        amt = float(r["amount"])
        return [{"acct": "GRNI", "dr": amt, "cr": 0.0}, {"acct": "AP", "dr": 0.0, "cr": amt}]

    if source_type == "SHIP":
        r = conn.execute(
            """
            SELECT s.qty_shipped AS qty, i.std_cost AS cost
            FROM shipment s
            JOIN sales_order so ON so.so_id = s.so_id
            JOIN item i ON i.item_id = so.item_id
            WHERE s.ship_id=?
            """,
            (source_id,),
        ).fetchone()
        value = float(r["qty"]) * float(r["cost"])
        return [{"acct": "COGS", "dr": value, "cr": 0.0}, {"acct": "INV", "dr": 0.0, "cr": value}]

    if source_type == "CINV":
        r = conn.execute("SELECT amount FROM customer_invoice WHERE cinv_id=?", (source_id,)).fetchone()
        amt = float(r["amount"])
        return [{"acct": "AR", "dr": amt, "cr": 0.0}, {"acct": "REV", "dr": 0.0, "cr": amt}]

    if source_type == "ADJ":
        # For ADJ, our engine posts either:
        # shrink: Dr ADJ_EXP / Cr INV
        # gain:   Dr INV / Cr ADJ_EXP
        rows = conn.execute(
            """
            SELECT l.acct, l.dr, l.cr
            FROM gl_header h JOIN gl_line l ON h.je_id=l.je_id
            WHERE h.source_type='ADJ' AND h.source_id=?
            """,
            (source_id,),
        ).fetchall()
        return [{"acct": r["acct"], "dr": float(r["dr"]), "cr": float(r["cr"])} for r in rows]

    return []


# -----------------------------
# Streamlit UI
# -----------------------------
def main():
    st.set_page_config(page_title="Supply Chain Accounting QA", layout="wide")

    conn = get_conn()

    st.title("Supply Chain Accounting QA Validation Framework")
    st.caption("A simple ERP simulation: post transactions → see GL impact → validate expected vs actual postings.")

    # Sidebar: demo controls
    with st.sidebar:
        st.subheader("Demo Controls")
        st.metric("On-hand (ITEM-001)", f"{on_hand(conn):.0f}")

        if st.button("Reset demo data", use_container_width=True):
            reset_demo(conn)
            st.success("Reset complete. Inventory restored to 100.")

        st.divider()
        st.subheader("Quick Tips")
        st.write(
            "- Use **Guided Demo** to run a full scenario\n"
            "- Use **Validation** to show PASS/FAIL like a QA tool\n"
            "- Use **Ledger** to explain accounting impact"
        )

    # Tabs
    tab_demo, tab_ledger, tab_validate = st.tabs(["Guided Demo", "General Ledger", "Validation (QA)"])
    # -----------------------------
    with tab_demo:
        st.subheader("1) Choose a scenario")
        scenario = st.radio(
            "Scenario",
            ["P2P: PO → Goods Receipt → Vendor Invoice", "O2C: Sales Order → Shipment → Customer Invoice", "Inventory Adjustment"],
            horizontal=False,
        )

        st.divider()
        st.subheader("2) Post transactions")

        if scenario.startswith("P2P"):
            c1, c2, c3 = st.columns(3)
            with c1:
                vendor = st.text_input("Vendor", "VendorA")
            with c2:
                qty = st.number_input("Quantity", min_value=1.0, value=10.0, step=1.0)
            with c3:
                unit_price = st.number_input("Unit Price", min_value=0.01, value=12.0, step=0.5)

            colA, colB, colC = st.columns([1, 1, 2])
            with colA:
                if st.button("Create PO", use_container_width=True):
                    po_id = create_po(conn, vendor, "ITEM-001", qty, unit_price)
                    st.success(f"PO created: {po_id}")
                    st.session_state["last_po"] = po_id

            with colB:
                if st.button("Post GR", use_container_width=True):
                    po_id = st.session_state.get("last_po") or _latest_id(conn, "purchase_order", "po_id")
                    if not po_id:
                        st.error("Create a PO first.")
                    else:
                        gr_id = receive_goods(conn, po_id, qty_received=qty)
                        st.success(f"GR posted: {gr_id}")
                        st.session_state["last_gr"] = gr_id

            with colC:
                if st.button("Post Vendor Invoice", use_container_width=True):
                    po_id = st.session_state.get("last_po") or _latest_id(conn, "purchase_order", "po_id")
                    if not po_id:
                        st.error("Create a PO first.")
                    else:
                        amount = float(qty) * float(unit_price)
                        inv_id = post_vendor_invoice(conn, po_id, amount)
                        st.success(f"Vendor Invoice posted: {inv_id}  (Amount={amount:.2f})")
                        st.session_state["last_vinv"] = inv_id

            st.info("Expected postings: GR → Dr INV / Cr GRNI. Vendor Invoice → Dr GRNI / Cr AP.")

        elif scenario.startswith("O2C"):
            c1, c2, c3 = st.columns(3)
            with c1:
                customer = st.text_input("Customer", "CustomerA")
            with c2:
                qty = st.number_input("Quantity", min_value=1.0, value=5.0, step=1.0)
            with c3:
                unit_price = st.number_input("Sales Unit Price", min_value=0.01, value=25.0, step=1.0)

            colA, colB, colC = st.columns([1, 1, 2])
            with colA:
                if st.button("Create SO", use_container_width=True):
                    so_id = create_so(conn, customer, "ITEM-001", qty, unit_price)
                    st.success(f"SO created: {so_id}")
                    st.session_state["last_so"] = so_id

            with colB:
                if st.button("Post Shipment", use_container_width=True):
                    so_id = st.session_state.get("last_so") or _latest_id(conn, "sales_order", "so_id")
                    if not so_id:
                        st.error("Create a SO first.")
                    else:
                        ship_id = ship_goods(conn, so_id, qty_shipped=qty)
                        st.success(f"Shipment posted: {ship_id}")
                        st.session_state["last_ship"] = ship_id

            with colC:
                if st.button("Post Customer Invoice", use_container_width=True):
                    so_id = st.session_state.get("last_so") or _latest_id(conn, "sales_order", "so_id")
                    if not so_id:
                        st.error("Create a SO first.")
                    else:
                        cinv_id = post_customer_invoice(conn, so_id)
                        st.success(f"Customer Invoice posted: {cinv_id}")
                        st.session_state["last_cinv"] = cinv_id

            st.info("Expected postings: Shipment → Dr COGS / Cr INV. Customer Invoice → Dr AR / Cr REV.")

        else:
            qty_delta = st.number_input("Qty Delta (+/-)", value=-2.0, step=1.0)
            if st.button("Post Adjustment", use_container_width=True):
                adj_id = inventory_adjust(conn, "ITEM-001", qty_delta)
                st.success(f"Adjustment posted: {adj_id}")
                st.session_state["last_adj"] = adj_id

            st.info("Expected postings: shrink → Dr ADJ_EXP / Cr INV; gain → Dr INV / Cr ADJ_EXP.")

        st.divider()
        st.subheader("3) Quick view (latest GL lines)")
        gl = fetch_gl(conn)
        if gl.empty:
            st.write("No GL postings yet.")
        else:
            st.dataframe(gl.head(12), use_container_width=True)

    # -----------------------------
    # Ledger
    # -----------------------------
    with tab_ledger:
        st.subheader("General Ledger Viewer")
        gl = fetch_gl(conn)

        if gl.empty:
            st.write("No postings yet. Go to **Guided Demo** and post a scenario.")
        else:
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                filter_type = st.selectbox("Filter by source_type", ["(All)"] + sorted(gl["source_type"].unique().tolist()))
            with c2:
                acct_filter = st.selectbox("Filter by account", ["(All)"] + sorted(gl["acct"].unique().tolist()))
            with c3:
                st.caption("Tip: Use filters to explain one transaction at a time.")

            df = gl.copy()
            if filter_type != "(All)":
                df = df[df["source_type"] == filter_type]
            if acct_filter != "(All)":
                df = df[df["acct"] == acct_filter]

            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download filtered GL (CSV)", data=csv, file_name="gl_export.csv", mime="text/csv")

    # -----------------------------
    # Validation 
    # -----------------------------
    with tab_validate:
        st.subheader("Validate expected vs actual postings (PASS/FAIL)")
        sources = fetch_recent_sources(conn)

        if sources.empty:
            st.write("No transactions posted yet. Go to **Guided Demo** first.")
        else:
            st.dataframe(sources, use_container_width=True, height=220)

            options = [(r["source_type"], r["source_id"]) for _, r in sources.iterrows()]
            pick = st.selectbox("Pick a transaction to validate", options=options)

            if st.button("Run Validation", use_container_width=True):
                source_type, source_id = pick
                exp_lines = expected_for(conn, source_type, source_id)

                if not exp_lines:
                    st.error(f"No expected rule defined for source_type={source_type}")
                else:
                    result = validate_posting(conn, source_type, source_id, exp_lines)
                    if result["passed"]:
                        st.success(" PASSED: Actual postings match expected matrix.")
                    else:
                        st.error(" FAILED: Posting mismatch detected.")
                        st.write("Differences:")
                        st.dataframe(pd.DataFrame(result["diffs"]), use_container_width=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("Expected (matrix)")
                        st.dataframe(pd.DataFrame(exp_lines), use_container_width=True)
                    with c2:
                        st.write("Actual (from GL)")
                        # result["actual"] is normalized dict; display as table
                        act_rows = [{"acct": k, "dr": v[0], "cr": v[1]} for k, v in result["actual"].items()]
                        st.dataframe(pd.DataFrame(act_rows), use_container_width=True)


def _latest_id(conn, table: str, id_col: str):
    r = conn.execute(f"SELECT {id_col} FROM {table} ORDER BY rowid DESC LIMIT 1").fetchone()
    return r[id_col] if r else None


if __name__ == "__main__":
    main()
