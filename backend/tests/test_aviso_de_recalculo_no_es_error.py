# -*- coding: utf-8 -*-
"""Un aviso del recalculo no es un error, y no puede borrar la pantalla.

Owner, 2026-09-29, recalculando el Forecast Final 2026: *«corri esto.. pero no
se si es un error»*, con el P&L desaparecido y un renglon rojo diciendo que
los meses cerrados no se habian tocado.

⚠️ No era un error: es el Forecast funcionando exactamente como debe. Para un
FORECAST los meses cerrados son `1..actuals_through` y el recalculo NO los
toca — es la regla del owner (CLAUDE.md §20.8: «solo recalcula los meses
futuros; los meses de actuals se preservan intactos siempre»).

Lo que estaba mal era la pantalla: mandaba ese aviso a `setError`, y ahi abajo
`if (error) return <div>{error}</div>` reemplaza TODO el contenido. Apretar
Recalcular y que el P&L desaparezca hace pensar que se rompio algo.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
FULL = FRONT / "app/pl/full/page.tsx"


def test_el_aviso_no_va_al_estado_de_error():
    src = FULL.read_text(encoding="utf-8")
    assert "const [aviso, setAviso]" in src
    assert 'setAviso(msg.startsWith("⚠") ? msg : null)' in src
    assert 'if (aviso.startsWith("⚠")) setError(aviso)' not in src, \
        "el aviso vuelve a borrar la pantalla"


def test_el_aviso_se_pinta_ARRIBA_del_pl_y_se_puede_cerrar():
    """La mayoria de estos avisos describen lo que el recalculo RESPETO. Perder
    el P&L por eso es peor que el aviso."""
    src = FULL.read_text(encoding="utf-8")
    assert "{aviso && (" in src
    assert 'aria-label="Cerrar aviso"' in src
    # Y va DESPUES del guard de error, o sea dentro del render normal.
    assert src.index("if (error)   return") < src.index("{aviso && (")


def test_error_sigue_reemplazando_la_pantalla_y_se_dice_por_que():
    """⚠️ `error` SI debe reemplazarla: significa que no hay P&L que mostrar.
    La distincion tiene que estar escrita o el proximo cambio la deshace."""
    src = FULL.read_text(encoding="utf-8")
    assert "if (error)   return" in src
    assert "no hay P&L que mostrar" in src


def test_para_un_forecast_los_meses_cerrados_son_hasta_actuals_through():
    """El fondo del aviso: no hay nada que arreglar en el calculo."""
    from app.engine.meses_cerrados import meses_cerrados
    import inspect
    src = inspect.getsource(meses_cerrados)
    assert 'if tipo == "FORECAST":' in src
    assert "set(range(1, corte + 1))" in src
    # Y un BUDGET no cierra meses, aunque traiga `actuals_through`.
    assert "un presupuesto no cierra meses" in src


def test_repartos_solo_protege_los_meses_que_TIENEN_asientos():
    """Por que el aviso dice planilla (1..7) y repartos (6, 7): son los meses
    cerrados que ademas tienen algo que proteger. No es una inconsistencia."""
    import inspect
    from app.engine import recalculate
    src = inspect.getsource(recalculate)
    assert "protegidos = cerrados & con_reparto" in src
