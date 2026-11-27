import pandas as pd
import numpy as np

np.random.seed(42)

# 1. Dimensiones
dim_canal = pd.DataFrame({
    'sk_canal': [1, 2, 3],
    'nombre_canal': ['Tienda Física', 'E-commerce', 'App Móvil'],
    'tipo_canal': ['Físico', 'Digital', 'Digital']
})

dim_sucursal = pd.DataFrame({
    'sk_sucursal': [1, 2, 3, 4],
    'nombre_sucursal': ['Sucursal Santiago Centro', 'Sucursal Las Condes', 'Sucursal Viña del Mar', 'Sucursal Concepción']
})

dim_producto = pd.DataFrame({
    'sk_producto': range(1, 13),
    'sku': [f'SKU-{100+i}' for i in range(1, 13)],
    'nombre_producto': [
        'Notebook Pro 15"', 'Smartphone X200', 'Audífonos ANC', 'Smart TV 55"',
        'Cafetera Express', 'Aspiradora Robot', 'Lámpara LED Smart', 'Set Sábanas Premium',
        'Cargador Rápido 65W', 'Mouse Ergonómico', 'Mochila Antirrobo', 'Funda Tablet'
    ],
    'categoria': [
        'Tecnología', 'Tecnología', 'Tecnología', 'Tecnología',
        'Hogar', 'Hogar', 'Hogar', 'Hogar',
        'Accesorios', 'Accesorios', 'Accesorios', 'Accesorios'
    ],
    'precio_lista': [950000, 520000, 85000, 480000, 120000, 260000, 35000, 45000, 28000, 32000, 42000, 18000],
    'costo_unitario': [680000, 360000, 48000, 340000, 72000, 165000, 18000, 22000, 12000, 15000, 21000, 7500],
    'es_registro_actual': [1]*12
})

dim_campana = pd.DataFrame({
    'sk_campana': [-1, 1, 2, 3],
    'nombre_campana': ['Sin Campaña', 'Cyber Retail 360', 'Campaña Email VIP', 'RR.SS. Tech & Hogar'],
    'presupuesto_asignado': [0, 18000000, 4500000, 7500000]
})

# 2. Fact_Ventas (5.000 transacciones en 2026)
n_ventas = 5000
fechas = pd.date_range('2026-01-01', '2026-11-20', freq='h')
fechas_sample = np.random.choice(fechas, n_ventas)
prod_idx = np.random.choice(dim_producto['sk_producto'], n_ventas)

fact_ventas = pd.DataFrame({
    'numero_ticket': np.random.randint(10000, 13800, n_ventas), # Permite múltiples ítems por ticket
    'fecha': pd.to_datetime(fechas_sample).date,
    'sk_producto': prod_idx,
    'sk_canal': np.random.choice([1, 2, 3], n_ventas, p=[0.48, 0.34, 0.18]),
    'sk_sucursal': np.random.choice([1, 2, 3, 4], n_ventas, p=[0.35, 0.30, 0.15, 0.20]),
    'sk_campana': np.random.choice([-1, 1, 2, 3], n_ventas, p=[0.55, 0.20, 0.12, 0.13]),
    'sk_cliente': np.random.randint(1, 1600, n_ventas),
    'cantidad': np.random.choice([1, 2, 3], n_ventas, p=[0.75, 0.20, 0.05])
})

fact_ventas = fact_ventas.merge(dim_producto[['sk_producto', 'precio_lista', 'costo_unitario']], on='sk_producto')
descuento = np.random.choice([0, 0.05, 0.10, 0.15], n_ventas, p=[0.6, 0.2, 0.15, 0.05])
fact_ventas['monto_bruto'] = fact_ventas['precio_lista'] * fact_ventas['cantidad']
fact_ventas['monto_descuento'] = (fact_ventas['monto_bruto'] * descuento).round(0)
# Regla de negocio: monto_neto sin IVA (1.19)
fact_ventas['monto_neto'] = ((fact_ventas['monto_bruto'] - fact_ventas['monto_descuento']) / 1.19).round(0)
fact_ventas['margen_ganancia'] = (fact_ventas['monto_neto'] - (fact_ventas['costo_unitario'] * fact_ventas['cantidad'])).round(0)
fact_ventas.drop(columns=['precio_lista', 'costo_unitario'], inplace=True)

# 3. Fact_Inventario
n_inv = 2000
fact_inventario = pd.DataFrame({
    'sk_inventario': range(1, n_inv + 1),
    'sk_producto': np.random.choice(dim_producto['sk_producto'], n_inv),
    'sk_sucursal': np.random.choice([1, 2, 3, 4], n_inv),
    'stock_actual': np.random.randint(0, 50, n_inv)
})
fact_inventario['flag_quiebre_stock'] = (fact_inventario['stock_actual'] <= 2).astype(int)

# Guardar CSVs
dim_canal.to_csv('Dim_Canal.csv', index=False)
dim_sucursal.to_csv('Dim_Sucursal.csv', index=False)
dim_producto.to_csv('Dim_Producto.csv', index=False)
dim_campana.to_csv('Dim_Campana.csv', index=False)
fact_ventas.to_csv('Fact_Ventas.csv', index=False)
fact_inventario.to_csv('Fact_Inventario.csv', index=False)

print("Datasets generados con éxito")