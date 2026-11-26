import sqlite3
import hashlib
import pandas as pd
import numpy as np

DB_NAME = "dataretail360.db"
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

for vista in ["dm_ventas_consolidadas", "dm_inventario_analitico"]:
    cur.execute(f"DROP VIEW IF EXISTS {vista};")
for tabla in ["Fact_Ventas", "Fact_Inventario", "Dim_Fecha", "Dim_Producto", "Dim_Cliente", "Dim_Sucursal", "Dim_Canal", "Dim_Campana"]:
    cur.execute(f"DROP TABLE IF EXISTS {tabla};")

cur.executescript("""
CREATE TABLE Dim_Fecha (
    sk_fecha INT PRIMARY KEY, fecha_completa DATE, anio INT, trimestre INT, mes INT, nombre_mes VARCHAR(20)
);
CREATE TABLE Dim_Producto (
    sk_producto INTEGER PRIMARY KEY AUTOINCREMENT, bk_sku VARCHAR(50), nombre_producto VARCHAR(150),
    categoria VARCHAR(50), costo_referencial DECIMAL(18,2), fecha_inicio_vigencia DATE,
    fecha_fin_vigencia DATE, es_registro_actual BIT
);
CREATE TABLE Dim_Cliente (
    sk_cliente INTEGER PRIMARY KEY AUTOINCREMENT, bk_rut VARCHAR(12), nombre_completo VARCHAR(150),
    email VARCHAR(100), segmento_cliente VARCHAR(30), es_registro_actual BIT, hash_registro VARCHAR(64)
);
CREATE TABLE Dim_Sucursal (
    sk_sucursal INT PRIMARY KEY, nombre_sucursal VARCHAR(100), region VARCHAR(50)
);
CREATE TABLE Dim_Canal (
    sk_canal INT PRIMARY KEY, nombre_canal VARCHAR(50), tipo_canal VARCHAR(20)
);
CREATE TABLE Dim_Campana (
    sk_campana INT PRIMARY KEY, nombre_campana VARCHAR(100), presupuesto_asignado DECIMAL(18,2)
);
CREATE TABLE Fact_Ventas (
    sk_venta INTEGER PRIMARY KEY AUTOINCREMENT, sk_fecha INT, sk_cliente INT, sk_producto INT,
    sk_sucursal INT, sk_canal INT, sk_campana INT, numero_ticket VARCHAR(50),
    cantidad_vendida INT, monto_bruto DECIMAL(18,2), monto_descuento DECIMAL(18,2),
    monto_neto DECIMAL(18,2), costo_total DECIMAL(18,2), margen_ganancia DECIMAL(18,2)
);
CREATE TABLE Fact_Inventario (
    sk_inventario INTEGER PRIMARY KEY AUTOINCREMENT, sk_fecha INT, sk_producto INT,
    sk_sucursal INT, cantidad_stock INT, stock_minimo INT, flag_quiebre_stock SMALLINT
);
""")

# Poblamiento de dimensiones
fechas = pd.date_range("2026-01-01", "2026-10-31", freq="D")
meses_es = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre"}
pd.DataFrame({
    "sk_fecha": fechas.strftime("%Y%m%d").astype(int),
    "fecha_completa": fechas.strftime("%Y-%m-%d"),
    "anio": fechas.year, "trimestre": fechas.quarter, "mes": fechas.month,
    "nombre_mes": [meses_es[m] for m in fechas.month]
}).to_sql("Dim_Fecha", conn, if_exists="append", index=False)

cur.executemany("INSERT INTO Dim_Sucursal VALUES (?,?,?);", [
    (1, "Tienda Costanera", "Metropolitana"), (2, "Tienda Plaza Egaña", "Metropolitana"),
    (3, "Dark Store Ñuñoa", "Metropolitana"), (4, "Tienda Viña Centro", "Valparaíso")
])
cur.executemany("INSERT INTO Dim_Canal VALUES (?,?,?);", [
    (1, "E-commerce", "Digital"), (2, "Tienda Física", "Físico"), (3, "App Móvil", "Digital")
])
cur.executemany("INSERT INTO Dim_Campana VALUES (?,?,?);", [
    (-1, "Sin Campaña", 0), (1, "CyberDay Tech 2026", 15000000),
    (2, "Renueva tu Hogar Q3", 8500000), (3, "Preventa VIP", 4200000)
])

# Incluye cambio SCD Tipo 2 en SKU-103
cur.executemany("""
    INSERT INTO Dim_Producto (bk_sku, nombre_producto, categoria, costo_referencial, fecha_inicio_vigencia, fecha_fin_vigencia, es_registro_actual)
    VALUES (?,?,?,?,?,?,?);
""", [
    ("SKU-101", "Notebook Pro 15 i7", "Tecnología", 620000, "2026-01-01", "9999-12-31", 1),
    ("SKU-102", "Smart TV 55 4K", "Tecnología", 340000, "2026-01-01", "9999-12-31", 1),
    ("SKU-103", "Audífonos NoiseCancel ANC", "Accesorios", 65000, "2026-01-01", "2026-06-30", 0),
    ("SKU-103", "Audífonos NoiseCancel ANC", "Tecnología", 72000, "2026-07-01", "9999-12-31", 1),
    ("SKU-104", "Aspiradora Robot Smart", "Hogar", 165000, "2026-01-01", "9999-12-31", 1),
    ("SKU-105", "Cafetera Express Barista", "Hogar", 78000, "2026-01-01", "9999-12-31", 1),
    ("SKU-106", "Teclado Mecánico RGB", "Accesorios", 35000, "2026-01-01", "9999-12-31", 1)
])

def h(t): return hashlib.sha256(t.encode()).hexdigest()
cur.executemany("""
    INSERT INTO Dim_Cliente (bk_rut, nombre_completo, email, segmento_cliente, es_registro_actual, hash_registro)
    VALUES (?,?,?,?,?,?);
""", [
    ("18456123K", "Camila Rojas", "camila@email.cl", "VIP", 1, h("18456123K")),
    ("192348765", "Matías Silva", "msilva@email.cl", "Frecuente", 1, h("192348765")),
    ("176543210", "Valentina Muñoz", "vmunoz@email.cl", "VIP", 1, h("176543210")),
    ("201112223", "Diego Herrera", "dherrera@email.cl", "Ocasional", 1, h("201112223"))
])

# Poblamiento de Hechos
np.random.seed(42)
sk_fechas = pd.read_sql_query("SELECT sk_fecha FROM Dim_Fecha", conn)["sk_fecha"].values
costos = {1: 620000, 2: 340000, 3: 65000, 4: 72000, 5: 165000, 6: 78000, 7: 35000}
precios = {1: 950000, 2: 520000, 3: 115000, 4: 125000, 5: 270000, 6: 135000, 7: 62000}

ventas = []
for i in range(1500):
    sk_f = int(np.random.choice(sk_fechas))
    sk_p = int(np.random.choice([1, 2, 4, 5, 6, 7])) if sk_f >= 20260701 else int(np.random.choice([1, 2, 3, 5, 6, 7]))
    sk_c = int(np.random.choice([1, 2, 3, 4]))
    sk_s = int(np.random.choice([1, 2, 3, 4], p=[0.35, 0.25, 0.20, 0.20]))
    sk_ca = int(np.random.choice([1, 2, 3], p=[0.40, 0.42, 0.18]))
    sk_cp = int(np.random.choice([-1, 1, 2, 3], p=[0.50, 0.20, 0.15, 0.15]))
    cant = int(np.random.randint(1, 3))
    bruto = round(precios[sk_p] * cant, 2)
    desc = round(bruto * np.random.choice([0, 0.05, 0.10]), 2)
    neto = round((bruto - desc) / 1.19, 2) # Regla oficial sin IVA
    costo = round(costos[sk_p] * cant, 2)
    margen = round(neto - costo, 2)
    ventas.append((sk_f, sk_c, sk_p, sk_s, sk_ca, sk_cp, f"B-{10000+np.random.randint(1, 950)}", cant, bruto, desc, neto, costo, margen))

cur.executemany("""
    INSERT INTO Fact_Ventas (sk_fecha, sk_cliente, sk_producto, sk_sucursal, sk_canal, sk_campana, numero_ticket, cantidad_vendida, monto_bruto, monto_descuento, monto_neto, costo_total, margen_ganancia)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);
""", ventas)

inv = []
for sk_p in [1, 2, 4, 5, 6, 7]:
    for sk_s in [1, 2, 3, 4]:
        stock = int(np.random.choice([0, 0, 3, 12, 30, 65]))
        inv.append((20261031, sk_p, sk_s, stock, 10, 1 if stock <= 2 else 0))

cur.executemany("""
    INSERT INTO Fact_Inventario (sk_fecha, sk_producto, sk_sucursal, cantidad_stock, stock_minimo, flag_quiebre_stock)
    VALUES (?,?,?,?,?,?);
""", inv)

# Capa Semántica Segura (Vistas dm_ sin PII)
cur.executescript("""
CREATE VIEW dm_ventas_consolidadas AS
SELECT f.fecha_completa, f.anio, f.trimestre, f.mes, f.nombre_mes,
       p.bk_sku, p.nombre_producto, p.categoria, p.es_registro_actual,
       c.sk_cliente, c.segmento_cliente,
       s.nombre_sucursal, ca.nombre_canal, ca.tipo_canal,
       cp.sk_campana, cp.nombre_campana, cp.presupuesto_asignado,
       v.numero_ticket, v.cantidad_vendida, v.monto_bruto, v.monto_descuento, v.monto_neto, v.margen_ganancia
FROM Fact_Ventas v
JOIN Dim_Fecha f ON v.sk_fecha = f.sk_fecha
JOIN Dim_Producto p ON v.sk_producto = p.sk_producto
JOIN Dim_Cliente c ON v.sk_cliente = c.sk_cliente
JOIN Dim_Sucursal s ON v.sk_sucursal = s.sk_sucursal
JOIN Dim_Canal ca ON v.sk_canal = ca.sk_canal
JOIN Dim_Campana cp ON v.sk_campana = cp.sk_campana;

CREATE VIEW dm_inventario_analitico AS
SELECT p.bk_sku, p.nombre_producto, p.categoria, s.nombre_sucursal,
       i.cantidad_stock, i.stock_minimo, i.flag_quiebre_stock
FROM Fact_Inventario i
JOIN Dim_Producto p ON i.sk_producto = p.sk_producto
JOIN Dim_Sucursal s ON i.sk_sucursal = s.sk_sucursal;
""")

conn.commit()
conn.close()
print("Base dataretail360.db y vistas dm_ creadas con éxito.")