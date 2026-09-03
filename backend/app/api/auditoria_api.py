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
from app.models.mapping import AccountMapping
from app.nombres_cuenta import limpiar_nombre

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

#: Nombre de cuenta cuando el asiento vino sin él.
#:
#: Owner, 2026-09-03: *«que todas las cuentas lleven nombre»*.
#:
#: Medido en producción sobre el ACTUAL Final 2026: de 115 asientos, los ÚNICOS
#: sin nombre son 13 códigos, y los trece son de planilla (60xx). No es un dato
#: perdido: la planilla no se importa del GL cuenta por cuenta, viene del bloque
#: de nómina, que trae el concepto y no su rótulo.
#:
#: ⚠️ Los nombres NO se escriben acá: se leen de `consulta_api.CONCEPTOS`, que
#: es de donde salen los mismos rótulos en Consulta y en Account Mapping. Una
#: segunda lista sería la garantía de que un día el mismo 6023 se llame
#: «Vacation Provision» en un reporte y otra cosa en el de al lado.
#:
#: Los catálogos `accounts` y `payroll_accounts` están VACÍOS en producción
#: (0 filas), así que no hay de dónde sacarlos por ahí; el día que se carguen,
#: este respaldo sigue siendo correcto porque dice lo mismo.
def _nombres_de_planilla() -> dict[str, str]:
    from app.api.consulta_api import CONCEPTOS
    return {codigo: rotulo for _campo, codigo, rotulo in CONCEPTOS}


async def _catalogo_gl(session) -> dict[tuple[str, str], str]:
    """Qué cuentas de GL puede tener cada departamento, y cómo se llaman.

    Owner, 2026-09-03: *«me gustaría todas las opciones que tiene cada
    departamento en cuanto a GL … pero que haya el 100% de los datos siempre»*.

    Sale de `account_mapping`, que es el catálogo real: 1.098 reglas sobre 27
    departamentos en producción, y **toda** cuenta del ACTUAL 2026 tiene una.
    Es una TABLA, editable sin desplegar — no una lista en el código.

    Devuelve `{(dept, cuenta): nombre}`.

    ⚠️ Sólo las reglas ACTIVAS. Una dada de baja describe cómo se clasificaba
    ANTES; ofrecerla como opción vigente invitaría a usarla de nuevo.
    """
    filas = (await session.execute(
        select(AccountMapping.dept_code, AccountMapping.account_code,
               AccountMapping.account_name_example)
        .where(AccountMapping.active_status == "YES"))).all()
    return {
        (dept or "", cuenta): (nombre or "").strip()
        for dept, cuenta, nombre in filas
    }


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
        rotulo_planilla = _nombres_de_planilla()
        catalogo = await _catalogo_gl(session)

        # ── 1. El detalle, fila por fila ──────────────────────────────────────
        #
        # ⚠️ Se leen TODOS los asientos, no sólo los que tienen monto, para
        # poder decir cuántos hay y qué pasó con cada uno. Owner, 2026-09-03:
        # *«que haya el 100% de los datos siempre»*. Una auditoría que descarta
        # filas en silencio no puede demostrar que no descartó nada.
        todos = list((await session.execute(select(ActualEntry).where(
            ActualEntry.scenario_id == scenario_id))).scalars())

        detalle = []
        por_linea: dict[str, Decimal] = {}
        por_depto: dict[str, dict[str, Decimal]] = {}
        vistas: set[tuple[str, str]] = set()
        n_con_monto = n_sin_tipo = 0
        monto_sin_tipo = CERO

        def _nombre(dept: str, cuenta: str, propio: str | None = None) -> str:
            """El nombre de una cuenta. Nunca vacío.

            El orden importa: primero lo que trajo el asiento —es el nombre con
            el que vino del GL—, después el catálogo del departamento, después
            los conceptos de planilla, y recién al final el código.

            En producción, de 115 asientos los ÚNICOS sin nombre propio son 13
            códigos de planilla (60xx): no se importan del GL cuenta por cuenta,
            vienen del bloque de nómina, que trae el concepto y no su rótulo.
            """
            # ⚠️ Se LIMPIA. `account_name` y `account_name_example` traen
            # todas las variantes vistas en el mayor pegadas con barras
            # —«DEPRECIATION1 | DEPRECIATION2 | DEPRECIATION»—, y eso no es un
            # rótulo: son sesenta caracteres donde caben veinte.
            return (limpiar_nombre(propio)
                    or limpiar_nombre(catalogo.get((dept, cuenta), ""))
                    or rotulo_planilla.get(cuenta, "")
                    or f"Cuenta {cuenta}")

        for e in todos:
            monto = Decimal(str(getattr(e, col, None) or 0))
            linea, tipo = pl_engine.linea_de_fila(e.account_code, e.dept_code)
            if not tipo:
                # 9xxx: estadística, no es plata. Se CUENTA en vez de
                # desaparecer, para que el total del mes se pueda comprobar.
                if monto != CERO:
                    n_sin_tipo += 1
                    monto_sin_tipo += monto
                continue
            vistas.add((e.dept_code, e.account_code))
            if monto == CERO:
                continue
            n_con_monto += 1
            detalle.append({
                "dept_code": e.dept_code,
                "dept_name": nombres.get(e.dept_code, e.dept_code),
                "account_code": e.account_code,
                "account_name": _nombre(e.dept_code, e.account_code, e.account_name),
                "outlet": e.outlet,
                "tipo": tipo,
                "linea": linea,
                "monto": _f(monto),
                "movimiento": True,
            })
            if linea:
                por_linea[linea] = por_linea.get(linea, CERO) + monto
            caja = por_depto.setdefault(e.dept_code, {c: CERO for c in COLUMNAS})
            caja[tipo] = caja.get(tipo, CERO) + monto

        # ── 1b. Las opciones de GL que el departamento tiene y NO usó ─────────
        #
        # Owner: *«todas las opciones que tiene cada departamento en cuanto a
        # GL»*. Sin esto sólo se ve lo que se movió, y una cuenta que DEBERÍA
        # tener monto y no lo tiene es invisible — que es el error más difícil
        # de encontrar: no se ve nada raro, se ve menos.
        #
        # ⚠️ Van marcadas `movimiento: false` y en CERO. No se inventa nada: se
        # dice que la opción existe y que este mes no se usó. La pantalla las
        # esconde con el interruptor «Compacto», que ya existe.
        #
        # Sólo de los departamentos que tienen algo este mes: ofrecer las 51
        # cuentas de un departamento que no operó llenaría el reporte de ruido.
        for (dept, cuenta), nombre in sorted(catalogo.items()):
            if dept not in por_depto or (dept, cuenta) in vistas:
                continue
            linea, tipo = pl_engine.linea_de_fila(cuenta, dept)
            if not tipo:
                continue
            detalle.append({
                "dept_code": dept,
                "dept_name": nombres.get(dept, dept),
                "account_code": cuenta,
                "account_name": _nombre(dept, cuenta, nombre),
                "outlet": None,
                "tipo": tipo,
                "linea": linea,
                "monto": 0.0,
                "movimiento": False,
            })

        detalle.sort(key=lambda r: (r["dept_code"], r["tipo"], r["account_code"]))

        # ── 2. El cuadre, POR RENGLÓN DEL REPORTE ─────────────────────────
        #
        # ⚠️ **No línea por línea, RENGLÓN por renglón**, y la diferencia no es
        # cosmética. El primer intento comparó cada `line_code` suelto y
        # reportó 37 descuadres en julio 2026, **todos falsos**, por dos
        # razones distintas:
        #
        # * los TOTALES y SUBTOTALES (`GOP`, `EBITDA_BEFORE`,
        #   `TOTAL_DEPRECIATIONS`) no tienen detalle propio: son sumas de otros
        #   renglones, así que su «detalle» siempre da cero;
        # * el vocabulario canónico parte el gasto de un departamento en varias
        #   líneas —`OPEX_FB` + `COS_FB_FOOD` + `COS_FB_BEV`— y el detalle
        #   atribuye a una sola. Cada par se descuadraba por el mismo monto con
        #   signos opuestos.
        #
        # El renglón del reporte agrupa justamente esos códigos, así que las
        # dos cosas se resuelven solas. Y es el nivel al que el owner audita:
        # él mira «Rooms», no `COS_FB_BEV`.
        #
        # La plantilla se importa de `pl_detail_api`: si cambia el reporte,
        # cambia la auditoría con él. Escribir una copia sería garantizar que
        # un día auditen cosas distintas.
        from app.api.pl_detail_api import CONSOLIDADO

        mensual = await _monthly_results(session, escenario)
        del_mes = next((m for m in mensual if m["month"] == mes), None)
        lineas_motor = {l.line_code: l for l in (del_mes or {}).get("lines", [])}

        # Los renglones DERIVADOS quedan afuera: el bloque de Operating Profit
        # es ingreso menos gasto, no se compone de asientos, y su «detalle»
        # siempre daría cero. En julio 2026 eran seis descuadres inventados.
        atribuibles = pl_engine.codigos_atribuibles()

        cuadre = []
        atribuidos: set[str] = set()
        for tipo, rotulo, codigos in CONSOLIDADO:
            if tipo != "det" or not codigos:
                continue
            if not any(c in atribuibles for c in codigos):
                continue
            motor = sum((Decimal(str(lineas_motor[c].amount_usd))
                         for c in codigos if c in lineas_motor), CERO)
            det = sum((por_linea.get(c, CERO) for c in codigos), CERO)
            atribuidos.update(codigos)
            if motor == CERO and det == CERO:
                continue
            cuadre.append({
                "linea": " · ".join(codigos),
                "nombre": rotulo,
                "seccion": "",
                "motor": _f(motor),
                "detalle": _f(det),
                "dif": _f(motor - det),
            })

        # Lo que el detalle atribuye a un código que NINGÚN renglón dibuja. No
        # debería pasar; si pasa, es exactamente lo que hay que ver, porque esa
        # plata está en los totales y en ninguna fila.
        for code, det in sorted(por_linea.items()):
            if code in atribuidos or det == CERO:
                continue
            cuadre.append({
                "linea": code, "nombre": "(ningún renglón lo dibuja)",
                "seccion": "HUERFANO", "motor": 0.0,
                "detalle": _f(det), "dif": _f(-det)})

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

        # ── 4. La cobertura: la prueba de que no se descartó nada ────────────
        #
        # Owner, 2026-09-03: *«que haya el 100% de los datos siempre»*.
        #
        # ⚠️ Esto NO es adorno: es lo único que distingue «no hay más» de «hay
        # más y no lo estoy mostrando». Antes el endpoint filtraba los montos
        # en cero y saltaba las cuentas 9xxx sin decirlo, así que un reporte al
        # que le faltaba media hoja se veía exactamente igual que uno completo.
        #
        # `suma_detalle` tiene que dar lo mismo que sumar la columna del mes en
        # `actual_entries` menos lo estadístico. Si no da, hay un asiento que
        # este reporte no está contando y el número de arriba lo delata.
        cobertura = {
            "asientos": len(todos),
            "con_monto": n_con_monto,
            "en_cero": len(todos) - n_con_monto - n_sin_tipo,
            "estadisticos": n_sin_tipo,
            "monto_estadistico": _f(monto_sin_tipo),
            "opciones_gl": sum(1 for r in detalle if not r["movimiento"]),
            "suma_detalle": round(
                sum(r["monto"] for r in detalle if r["movimiento"]), 2),
        }

        # ── 5. Los avisos ─────────────────────────────────────────────────────
        avisos = []
        if not n_con_monto:
            avisos.append(
                "Este escenario no tiene detalle por cuenta cargado para el mes. "
                "La auditoría sólo aplica a los actuales importados: un "
                "presupuesto armado en los checkbooks no tiene GL que auditar.")
        # ⚠️ Sólo las que TIENEN movimiento. Una opción del catálogo en cero
        # que no cae en ninguna línea no es plata perdida: es una opción que no
        # se usó. Contarla acá inventaría un problema.
        huerfanos = [r for r in detalle if not r["linea"] and r["movimiento"]]
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
            "cobertura": cobertura,
            "avisos": avisos,
            "nota_cuenta_local": (
                "El GL que importa la app viene en códigos USALI de cuatro "
                "dígitos. La cuenta contable local (ej. 61011101) no se guarda "
                "junto al monto en ninguna tabla, así que no se puede mostrar "
                "sin inventarla."),
        }
