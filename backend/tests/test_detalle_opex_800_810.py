# -*- coding: utf-8 -*-
"""Las sub-líneas de OPEX van de 800 a 810, y ninguna ruta se sale.

Owner, 2026-11-12: *«debe ir de 800 a 810»*.

El rango estaba en el CLAUDE.md desde el principio y **las cuatro rutas que
crean una línea lo ignoraban**, cada una a su manera. Una cuenta de Amarena
llegó a tener 101 filas con dos numeraciones conviviendo. Estas pruebas
vigilan que ninguna vuelva a inventar un código.
"""
import pathlib
import re

import pytest

from app.opex_detalle import (
    CODIGOS, PRIMERO, ULTIMO, es_valido, libres, siguiente, varios,
)

API = pathlib.Path(__file__).resolve().parent.parent / "app/api"


# ────────────────────────────── El rango ────────────────────────────────────

def test_son_once_de_800_a_810():
    assert CODIGOS == [str(n) for n in range(800, 811)]
    assert len(CODIGOS) == 11
    assert PRIMERO == 800 and ULTIMO == 810


def test_lo_de_afuera_no_vale():
    for malo in ("001", "811", "799", "", None, "0", "8100"):
        assert not es_valido(malo), malo
    for bueno in CODIGOS:
        assert es_valido(bueno)


# ──────────────────── El botón «+10 líneas» ─────────────────────────────────

def test_una_cuenta_llena_no_entrega_un_doceavo():
    """⚠️ El bug original. El botón hacía `max+1` sin techo: una cuenta en 810
    recibía 811, el usuario lo veía como una línea más, y el Excel lo traía de
    vuelta dejando el desorden fijo."""
    assert siguiente(CODIGOS) is None
    assert varios(CODIGOS, 10) == []


def test_un_codigo_vacio_no_reinicia_la_numeracion():
    """⚠️ La segunda falla, la que hizo las 101 filas. `int('')` reventaba, el
    máximo quedaba en CERO y empezaba `001, 002…` al lado de lo que ya estaba.
    Una fila vacía no ocupa ningún código del rango, así que el próximo libre
    sigue siendo el primero."""
    assert siguiente([""]) == "800"
    assert siguiente(["", "001", "002"]) == "800"


def test_pedir_mas_de_lo_que_cabe_entrega_lo_que_cabe():
    """Pedir diez cuando quedan tres entrega tres. Fallar entero obligaría al
    usuario a adivinar cuántas caben antes de pedirlas."""
    usados = CODIGOS[:8]
    assert varios(usados, 10) == ["808", "809", "810"]
    assert varios(usados, 2) == ["808", "809"]


def test_sigue_por_el_hueco_y_no_por_el_maximo():
    """Si 805 quedó libre, el próximo es 805 — no 811."""
    usados = [c for c in CODIGOS if c != "805"]
    assert siguiente(usados) == "805"


def test_libres_ignora_lo_que_esta_fuera_de_rango():
    """Un `001` viejo no ocupa cupo: justamente se lo quiere reubicar adentro."""
    assert libres(["001", "002", "800"]) == CODIGOS[1:]


# ─────────────── Que ninguna ruta vuelva a inventar un código ───────────────

@pytest.mark.parametrize("archivo", ["opex_api.py", "scenarios_api.py"])
def test_ninguna_ruta_escribe_un_codigo_a_mano(archivo):
    """⚠️ Arreglar esto ruta por ruta es cómo se llegó al desorden. Si alguien
    vuelve a poner un `"001"` literal o un `zfill(3)`, esto lo frena."""
    t = (API / archivo).read_text(encoding="utf-8")
    # Sólo las líneas que ASIGNAN un detail_code, no los comentarios.
    for linea in t.splitlines():
        if "detail_code" not in linea or linea.strip().startswith("#"):
            continue
        assert "zfill" not in linea, f"{archivo}: correlativo a mano → {linea.strip()}"
        assert not re.search(r'detail_code\s*[=:]\s*["\']0\d\d["\']', linea), \
            f"{archivo}: código literal fuera del rango → {linea.strip()}"
