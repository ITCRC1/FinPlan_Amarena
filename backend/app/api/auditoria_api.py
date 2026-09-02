# -*- coding: utf-8 -*-
"""La auditoría del detalle: cada monto del GL y en qué renglón del P&L terminó.

Owner, 2026-09-02, entregando `p&L auditoria 2026.xlsx` y `julio FORMAT
2026.xlsx`: *«necesito crear esos 2 tabs en cierre; uno para ver el detalle tal
cual el formato y el otro para ver la auditoría de los detalles»*.

## Qué contesta

Tres preguntas, en un solo viaje, para UN mes:

1. **¿De qué está hecha cada línea?** El detalle cuenta por cuenta, agrupado por
   departamento, con la naturaleza (Ingresos · Costo · Payroll · Opex · Reparto ·
   Bajo GOP) y el renglón del P&L al que cae.
2. **¿Cuadra?** Por cada línea del motor, cuánto suma su detalle y cuál es la
   diferencia. Es la columna «Dif.» del libro del owner.
3. **¿Cómo se reparte por departamento?** La matriz Ingresos / Costo / Payroll /
   Opex / Bajo GOP / Total gasto que él ya usa.

## Lo que hace válida a una auditoría

**Clasificar igual que el motor.** La atribución la hace
`pl_engine.linea_de_fila`, que reusa `group_for_dept`,
`revenue_line_for_account` y `nonop_line_for_account` — las mismas funciones que
usa `build_actual_inputs`. Repetir esas tablas acá daría un reporte que **cuadra
consigo mismo** y da el visto bueno justo cuando el P&L está mal.

⚠️ **Sólo tiene sentido sobre un escenario con detalle por cuenta**
(`actual_entries`), que es lo que dejan los actuales importados. Un BUDGET
armado en los checkbooks no tiene GL: se contesta con el detalle vacío y se
dice por qué, en vez de devolver ceros que se leerían como «no hay nada».

## Lo que NO trae, y no es un olvido

**La cuenta contable local** (`61011101 Salarios`) y el renglón del archivo
fuente. El GL que importa la app viene codificado en USALI de cuatro dígitos
—`_acct_code` exige exactamente cuatro— y la cuenta local **no se guarda con el
monto en ninguna tabla**. Inventarla sería justo lo que este libro no puede
hacer. Para tenerla haría falta que el importador la conserve; queda dicho en el
`aviso` de la respuesta para que se vea en pantalla y no sólo acá.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select

from app.api.pl_api import _get_scenario_or_404, _monthly_results, get_session
from app.engine import pl_engine
from app.errores import ErrorApi
from app.models.actual_entry import ActualEntry
from app.models.department_catalog import DepartmentCatalog

router = APIRouter(tags=["auditoria"])

MESES = ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"]

#: Las columnas de la matriz por departamento, en el orden del libro del owner.
COLUMNAS = [pl_engine.TIPO_INGRESO, pl_engine.TIPO_COSTO, pl_engine.TIPO_PAYROLL,
            pl_engine.TIPO_OPEX, pl_engine.TIPO_REPARTO, pl_engine.TIPO_BAJO_GOP]

#: Qué naturalezas son GASTO. El reparto entra —es un crédito, resta— y el
#: ingreso no. Sin esta distinción el «total gasto» de un departamento de
#: reparto saldría bruto y no netearía.
GASTO = {pl_engine.TIPO_COSTO, pl_engine.TIPO_PAYROLL, pl_engine.TIPO_OPEX,
         pl_engine.TIPO_REPARTO, pl_engine.TIPO_BAJO_GOP}

CERO = Decimal("0")


def _f(x) -> float:
    return float(x or 0)


@router.get("/pl/{scenario_id}/auditoria/")
async def auditoria_del_mes(scenario_id: str, mes: int):
    """El detalle de UN mes, cuadrado contra las líneas del motor."""
    if not 1 <= mes <= 12:
        raise ErrorApi(422, "mes.rango_invalido")

    async with get_session() as session:
        escenario = await _get_scenario_or_404(session, scenario_id)
        col = MESES[mes - 1]

        nombres = {
            d.dept_code: d.dept_name
            for d in (await session.execute(select(DepartmentCatalog))).scalars()
        }

        filas_raw = [
            e for e in (await session.execute(select(ActualEntry).where(
                ActualEntry.scenario_id == scenario_id))).scalars()
            if (getattr(e, col, None) or CERO) != CERO
        ]

        # ── 1. El detalle, fila por fila ──────────────────────────────────────
        detalle = []
        por_linea: dict[str, Decimal] = {}
        por_depto: dict[str, dict[str, Decimal]] = {}
        for e in filas_raw:
            monto = Decimal(str(getattr(e, col)))
            linea, tipo = pl_engine.linea_de_fila(e.account_code, e.dept_code)
            if not tipo:
                continue   # 9xxx: estadística, no es plata
            detalle.append({
                "dept_code": e.dept_code,
                "dept_name": nombres.get(e.dept_code, e.dept_code),
                "account_code": e.account_code,
                "account_name": e.account_name,
                "outlet": e.outlet,
                "tipo": tipo,
                "linea": linea,
                "monto": _f(monto),
            })
            if linea:
                por_linea[linea] = por_linea.get(linea, CERO) + monto
            caja = por_depto.setdefault(e.dept_code, {c: CERO for c in COLUMNAS})
            caja[tipo] = caja.get(tipo, CERO) + monto

        detalle.sort(key=lambda r: (r["dept_code"], r["tipo"], r["account_code"]))

        # ── 2. El cuadre contra el motor ──────────────────────────────────────
        #
        # ⚠️ Se compara contra `_monthly_results`, que es EL MISMO cálculo que
        # dibuja el P&L en pantalla — no contra `pl_lines`, que es una foto que
        # puede estar vieja si nadie apretó Recalcular.
        mensual = await _monthly_results(session, escenario)
        del_mes = next((m for m in mensual if m["month"] == mes), None)
        lineas_motor = {l.line_code: l for l in (del_mes or {}).get("lines", [])}

        cuadre = []
        for code, l in lineas_motor.items():
            if code not in por_linea and not l.amount_usd:
                continue
            det = por_linea.get(code, CERO)
            cuadre.append({
                "linea": code,
                "nombre": l.line_name,
                "seccion": l.section,
                "motor": _f(l.amount_usd),
                "detalle": _f(det),
                "dif": _f(Decimal(str(l.amount_usd)) - det),
            })
        # Lo que el detalle atribuye a una línea que el motor no dibuja. No
        # debería pasar nunca; si pasa, es exactamente lo que hay que ver.
        for code, det in por_linea.items():
            if code not in lineas_motor:
                cuadre.append({"linea": code, "nombre": "(sin línea en el P&L)",
                               "seccion": "HUERFANO", "motor": 0.0,
                               "detalle": _f(det), "dif": _f(-det)})
        cuadre.sort(key=lambda r: (r["seccion"], r["linea"]))

        # ── 3. La matriz por departamento ─────────────────────────────────────
        departamentos = []
        for dept in sorted(por_depto):
            caja = por_depto[dept]
            departamentos.append({
                "dept_code": dept,
                "dept_name": nombres.get(dept, dept),
                **{c: _f(caja.get(c, CERO)) for c in COLUMNAS},
                "total_gasto": _f(sum((caja.get(c, CERO) for c in GASTO), CERO)),
            })
        totales = {c: round(sum(d[c] for d in departamentos), 2) for c in COLUMNAS}
        totales["total_gasto"] = round(
            sum(d["total_gasto"] for d in departamentos), 2)

        # ── 4. Los avisos ─────────────────────────────────────────────────────
        avisos = []
        if not filas_raw:
            avisos.append(
                "Este escenario no tiene detalle por cuenta cargado para el mes. "
                "La auditoría sólo aplica a los actuales importados: un "
                "presupuesto armado en los checkbooks no tiene GL que auditar.")
        huerfanos = [r for r in detalle if not r["linea"]]
        if huerfanos:
            avisos.append(
                f"{len(huerfanos)} fila(s) no caen en ninguna línea del P&L y "
                f"por eso NO suman: revisá su departamento y su cuenta.")
        descuadres = [c for c in cuadre if abs(c["dif"]) >= 0.005]
        if descuadres:
            avisos.append(
                f"{len(descuadres)} línea(s) no cuadran contra su detalle.")

        return {
            "scenario_id": scenario_id,
            "escenario": f"{escenario.type} {escenario.version} {escenario.year}",
            "year": escenario.year,
            "mes": mes,
            "detalle": detalle,
            "cuadre": cuadre,
            "departamentos": departamentos,
            "totales": totales,
            "columnas": COLUMNAS,
            "avisos": avisos,
            "nota_cuenta_local": (
                "El GL que importa la app viene en códigos USALI de cuatro "
                "dígitos. La cuenta contable local (ej. 61011101) no se guarda "
                "junto al monto en ninguna tabla, así que no se puede mostrar "
                "sin inventarla."),
        }
