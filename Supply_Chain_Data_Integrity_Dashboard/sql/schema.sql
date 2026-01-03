DROP TABLE IF EXISTS dq_issues;
DROP TABLE IF EXISTS standard_prices;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS po_lines;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS materials;
DROP TABLE IF EXISTS suppliers;


CREATE TABLE suppliers (
 supplier_id INTEGER PRIMARY KEY,
 supplier_name TEXT,
 default_lead_time_days INTEGER
);

CREATE TABLE materials (
 material_id INTEGER PRIMARY KEY,
 material_name TEXT,
 uom TEXT
);

CREATE TABLE purchase_orders (
 po_id INTEGER PRIMARY KEY,
 supplier_id INTEGER,
 order_date TEXT,
 promised_date TEXT,
 received_date TEXT,
 status TEXT
);

CREATE TABLE po_lines (
 po_id INTEGER,
 line_id INTEGER,
 material_id INTEGER,
 qty_ordered INTEGER,
 unit_price REAL
);

CREATE TABLE inventory (
 material_id INTEGER,
 on_hand_qty INTEGER,
 safety_stock_qty INTEGER
);

CREATE TABLE standard_prices (
 material_id INTEGER,
 standard_price REAL
);

CREATE TABLE dq_issues (
 issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
 rule_name TEXT,
 severity TEXT,
 table_name TEXT,
 record_key TEXT,
 issue_detail TEXT,
 detected_at TEXT DEFAULT (datetime('now'))
);