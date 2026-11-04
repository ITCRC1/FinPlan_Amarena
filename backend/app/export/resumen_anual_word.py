# -*- coding: utf-8 -*-
"""El resumen ejecutivo año contra año, en Word.

Owner, 2026-11-04: *«hazlo en esta misma estructura… como si fuera un resumen
ejecutivo»*, mostrando el informe operativo de CWL.

## Los números NO se calculan acá

Este módulo recibe el payload que ya armó `resumen_anual_api` —el mismo que
dibuja la pantalla— y lo redacta. No suma, no promedia y no corrige nada.

Es la misma regla que sostiene `executive_summary.py`: si el documento
derivara sus propias cifras, el día que difieran de la pantalla nadie sabría
cuál manda, y la diferencia no se vería, porque un documento en prosa no cuadra
contra nada. Acá el Word y la pantalla **son el mismo número** porque salen de
la misma llamada.

## Estructura

Sigue el informe de CWL en lo que aplica a un corte anual:

    1. Propósito y cómo leerlo     — de dónde salen los números y qué NO dicen
    2. Resumen ejecutivo           — los KPIs y la cascada, en una tabla
    3. Lectura del año             — la narrativa, con sus advertencias
    4. Ingresos por línea          — los doce meses de cada año
    5. Gasto por clase             — planilla, OPEX, costo, propiedad
    6. Utilidad por departamento
    7. Anexo: el detalle mensual completo

No lleva las secciones de hallazgos de clasificación ni la agenda por
responsable: ésas viven de un cierre mensual con mayor cargado, y acá se está
comparando un presupuesto contra una proyección.
"""
from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

DOCX = ("application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document")

FUENTE = "Calibri"
CUERPO = 10
AZUL = RGBColor(0x1F, 0x38, 0x64)
GRIS = RGBColor(0x59, 0x59, 0x59)
ROJO = RGBColor(0xC0, 0x00, 0x00)
VERDE = RGBColor(0x1E, 0x7A, 0x45)


def _m(v) -> str:
    """Un monto como lo lee el owner: sin centavos, con punto de miles."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    if abs(v) < 0.5:
        return "—"
    return "{}${:,.0f}".format("-" if v < 0 else "", abs(v)).replace(",", ".")


def _dm(v) -> str:
    """Una diferencia en dólares. El signo va ANTES del símbolo: «+$66.61» y no
    «$+66.61», que es lo que sale de pegar un formato con signo detrás del $."""
    return "{}${:,.2f}".format("+" if v >= 0 else "-", abs(v))


def _pc(v) -> str:
    return "—" if v is None else "{:+.1f}%".format(v)


def _h(doc, texto: str, nivel: int = 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10 if nivel == 1 else 7)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(13 if nivel == 1 else 11)
    r.font.color.rgb = AZUL
    r.font.name = FUENTE
    return p


def _p(doc, texto: str, italic: bool = False, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(texto)
    r.italic = italic
    r.font.size = Pt(CUERPO)
    r.font.name = FUENTE
    if color is not None:
        r.font.color.rgb = color
    return p


def _tabla(doc, encabezados, filas, resaltar=()):
    """Una tabla simple. `resaltar` son los índices de fila que van en negrita."""
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"
    for i, h in enumerate(encabezados):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h))
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.name = FUENTE
        r.font.color.rgb = AZUL
    for n, fila in enumerate(filas):
        cells = t.add_row().cells
        for i, v in enumerate(fila):
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            if i:
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r = par.add_run(str(v))
            r.font.size = Pt(8.5)
            r.font.name = FUENTE
            if n in resaltar:
                r.bold = True
    return t


def _cuadro(doc, filas, a_anio, b_anio):
    """Concepto · año base · año comparado · variación, con el % al lado."""
    _tabla(doc,
           ["Concepto", str(a_anio), str(b_anio), "Variación", "%"],
           [[f["nombre"], _m(f["base"]), _m(f["comp"]), _m(f["var"]),
             _pc(f.get("var_pct"))] for f in filas])


def _mensual(doc, titulo, filas, meses, lado, anio):
    """Los doce meses de un año, una fila por concepto."""
    _h(doc, "{} — {}".format(titulo, anio), nivel=2)
    _tabla(doc, ["Concepto"] + meses + ["Año"],
           [[f["nombre"]] + [_m(x) for x in f[lado]] + [_m(f[
               "base" if lado == "base_meses" else "comp"])] for f in filas])


def build_resumen_anual(d: dict, propiedad: str = "Amarena") -> bytes:
    """`d` es la respuesta de `/reports/resumen-anual/`, tal cual."""
    a, b = d["base"], d["comparado"]
    ka, kb = d["kpis"]["base"], d["kpis"]["comp"]
    meses = d["meses"]

    doc = Document()
    est = doc.styles["Normal"]
    est.font.name = FUENTE
    est.font.size = Pt(CUERPO)

    # ── Portada ────────────────────────────────────────────────────────────
    p = doc.add_paragraph()
    r = p.add_run("{}\nResumen ejecutivo · {} contra {}".format(
        propiedad.upper(), a["anio"], b["anio"]))
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    r.font.name = FUENTE
    _p(doc, "{} {} {}   vs   {} {} {}".format(
        a["tipo"], a["version"], a["anio"], b["tipo"], b["version"], b["anio"]),
       italic=True, color=GRIS)

    # ── 1. Propósito ───────────────────────────────────────────────────────
    _h(doc, "1.  Propósito y cómo leer este documento")
    _p(doc, "Compara dos años completos: el que termina, leído del Forecast, y "
            "el que viene, leído del Budget. No es un «cómo vamos contra lo que "
            "dijimos» —esa pregunta la contesta el cierre mensual— sino en qué "
            "se diferencia un año del otro.")
    _p(doc, "Los números salen del mismo motor que calcula el P&L y el Dashboard. "
            "Este documento no suma ni corrige nada: lo pide y lo redacta. Si un "
            "número de acá no coincidiera con el P&L, sería un error del motor y "
            "no del informe — por construcción no pueden diferir.")
    if d["meses_con_dato"]["base"] < 12 or d["meses_con_dato"]["comp"] < 12:
        _p(doc, "⚠️  {} trae {} meses con dato y {} trae {}. Un año incompleto "
                "contra uno completo exagera toda variación: léanse los "
                "porcentajes con esa reserva.".format(
                    a["anio"], d["meses_con_dato"]["base"],
                    b["anio"], d["meses_con_dato"]["comp"]), color=ROJO)

    # ── 2. Resumen ejecutivo ───────────────────────────────────────────────
    _h(doc, "2.  Resumen ejecutivo")
    _h(doc, "2.1  Indicadores de habitaciones", nivel=2)
    _tabla(doc, ["Indicador", str(a["anio"]), str(b["anio"]), "Variación"], [
        ["Noches disponibles", "{:,.0f}".format(ka["disponibles"]),
         "{:,.0f}".format(kb["disponibles"]),
         "{:+,.0f}".format(kb["disponibles"] - ka["disponibles"])],
        ["Noches ocupadas", "{:,.0f}".format(ka["ocupadas"]),
         "{:,.0f}".format(kb["ocupadas"]),
         "{:+,.0f}".format(kb["ocupadas"] - ka["ocupadas"])],
        ["Pax", "{:,.0f}".format(ka["pax"]), "{:,.0f}".format(kb["pax"]),
         "{:+,.0f}".format(kb["pax"] - ka["pax"])],
        ["Ocupación", "{:.1f}%".format(100 * ka["ocupacion"]),
         "{:.1f}%".format(100 * kb["ocupacion"]),
         "{:+.1f} pp".format(100 * (kb["ocupacion"] - ka["ocupacion"]))],
        ["ADR", "${:,.2f}".format(ka["adr"]), "${:,.2f}".format(kb["adr"]),
         _dm(kb["adr"] - ka["adr"])],
        ["RevPAR", "${:,.2f}".format(ka["revpar"]), "${:,.2f}".format(kb["revpar"]),
         _dm(kb["revpar"] - ka["revpar"])],
    ])
    _h(doc, "2.2  La cascada, de ingreso a utilidad", nivel=2)
    _cuadro(doc, d["resultado"], a["anio"], b["anio"])

    # ── 3. Lectura del año ─────────────────────────────────────────────────
    _h(doc, "3.  Lectura del año")
    _p(doc, "Las frases que siguen se arman con los números del cuadro. "
            "Describen lo que se movió; no dicen si está bien — eso es juicio, "
            "y el juicio no sale del dato.", italic=True, color=GRIS)
    for f in d["narrativa"]:
        _p(doc, ("• " + f), color=(ROJO if f.startswith("⚠️") else None))

    # ── 4 a 6 ──────────────────────────────────────────────────────────────
    _h(doc, "4.  Ingresos por línea")
    _cuadro(doc, d["ingresos"], a["anio"], b["anio"])

    _h(doc, "5.  Gasto por clase")
    _cuadro(doc, d["clases"], a["anio"], b["anio"])
    _p(doc, "«Propiedad — todas las 8xxx» incluye capital, financieros, "
            "depreciación e impuesto. La línea «No operativos» de la cascada es "
            "sólo el bloque de arriba del EBITDA, así que da distinto a "
            "propósito.", italic=True, color=GRIS)

    _h(doc, "6.  Utilidad por departamento")
    _cuadro(doc, [x["utilidad"] for x in d["departamentos"]], a["anio"], b["anio"])

    # ── 7. Anexo mensual ───────────────────────────────────────────────────
    doc.add_page_break()
    _h(doc, "7.  Anexo — el detalle mes a mes")
    _p(doc, "Los mismos conceptos, abiertos por mes. Es el detalle al que se "
            "baja cuando una variación anual no se explica sola.",
       italic=True, color=GRIS)
    for titulo, filas in (("Ingresos", d["ingresos"]),
                          ("Gasto por clase", d["clases"]),
                          ("Resultado", d["resultado"])):
        _mensual(doc, titulo, filas, meses, "base_meses", a["anio"])
        _mensual(doc, titulo, filas, meses, "comp_meses", b["anio"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
