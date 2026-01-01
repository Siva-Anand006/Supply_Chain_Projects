import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_DB = "erp.db"


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection, schema_path: str = "schema.sql") -> None:
    schema = Path(schema_path).read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()


def seed(conn: sqlite3.Connection) -> None:
    chart_of_accounts = [
        ("INV", "Inventory", "DR"),
        ("COGS", "Cost of Goods Sold", "DR"),
        ("AP", "Accounts Payable", "CR"),
        ("AR", "Accounts Receivable", "DR"),
        ("REV", "Revenue", "CR"),
        ("GRNI", "Goods Received Not Invoiced", "CR"),
        ("ADJ_EXP", "Inventory Adjustment Expense", "DR"),
    ]

    conn.executemany(
        "INSERT OR IGNORE INTO account(acct, name, normal_balance) VALUES (?,?,?)",
        chart_of_accounts,
    )

    conn.execute(
        "INSERT OR IGNORE INTO item(item_id, description, std_cost) VALUES (?,?,?)",
        ("ITEM-001", "Demo Widget", 10.00),
    )

    conn.execute(
        "INSERT OR IGNORE INTO inventory_balance(item_id, qty_on_hand) VALUES (?,?)",
        ("ITEM-001", 100.0),
    )

    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

