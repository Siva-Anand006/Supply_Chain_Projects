import sqlite3
from pathlib import Path

DB_PATH = Path("procurement.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def run_script(path):
    with get_conn() as conn:
        conn.executescript(Path(path).read_text())
        conn.commit()