import uuid
import sqlite3
from scaqa.db import now_iso


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _std_cost(conn: sqlite3.Connection, item_id: str) -> float:
    r = conn.execute(
        "SELECT std_cost FROM item WHERE item_id=?", (item_id,)
    ).fetchone()
    return float(r["std_cost"])


def _on_hand(conn: sqlite3.Connection, item_id: str) -> float:
    r = conn.execute(
        "SELECT qty_on_hand FROM inventory_balance WHERE item_id=?", (item_id,)
    ).fetchone()
    return float(r["qty_on_hand"])


def _set_on_hand(conn: sqlite3.Connection, item_id: str, qty: float):
    conn.execute(
        """
        INSERT INTO inventory_balance(item_id, qty_on_hand)
        VALUES (?,?)
        ON CONFLICT(item_id)
        DO UPDATE SET qty_on_hand=excluded.qty_on_hand
        """,
        (item_id, qty),
    )


def _post_je(conn, source_type, source_id, memo, lines):
    total_dr = sum(l["dr"] for l in lines)
    total_cr = sum(l["cr"] for l in lines)

    if round(total_dr - total_cr, 2) != 0:
        raise ValueError("Journal entry not balanced")

    je_id = _new_id("JE")

    conn.execute(
        """
        INSERT INTO gl_header(je_id, source_type, source_id, memo, created_at)
        VALUES (?,?,?,?,?)
        """,
        (je_id, source_type, source_id, memo, now_iso()),
    )

    conn.executemany(
        "INSERT INTO gl_line(je_id, acct, dr, cr) VALUES (?,?,?,?)",
        [(je_id, l["acct"], l["dr"], l["cr"]) for l in lines],
    )

    return je_id


# -------------------- P2P FLOW --------------------

def create_po(conn, vendor, item_id, qty, unit_price):
    po_id = _new_id("PO")
    conn.execute(
        "INSERT INTO purchase_order VALUES (?,?,?,?,?,?)",
        (po_id, vendor, item_id, qty, unit_price, "OPEN"),
    )
    conn.commit()
    return po_id


def receive_goods(conn, po_id, qty_received):
    po = conn.execute(
        "SELECT * FROM purchase_order WHERE po_id=?", (po_id,)
    ).fetchone()

    gr_id = _new_id("GR")
    conn.execute(
        "INSERT INTO goods_receipt VALUES (?,?,?,?)",
        (gr_id, po_id, qty_received, "POSTED"),
    )

    value = qty_received * po["unit_price"]

    _set_on_hand(conn, po["item_id"], _on_hand(conn, po["item_id"]) + qty_received)

    _post_je(
        conn,
        "GR",
        gr_id,
        "Goods receipt",
        [
            {"acct": "INV", "dr": value, "cr": 0},
            {"acct": "GRNI", "dr": 0, "cr": value},
        ],
    )

    conn.commit()
    return gr_id


def post_vendor_invoice(conn, po_id, amount):
    inv_id = _new_id("VINV")
    conn.execute(
        "INSERT INTO vendor_invoice VALUES (?,?,?,?)",
        (inv_id, po_id, amount, "POSTED"),
    )

    _post_je(
        conn,
        "VINV",
        inv_id,
        "Vendor invoice",
        [
            {"acct": "GRNI", "dr": amount, "cr": 0},
            {"acct": "AP", "dr": 0, "cr": amount},
        ],
    )

    conn.commit()
    return inv_id


# -------------------- O2C FLOW --------------------

def create_so(conn, customer, item_id, qty, unit_price):
    so_id = _new_id("SO")
    conn.execute(
        "INSERT INTO sales_order VALUES (?,?,?,?,?,?)",
        (so_id, customer, item_id, qty, unit_price, "OPEN"),
    )
    conn.commit()
    return so_id


def ship_goods(conn, so_id, qty_shipped):
    so = conn.execute(
        "SELECT * FROM sales_order WHERE so_id=?", (so_id,)
    ).fetchone()

    ship_id = _new_id("SHIP")
    conn.execute(
        "INSERT INTO shipment VALUES (?,?,?,?)",
        (ship_id, so_id, qty_shipped, "POSTED"),
    )

    cost = qty_shipped * _std_cost(conn, so["item_id"])

    _set_on_hand(conn, so["item_id"], _on_hand(conn, so["item_id"]) - qty_shipped)

    _post_je(
        conn,
        "SHIP",
        ship_id,
        "Shipment",
        [
            {"acct": "COGS", "dr": cost, "cr": 0},
            {"acct": "INV", "dr": 0, "cr": cost},
        ],
    )

    conn.commit()
    return ship_id


def post_customer_invoice(conn, so_id):
    so = conn.execute(
        "SELECT * FROM sales_order WHERE so_id=?", (so_id,)
    ).fetchone()

    amount = so["qty"] * so["unit_price"]
    cinv_id = _new_id("CINV")

    conn.execute(
        "INSERT INTO customer_invoice VALUES (?,?,?,?)",
        (cinv_id, so_id, amount, "POSTED"),
    )

    _post_je(
        conn,
        "CINV",
        cinv_id,
        "Customer invoice",
        [
            {"acct": "AR", "dr": amount, "cr": 0},
            {"acct": "REV", "dr": 0, "cr": amount},
        ],
    )

    conn.commit()
    return cinv_id


# -------------------- INVENTORY ADJUST --------------------

def inventory_adjust(conn, item_id, qty_delta):
    adj_id = _new_id("ADJ")
    value = abs(qty_delta) * _std_cost(conn, item_id)

    _set_on_hand(conn, item_id, _on_hand(conn, item_id) + qty_delta)

    if qty_delta < 0:
        lines = [
            {"acct": "ADJ_EXP", "dr": value, "cr": 0},
            {"acct": "INV", "dr": 0, "cr": value},
        ]
    else:
        lines = [
            {"acct": "INV", "dr": value, "cr": 0},
            {"acct": "ADJ_EXP", "dr": 0, "cr": value},
        ]

    _post_je(conn, "ADJ", adj_id, "Inventory adjustment", lines)
    conn.commit()
    return adj_id
