# -*- coding: utf-8 -*-
"""Qué sub-tabs de Cierre de Mes se ven, y para quién.

Owner, 2026-09-02: *«esta vista la van a ver los dueños; me gustaría tener la
opción de poder esconder y visualizar a mi manera, poder quitar y poner tabs sin
borrarlas, sólo para dejar lo importante para el dueño»*.

Es la MISMA matriz que la barra (`tab_enablement`) con un tercer nivel,
`SUBTAB`, así que hereda sus reglas ya probadas — y estas pruebas vigilan que
las herede de verdad.
"""
from pathlib import Path

from app.models.tab_enablement import SCOPE_KINDS

RAIZ = Path(__file__).resolve().parents[2]
CIERRE = RAIZ / "frontend/app/month-end/pl"


def test_SUBTAB_es_un_nivel_propio():
    """⚠️ No es un `ITEM`. Son tres decisiones distintas: «esta propiedad no
    hace Break-Even», «no usa el reporte a la Junta» y «en el cierre no quiero
    que el dueño vea el Flow Through». Metiéndolos en el mismo nivel, apagar un
    sub-tab podría apagar una entrada del menú que se llame igual."""
    assert SCOPE_KINDS == ["TAB", "ITEM", "SUBTAB"]


def test_el_default_sigue_siendo_PRENDIDO():
    """La tabla es esparsa: sin fila, se ve.

    El día que esto se despliega no cambia nada en ninguna propiedad, y un
    sub-tab nuevo nace visible. Al revés —nacer oculto— sería peor: se
    construye algo, nadie lo ve, y nadie sabe que existe para prenderlo.
    """
    import inspect

    from app.api import _apagados

    fuente = inspect.getsource(_apagados.tabs_apagados)
    assert "sólo lo que alguien apagó" in fuente
    # Y todos los niveles llegan presentes, aunque estén vacíos: la pantalla no
    # tiene que saber si alguien apagó alguno todavía.
    assert "{k: set() for k in SCOPE_KINDS}" in fuente


def test_se_puede_esconder_TODO_sin_quedarse_afuera():
    """⚠️ El botón que abre el panel NO es un sub-tab.

    Si lo fuera, «Esconder todas» dejaría la pantalla sin forma de volver — y
    la única salida sería tocar la base. Es la misma propiedad que hace seguro
    apagar la pantalla de administración de la barra.
    """
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    i = pagina.index("setPanelVistas(x => !x)")
    # El botón vive en la fila, no dentro del `.map` de VISTAS.
    assert "VISTAS.filter" in pagina[:i], (
        "el botón de Vistas quedó antes del filtro: revisá que no sea un "
        "sub-tab más")
    assert "⚙ Vistas" in pagina


def test_el_sub_tab_ABIERTO_no_se_saca_de_la_fila():
    """Si alguien esconde el sub-tab en el que está parado, quitarle el botón lo
    dejaría mirando un cuadro sin saber cuál es."""
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    assert "!subOcultos.includes(v.key) || v.key === vista" in pagina


def test_la_pantalla_pide_su_vista_SIN_perfil():
    """Sin perfil, el backend contesta por el rol de quien llama.

    ⚠️ Es lo que hace que cada quien vea su vista sin que esta pantalla tenga
    que saber de roles. Mandar `perfil=""` acá le daría a todos la matriz de la
    propiedad y el filtro por perfil no se aplicaría nunca.
    """
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    assert "getTabsApagados(HOTEL_ID)\n" in pagina


def test_el_panel_SI_manda_el_perfil_aunque_este_vacio():
    """Al revés que la pantalla: sin mandarlo, el admin editaría SU vista
    creyendo que edita la de la propiedad."""
    panel = (CIERRE / "VistasVisibles.tsx").read_text(encoding="utf-8")
    assert "getTabsApagados(HOTEL_ID, perfil)" in panel
    assert "saveTabsApagados(HOTEL_ID," in panel


def test_esconder_NO_es_un_permiso_y_la_pantalla_lo_dice():
    """La ruta sigue respondiendo: quien conozca la URL entra igual. Para
    impedir el cambio está el perfil `viewer`. Decirlo evita que alguien crea
    que esconder un sub-tab protege un dato."""
    panel = (CIERRE / "VistasVisibles.tsx").read_text(encoding="utf-8")
    assert "no es un permiso" in panel.lower()
    assert "Sólo lectura" in panel
