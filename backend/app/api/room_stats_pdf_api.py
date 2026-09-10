# -*- coding: utf-8 -*-
"""Cierre de mes · Estadística de habitaciones desde el PDF del PMS.

Owner, 2026-09-09: *«la idea es que se suba el documento y se lea la
información pero que no se guarde — solo se tomen los datos y ya»* · *«esto
debe quedar en cierre de mes»* · *«Amarena no tiene Opera»*.

## Qué hace y qué NO hace

**Lee. Nada más.** Este endpoint no escribe una sola fila. Recibe el PDF de
Skill4, lo parsea en memoria, devuelve las filas ya alineadas a las categorías
de la propiedad y descarta el archivo. Guardar es un segundo paso explícito, y
lo hace el endpoint que ya existía para la carga manual:
`PUT /scenarios/{id}/room-stats-entry/{month}/`.

⚠️ **Esa separación es la funcionalidad, no una comodidad de diseño.** El PDF
trae los nombres de categoría del PMS («BEACH FRONT DLXE VILLA») y la base
guarda los nombres de la propiedad (`RoomTypeConfig.name`). Si esto guardara
solo, una categoría cuyo nombre no coincide se archivaría bajo un rótulo que
el reporte no busca: las noches entran, el Room Stats sigue en cero y **nada
avisa**. Es el mismo modo de falla que el comentario de
`revenue_api._canonical_room_types` documenta para Amarena. Por eso acá se
propone el calce, se marca lo que no calzó, y **una persona confirma**.

## Por qué no se reusa el importador de Opera

`room_stats_importer.py` lee la hoja «Room Stats» del paquete ejecutivo de
Opera. **Amarena no tiene Opera.** Su PMS es Skill4 y lo que emite es un PDF
por mes — otro formato, otras columnas, otro archivo. El lector vive en
`importers/skill4_room_stats_pdf.py`; acá solo se lo conecta a la pantalla.

## De dónde sale cada número

| Campo del Room Stats | De dónde |
|---|---|
| `nights_occupied` | Estancias de **Habitaciones** del PDF |
| `pax` | Estancias de **Clientes** (noches-huésped) |
| `revenue` | Ing. Hospedaje |
| `units` / `nights_available` | **De `RoomTypeConfig`, no del PDF** |

⚠️ **Las noches disponibles NO vienen del PDF por categoría.** El resumen las
da solo a nivel hotel y en dos versiones que no coinciden: 496 (inventario
completo) y 238 (descontando 258 bloqueadas en marzo 2026). Se usa
`units × días`, que es exactamente lo que ya hace la carga manual — así el
Room Stats no cambia de vara según cómo entró el mes. Las dos cifras del PDF
viajan en `resumen` para que se vean en pantalla y se decida mirando, no
adivinando.
"""
from __future__ import annotations

import calendar
import unicodedata

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errores import ErrorApi
from app.hotel_actual import HOTEL_ID
from app.importers.skill4_room_stats_pdf import leer_pdf_skill4, nombre_del_mes
from app.models.actual_room_stat import ActualRoomStat
from app.models.room_type_config import RoomTypeConfig
from app.models.scenario import Scenario

router = APIRouter(tags=["cierre-room-stats"])

#: Rótulo de la fila que recoge el ingreso de habitaciones sin categoría.
#: Es el MISMO literal que usa `revenue_api`, a propósito: las dos pantallas
#: escriben en `actual_room_stats` y un rótulo distinto crearía una segunda
#: fila fantasma para el mismo concepto.
OTROS_ROOMS = "Other Rooms Revenue"

#: Abreviaturas del PMS que no son palabras. Sin esto «DLXE» nunca calza con
#: «DELUXE» y toda categoría de Amarena entraría sin sugerencia de calce.
_SINONIMOS = {
    "DLXE": "DELUXE", "DLX": "DELUXE", "DBL": "DOUBLE", "STD": "STANDARD",
    "STE": "SUITE", "STES": "SUITES", "APTO": "APARTAMENTO", "HAB": "HABITACION",
    "VLL": "VILLA", "JR": "JUNIOR", "KG": "KING", "QN": "QUEEN",
}
#: Palabras que no distinguen una categoría de otra: si el calce se apoyara en
#: ellas, «BEACH FRONT DLXE VILLA» y «GARDEN VIEW DLXE VILLA» empatarían.
_VACIAS = {"DE", "DEL", "LA", "EL", "CON", "Y", "BED", "BEDS", "CAMA", "CAMAS"}


def _normalizar(texto: str) -> str:
    """Mayúsculas, sin acentos, sin puntuación, espacios colapsados."""
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s.upper())
    return " ".join(s.split())


def _tokens(texto: str) -> set:
    return {_SINONIMOS.get(p, p) for p in _normalizar(texto).split()} - _VACIAS


def _calce(nombre_pdf: str, categorias: list) -> tuple:
    """Elige la categoría de la propiedad que mejor calza con la del PDF.

    Devuelve `(RoomTypeConfig | None, confianza)`. `confianza` es
    `'exacto'`, `'probable'` o `'ninguno'` — y la pantalla la muestra: un
    calce por parecido que nadie revisó es la forma de archivar las noches
    bajo la categoría equivocada.
    """
    objetivo = _tokens(nombre_pdf)
    if not objetivo:
        return None, "ninguno"
    for c in categorias:
        if _tokens(c.name) == objetivo or _tokens(c.short_name) == objetivo:
            return c, "exacto"
    mejor, mejor_puntaje = None, 0.0
    for c in categorias:
        for candidato in (_tokens(c.name), _tokens(c.short_name)):
            if not candidato:
                continue
            comunes = objetivo & candidato
            if not comunes:
                continue
            # Jaccard: penaliza tanto lo que falta como lo que sobra.
            puntaje = len(comunes) / len(objetivo | candidato)
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = c, puntaje
    if mejor is not None and mejor_puntaje >= 0.5:
        return mejor, "probable"
    return None, "ninguno"


async def _escenario(scenario_id: str, db: AsyncSession) -> Scenario:
    sc = (await db.execute(
        select(Scenario).where(Scenario.id == scenario_id))).scalar_one_or_none()
    if sc is None:
        raise ErrorApi(404, "escenario.no_existe_id", escenario=scenario_id)
    return sc


@router.post("/scenarios/{scenario_id}/room-stats/leer-pdf/")
async def leer_pdf_room_stats(
    scenario_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Lee el PDF de Skill4 y devuelve el mes ya armado. **No guarda nada.**

    El archivo se descarta al terminar la petición: no se escribe a disco, no
    se guarda en la base y no pasa por el registro de subidas (ese registro
    existe para frenar reimports, y acá no hay import que frenar).

    Lo que vuelve alcanza para pintar la pantalla y para guardar después con
    `PUT /scenarios/{id}/room-stats-entry/{month}/` sin volver a subir el PDF.
    """
    sc = await _escenario(scenario_id, db)
    raw = await file.read()
    if not raw:
        raise ErrorApi(422, "skill4.archivo_vacio")
    try:
        lectura = leer_pdf_skill4(raw)
    except ValueError as e:
        raise ErrorApi(422, "skill4.no_se_pudo_leer", detalle=str(e))
    except Exception as e:  # noqa: BLE001 - un PDF corrupto no debe ser un 500
        raise ErrorApi(422, "skill4.no_se_pudo_leer", detalle=str(e))

    # ⚠️ El año del PDF tiene que ser el del escenario. Sin esta comparación,
    # el PDF de marzo 2025 entraría como marzo del escenario 2026 —mismo mes,
    # otro año— y el reporte no tendría cómo notarlo.
    if lectura.year != sc.year:
        raise ErrorApi(422, "skill4.ano_no_coincide",
                       ano_archivo=lectura.year, ano_escenario=sc.year)

    categorias = (await db.execute(
        select(RoomTypeConfig)
        .where(RoomTypeConfig.hotel_id == HOTEL_ID, RoomTypeConfig.active == True)  # noqa: E712
        .order_by(RoomTypeConfig.sort_order)
    )).scalars().all()

    dias = calendar.monthrange(lectura.year, lectura.month)[1]
    ya_cargado = {s.room_type_name: s for s in (await db.execute(select(ActualRoomStat).where(
        ActualRoomStat.scenario_id == scenario_id,
        ActualRoomStat.month == lectura.month))).scalars().all()}

    filas, sin_calce = [], []
    usadas = set()
    for t in lectura.por_tipo():
        cat, confianza = _calce(t["room_type_name"], categorias)
        if cat is not None and cat.name in usadas:
            # Dos categorías del PDF apuntando a la misma de la propiedad:
            # sumarlas en silencio perdería una. Se manda a revisión manual.
            cat, confianza = None, "ninguno"
        if cat is not None:
            usadas.add(cat.name)
        else:
            sin_calce.append(t["room_type_name"])
        anterior = ya_cargado.get(cat.name) if cat is not None else None
        filas.append({
            "nombre_pdf": t["room_type_name"],
            "room_type_name": cat.name if cat is not None else None,
            "room_type_code": cat.code if cat is not None else "",
            "confianza": confianza,
            "units": cat.units if cat is not None else 0,
            "nights_available": (cat.units * dias) if cat is not None else 0,
            "nights_occupied": t["nights_occupied"],
            "pax": t["pax"],
            "revenue": t["revenue"],
            "adr": t["adr"],
            "hab_entradas": t["hab_entradas"],
            "cli_entradas": t["cli_entradas"],
            "agencias": [
                {"agencia": f.agencia, "revenue": round(f.ingreso_hospedaje, 2),
                 "nights_occupied": f.hab_estancias, "pax": f.cli_estancias,
                 "hab_entradas": f.hab_entradas, "cli_entradas": f.cli_entradas,
                 "tarifa_promedio": f.tarifa_promedio}
                for f in lectura.filas if f.room_type_name == t["room_type_name"]
            ],
            # Lo que hoy hay guardado para esa categoría, para que se vea qué
            # se estaría pisando antes de apretar Guardar.
            "actual_guardado": None if anterior is None else {
                "nights_occupied": float(anterior.nights_occupied),
                "pax": float(anterior.pax), "revenue": float(anterior.revenue)},
        })

    # Categorías de la propiedad que el PDF no trajo. Van igual, en cero: el
    # guardado reemplaza el mes entero, y omitirlas dejaría viva la cifra de
    # una carga anterior sin que se vea en la pantalla que la reemplazó.
    calzadas = {f["room_type_name"] for f in filas if f["room_type_name"]}
    ausentes = [c.name for c in categorias if c.name not in calzadas]

    noches = sum(f["nights_occupied"] for f in filas)
    ingreso = round(sum(f["revenue"] for f in filas), 2)
    r = lectura.resumen
    return {
        "guardado": False,           # este endpoint NUNCA guarda
        "archivo": file.filename,
        "entidad": lectura.entidad,
        "scenario_id": scenario_id,
        "year": lectura.year,
        "month": lectura.month,
        "mes_nombre": nombre_del_mes(lectura.month),
        "moneda": lectura.moneda,
        "dias_del_mes": dias,
        "filas": filas,
        "categorias_sin_calce": sin_calce,
        "categorias_ausentes_en_el_pdf": ausentes,
        "mes_ya_tiene_datos": bool(ya_cargado),
        "totales": {
            "nights_occupied": noches,
            "pax": sum(f["pax"] for f in filas),
            "revenue": ingreso,
            "adr": round(ingreso / noches, 2) if noches else 0.0,
            "nights_available_config": sum(f["nights_available"] for f in filas),
        },
        "resumen_pdf": {
            "dias": r.dias,
            "capacidad_hab": r.capacidad_hab,
            "habitaciones_totales": r.habitaciones_totales,
            "habitaciones_disponibles": r.habitaciones_disponibles,
            "habitaciones_bloqueadas": r.habitaciones_bloqueadas,
            "ocupacion_sobre_total": r.ocupacion_sobre_total,
            "ocupacion_sobre_disponibles": r.ocupacion_sobre_disponibles,
            "ingreso_hospedaje": r.ingreso_hospedaje,
            "ingreso_puntos_venta": r.ingreso_puntos_venta,
            "ingreso_otros": r.ingreso_otros,
            "ingreso_total_hotel": r.ingreso_total_hotel,
        },
        # Vacío = la suma del detalle da los totales que el propio archivo
        # declara. Con algo adentro, el archivo y lo leído se separaron.
        "avisos_de_cuadre": lectura.cuadre(),
    }
