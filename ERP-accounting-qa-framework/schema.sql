PRAGMA foreign_keys = ON;

-- master data
CREATE TABLE IF NOT EXISTS item (
  item_id TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  std_cost REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
  acct TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  normal_balance TEXT NOT NULL CHECK (normal_balance IN ('DR','CR'))
);

-- business documents
CREATE TABLE IF NOT EXISTS purchase_order (
  po_id TEXT PRIMARY KEY,
  vendor TEXT NOT NULL,
  item_id TEXT NOT NULL REFERENCES item(item_id),
  qty REAL NOT NULL,
  unit_price REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goods_receipt (
  gr_id TEXT PRIMARY KEY,
  po_id TEXT NOT NULL REFERENCES purchase_order(po_id),
  qty_received REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_invoice (
  inv_id TEXT PRIMARY KEY,
  po_id TEXT NOT NULL REFERENCES purchase_order(po_id),
  amount REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_order (
  so_id TEXT PRIMARY KEY,
  customer TEXT NOT NULL,
  item_id TEXT NOT NULL REFERENCES item(item_id),
  qty REAL NOT NULL,
  unit_price REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment (
  ship_id TEXT PRIMARY KEY,
  so_id TEXT NOT NULL REFERENCES sales_order(so_id),
  qty_shipped REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_invoice (
  cinv_id TEXT PRIMARY KEY,
  so_id TEXT NOT NULL REFERENCES sales_order(so_id),
  amount REAL NOT NULL,
  status TEXT NOT NULL
);

-- inventory
CREATE TABLE IF NOT EXISTS inventory_balance (
  item_id TEXT PRIMARY KEY REFERENCES item(item_id),
  qty_on_hand REAL NOT NULL
);

-- accounting
CREATE TABLE IF NOT EXISTS gl_header (
  je_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  memo TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_line (
  line_id INTEGER PRIMARY KEY AUTOINCREMENT,
  je_id TEXT NOT NULL REFERENCES gl_header(je_id),
  acct TEXT NOT NULL REFERENCES account(acct),
  dr REAL NOT NULL DEFAULT 0,
  cr REAL NOT NULL DEFAULT 0,
  CHECK (dr >= 0 AND cr >= 0),
  CHECK (NOT (dr > 0 AND cr > 0))
);

CREATE INDEX IF NOT EXISTS idx_gl_header_source ON gl_header(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_gl_line_je ON gl_line(je_id);
