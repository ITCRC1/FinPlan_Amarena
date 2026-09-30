# -*- coding: utf-8 -*-
"""Los cuatro checkbooks entran al paquete del cierre, en tres cortes.

Owner, 2026-09-30: *«quiero agregar todos estos tabs al excel que bajo para el
resumen ejecutivo, con el mismo formato: opex mes, ytd y full year; salarios
mes, ytd y full year…»* y, aclarandolo: *«seria practicamente unir o hacer merge
de los excels ya que estan en el mismo formato»*.

Y eso es exactamente lo que se hizo: no hay un cuadro nuevo. Los checkbooks ya
sabian dibujarse en mes · YTD · full year (`cuadroCheckbookCortes`), asi que se
enganchan como capitulos mas del paquete y quedan a la par de los demas en
«Armar paquete» — con su casilla y sus flechas.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def _src() -> str:
    return PAGINA.read_text(encoding="utf-8")


def test_los_cuatro_libros_son_capitulos():
    s = _src()
    assert "const EXTRAS = [" in s
    for clave, clase in (("cb_opex", "opex"), ("cb_payroll", "payroll"),
                         ("cb_cost", "cost"), ("cb_property", "property")):
        assert f'key: "{clave}"' in s and f'clase: "{clase}"' in s
    # Se registran como capitulos, no como un caso aparte del boton.
    assert "...Object.fromEntries(EXTRAS.map(e => [e.key, async () => {" in s


def test_es_un_MERGE_y_no_un_cuadro_nuevo():
    """⚠️ Owner: «seria practicamente unir o hacer merge de los excels ya que
    estan en el mismo formato». Escribir otro armado seria una segunda
    definicion del mismo cuadro: empiezan iguales y se separan en el primer
    arreglo que alguien hace de un lado — y entonces el checkbook suelto y el
    del paquete dirian cosas distintas de los mismos datos."""
    s = _src()
    assert "cuadroCheckbookCortes(" in s
    assert 'from "@/lib/checkbookCortes"' in s


def test_heredan_las_reglas_del_full_year():
    """La varianza es Forecast contra Budget, y la primera columna del año es el
    Forecast Current — no el Actual, que ahi repite el YTD. Vienen con el cuadro
    justamente por no haberlo reescrito."""
    s = _src()
    assert "x.is_current_forecast" in s
    assert "{ visibles, actualDelFullYear: actualFull }" in s


def test_aparecen_en_ARMAR_PAQUETE_junto_a_los_demas():
    """Si no entraran en la lista del panel, bajarian siempre y no se podrian
    ordenar ni apagar — que es lo contrario de lo que se pidio hace dos
    mensajes."""
    s = _src()
    assert "const CLAVES_DEL_PAQUETE = () =>" in s
    assert "...EXTRAS.map(e => e.key)" in s
    assert "vistas={CLAVES_DEL_PAQUETE()}" in s
    assert "CLAVES_DEL_PAQUETE(), subOcultos," in s


def test_NO_pasan_por_tab_enablement():
    """⚠️ Esa matriz gobierna sub-tabs de esta pantalla, y estos no lo son: no
    tienen fila, asi que si se filtraran por ella nunca apareceria ninguno."""
    s = _src()
    i = s.index("const EXTRAS = [")
    assert "No pasan por `tab_enablement`" in s[max(0, i - 900):i]


def test_tienen_nombre_propio_en_el_panel():
    """No estan en el diccionario de traducciones —no son tabs—, asi que
    `t('tab_cb_opex')` devolveria la clave cruda y el panel mostraria
    «tab_cb_opex»."""
    s = _src()
    assert "const rotuloDelCapitulo = useCallback((k: string) => {" in s
    assert "rotulo={rotuloDelCapitulo}" in s
    assert "t(`tab_${k}`)" in s   # los sub-tabs siguen saliendo del diccionario


def test_un_libro_vacio_no_baja_como_hoja_en_cero():
    """Una hoja con una sola fila en cero se lee como «no hubo gasto», que es
    una afirmacion — y distinta de «este libro no tiene nada cargado»."""
    s = _src()
    assert "return c.filas.length > 1 ? [c] : [];" in s
