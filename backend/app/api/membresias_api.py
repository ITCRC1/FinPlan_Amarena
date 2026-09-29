# -*- coding: utf-8 -*-
"""Las membresías del club: leerlas, guardarlas a mano y subirlas por Excel.

Owner, 2026-09-29: *«que se pueda actualizar manualmente por mes. o que se
pueda bajar o subir con un excel»*.

## Qué NO hace este módulo

**No calcula el total.** Se devuelve calculado para pintar la pantalla, pero no
se guarda: el total es la suma de los conceptos y tenerlo escrito abre la
puerta a que digan cosas distintas —el modo de falla que no avisa— y a que
alguien «corrija» el total sin tocar los renglones.

**No toca el P&L.** Es un conteo de membresías, no plata. El día que la
propiedad quiera que la cuota entre al estado de resultados hay que decidir la
tarifa y por dónde entra, y eso es otra conversación.
"""
from __future__ import annotations

import calendar
import io
import re
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.errores import ErrorApi
from app.importers.registro_dep import registro_de_subida
from app.models.membresia_mes import CONCEPTOS, MembresiaMes
from app.models.scenario import Scenario

router = APIRouter(tags=["membresias"])

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

#: Clave canónica por concepto, para reconocer un rótulo que vuelve del Excel.
_POR_CLAVE = {c: r for c, r in CONCEPTOS}


def _cierre(year: int, month: int) -> str:
    """«31 de agosto 2026». El último día sale del calendario, no de una
    constante: febrero cambia con el año bisiesto."""
    return f"{calendar.monthrange(year, month)[1]} de {MESES[month - 1].lower()} {year}"


def _rotulo(concepto: str, year: int, month: int) -> str:
    plantilla = _POR_CLAVE.get(concepto)
    if plantilla is None:
        # ⚠️ Un concepto que no reconocemos NO se esconde: se muestra con su
        # clave. Esconderlo haría desaparecer un conteo que alguien cargó y el
        # total dejaría de cuadrar contra el papel sin que se vea por qué.
        return concepto
    return plantilla.format(cierre=_cierre(year, month))


def _norm(t: str) -> str:
    """Un rótulo comparable: sin acentos, sin comillas, sin dobles espacios."""
    t = (t or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n"), ("«", ""), ("»", ""), ('"', ""), ("“", ""),
                 ("”", ""), (" ", " ")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


#: Rótulo normalizado → clave. Se arma una vez y sirve para leer un Excel que
#: vino de la descarga: el rótulo de `activas` cambia con el mes, así que se
#: reconoce por su comienzo.
_POR_ROTULO = {_norm(r.split("{")[0]): c for c, r in CONCEPTOS}


def _concepto_de(rotulo: str) -> str | None:
    n = _norm(rotulo)
    if not n:
        return None
    if n in _POR_CLAVE:
        return n                      # vino la clave cruda
    for prefijo, clave in _POR_ROTULO.items():
        if prefijo and n.startswith(prefijo):
            return clave
    return None


async def _escenario(scenario_id: str, db: AsyncSession) -> Scenario:
    sc = (await db.execute(
        select(Scenario).where(Scenario.id == scenario_id))).scalar_one_or_none()
    if sc is None:
        raise ErrorApi(404, "escenario.no_existe_id", escenario=scenario_id)
    return sc


def _mes(filas: list[MembresiaMes], year: int, month: int) -> dict:
    """Un mes armado: los conceptos canónicos primero, y al final lo que no
    reconocemos. El total se CALCULA."""
    por_concepto = {f.concepto: float(f.cantidad) for f in filas}
    conceptos = []
    for clave, _plantilla in CONCEPTOS:
        conceptos.append({"concepto": clave,
                          "rotulo": _rotulo(clave, year, month),
                          "cantidad": por_concepto.pop(clave, 0.0)})
    for clave, cantidad in sorted(por_concepto.items()):
        conceptos.append({"concepto": clave, "rotulo": clave,
                          "cantidad": cantidad, "desconocido": True})
    return {
        "month": month,
        "mes_nombre": MESES[month - 1],
        "cierre": _cierre(year, month),
        # ⚠️ `cargado` es «alguien escribió este mes», no «el total da cero».
        # Un mes sin cargar y un mes en cero son afirmaciones distintas.
        "cargado": bool(filas),
        "conceptos": conceptos,
        "total": round(sum(c["cantidad"] for c in conceptos), 2),
    }


@router.get("/scenarios/{scenario_id}/membresias/")
async def get_membresias(scenario_id: str, db: AsyncSession = Depends(get_db)):
    """Los doce meses. Los que nadie cargó vienen con `cargado: false`."""
    sc = await _escenario(scenario_id, db)
    filas = (await db.execute(select(MembresiaMes).where(
        MembresiaMes.scenario_id == scenario_id))).scalars().all()
    por_mes: dict[int, list] = {m: [] for m in range(1, 13)}
    for f in filas:
        por_mes.setdefault(f.month, []).append(f)
    meses = [_mes(por_mes[m], sc.year, m) for m in range(1, 13)]
    return {
        "scenario_id": scenario_id, "year": sc.year,
        "escenario": f"{sc.type} {sc.version} {sc.year}",
        "meses": meses,
        "meses_cargados": [m["month"] for m in meses if m["cargado"]],
    }


class ConceptoIn(BaseModel):
    concepto: str
    cantidad: float = 0


class MembresiasMesIn(BaseModel):
    conceptos: list[ConceptoIn]


@router.put("/scenarios/{scenario_id}/membresias/{month}/")
async def put_membresias(
    scenario_id: str, month: int, body: MembresiasMesIn,
    db: AsyncSession = Depends(get_db),
):
    """Guarda (reemplaza) un mes.

    ⚠️ Reemplaza el mes ENTERO, igual que el resto del cierre: mandar la lista
    incompleta borra lo que falte. Es lo que hace que «guardar» signifique
    siempre lo mismo en esta pantalla.

    ⚠️ Un mes con todo en cero se BORRA en vez de guardarse en cero. `cargado`
    es «alguien escribió este mes»; dejar cinco ceros escritos haría que un mes
    que se vació a propósito se lea igual que un mes contado y sin membresías.
    """
    await _escenario(scenario_id, db)
    if not 1 <= month <= 12:
        raise ErrorApi(422, "mes.fuera_de_rango")

    await db.execute(delete(MembresiaMes).where(
        MembresiaMes.scenario_id == scenario_id, MembresiaMes.month == month))
    guardados = 0
    for c in body.conceptos:
        clave = (c.concepto or "").strip()
        if not clave or not c.cantidad:
            continue
        if c.cantidad < 0:
            raise ErrorApi(422, "membresias.cantidad_negativa",
                           concepto=clave, cantidad=c.cantidad)
        db.add(MembresiaMes(id=str(uuid.uuid4()), scenario_id=scenario_id,
                            month=month, concepto=clave, cantidad=c.cantidad))
        guardados += 1
    await db.commit()
    return {"saved": True, "month": month, "conceptos_saved": guardados}


# ⚠️ Esta puerta ESCRIBE, asi que registra el archivo — al reves que los
# lectores del cierre, que leen y descartan. El registro es lo que frena
# volver a subir el mismo archivo por accidente y sobreescribir un conteo
# que alguien ya corrigio a mano.
@router.post("/scenarios/{scenario_id}/membresias/importar/",
             dependencies=[Depends(registro_de_subida)])
async def importar_membresias(
    scenario_id: str, file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Sube el Excel que bajó esta misma pantalla, y escribe los meses que trae.

    Owner: *«o que se pueda bajar o subir con un excel»*. Lee **el mismo
    formato que produce la descarga** —conceptos en filas, meses en columnas—
    para que el viaje de ida y vuelta sea el mismo papel.

    ⚠️ **Sólo escribe los meses que el archivo trae con algún número.** Una
    columna vacía se deja como está: si borrara el mes, bajar el Excel, tocar
    agosto y volver a subirlo se llevaría los otros once por delante.

    ⚠️ Un rótulo que no se reconoce **no se inventa ni se descarta**: se
    reporta. Adivinar a qué concepto se parece mandaría un conteo al renglón
    equivocado y el total seguiría dando lo mismo.
    """
    sc = await _escenario(scenario_id, db)
    raw = await file.read()
    if not raw:
        raise ErrorApi(422, "skill4.archivo_vacio")

    try:
        filas = _leer_libro(raw, file.filename or "")
    except ValueError as e:
        raise ErrorApi(422, "membresias.no_se_pudo_leer", detalle=str(e))
    except Exception as e:  # noqa: BLE001 - un Excel corrupto no es un 500
        raise ErrorApi(422, "membresias.no_se_pudo_leer", detalle=str(e))

    cabecera, cuerpo = filas[0], filas[1:]
    # Qué mes es cada columna. Se reconoce por el nombre del mes en cualquier
    # parte del rótulo: «Ago», «Agosto», «Agosto 2026» y «Ago 2026» son el mismo.
    columnas: dict[int, int] = {}
    for i, celda in enumerate(cabecera[1:], start=1):
        n = _norm(str(celda or ""))
        if not n or n.startswith("total"):
            continue
        for m, nombre in enumerate(MESES, start=1):
            if n.startswith(_norm(nombre)[:3]):
                columnas[i] = m
                break
    if not columnas:
        raise ErrorApi(422, "membresias.sin_meses")

    # concepto -> {mes: cantidad}
    leido: dict[str, dict[int, float]] = {}
    desconocidos: list[str] = []
    for fila in cuerpo:
        rotulo = str(fila[0] or "").strip() if fila else ""
        if not rotulo or _norm(rotulo).startswith("total"):
            continue                       # la fila del total no se importa
        clave = _concepto_de(rotulo)
        if clave is None:
            desconocidos.append(rotulo)
            continue
        for i, mes in columnas.items():
            if i >= len(fila):
                continue
            v = _numero(fila[i])
            if v is not None:
                leido.setdefault(clave, {})[mes] = v
    if desconocidos:
        raise ErrorApi(422, "membresias.concepto_desconocido",
                       desconocidos=", ".join(sorted(set(desconocidos))),
                       validos=", ".join(c for c, _ in CONCEPTOS))
    if not leido:
        raise ErrorApi(422, "membresias.sin_datos")

    meses_con_dato = sorted({m for v in leido.values() for m in v})
    for mes in meses_con_dato:
        await db.execute(delete(MembresiaMes).where(
            MembresiaMes.scenario_id == scenario_id, MembresiaMes.month == mes))
        for clave, por_mes in leido.items():
            cantidad = por_mes.get(mes, 0.0)
            if not cantidad:
                continue
            db.add(MembresiaMes(id=str(uuid.uuid4()), scenario_id=scenario_id,
                                month=mes, concepto=clave, cantidad=cantidad))
    await db.commit()
    return {"saved": True, "year": sc.year,
            "meses": meses_con_dato,
            "meses_nombre": [MESES[m - 1] for m in meses_con_dato]}


def _numero(v) -> float | None:
    """Una celda. `None` = vacía, que NO es cero: una columna sin número se
    deja como está en vez de borrar el mes."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _leer_libro(raw: bytes, nombre: str) -> list[list]:
    if nombre.lower().endswith(".csv"):
        import csv
        return [list(r) for r in csv.reader(
            io.StringIO(raw.decode("utf-8-sig", errors="replace")))]

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    for ws in wb.worksheets:
        filas = [list(f) for f in ws.iter_rows(values_only=True)]
        # La hoja buena es la que tiene un concepto conocido en la primera
        # columna. Pedirle a la persona que la renombre sería un paso más que
        # se puede equivocar.
        for i, f in enumerate(filas[:30]):
            if f and _concepto_de(str(f[0] or "")) is not None:
                # La cabecera es la última fila no vacía antes del primer
                # concepto: ahí están los meses.
                cab = next((filas[j] for j in range(i - 1, -1, -1)
                            if any(x is not None for x in filas[j])), [])
                return [cab] + filas[i:]
    raise ValueError(
        "no se encontró la tabla: hace falta una columna con los conceptos "
        "(" + ", ".join(r.split("{")[0].strip() for _, r in CONCEPTOS) + ")")
