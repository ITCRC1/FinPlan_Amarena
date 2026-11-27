# -*- coding: utf-8 -*-
"""El alias manda sobre el nombre del mayor, y vive fuera del mapeo.

Owner, 2026-11-27: «quiero que sea editable un tipo ALIAS para poner como quiero
que salga en los reportes finales» · «hay cuentas que se repiten en varios
departamentos… Cleaning Rooms o Cleaning F&B, y ninguno se ve afectado» · «el GL
actual debe ser igual, solo agregamos una columna adicional».
"""
import pathlib

from app.alias_de_cuenta import limpiar, resolver

RAIZ = pathlib.Path(__file__).resolve().parents[1]


# ─────────────────────────── El orden de prioridad ──────────────────────────

def test_el_alias_le_gana_al_nombre_del_mayor():
    """Es la razón de ser: antes mandaba lo que contabilidad tipeó en Integrity
    y editar el mapeo no cambiaba lo que bajaba al reporte."""
    alias = {("0110", "7065"): "Cleaning Rooms"}
    assert resolver(alias, "0110", "7065",
                    del_mayor="CLEANING SUPPLIES1",
                    del_catalogo="Cleaning Supplies") == "Cleaning Rooms"


def test_sin_alias_sigue_mandando_el_mayor():
    """Quitar un alias devuelve la cuenta a su nombre real: deshacer no obliga
    a acordarse de cómo se llamaba."""
    assert resolver({}, "0110", "7065",
                    del_mayor="CLEANING SUPPLIES1",
                    del_catalogo="Cleaning Supplies") == "CLEANING SUPPLIES1"


def test_sin_mayor_cae_al_catalogo_y_despues_al_codigo():
    assert resolver({}, "0110", "7065", del_catalogo="Cleaning Supplies") == "Cleaning Supplies"
    # Nunca vacío: una fila sin nombre en un reporte a dueños no se puede rastrear.
    assert resolver({}, "0110", "7065") == "7065"


def test_la_misma_cuenta_se_llama_distinto_en_cada_departamento():
    """Lo que el owner pidió: «Cleaning Rooms o Cleaning F&B, y ninguno se ve
    afectado»."""
    alias = {("0110", "7065"): "Cleaning Rooms",
             ("0120", "7065"): "Cleaning F&B"}
    assert resolver(alias, "0110", "7065", del_mayor="x") == "Cleaning Rooms"
    assert resolver(alias, "0120", "7065", del_mayor="x") == "Cleaning F&B"
    # Un depto sin alias propio no hereda el del vecino.
    assert resolver(alias, "0140", "7065", del_mayor="x") == "x"


def test_un_alias_sin_departamento_vale_para_todos():
    """Para no repetir doce veces el mismo nombre cuando no cambia por depto."""
    alias = {("", "7380"): "Varios"}
    assert resolver(alias, "0110", "7380", del_mayor="Miscellaneous") == "Varios"
    assert resolver(alias, "0200", "7380", del_mayor="Misc") == "Varios"


def test_el_del_departamento_le_gana_al_general():
    alias = {("", "7380"): "Varios", ("0200", "7380"): "Varios Mantenimiento"}
    assert resolver(alias, "0200", "7380") == "Varios Mantenimiento"
    assert resolver(alias, "0110", "7380") == "Varios"


def test_limpiar_quita_el_espacio_de_sobra_y_acota():
    assert limpiar("  Cleaning   Rooms  ") == "Cleaning Rooms"
    assert limpiar(None) == ""
    assert len(limpiar("x" * 300)) == 160


# ─────────────────── Vive FUERA del mapeo, y por una razón ──────────────────

def test_el_alias_no_vive_en_account_mapping():
    """⚠️ `seed_mapping` re-afirma campo por campo todas las filas de
    `account_mapping` desde el JSON en CADA despliegue. Un alias guardado ahí
    se borraría solo, sin error y con el total cuadrando. Por eso tiene tabla
    propia — y por eso esta prueba existe."""
    from app.alias_de_cuenta import AliasDeCuenta
    from app.models.mapping import AccountMapping

    assert AliasDeCuenta.__tablename__ != AccountMapping.__tablename__
    columnas = {c.name for c in AccountMapping.__table__.columns}
    assert "alias" not in columnas, (
        "el alias entró a account_mapping: el seed lo va a borrar en el "
        "próximo despliegue")


def test_el_seed_no_toca_la_tabla_de_alias():
    fuente = (RAIZ / "app" / "seed_mapping.py").read_text(encoding="utf-8")
    assert "alias" not in fuente.lower(), (
        "seed_mapping nombra los alias: si los siembra, los pisa")


# ───────────────────────── El GL no se toca ─────────────────────────────────

def test_el_gl_conserva_el_nombre_real_y_agrega_el_alias_al_lado():
    """Owner: «el GL actual debe ser igual, solo agregamos una columna
    adicional». El nombre contable es con lo que se audita contra Integrity."""
    fuente = (RAIZ / "app" / "api" / "gl_api.py").read_text(encoding="utf-8")
    assert 'f["alias"] = alias_de_cuenta.resolver(' in fuente
    assert 'f["account_name"] = alias' not in fuente, (
        "el alias está pisando el nombre del mayor en el GL")
