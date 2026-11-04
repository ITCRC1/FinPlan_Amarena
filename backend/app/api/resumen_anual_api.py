# -*- coding: utf-8 -*-
"""Resumen ejecutivo de un año contra otro — Forecast 2026 vs Budget 2027.

Owner, 2026-11-04: *«un resumen ejecutivo de alto nivel… donde analiza en este
caso es forecast 2026 full year versus budget 2027 full year y pones datos
mensuales para mejorar el entendimiento»*, y sobre cómo se mantiene al día:
*«debe haber una forma de que este reporte se actualice en forma automática o
un botón para darle refresh»*.

## Por qué esto no guarda nada

No hay tabla, ni foto, ni «generar». Cada llamada arma el resumen desde
`_monthly_results` —el mismo motor que alimenta el Dashboard, el P&L del cierre
y el Full P&L—, así que **abrir la pantalla ES actualizarla**. El botón de
refresh del frontend no recalcula nada en la base: vuelve a pedir esto.

Eso resuelve el pedido por construcción. Un informe que se guarda queda viejo
en cuanto alguien toca un checkbook, y el día que el número del informe y el
del P&L no coinciden nadie sabe cuál manda. Acá no pueden no coincidir: es el
mismo número leído una vez.

## El corte es AÑO CONTRA AÑO, y eso lo hace distinto del otro resumen

`app/export/executive_summary.py` compara dentro de un mismo año —el mes, el
acumulado y la proyección contra su presupuesto—. Este compara dos años
completos de dos escenarios distintos, que es otra pregunta: no «cómo vamos
contra lo que dijimos» sino «en qué se diferencia el año que viene del que
termina».

⚠️ **Los dos lados tienen que ser años completos.** Comparar un ACTUAL con
meses sin cargar contra doce meses de presupuesto da un derrumbe que sólo dice
que el año no terminó. Por eso el default del lado izquierdo es el FORECAST
—que sí proyecta los doce— y la respuesta trae `meses_con_dato` de cada lado
para que la pantalla lo pueda advertir.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from app.auth import get_current_user
from app.db import get_session
from app.engine import pl_engine
from app.errores import ErrorApi
from app.models.scenario import Scenario

router = APIRouter(tags=["reports"])

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

#: Las líneas de ingreso del P&L, en el orden en que se leen.
INGRESOS = [
    ("REV_ROOMS", "Habitaciones"),
    ("REV_FB", "A&B — comida"),
    ("REV_FB_BEV", "A&B — bebida"),
    ("REV_FB_MISC", "A&B — misceláneo"),
    ("REV_SPA", "Spa"),
    ("REV_TOURS", "Tours"),
    ("REV_TRANSPORTATION", "Transporte"),
    ("REV_RETAIL", "Tienda"),
    ("REV_LAUNDRY", "Lavandería"),
    ("REV_RENT", "Alquileres"),
    ("REV_CLUB", "Club"),
    ("REV_SUSTAINABILITY", "Sostenibilidad"),
    ("REV_MISC_OTHER", "Otros"),
]

#: La cascada, de arriba a abajo. `signo` dice cómo leer una variación: en un
#: ingreso subir es bueno; en un gasto, subir es malo. Sin esto el resumen
#: pintaría de verde un sobrecosto.
RESULTADO = [
    ("TOTAL_REVENUES", "Ingresos totales", +1),
    ("TOTAL_OPERATING_EXPENSES", "Gastos operativos", -1),
    ("OPERATING_PROFIT", "Utilidad operativa", +1),
    ("TOTAL_OVERHEAD_EXPENSES", "Overhead", -1),
    ("TOTAL_GOP", "GOP", +1),
    # ⚠️ NO es lo mismo que la clase «Gastos de propiedad» del cuadro de abajo.
    # Esta línea es sólo el bloque de arriba del EBITDA —renta, honorarios,
    # seguro, otros—; la clase cuenta TODAS las 8xxx, con capital, financieros,
    # depreciación e impuesto adentro. Las dos están bien y dan distinto; por
    # eso se llaman distinto, que es lo que evita la pregunta de «cuál es».
    ("TOTAL_NON_OP_EXPENSES", "No operativos (renta, honorarios, seguro)", -1),
    ("EBITDA_BEFORE_CAPITAL", "EBITDA antes de capital", +1),
    ("NET_PROFIT", "Utilidad neta", +1),
]

#: Las cuatro clases de gasto, como las lee el owner.
CLASES = [("payroll", "Planilla"), ("opex", "OPEX"),
          ("cost", "Costo de ventas"),
          ("property", "Propiedad — todas las 8xxx")]


def _vacio():
    return {"meses": [0.0] * 12, "anio": 0.0}


async def _lado(session, scenario) -> dict:
    """Un año completo: KPIs, líneas del P&L y gasto por clase, mes a mes."""
    from app.api.pl_api import _monthly_results
    from app.api.gasto_por_clase_api import _por_mes

    meses = await _monthly_results(session, scenario)
    lineas: dict[str, dict] = {}
    kpis = {k: [0.0] * 12 for k in
            ("rooms_available", "rooms_occupied", "guests")}
    con_dato = 0
    for m in meses:
        i = int(m["month"]) - 1
        k = m.get("kpis") or {}
        for clave in kpis:
            kpis[clave][i] = float(k.get(clave) or 0)
        hay = False
        for ln in m["lines"]:
            code = getattr(ln, "line_code", None) or (
                ln.get("line_code") if isinstance(ln, dict) else None)
            if not code:
                continue
            monto = float(getattr(ln, "amount_usd", None)
                          if not isinstance(ln, dict) else ln.get("amount_usd") or 0)
            d = lineas.setdefault(code, _vacio())
            d["meses"][i] += monto
            d["anio"] += monto
            if monto:
                hay = True
        if hay:
            con_dato += 1

    gasto = {c: [0.0] * 12 for c, _n in CLASES}
    # `detalle` lo llena `_por_mes`: {clase: {depto: [12 meses]}}. Es la misma
    # apertura que usa el tab de Gasto por Clase, no una cuenta nueva.
    detalle: dict = {}
    for fila in await _por_mes(session, scenario.id, detalle):
        i = int(fila["month"]) - 1
        for c, _n in CLASES:
            gasto[c][i] = float(fila.get(c) or 0)

    return {
        "escenario": {"id": str(scenario.id), "tipo": scenario.type,
                      "version": scenario.version, "anio": scenario.year},
        "meses_con_dato": con_dato,
        "kpis": kpis,
        "lineas": lineas,
        "gasto": gasto,
        "detalle": detalle,
    }


def _serie(lado: dict, code: str) -> dict:
    return lado["lineas"].get(code) or _vacio()


def _fila(code: str, nombre: str, a: dict, b: dict, signo: int = 1) -> dict:
    """Una fila del cuadro: los doce meses de cada lado y su variación.

    `favorable` ya viene resuelto acá y no en la pantalla: si cada vista decide
    por su cuenta si un aumento de gasto es bueno, tarde o temprano una lo
    pinta al revés.
    """
    sa, sb = _serie(a, code), _serie(b, code)
    var = sb["anio"] - sa["anio"]
    return {
        "code": code, "nombre": nombre,
        "base": sa["anio"], "base_meses": [round(x, 2) for x in sa["meses"]],
        "comp": sb["anio"], "comp_meses": [round(x, 2) for x in sb["meses"]],
        "var": round(var, 2),
        "var_pct": (round(100 * var / abs(sa["anio"]), 1) if sa["anio"] else None),
        "favorable": (var * signo) > 0 if abs(var) > 0.005 else None,
    }


def _kpis(lado: dict) -> dict:
    """Disponibles, ocupadas, pax, ocupación, ADR y RevPAR del año."""
    k = lado["kpis"]
    disp, occ, pax = (sum(k["rooms_available"]), sum(k["rooms_occupied"]),
                      sum(k["guests"]))
    rooms = _serie(lado, "REV_ROOMS")["anio"]
    return {
        "disponibles": round(disp, 1), "ocupadas": round(occ, 1),
        "pax": round(pax, 1),
        "ocupacion": round(occ / disp, 4) if disp else 0.0,
        "adr": round(rooms / occ, 2) if occ else 0.0,
        "revpar": round(rooms / disp, 2) if disp else 0.0,
        "rooms": round(rooms, 2),
        "meses": {
            "disponibles": [round(x, 1) for x in k["rooms_available"]],
            "ocupadas": [round(x, 1) for x in k["rooms_occupied"]],
            "pax": [round(x, 1) for x in k["guests"]],
            "ocupacion": [round(o / d, 4) if d else 0.0
                          for o, d in zip(k["rooms_occupied"], k["rooms_available"])],
        },
    }


def _departamentos(a: dict, b: dict) -> list[dict]:
    """Ingreso, gasto y utilidad por grupo operativo, los dos años."""
    out = []
    for grupo in pl_engine.OPERATING_GROUP_ORDER:
        nombre = pl_engine.GROUP_NAMES.get(grupo, grupo)
        rev = _fila(f"REV_{grupo}", nombre, a, b, +1)
        gas = _fila(f"OPEX_{grupo}", nombre, a, b, -1)
        uti = _fila(f"PROFIT_{grupo}", nombre, a, b, +1)
        if not any(abs(x["base"]) > 0.005 or abs(x["comp"]) > 0.005
                   for x in (rev, gas, uti)):
            continue           # un grupo que no opera en ninguno de los dos años
        out.append({"grupo": grupo, "nombre": nombre,
                    "ingreso": rev, "gasto": gas, "utilidad": uti})
    return out


def _por_departamento(a: dict, b: dict, clase: str, nombres: dict) -> list[dict]:
    """Una fila por departamento, con los doce meses de cada año.

    Los departamentos son la UNIÓN de los dos años: uno que existe sólo en el
    presupuesto nuevo tiene que verse —es precisamente el que hay que mirar— y
    uno que desaparece, también.
    """
    da = (a["detalle"].get(clase) or {})
    db = (b["detalle"].get(clase) or {})
    out = []
    for dept in sorted(set(da) | set(db)):
        ma = [round(x, 2) for x in da.get(dept, [0.0] * 12)]
        mb = [round(x, 2) for x in db.get(dept, [0.0] * 12)]
        ta, tb = sum(ma), sum(mb)
        if abs(ta) < 0.005 and abs(tb) < 0.005:
            continue
        var = tb - ta
        out.append({
            "code": dept, "nombre": nombres.get(dept, dept),
            "base": round(ta, 2), "base_meses": ma,
            "comp": round(tb, 2), "comp_meses": mb,
            "var": round(var, 2),
            "var_pct": (round(100 * var / abs(ta), 1) if ta else None),
            # En un gasto, subir NO es favorable.
            "favorable": var < 0 if abs(var) > 0.005 else None,
        })
    return sorted(out, key=lambda x: -abs(x["comp"]))


def _totales(filas: list[dict], nombre: str, signo: int = 1) -> dict:
    """La fila de total de un cuadro. Se calcula acá y no en la pantalla: dos
    vistas sumando por su cuenta terminan dando dos totales distintos."""
    ma = [round(sum(f["base_meses"][i] for f in filas), 2) for i in range(12)]
    mb = [round(sum(f["comp_meses"][i] for f in filas), 2) for i in range(12)]
    ta, tb = round(sum(ma), 2), round(sum(mb), 2)
    var = round(tb - ta, 2)
    return {"code": "TOTAL", "nombre": nombre, "base": ta, "base_meses": ma,
            "comp": tb, "comp_meses": mb, "var": var,
            "var_pct": (round(100 * var / abs(ta), 1) if ta else None),
            "favorable": (var * signo) > 0 if abs(var) > 0.005 else None,
            "es_total": True}


def _narrativa(a: dict, b: dict, ka: dict, kb: dict,
               ingresos: list[dict], resultado: list[dict],
               deptos: list[dict], clases: list[dict]) -> list[dict]:
    """La lectura del año, en BLOQUES y no en una lista de frases sueltas.

    Trece renglones seguidos son un volcado: el ojo no encuentra dónde empieza
    cada idea y los avisos —que es lo único que exige una decisión— quedan al
    mismo nivel que el resto. Agrupadas por tema, con un titular arriba y los
    avisos aparte, se lee en diagonal y se entiende igual.

    Cada bloque es `{titulo, tipo, lineas}`. El `tipo` lo usa la pantalla para
    el color y el Word para el formato; ninguno de los dos decide por su cuenta
    qué es un aviso.

    ⚠️ **Describe, no interpreta.** Dice qué se movió y cuánto; no dice si está
    bien. En CWL la narrativa se escribe a mano justamente porque el juicio —si
    una favorabilidad es ahorro o diferimiento, qué hallazgo va primero— no sale
    del dato. Acá el owner la pidió automática, así que cada frase se limita a
    lo que el número sostiene.
    """
    def m(v):
        return "${:,.0f}".format(v).replace(",", ".")

    def p(v):
        return "—" if v is None else "{:+.1f}%".format(v)

    ay, by = a["escenario"]["anio"], b["escenario"]["anio"]
    bloques: list[dict] = []

    def bloque(titulo, tipo, lineas):
        lineas = [x for x in lineas if x]
        if lineas:
            bloques.append({"titulo": titulo, "tipo": tipo, "lineas": lineas})

    rev = next(x for x in resultado if x["code"] == "TOTAL_REVENUES")
    gop = next((x for x in resultado if x["code"] == "TOTAL_GOP"), None)
    net = next((x for x in resultado if x["code"] == "NET_PROFIT"), None)

    # ── El titular ──────────────────────────────────────────────────────────
    titular = "El ingreso pasa de {} a {} ({})".format(
        m(rev["base"]), m(rev["comp"]), p(rev["var_pct"]))
    if gop:
        titular += ", y el GOP de {} a {}".format(m(gop["base"]), m(gop["comp"]))
    bloque("El año en una frase", "titular", [titular + "."])

    # ── De dónde sale el ingreso ────────────────────────────────────────────
    lineas = ["Volumen y tarifa: {:.0f} noches contra {:.0f}, ocupación de "
              "{:.1f}% contra {:.1f}%, ADR de ${:,.2f} contra ${:,.2f}.".format(
                  ka["ocupadas"], kb["ocupadas"], 100 * ka["ocupacion"],
                  100 * kb["ocupacion"], ka["adr"], kb["adr"])]
    suben = sorted((x for x in ingresos if x["var"] > 0), key=lambda x: -x["var"])[:3]
    if suben:
        lineas.append("Lo que más suma: " + " · ".join(
            "{} {}".format(x["nombre"], m(x["var"])) for x in suben) + ".")
    bajan = sorted((x for x in ingresos if x["var"] < 0), key=lambda x: x["var"])[:3]
    if bajan:
        lineas.append("Lo que resta: " + " · ".join(
            "{} {}".format(x["nombre"], m(x["var"])) for x in bajan) + ".")
    bloque("De dónde viene el ingreso", "normal", lineas)

    # ── El gasto ────────────────────────────────────────────────────────────
    bloque("Qué pasa con el gasto", "normal",
           ["{}: de {} a {} ({}).".format(x["nombre"], m(x["base"]), m(x["comp"]),
                                          p(x["var_pct"]))
            for x in clases if abs(x["var"]) > 0.005])

    # ── El resultado ────────────────────────────────────────────────────────
    lineas = []
    if gop:
        lineas.append("El GOP mejora {} — de {} a {}.".format(
            m(abs(gop["var"])), m(gop["base"]), m(gop["comp"]))
            if gop["var"] > 0 else
            "El GOP cae {} — de {} a {}.".format(
                m(abs(gop["var"])), m(gop["base"]), m(gop["comp"])))
    if net:
        lineas.append("La utilidad neta cierra en {} contra {}.".format(
            m(net["comp"]), m(net["base"])))
    mejor = max(deptos, key=lambda d: d["utilidad"]["var"], default=None)
    peor = min(deptos, key=lambda d: d["utilidad"]["var"], default=None)
    if mejor and abs(mejor["utilidad"]["var"]) > 0.005:
        lineas.append("El departamento que más mejora es {} ({}); el que más "
                      "se deteriora, {} ({}).".format(
                          mejor["nombre"], m(mejor["utilidad"]["var"]),
                          peor["nombre"], m(peor["utilidad"]["var"])))
    bloque("El resultado", "normal", lineas)

    # ── Lo que exige una decisión ───────────────────────────────────────────
    avisos = []
    ceros = [x["nombre"] for x in ingresos
             if abs(x["comp"]) < 0.005 and abs(x["base"]) > 0.005]
    if ceros:
        falta = sum(x["base"] for x in ingresos
                    if abs(x["comp"]) < 0.005 and abs(x["base"]) > 0.005)
        avisos.append("Facturaron en {} y están en CERO en {}: {} — {} que hoy "
                      "no están presupuestados. Si no es una decisión, faltan "
                      "cargarlas.".format(ay, by, ", ".join(ceros), m(falta)))
    if a["meses_con_dato"] < 12 or b["meses_con_dato"] < 12:
        avisos.append("{} trae {} meses con dato y {} trae {}. Un año incompleto "
                      "contra uno completo exagera toda variación: los "
                      "porcentajes de arriba se leen con esa reserva.".format(
                          ay, a["meses_con_dato"], by, b["meses_con_dato"]))
    bloque("Lo que hay que decidir", "aviso", avisos)
    return bloques


@router.get("/reports/resumen-anual/")
async def resumen_anual(
    base: str = Query(..., description="escenario del año que termina (Forecast)"),
    comparado: str = Query(..., description="escenario del año que viene (Budget)"),
    _=Depends(get_current_user),
):
    """El resumen ejecutivo, calculado en vivo. No guarda nada."""
    async with get_session() as session:
        a_scn = await session.get(Scenario, base)
        b_scn = await session.get(Scenario, comparado)
        if a_scn is None or b_scn is None:
            raise ErrorApi(404, "escenario.no_encontrado")
        a = await _lado(session, a_scn)
        b = await _lado(session, b_scn)
        from app.api._nombres_de_depto import nombres_de_depto
        nombres = await nombres_de_depto(session)

    ka, kb = _kpis(a), _kpis(b)
    # ⚠️ Las líneas declaradas en INGRESOS son las que tienen nombre lindo, pero
    # NO son todas: el motor emite más códigos REV_ (Private Bar, Tienda, Área
    # Recreativa, Other Rooms, los Rental…). Si sólo se listaran ésas, el total
    # del cuadro daría $163,72 menos que TOTAL_REVENUES del P&L — y un total que
    # no cuadra con el P&L hace dudar de todo lo demás, con razón.
    #
    # Así que después de las declaradas se barren las que queden, con el código
    # por nombre. Una línea nueva aparece sola el día que exista.
    ingresos = [_fila(c, n, a, b, +1) for c, n in INGRESOS]
    declarados = {c for c, _n in INGRESOS}
    sueltos = sorted({c for lado in (a, b) for c in lado["lineas"]
                      if c.startswith("REV_") and c not in declarados
                      and c != "TOTAL_REVENUES"})
    for c in sueltos:
        nombre = c[4:].replace("_", " ").title()
        ingresos.append(_fila(c, nombre, a, b, +1))
    ingresos = [x for x in ingresos
                if abs(x["base"]) > 0.005 or abs(x["comp"]) > 0.005]
    resultado = [_fila(c, n, a, b, s) for c, n, s in RESULTADO]
    deptos = _departamentos(a, b)

    clases = []
    for c, nombre in CLASES:
        sa, sb = sum(a["gasto"][c]), sum(b["gasto"][c])
        var = sb - sa
        clases.append({
            "clase": c, "nombre": nombre,
            "base": round(sa, 2), "base_meses": [round(x, 2) for x in a["gasto"][c]],
            "comp": round(sb, 2), "comp_meses": [round(x, 2) for x in b["gasto"][c]],
            "var": round(var, 2),
            "var_pct": (round(100 * var / abs(sa), 1) if sa else None),
            "favorable": var < 0 if abs(var) > 0.005 else None,
        })

    ap_opex = _por_departamento(a, b, "opex", nombres)
    ap_pay = _por_departamento(a, b, "payroll", nombres)
    ap_cost = _por_departamento(a, b, "cost", nombres)

    return {
        "meses": MESES,
        "base": a["escenario"], "comparado": b["escenario"],
        "meses_con_dato": {"base": a["meses_con_dato"], "comp": b["meses_con_dato"]},
        "kpis": {"base": ka, "comp": kb},
        "ingresos": ingresos,
        "clases": clases,
        "resultado": resultado,
        "departamentos": deptos,
        # Las tres aperturas por departamento, con los doce meses de cada año.
        # Van en la misma respuesta y no en tres endpoints: el resumen se lee
        # de una sola lectura del motor, y partirlo invitaría a que una pestaña
        # muestre un corte distinto de las otras.
        "aperturas": {
            "ingresos": {"titulo": "Ingresos por línea", "filas": ingresos,
                         "total": _totales(ingresos, "Total ingresos", +1)},
            "opex": {"titulo": "OPEX por departamento", "filas": ap_opex,
                     "total": _totales(ap_opex, "Total OPEX", -1)},
            "payroll": {"titulo": "Planilla por departamento", "filas": ap_pay,
                        "total": _totales(ap_pay, "Total planilla", -1)},
            "cost": {"titulo": "Costo de ventas por departamento", "filas": ap_cost,
                     "total": _totales(ap_cost, "Total costo", -1)},
        },
        "totales": {
            "ingresos": _totales(ingresos, "Total ingresos", +1),
            "clases": _totales(clases, "Gasto total", -1),
        },
        "narrativa": _narrativa(a, b, ka, kb, ingresos, resultado, deptos, clases),
    }


@router.get("/reports/resumen-anual/word/")
async def resumen_anual_word(
    base: str = Query(...),
    comparado: str = Query(...),
    propiedad: str = Query("Amarena"),
    _=Depends(get_current_user),
):
    """El mismo resumen, en Word.

    ⚠️ Llama al endpoint de arriba en vez de recalcular: así el documento y la
    pantalla son el MISMO número, no dos cálculos que casualmente coinciden.
    """
    from app.export.resumen_anual_word import DOCX, build_resumen_anual

    datos = await resumen_anual(base=base, comparado=comparado, _=None)
    blob = build_resumen_anual(datos, propiedad)
    nombre = "Resumen_Ejecutivo_{}_vs_{}.docx".format(
        datos["base"]["anio"], datos["comparado"]["anio"])
    return Response(
        content=blob, media_type=DOCX,
        headers={"Content-Disposition":
                 "attachment; filename*=UTF-8''" + quote(nombre)})
