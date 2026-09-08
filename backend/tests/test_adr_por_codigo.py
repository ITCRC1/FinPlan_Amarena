# -*- coding: utf-8 -*-
"""El ADR sale SIEMPRE de la cuenta 4000, y se identifica por código.

Owner, 2026-09-08: *«no tengo ADR en actual»* — y enseguida *«igual calcula
revpar»*, que sale del mismo número (`adr × ocupadas / disponibles`), así que
los dos estaban en cero. Y al ver el arreglo: *«el ADR debe ser siempre con la
cuenta 4000, rooms only»*.

## Qué pasó

La regla buscaba la fila cuyo NOMBRE de cuenta fuera exactamente «rooms».
Funcionó mientras el archivo del owner rotulara así esa fila. El día que empezó
a usar la plantilla que genera el app, la fila pasó a llamarse **«Room Revenue»**
—el nombre canónico del mapeo—, la suma dio cero, y el ADR quedó en blanco en
los cinco meses del ACTUAL 2026.

**Nada lo avisó.** El P&L cuadraba igual: el ADR es una estadística derivada y
ninguna línea del estado de resultados depende de él.

## Dos cosas se arreglaron juntas

1. **Se identifica por CÓDIGO.** Es la regla del resto del sistema —el NOMBRE es
   etiqueta, el CÓDIGO no se mueve— y acá no había motivo para ser la excepción.

2. **Se quitó la regla partida por año.** Había una excepción histórica: hasta
   2025, y en todo Budget, el ADR salía sobre TODO el ingreso del departamento
   Rooms. El owner la cerró: siempre la 4000. Un mismo indicador calculado de
   dos formas según el año hace incomparables las series, que es justo lo que un
   ADR sirve para comparar.
"""
import inspect

from app.importers import gl_detail_importer as gl


def _codigo():
    """La fuente SIN comentarios.

    El comentario del arreglo cuenta la historia y menciona la comparación
    vieja; una guarda que se dispara con su propia explicación obliga a no
    explicar, que es peor que no tener la guarda.
    """
    return "\n".join(
        l for l in inspect.getsource(gl.consolidate_block).splitlines()
        if not l.lstrip().startswith("#"))


def test_el_adr_se_calcula_por_codigo_de_cuenta():
    assert '== "4000"' in _codigo(), (
        "el ADR volvió a depender de algo que no es el código de cuenta")


def test_ya_no_depende_del_rotulo_de_la_fila():
    """⚠️ Si vuelve a compararse contra un nombre, basta con que el archivo
    cambie de rótulo para que el ADR y el RevPAR se vayan a cero en silencio."""
    assert '.lower() == "rooms"' not in _codigo()


def test_es_la_MISMA_regla_para_todo_anio_y_toda_version():
    """Owner, 2026-09-08: «el ADR debe ser siempre con la cuenta 4000».

    Antes había una excepción por año (≤2025) y otra por tipo (BUDGET), que
    calculaban el ADR sobre todo el departamento. Dos formas de calcular el
    mismo indicador hacen que la serie no se pueda comparar consigo misma.
    """
    codigo = _codigo()
    assert "whole_dept" not in codigo
    assert "year <= 2025" not in codigo


def test_sigue_siendo_solo_habitaciones():
    """4000 es la renta de habitación. La 4001 (Cancellations) y la 4002
    (No Show) están fuera, y el departamento tiene que ser Rooms."""
    codigo = _codigo()
    assert 'group_for_dept(r["dept_code"]) == "ROOMS"' in codigo
    i = codigo.index('== "4000"')
    assert "4001" not in codigo[i:i + 400]
