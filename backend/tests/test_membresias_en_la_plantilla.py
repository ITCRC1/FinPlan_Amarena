# -*- coding: utf-8 -*-
"""Los socios del Club se pueden subir por la plantilla del Detalle.

Owner, 2026-09-08: *«la estadística también debe traer total membresías,
membresías condicionados, membresías pagando y membresías en acuerdo de pago;
el upload debe tener estas líneas para poder subir estas estadísticas»*.

Antes existían la tabla (`ClubMembershipStat`) y la pantalla, pero no había
cómo cargarlos con el archivo mensual: la plantilla no ofrecía las filas y el
importador no las reconocía. Los cuatro conteos quedaban en cero.
"""
import inspect
import json
import pathlib

CATALOGO = (pathlib.Path(__file__).resolve().parents[1]
            / "app" / "seed_data" / "stats_catalog.json")


def _catalogo():
    return json.loads(CATALOGO.read_text(encoding="utf-8"))["cuentas"]


def test_las_cuatro_estan_en_el_catalogo():
    codigos = {c["code"]: c for c in _catalogo()}
    for code in ("9800", "9801", "9802", "9803"):
        assert code in codigos, f"falta la cuenta estadística {code}"
        assert codigos[code]["grupo"] == "9800"


def test_el_total_del_anio_NO_es_la_suma_de_los_meses():
    """⚠️ Son socios, no ingresos.

    El valor del año es el PROMEDIO de los meses contados. Sumar los doce daría
    1.500 socios donde hay 129 — por eso `agrega` es PROM y no SUM.

    Owner, 2026-11-11: *«al año debe ser un promedio de los socios siempre…
    no se suman»*. Antes decía `FIN` —el saldo de diciembre—, que fue lo que
    se escribió cuando nacieron estas cuentas y que **nunca leyó nadie**: al
    implementarlo por primera vez el owner corrigió el criterio.
    """
    for c in _catalogo():
        if c["grupo"] == "9800":
            assert c["agrega"] == "PROM", (
                f"{c['code']} agrega como {c['agrega']}: el valor del año "
                f"dejaría de ser el promedio de los meses contados")


def test_el_importador_las_manda_a_su_propia_tabla():
    """No van a `ScenarioStat` con las de habitaciones: son otra tabla."""
    from app.importers import gl_detail_importer as gl

    assert set(gl.MEMBRESIA_BY_ACCT) == {"9800", "9801", "9802", "9803"}
    assert set(gl.MEMBRESIA_BY_ACCT.values()) == {
        "total", "condicionados", "pagando", "acuerdo_pago"}
    # Y que las recoja de verdad, no solo que exista el mapa.
    assert 'blk["membresias"]' in inspect.getsource(gl)


def test_al_subir_se_escriben_en_MembresiaMes():
    """Los socios que trae el archivo tienen que llegar a la base.

    Desde el 2026-11-13 van a `membresias_mes` y no a la tabla vieja de cuatro
    columnas, que se eliminó: aquélla guardaba el total como un campo aparte y
    podía contradecir a sus partes —llegó a decir 130 con 86 pagando—. Acá el
    total es la suma y no hay dos números sobre el mismo hecho.
    """
    from app.api import scenarios_api

    src = inspect.getsource(scenarios_api)
    assert "db.add(MembresiaMes(" in src, (
        "el importador dejó de escribir los socios: la plantilla los ofrece y "
        "el archivo los trae, pero no llegan a la base")
    assert "ClubMembershipStat" not in src, (
        "volvió una referencia a la tabla vieja, que ya no existe")


def test_solo_se_borra_el_mes_que_el_archivo_trae():
    """⚠️ Un archivo sin las líneas de socios NO puede dejar en cero un conteo
    que ya estaba. Es el mismo criterio que el merge usa para todo lo demás."""
    src = inspect.getsource(__import__(
        "app.api.scenarios_api", fromlist=["x"]))
    i = src.index("db.add(MembresiaMes(")
    bloque = src[max(0, i - 1600):i]
    assert "MembresiaMes.month.in_(meses_socios)" in bloque, (
        "el borrado dejó de acotarse a los meses que trae el archivo")
    assert "if membresias:" in bloque, (
        "un archivo sin líneas de socios no debe tocar el conteo")


def test_las_filas_solo_salen_si_el_club_esta_habilitado():
    """El owner avisó que el Club se va cuando se opere por fuera del hotel.

    Ese día se desmarca en Provisionamiento y estas cuatro filas desaparecen
    solas. Por eso la condición NO es un `if hotel == "AMA"`.
    """
    from app.api import scenarios_api
    from app.export import detail_excel

    assert len(detail_excel.MEMBRESIA_ROWS) == 4
    src = inspect.getsource(scenarios_api.export_scenario_detail)
    assert "DeptEnablement" in src and '"260"' in src, (
        "las filas de socios dejaron de mirar si el Club está habilitado")
    assert 'HOTEL_ID == "AMA"' not in src
