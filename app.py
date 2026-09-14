# -*- coding: utf-8 -*-
"""
Etiquetas de feria — Kbas Office
Sube el Excel de la temporada, pega las referencias que necesites
(salteadas, en cualquier orden) y descarga un PDF de etiquetas con
código de barras EAN-13, listo para imprimir en hojas Multi3 4717
(A4, 44 etiquetas de 48,5 x 25,4 mm — 4 por línea, 11 filas).
"""

import io
import re

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# ---------- Plantilla Multi3 4717 (48,5 x 25,4 mm · 44 por hoja) ----------
COLS, FILAS = 4, 11                   # 44 etiquetas por hoja (4 por línea)
ETI_W, ETI_H = 48.5 * mm, 25.4 * mm   # medida real de la etiqueta impresa

ANCHO_PAG, ALTO_PAG = A4

# La hoja 4717 lleva las etiquetas centradas en el A4 y pegadas entre sí
# (cantos rectos, sin separación). Calculamos el margen para centrar la
# cuadrícula: ~8,0 mm a los lados y ~8,8 mm arriba/abajo.
#
# OFFSET_IMPRESORA: si tu impresora desplaza todo al imprimir (no borderless),
# súbelo aquí y se pre-compensa. De momento partimos de 0 y, si hiciera falta,
# se afina con los sliders de "Ajuste fino" tras una impresión de prueba.
OFFSET_IMPRESORA = 0 * mm

MARGEN_IZQ = (ANCHO_PAG - COLS * ETI_W) / 2 - OFFSET_IMPRESORA
MARGEN_SUP = (ALTO_PAG - FILAS * ETI_H) / 2 - OFFSET_IMPRESORA
PASO_X = ETI_W                        # sin separación horizontal entre etiquetas
PASO_Y = ETI_H                        # sin separación vertical entre etiquetas

PRECIOS = {
    "Sin precio": None,
    "Precio venta": "Precio venta",
    "PVP Recomendado": "PVP Recomendado",
    "PVP tienda online": "Pvp tienda online",
}


def limpiar(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def a_precio(v):
    s = limpiar(v).replace("€", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def extraer_refs(texto):
    """Acepta refs separadas por comas, espacios, puntos y coma o líneas."""
    trozos = re.split(r"[\s,;]+", texto.upper())
    refs = []
    for t in trozos:
        t = t.strip()
        if t and t not in refs:
            refs.append(t)
    return refs


def generar_pdf(etiquetas, fila_ini, col_ini, ajuste_x=0.0, ajuste_y=0.0, hueco_texto=1.2):
    """etiquetas: lista de dicts {ref, ean, precio}. Devuelve bytes del PDF.
    ajuste_x/ajuste_y: desplazamiento fino en mm (positivo = derecha/abajo).
    hueco_texto: separación en mm entre el texto y el código de barras."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, alto_pag = A4
    ajuste_x_pt, ajuste_y_pt = ajuste_x * mm, ajuste_y * mm

    pos = (fila_ini - 1) * COLS + (col_ini - 1)  # hueco inicial en la hoja

    for et in etiquetas:
        hoja_pos = pos % (COLS * FILAS)
        if pos > 0 and hoja_pos == 0:
            c.showPage()
        col = hoja_pos % COLS
        fila = hoja_pos // COLS

        x = MARGEN_IZQ + col * PASO_X + ajuste_x_pt
        y = alto_pag - MARGEN_SUP - fila * PASO_Y - ETI_H - ajuste_y_pt

        # Línea 1: ref + precio (negrita, pegada al código)
        c.setFont("Helvetica-Bold", 9)
        texto = et["ref"]
        if et["precio"] is not None:
            texto += f'  {et["precio"]:.2f} €'.replace(".", ",")
        c.drawString(x + 2.0 * mm, y + ETI_H - 4.0 * mm, texto)

        # Código de barras EAN-13 (el widget recalcula el dígito de control)
        # Con la etiqueta más ancha (48,5 mm) usamos el barcode a tamaño casi
        # nominal para que escanee mejor en la feria.
        codigo = et["ean"][:12]
        bc = Ean13BarcodeWidget(codigo)
        bc.barHeight = 13 * mm
        bc.barWidth = 0.33 * mm
        bc.fontSize = 7
        bc.humanReadable = True
        b = bc.getBounds()
        d = Drawing(b[2] - b[0], b[3] - b[1])
        d.add(bc)
        d.translate(-b[0], -b[1])
        y_codigo = y + ETI_H - 4.0 * mm - hueco_texto * mm - (b[3] - b[1])
        renderPDF.draw(d, c, x + 2.0 * mm, y_codigo)

        pos += 1

    c.save()
    buf.seek(0)
    return buf


# ---------- Interfaz ----------
st.set_page_config(page_title="Etiquetas de feria · Kbas Office", page_icon="🏷️")

st.title("Etiquetas de feria")
st.caption("Sube el Excel de la temporada, pega las referencias que necesites (en cualquier orden) y descarga el PDF de etiquetas para hojas Multi3 4717 (48,5 x 25,4 mm · 44 por hoja, 4 por línea).")

excel_subido = st.file_uploader(
    "1 · Excel de la temporada (con columnas Ref. y Barcode)",
    type=["xlsx", "xlsm"],
)

refs_texto = st.text_area(
    "2 · Referencias (una por línea, o separadas por comas o espacios)",
    height=140,
    placeholder="KB1472601_00\nKB3802605_41, KT3872613_05\nKB1472603_08",
)

c1, c2 = st.columns(2)
with c1:
    unidades = st.number_input("Etiquetas por referencia", min_value=1, max_value=COLS * FILAS, value=1)
    precio_elegido = st.selectbox("Precio en la etiqueta", list(PRECIOS.keys()), index=0)
with c2:
    fila_ini = st.number_input("Empezar en fila (para hojas empezadas)", min_value=1, max_value=FILAS, value=1)
    col_ini = st.number_input("Empezar en columna", min_value=1, max_value=COLS, value=1)

with st.expander("⚙ Ajuste fino de impresión (mueve todo si tu impresora descuadra)"):
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        ajuste_x = st.number_input("Mover horizontal (mm, + = derecha)", value=0.0, step=0.5, format="%.1f")
    with cc2:
        ajuste_y = st.number_input("Mover vertical (mm, + = abajo)", value=0.0, step=0.5, format="%.1f")
    with cc3:
        hueco_texto = st.number_input("Separación texto-código (mm)", value=1.2, step=0.2, format="%.1f", min_value=0.0)
    st.caption("Imprime, mide con una regla cuánto se desvía, y ajusta estos números. La próxima vez ya sale bien a la primera.")

if excel_subido and refs_texto.strip():
    if st.button("Generar PDF de etiquetas", type="primary"):
        try:
            df = pd.read_excel(io.BytesIO(excel_subido.getvalue()))
        except Exception as e:
            st.error(f"No puedo leer el Excel: {e}")
            st.stop()

        if "Ref." not in df.columns or "Barcode" not in df.columns:
            st.error("El Excel debe tener las columnas 'Ref.' y 'Barcode'. Usa el export habitual del ERP.")
            st.stop()

        df["_ref"] = df["Ref."].astype(str).str.strip().str.upper()
        col_precio = PRECIOS[precio_elegido]

        refs = extraer_refs(refs_texto)
        etiquetas, no_encontradas, sin_ean = [], [], []
        for ref in refs:
            fila = df[df["_ref"] == ref]
            if fila.empty:
                no_encontradas.append(ref)
                continue
            fila = fila.iloc[0]
            ean = re.sub(r"\D", "", limpiar(fila.get("Barcode")))
            if len(ean) < 12:
                sin_ean.append(ref)
                continue
            precio = a_precio(fila.get(col_precio)) if col_precio else None
            for _ in range(int(unidades)):
                etiquetas.append({"ref": ref, "ean": ean, "precio": precio})

        if not etiquetas:
            st.error("Ninguna de las referencias está en el Excel (o no tienen código de barras).")
            st.stop()

        pdf = generar_pdf(etiquetas, int(fila_ini), int(col_ini), ajuste_x, ajuste_y, hueco_texto)

        st.success(f"Listo: {len(etiquetas)} etiquetas de {len(refs) - len(no_encontradas) - len(sin_ean)} referencias.")
        if no_encontradas:
            with st.expander(f"⚠ {len(no_encontradas)} referencias no están en el Excel"):
                st.text("\n".join(no_encontradas))
        if sin_ean:
            with st.expander(f"⚠ {len(sin_ean)} referencias sin código de barras válido"):
                st.text("\n".join(sin_ean))

        st.download_button(
            "⬇ Descargar etiquetas.pdf",
            data=pdf,
            file_name="etiquetas.pdf",
            mime="application/pdf",
        )
        st.caption("Al imprimir: tamaño real / escala 100%, sin 'ajustar a la página', para que caigan clavadas en las pegatinas.")
else:
    st.info("Sube el Excel y pega al menos una referencia para empezar.")
