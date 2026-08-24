# -*- coding: utf-8 -*-
"""
Etiquetas de feria — Kbas Office
Sube el Excel de la temporada, pega las referencias que necesites
(salteadas, en cualquier orden) y descarga un PDF de etiquetas con
código de barras EAN-13, listo para imprimir en hojas Multi3 4716
(A4, 65 etiquetas de 38 x 21,2 mm).
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

# ---------- Plantilla Multi3 4716 (= Avery L7651) ----------
COLS, FILAS = 5, 13                 # 65 etiquetas por hoja
ETI_W, ETI_H = 38 * mm, 21.2 * mm   # tamaño de cada etiqueta
# La impresora de Salva añade ~1cm de margen extra por cada lado al imprimir
# (sin la opción "sin márgenes"/borderless). Se compensa aquí: se pide 0mm
# para que, tras el offset físico de la impresora, caiga en el 1cm real.
OFFSET_IMPRESORA = 10 * mm

MARGEN_IZQ = 10 * mm - OFFSET_IMPRESORA
MARGEN_SUP = 10 * mm - OFFSET_IMPRESORA
PASO_X = ETI_W                      # sin separación horizontal entre etiquetas
PASO_Y = ETI_H                      # sin separación vertical entre etiquetas

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


def generar_pdf(etiquetas, fila_ini, col_ini):
    """etiquetas: lista de dicts {ref, ean, precio}. Devuelve bytes del PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, alto_pag = A4

    pos = (fila_ini - 1) * COLS + (col_ini - 1)  # hueco inicial en la hoja

    for et in etiquetas:
        hoja_pos = pos % (COLS * FILAS)
        if pos > 0 and hoja_pos == 0:
            c.showPage()
        col = hoja_pos % COLS
        fila = hoja_pos // COLS

        x = MARGEN_IZQ + col * PASO_X
        y = alto_pag - MARGEN_SUP - fila * PASO_Y - ETI_H

        # Línea 1: ref + precio (negrita, pegada al código)
        c.setFont("Helvetica-Bold", 8)
        texto = et["ref"]
        if et["precio"] is not None:
            texto += f'  {et["precio"]:.2f} €'.replace(".", ",")
        c.drawString(x + 1.5 * mm, y + ETI_H - 3.6 * mm, texto)

        # Código de barras EAN-13 (el widget recalcula el dígito de control)
        codigo = et["ean"][:12]
        bc = Ean13BarcodeWidget(codigo)
        bc.barHeight = 13 * mm
        bc.barWidth = 0.28 * mm
        bc.fontSize = 6
        bc.humanReadable = True
        b = bc.getBounds()
        d = Drawing(b[2] - b[0], b[3] - b[1])
        d.add(bc)
        d.translate(-b[0], -b[1])  # compensar el origen interno del widget
        renderPDF.draw(d, c, x + 1.5 * mm, y + 1.2 * mm)

        pos += 1

    c.save()
    buf.seek(0)
    return buf


# ---------- Interfaz ----------
st.set_page_config(page_title="Etiquetas de feria · Kbas Office", page_icon="🏷️")

st.title("Etiquetas de feria")
st.caption("Sube el Excel de la temporada, pega las referencias que necesites (en cualquier orden) y descarga el PDF de etiquetas para hojas Multi3 4716 (65 por hoja).")

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
    unidades = st.number_input("Etiquetas por referencia", min_value=1, max_value=65, value=1)
    precio_elegido = st.selectbox("Precio en la etiqueta", list(PRECIOS.keys()), index=0)
with c2:
    fila_ini = st.number_input("Empezar en fila (para hojas empezadas)", min_value=1, max_value=FILAS, value=1)
    col_ini = st.number_input("Empezar en columna", min_value=1, max_value=COLS, value=1)

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

        pdf = generar_pdf(etiquetas, int(fila_ini), int(col_ini))

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
