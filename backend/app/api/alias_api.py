# -*- coding: utf-8 -*-
"""Los alias de cuenta: listarlos, escribirlos y pre-cargarlos.

Owner, 2026-11-27: *«crea el alias para mí y le pones lo mismo que el nombre de
la cuenta, y yo poco a poco con el tiempo voy renombrando el alias según mis
necesidades»*.

    GET    /alias/                 → todos, con el nombre real al lado
    PUT    /alias/                 → escribir o borrar uno — solo admin
    POST   /alias/precargar/       → crearlos todos con el nombre de hoy — admin

⚠️ **La pre-carga NO usa `account_name_example`**: usa lo que el reporte muestra
HOY, que es el nombre del mayor cuando existe. Sembrar con el nombre del
catálogo renombraría solo decenas de cuentas el día que se prenda el alias —un
cambio invisible en el total y visible en la cara del dueño.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alias_de_cuenta import AliasDeCuenta, limpiar
from app.auth import get_current_admin
from app.db import get_db
from app.errores import ErrorApi
from app.hotel_actual import HOTEL_ID
from app.models.mapping import AccountMapping

router = APIRouter(tags=["alias"])


class AliasIn(BaseModel):
    dept_code: str = ""
    account_code: str
    alias: str = ""          # vacío = borrar el alias y volver al nombre real
    nota: str = ""


def _fila(a: AliasDeCuenta, real: str = "") -> dict:
    return {"dept_code": a.dept_code, "account_code": a.account_code,
            "alias": a.alias, "nota": a.nota, "nombre_real": real,
            "escrito_por": a.escrito_por,
            "escrito_el": a.escrito_el.isoformat() if a.escrito_el else None}


async def _nombres_del_catalogo(db: AsyncSession) -> dict:
    """`(depto, cuenta) → account_name_example`, para mostrar el nombre real."""
    return {(m.dept_code or "", m.account_code): (m.account_name_example or "")
            for m in (await db.execute(select(AccountMapping).where(
                AccountMapping.active_status == "YES"))).scalars()}


@router.get("/alias/")
async def listar_alias(db: AsyncSession = Depends(get_db)):
    """Los alias de la propiedad, con el nombre del catálogo al lado.

    Los dos viajan juntos a propósito: un alias que tapa el nombre contable sin
    mostrarlo deja al owner sin saber qué cuenta está mirando cuando alguien
    renombre algo en Integrity.
    """
    cat = await _nombres_del_catalogo(db)
    filas = (await db.execute(select(AliasDeCuenta).where(
        AliasDeCuenta.hotel_id == HOTEL_ID).order_by(
        AliasDeCuenta.dept_code, AliasDeCuenta.account_code))).scalars().all()
    return {"hotel_id": HOTEL_ID, "total": len(filas),
            "alias": [_fila(a, cat.get((a.dept_code or "", a.account_code), ""))
                      for a in filas]}


@router.put("/alias/")
async def escribir_alias(body: AliasIn, user=Depends(get_current_admin),
                         db: AsyncSession = Depends(get_db)):
    """Escribe un alias. Mandarlo vacío lo BORRA y la cuenta vuelve a su nombre
    real: así se deshace sin tener que acordarse de cómo se llamaba."""
    cuenta = (body.account_code or "").strip()
    if not cuenta:
        raise ErrorApi(422, "alias.sin_cuenta")
    dept = (body.dept_code or "").strip()
    texto = limpiar(body.alias)

    fila = (await db.execute(select(AliasDeCuenta).where(
        AliasDeCuenta.hotel_id == HOTEL_ID,
        AliasDeCuenta.dept_code == dept,
        AliasDeCuenta.account_code == cuenta))).scalar_one_or_none()

    if not texto:
        if fila is not None:
            await db.delete(fila)
            await db.commit()
        return {"borrado": True, "dept_code": dept, "account_code": cuenta}

    if fila is None:
        fila = AliasDeCuenta(hotel_id=HOTEL_ID, dept_code=dept, account_code=cuenta)
        db.add(fila)
    fila.alias = texto
    fila.nota = (body.nota or "").strip()[:300]
    fila.escrito_por = getattr(user, "email", "") or ""
    await db.commit()
    await db.refresh(fila)
    cat = await _nombres_del_catalogo(db)
    return _fila(fila, cat.get((dept, cuenta), ""))


@router.post("/alias/precargar/")
async def precargar_alias(_=Depends(get_current_admin),
                          db: AsyncSession = Depends(get_db)):
    """Crea un alias por cada (departamento, cuenta) con el nombre de HOY.

    Owner: *«le pones lo mismo que el nombre de la cuenta y yo poco a poco voy
    renombrando»*. Después de esto **nada cambia en los reportes**: el alias
    dice lo mismo que ya decían. Lo que cambia es que hay dónde escribir.

    ⚠️ El nombre de hoy sale del MAYOR cuando existe, y sólo si no, del
    catálogo. Es el orden que ya usaban los reportes: sembrar con el del
    catálogo habría renombrado solas las cuentas donde contabilidad escribió
    distinto.

    No pisa lo que ya esté escrito: correrlo dos veces no deshace ediciones.
    """
    from sqlalchemy import text as _sql

    # Lo que el mayor trae, por (depto, cuenta). Una cuenta puede aparecer en
    # varios escenarios con nombres distintos: gana el más reciente cargado.
    del_mayor: dict[tuple[str, str], str] = {}
    for dept, cuenta, nombre in (await db.execute(_sql("""
        SELECT dept_code, account_code, account_name
          FROM actual_entries
         WHERE COALESCE(account_name, '') <> ''
         ORDER BY orden_archivo NULLS LAST
    """))).all():
        del_mayor[(dept or "", str(cuenta))] = nombre

    cat = await _nombres_del_catalogo(db)
    ya = {(a.dept_code or "", a.account_code) for a in (await db.execute(
        select(AliasDeCuenta).where(AliasDeCuenta.hotel_id == HOTEL_ID))).scalars()}

    creados = 0
    for llave in sorted(set(cat) | set(del_mayor)):
        if llave in ya:
            continue
        dept, cuenta = llave
        nombre = limpiar(del_mayor.get(llave) or cat.get(llave, "").split("|")[0])
        if not nombre:
            continue
        db.add(AliasDeCuenta(hotel_id=HOTEL_ID, dept_code=dept,
                             account_code=cuenta, alias=nombre,
                             nota="Pre-cargado con el nombre que ya mostraba el reporte"))
        creados += 1
    await db.commit()
    return {"creados": creados, "ya_estaban": len(ya),
            "nota": ("Los alias dicen lo mismo que los reportes ya decían: "
                     "nada cambió. Editá el que quieras renombrar.")}
