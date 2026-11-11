# -*- coding: utf-8 -*-
"""El puente de membresías → cuentas estadísticas 98xx.

Owner, 2026-11-11: *«por qué estas estadísticas no quedaron mapeadas»*.

Había dos tablas de membresías y el catálogo apuntaba a la vieja. Estas
pruebas vigilan el puente nuevo y, sobre todo, las dos formas en que puede
volver a romperse **sin dar error**: que un concepto desaparezca en silencio, y
que el total del año se sume en vez de tomarse de diciembre.
"""
import json
import pathlib
from decimal import Decimal

import pytest

from app.estadisticas.membresias_puente import (
    CONCEPTO_A_CUENTA, CUENTA_TOTAL, CUENTAS, DEPT_CLUB, ORIGEN,
    sincronizar_membresias,
)
from app.models.membresia_mes import CONCEPTOS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "app/seed_data/stats_catalog.json"


def _cuentas_del_catalogo() -> dict[str, dict]:
    d = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return {c["code"]: c for c in d["cuentas"]}


# ─────────────────── Lo que no puede volver a pasar ────────────────────────

def test_todo_concepto_de_la_pantalla_tiene_cuenta():
    """El bug original: la pantalla tenía CINCO conceptos y el catálogo CUATRO
    cuentas, así que «pendiente de firma» y «excepción no paga» no tenían
    dónde caer. Si alguien agrega un concepto a `CONCEPTOS` sin darle cuenta,
    esto lo frena acá y no seis meses después en un reporte que no cuadra."""
    faltan = [c for c, _rotulo in CONCEPTOS if c not in CONCEPTO_A_CUENTA]
    assert not faltan, f"conceptos sin cuenta estadística: {faltan}"


def test_las_cuentas_existen_en_el_catalogo_sembrado():
    """⚠️ El catálogo se re-afirma desde `stats_catalog.json` en CADA deploy
    (`seed_stats.py`). Una cuenta creada sólo por migración se borra sola en
    el despliegue siguiente, y lo hace sin error: el puente escribiría contra
    una cuenta que no existe."""
    cat = _cuentas_del_catalogo()
    for cuenta in sorted(CUENTAS):
        assert cuenta in cat, f"{cuenta} no está en stats_catalog.json"


def test_las_cuentas_no_se_suman_a_lo_largo_del_anio():
    """`agrega=PROM`: el año es el PROMEDIO de los meses contados.

    Owner, 2026-11-11: *«al año debe ser un promedio de los socios siempre…
    no se suman»*. Son socios, no ingresos — sumarlos daría 1.500 donde hay
    129.

    ⚠️ El catálogo y el código tienen que decir lo mismo. Decía `FIN` —el
    saldo de diciembre— y nunca lo leyó nadie; al implementarlo por primera
    vez el owner corrigió el criterio y las dos puntas se cambiaron juntas."""
    cat = _cuentas_del_catalogo()
    for cuenta in sorted(CUENTAS):
        assert cat[cuenta]["agrega"] == "PROM", (
            f"{cuenta} agrega={cat[cuenta]['agrega']}: el valor del año no "
            "sería el promedio y multiplicaría o hundiría los socios")


def test_las_cuentas_son_del_departamento_del_club():
    cat = _cuentas_del_catalogo()
    for cuenta in sorted(CUENTAS):
        assert cat[cuenta]["deptos"] == [DEPT_CLUB]


# ─────────────────────────── El volcado ────────────────────────────────────

class _Fila:
    def __init__(self, month, concepto, cantidad):
        self.month, self.concepto, self.cantidad = month, concepto, cantidad


class _Db:
    """Lo mínimo de una sesión: qué se borró y qué se agregó."""
    def __init__(self, filas):
        self._filas, self.agregadas, self.borrados = filas, [], []

    async def execute(self, stmt):
        self.borrados.append(stmt)
        return _Res(self._filas)

    async def flush(self):
        pass

    def add(self, obj):
        self.agregadas.append(obj)


class _Res:
    def __init__(self, filas):
        self._filas = filas

    def scalars(self):
        return self

    def all(self):
        return self._filas


@pytest.mark.asyncio
async def test_el_total_es_la_suma_de_los_conceptos_del_mes():
    """Los números reales de Amarena, agosto 2026: 92+33+2+2+1 = 130."""
    db = _Db([
        _Fila(8, "activas", 92), _Fila(8, "condicionados", 33),
        _Fila(8, "pendiente_firma", 2), _Fila(8, "plan_pago", 2),
        _Fila(8, "excepcion", 1),
    ])
    r = await sincronizar_membresias(db, "esc-1")

    total = [e for e in db.agregadas if e.account_code == CUENTA_TOTAL]
    assert len(total) == 1
    assert total[0].value == Decimal("130")
    assert total[0].month == 8 and total[0].dept_code == DEPT_CLUB
    assert r["sin_cuenta"] == []
    # Cinco conceptos + el total.
    assert r["valores_escritos"] == 6


@pytest.mark.asyncio
async def test_un_concepto_desconocido_se_INFORMA_no_se_esconde():
    """⚠️ El modo de falla que no avisa. `membresias_mes` guarda un concepto
    por fila justamente para que un estado nuevo del club no cueste una
    migración; este catálogo usa códigos fijos. Cuando aparezca la «tercera
    etapa», el concepto se va a cargar bien y no va a tener cuenta.

    Descartarlo en silencio dejaría el estadístico corto sin que nada lo diga.
    Tiene que salir en `sin_cuenta` — y el TOTAL tiene que seguir incluyéndolo,
    porque es el total que muestra la pantalla."""
    db = _Db([
        _Fila(9, "activas", 92),
        _Fila(9, "tercera_etapa", 7),      # el día que exista
    ])
    r = await sincronizar_membresias(db, "esc-1")

    assert r["sin_cuenta"] == ["tercera_etapa"]
    total = [e for e in db.agregadas if e.account_code == CUENTA_TOTAL][0]
    assert total.value == Decimal("99"), (
        "el total del estadístico tiene que cuadrar contra el de la pantalla, "
        "incluido lo que todavía no tiene cuenta")


@pytest.mark.asyncio
async def test_un_mes_sin_filas_no_se_escribe_en_cero():
    """Un mes que nadie contó NO es un mes con cero socios. La pantalla lo
    deja en blanco; el estadístico también."""
    db = _Db([_Fila(1, "activas", 62)])
    r = await sincronizar_membresias(db, "esc-1")

    assert r["meses"] == [1]
    assert {e.month for e in db.agregadas} == {1}


@pytest.mark.asyncio
async def test_lo_que_escribe_queda_marcado_como_del_motor():
    """`origen=MOTOR` es lo que permite rehacerlo sin pisar un conteo que
    alguien cargó por archivo o a mano."""
    db = _Db([_Fila(1, "activas", 62)])
    await sincronizar_membresias(db, "esc-1")
    assert {e.origen for e in db.agregadas} == {ORIGEN}


@pytest.mark.asyncio
async def test_activas_va_a_la_cuenta_de_pagando():
    """Los rótulos difieren —«activas de cobro» contra «pagando»— pero es el
    mismo hecho. Se mantiene el código viejo para no romper el histórico que
    ya se reporta con él."""
    assert CONCEPTO_A_CUENTA["activas"] == "9802"
