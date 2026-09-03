# -*- coding: utf-8 -*-
"""El Word trae TODAS las vistas activas, en el orden de la pantalla.

Owner, 2026-09-03: *«asegurate que todas las vistas estén en el Word»*, *«en el
mismo orden»*, *«pero sólo las vistas activas: las que están escondidas no se
necesitan»*.

Y antes, el 2026-09-02: *«¿por qué el Word baja unos pocos tabs y no todos los
que se ven disponibles?»* — la versión anterior armaba los capítulos en una
secuencia escrita a mano y sólo cubría nueve de los diecisiete sub-tabs.

⚠️ Con una secuencia a mano, cada sub-tab nuevo hay que acordarse de agregarlo,
y **olvidarse no falla**: el capítulo simplemente no sale. Por eso ahora es un
registro que se recorre con `VISTAS`, y por eso existe esta prueba.
"""
import re
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGINA = FRONT / "app/month-end/pl/page.tsx"

#: Sub-tabs que a propósito NO tienen capítulo, con el motivo.
SIN_CAPITULO = {
    # Es una pantalla de CONSULTA: lo que muestra depende de los filtros que se
    # elijan en el momento y de un «agrupar por» que cambia hasta las columnas.
    # Un capítulo fijo tendría que inventar una consulta.
    "consulta",
}


def _fuente() -> str:
    return PAGINA.read_text(encoding="utf-8")


def _vistas() -> list[str]:
    src = _fuente()
    bloque = src[src.index("const VISTAS = ["):src.index("] as const;")]
    return re.findall(r'\{\s*key:\s*"([a-z0-9]+)"', bloque)


def _con_capitulo() -> set[str]:
    src = _fuente()
    i = src.index("const CAPITULOS:")
    bloque = src[i:src.index("async function resumen12Cuadros")]
    return set(re.findall(r"^    ([a-z0-9]+): async \(\)", bloque, re.M))


def test_TODA_vista_tiene_capitulo():
    faltan = set(_vistas()) - _con_capitulo() - SIN_CAPITULO
    assert not faltan, (
        f"estos sub-tabs no salen en el Word: {sorted(faltan)}. Agregá su "
        f"capítulo en `CAPITULOS`, o ponelo en `SIN_CAPITULO` con el motivo")


def test_el_que_NO_tiene_capitulo_lo_dice_y_por_que():
    """Un `return []` sin explicación es indistinguible de un olvido."""
    src = _fuente()
    for clave in SIN_CAPITULO:
        i = src.index(f"    {clave}: async ()")
        cuerpo = src[i:i + 900]
        assert "no es un olvido" in cuerpo, (
            f"«{clave}» devuelve vacío sin decir por qué")


def test_el_orden_del_documento_es_el_de_la_PANTALLA():
    """No un orden propio: el documento se lee en el mismo orden en que se miró
    la pantalla."""
    src = _fuente()
    cuerpo = src[src.index("async function bajarWord()"):]
    assert "for (const clave of activos)" in cuerpo
    assert "VISTAS.map(v => v.key).filter(k => !subOcultos.includes(k))" in cuerpo


def test_solo_las_vistas_ACTIVAS():
    """Owner: «las que están escondidas no se necesitan en el Word».

    ⚠️ Y se resuelve con `subOcultos` —lo que la pantalla YA usa para dibujar—
    y no leyendo `tab_enablement` otra vez. Una segunda lectura de la misma
    decisión es una segunda oportunidad de que difieran."""
    src = _fuente()
    cuerpo = src[src.index("async function bajarWord()"):]
    assert "subOcultos.includes(k)" in cuerpo
    assert "tab_enablement" not in cuerpo


def test_el_PL_Statement_sale_en_sus_DOS_vistas():
    """Owner: «el P&L Statement tiene 2 vistas en el mismo archivo; quiero que
    despliegues una de totales y otra de vista departamental».

    En la pantalla el botón muestra una por vez; en el documento caben las dos,
    y son dos lecturas distintas del mismo mes — el total dice cuánto y el
    departamental dice de dónde."""
    src = _fuente()
    assert "[cuadroEstado(false), cuadroEstado(true)]" in src
    # Y el título distingue cuál es cuál: dos capítulos idénticos de nombre
    # serían peor que uno solo.
    assert '" — Departamental" : " — Totales"' in src


def test_un_capitulo_que_falla_no_se_lleva_el_DOCUMENTO():
    """Con doce capítulos, que uno reviente y no salga nada sería perder el
    cierre entero por un cuadro."""
    src = _fuente()
    cuerpo = src[src.index("for (const clave of activos)"):]
    assert "} catch {" in cuerpo[:400]
