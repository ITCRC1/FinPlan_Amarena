# -*- coding: utf-8 -*-
"""El cuadro de los tres cortes baja sus TRES ambitos, una hoja cada uno.

Owner, 2026-09-30: *«en el excel quiero dejar solamente este tab, pero este tab
tiene varias versiones —consolidado, Hotel y Club—; me gustaria que cuando se
baje al excel automaticamente despliegue las 3 versiones en tab 1, tab 2 y tab 3
con su respectivo nombre»*.

En pantalla se miran de a uno con el selector. El archivo se archiva y se manda,
y ahi bajar solo el que estaba abierto convierte al documento en una foto de
como tenia la pantalla quien lo bajo.

## Verificado corriendo el armado

    "P&L Ago Consolidado"  Full P&L Agosto 2026 · Consolidado · mes, YTD y full year
    "P&L Ago Hotel"        Full P&L Agosto 2026 · Hotel · ...
    "P&L Ago Club"         Full P&L Agosto 2026 · Club · ...
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LIB = FRONT / "lib/tresCortes.ts"
COMP = FRONT / "app/month-end/pl/TresCortes.tsx"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def test_los_tres_ambitos_estan_en_UN_solo_lugar():
    """⚠️ El selector de la pantalla y el Excel tienen que ofrecer los mismos
    tres. Con dos listas, el dia que se agregue un ambito el archivo seguiria
    bajando tres hojas y nada avisaria que falta una — ni el archivo ni la
    pantalla se veen mal."""
    src = LIB.read_text(encoding="utf-8")
    assert "export const AMBITOS = [" in src
    for clave in ('"consolidado"', '"hotel"', '"club"'):
        assert clave in src
    comp = COMP.read_text(encoding="utf-8")
    assert "AMBITOS.map(a => (" in comp, "la pantalla escribe su propia lista"
    assert '<option value="hotel">' not in comp


def test_el_ARCHIVO_trae_los_tres():
    """El paquete de arriba y el boton del propio sub-tab."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "for (const a of AMBITOS) {" in pag
    assert "cuadroTresCortes(d, mes, escenarios, a.clave, compacto," in pag
    comp = COMP.read_text(encoding="utf-8")
    assert "for (const a of AMBITOS) {" in comp


def test_cada_pestana_dice_CUAL_es():
    """⚠️ Tres hojas llamadas «Full P&L Ago» las desempata Excel con un numero
    —«Full P&L Ago 2», «…3»— y entonces hay que abrirlas una por una para saber
    cual es el Club."""
    src = LIB.read_text(encoding="utf-8")
    assert "hoja: `P&L ${MES3[mes - 1]} ${rotuloAmbito(ambito)}`" in src
    # Y el titulo adentro de la hoja tambien, para cuando se imprime suelta.
    assert "${rotuloAmbito(ambito)}`" in src


def test_el_encabezado_estadistico_se_pide_UNA_vez():
    """Es de la PROPIEDAD, no del ambito: pedirlo tres veces daria lo mismo tres
    veces y triplicaria las llamadas."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "stats = stats ?? await estadisticasDeLosCortes(" in pag


def test_un_ambito_desconocido_no_deja_la_pestana_sin_nombre():
    """Mejor una pestaña con un nombre raro que una sin nombre."""
    src = LIB.read_text(encoding="utf-8")
    assert "AMBITOS.find(a => a.clave === clave)?.rotulo ?? clave" in src
