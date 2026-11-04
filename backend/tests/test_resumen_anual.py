# -*- coding: utf-8 -*-
"""El resumen ejecutivo año contra año.

Dos propiedades que no se pueden perder:

**No guarda nada.** El owner pidió que el informe se mantenga al día solo. La
única forma de garantizarlo es que no exista una copia: cada llamada lo calcula
desde el motor. Si alguien agrega una tabla de caché, esto se vuelve una foto
que envejece, y el día que el informe y el P&L no coincidan nadie sabrá cuál
manda.

**El color de una variación lo decide el backend.** En un ingreso subir es
bueno; en un gasto, subir es malo. Si cada pantalla lo resolviera sola, alguna
terminaría pintando de verde un sobrecosto.
"""
import inspect

from app.api import resumen_anual_api as ra


def test_no_escribe_en_la_base():
    """Un informe que se guarda queda viejo. Este se calcula y se olvida."""
    src = inspect.getsource(ra)
    for prohibido in ("session.add(", "db.add(", "commit()", "delete("):
        assert prohibido not in src, (
            f"«{prohibido}» en el resumen anual: si empieza a guardar deja de "
            "actualizarse solo, que es justo lo que se pidió")


def test_un_gasto_que_sube_no_es_favorable():
    a = {"lineas": {"X": {"meses": [0] * 12, "anio": 100.0}}}
    b = {"lineas": {"X": {"meses": [0] * 12, "anio": 150.0}}}
    ingreso = ra._fila("X", "Ingreso", a, b, +1)
    gasto = ra._fila("X", "Gasto", a, b, -1)
    assert ingreso["favorable"] is True, "más ingreso es bueno"
    assert gasto["favorable"] is False, "más gasto NO es bueno"
    assert ingreso["var"] == gasto["var"] == 50.0, "la variación es la misma"


def test_sin_variacion_no_hay_color():
    """Cero no es ni bueno ni malo: pintarlo de verde o rojo es inventar."""
    a = {"lineas": {"X": {"meses": [0] * 12, "anio": 100.0}}}
    f = ra._fila("X", "X", a, a, +1)
    assert f["favorable"] is None and f["var"] == 0.0


def test_la_variacion_porcentual_tolera_el_cero():
    """Un año que arranca en cero no puede reventar el informe entero."""
    a = {"lineas": {}}
    b = {"lineas": {"X": {"meses": [0] * 12, "anio": 500.0}}}
    f = ra._fila("X", "X", a, b, +1)
    assert f["var"] == 500.0
    assert f["var_pct"] is None, "dividir entre cero no da un porcentaje"


def test_la_narrativa_avisa_de_las_lineas_que_quedaron_en_cero():
    """Es el hallazgo que el owner no puede ver en un total: una línea que
    facturó y desapareció no mueve el total lo suficiente para notarse."""
    a = {"escenario": {"anio": 2026}, "meses_con_dato": 12,
         "lineas": {}, "kpis": {}, "gasto": {}}
    b = {"escenario": {"anio": 2027}, "meses_con_dato": 12,
         "lineas": {}, "kpis": {}, "gasto": {}}
    ingresos = [{"nombre": "A&B", "base": 11713.0, "comp": 0.0,
                 "var": -11713.0, "var_pct": -100.0}]
    resultado = [{"code": "TOTAL_REVENUES", "nombre": "Ingresos",
                  "base": 11713.0, "comp": 0.0, "var": -11713.0, "var_pct": -100.0}]
    k = {"ocupadas": 0, "ocupacion": 0, "adr": 0}
    frases = ra._narrativa(a, b, k, k, ingresos, resultado, [], [])
    assert any("CERO" in f and "A&B" in f for f in frases), frases


def test_la_narrativa_avisa_cuando_un_año_esta_incompleto():
    """Diez meses contra doce exagera toda variación. Decirlo es parte del dato."""
    a = {"escenario": {"anio": 2026}, "meses_con_dato": 10,
         "lineas": {}, "kpis": {}, "gasto": {}}
    b = {"escenario": {"anio": 2027}, "meses_con_dato": 12,
         "lineas": {}, "kpis": {}, "gasto": {}}
    k = {"ocupadas": 0, "ocupacion": 0, "adr": 0}
    res = [{"code": "TOTAL_REVENUES", "nombre": "Ingresos", "base": 1.0,
            "comp": 2.0, "var": 1.0, "var_pct": 100.0}]
    frases = ra._narrativa(a, b, k, k, [], res, [], [])
    assert any("exagera" in f for f in frases), frases


def test_las_dos_lineas_de_propiedad_se_llaman_distinto():
    """Dan distinto a propósito —una son todas las 8xxx, la otra sólo el bloque
    de arriba del EBITDA— así que no pueden compartir nombre: con el mismo
    rótulo y dos valores, el informe parece estar equivocado."""
    clase = dict(ra.CLASES)["property"]
    cascada = next(n for c, n, _s in ra.RESULTADO if c == "TOTAL_NON_OP_EXPENSES")
    assert clase != cascada
    assert "8xxx" in clase and "renta" in cascada.lower()
