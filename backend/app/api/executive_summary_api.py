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
    DOCX, MESES, build_executive_summary, k, linea, pct, usd, var_pct,
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
    ("REV_ROOMS", "Habitaciones"), ("REV_FB", "A y B"), ("REV_SPA", "Spa"),
    ("REV_TOURS", "Tours"), ("REV_TRANSPORT", "Transporte"),
    ("REV_CLUB", "Club Madresal"), ("REV_LAUNDRY", "Lavandería"),
    ("REV_RETAIL", "Tienda"), ("REV_OTHER", "Otros ingresos"),
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


async def _forecast_current() -> str | None:
    """El Forecast que manda: el que el backend marca como current.

    Lo marca `is_current_forecast` —es el target de los uploads—, no se adivina
    por el nombre. Si no hay ninguno marcado, cualquiera del año del hotel: un
    forecast tiene los doce meses y el Actual no.
    """
    from app.db import get_session
    from app.hotel_actual import HOTEL_ID
    from app.models.scenario import Scenario
    from sqlalchemy import select

    async with get_session() as db:
        filas = (await db.execute(select(Scenario).where(
            Scenario.hotel_id == HOTEL_ID,
            Scenario.type == "FORECAST"))).scalars().all()
    if not filas:
        return None
    actual = next((f for f in filas if f.is_current_forecast), None)
    return str((actual or filas[0]).id)


async def _nombre_de_la_propiedad(pedido: str | None) -> str:
    """El nombre del hotel para la portada.

    ⚠️ La pantalla manda `HOTEL_ID` —«AMA»—, que es el código del despliegue y
    no un nombre: el informe del 30/09 salió con «AMA» bajo el título. El
    nombre vive en la tabla `hotels`, que es de este lado.
    """
    from app.db import get_session
    from app.hotel_actual import HOTEL_ID
    from app.models.hotel import Hotel

    if pedido and pedido.strip() and pedido.strip().upper() != HOTEL_ID.upper():
        return pedido.strip()
    async with get_session() as db:
        h = await db.get(Hotel, HOTEL_ID)
    return (h.name if h and h.name else (pedido or HOTEL_ID))


@router.post("/reports/executive-summary/word/")
async def resumen_ejecutivo_word(body: Cuerpo, _=Depends(get_current_user)):
    """El informe del mes, en .docx.

    ⚠️ **El decorador es de ESTA función.** Al agregar `_forecast_current` se
    coló entre el `@router.post` y el endpoint, y la ruta quedó registrada
    sobre el ayudante: el navegador bajaba un `.docx` de 38 bytes con el id del
    forecast adentro y Word decía «unreadable content». La ruta contestaba 200,
    así que en el log no se veía nada raro. Lo cuida
    `test_la_ruta_del_word_devuelve_un_DOCX`.
    """
    if not 1 <= body.mes <= 12:
        raise ErrorApi(422, "mes.rango_invalido")

    from app.api.gasto_por_clase_api import gasto_por_clase
    from app.api.pl_api import get_pl_compare

    # ⚠️ **El Forecast se resuelve acá si no vino.** Es la MISMA regla que la
    # pantalla y el Excel: el año completo se apoya en el Forecast Current,
    # esté o no en una ranura.
    #
    # Sin esto, el informe del 30/09 salió con la sección 1.3 diciendo «el
    # ingreso proyectado del año llegó a $306.1K, $242.2K POR DEBAJO de lo
    # presupuestado (-44.2%)»: era el Actual de ocho meses contra doce de
    # presupuesto. Todos los números estaban bien calculados y la conclusión era
    # falsa — el año no había terminado. Y la Sección 3 salía vacía.
    forecast_id = body.forecast_id or await _forecast_current()
    ids = [body.actual_id, body.budget_id] + (
        [forecast_id] if forecast_id else [])
    comp = await get_pl_compare(",".join(ids), month=body.mes)
    por_id = {v["scenario_id"]: v for v in comp["versions"]}
    act = por_id.get(body.actual_id)
    bud = por_id.get(body.budget_id)
    fcs = por_id.get(forecast_id) if forecast_id else None
    if not act or not bud:
        raise ErrorApi(404, "escenario.no_encontrado")

    # ── El gasto por clase, para el flow-through ─────────────────────────────
    # ⚠️ `detalle=True`: las secciones de detalle por departamento (1.x.1 a
    # 1.x.5) salen de ACÁ y no de una segunda consulta. Es el mismo agregador
    # que ya da el flow-through, así que el desglose suma exactamente el total
    # que el informe ya dijo dos párrafos antes.
    gpc = await gasto_por_clase(scenarios=",".join(ids), detalle=True)
    meses_de = {v["scenario_id"]: v["meses"] for v in gpc["escenarios"]}
    detalle_de = {v["scenario_id"]: (v.get("detalle") or {})
                  for v in gpc["escenarios"]}

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

    # ⚠️ La suma va con la lista y no se calcula en el informe: acá están los
    # números; allá, sólo cadenas ya formateadas (owner, 2026-09-30: *«sumas al
    # final de este cuadro»*).
    mix_total = None
    if mix:
        # ⚠️ **El total es el del MOTOR, no la suma de lo listado.** `TOTAL_
        # REVENUES` es el mismo renglón que el informe ya dijo dos páginas
        # antes; si acá sumara los renglones de la lista, el cuadro cerraría
        # contra sí mismo y contra nada más. Medido en agosto 2026: la lista da
        # 301.944,67 y el P&L dice 306.124,86 — se le escapan cuatro líneas de
        # ingreso que nadie declaró en `RENGLONES_MIX`.
        ta = linea(act["ytd"], "TOTAL_REVENUES")
        tb = linea(bud["ytd"], "TOTAL_REVENUES")
        # Y lo que falte se MUESTRA. Un cuadro cuyos renglones no suman su
        # propio total obliga a sacar la calculadora; peor, invita a pensar que
        # uno de los dos números está mal.
        ra = ta - sum(linea(act["ytd"], c) for c, _r in RENGLONES_MIX)
        rb = tb - sum(linea(bud["ytd"], c) for c, _r in RENGLONES_MIX)
        if abs(ra) >= 0.005 or abs(rb) >= 0.005:
            vr = var_pct(ra, rb)
            mix.append(["Otras líneas de ingreso", usd(ra), usd(rb), usd(ra - rb),
                        f"{vr * 100:+,.1f}%" if vr is not None else "n/d"])
        vt = var_pct(ta, tb)
        mix_total = ["Total ingresos", usd(ta), usd(tb), usd(ta - tb),
                     f"{vt * 100:+,.1f}%" if vt is not None else "n/d"]

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
                # El nombre del mes, no «03»: el informe se lee en español y un
                # número de dos cifras en la primera columna parece un código.
                MESES[m["month"] - 1], usd(float(kp.get("adr") or 0)),
                pct(float(kp.get("occupancy_pct") or 0)),
                f"{float(kp.get('rooms_occupied') or 0):,.0f}"])
    except Exception:
        adr_mes = []   # sin la serie el informe sale igual; sin informe, no

    # ── La estadística de la propiedad, para la Sección 2 ────────────────────
    #
    # Owner, 2026-09-30, pidiendo las secciones nuevas: *«2.4 Revenue por tipo
    # de Habitación. 2.5 Análisis de Canales. 2.6 Membresías Actuales»*.
    #
    # ⚠️ Los tres salen de los MISMOS endpoints que las pantallas: el año de
    # room stats trae el desglose por categoría y por canal, y las membresías su
    # propio mes. Rederivarlos acá sería una segunda verdad.
    #
    # ⚠️ Y los tres van en `try`: una propiedad puede no tener el PDF del PMS
    # cargado, o no tener Club. Sin la sección el informe sale igual; sin
    # informe, no.
    from app.api.membresias_api import get_membresias
    from app.api.room_stats_pdf_api import anio_room_stats
    from app.db import get_session

    room_stats: dict = {}
    membresias: dict = {}
    async with get_session() as db:
        try:
            room_stats = await anio_room_stats(body.actual_id, db=db)
        except Exception:
            room_stats = {}
        try:
            membresias = await get_membresias(body.actual_id, db=db)
        except Exception:
            membresias = {}

    # ── Positivos y negativos, ORDENADOS por tamaño ──────────────────────────
    positivos, negativos = _positivos_y_negativos(act, bud, fcs, totales, mix)

    etiqueta = lambda v: f"{v['type']} {v['version']} {v['year']}"  # noqa: E731
    datos = {
        "propiedad": await _nombre_de_la_propiedad(body.propiedad),
        "mes": body.mes,
        "anio": act["year"],
        "actual": act, "budget": bud, "forecast": fcs,
        "rotulos": {"actual": etiqueta(act), "budget": etiqueta(bud),
                    **({"forecast": etiqueta(fcs)} if fcs else {})},
        "totales": totales,
        "mix": mix,
        "mix_total": mix_total,
        # ── El desglose por departamento, para las secciones 1.x.1 a 1.x.5 ──
        #
        # Owner, 2026-09-30: *«quiero agregar más secciones»*, con el detalle de
        # ingresos, salarios, costo, opex y propiedad para cada uno de los tres
        # cortes.
        "detalle": detalle_de,
        "departamentos": gpc.get("departamentos") or {},
        "nombres_cuenta": {k: v for e in gpc["escenarios"]
                           for k, v in (e.get("nombres_cuenta") or {}).items()},
        "rangos": rangos,
        "room_stats": room_stats,
        "membresias": membresias,
        "ids": {"actual": body.actual_id, "budget": body.budget_id,
                "forecast": body.forecast_id},
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
    cuenta("Ingreso total",
           f"El ingreso llegó a {k(rev)} contra {k(revb)} presupuestados, una "
           f"diferencia de {k(rev - revb)}"
           + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
           rev >= revb)

    # Volumen y tarifa.
    occ_a = float((a.get("kpis") or {}).get("occupancy_pct") or 0)
    occ_b = float((b.get("kpis") or {}).get("occupancy_pct") or 0)
    noc_a = float((a.get("kpis") or {}).get("rooms_occupied") or 0)
    noc_b = float((b.get("kpis") or {}).get("rooms_occupied") or 0)
    cuenta("Demanda y volumen de huéspedes",
           f"Se vendieron {noc_a:,.0f} noches contra {noc_b:,.0f} presupuestadas, "
           f"con una ocupación de {pct(occ_a)} contra {pct(occ_b)}.",
           noc_a >= noc_b)
    adr_a = float((a.get("kpis") or {}).get("adr") or 0)
    adr_b = float((b.get("kpis") or {}).get("adr") or 0)
    vp = var_pct(adr_a, adr_b)
    cuenta("Tarifa promedio",
           f"La tarifa acumulada cerró en {usd(adr_a)} contra {usd(adr_b)} "
           f"presupuestados"
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
        cuenta(f"Ingreso de {rotulo}",
               f"{rotulo} llegó a {va} contra {vb} presupuestados, "
               f"{k(abs(d))} {'por encima' if d >= 0 else 'por debajo'} del plan.",
               d >= 0)

    # Los cuatro bloques de gasto.
    for clave, rotulo in (("TOTAL_PAYROLL", "Planilla y beneficios"),
                          ("TOTAL_OPEX_ONLY", "Gasto operativo"),
                          ("TOTAL_COST", "Costo de ventas"),
                          ("TOTAL_PROPERTY", "Gasto de propiedad")):
        ga, gb = totales(a, clave), totales(b, clave)
        vp = var_pct(ga, gb)
        # ⚠️ En gasto, MENOS es favorable. Con la regla del ingreso, un
        # sobrecosto entraría en la lista de positivos.
        cuenta(rotulo,
               f"{rotulo} cerró en {k(ga)} contra {k(gb)} presupuestados, "
               f"{k(abs(ga - gb))} {'por encima' if ga >= gb else 'por debajo'} "
               f"del plan"
               + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
               ga <= gb)

    # La conversión: EBITDA y Net Profit.
    for code, rotulo in (("EBITDA_BEFORE", "EBITDA antes de capital"),
                         ("NET_PROFIT", "Utilidad neta")):
        x, y = linea(a, code), linea(b, code)
        vp = var_pct(x, y)
        cuenta(rotulo,
               f"{rotulo} cerró en {k(x)} contra {k(y)} presupuestados, "
               f"{k(abs(x - y))} {'por encima' if x >= y else 'por debajo'} "
               f"del plan"
               + (f" ({vp * 100:+,.1f}%)" if vp is not None else "") + ".",
               x >= y)
    return pos, neg
