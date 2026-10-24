# -*- coding: utf-8 -*-
"""El P&L USALI reagrupa el P&L; no lo vuelve a calcular.

El cuadro de `pl_usali_api` y el P&L de siempre tienen que decir los MISMOS
números: es el mismo cierre con otra agrupación y otro idioma.

⚠️ **El modo de falla que estos tests cuidan no es un error, es una deriva.**
Dos cascadas sobre los mismos datos no se separan el día que se escriben: se
separan el día que alguien arregla un mapeo en una y se olvida de la otra. Ahí
el hotel tiene dos P&L que cuadran por dentro y no entre sí, y los dos siguen
pareciendo correctos. `Formato.tsx` ya dejó escrita esa lección —«la plantilla
no se escribe dos veces»— y acá queda defendida.

Son tests de ESTRUCTURA: leen el fuente. No necesitan base, igual que
`test_orden_de_subtabs`.
"""
import re
from decimal import Decimal
from pathlib import Path

BACK = Path(__file__).resolve().parents[1]
FUENTE = BACK / "app/api/pl_usali_api.py"
SRC = FUENTE.read_text(encoding="utf-8")


def test_el_resumen_sale_de_la_misma_funcion_que_el_PL():
    """El resumen tiene que leer `_serie_por_codigo`, la fuente del P&L Detail."""
    assert "from app.api.pl_detail_api import _serie_por_codigo" in SRC
    assert "_serie_por_codigo(s, scenario_id)" in SRC


def test_el_detalle_sale_del_mismo_mayor_que_el_panel_de_celda():
    """Si el detalle tuviera su propia lectura, el panel que se abre al tocar
    una celda y este cuadro podrían discrepar sin que nada avise."""
    assert "from app.api.detalle_celda_api import _del_auxiliar, _del_mayor" in SRC
    assert "_del_mayor(s, escenario, clase" in SRC
    assert "_del_auxiliar(s, escenario, clase" in SRC


def test_la_cascada_se_toma_de_las_lineas_calculadas():
    """GOP, EBITDA, EBT y la utilidad neta salen de su línea, no de una suma
    hecha acá. Sumarlas a mano es exactamente cómo empiezan a diferir."""
    from app.api.pl_usali_api import CASCADA
    codigos = {c for c, _ in CASCADA}
    for esperado in ("TOTAL_GOP", "EBITDA_BEFORE_CAPITAL", "EBT", "NET_PROFIT"):
        assert esperado in codigos, f"falta {esperado} en la cascada"


def test_las_secciones_salen_por_prefijo_y_no_por_lista_a_mano():
    """⚠️ Una lista escrita a mano se queda vieja cuando entra un departamento
    nuevo: el renglón no aparecería y el total seguiría cuadrando, porque sale
    de una línea TOTAL_* calculada aparte."""
    from app.api.pl_usali_api import SECCIONES
    prefijos = {p for _, p, _ in SECCIONES}
    assert prefijos == {"REV_", "OPEX_", "PROFIT_", "OH_"}


def test_hay_bloque_de_control_y_compara_los_dos_origenes():
    """El resumen viene de las líneas del P&L y el detalle del mayor. Que
    cuadren no se asume: se mide y se muestra."""
    assert '"control"' in SRC
    for clave in ("ingresos_dif", "gastos_dif"):
        assert clave in SRC, f"el control no expone {clave}"


def test_el_mes_cero_es_el_ano_completo():
    from app.api.pl_usali_api import _mes
    serie = [1.0] * 12
    assert _mes(serie, 0) == Decimal("12.0")
    assert _mes(serie, 9) == Decimal("1.0")
    # Una serie vacía no revienta: devuelve cero.
    assert _mes(None, 9) == Decimal("0")


def test_el_porcentaje_con_base_cero_no_revienta():
    """Un mes sin ingresos daría división por cero, y el cierre de un mes
    cerrado o de una propiedad nueva es exactamente ese caso."""
    from app.api.pl_usali_api import _pct
    assert _pct(Decimal("10"), Decimal("0")) == 0.0
    assert _pct(Decimal("25"), Decimal("100")) == 0.25


def test_no_se_inventa_un_diccionario_de_nombres_de_departamento():
    """Los rótulos salen de `department_catalog`. Un segundo juego de nombres
    haría que el mismo departamento se llame distinto según el cuadro."""
    assert "DepartmentCatalog" in SRC
    # No debe haber un mapa literal de código → nombre en español.
    assert not re.search(r'"01\d\d"\s*:\s*"', SRC), \
        "hay nombres de departamento escritos a mano en el fuente"
