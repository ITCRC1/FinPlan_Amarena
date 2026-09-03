# -*- coding: utf-8 -*-
"""De qué está hecha UNA celda del cuadro, sin salir de la pantalla.

Owner, 2026-09-03: *«¿será posible que se pueda hacer link? Toco la línea de
Rooms Revenue y me abre el detalle, sin ir, solamente se despliega lo más
detallado que haya. Seguro tenga más sentido para payroll y gastos, donde los GL
son más. Si abro payroll de Rooms se me despliegan los GL que suman eso, como un
cuadro sin salir a la otra ventana… así voy presentando y puedo ver los detalles
de una vez»*.

## Lo que contesta

Dado un renglón del cuadro —una clase (`payroll`, `opex`, `cost`, `property`,
`revenue`) y su clave (el departamento, la cuenta o la línea)— devuelve **las
cuentas que suman ese número**, para CADA versión pedida, con los doce meses.

Así el mismo desplegable sirve para comparar: la misma cuenta, el actual al lado
del presupuesto y del forecast.

## El presupuesto TAMBIÉN se abre por cuenta

Owner, 2026-09-03: *«el presupuesto debe tener GL, siempre debe estar conectado
a un GL»*. Y lo está: cada línea del checkbook lleva su `account_code` —opex,
costo y below-GOP— y los 17 conceptos de planilla **son** cuentas del mayor
(`c6000_sw` es la 6000). Así que el desplegable abre por cuenta en las tres
versiones, y se comparan cuenta contra cuenta, que es todo el punto.

Lo que cambia es de qué TABLA sale, y eso se declara en `fuente`:

* un **ACTUAL** lo trae de `actual_entries` — el mayor cargado;
* un **BUDGET** o un **FORECAST** lo trae de sus auxiliares, que es donde vive
  su detalle. No es «menos detalle»: es el mismo nivel, en otra tabla.

⚠️ **La única excepción es el ingreso agregado**, y no se inventa. Una línea del
checkbook como `ROOMS` o `FOOD` agrega VARIAS cuentas del mayor, así que
`REVENUE_LINE_ACCOUNT` sólo declara cuenta donde la línea ES una cuenta (las
tres del Club). Ponerle una a `ROOMS` sería elegir una de las que agrupa. Donde
no se puede bajar a cuenta, se muestra la línea y se dice por qué.

## Por qué no se reusó Consulta GL

`consulta_api` contesta la pregunta contraria —«dame todo el GL filtrado, en
formato largo, para pivotear en Excel»— y sólo mira el mayor. Acá la pregunta es
«de qué está hecha ESTA celda», que empieza por la clase y la clave del cuadro y
tiene que funcionar sobre un presupuesto.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db import get_session
from app.engine import pl_engine
from app.engine import recalculate as recalc
from app.errores import ErrorApi
from app.models.actual_entry import ActualEntry
from app.models.cost_entry import CostEntry
from app.models.department_catalog import DepartmentCatalog
from app.models.mapping import AccountMapping
from app.models.nonop_entry import NonOpEntry
from app.models.opex_entry import OpexEntry
from app.models.payroll_concept_entry import PayrollConceptEntry
from app.models.revenue_account_entry import RevenueAccountEntry
from app.models.scenario import Scenario
from app.nombres_cuenta import limpiar_nombre, nombre_de_cuenta

router = APIRouter(tags=["detalle-celda"])

MESES = ["jan", "feb", "mar", "apr", "may", "jun",
         "jul", "aug", "sep", "oct", "nov", "dec"]

CERO = Decimal("0")

#: La clase del cuadro → el primer dígito de la cuenta en el mayor.
CLASE_A_DIGITO = {"cost": "5", "payroll": "6", "opex": "7", "property": "8"}


def _f(x) -> float:
    return float(x or 0)


def _padre(dept: str) -> str:
    """El departamento del P&L al que pertenece un sub-departamento.

    ⚠️ Sube en CADENA: `consolidate_dept` resuelve un escalón y hay cadenas de
    dos —el 0132 cuelga del 0130 y el 0130 del 0140—. Es la misma función que
    usa `gasto_por_clase` para armar la celda; si acá subiera un escalón menos,
    el desplegable mostraría cuentas que no son las que suman ese número.
    """
    visto: set[str] = set()
    for _ in range(5):
        padre = pl_engine.consolidate_dept(dept)
        if padre == dept or padre in visto:
            return dept
        visto.add(dept)
        dept = padre
    return dept


async def _del_mayor(session, escenario, clase: str, clave: str) -> dict:
    """Las cuentas del mayor que caen en esa celda. Devuelve {cuenta: [12]}."""
    filas = (await session.execute(select(ActualEntry).where(
        ActualEntry.scenario_id == escenario.id))).scalars().all()
    out: dict[str, list[Decimal]] = {}
    nombres: dict[str, str] = {}
    digito = CLASE_A_DIGITO.get(clase)

    for e in filas:
        cuenta = str(e.account_code or "")
        dept = str(e.dept_code or "")
        if clase == "revenue":
            # El ingreso se indexa por LÍNEA del P&L, no por departamento: es
            # el mismo vocabulario que usa la celda.
            linea, tipo = pl_engine.linea_de_fila(cuenta, dept)
            if tipo != pl_engine.TIPO_INGRESO or (clave and linea != clave):
                continue
        elif clase == "property":
            # La clase 8 se abre por CUENTA, no por departamento: vive todo en
            # el mismo (0250).
            if not cuenta.startswith("8") or (clave and cuenta != clave):
                continue
        else:
            # `clave` vacía = la clase entera. Es lo que se abre al tocar el
            # renglón del concepto («Payroll») en vez de una de sus
            # sub-filas por departamento.
            if not digito or cuenta[:1] != digito:
                continue
            if clave and _padre(dept) != clave:
                continue
        serie = out.setdefault(cuenta, [CERO] * 12)
        for i, col in enumerate(MESES):
            serie[i] += Decimal(str(getattr(e, col, None) or 0))
        if cuenta not in nombres:
            nombres[cuenta] = (e.account_name or "").strip()
    return {"series": out, "nombres": nombres}


async def _del_auxiliar(session, escenario, clase: str, clave: str) -> dict:
    """Lo mismo, para una versión SIN mayor: sale de los checkbooks."""
    out: dict[str, list[Decimal]] = {}
    nombres: dict[str, str] = {}

    def sumar(cuenta: str, fila, nombre: str = "") -> None:
        serie = out.setdefault(cuenta, [CERO] * 12)
        for i, col in enumerate(MESES):
            serie[i] += Decimal(str(getattr(fila, col, None) or 0))
        if nombre and cuenta not in nombres:
            nombres[cuenta] = nombre

    if clase == "opex":
        for r in (await session.execute(select(OpexEntry).where(
                OpexEntry.scenario_id == escenario.id))).scalars():
            if not clave or _padre(str(r.dept_code or "")) == clave:
                sumar(str(r.account_code or ""), r,
                      str(getattr(r, "account_name", "") or ""))
    elif clase == "cost":
        for r in (await session.execute(select(CostEntry).where(
                CostEntry.scenario_id == escenario.id))).scalars():
            if not clave or _padre(str(r.dept_code or "")) == clave:
                sumar(str(r.account_code or ""), r,
                      str(getattr(r, "account_name", "") or ""))
    elif clase == "payroll":
        # ⚠️ La planilla no guarda una cuenta por fila: guarda los 17 CONCEPTOS
        # como columnas (`c6000_sw`, `c6020_ccss`…). Cada concepto ES una
        # cuenta del mayor, y así se abre igual que el actual — que es todo el
        # punto de este desplegable: comparar lo mismo con lo mismo.
        from app.api.consulta_api import CONCEPTOS
        acumulado: dict[str, list[Decimal]] = {}
        for r in (await session.execute(select(PayrollConceptEntry).where(
                PayrollConceptEntry.scenario_id == escenario.id))).scalars():
            if clave and _padre(str(r.dept_code or "")) != clave:
                continue
            mes = int(getattr(r, "month", 0) or 0)
            if not 1 <= mes <= 12:
                continue
            for campo, cuenta, rotulo in CONCEPTOS:
                v = Decimal(str(getattr(r, campo, None) or 0))
                if v == CERO:
                    continue
                acumulado.setdefault(cuenta, [CERO] * 12)[mes - 1] += v
                nombres.setdefault(cuenta, rotulo)
        out.update(acumulado)
    elif clase == "property":
        for r in (await session.execute(select(NonOpEntry).where(
                NonOpEntry.scenario_id == escenario.id))).scalars():
            if not clave or str(r.account_code or "") == clave:
                sumar(str(r.account_code or ""), r,
                      str(getattr(r, "description", "") or ""))
    elif clase == "revenue":
        # 1) Si hay ingreso cargado POR CUENTA, ése es el detalle: es el mismo
        #    nivel que el mayor del actual.
        for r in (await session.execute(select(RevenueAccountEntry).where(
                RevenueAccountEntry.scenario_id == escenario.id))).scalars():
            linea, tipo = pl_engine.linea_de_fila(str(r.account_code or ""),
                                                  str(r.dept_code or ""))
            if tipo == pl_engine.TIPO_INGRESO and (not clave or linea == clave):
                sumar(str(r.account_code or ""), r,
                      str(getattr(r, "account_name", "") or ""))
        if out:
            return {"series": out, "nombres": nombres}

        # 2) Si no, el checkbook de ingreso, que va por LÍNEA. Las líneas que
        #    SON una cuenta se muestran con su cuenta; las que agregan varias
        #    se muestran con su nombre y el aviso.
        from app.models.revenue_entry import (
            REVENUE_LINE_ACCOUNT, REVENUE_LINE_LABELS, RevenueEntry)
        agregadas = False
        for r in (await session.execute(select(RevenueEntry).where(
                RevenueEntry.scenario_id == escenario.id))).scalars():
            par = REVENUE_LINE_ACCOUNT.get(r.line)
            dept, cuenta = par if par else ("", "")
            linea, tipo = (pl_engine.linea_de_fila(cuenta, dept) if cuenta
                           else (None, None))
            if cuenta and (tipo != pl_engine.TIPO_INGRESO
                           or (clave and linea != clave)):
                continue
            if not cuenta:
                # ⚠️ Sin cuenta declarada no se puede saber si esta línea cae en
                # la celda que se abrió. Se compara por la línea del P&L a la
                # que va, que es lo que el motor usa.
                # `REVENUE_LINE_TO_REPORT_LINE` es la MISMA tabla con la que
                # el motor lleva el checkbook de ingreso al P&L. Rehacer el
                # mapeo acá daría un desplegable que no suma la celda.
                if clave and pl_engine.REVENUE_LINE_TO_REPORT_LINE.get(
                        str(r.line or "").lower()) != clave:
                    continue
                agregadas = True
            sumar(cuenta or r.line, r,
                  REVENUE_LINE_LABELS.get(r.line, r.line))
        return {"series": out, "nombres": nombres, "agregado": agregadas}
    return {"series": out, "nombres": nombres}


@router.get("/gasto-por-clase/detalle-de-celda/")
async def detalle_de_celda(
    scenarios: str = Query(..., description="ids separados por coma"),
    clase: str = Query(..., description="revenue | cost | payroll | opex | property"),
    clave: str = Query("", description="departamento, cuenta o línea; vacío = toda la clase"),
):
    """Las cuentas que suman una celda del cuadro, por versión."""
    ids = [s for s in (scenarios or "").split(",") if s.strip()]
    if not ids:
        raise ErrorApi(422, "escenario.falta")
    if clase not in ("revenue", "cost", "payroll", "opex", "property"):
        raise ErrorApi(422, "clase.desconocida")

    async with get_session() as session:
        catalogo = {
            (m.dept_code or "", m.account_code): m.account_name_example
            for m in (await session.execute(select(AccountMapping).where(
                AccountMapping.active_status == "YES"))).scalars()
        }
        deptos = {d.dept_code: d.dept_name for d in
                  (await session.execute(select(DepartmentCatalog))).scalars()}

        versiones = []
        series: dict[str, dict[str, list[Decimal]]] = {}
        nombres: dict[str, str] = {}

        for sid in ids:
            escenario = await session.get(Scenario, sid)
            if escenario is None:
                continue
            # La MISMA pregunta que hace `gasto_por_clase` para elegir de dónde
            # lee la celda: si el mayor manda, el detalle es el mayor.
            manda_el_mayor = (escenario.type == "ACTUAL"
                              or await recalc.lo_subido_manda(session, escenario))
            r = (await _del_mayor(session, escenario, clase, clave)
                 if manda_el_mayor
                 else await _del_auxiliar(session, escenario, clase, clave))
            series[sid] = r["series"]
            for cuenta, nombre in r["nombres"].items():
                if nombre and cuenta not in nombres:
                    nombres[cuenta] = nombre
            versiones.append({
                "scenario_id": sid,
                "escenario": f"{escenario.type} {escenario.version} {escenario.year}",
                "fuente": "Mayor (GL)" if manda_el_mayor else "Auxiliar (checkbook)",
                # ⚠️ Una línea de ingreso que agrega varias cuentas del mayor se
                # muestra como línea, no como cuenta: elegir una de las que
                # agrupa sería inventar.
                "agregado": bool(r.get("agregado")),
            })

        cuentas = sorted({c for s in series.values() for c in s})
        filas = []
        for cuenta in cuentas:
            filas.append({
                "cuenta": cuenta,
                "nombre": nombre_de_cuenta(cuenta, nombres.get(cuenta),
                                           catalogo, clave),
                "series": {sid: [_f(v) for v in series[sid].get(cuenta, [CERO] * 12)]
                           for sid in series},
            })

        rotulo = clave or "Todos los departamentos"
        if clase not in ("revenue", "property") and clave in deptos:
            rotulo = f"{clave} · {deptos[clave]}"
        elif clase == "property":
            rotulo = f"{clave} · {limpiar_nombre(catalogo.get(('', clave))) or ''}".strip(" ·")

        return {
            "clase": clase,
            "clave": clave,
            "rotulo": rotulo,
            "versiones": versiones,
            "filas": filas,
        }
