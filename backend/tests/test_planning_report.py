# -*- coding: utf-8 -*-
"""Planning Report: los doce meses de una version y el ano de todas.

Owner, 2026-10-01, mirando el cierre y pidiendolo para el Budget 2027: *«por que
no creas un tab llamado Planning Report»* · *«quiero 12 meses, y full year para
comparar con otras versiones»* · *«quizas aca no necesitamos revisar mes, YTD o
Full Year»*.

## Que defiende este archivo

1. **La FORMA.** Doce columnas de mes de la version principal, una de ano por
   version, y la variacion. Si alguien le agrega el selector de mes o de corte
   que tiene el cierre, deja de ser este reporte.
2. **Que la columna del ano sea una FORMULA.** Es la celda que mas se mira, y la
   unica del cuadro que se puede escribir como `=SUM(B5:M5)` sin inventar nada:
   sus doce sumandos estan en la misma fila.
3. **Que la cascada use la MISMA tabla de componentes que el cierre.** Dos listas
   de que suma cada subtotal se separan en el primer renglon que alguien agregue
   de un lado, y el exportador descarta la formula que no cuadra EN SILENCIO:
   nadie se entera hasta que falta media hoja de formulas.

## Lo que este archivo NO puede comprobar

Que los numeros esten bien. Eso lo comprueba el exportador celda por celda
—`_formula` solo escribe la suma cuando da lo mismo que el motor— y se verifico
aparte con los datos reales de produccion: 692 celdas con formula en las tres
hojas, 692 coincidencias al abrir el libro en Excel y recalcularlo entero.
"""
import pathlib
import re

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LIB = FRONT / "lib/planningReport.ts"
PAGINA = FRONT / "app/planning/report/page.tsx"


def _lib() -> str:
    return LIB.read_text(encoding="utf-8")


def test_la_pantalla_existe_y_esta_en_el_menu():
    """Una pantalla que nadie puede abrir es una pantalla que no existe."""
    assert PAGINA.exists(), "falta app/planning/report/page.tsx"
    nav = (FRONT / "components/TopNav.tsx").read_text(encoding="utf-8")
    assert '{ key: "planningReport", href: "/planning/report" }' in nav
    for idioma in ("es", "en"):
        msgs = (FRONT / f"messages/{idioma}.json").read_text(encoding="utf-8")
        assert '"planningReport"' in msgs, f"falta el rotulo en {idioma}"


def test_son_DOCE_meses_y_el_ano_no_hay_corte():
    """⚠️ Lo que distingue este reporte del cierre.

    El cierre parte el ano en mes, acumulado y ano porque contesta «como vamos».
    Planning contesta «como queda el ano»: el acumulado a octubre no dice nada
    ahi. Si aparece un selector de corte o de mes, el reporte dejo de ser este.
    """
    lib = _lib()
    assert 'const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",' in lib
    assert "DOCE.map" in lib
    pagina = PAGINA.read_text(encoding="utf-8")
    for prohibido in ('"ytd"', "setMes(", "horizonte", "setHorizonte"):
        assert prohibido not in pagina, (
            f"la pantalla volvio a tener {prohibido}: es el reporte del cierre, "
            "no el de planning")


def test_la_columna_del_ANO_baja_como_formula():
    """`=SUM(B5:M5)`: sus doce sumandos estan en la misma fila, asi que es la
    unica columna del cuadro que se puede escribir sin inventar nada.

    ⚠️ Las otras columnas de ano —las de las versiones comparadas— NO la
    llevan, y es correcto: sus doce meses no estan en la hoja y la formula no
    tendria a que apuntar."""
    lib = _lib()
    assert "suma_cols: DOCE.map((_m, i) => 1 + i)" in lib
    # La de las versiones comparadas se arma aparte y sin `suma_cols`.
    comparadas = lib[lib.index("versiones.slice(1).map"):]
    assert "suma_cols" not in comparadas.split("...(par")[0]


def test_la_variacion_resta_las_dos_columnas_de_ANO():
    """Y apunta al bloque de anos, no a los meses: `resta` son indices de columna
    y el bloque empieza en la 13."""
    lib = _lib()
    assert "const BASE_ANIO = 13" in lib
    assert "resta: [BASE_ANIO + par[0], BASE_ANIO + par[1]]" in lib


def test_la_cascada_usa_la_MISMA_tabla_que_el_cierre():
    """⚠️ Importada, no copiada.

    `componentesDelPL` dice que suma cada subtotal y `resultadosDelPL` que resta
    cada resultado. Son del P&L del cierre y es la MISMA cascada: una segunda
    copia se desactualiza en el primer renglon que alguien agregue de un lado, y
    el exportador tira la formula que no cuadra sin decir nada.
    """
    lib = _lib()
    assert 'from "@/lib/tresCortes"' in lib
    assert "componentesDelPL(emitidas)" in lib
    assert "resultadosDelPL(emitidas)" in lib
    # Y no se redefinieron aca.
    assert "function componentesDelPL" not in lib
    assert "function resultadosDelPL" not in lib


def test_los_ordinales_se_cuentan_sobre_LO_QUE_SE_EMITE():
    """El modo compacto saca filas. Un indice contado sobre `datos.filas` apunta
    a otra en cuanto una cuenta entra o sale — y degrada en silencio."""
    lib = _lib()
    assert "const emitidas = (datos.filas ?? []).filter(" in lib
    assert "emitidas.map(f =>" in lib


def test_la_pantalla_dibuja_EL_MISMO_cuadro_que_baja():
    """⚠️ Owner, 2026-08-27: «el excel no baja lo que esta viendo».

    `cuadroPlanning` devuelve un `Cuadro` y la pantalla lo dibuja. Con una tabla
    en JSX y otra en el exportador, las dos pueden decir cosas distintas — y ya
    paso una vez.
    """
    pagina = PAGINA.read_text(encoding="utf-8")
    assert "cuadroPlanning(datos, escenarios," in pagina
    assert "cuadro.columnas.map(" in pagina and "cuadro.filas.map(" in pagina
    assert "bajarCuadros(" in pagina


def test_el_excel_trae_los_TRES_ambitos():
    """En la pantalla se mira uno por vez; en un libro que se manda, los tres
    juntos son la comparacion que se hace igual."""
    pagina = PAGINA.read_text(encoding="utf-8")
    bloque = pagina[pagina.index("async function bajar()"):]
    assert "for (const a of AMBITOS)" in bloque


def test_abre_en_un_BUDGET_con_la_regla_COMPARTIDA():
    """Es la pantalla de planificar: abrir en el ACTUAL seria abrir en el ano que
    ya paso.

    ⚠️ Y con `useEscenarioDe`, no con una regla propia. Owner, 2026-08-14:
    «lo dejo en Working 2027 y aparece en Working 2035» — cada pantalla traia su
    «el ano mas nuevo» copiado a mano, y el dia que nacieron los Working
    2028-2035 todos los reportes se fueron a 2035 sin que nada fallara.
    """
    pagina = PAGINA.read_text(encoding="utf-8")
    assert "useEscenarioDe(" in pagina
    assert '"planning/report:budget", escenarios, "budget"' in pagina


def test_cada_columna_declara_su_version():
    """Tres columnas que dicen «Full Year» no se distinguen. La segunda linea de
    la cabecera lleva el nombre de la version."""
    lib = _lib()
    assert re.search(r'label: "Full Year", sub: nombre\(0\)', lib)
    assert re.search(r'label: "Full Year", sub: nombre\(i \+ 1\)', lib)
