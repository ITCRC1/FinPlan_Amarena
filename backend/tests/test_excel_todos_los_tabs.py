# -*- coding: utf-8 -*-
"""Un solo Excel con TODOS los sub-tabs.

Owner, 2026-09-03: *«se podrá bajar en Excel todos los tabs; que bajen todos es
todos, en un solo archivo»*.
"""
import re
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def _src() -> str:
    return PAGINA.read_text(encoding="utf-8")


def _cuerpo() -> str:
    s = _src()
    return s[s.index("async function bajarExcel()"):s.index("async function bajarWord()")]


def test_sale_del_MISMO_registro_que_el_Word():
    """⚠️ Un segundo armado sería un segundo lugar donde olvidarse un sub-tab —
    que es exactamente el defecto que el Word acaba de tener."""
    assert "CAPITULOS[v.key]" in _cuerpo()


def test_NO_filtra_por_los_escondidos():
    """«Todos es todos». El Word es lo que ve el dueño y por eso respeta el
    panel de Vistas; esto es el respaldo para trabajar, y ahí esconder una hoja
    no ayuda a nadie."""
    cuerpo = _cuerpo()
    assert "for (const v of VISTAS)" in cuerpo
    assert "subOcultos" not in cuerpo, (
        "el Excel completo empezó a respetar el panel de Vistas: deja de ser "
        "«todos»")


def test_INCLUYE_los_cuadros_sin_datos():
    """En un Word una página en cero se lee como «el mes no tuvo movimiento»;
    en Excel una hoja vacía se ve vacía, y sacarla dejaría la duda de si el tab
    existe."""
    assert "tieneDatos" not in _cuerpo()


def test_cada_cuadro_va_a_su_HOJA():
    assert "hoja: c.titulo" in _cuerpo()


def test_no_se_baja_con_la_pantalla_a_medio_cargar():
    """El mismo motivo que en el Word: la mitad de los capítulos lee el estado
    de la pantalla y la otra mitad pide lo suyo con `await`."""
    assert "if (!datos.length || !gastos.length)" in _cuerpo()


def test_avisa_cuales_no_se_pudieron_armar():
    """Un archivo con quince hojas se ve completo aunque falten dos."""
    cuerpo = _cuerpo()
    assert "fallaron.push" in cuerpo and "fallaron.join" in cuerpo


def test_es_EL_boton_de_Excel_y_no_uno_aparte():
    """Owner, 2026-09-03: «necesito que el botón que está a la par de download
    de Word, de Excel, ahí estén todos los tabs, en el mismo orden».

    ⚠️ Antes ese botón bajaba UNA sola hoja —el P&L— y el intento anterior fue
    agregar un segundo botón al lado. Dos descargas parecidas dejan al usuario
    eligiendo entre ellas, que es una decisión que nadie quiere tomar.
    """
    src = _src()
    assert "onClick={bajarExcel}" in src
    assert "bajarExcelTodo" not in src, "quedó el segundo botón"
    # Uno solo en la BARRA de arriba. Los otros «⬇ Excel» del archivo son los
    # de cada sub-tab —bajan su propio cuadro— y ésos sí van.
    assert src.count("onClick={bajarExcel}") == 1
    # Y el viejo de una sola hoja no puede volver.
    assert "[cuadroPL()]);" not in src


def test_el_ORDEN_es_el_de_la_pantalla():
    """«En el mismo orden»: se recorre `VISTAS`, la misma lista que dibuja la
    fila de sub-tabs."""
    assert "for (const v of VISTAS)" in _cuerpo()


def test_el_PL_Statement_aporta_sus_DOS_vistas_tambien_al_Excel():
    """Owner: «no veo que el detallado en Word salga».

    ⚠️ El capítulo del P&L Statement devuelve DOS cuadros —Totales y
    Departamental— y el Excel usa el mismo registro, así que las dos son dos
    hojas. Si alguien volviera a dejar uno solo, se perdería en los dos
    formatos a la vez.
    """
    src = _src()
    assert "[cuadroEstado(false), cuadroEstado(true)]" in src
    # Y el desglose por departamento está DENTRO del cuadro, no sólo en la
    # pantalla: es lo que hace distinta a la versión departamental.
    cuadro = src[src.index("function cuadroEstado("):src.index("function cuadroSummary")]
    assert "conDepto ? desglose(f.code) : []" in cuadro
    assert '" — Departamental" : " — Totales"' in cuadro
