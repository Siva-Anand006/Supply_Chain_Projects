INSERT INTO suppliers VALUES
(1,'Alpha Metals',-5),
(2,'Beta Plastics',14),
(3,'Gamma Components',0);

INSERT INTO materials VALUES
(1,'Steel Rod','KG'),
(2,'Plastic Housing',NULL),
(3,'Copper Wire','M');

INSERT INTO purchase_orders VALUES
(101,1,'2025-01-01','2025-01-10','2025-01-12','RECEIVED'),
(102,2,'2025-01-05','2025-01-20',NULL,'RECEIVED'),
(103,3,'2025-01-07','2025-01-18','2025-01-15','RECEIVED');

INSERT INTO po_lines VALUES
(101,1,1,100,10.5),
(102,1,2,50,-2),
(103,1,3,0,5);

INSERT INTO inventory VALUES
(1,500,300),
(2,100,200),
(3,50,50);

INSERT INTO standard_prices VALUES
(1,10),
(2,5),
(3,4.5);