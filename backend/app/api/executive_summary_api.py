# -*- coding: utf-8 -*-
"""El Resumen Ejecutivo mensual, en Word.

Owner, 2026-09-30, entregando el `Executive Summary` de CWL: *«usa este formato
como estándar y prepara uno igual para agosto en Amarena. quiero el informe en
word»*.

## ⚠️ Los números salen del MOTOR, no de la pantalla

`get_pl_compare` y `gasto_por_clase` son los mismos que alimentan el Dashboard y
el P&L del cierre. Este módulo no calcula un solo total: los pide y los redacta.

Es la diferencia entre un informe y un adorno. Si el resumen derivara sus
propias cifras, el día que difieran del cierre nadie sabría cuál mandó — y la
diferencia no se vería, porque un informe en prosa no cuadra contra nada.

## La prosa se escribe con los números

Cada frase toma la variación real y la dice. Los positivos y los negativos de la
Sección 4 no son una lista fija: se ORDENAN por tamaño de variación, así que el
informe habla de lo que de verdad movió el mes y no de lo que movió el mes en
que se escribió la plantilla.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.auth import get_current_user
from app.errores import ErrorApi
from app.export.executive_summary import (
    DOCX, build_executive_summary, k, linea, pct, usd, var_pct,
)

router = APIRouter(tags=["reports"])

#: Los cuatro bloques de gasto del pie del cuadro, con la clave que usa
#: `gasto-por-clase`. ⚠️ `TOTAL_REVENUES` se resuelve contra las líneas del P&L,
#: no contra este cuadro: acá sólo vive el GASTO.
CLASES = {
    "TOTAL_PAYROLL": "payroll",
    "TOTAL_OPEX_ONLY": "opex",
    "TOTAL_COST": "cost",
    "TOTAL_PROPERTY": "property",
}

#: Qué renglones del P&L se miran para armar positivos y negativos, y cómo se
#: llaman en el informe. El orden no importa: se ordenan por tamaño.
RENGLONES_MIX = [
    ("REV_ROOMS", "Rooms"), ("REV_FB", "F&B"), ("REV_SPA", "Spa"),
    ("REV_TOURS", "Tours"), ("REV_TRANSPORT", "Transportation"),
    ("REV_CLUB", "Madresal Club"), ("REV_LAUNDRY", "Laundry"),
    ("REV_RETAIL", "Retail"), ("REV_OTHER", "Other revenue"),
]


class Cuerpo(BaseModel):
    actual_id: str
    budget_id: str
    forecast_id: str | None = None
    mes: int
    propiedad: str | None = None


def _sel(meses: list[dict], desde: int, hasta: int, clave: str) -> float:
    """Un total de `gasto-por-clase` acumulado sobre un rango de meses."""
    return sum(float(m.get(clave) or 0.0)
               for m in meses if desde <= int(m.get("month") or 0) <= hasta)


@router.post("/reports/executive-summary/word/")
async def resumen_ejecutivo_word(body: Cuerpo, _=Depends(get_current_user)):
    """El informe del mes, en .docx."""
    if not 1 <= body.mes <= 12:
        raise ErrorApi(422, "mes.rango_invalido")

    from app.api.gasto_por_clase_api import gasto_por_clase
    from app.api.pl_api import get_pl_compare

    ids = [body.actual_id, body.budget_id] + (
        [body.forecast_id] if body.forecast_id else [])
    comp = await get_pl_compare(",".join(ids), month=body.mes)
    por_id = {v["scenario_id"]: v for v in comp["versions"]}
    act = por_id.get(body.actual_id)
    bud = por_id.get(body.budget_id)
    fcs = por_id.get(body.forecast_id) if body.forecast_id else None
    if not act or not bud:
        raise ErrorApi(404, "escenario.no_encontrado")

    # ── El gasto por clase, para el flow-through ─────────────────────────────
    gpc = await gasto_por_clase(scenarios=",".join(ids), detalle=False)
    meses_de = {v["scenario_id"]: v["meses"] for v in gpc["escenarios"]}

    #: `col` trae su propio corte; se lo ata al escenario y al rango por el
    #: rótulo que `get_pl_compare` ya puso en cada columna.
    rangos = {"month": (body.mes, body.mes), "ytd": (1, body.mes), "full": (1, 12)}

    def totales(col: dict, clave: str) -> float:
        if clave == "TOTAL_REVENUES":
            return linea(col, "TOTAL_REVENUES")
        sid, corte = col["__sid"], col["__corte"]
        d, h = rangos[corte]
        return _sel(meses_de.get(sid, []), d, h, CLASES[clave])

    # Se marca cada columna con su escenario y su corte: el flow-through
    # necesita saber de dónde salió para pedirle el gasto al cuadro correcto.
    for v in comp["versions"]:
        for corte in ("month", "ytd", "full"):
            v[corte]["__sid"] = v["scenario_id"]
            v[corte]["__corte"] = corte

    # ── El mix por departamento, YTD ─────────────────────────────────────────
    mix = []
    for code, rotulo in RENGLONES_MIX:
        a, b = linea(act["ytd"], code), linea(bud["ytd"], code)
        if abs(a) < 0.005 and abs(b) < 0.005:
            continue   # un renglón que no existe en esta propiedad no se lista
        vp = var_pct(a, b)
        mix.append([rotulo, usd(a), usd(b), usd(a - b),
                    f"{vp * 100:+,.1f}%" if vp is not None else "n/d"])

    # ── El ADR mes a mes, para la sección de tarifa ──────────────────────────
    from app.api.pl_api import get_pl_monthly
    adr_mes = []
    try:
        mensual = await get_pl_monthly(body.actual_id)
        for m in mensual.get("months", []):
            kp = m.get("kpis") or {}
            # ⚠️ Un mes sin noches ocupadas NO entra: su ADR es cero por falta
            # de operación, no por tarifa baja, y en una tabla de tarifas un
            # cero se lee como un desplome.
            if not float(kp.get("rooms_occupied") or 0):
                continue
            adr_mes.append([
                f"{m['month']:02d}", usd(float(kp.get("adr") or 0)),
                pct(float(kp.get("occupancy_pct") or 0)),
                f"{float(kp.get('rooms_occupied') or 0):,.0f}"])
    except Exception:
        adr_mes = []   # sin la serie el informe sale igual; sin informe, no

    # ── Positivos y negativos, ORDENADOS por tamaño ──────────────────────────
    positivos, negativos = _positivos_y_negativos(act, bud, fcs, totales, mix)

    etiqueta = lambda v: f"{v['type']} {v['version']} {v['year']}"  # noqa: E731
    datos = {
        "propiedad": body.propiedad or "",
        "mes": body.mes,
        "anio": act["year"],
        "actual": act, "budget": bud, "forecast": fcs,
        "rotulos": {"actual": etiqueta(act), "budget": etiqueta(bud),
                    **({"forecast": etiqueta(fcs)} if fcs else {})},
        "totales": totales,
        "mix": mix,
        "adr_por_mes": adr_mes,
        "positivos": positivos,
        "negativos": negativos,
    }
    docx = build_executive_summary(datos)
    nombre = f"Executive_Summary_{act['year']}_{body.mes:02d}.docx"
    return Response(content=docx, media_type=DOCX, headers={
        "Content-Disposition": f'attachment; filename="{nombre}"'})


def _positivos_y_negativos(act, bud, fcs, totales, mix):
    """Lo que salió bien y lo que salió mal, sacado de las propias variaciones.

    ⚠️ **Se ordenan por tamaño, no por una lista fija.** Un informe que siempre
    comenta los mismos seis renglones habla del mes en que se escribió la
    plantilla, no del mes que se está cerrando.
    """
    a, b = act["ytd"], bud["ytd"]
    pos: list[tuple[str, str]] = []
    neg: list[tuple[str, str]] = []

    def cuenta(titulo, texto, favorable):
        (pos if favorable else neg).append((titulo, texto))

    # Ingreso total.
    rev, revb = linea(a, "TOTAL_REVENUES"), linea(b, "TOTAL_REVENUES")
    vp = var_pct(rev, revb)
    cuenta("Revenue vs Budget",
           f"Total Revenue reached {k(rev)} versus {k(revb)} Budget, a variance "
           f"of {k(rev - revb)}"
           + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
           rev >= revb)

    # Volumen y tarifa.
    occ_a = float((a.get("kpis") or {}).get("occupancy_pct") or 0)
    occ_b = float((b.get("kpis") or {}).get("occupancy_pct") or 0)
    noc_a = float((a.get("kpis") or {}).get("rooms_occupied") or 0)
    noc_b = float((b.get("kpis") or {}).get("rooms_occupied") or 0)
    cuenta("Demand and guest volume",
           f"The hotel sold {noc_a:,.0f} rooms versus {noc_b:,.0f} Budget, with "
           f"occupancy of {pct(occ_a)} against {pct(occ_b)}.", noc_a >= noc_b)
    adr_a = float((a.get("kpis") or {}).get("adr") or 0)
    adr_b = float((b.get("kpis") or {}).get("adr") or 0)
    vp = var_pct(adr_a, adr_b)
    cuenta("Rate performance",
           f"YTD ADR closed at {usd(adr_a)} versus {usd(adr_b)} Budget"
           + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
           adr_a >= adr_b)

    # Los departamentos: los tres que más movieron, de cada lado.
    porte = []
    for fila in mix:
        try:
            d = float(fila[3].replace("$", "").replace(",", ""))
        except ValueError:
            continue
        porte.append((d, fila[0], fila[1], fila[2]))
    porte.sort(key=lambda x: -abs(x[0]))
    for d, rotulo, va, vb in porte[:6]:
        if abs(d) < 500:
            continue
        cuenta(f"{rotulo} revenue",
               f"{rotulo} reached {va} versus {vb} Budget, "
               f"{k(abs(d))} {'above' if d >= 0 else 'below'} plan.", d >= 0)

    # Los cuatro bloques de gasto.
    for clave, rotulo in (("TOTAL_PAYROLL", "Payroll and Benefits"),
                          ("TOTAL_OPEX_ONLY", "Operating Expenses"),
                          ("TOTAL_COST", "Cost of Sales"),
                          ("TOTAL_PROPERTY", "Property Expenses")):
        ga, gb = totales(a, clave), totales(b, clave)
        vp = var_pct(ga, gb)
        # ⚠️ En gasto, MENOS es favorable. Con la regla del ingreso, un
        # sobrecosto entraría en la lista de positivos.
        cuenta(rotulo,
               f"{rotulo} closed at {k(ga)} versus {k(gb)} Budget, "
               f"{k(abs(ga - gb))} {'above' if ga >= gb else 'below'} plan"
               + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
               ga <= gb)

    # La conversión: EBITDA y Net Profit.
    for code, rotulo in (("EBITDA_BEFORE", "EBITDA Before Capital"),
                         ("NET_PROFIT", "Net Profit")):
        x, y = linea(a, code), linea(b, code)
        vp = var_pct(x, y)
        cuenta(rotulo,
               f"{rotulo} closed at {k(x)} versus {k(y)} Budget, "
               f"{k(abs(x - y))} {'above' if x >= y else 'below'} plan"
               + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
               x >= y)
    return pos, neg
