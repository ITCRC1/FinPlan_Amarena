# -*- coding: utf-8 -*-
"""El Resumen Ejecutivo mensual en Word, con el formato que el owner ya usa.

Owner, 2026-09-30, entregando `Executive Summary – Financial & Operational
Results YTD AUGUST 2026.pdf`: *«necesito un análisis de resultados según el PDF
que te voy a pasar. usa este formato como estándar y prepara uno igual para
agosto en Amarena. quiero el informe en word»*.

## Qué es y qué NO es

Es el documento que se manda a los dueños: portada, introducción, y el año
mirado desde los tres cortes —el mes, el acumulado y el aterrizaje— con la
prosa que explica cada variación y los cuadros que la sostienen.

⚠️ **La prosa se ESCRIBE con los números, no al revés.** Cada frase se arma a
partir de la variación real que calculó el motor: si el ingreso está 7,4% arriba
del presupuesto, el texto dice 7,4% porque lo leyó, no porque alguien lo tecleó.
Un informe donde el texto y el cuadro pueden discrepar es peor que no tenerlo —
la discrepancia no se ve, y el que la encuentre deja de creerle a los dos.

⚠️ **Lo que el sistema no sabe, el informe lo DICE.** El PDF del owner trae
secciones que no salen de la contabilidad —la actividad comercial del mes, el
mix por país, las notas de mercado—. Acá van con un recuadro que pide el dato en
vez de una frase inventada que se lea igual de bien.

## De dónde salen los números

De `pl_api.get_pl_compare`, el MISMO agregador del Dashboard y del P&L a dueños.
No hay una segunda aritmética: el informe no puede decir un GOP distinto del que
muestra la pantalla de la que salió.
"""
from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

DOCX = ("application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document")

VERDE = RGBColor(0x2A, 0x4A, 0x33)
ORO = RGBColor(0xA8, 0x8C, 0x50)
GRIS = RGBColor(0x60, 0x66, 0x6E)
NEGRO = RGBColor(0x1A, 0x1D, 0x21)
ROJO = RGBColor(0xB3, 0x26, 0x1E)

MESES = ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "setiembre", "octubre", "noviembre", "diciembre"]


# ═══════════════════════ Números, dichos como en el PDF ═══════════════════════

def k(v: float | None) -> str:
    """En miles, como el owner los escribe: `$277.9K`, `$3.974M`.

    ⚠️ El PDF mezcla las dos escalas a propósito —miles para un mes, millones
    para el año— porque `$3,973,720.59` en medio de una frase no se lee. El
    corte está en el millón.
    """
    if v is None:
        return "n/d"
    s = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000:
        return f"{s}${a / 1_000_000:,.3f}M"
    return f"{s}${a / 1_000:,.1f}K"


def usd(v: float | None, dec: int = 2) -> str:
    if v is None:
        return "n/d"
    return f"${v:,.{dec}f}"


def pct(v: float | None, dec: int = 2) -> str:
    return "n/d" if v is None else f"{v * 100:,.{dec}f}%"


def var_pct(act: float, base: float) -> float | None:
    """La variación relativa. `None` cuando la base es cero.

    ⚠️ No es «infinito» ni «100%»: dividir entre cero no da un porcentaje, y
    escribir uno ahí inventa una magnitud. El texto dice «n/d» y sigue.
    """
    return None if abs(base) < 0.005 else (act - base) / base


def signo(v: float) -> str:
    """«above» / «below», que es como lo lee el dueño."""
    return "above" if v >= 0 else "below"


# ═══════════════════════════ Piezas de Word ═══════════════════════════════════

def _margenes(sec) -> None:
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)


def _pie(sec, propiedad: str) -> None:
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(propiedad + "   ")
    r.font.size = Pt(8)
    r.font.color.rgb = GRIS
    _campo(p, "PAGE")
    r2 = p.add_run(" | P a g e")
    r2.font.size = Pt(8)
    r2.font.color.rgb = GRIS


def _campo(parrafo, instruccion: str) -> None:
    """Un campo de Word (el número de página se numera solo al imprimir)."""
    ini = OxmlElement("w:fldChar")
    ini.set(qn("w:fldCharType"), "begin")
    txt = OxmlElement("w:instrText")
    txt.set(qn("xml:space"), "preserve")
    txt.text = f" {instruccion} "
    fin = OxmlElement("w:fldChar")
    fin.set(qn("w:fldCharType"), "end")
    r = parrafo.add_run()._r
    for e in (ini, txt, fin):
        r.append(e)


def _h(doc, texto: str, nivel: int = 1, color=VERDE):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if nivel == 1 else 10)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(14 if nivel == 1 else 12 if nivel == 2 else 11)
    r.font.color.rgb = color
    return p


def _p(doc, partes, justificar: bool = True):
    """Un párrafo. `partes` es texto, o una lista de (texto, negrita)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.15
    if justificar:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for trozo in ([partes] if isinstance(partes, str) else partes):
        txt, negrita = (trozo, False) if isinstance(trozo, str) else trozo
        r = p.add_run(txt)
        r.bold = negrita
        r.font.size = Pt(11)
        r.font.color.rgb = NEGRO
    return p


def _sombra(celda, hexcolor: str) -> None:
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hexcolor)
    celda._tc.get_or_add_tcPr().append(el)


def _tabla(doc, encabezados, filas, anchos=None, resaltar=()):
    """Un cuadro. `filas` = lista de listas de texto ya formateado.

    `resaltar` son los índices de fila que van en negrita con fondo —los
    totales—. Los negativos salen en rojo, que es como se leen en el PDF.
    """
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"
    for i, h in enumerate(encabezados):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if i:
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _sombra(c, "2A4A33")
    for n, fila in enumerate(filas):
        celdas = t.add_row().cells
        for i, v in enumerate(fila):
            celdas[i].text = ""
            p = celdas[i].paragraphs[0]
            if i:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r = p.add_run(str(v))
            r.font.size = Pt(8.5)
            r.bold = n in resaltar
            if str(v).startswith("-") or str(v).startswith("($"):
                r.font.color.rgb = ROJO
            if n in resaltar:
                _sombra(celdas[i], "EDF1F5")
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Cm(w)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    return t


def _pendiente(doc, titulo: str, que_falta: str) -> None:
    """Un recuadro que PIDE el dato, donde el sistema no lo tiene.

    ⚠️ Esto es lo contrario de dejar la sección afuera y también de rellenarla.
    Una sección ausente no se nota; una inventada se lee igual de bien que una
    cierta. Un recuadro que dice qué falta se ve, y se completa.
    """
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    c.text = ""
    p = c.paragraphs[0]
    r = p.add_run(titulo + " — ")
    r.bold = True
    r.font.size = Pt(9.5)
    r2 = p.add_run(que_falta)
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = GRIS
    _sombra(c, "FDF6E3")
    doc.add_paragraph().paragraph_format.space_after = Pt(8)


# ═══════════════════════ La lectura de los cortes ═════════════════════════════

def linea(col: dict, code: str) -> float:
    """Un renglón del P&L de un corte. Cero si la versión no lo tiene."""
    for ln in col.get("lines", []):
        if ln["line_code"] == code:
            return float(ln["amount_usd"])
    return 0.0


def kpi(col: dict, nombre: str) -> float:
    return float((col.get("kpis") or {}).get(nombre) or 0.0)


#: Los renglones del cuadro, con el rótulo del owner. El orden es el del PDF.
CASCADA = [
    ("TOTAL REVENUES", "TOTAL_REVENUES", True),
    ("Total Operating expenses", "TOTAL_OPEXP", False),
    ("OPERATING PROFIT", "TOTAL_OP_PROFIT", True),
    ("TOTAL OVERHEAD EXPENSES", "TOTAL_OVERHEAD", False),
    ("TOTAL GROSS OPERATING PROFIT", "GOP", True),
    ("TOTAL NON OP EXPENSES", "TOTAL_NON_OP", False),
    ("EBITDA BEFORE CAPITAL", "EBITDA_BEFORE", True),
    ("EBITDA AFTER CAPITAL", "EBITDA_AFTER", False),
    ("EARNINGS BEFORE INCOME TAXES", "EBT", False),
    ("NET PROFIT", "NET_PROFIT", True),
]


def _cuadro_corte(doc, titulo: str, act: dict, bud: dict, fcs: dict | None,
                  rot_a: str, rot_b: str, rot_c: str) -> None:
    """El cuadro de un corte: KPIs arriba y la cascada abajo, con su variación."""
    _p(doc, [(titulo, True)], justificar=False)
    filas = [
        ["Total available Rooms", f"{kpi(act, 'rooms_available'):,.0f}",
         f"{kpi(bud, 'rooms_available'):,.0f}", "",
         f"{kpi(fcs, 'rooms_available'):,.0f}" if fcs else ""],
        ["Total Rooms Occupied", f"{kpi(act, 'rooms_occupied'):,.0f}",
         f"{kpi(bud, 'rooms_occupied'):,.0f}",
         f"{kpi(act, 'rooms_occupied') - kpi(bud, 'rooms_occupied'):,.0f}",
         f"{kpi(fcs, 'rooms_occupied'):,.0f}" if fcs else ""],
        ["Total Guests", f"{kpi(act, 'guests'):,.0f}", f"{kpi(bud, 'guests'):,.0f}",
         f"{kpi(act, 'guests') - kpi(bud, 'guests'):,.0f}",
         f"{kpi(fcs, 'guests'):,.0f}" if fcs else ""],
        ["% Occupancy", pct(kpi(act, "occupancy_pct")), pct(kpi(bud, "occupancy_pct")),
         f"{(kpi(act, 'occupancy_pct') - kpi(bud, 'occupancy_pct')) * 100:,.2f}pp",
         pct(kpi(fcs, "occupancy_pct")) if fcs else ""],
        ["Average Daily Room Only", usd(kpi(act, "adr")), usd(kpi(bud, "adr")),
         usd(kpi(act, "adr") - kpi(bud, "adr")),
         usd(kpi(fcs, "adr")) if fcs else ""],
        ["Total RevPAR", usd(kpi(act, "revpar")), usd(kpi(bud, "revpar")),
         usd(kpi(act, "revpar") - kpi(bud, "revpar")),
         usd(kpi(fcs, "revpar")) if fcs else ""],
    ]
    for rotulo, code, fuerte in CASCADA:
        a, b = linea(act, code), linea(bud, code)
        vp = var_pct(a, b)
        filas.append([rotulo, usd(a), usd(b), usd(a - b) + (
            f"  ({vp * 100:,.1f}%)" if vp is not None else ""),
            usd(linea(fcs, code)) if fcs else ""])
    _tabla(doc, ["ACCOUNT DESCRIPTION", rot_a, rot_b, "Variance", rot_c],
           filas, anchos=[5.2, 2.9, 2.9, 3.2, 2.9],
           resaltar={i for i, (_, _, f) in enumerate(CASCADA, start=6) if f})


#: El flow-through: dónde se quedó cada dólar de más que entró.
FLOW = [
    ("Revenue", "TOTAL_REVENUES", "Topline vs Budget"),
    ("Payroll (Overtime + FX + Commissions)", "TOTAL_PAYROLL",
     "Operational scaling pressure + FX"),
    ("Operating Expenses", "TOTAL_OPEX_ONLY", "Operating spend vs Budget"),
    ("Cost of Sales", "TOTAL_COST", "Higher guest activity and service delivery"),
    ("Property / Capital", "TOTAL_PROPERTY", "Fees + capex decisions"),
]


def _flow_through(doc, titulo: str, act: dict, bud: dict, totales) -> None:
    """El cuadro de flow-through: la variación de cada bloque de costo.

    ⚠️ El gasto se muestra con el signo del EFECTO sobre la utilidad, no con el
    de la cuenta. Gastar de más es negativo aunque el gasto haya subido: un
    cuadro donde «+9.161» significa «me fue peor» se lee al revés.
    """
    _h(doc, titulo, nivel=3, color=NEGRO)
    filas = []
    for rotulo, clave, nota in FLOW:
        a, b = totales(act, clave), totales(bud, clave)
        efecto = (a - b) if clave == "TOTAL_REVENUES" else -(a - b)
        filas.append([rotulo, usd(efecto) if efecto >= 0 else f"({usd(abs(efecto))})",
                      nota])
    for rotulo, code, nota in (("Net Profit", "NET_PROFIT", "Flow-through neto"),
                               ("EBITDA Before Capital", "EBITDA_BEFORE",
                                "Efecto sobre EBITDA")):
        d = linea(act, code) - linea(bud, code)
        filas.append([rotulo, usd(d) if d >= 0 else f"({usd(abs(d))})", nota])
    _tabla(doc, ["Concept", "Variance ($)", "Notes"], filas,
           anchos=[6.5, 3.4, 7.2], resaltar={len(filas) - 2, len(filas) - 1})


# ═════════════════════════════ El documento ═══════════════════════════════════

def build_executive_summary(datos: dict) -> bytes:
    """Arma el .docx. `datos` lo prepara `export_api`, leyendo del motor."""
    propiedad = datos["propiedad"]
    mes = int(datos["mes"])
    anio = int(datos["anio"])
    mes_ing = MESES[mes - 1]

    act, bud, fcs = datos["actual"], datos["budget"], datos.get("forecast")
    rot = datos["rotulos"]

    doc = Document()
    est = doc.styles["Normal"]
    est.font.name = "Arial"
    est.font.size = Pt(11)
    _margenes(doc.sections[0])
    _pie(doc.sections[0], propiedad)

    # ── Portada ──────────────────────────────────────────────────────────────
    for _ in range(8):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("MONTHLY EXECUTIVE SUMMARY")
    r.bold = True
    r.font.size = Pt(17)
    r.font.color.rgb = ORO
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{mes_ing.upper()} {anio}")
    r.bold = True
    r.font.size = Pt(40)
    r.font.color.rgb = VERDE
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(propiedad)
    r.font.size = Pt(13)
    r.font.color.rgb = NEGRO
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Generado por FinPlan el {date.today():%d/%m/%Y} · "
                  f"{rot['actual']} vs {rot['budget']}"
                  + (f" vs {rot['forecast']}" if fcs else ""))
    r.font.size = Pt(8.5)
    r.font.color.rgb = GRIS
    doc.add_page_break()

    # ── Introducción ─────────────────────────────────────────────────────────
    _h(doc, "INTRODUCTION", nivel=1, color=NEGRO)
    _p(doc, "This report presents a comprehensive analysis of the hotel's "
            "financial and operational performance across three key perspectives:")
    _p(doc, [(f"{mes_ing} {anio} (Monthly Performance vs Budget)", True),
             ", providing a detailed view of execution for the current month."])
    _p(doc, [(f"Year-to-Date {mes_ing} {anio} (Cumulative Performance vs Budget)", True),
             ", highlighting overall trends and performance."])
    _p(doc, [(f"Full Year Forecast {anio} (Projected Performance vs Budget)", True),
             ", offering a forward-looking assessment of expected results and key "
             "risks for the remainder of the year."])
    _p(doc, "The objective of this analysis is to evaluate not only the level of "
            "revenue and profitability achieved, but also to understand the "
            "underlying drivers of performance, including volume, rate, cost "
            "structure, and operational dynamics for the full year.")
    doc.add_page_break()

    _h(doc, f"Executive Summary — Financial & Operational Results "
            f"YTD {mes_ing} {anio}", nivel=1)

    # ── 1.1 / 1.2 / 1.3 ──────────────────────────────────────────────────────
    cortes = [
        ("1.1", f"{mes_ing} {anio} (Monthly Performance vs Budget)", "month",
         f"{mes_ing} Total Revenue", mes_ing),
        ("1.2", f"YTD {mes_ing} {anio} (Cumulative Performance vs Budget)", "ytd",
         f"YTD {mes_ing} Total Revenue", f"YTD {mes_ing}"),
        ("1.3", f"Full Year Forecast {anio} vs Budget", "full",
         "Full-Year Revenue", "Full Year"),
    ]
    for num, titulo, corte, sujeto, rotulo_corte in cortes:
        a = act[corte]
        b = bud[corte]
        f = fcs[corte] if fcs else None
        # ⚠️ En el año completo el Actual son los meses cargados: quien contesta
        # «cómo cierra el año» es el Forecast. Comparar el Actual contra doce
        # meses de presupuesto daría un derrumbe que sólo dice que el año no
        # terminó.
        principal = f if (corte == "full" and f) else a
        rot_principal = rot["forecast"] if (corte == "full" and f) else rot["actual"]

        _h(doc, f"{num} {titulo}", nivel=2)
        rev, revb = linea(principal, "TOTAL_REVENUES"), linea(b, "TOTAL_REVENUES")
        vp = var_pct(rev, revb)
        occ_a, occ_b = kpi(principal, "occupancy_pct"), kpi(b, "occupancy_pct")
        adr_a, adr_b = kpi(principal, "adr"), kpi(b, "adr")
        noc_a, noc_b = kpi(principal, "rooms_occupied"), kpi(b, "rooms_occupied")
        gasto_a = sum(datos["totales"](principal, c) for _, c, _ in FLOW[1:])
        gasto_b = sum(datos["totales"](b, c) for _, c, _ in FLOW[1:])
        vg = var_pct(gasto_a, gasto_b)
        eb_a, eb_b = linea(principal, "EBITDA_BEFORE"), linea(b, "EBITDA_BEFORE")
        np_a, np_b = linea(principal, "NET_PROFIT"), linea(b, "NET_PROFIT")

        _p(doc, [
            (f"{sujeto} reached {k(rev)}, {k(abs(rev - revb))} "
             f"{signo(rev - revb)} Budget", True),
            (f" ({vp * 100:+,.1f}%)" if vp is not None else "", True),
            f", supported by occupancy of {pct(occ_a)} vs {pct(occ_b)} Budget, "
            f"with {noc_a:,.0f} occupied rooms versus {noc_b:,.0f} budgeted, "
            f"while ADR closed at ",
            (f"{usd(adr_a)} vs {usd(adr_b)}", True),
            ". Total Operating and Property Expenses were ",
            (f"{k(abs(gasto_a - gasto_b))} {signo(gasto_a - gasto_b)} Budget"
             + (f" ({vg * 100:+,.1f}%)" if vg is not None else ""), True),
            f". Consequently, EBITDA Before Capital closed at {k(eb_a)} versus "
            f"{k(eb_b)} Budget, while Net Profit was {k(np_a)} versus "
            f"{k(np_b)} Budget.",
        ])

        # El contraste contra el Forecast, sólo donde significa algo: en el full
        # year el Forecast YA es la columna principal.
        if f is not None and corte != "full":
            rf = linea(f, "TOTAL_REVENUES")
            ef = linea(f, "EBITDA_BEFORE")
            _h(doc, "Performance vs Forecast", nivel=3, color=NEGRO)
            _p(doc, f"Compared with the Forecast, Total Revenue was "
                    f"{k(abs(rev - rf))} {signo(rev - rf)} the revised outlook, "
                    f"while EBITDA Before Capital closed {k(abs(eb_a - ef))} "
                    f"{signo(eb_a - ef)} Forecast.")

        _cuadro_corte(doc, f"{rotulo_corte} {anio} — Actual vs Budget vs Forecast",
                      principal, b, f, rot_principal, rot["budget"],
                      rot.get("forecast", ""))
        _flow_through(doc, f"{rotulo_corte} {anio} – Flow Through Analysis "
                           f"(vs Budget)", principal, b, datos["totales"])
        doc.add_page_break()

    # ── Sección 2 — Drivers ──────────────────────────────────────────────────
    _h(doc, "SECTION 2 — Performance Drivers", nivel=1)
    ytd_a, ytd_b = act["ytd"], bud["ytd"]
    _h(doc, "2.1 Volume (Demand)", nivel=2)
    d_noc = kpi(ytd_a, "rooms_occupied") - kpi(ytd_b, "rooms_occupied")
    d_pax = kpi(ytd_a, "guests") - kpi(ytd_b, "guests")
    _p(doc, f"Year-to-date the hotel sold {kpi(ytd_a, 'rooms_occupied'):,.0f} rooms "
            f"versus {kpi(ytd_b, 'rooms_occupied'):,.0f} budgeted "
            f"({d_noc:+,.0f}), with {kpi(ytd_a, 'guests'):,.0f} guests versus "
            f"{kpi(ytd_b, 'guests'):,.0f} ({d_pax:+,.0f}). Occupancy closed at "
            f"{pct(kpi(ytd_a, 'occupancy_pct'))} against "
            f"{pct(kpi(ytd_b, 'occupancy_pct'))} Budget.")

    _h(doc, "2.2 Rate (Quality of Revenue)", nivel=2)
    _p(doc, f"Cumulative ADR stands at {usd(kpi(ytd_a, 'adr'))} versus "
            f"{usd(kpi(ytd_b, 'adr'))} Budget, and Total RevPAR at "
            f"{usd(kpi(ytd_a, 'revpar'))} versus {usd(kpi(ytd_b, 'revpar'))}. "
            f"RevPAR is measured on TOTAL revenue per available room, so it "
            f"reflects the whole property and not only the room night.")
    if datos.get("adr_por_mes"):
        _tabla(doc, ["Month", "ADR", "Occupancy", "Rooms occupied"],
               datos["adr_por_mes"], anchos=[4.0, 4.0, 4.0, 4.0])

    # ── 2.3 Revenue mix ──────────────────────────────────────────────────────
    _h(doc, "2.3 Revenue Mix", nivel=2)
    mix = datos.get("mix") or []
    if mix:
        _p(doc, "Departmental contribution year-to-date, against Budget:")
        _tabla(doc, ["Department", "YTD Actual", "YTD Budget", "Var $", "Var %"],
               mix, anchos=[5.6, 3.2, 3.2, 3.0, 2.2])
    else:
        _pendiente(doc, "Revenue Mix",
                   "el detalle por departamento no vino en esta corrida.")

    doc.add_page_break()

    # ── Sección 3 — lo que la contabilidad no sabe ───────────────────────────
    _h(doc, "SECTION 3 — Commercial Strategy Snapshot", nivel=1)
    _pendiente(doc, "Actividad comercial del mes",
               "esta sección no sale de la contabilidad: se redacta con el "
               "equipo comercial (actividades, agencias, medios, segmentos de "
               "alto valor y foco de gestión). El sistema no la inventa.")
    _pendiente(doc, "Market Intelligence — mix por país",
               "requiere el detalle de noches por país del PMS. Si se cargó la "
               "segmentación del mes en Cierre de Mes · Estadística de "
               "habitaciones, el dato está ahí y se puede pegar acá.")

    # ── Sección 4 — positivos y negativos, de los propios números ────────────
    _h(doc, f"SECTION 4 — Overall Positives and Negatives YTD {mes_ing} {anio}",
       nivel=1)
    _h(doc, "4.1 Overall Positive", nivel=2)
    if datos.get("positivos"):
        for titulo, texto in datos["positivos"]:
            _p(doc, [(titulo + ". ", True), texto])
    else:
        _p(doc, "No se identificaron variaciones favorables materiales en el "
                "acumulado.")
    _h(doc, "4.2 Overall Negative", nivel=2)
    if datos.get("negativos"):
        for titulo, texto in datos["negativos"]:
            _p(doc, [(titulo + ". ", True), texto])
    else:
        _p(doc, "No se identificaron variaciones desfavorables materiales en el "
                "acumulado.")

    # ── Sección 4.3 — tipo de cambio ─────────────────────────────────────────
    _h(doc, "4.3 Exchange Rate Trend — Potential Risk", nivel=2)
    if datos.get("fx"):
        _p(doc, datos["fx"])
    else:
        _pendiente(doc, "Exposición cambiaria",
                   "requiere el tipo de cambio presupuestado contra el real del "
                   "período y la proporción de costos pagados en colones. Se "
                   "carga en Master Data · Tipos de cambio.")

    # ── Cierre ───────────────────────────────────────────────────────────────
    doc.add_page_break()
    _h(doc, "Nota metodológica", nivel=2, color=GRIS)
    _p(doc, "Todas las cifras de este informe salen del mismo motor que alimenta "
            "el P&L del cierre: no hay una segunda aritmética. El corte del año "
            "completo compara el Forecast contra el Budget —no el Actual—, "
            "porque el Actual del año son los meses efectivamente cargados y "
            "restarle doce meses de presupuesto mostraría una caída que sólo "
            "significa que el año no ha terminado. La ocupación, el ADR y el "
            "RevPAR de un período se rederivan sobre los totales de ese período; "
            "no son promedios de los meses.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
