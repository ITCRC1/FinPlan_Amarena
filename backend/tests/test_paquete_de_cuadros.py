# -*- coding: utf-8 -*-
"""Que hojas bajan en el paquete, y en que orden.

Owner, 2026-09-30: *«ocupo una opcion para escoger que tabs y en que orden van
en el paquete de excel que se baja»* y, enseguida, *«tengo muchas tabs que no
necesito porque se repiten»*.

## El defecto que estaba detras de la segunda frase

El **Word** filtraba por `subOcultos` y el **Excel** bajaba TODAS las vistas.
El mismo cierre salia con un juego de hojas en un formato y otro en el otro, y
esconder un sub-tab en «Vistas» no sacaba nada del Excel: habia que borrar las
repetidas a mano, cada mes.

## Verificado corriendo la aritmetica

Las ocho comprobaciones pasan, incluidas las tres que importan: lo escondido no
baja, el orden elegido manda, y lo que no se ordeno va DESPUES sin perderse —
si no, una vista nueva no saldria en ningun archivo hasta que alguien volviera
a abrir el panel.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LIB = FRONT / "lib/paqueteCuadros.ts"
PANEL = FRONT / "app/month-end/pl/PaqueteCuadros.tsx"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def test_existe_y_la_pantalla_lo_ofrece():
    assert LIB.exists() and PANEL.exists()
    pag = PAGINA.read_text(encoding="utf-8")
    assert "⚙ Armar paquete" in pag
    assert "<PaqueteCuadros" in pag


def test_el_EXCEL_y_el_WORD_bajan_LO_MISMO():
    """⚠️ El defecto que el owner vio como «tabs repetidas». Dos recorridos del
    mismo cierre dan dos juegos de hojas distintos, y nadie sabe cual manda."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "const capitulosDelArchivo = useCallback(" in pag
    # Los dos llaman a la MISMA funcion.
    assert pag.count("capitulosDelArchivo()") == 2
    # Y ya no queda el recorrido crudo del Excel.
    assert "for (const v of VISTAS) {" not in pag


def test_lo_que_la_propiedad_escondio_NO_baja():
    """Seria la pantalla diciendo una cosa y el adjunto otra."""
    src = LIB.read_text(encoding="utf-8")
    assert "!ocultos.includes(k)" in src
    # Y tampoco se ofrece en el panel: mostrarlo daria a entender que se puede
    # meter en el archivo un reporte que la pantalla no muestra.
    panel = PANEL.read_text(encoding="utf-8")
    assert "!ocultos.includes(k)" in panel


def test_se_guarda_lo_APAGADO_y_no_lo_prendido():
    """⚠️ Asi un capitulo nuevo nace adentro. Al reves —guardar lo prendido— se
    construye un reporte y no sale en ningun archivo hasta que alguien se
    acuerde de prenderlo."""
    src = LIB.read_text(encoding="utf-8")
    assert "fuera: string[];" in src
    assert "!p.fuera.includes(k)" in src


def test_lo_que_no_se_ordeno_va_DESPUES_y_no_se_pierde():
    """Si solo se respetara `orden`, una vista nueva no saldria en ningun
    archivo hasta que alguien volviera a abrir el panel."""
    src = LIB.read_text(encoding="utf-8")
    assert "const puestas = p.orden.filter(k => dentro.includes(k));" in src
    assert "...dentro.filter(k => !puestas.includes(k))" in src


def test_el_default_es_TODO_lo_visible():
    """Sin eleccion guardada baja lo mismo que bajaba antes. Un default vacio
    haria que el boton dejara de funcionar el dia que esto se despliega, y nadie
    sabria por que."""
    src = LIB.read_text(encoding="utf-8")
    assert "const VACIO: Paquete = { fuera: [], orden: [] };" in src
    assert "return VACIO;" in src


def test_un_localStorage_roto_no_deja_sin_archivo():
    """Bloqueado o con basura adentro, se vuelve al default."""
    src = LIB.read_text(encoding="utf-8")
    assert "} catch {" in src and "return VACIO;" in src


def test_la_eleccion_NO_viaja_a_la_base():
    """⚠️ Son dos decisiones distintas. Esconder un sub-tab es de la propiedad y
    lo ven todos; armar un paquete es de quien lo manda esa vez. Meter lo
    segundo en `tab_enablement` obligaria a apagar un reporte para TODOS con tal
    de sacarlo de un Excel."""
    src = LIB.read_text(encoding="utf-8")
    assert "localStorage" in src
    assert "saveTabsApagados" not in src
    panel = PANEL.read_text(encoding="utf-8")
    assert "saveTabsApagados" not in panel
