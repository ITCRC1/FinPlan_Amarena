# -*- coding: utf-8 -*-
"""Las membresías del Club bajan al Excel en vivo por el tab de estadísticas.

Owner, 2026-11-11: *«metelas en A y yo las saco de ahí, filtradas»*.

El tab de `consolidado/estadisticas/` servía una lista fija de once KPIs de
habitaciones sacados del P&L. Las membresías viven en `statistical_entries` y
no tenían por dónde salir: el puente las había cargado y el Excel no las veía.
"""
import pytest

from app.api.consolidado_api import (
    INDICADORES, MEMBRESIAS, _membresias_del_escenario,
)
from app.estadisticas.membresias_puente import CUENTAS


class _Fila:
    def __init__(self, account_code, month, value):
        self.account_code, self.month, self.value = account_code, month, value


class _Res:
    def __init__(self, filas):
        self._filas = filas

    def scalars(self):
        return self

    def all(self):
        return self._filas


class _Sesion:
    def __init__(self, filas):
        self._filas = filas

    async def execute(self, _stmt):
        return _Res(self._filas)


# ───────────────────────── Lo que no puede romperse ────────────────────────

@pytest.mark.asyncio
async def test_el_anio_es_el_ULTIMO_SALDO_y_no_la_suma():
    """⚠️ El error que no avisa. Son un padrón, no un flujo: sumar nueve meses
    de ~120 socios daría más de mil donde hay 130. El número saldría enorme y
    nadie sabría por qué."""
    filas = [_Fila("9800", m, v) for m, v in
             enumerate([100, 107, 112, 121, 123, 124, 110, 130, 130], start=1)]
    _por_mes, del_anio = await _membresias_del_escenario(_Sesion(filas), "esc")

    assert del_anio["club_total"] == 130, "tiene que ser el saldo, no la suma"
    assert del_anio["club_total"] != sum(f.value for f in filas)


@pytest.mark.asyncio
async def test_un_actual_a_mitad_de_anio_no_muestra_cero():
    """La regla escrita dice «el saldo de diciembre», pero un ACTUAL que va por
    septiembre no tiene diciembre. Tomarlo literal mostraría CERO socios en el
    año — se leería como que el Club se quedó vacío."""
    filas = [_Fila("9800", 9, 130)]          # sólo hasta septiembre
    _por_mes, del_anio = await _membresias_del_escenario(_Sesion(filas), "esc")
    assert del_anio["club_total"] == 130


@pytest.mark.asyncio
async def test_sin_membresias_no_revienta():
    """Un escenario sin Club baja en cero, no con un error."""
    por_mes, del_anio = await _membresias_del_escenario(_Sesion([]), "esc")
    assert por_mes == {}
    assert set(del_anio) == {k for k, _c, _n, _u in MEMBRESIAS}
    assert set(del_anio.values()) == {0.0}


@pytest.mark.asyncio
async def test_cada_cuenta_cae_en_su_indicador():
    filas = [_Fila("9802", 8, 92), _Fila("9801", 8, 33), _Fila("9805", 8, 1)]
    por_mes, _ = await _membresias_del_escenario(_Sesion(filas), "esc")
    assert por_mes[8] == {"club_activas": 92.0, "club_condicionados": 33.0,
                          "club_excepcion": 1.0}


# ───────────────────────── La forma del tab ────────────────────────────────

def test_las_claves_no_chocan_con_los_kpis_de_habitaciones():
    """Las dos listas se concatenan en una sola salida: una clave repetida
    haría que una pise a la otra en silencio."""
    rooms = {k for k, _n, _u in INDICADORES}
    club = {k for k, _c, _n, _u in MEMBRESIAS}
    assert not (rooms & club)


def test_toda_cuenta_del_puente_baja_al_excel():
    """Si el puente aprende una cuenta nueva (el `9806` del día que el Club
    agregue un estado) y nadie la agrega acá, ese conteo se carga, se guarda
    y NO baja. Esto lo frena."""
    en_el_tab = {c for _k, c, _n, _u in MEMBRESIAS}
    assert CUENTAS <= en_el_tab, f"no bajan al Excel: {CUENTAS - en_el_tab}"


def test_el_rotulo_permite_filtrarlas():
    """El owner las saca filtrando: *«yo las saco de ahí, filtradas»*. Sin un
    prefijo estable quedan mezcladas con los KPIs de habitaciones."""
    for _k, _c, nombre, _u in MEMBRESIAS:
        assert nombre.startswith("Club · "), nombre


def test_la_unidad_no_es_dinero_ni_porcentaje():
    """`estadisticas.m` multiplica por 100 lo que venga con unidad `%`. Una
    membresía marcada así bajaría como 13.000."""
    for _k, _c, _n, unidad in MEMBRESIAS:
        assert unidad == "socios"
