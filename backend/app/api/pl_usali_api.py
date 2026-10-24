# -*- coding: utf-8 -*-
"""El P&L USALI del cierre: el resumen en español, y el detalle cuenta por cuenta.

Owner, 2026-10-23, entregando `AMAREANA SEPTEMBER 2026 ACTUAL VERSUS FORECAST.xlsx`:
*«necesito que construyas el tab llamado P&L USALI SEPT, tal cual; métemelo acá
en cierre de mes como un sub tab más»*.

## ⚠️ No calcula nada: reagrupa

El cuadro del Excel y el P&L que ya está en pantalla dicen **los mismos
números**. Cotejado contra el cierre de septiembre de Amarena:

| | Excel USALI | P&L en pantalla |
|---|---|---|
| Habitaciones, ingreso | 21.999,59 | 21.999,59 |
| Tours, gasto | 1.116,32 | 1.116,32 |
| Total ingresos | 50.378,93 | 50.378,93 |
| Total gastos departamentales | 61.170,45 | 61.170,45 |

Lo que cambia es **la agrupación y el idioma**, no la aritmética. Por eso el
resumen sale de `_serie_por_codigo` —la misma función que alimenta el P&L
Detail— y no de una cascada escrita de nuevo.

**Escribirla de nuevo era el error caro.** Dos cascadas sobre los mismos datos
no se separan el primer día: se separan el día que alguien arregla un mapeo en
una y se olvida de la otra, y entonces el hotel tiene dos P&L que cuadran por
dentro y no entre sí. `Formato.tsx` ya dejó escrita esa lección.

## Las secciones salen por prefijo, no por lista

`REV_*`, `OPEX_*`, `PROFIT_*`, `OH_*`. Una lista escrita a mano se queda vieja
el día que entra un departamento nuevo, y el renglón nuevo **no aparecería y
nada lo diría** — el total seguiría cuadrando porque sale de `TOTAL_*`, que es
una línea calculada aparte.

## El detalle

Viene de `_del_mayor` / `_del_auxiliar` con `clave=""`: una pasada por clase
—cinco en total— devuelve **todas** las cuentas de **todos** los departamentos.
Es el mismo origen que usa el panel que se abre al tocar una celda del P&L, así
que el detalle de acá y el de allá no pueden discrepar.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.api.detalle_celda_api import _del_auxiliar, _del_mayor
from app.api.pl_detail_api import _serie_por_codigo
from app.auth import get_current_user
from app.db import get_session
from app.engine import recalculate as recalc
from app.errores import ErrorApi
from app.models.mapping import AccountMapping
from app.models.department_catalog import DepartmentCatalog
from app.models.scenario import Scenario
from sqlalchemy import select

router = APIRouter(tags=["pl-usali"])

CERO = Decimal("0")

#: Las cinco clases que tiene el detalle, en el orden en que el owner las lee
#: dentro de cada departamento: primero lo que entra, después lo que cuesta.
CLASES = [
    ("revenue", "INGRESOS"),
    ("cost", "COSTO DE VENTAS"),
    ("payroll", "PLANILLA Y CARGAS SOCIALES"),
    ("opex", "OTROS GASTOS"),
    ("property", "CARGOS FIJOS Y NO OPERATIVOS"),
]

#: Prefijo de línea → sección del resumen. El orden es el del cuadro.
SECCIONES = [
    ("ingresos", "REV_", "INGRESOS OPERATIVOS"),
    ("gastos_dept", "OPEX_", "GASTOS DEPARTAMENTALES"),
    ("utilidad_dept", "PROFIT_", "UTILIDAD DEPARTAMENTAL"),
    ("no_distribuidos", "OH_", "GASTOS NO DISTRIBUIDOS"),
]

#: La cascada de abajo del GOP, en orden. Cada entrada es (código, rótulo).
#: ⚠️ Son códigos CALCULADOS del propio P&L: tomarlos de acá y no sumarlos a
#: mano es lo que garantiza que el GOP de este cuadro sea el mismo GOP.
CASCADA = [
    ("TOTAL_GOP", "UTILIDAD BRUTA DE OPERACIÓN (GOP)"),
    ("TOTAL_RENT_MGMT_FEES", "Honorarios de administración"),
    ("__despues_honorarios", "UTILIDAD DESPUÉS DE HONORARIOS"),
    ("TOTAL_OTHER_EXPENSES", "Cargos fijos y no operativos"),
    ("EBITDA_BEFORE_CAPITAL", "EBITDA"),
    ("CAPITAL_EXPENSE", "Reserva de capital"),
    ("FINANCIAL_EXPENSES", "Gastos financieros (incl. diferencial cambiario)"),
    ("TOTAL_DEPRECIATIONS", "Depreciación"),
    ("EBT", "UTILIDAD ANTES DE IMPUESTOS"),
    ("INCOME_TAXES", "Impuesto de renta"),
    ("NET_PROFIT", "UTILIDAD NETA"),
]


def _mes(serie, mes: int) -> Decimal:
    """El monto del mes, o el año completo con `mes=0`."""
    if not serie:
        return CERO
    if mes == 0:
        return Decimal(str(sum(serie)))
    return Decimal(str(serie[mes - 1])) if len(serie) >= mes else CERO


def _pct(monto: Decimal, base: Decimal) -> float:
    """Participación sobre la base. Base cero da 0 y no una división rota."""
    return round(float(monto / base), 4) if base else 0.0


@router.get("/reports/pl-usali/{scenario_id}/")
async def pl_usali(
    scenario_id: str,
    mes: int = Query(0, ge=0, le=12, description="1-12; 0 = año completo"),
    ambito: str = Query("consolidado", description="consolidado | hotel | club"),
    _=Depends(get_current_user),
):
    """El cuadro USALI de un mes: resumen, detalle por departamento y control."""
    if ambito not in ("consolidado", "hotel", "club"):
        raise ErrorApi(422, "reporte.ambito_desconocido", ambito=ambito)

    async with get_session() as s:
        escenario = await s.get(Scenario, scenario_id)
        if escenario is None:
            raise ErrorApi(404, "escenario.no_encontrado")

        # ── El resumen, con los números del P&L ─────────────────────────────
        por_codigo = await _serie_por_codigo(s, scenario_id)
        rotulos = await _rotulos(s)

        resumen: dict = {}
        total_ingresos = CERO
        for clave, prefijo, titulo in SECCIONES:
            filas = []
            for code, serie in sorted(por_codigo.items()):
                if not code.startswith(prefijo) or code.startswith("TOTAL"):
                    continue
                monto = _mes(serie, mes)
                filas.append({"code": code,
                              "rotulo": rotulos.get(code, code),
                              "monto": round(float(monto), 2)})
            total = Decimal(str(sum(f["monto"] for f in filas)))
            if clave == "ingresos":
                total_ingresos = total
            resumen[clave] = {
                "titulo": titulo,
                "filas": filas,
                "total": round(float(total), 2),
            }
        # El % se mide contra el ingreso total, igual que en el Excel.
        for bloque in resumen.values():
            for f in bloque["filas"]:
                f["pct"] = _pct(Decimal(str(f["monto"])), total_ingresos)
            bloque["pct"] = _pct(Decimal(str(bloque["total"])), total_ingresos)

        cascada = []
        for code, rotulo in CASCADA:
            if code == "__despues_honorarios":
                monto = (Decimal(str(resumen_valor(por_codigo, "TOTAL_GOP", mes)))
                         - Decimal(str(resumen_valor(
                             por_codigo, "TOTAL_RENT_MGMT_FEES", mes))))
            else:
                monto = _mes(por_codigo.get(code), mes)
            cascada.append({"code": code, "rotulo": rotulo,
                            "monto": round(float(monto), 2),
                            "pct": _pct(monto, total_ingresos)})

        # ── El detalle, cuenta por cuenta ───────────────────────────────────
        manda_el_mayor = (escenario.type == "ACTUAL"
                          or await recalc.lo_subido_manda(s, escenario))
        catalogo = {
            (m.dept_code or "", m.account_code): m.account_name_example
            for m in (await s.execute(select(AccountMapping).where(
                AccountMapping.active_status == "YES"))).scalars()
        }
        deptos = {d.dept_code: d for d in
                  (await s.execute(select(DepartmentCatalog))).scalars()}

        #: {dept: {clase: [filas]}}
        arbol: dict[str, dict[str, list]] = {}
        for clase, _titulo in CLASES:
            crudo = (await _del_mayor(s, escenario, clase, "") if manda_el_mayor
                     else await _del_auxiliar(s, escenario, clase, ""))
            series = crudo.get("series", {})
            # El nombre que trae el mayor le gana al del catálogo: es el que la
            # persona ve en su propio archivo contable.
            del_mayor = crudo.get("nombres", {})
            for llave, serie in series.items():
                dept, cuenta = llave if isinstance(llave, tuple) else ("", llave)
                monto = _mes(serie, mes)
                if not monto:
                    continue
                arbol.setdefault(dept, {}).setdefault(clase, []).append({
                    "cuenta": cuenta,
                    "nombre": (del_mayor.get(cuenta)
                               or catalogo.get((dept, cuenta))
                               or catalogo.get(("", cuenta)) or ""),
                    "monto": round(float(monto), 2),
                })

        departamentos = []
        for dept in sorted(arbol):
            cat = deptos.get(dept)
            ingreso = Decimal(str(sum(
                f["monto"] for f in arbol[dept].get("revenue", []))))
            secciones, gasto = [], CERO
            for clase, titulo in CLASES:
                filas = sorted(arbol[dept].get(clase, []),
                               key=lambda f: f["cuenta"])
                if not filas:
                    continue
                total = Decimal(str(sum(f["monto"] for f in filas)))
                if clase != "revenue":
                    gasto += total
                for f in filas:
                    f["pct"] = _pct(Decimal(str(f["monto"])), ingreso or total)
                secciones.append({"clase": clase, "titulo": titulo,
                                  "filas": filas,
                                  "total": round(float(total), 2),
                                  "pct": _pct(total, ingreso or total)})
            departamentos.append({
                "dept_code": dept,
                "dept_name": cat.dept_name if cat else dept,
                "kind": (cat.pl_kind if cat else "OPERATING") or "OPERATING",
                "secciones": secciones,
                "ingreso": round(float(ingreso), 2),
                "gasto": round(float(gasto), 2),
                "utilidad": round(float(ingreso - gasto), 2),
            })

        # ── Control: el resumen contra el detalle ───────────────────────────
        #
        # ⚠️ Es la razón de ser del bloque. Los dos lados salen de orígenes
        # distintos —el resumen de las líneas del P&L, el detalle del mayor— y
        # si se separan hay que verlo acá y no en una reunión con el dueño.
        det_ingreso = Decimal(str(sum(d["ingreso"] for d in departamentos)))
        det_gasto = Decimal(str(sum(d["gasto"] for d in departamentos)))
        res_gasto = (Decimal(str(resumen["gastos_dept"]["total"]))
                     + Decimal(str(resumen["no_distribuidos"]["total"])))

        return {
            "scenario_id": scenario_id,
            "escenario": f"{escenario.type} · {escenario.version} · {escenario.year}",
            "year": escenario.year,
            "mes": mes,
            "ambito": ambito,
            "resumen": resumen,
            "cascada": cascada,
            "departamentos": departamentos,
            "control": {
                "ingresos_resumen": round(float(total_ingresos), 2),
                "ingresos_detalle": round(float(det_ingreso), 2),
                "ingresos_dif": round(float(total_ingresos - det_ingreso), 2),
                "gastos_resumen": round(float(res_gasto), 2),
                "gastos_detalle": round(float(det_gasto), 2),
                "gastos_dif": round(float(res_gasto - det_gasto), 2),
            },
        }


def resumen_valor(por_codigo: dict, code: str, mes: int) -> float:
    """El monto de una línea calculada del P&L, para el mes pedido."""
    return round(float(_mes(por_codigo.get(code), mes)), 2)


async def _rotulos(s) -> dict[str, str]:
    """Rótulo en español de cada línea, del propio catálogo de departamentos.

    ⚠️ El nombre NO se traduce acá con un diccionario escrito a mano. El
    catálogo ya guarda `dept_name` en español, que es lo que el owner lee en
    todas las demás pantallas; inventar otro juego de nombres haría que el
    mismo departamento se llame distinto según el cuadro.
    """
    out: dict[str, str] = {}
    for d in (await s.execute(select(DepartmentCatalog))).scalars():
        if not d.default_pl_group:
            continue
        g = d.default_pl_group
        for prefijo in ("REV_", "OPEX_", "PROFIT_", "OH_"):
            out[f"{prefijo}{g}"] = d.dept_name or g
    return out
