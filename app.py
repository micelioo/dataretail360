import os
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="DataRetail 360 | Plataforma Analítica", layout="wide")
AZUL_CORP = "#1B4F72"
NARANJA_ALERTA = "#D35400"
CELESTE_SEC = "#5DADE2"

@st.cache_data
def cargar_desde_dw():
    conn = sqlite3.connect("dataretail360.db")
    df_v = pd.read_sql_query("SELECT * FROM dm_ventas_consolidadas", conn)
    df_i = pd.read_sql_query("SELECT * FROM dm_inventario_analitico", conn)
    conn.close()
    df_v["periodo"] = df_v["anio"].astype(str) + "-" + df_v["mes"].astype(str).str.zfill(2)
    return df_v, df_i

def generar_sql_nlq(pregunta: str, api_key: str = "") -> str:
    """Genera SQL mediante LLM (si hay API Key) o motor NLQ local sobre capa semántica."""
    p = pregunta.lower()
    if api_key.strip():
        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            prompt = f"""Eres un asistente Text-to-SQL para SQLite.
Usa SOLO las vistas dm_ventas_consolidadas y dm_inventario_analitico.
Columnas dm_ventas_consolidadas: fecha_completa, anio, trimestre, mes, nombre_mes, bk_sku, nombre_producto, categoria, es_registro_actual, sk_cliente, segmento_cliente, nombre_sucursal, nombre_canal, tipo_canal, sk_campana, nombre_campana, presupuesto_asignado, numero_ticket, cantidad_vendida, monto_bruto, monto_descuento, monto_neto, margen_ganancia.
Columnas dm_inventario_analitico: bk_sku, nombre_producto, categoria, nombre_sucursal, cantidad_stock, stock_minimo, flag_quiebre_stock.
Devuelve SOLO la consulta SQL sin markdown. Pregunta: {pregunta}"""
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return resp.text.replace("```sql", "").replace("```", "").strip()
        except Exception:
            pass

    # Fallback NLQ determinístico
    if "sucursal" in p:
        return """SELECT nombre_sucursal,
       ROUND(SUM(monto_neto), 0) AS venta_neta_oficial,
       ROUND(SUM(margen_ganancia) * 100.0 / SUM(monto_neto), 1) AS margen_pct
FROM dm_ventas_consolidadas
GROUP BY nombre_sucursal
ORDER BY venta_neta_oficial DESC;"""
    elif "campaña" in p or "campana" in p or "roi" in p:
        return """SELECT nombre_campana, presupuesto_asignado,
       ROUND((SUM(margen_ganancia) - presupuesto_asignado) * 100.0 / presupuesto_asignado, 1) AS roi_pct
FROM dm_ventas_consolidadas
WHERE sk_campana != -1
GROUP BY nombre_campana, presupuesto_asignado
ORDER BY roi_pct DESC;"""
    elif "quiebre" in p or "stock" in p or "inventario" in p:
        return """SELECT bk_sku, nombre_producto, nombre_sucursal, cantidad_stock
FROM dm_inventario_analitico
WHERE flag_quiebre_stock = 1
ORDER BY bk_sku;"""
    else:
        return """SELECT categoria,
       ROUND(SUM(monto_neto), 0) AS venta_neta_oficial,
       ROUND(SUM(margen_ganancia), 0) AS margen_oficial
FROM dm_ventas_consolidadas
WHERE anio = 2026 AND trimestre = 3 AND es_registro_actual = 1
GROUP BY categoria
ORDER BY venta_neta_oficial DESC;"""

def auditar_sql(sql: str) -> list:
    """Validador crítico de gobernanza, privacidad (PII) y reglas de negocio."""
    alertas = []
    s = sql.lower()
    if any(t in s for t in ["dim_cliente", "fact_ventas", "bk_rut", "nombre_completo", "email"]):
        alertas.append("Fuga de privacidad (PII) o acceso directo a tablas base fuera de capa semántica (`dm_`).")
    if "monto_bruto" in s and "1.19" not in s and "monto_neto" not in s:
        alertas.append("Alucinación de métrica: usa `monto_bruto` sin descontar IVA (1.19).")
    if "categoria" in s and "es_registro_actual" not in s and "dm_ventas" in s:
        alertas.append("Advertencia SCD Tipo 2: no filtra `es_registro_actual = 1` (afecta agrupación actual de `SKU-103`).")
    if any(cmd in s for cmd in ["drop ", "delete ", "update ", "insert ", "alter "]):
        alertas.append("Bloqueo de seguridad: solo se permiten consultas de lectura (`SELECT`).")
    return alertas

df_ventas, df_inv = cargar_desde_dw()

st.title("DataRetail 360 - Solución analítica integrada")
st.caption("Conectado a capa semántica SQLite (`dm_ventas_consolidadas` & `dm_inventario_analitico`) | Datos anonimizados sin PII")

tab1, tab2 = st.tabs(["Dashboard ejecutivo", "IA Generativa (Text-to-SQL) y Auditoría"])

with tab1:
    st.sidebar.header("Filtros globales")
    sel_canal = st.sidebar.multiselect("Canal", df_ventas["nombre_canal"].unique(), default=df_ventas["nombre_canal"].unique())
    sel_suc = st.sidebar.multiselect("Sucursal", df_ventas["nombre_sucursal"].unique(), default=df_ventas["nombre_sucursal"].unique())
    sel_cat = st.sidebar.multiselect("Categoría", df_ventas["categoria"].unique(), default=df_ventas["categoria"].unique())
    sel_seg = st.sidebar.multiselect("Segmento Cliente", df_ventas["segmento_cliente"].unique(), default=df_ventas["segmento_cliente"].unique())

    df_v = df_ventas[
        (df_ventas["nombre_canal"].isin(sel_canal)) &
        (df_ventas["nombre_sucursal"].isin(sel_suc)) &
        (df_ventas["categoria"].isin(sel_cat)) &
        (df_ventas["segmento_cliente"].isin(sel_seg))
    ]
    df_i = df_inv[(df_inv["nombre_sucursal"].isin(sel_suc)) & (df_inv["categoria"].isin(sel_cat))]

    venta_neta = df_v["monto_neto"].sum()
    margen_pct = (df_v["margen_ganancia"].sum() / venta_neta * 100) if venta_neta > 0 else 0
    ticket_prom = (venta_neta / df_v["numero_ticket"].nunique()) if len(df_v) > 0 else 0
    quiebre_pct = (df_i["flag_quiebre_stock"].mean() * 100) if len(df_i) > 0 else 0
    compras_cli = df_v.groupby("sk_cliente")["numero_ticket"].nunique()
    rec_pct = ((compras_cli > 1).sum() / len(compras_cli) * 100) if len(compras_cli) > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Venta neta total", f"${venta_neta:,.0f}", "Meta: > +8% anual")
    c2.metric("Margen bruto %", f"{margen_pct:.1f}%", f"{margen_pct - 28:.1f} pp vs Meta (28%)")
    c3.metric("Ticket promedio", f"${ticket_prom:,.0f}", f"{ticket_prom - 65000:,.0f} CLP vs Meta (65k)")
    c4.metric("Quiebre de stock %", f"{quiebre_pct:.1f}%", "Meta: < 3,0%", delta_color="inverse")
    c5.metric("Recurrencia clientes", f"{rec_pct:.1f}%", f"{rec_pct - 35:.1f} pp vs Meta (35%)")

    st.divider()

    col_izq, col_der = st.columns([6, 4])
    with col_izq:
        st.subheader("Evolución mensual de venta neta vs. meta (+8%)")
        v_mes = df_v.groupby("periodo", as_index=False)["monto_neto"].sum().sort_values("periodo")
        fig_l = px.line(v_mes, x="periodo", y="monto_neto", markers=True, labels={"periodo": "Mes", "monto_neto": "Venta Neta ($)"})
        fig_l.update_traces(line_color=AZUL_CORP, line_width=3)
        fig_l.add_hline(y=v_mes["monto_neto"].mean() * 1.08, line_dash="dash", line_color=NARANJA_ALERTA, annotation_text="Meta (+8%)")
        st.plotly_chart(fig_l, use_container_width=True)

    with col_der:
        st.subheader("Venta neta y margen por sucursal")
        v_suc = df_v.groupby("nombre_sucursal", as_index=False).agg(venta=("monto_neto", "sum"), margen=("margen_ganancia", "sum"))
        v_suc["margen_pct"] = (v_suc["margen"] / v_suc["venta"] * 100).round(1)
        v_suc["color"] = v_suc["margen_pct"].apply(lambda x: NARANJA_ALERTA if x < 28 else AZUL_CORP)
        fig_b = px.bar(v_suc.sort_values("venta"), x="venta", y="nombre_sucursal", orientation="h", text="margen_pct",
                       labels={"venta": "Venta Neta ($)", "nombre_sucursal": ""})
        fig_b.update_traces(marker_color=v_suc.sort_values("venta")["color"], texttemplate="Margen: %{text}%", textposition="outside")
        fig_b.update_layout(margin=dict(r=85))
        st.plotly_chart(fig_b, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("ROI de campañas (%)")
        v_camp = df_v[df_v["sk_campana"] != -1].groupby(["nombre_campana", "presupuesto_asignado"], as_index=False)["margen_ganancia"].sum()
        v_camp["roi_pct"] = ((v_camp["margen_ganancia"] - v_camp["presupuesto_asignado"]) / v_camp["presupuesto_asignado"] * 100).round(1)
        fig_c = px.bar(v_camp, x="nombre_campana", y="roi_pct", text="roi_pct", labels={"nombre_campana": "Campaña", "roi_pct": "ROI (%)"})
        fig_c.update_traces(marker_color=AZUL_CORP, texttemplate="%{text}%", textposition="outside")
        fig_c.add_hline(y=150, line_dash="dash", line_color=NARANJA_ALERTA, annotation_text="Meta 150%")
        st.plotly_chart(fig_c, use_container_width=True)

    with col2:
        st.subheader("Participación digital vs. física")
        v_can = df_v.groupby(["periodo", "tipo_canal"], as_index=False)["monto_neto"].sum()
        fig_d = px.bar(v_can, x="periodo", y="monto_neto", color="tipo_canal", barmode="relative",
                       color_discrete_map={"Digital": AZUL_CORP, "Físico": CELESTE_SEC})
        st.plotly_chart(fig_d, use_container_width=True)

    with col3:
        st.subheader("Alerta: productos en quiebre")
        alertas = df_i[df_i["flag_quiebre_stock"] == 1][["bk_sku", "nombre_producto", "nombre_sucursal", "cantidad_stock"]]
        st.dataframe(alertas.sort_values("bk_sku"), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Asistente NLQ / Text-to-SQL y Auditoría de gobernanza")
    api_key = st.sidebar.text_input("Gemini API Key (opcional para LLM en vivo)", type="password")

    pregunta_nlq = st.text_input(
        "Consulta en lenguaje natural sobre el modelo dimensional:",
        value="Muéstrame la venta neta y margen por categoría en el tercer trimestre de 2026"
    )

    sql_generada = generar_sql_nlq(pregunta_nlq, api_key)
    sql_editada = st.text_area("SQL generada (editable para pruebas de auditoría):", value=sql_generada, height=130)

    errores_gov = auditar_sql(sql_editada)
    if errores_gov:
        for err in errores_gov:
            st.error(err)
    else:
        st.success("Consulta validada: cumple reglas de capa semántica (`dm_`), sin PII y métricas oficiales.")
        try:
            conn = sqlite3.connect("dataretail360.db")
            df_res = pd.read_sql_query(sql_editada, conn)
            conn.close()
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error de sintaxis SQL: {e}")

    st.divider()
    st.markdown("#### Caso documentado de auditoría crítica (Antes vs. Después)")
    c_err, c_ok = st.columns(2)
    with c_err:
        st.error("SQL sin gobernanza (alucinaciones detectadas)")
        st.code("""SELECT p.categoria, c.nombre_completo, c.rut,
       SUM(v.monto_bruto - v.monto_descuento) AS venta_neta
FROM Fact_Ventas v
JOIN Dim_Producto p ON v.sk_producto = p.sk_producto
JOIN Dim_Cliente c ON v.sk_cliente = c.sk_cliente
WHERE trimestre = 3;""", language="sql")
        st.markdown("""
        **Hallazgos:**
        1. **Alucinación de métrica:** No divide por `1.19` (sobreestima ventas en 19% al incluir IVA).
        2. **Fuga de privacidad (PII):** Expone `nombre_completo` y `rut` desde `Dim_Cliente`.
        3. **Omisión SCD Tipo 2:** No filtra `es_registro_actual = 1` para productos recategorizados.
        """)

    with c_ok:
        st.success("SQL corregida sobre capa semántica (`dm_`)")
        sql_validada = """SELECT categoria,
       ROUND(SUM(monto_neto), 0) AS venta_neta_oficial,
       ROUND(SUM(margen_ganancia), 0) AS margen_oficial
FROM dm_ventas_consolidadas
WHERE anio = 2026 AND trimestre = 3 AND es_registro_actual = 1
GROUP BY categoria
ORDER BY venta_neta_oficial DESC;"""
        st.code(sql_validada, language="sql")
        conn = sqlite3.connect("dataretail360.db")
        df_res_ref = pd.read_sql_query(sql_validada, conn)
        conn.close()
        st.dataframe(df_res_ref, use_container_width=True, hide_index=True)