import pytest

from scaqa.db import connect, init_db, seed
from scaqa.engine import (
    create_po, receive_goods, post_vendor_invoice,
    create_so, ship_goods, post_customer_invoice,
    inventory_adjust
)
from scaqa.validator import validate_posting


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "test_erp.db"
    c = connect(str(db_path))
    init_db(c, "schema.sql")
    seed(c)
    yield c
    c.close()


def test_p2p_gr_and_vendor_invoice(conn):
    # PO: 10 units @ $12
    po_id = create_po(conn, "VendorA", "ITEM-001", 10, 12)

    # GR: receive 10 units -> Dr INV 120 / Cr GRNI 120
    gr_id = receive_goods(conn, po_id, 10)
    expected_gr = [
        {"acct": "INV", "dr": 120.0, "cr": 0.0},
        {"acct": "GRNI", "dr": 0.0, "cr": 120.0},
    ]
    r1 = validate_posting(conn, "GR", gr_id, expected_gr)
    assert r1["passed"], f"GR posting mismatch: {r1['diffs']}"

    # Vendor invoice $120 -> Dr GRNI 120 / Cr AP 120
    inv_id = post_vendor_invoice(conn, po_id, 120.0)
    expected_inv = [
        {"acct": "GRNI", "dr": 120.0, "cr": 0.0},
        {"acct": "AP", "dr": 0.0, "cr": 120.0},
    ]
    r2 = validate_posting(conn, "VINV", inv_id, expected_inv)
    assert r2["passed"], f"VINV posting mismatch: {r2['diffs']}"


def test_o2c_shipment_and_customer_invoice(conn):
    # SO: 5 units @ $25 (revenue side)
    so_id = create_so(conn, "CustomerA", "ITEM-001", 5, 25)

    # Shipment: 5 units, std cost is $10 -> Dr COGS 50 / Cr INV 50
    ship_id = ship_goods(conn, so_id, 5)
    expected_ship = [
        {"acct": "COGS", "dr": 50.0, "cr": 0.0},
        {"acct": "INV", "dr": 0.0, "cr": 50.0},
    ]
    r1 = validate_posting(conn, "SHIP", ship_id, expected_ship)
    assert r1["passed"], f"SHIP posting mismatch: {r1['diffs']}"

    # Customer invoice: 5 * 25 = 125 -> Dr AR 125 / Cr REV 125
    cinv_id = post_customer_invoice(conn, so_id)
    expected_cinv = [
        {"acct": "AR", "dr": 125.0, "cr": 0.0},
        {"acct": "REV", "dr": 0.0, "cr": 125.0},
    ]
    r2 = validate_posting(conn, "CINV", cinv_id, expected_cinv)
    assert r2["passed"], f"CINV posting mismatch: {r2['diffs']}"


def test_inventory_adjustment(conn):
    # Shrink 2 units @ std cost $10 -> Dr ADJ_EXP 20 / Cr INV 20
    adj_id = inventory_adjust(conn, "ITEM-001", -2)

    expected_adj = [
        {"acct": "ADJ_EXP", "dr": 20.0, "cr": 0.0},
        {"acct": "INV", "dr": 0.0, "cr": 20.0},
    ]

    r = validate_posting(conn, "ADJ", adj_id, expected_adj)
    assert r["passed"], f"ADJ posting mismatch: {r['diffs']}"
