"""Checkbook OPEX en vivo (port de CWL, owner 2026-11-23).

En Amarena el endpoint NO usa el Excel de subida de OPEX (que allá sí cambió):
trae dos ayudantes propios. Estas pruebas fijan lo que el libro necesita de ellos.
"""
from app.api.consolidado_planilla_api import LUGARES, _hoja_de, _lugares_por_defecto, _seg3_de
from app.opex_detalle import CODIGOS


def test_seg3_de_respeta_los_codigos_800_810_de_amarena():
    for c in CODIGOS:
        assert _seg3_de(c) == c


def test_seg3_de_traduce_los_codigos_viejos_y_el_vacio():
    # Un «001» de antes del rango oficial es el 801; vacío o raro, el 800.
    assert _seg3_de("001") == "801"
    assert _seg3_de("010") == "810"
    assert _seg3_de("") == "800"
    assert _seg3_de(None) == "800"
    assert _seg3_de("abc") == "800"


def test_hoja_de_deja_al_depto_con_hoja_propia():
    assert _hoja_de("0190", {"0190", "0110"}) == "0190"


def test_los_seis_lugares_tienen_defecto():
    d = _lugares_por_defecto(2027, "Working", None)
    assert set(d) == set(LUGARES)
    assert d["MES"] == ("BUDGET", 2027, "Working", 12)
