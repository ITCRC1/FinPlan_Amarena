# -*- coding: utf-8 -*-
"""El reporte de conceptos por departamento, de vuelta a la planilla.

Owner, 2026-11-11: *«tenemos que hacer que este archivo llegue a budget 2027 y
que haga prorrateo con las posiciones»*.

El archivo agrega por departamento y la base guarda por posición. Estas
pruebas vigilan las dos cosas que pueden romperse sin dar error: que entre un
número calculado como si fuera un dato, y que el reparto pierda centavos.
"""
from decimal import Decimal

import pytest

from app.importers.conceptos_por_depto import (
    CALCULADAS, IMPORTABLES, repartir,
)
from app.models.payroll_concept_entry import PayrollConceptEntry


# ─────────────────── Lo que NUNCA puede entrar ─────────────────────────────

def test_las_calculadas_no_son_importables():
    """⚠️ 6000 sale de salario × FTE / TC; 6020 es 26.83% de BASE y 6021 es
    BASE/12. Guardarlas haría que el siguiente Recalcular las cambie **sin que
    nadie vea por qué**: se guardó un resultado donde va un insumo."""
    assert CALCULADAS == {"6000", "6020", "6021"}
    assert not (CALCULADAS & set(IMPORTABLES)), "una calculada entró como importable"


def test_los_importables_existen_en_el_modelo():
    """Un campo mal escrito no revienta: `setattr` crea un atributo suelto en
    el objeto, el ORM lo ignora y el monto se pierde en silencio."""
    for cuenta, campo in IMPORTABLES.items():
        assert hasattr(PayrollConceptEntry, campo), f"{cuenta} apunta a «{campo}», que no existe"


def test_estan_los_catorce_conceptos_digitados():
    """Los seis del grupo BASE más los ocho beneficios. Si el modelo gana un
    concepto manual y acá no se agrega, ese renglón del archivo se descarta."""
    assert len(IMPORTABLES) == 14
    assert {"6001", "6002", "6003", "6010", "6024", "6027"} <= set(IMPORTABLES)


# ─────────────────────────── El reparto ────────────────────────────────────

@pytest.mark.parametrize("total,pesos", [
    (Decimal("100.00"), [Decimal(3), Decimal(1)]),
    (Decimal("100.00"), [Decimal(1)] * 3),          # el resto feo: 33,33…
    (Decimal("7.77"),   [Decimal(5)]),
    (Decimal("0.01"),   [Decimal(1)] * 5),          # menos plata que puestos
    (Decimal("9979.47"), [Decimal(str(x)) for x in (2173.91, 1086.96, 1086.96, 1086.96, 543.48)]),
])
def test_la_suma_de_las_partes_es_el_total(total, pesos):
    """⚠️ Redondear cada parte por separado deja centavos sueltos que el P&L
    arrastra y que después nadie puede explicar."""
    partes = repartir(total, pesos)
    assert sum(partes) == total
    assert len(partes) == len(pesos)


def test_sin_salarios_reparte_en_partes_iguales():
    """Un departamento entero en FTE 0 no tiene prorrata posible. Descartar el
    monto haría desaparecer plata que el archivo sí traía."""
    partes = repartir(Decimal("90.00"), [Decimal(0)] * 3)
    assert partes == [Decimal("30.00")] * 3
    assert sum(partes) == Decimal("90.00")


def test_reparte_a_prorrata_y_no_en_partes_iguales():
    """El que gana el triple recibe el triple."""
    partes = repartir(Decimal("100.00"), [Decimal(3), Decimal(1)])
    assert partes[0] == Decimal("75.00") and partes[1] == Decimal("25.00")


def test_sin_puestos_no_revienta():
    assert repartir(Decimal("100.00"), []) == []
