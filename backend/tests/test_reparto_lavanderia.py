# -*- coding: utf-8 -*-
"""El reparto de lavandería: filas en blanco y departamentos que no existen.

Owner, 2026-09-03: *«ya hice el allocation de lavandería, favor revisá porque me
está dando error cuando guardo»* · *«dice application error, a client-side
exception has occurred»*.

El backend devolvía **200 en todos los guardados** —está en el log de
producción—, así que el error era de la pantalla. Lo que encontró la revisión
fue dos filas invalidas en `laundry_allocation_config` del BUDGET 2026:

    ('',    '',      0.00, False)   <- una fila SIN departamento
    ('110', 'Rooms', 0.70, True)    <- el codigo de Rooms es `0110`, no `110`

La segunda es la cara: `110` no existe en el catálogo, así que
`group_for_dept("110")` cae en `OTHER_OVERHEAD` y los $6.886,96 repartidos no
llegan a Habitaciones.
"""
import inspect

from app.api import allocation_api
from app.engine import pl_engine


def test_una_fila_SIN_departamento_no_se_guarda():
    """⚠️ Y si venían DOS en blanco, el commit reventaba.

    El `select` no ve lo que está pendiente en la sesión, así que las dos se
    insertaban y `uq_laundry_config` las rechazaba al hacer commit. La pantalla
    agrega renglones vacíos para escribir encima: guardar antes de llenarlos no
    puede romper nada.
    """
    fuente = inspect.getsource(allocation_api.upsert_laundry_config)
    assert 'code = (row.dept_code or "").strip()' in fuente
    assert "if not code:" in fuente and "continue" in fuente
    assert "limpias[code] = row" in fuente, (
        "se dejó de deduplicar por departamento: dos filas del mismo depto en "
        "un guardado volverían a chocar contra el UNIQUE")


def test_el_codigo_de_Rooms_es_0110_y_no_110():
    """El reparto a un departamento que no existe se pierde en OTHER_OVERHEAD.

    No es un error del motor: `group_for_dept` contesta lo que puede con lo que
    le dan. Es que `110` no está en el catálogo — el de Habitaciones es `0110`.
    """
    assert pl_engine.group_for_dept("0110") == "ROOMS"
    assert pl_engine.group_for_dept("110") != "ROOMS", (
        "si `110` empezara a resolver a ROOMS, este cotejo dejaría de avisar "
        "que el código está mal escrito")


def test_el_credito_del_reparto_va_a_la_cuenta_de_ALLOCATION():
    """El crédito al departamento de origen usa una 49xx; si no, el gasto no
    netea y la lavandería seguiría contándose entera."""
    assert "4999" in pl_engine.ALLOCATION_ACCOUNTS
    assert "4900" in pl_engine.ALLOCATION_ACCOUNTS
