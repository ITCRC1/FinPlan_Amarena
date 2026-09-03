# -*- coding: utf-8 -*-
"""Tocar una línea y ver de qué está hecha, sin salir de la pantalla.

Owner, 2026-09-03: *«toco la línea de Rooms Revenue y me abre el detalle, sin
ir… si abro payroll de Rooms se me despliegan los GL que suman eso, como un
cuadro sin salir a la otra ventana… así voy presentando y puedo ver los detalles
de una vez»*.

Y, enseguida: *«el presupuesto debe tener GL, siempre debe estar conectado a un
GL»*.
"""
import inspect
from pathlib import Path

from app.api import detalle_celda_api as api

FRONT = Path(__file__).resolve().parents[2] / "frontend"
CIERRE = FRONT / "app/month-end/pl"


def test_el_presupuesto_se_abre_POR_CUENTA_igual_que_el_actual():
    """⚠️ Y sí tiene cuenta: cada línea del checkbook lleva su `account_code`
    —opex, costo y below-GOP— y los 17 conceptos de planilla SON cuentas del
    mayor (`c6000_sw` es la 6000).

    Verificado en producción sobre Rooms: el ACTUAL y los dos BUDGET abren las
    mismas cuentas 6000, 6020, 6023… y se comparan una contra otra.
    """
    fuente = inspect.getsource(api._del_auxiliar)
    assert "account_code" in fuente
    assert "from app.api.consulta_api import CONCEPTOS" in fuente, (
        "la planilla del presupuesto dejó de abrirse por concepto, que es lo "
        "que la hace comparable cuenta contra cuenta con el mayor")


def test_cada_version_DICE_de_donde_sale_su_detalle():
    """Un ACTUAL lo trae del mayor y un presupuesto de sus auxiliares.
    Mezclarlos sin decirlo sería peor que no mostrarlos."""
    fuente = inspect.getsource(api.detalle_de_celda)
    assert '"Mayor (GL)"' in fuente and '"Auxiliar (checkbook)"' in fuente


def test_elige_la_fuente_con_la_MISMA_regla_que_el_cuadro():
    """⚠️ `lo_subido_manda` es lo que usa `gasto_por_clase` para decidir de
    dónde lee la celda. Con otro criterio, el desplegable abriría cuentas que
    no son las que suman el número que se tocó."""
    fuente = inspect.getsource(api.detalle_de_celda)
    assert "recalc.lo_subido_manda" in fuente


def test_el_departamento_sube_EN_CADENA():
    """`consolidate_dept` resuelve un escalón y hay cadenas de dos —el 0132
    cuelga del 0130 y el 0130 del 0140—. Es la misma función que usa el cuadro;
    con un escalón menos, el detalle no sumaría la celda."""
    fuente = inspect.getsource(api._padre)
    assert "for _ in range(5)" in fuente


def test_una_linea_de_ingreso_AGREGADA_no_se_disfraza_de_cuenta():
    """⚠️ `ROOMS` del checkbook agrega la 4000, la 4001 y la 4002. Ponerle una
    cuenta sería elegir una de las que agrupa.

    Sale con el nombre de la línea y marcada `agregado`, y la pantalla lo
    explica.
    """
    fuente = inspect.getsource(api._del_auxiliar)
    assert "REVENUE_LINE_ACCOUNT" in fuente
    assert '"agregado"' in fuente
    pantalla = (CIERRE / "DetalleCelda.tsx").read_text(encoding="utf-8")
    assert "v.agregado" in pantalla


def test_el_mapeo_de_linea_del_checkbook_NO_se_reescribe():
    """Sale de `REVENUE_LINE_TO_REPORT_LINE`, la misma tabla con la que el
    motor lleva el checkbook de ingreso al P&L."""
    fuente = inspect.getsource(api._del_auxiliar)
    assert "pl_engine.REVENUE_LINE_TO_REPORT_LINE" in fuente


def test_el_corte_del_desplegable_es_el_del_CUADRO():
    """⚠️ Si sumara el año entero mientras el cuadro muestra julio, los números
    no cerrarían con la celda que se tocó — y existe justamente para explicar
    esa celda."""
    pantalla = (CIERRE / "DetalleCelda.tsx").read_text(encoding="utf-8")
    assert 'horizonte === "month"' in pantalla and 'horizonte === "ytd"' in pantalla


def test_se_cierra_con_ESCAPE_y_tocando_afuera():
    """Está pensado para presentar: buscar la X con el mouse se nota."""
    pantalla = (CIERRE / "DetalleCelda.tsx").read_text(encoding="utf-8")
    assert 'e.key === "Escape"' in pantalla
    assert "onClick={onCerrar}" in pantalla
    # ⚠️ Y tocar DENTRO no cierra: sin esto, seleccionar un número para
    # copiarlo cerraría el cuadro.
    assert "e.stopPropagation()" in pantalla


def test_solo_se_marca_lo_que_de_verdad_ABRE():
    """Un adorno que no hace nada al tocarlo es peor que no tenerlo."""
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    assert "CLASE_DE[f.code] ? ABRIBLE : {}" in pagina


def test_el_total_del_desplegable_se_dibuja():
    """Tiene que dar exactamente la celda que se tocó. Si no da, el desplegable
    está explicando otra cosa — y sin el renglón no hay forma de notarlo."""
    pantalla = (CIERRE / "DetalleCelda.tsx").read_text(encoding="utf-8")
    assert ">TOTAL<" in pantalla.replace("\n", "").replace(" ", "")
