# -*- coding: utf-8 -*-
"""Amplía el reporte a dueños de Amarena: contexto al inicio, análisis al final.

Owner, 2026-11-13: *«necesito el mismo excel que adopte los cambios… y que
automatices todo para usarlo»* · *«no quites nada de lo que hay en el tab de
presentación, solo amplía y mejora»* · *«cada nota en la presentación debe ser
concluyente y esclarecedora»*.

## Qué hace

Toma el Master File y le agrega, **sin tocar una sola fila de lo que ya está**:

* una pestaña `AM11 Contexto` con los indicadores externos —turismo mundial,
  Costa Rica, macro 2027— y la sensibilidad de tipo de cambio;
* seis páginas nuevas en `Reporte`: tres de contexto (que van adelante en la
  lectura, aunque se escriban al final del archivo) y tres de productividad,
  posiciones y riesgos.

## Por qué todo son FÓRMULAS y no números

El reporte actual ya está hecho así: sus notas son cadenas armadas con `FIXED()`
desde `'AM02 Resumen FY'`, y por eso se reescriben solas al refrescar. Si las
páginas nuevas trajeran números pegados, **el día que alguien actualice los
datos la mitad del reporte diría una cosa y la otra mitad otra**, sin que nada
avise. Eso es exactamente el modo de falla que este proyecto persigue.

La única excepción son los indicadores externos (llegadas del ICT, inflación
del BCCR): esos no salen de FinPlan y van como **entradas editables** en AM11,
con su fuente al lado. Las páginas los leen de ahí, así que actualizarlos es
escribir en una celda, no editar el reporte.

## Lo que NO se toca

Las filas 1 a 512 de `Reporte` quedan intactas salvo el pie de página, que
decía «de 9» y ahora dice «de 15»: el reporte tiene seis páginas más y el pie
mentiría. Es la única edición sobre lo existente, y es para que siga siendo
cierto.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ── La paleta del reporte, leída del archivo original ────────────────────────
MARRON = "FF4A3B2C"      # titulares y barras
ORO = "FFC8A97E"         # acento
CREMA = "FFF6F0E6"       # fondo de las tarjetas
APAGADO = "FF7A6E62"     # texto secundario
CLARO = "FFEFE6D6"       # texto sobre marrón
TEXTO = "FF222222"
ALERTA = "FF9A3412"
BIEN = "FF4A7A3C"

DISPLAY = "Georgia"
CUERPO = "Calibri"

#: Alto de una página del reporte, en filas. Las nueve actuales empiezan en 1,
#: 58, 115… cada 57: respetarlo es lo que hace que la impresión siga cuadrando.
PASO = 57

PIE = ("Amarena Hotel & Madresal Beach Club · Místico, Playa Hermosa, Costa Rica")


def _f(sz=11, b=False, color=TEXTO, name=CUERPO):
    return Font(name=name, size=sz, bold=b, color=color)


def _fill(c):
    return PatternFill("solid", fgColor=c)


#: Una referencia a OTRA hoja dentro de una fórmula: `'AM02 Resumen FY'!C19`.
_REF_HOJA = re.compile(r"('[^']+'!)(\$?)([A-Z]{1,3})(\$?)(\d+)")


def absolutizar(formula: str) -> str:
    """`'AM02 Resumen FY'!C19` → `'AM02 Resumen FY'!$C$19`.

    ⚠️ **Sin esto las páginas se rompen al pegarlas.** Estas fórmulas se
    escriben en un libro aparte y después se copian a la fila 514 del reporte.
    Excel trata una referencia relativa como un desplazamiento, así que al
    bajar 511 filas convierte `D15` en `D526` — y como esa celda no existe,
    queda `#REF!`. Pasó: 97 celdas de golpe, y lo peor es que el libro abría
    bien y los errores estaban en el medio del documento.

    Una referencia absoluta apunta al mismo lugar se pegue donde se pegue, que
    es justo lo que hace falta cuando el destino final no es donde se escribió.
    """
    if not isinstance(formula, str) or not formula.startswith("="):
        return formula
    return _REF_HOJA.sub(lambda m: f"{m.group(1)}${m.group(3)}${m.group(5)}",
                         formula)


def celda(ws, ref, valor, *, sz=11, b=False, color=TEXTO, name=CUERPO,
          fondo=None, al=None, wrap=False, fmt=None):
    c = ws[ref]
    c.value = absolutizar(valor)
    c.font = _f(sz, b, color, name)
    if fondo:
        c.fill = _fill(fondo)
    if al or wrap:
        c.alignment = Alignment(horizontal=al, vertical="top", wrap_text=wrap)
    if fmt:
        c.number_format = fmt
    return c


def cabecera_pagina(ws, r0, titulo, bajada, pagina, total):
    """La banda marrón de arriba y el pie, iguales a las páginas existentes."""
    celda(ws, f"B{r0}", "BORRADOR · PRELIMINAR Y NO AUDITADO",
          sz=8, b=True, color=APAGADO)
    for col in "BCDEFGHIJKLM":
        ws[f"{col}{r0+1}"].fill = _fill(MARRON)
    celda(ws, f"B{r0+1}",
          "AMARENA HOTEL & MADRESAL BEACH CLUB · Reporte a dueños F26 vs B27",
          sz=8, b=True, color=ORO, fondo=MARRON)
    celda(ws, f"B{r0+2}", titulo, sz=20, b=True, color=MARRON, name=DISPLAY)
    celda(ws, f"B{r0+3}", bajada, sz=9, color=APAGADO)
    celda(ws, f"B{r0+PASO-2}", PIE, sz=8, color=APAGADO)
    celda(ws, f"J{r0+PASO-2}",
          f"Reporte a dueños F26 vs B27 · Página {pagina} de {total}",
          sz=8, color=APAGADO, al="right")


def tarjeta(ws, col, r, rotulo, formula, nota, *, fmt=None, color=MARRON):
    """Una de las tarjetas crema con número grande, como en el dashboard."""
    for dc in range(3):
        for dr in range(4):
            ws.cell(row=r + dr, column=col + dc).fill = _fill(CREMA)
    celda(ws, ws.cell(row=r, column=col).coordinate, rotulo,
          sz=8, b=True, color=APAGADO, fondo=CREMA, al="center")
    celda(ws, ws.cell(row=r + 1, column=col).coordinate, formula,
          sz=16, b=True, color=color, name=DISPLAY, fondo=CREMA,
          al="center", fmt=fmt)
    celda(ws, ws.cell(row=r + 3, column=col).coordinate, nota,
          sz=8, color=APAGADO, fondo=CREMA, al="center", wrap=True)


def bloque_nota(ws, r, texto, *, acento=MARRON):
    """Una conclusión. Ocupa el ancho útil y se lee como una afirmación.

    ⚠️ `texto` casi siempre es una FÓRMULA: así la conclusión se reescribe sola
    cuando cambian los datos. Una nota con el número pegado adentro envejece sin
    avisar, y en un reporte a dueños eso se descubre en la reunión.
    """
    ws[f"B{r}"].fill = _fill(ORO)
    celda(ws, f"C{r}", texto, sz=9, color=TEXTO, wrap=True)
    ws.merge_cells(f"C{r}:M{r}")
    ws.row_dimensions[r].height = 42


# ─────────────────── AM11 · el contexto externo, editable ───────────────────

#: Indicadores que NO salen de FinPlan. Van como entrada editable con su fuente
#: al lado: actualizarlos es escribir en una celda, no editar seis páginas.
#: (fila, rótulo, valor, formato, fuente)
CONTEXTO = [
    ("T", "TURISMO INTERNACIONAL", None, None, ""),
    ("d", "Llegadas internacionales 2025 (millones)", 1520, "#,##0",
     "UN Tourism · World Tourism Barometer"),
    ("d", "Crecimiento mundial 2025", 0.04, "0.0%", "UN Tourism"),
    ("d", "Crecimiento mundial I sem. 2026", 0.004, "0.0%", "UN Tourism"),
    ("d", "Previsión 2026 (rango bajo)", 0.01, "0.0%", "UN Tourism · revisada"),
    ("d", "Previsión 2026 (rango alto)", 0.02, "0.0%", "UN Tourism · revisada"),
    ("d", "Previsión llegadas 2027", 0.08, "0.0%",
     "Tourism Economics · consultora privada, NO oficial"),
    ("d", "Previsión larga distancia 2027", 0.11, "0.0%", "Tourism Economics"),
    ("d", "Medio Oriente I sem. 2026", -0.22, "0.0%", "UN Tourism"),

    ("T", "COSTA RICA · LLEGADAS (ICT)", None, None, ""),
    ("d", "Llegadas ene–sep 2026", 2127506, "#,##0", "ICT vía El Financiero"),
    ("d", "Variación ene–sep 2026", 0.054, "0.0%", "ICT"),
    ("d", "Llegadas ene–jul 2026", 2001660, "#,##0", "ICT vía La Nación"),
    ("d", "Variación ene–jul 2026", 0.064, "0.0%", "ICT"),
    ("d", "Peso de Estados Unidos", 0.57, "0.0%", "ICT · ene–jul"),
    ("d", "Canadá · I semestre", 0.265, "0.0%", "ICT"),
    ("d", "Europa · ene–sep", 0.084, "0.0%", "ICT"),
    ("d", "Caídas interanuales aéreas en 2026", 3, "#,##0",
     "ICT · la de setiembre fue la tercera"),

    ("T", "COSTA RICA · MACRO 2027", None, None, ""),
    ("d", "Inflación proyectada 2027", 0.033, "0.0%", "BCCR · IPM oct-2026"),
    ("d", "Inflación II semestre 2027", 0.027, "0.0%", "BCCR"),
    ("d", "Meta de inflación", 0.03, "0.0%", "BCCR · ±1 punto"),
    ("d", "Crecimiento PIB 2027–2028", 0.035, "0.0%", "BCCR"),
    ("d", "Tasa de política monetaria", 0.03, "0.0%", "BCCR · set-2026"),
    ("d", "Tipo de cambio Monex 30-oct-2026", 452.08, "#,##0.00",
     "BCCR · el colón sigue apreciándose"),
    ("d", "Alza salario mínimo privado 2027", 0.017, "0.0%",
     "Consejo Nacional de Salarios · 28-oct-2026"),

    ("T", "SUPUESTO DEL BUDGET", None, None, ""),
    ("d", "Tipo de cambio del Budget 2027", 460.00, "#,##0.00",
     "FinPlan · exchange_rates, fijo los 12 meses"),
    ("d", "Puestos en colones", 38, "#,##0", "FinPlan · los 38 de 38"),
]

#: Los escenarios de la tabla de sensibilidad. El del budget va marcado.
TC_ESCENARIOS = [
    (480.0, "El colón se deprecia"),
    (470.0, "Depreciación leve"),
    (460.0, "SUPUESTO DEL BUDGET"),
    (452.0, "Mercado hoy · BCCR 30-oct"),
    (445.0, "Apreciación leve"),
    (440.0, "Apreciación moderada"),
    (430.0, "Apreciación fuerte"),
]


def hoja_contexto(wb):
    """`AM11 Contexto` — lo externo como entrada, la sensibilidad como fórmula."""
    if "AM11 Contexto" in wb.sheetnames:
        del wb["AM11 Contexto"]
    ws = wb.create_sheet("AM11 Contexto")
    ws.sheet_view.showGridLines = False
    for col, an in (("A", 2.0), ("B", 44.0), ("C", 15.0), ("D", 54.0),
                    ("E", 15.0), ("F", 15.0), ("G", 15.0)):
        ws.column_dimensions[col].width = an

    celda(ws, "B1", "AM11 · Contexto externo y sensibilidad de tipo de cambio",
          sz=14, b=True, color=MARRON, name=DISPLAY)
    celda(ws, "B2",
          "Lo que NO sale de FinPlan. Editá la columna C y las páginas 1 a 3 "
          "del reporte se actualizan solas. Cada dato lleva su fuente.",
          sz=9, color=APAGADO)

    r = 4
    ref = {}
    for tipo, rotulo, valor, fmt, fuente in CONTEXTO:
        if tipo == "T":
            r += 1
            celda(ws, f"B{r}", rotulo, sz=9, b=True, color=ORO, fondo=MARRON)
            for col in "CD":
                ws[f"{col}{r}"].fill = _fill(MARRON)
            r += 1
            continue
        celda(ws, f"B{r}", rotulo, sz=10)
        celda(ws, f"C{r}", valor, sz=10, b=True, color=MARRON, fmt=fmt, al="right")
        celda(ws, f"D{r}", fuente, sz=8.5, color=APAGADO)
        ref[rotulo] = f"'AM11 Contexto'!C{r}"
        r += 1

    tc_budget = ref["Tipo de cambio del Budget 2027"]
    tc_mercado = ref["Tipo de cambio Monex 30-oct-2026"]

    # ── La sensibilidad. Todo fórmula contra la planilla real de AM10. ──────
    r += 1
    fila_sens = r
    celda(ws, f"B{r}", "SENSIBILIDAD · PLANILLA SEGÚN TIPO DE CAMBIO",
          sz=9, b=True, color=ORO, fondo=MARRON)
    for col in "CDEF":
        ws[f"{col}{r}"].fill = _fill(MARRON)
    r += 1
    celda(ws, f"B{r}",
          "Los 38 puestos están en colones. La planilla en dólares es "
          "inversamente proporcional al tipo de cambio.", sz=8.5, color=APAGADO)
    r += 1
    for col, t in (("B", "Tipo de cambio ₡/$"), ("C", "Planilla B27 $"),
                   ("D", "Diferencia vs Budget"), ("E", "% del déficit EBITDA"),
                   ("F", "Escenario")):
        celda(ws, f"{col}{r}", t, sz=8, b=True, color=APAGADO, fondo=CREMA)
    r += 1
    primera = r
    PLANILLA = "'AM10 Posiciones y FTE'!D15"
    EBITDA = "'AM02 Resumen FY'!C29"
    for tc, nombre in TC_ESCENARIOS:
        esb = abs(tc - 460.0) < 0.01
        celda(ws, f"B{r}", tc, sz=10, b=esb, fmt="#,##0.00", al="right",
              color=MARRON if esb else TEXTO)
        celda(ws, f"C{r}", f"={PLANILLA}*{tc_budget}/B{r}", sz=10, b=esb,
              fmt="#,##0", al="right")
        celda(ws, f"D{r}", f"=C{r}-{PLANILLA}", sz=10, fmt="+#,##0;-#,##0;—",
              al="right", color=ALERTA if tc < 460 else BIEN)
        celda(ws, f"E{r}", f"=IF({EBITDA}>=0,\"\",D{r}/-{EBITDA})", sz=10,
              fmt="0.0%;-0.0%;—", al="right", color=APAGADO)
        celda(ws, f"F{r}", nombre, sz=9, b=esb,
              color=MARRON if esb else APAGADO)
        r += 1
    ultima = r - 1

    r += 1
    celda(ws, f"B{r}", "CONCLUSIÓN (se reescribe sola)",
          sz=9, b=True, color=MARRON)
    r += 1
    celda(ws, f"B{r}",
          f'="Los {{}} puestos de Amarena están en colones y el Budget los '
          f'convierte a ₡"&FIXED({tc_budget},2)&" fijo los doce meses. '
          f'El mercado está en ₡"&FIXED({tc_mercado},2)&", y el BCCR advierte '
          f'que el colón sigue apreciándose. Cerrar sólo esa brecha cuesta $"'
          f'&FIXED({PLANILLA}*{tc_budget}/{tc_mercado}-{PLANILLA},0)&" de '
          f'planilla adicional; una apreciación a ₡430 cuesta $"'
          f'&FIXED({PLANILLA}*{tc_budget}/430-{PLANILLA},0)&", que es el "'
          f'&FIXED(({PLANILLA}*{tc_budget}/430-{PLANILLA})/-{EBITDA}*100,0)'
          f'&"% del déficit de EBITDA, por una variable que no depende de la '
          f'gestión."'.replace("{}", "\"&FIXED(" + ref["Puestos en colones"] + ",0)&\""),
          sz=9, wrap=True)
    ws.merge_cells(f"B{r}:F{r+2}")
    ws.row_dimensions[r].height = 46
    return ref, fila_sens, primera, ultima
