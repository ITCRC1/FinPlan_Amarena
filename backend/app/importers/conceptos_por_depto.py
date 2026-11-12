# -*- coding: utf-8 -*-
"""Leer de vuelta el reporte de conceptos por departamento.

Owner, 2026-11-11: *«tenemos que hacer que este archivo llegue a budget 2027 y
que haga prorrateo con las posiciones»*.

## Lo que este archivo era, y por qué ahora vuelve

`export/conceptos_por_depto_excel.py` lo escribió como **reporte**: su propia
documentación dice «⚠️ Este archivo NO se sube». Y tenía razón para su momento:
el libro muestra los conceptos ya calculados, con una columna que explica la
regla de cada uno, y eso no es una plantilla de carga.

Pero resultó ser la vista con la que la propiedad **quiere trabajar** —todos
los conceptos de un departamento, los doce meses, de un vistazo— así que el
camino de vuelta se abre acá, en un lector aparte, sin tocar el exportador.

## El problema que resuelve el prorrateo

El archivo agrega por DEPARTAMENTO. FinPlan guarda por POSICIÓN
(`payroll_concept_entries` tiene una fila por puesto × mes). Para devolver un
número hay que repartirlo, y se reparte **a prorrata del salario** de cada
puesto en ese mes.

⚠️ **Eso redistribuye lo que ya estaba.** Si un feriado trabajado estaba
cargado entero a la persona que lo trabajó, al volver queda repartido entre
todo el departamento. El total del depto no se mueve y el P&L tampoco, pero la
asignación por persona se pierde. El owner lo eligió así el 2026-11-11,
sabiéndolo.

## Tres filas que NUNCA entran

| fila | por qué |
|---|---|
| `6000` | sale de salario × FTE / TC: escribirlo pelearía con las posiciones |
| `6020` | `BASE × 26.83%` — lo recalcula el motor |
| `6021` | `BASE / 12` — igual |

Más `BASE` y `TOTAL`, que son subtotales. Guardar un resultado donde va un
insumo hace que el siguiente Recalcular lo cambie **sin que nadie vea por
qué** — el modo de falla que este proyecto persigue.
"""
from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

import openpyxl

#: Los 14 conceptos que SÍ se digitan, y su campo en el modelo.
#: Los seis del grupo BASE primero, después los ocho beneficios, en el orden
#: del reporte para que leer el archivo y leer esta tabla den lo mismo.
IMPORTABLES: dict[str, str] = {
    "6001": "c6001_overtime",
    "6002": "c6002_day_off",
    "6003": "c6003_working_holiday",
    "6010": "c6010_commissions",
    "6024": "c6024_vacations_taken",
    "6027": "c6027_incentive_bonus",
    "6004": "c6004_disabilities",
    "6022": "c6022_occ_hazard",
    "6023": "c6023_vacation_prov",
    "6025": "c6025_cafeteria",
    "6026": "c6026_severance",
    "6028": "c6028_housing",
    "6029": "c6029_transport",
    "6030": "c6030_other",
}

#: Lo que se saltea **a propósito**, para poder distinguirlo de una fila que no
#: se reconoció. Una cuenta que no esté ni acá ni en IMPORTABLES se informa.
CALCULADAS = {"6000", "6020", "6021"}

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
         "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _numero(v) -> Decimal | None:
    """`None` si la celda está vacía. Vacío NO es cero: un mes sin número es
    un mes del que el archivo no dice nada, y escribir un cero ahí borraría
    lo que haya cargado."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _depto_de(ws) -> str:
    """El código de departamento. Sale del título («0111 — Front Desk»), y si
    no, del nombre de la hoja, que lleva el mismo prefijo.

    No se usa el nombre de la hoja primero porque Excel lo recorta a 31
    caracteres y puede venir alterado; el título de la fila 1 no.
    """
    for fuente in (ws.cell(row=1, column=1).value, ws.title):
        m = re.match(r"\s*(\d{3,4})\b", str(fuente or ""))
        if m:
            return m.group(1)
    return ""


def leer_conceptos_por_depto(data: bytes) -> tuple[dict, list[str]]:
    """`({dept: {cuenta: {mes: monto}}}, avisos)`.

    Una hoja por departamento. Las columnas se ubican **por encabezado** y no
    por posición: buscarlas por número es lo que rompe un archivo en cuanto
    alguien inserta una columna, y la propiedad trabaja sobre estos libros.
    """
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    salida: dict[str, dict[str, dict[int, Decimal]]] = {}
    avisos: list[str] = []

    for ws in wb.worksheets:
        dept = _depto_de(ws)
        if not dept:
            avisos.append(f"La hoja «{ws.title}» no dice de qué departamento es; se omitió.")
            continue

        filas = list(ws.iter_rows(values_only=True))
        enc = col_mes = None
        for i, f in enumerate(filas[:12]):
            vals = [str(x).strip().upper() if x is not None else "" for x in f]
            if "CUENTA" in vals and "ENE" in vals:
                enc = i
                col_mes = {vals.index(m) : n for n, m in enumerate(MESES, start=1)
                           if m in vals}
                break
        if enc is None:
            avisos.append(f"La hoja «{ws.title}» no tiene la fila de encabezados "
                          "(la que dice «Cuenta» y «ENE»); se omitió.")
            continue

        por_cuenta: dict[str, dict[int, Decimal]] = {}
        for f in filas[enc + 1:]:
            cuenta = str(f[0] or "").strip()
            if not cuenta:
                continue
            # Las filas de POSICIÓN llevan guion («0111-04») y son el desglose
            # del S&W, no un concepto: su monto ya está en la fila 6000.
            if "-" in cuenta or cuenta in CALCULADAS:
                continue
            campo = IMPORTABLES.get(cuenta)
            if campo is None:
                avisos.append(f"{dept}: la cuenta «{cuenta}» no se reconoce; se omitió.")
                continue
            meses = {}
            for col, mes in col_mes.items():
                v = _numero(f[col]) if col < len(f) else None
                if v is not None:
                    meses[mes] = v
            if meses:
                por_cuenta[cuenta] = meses

        if por_cuenta:
            salida[dept] = por_cuenta
        else:
            avisos.append(f"{dept}: la hoja no trae ningún concepto con monto.")

    return salida, avisos


def repartir(total: Decimal, pesos: list[Decimal]) -> list[Decimal]:
    """Reparte `total` entre los puestos, a prorrata de `pesos` (el S&W).

    ⚠️ **La suma de las partes tiene que dar el total, exactamente.** Redondear
    cada parte por separado deja una diferencia de centavos que el P&L arrastra
    y que nadie puede explicar después. Lo que sobra va al puesto de mayor
    peso, que es donde menos se nota en términos relativos.

    ⚠️ Si NINGÚN puesto tiene salario ese mes —todo el departamento en FTE 0—
    no hay prorrata posible y se reparte **en partes iguales**. La alternativa
    sería descartar el monto, y eso haría desaparecer plata que el archivo sí
    traía.
    """
    n = len(pesos)
    if n == 0:
        return []
    suma = sum(pesos)
    if suma <= 0:
        base = [Decimal(1)] * n          # sin salarios: partes iguales
        suma = Decimal(n)
    else:
        base = pesos

    partes = [(total * p / suma).quantize(Decimal("0.0001")) for p in base]
    resto = total - sum(partes)
    if resto:
        i = max(range(n), key=lambda k: base[k])
        partes[i] += resto
    return partes
