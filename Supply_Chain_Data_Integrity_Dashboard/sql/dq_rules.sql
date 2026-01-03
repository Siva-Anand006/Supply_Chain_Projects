INSERT INTO dq_issues(rule_name,severity,table_name,record_key,issue_detail)
SELECT 'LEAD_TIME_INVALID','HIGH','suppliers',supplier_id,'Lead time <= 0'
FROM suppliers WHERE default_lead_time_days <= 0;

INSERT INTO dq_issues(rule_name,severity,table_name,record_key,issue_detail)
SELECT 'INVALID_UOM','MEDIUM','materials',material_id,'UOM missing'
FROM materials WHERE uom IS NULL;

INSERT INTO dq_issues(rule_name,severity,table_name,record_key,issue_detail)
SELECT 'NEGATIVE_PRICE','HIGH','po_lines',po_id,'Unit price < 0'
FROM po_lines WHERE unit_price < 0;

INSERT INTO dq_issues(rule_name,severity,table_name,record_key,issue_detail)
SELECT 'ZERO_QTY','HIGH','po_lines',po_id,'Quantity <= 0'
FROM po_lines WHERE qty_ordered <= 0;

INSERT INTO dq_issues(rule_name,severity,table_name,record_key,issue_detail)
SELECT 'MISSING_RECEIPT','HIGH','purchase_orders',po_id,'Received but no date'
FROM purchase_orders WHERE status='RECEIVED' AND received_date IS NULL;