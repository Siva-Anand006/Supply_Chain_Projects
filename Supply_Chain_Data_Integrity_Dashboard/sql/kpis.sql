-- Rebuild KPI views safely
DROP VIEW IF EXISTS kpi_otd_by_supplier;
DROP VIEW IF EXISTS kpi_ppv;
DROP VIEW IF EXISTS kpi_material_availability;

CREATE VIEW kpi_otd_by_supplier AS
SELECT
  supplier_id,
  COUNT(*) AS received_pos,
  SUM(CASE WHEN received_date <= promised_date THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS otd_rate
FROM purchase_orders
WHERE status='RECEIVED'
GROUP BY supplier_id;

CREATE VIEW kpi_ppv AS
SELECT
  pl.material_id,
  SUM((pl.unit_price - sp.standard_price) * pl.qty_ordered) AS total_ppv
FROM po_lines pl
JOIN standard_prices sp ON sp.material_id = pl.material_id
GROUP BY pl.material_id;

CREATE VIEW kpi_material_availability AS
SELECT
  material_id,
  on_hand_qty,
  safety_stock_qty,
  (on_hand_qty * 1.0) / NULLIF(safety_stock_qty, 0) AS coverage_ratio
FROM inventory;
