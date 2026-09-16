-- ============================================================
-- Controlling-Agent Demo - Datenbankschema und Beispieldaten
-- Angelehnt an SAP-CO-Strukturen (stark vereinfacht):
--   Kostenstelle  ~ SAP CSKS
--   Kostenart     ~ SAP CSKA
--   Planwerte     ~ SAP COSP (Planung)
--   Istbuchungen  ~ SAP COEP (Einzelposten)
-- ============================================================

DROP TABLE IF EXISTS istbuchungen;
DROP TABLE IF EXISTS planwerte;
DROP TABLE IF EXISTS kostenart;
DROP TABLE IF EXISTS kostenstelle;

CREATE TABLE kostenstelle (
    kostenstelle     VARCHAR(10) PRIMARY KEY,
    bezeichnung      VARCHAR(100) NOT NULL,
    verantwortlicher VARCHAR(100) NOT NULL
);

CREATE TABLE kostenart (
    kostenart        VARCHAR(10) PRIMARY KEY,
    bezeichnung      VARCHAR(100) NOT NULL,
    kostenartentyp   VARCHAR(30) NOT NULL   -- z. B. Personal, Material, Sonstige
);

CREATE TABLE planwerte (
    id           SERIAL PRIMARY KEY,
    kostenstelle VARCHAR(10) NOT NULL REFERENCES kostenstelle(kostenstelle),
    kostenart    VARCHAR(10) NOT NULL REFERENCES kostenart(kostenart),
    periode      CHAR(7)     NOT NULL,      -- Format 'YYYY-MM'
    planbetrag   NUMERIC(12,2) NOT NULL,
    UNIQUE (kostenstelle, kostenart, periode)
);

CREATE TABLE istbuchungen (
    id             SERIAL PRIMARY KEY,
    kostenstelle   VARCHAR(10) NOT NULL REFERENCES kostenstelle(kostenstelle),
    kostenart      VARCHAR(10) NOT NULL REFERENCES kostenart(kostenart),
    periode        CHAR(7)     NOT NULL,
    betrag         NUMERIC(12,2) NOT NULL,
    buchungstext   VARCHAR(200),
    buchungsdatum  DATE NOT NULL
);

-- ------------------------------------------------------------
-- Stammdaten
-- ------------------------------------------------------------
INSERT INTO kostenstelle (kostenstelle, bezeichnung, verantwortlicher) VALUES
    ('4100', 'Vertrieb Nord',      'Anna Mueller'),
    ('4200', 'Produktion Werk 1',  'Thomas Schmidt');

INSERT INTO kostenart (kostenart, bezeichnung, kostenartentyp) VALUES
    ('600000', 'Personalkosten',   'Personal'),
    ('610000', 'Materialkosten',   'Material'),
    ('620000', 'Reisekosten',      'Sonstige'),
    ('630000', 'Marketingkosten',  'Sonstige');

-- ------------------------------------------------------------
-- Planwerte (identisches Budget je Monat, zur Vereinfachung)
-- ------------------------------------------------------------
INSERT INTO planwerte (kostenstelle, kostenart, periode, planbetrag) VALUES
    ('4100', '600000', '2026-06', 45000), ('4100', '600000', '2026-07', 45000), ('4100', '600000', '2026-08', 45000),
    ('4100', '610000', '2026-06',  5000), ('4100', '610000', '2026-07',  5000), ('4100', '610000', '2026-08',  5000),
    ('4100', '620000', '2026-06',  8000), ('4100', '620000', '2026-07',  8000), ('4100', '620000', '2026-08',  8000),
    ('4100', '630000', '2026-06', 12000), ('4100', '630000', '2026-07', 12000), ('4100', '630000', '2026-08', 12000),

    ('4200', '600000', '2026-06', 60000), ('4200', '600000', '2026-07', 60000), ('4200', '600000', '2026-08', 60000),
    ('4200', '610000', '2026-06', 80000), ('4200', '610000', '2026-07', 80000), ('4200', '610000', '2026-08', 80000),
    ('4200', '620000', '2026-06',  3000), ('4200', '620000', '2026-07',  3000), ('4200', '620000', '2026-08',  3000),
    ('4200', '630000', '2026-06',  2000), ('4200', '630000', '2026-07',  2000), ('4200', '630000', '2026-08',  2000);

-- ------------------------------------------------------------
-- Istbuchungen
-- Bewusst eingebaute Auffaelligkeit: Materialkosten Kostenstelle
-- 4200 schiessen im August wegen eines Rohstoffpreisanstiegs
-- deutlich ueber Plan -- das soll der Agent im Beispiel erkennen
-- und als Haupttreiber der Abweichung benennen.
-- ------------------------------------------------------------
INSERT INTO istbuchungen (kostenstelle, kostenart, periode, betrag, buchungstext, buchungsdatum) VALUES
    ('4100', '600000', '2026-06', 44200, 'Gehaelter Juni',            '2026-06-28'),
    ('4100', '600000', '2026-07', 45100, 'Gehaelter Juli',            '2026-07-28'),
    ('4100', '600000', '2026-08', 45300, 'Gehaelter August',          '2026-08-28'),
    ('4100', '610000', '2026-06',  4800, 'Buerobedarf',               '2026-06-15'),
    ('4100', '610000', '2026-07',  5150, 'Buerobedarf',               '2026-07-14'),
    ('4100', '610000', '2026-08',  4950, 'Buerobedarf',               '2026-08-13'),
    ('4100', '620000', '2026-06',  7600, 'Kundenbesuche',             '2026-06-20'),
    ('4100', '620000', '2026-07',  9100, 'Messe Muenchen',            '2026-07-18'),
    ('4100', '620000', '2026-08', 12400, 'Kundenreisen Q3',           '2026-08-22'),
    ('4100', '630000', '2026-06', 11800, 'Onlinekampagne',            '2026-06-10'),
    ('4100', '630000', '2026-07', 12200, 'Onlinekampagne',            '2026-07-10'),
    ('4100', '630000', '2026-08', 11500, 'Onlinekampagne',            '2026-08-10'),

    ('4200', '600000', '2026-06', 59500, 'Loehne Produktion',         '2026-06-28'),
    ('4200', '600000', '2026-07', 60200, 'Loehne Produktion',         '2026-07-28'),
    ('4200', '600000', '2026-08', 61000, 'Loehne + Ueberstunden',     '2026-08-28'),
    ('4200', '610000', '2026-06', 79500, 'Rohstoffe Standard',        '2026-06-12'),
    ('4200', '610000', '2026-07', 81200, 'Rohstoffe Standard',        '2026-07-11'),
    ('4200', '610000', '2026-08', 118400, 'Rohstoffe -- Preisanstieg Stahl', '2026-08-09'),
    ('4200', '620000', '2026-06',  2100, 'Werksbesuche',              '2026-06-05'),
    ('4200', '620000', '2026-07',  2400, 'Werksbesuche',              '2026-07-06'),
    ('4200', '620000', '2026-08',  2600, 'Werksbesuche',              '2026-08-07'),
    ('4200', '630000', '2026-06',  1800, 'Produktbroschueren',        '2026-06-02'),
    ('4200', '630000', '2026-07',  1900, 'Produktbroschueren',        '2026-07-03'),
    ('4200', '630000', '2026-08',  2050, 'Produktbroschueren',        '2026-08-04');
