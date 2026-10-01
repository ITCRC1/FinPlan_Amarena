# -*- coding: utf-8 -*-
"""Todas las hojas del cierre bajan con FORMULAS, no con numeros pegados.

Owner, 2026-09-30, mirando el Excel del cierre: *«necesito que todos los tabs
que bajan en ese archivo esten formulados. Cada uno de ellos. Revisar los
subtotales con los totales y que todo lleve formula»*.

## Por que importa, y por que un numero no alcanza

Un Excel de junta SE TOCA. Alguien corrige un actual en una celda y espera que
la variacion, el subtotal y el total se muevan con el. Con el numero pegado no
se mueven, y la hoja queda diciendo dos cosas distintas sin que nada avise — que
es peor que no traer el dato.

## Las cuatro formas, y por que son cuatro

| forma | que dice | ejemplo |
|---|---|---|
| `columnas[n].resta` | la columna es `a - b` | la variacion |
| `columnas[n].suma_cols` | la columna suma OTRAS COLUMNAS | la columna «Año» de los doce meses |
| `filas[n].suma_de` | la fila suma OTRAS FILAS | TOTAL REVENUES |
| `filas[n].combina_filas` | la fila combina otras CON SIGNO | GOP = Operating Profit − Overhead |

Las dos primeras no se pueden expresar con las dos segundas ni al reves:
`suma_de` suma hacia abajo y `suma_cols` hacia el costado, y la cascada del P&L
no suma nada — resta.

## ⚠️ Lo que este archivo NO puede comprobar

Que la formula de el mismo numero. Eso lo comprueba el exportador celda por
celda (`_formula`, con `cuadra()`), y se verifico aparte abriendo el libro en
Excel y recalculandolo entero: 576 celdas con formula, 576 coincidencias con el
valor que el motor dejo en cache.

Esto defiende algo mas chico y mas facil de romper: que los capitulos sigan
DECLARANDO de que esta hecha cada celda. Una declaracion que se borra no rompe
nada —la hoja sale igual, con numeros— y por eso nadie se entera.
"""
import pathlib
import re

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
PAGINA = FRONT / "app/month-end/pl/page.tsx"
TRES = FRONT / "lib/tresCortes.ts"


def _pagina() -> str:
    return PAGINA.read_text(encoding="utf-8")


def test_el_contrato_tiene_LAS_CUATRO_formas():
    """Las cuatro, y documentadas: un campo sin explicar se usa mal."""
    src = (FRONT / "lib/exportCuadro.ts").read_text(encoding="utf-8")
    for campo in ("resta?: [number, number];", "suma_cols?: number[];",
                  "suma_de?: number[];",
                  "combina_filas?: [number, number][];"):
        assert campo in src, f"el contrato perdio `{campo}`"


def test_el_escritor_respeta_el_ORDEN_de_precedencia():
    """⚠️ En una celda pueden valer dos formas a la vez — la esquina de un cuadro
    de doce meses es fila-total y columna-suma—. Gana la columna, que es la mas
    corta de revisar; y `resta` gana sobre todo, porque una variacion es
    exactamente una resta y no hay margen de error."""
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app/export/cuadro_excel.py").read_text(encoding="utf-8")
    cuerpo = src[src.index("def _formula("):src.index("CENTAVO = ")]
    orden = [m.group(1) for m in re.finditer(
        r'(?:col|f)\.get\("(resta|suma_cols|suma_de|combina_filas)"\)', cuerpo)]
    assert orden == ["resta", "suma_cols", "suma_de", "combina_filas"], orden


def test_la_cascada_del_PL_declara_sus_SUMAS_y_sus_RESTAS():
    """Las dos mitades. Los subtotales suman el detalle que tienen arriba; los
    cinco resultados —GOP, los dos EBITDA, el EBT y el Net Profit— lo RESTAN.

    ⚠️ Con una sola de las dos, la hoja queda a medio formular justo en las
    lineas que mas se miran."""
    src = TRES.read_text(encoding="utf-8")
    assert "export function componentesDelPL(" in src
    assert "export function resultadosDelPL(" in src
    # Y las dos se usan en el cuadro.
    assert "componentesDelPL(emitidas).forEach(" in src
    assert "resultadosDelPL(emitidas).forEach(" in src
    # Los cinco resultados de la cascada, por su rotulo.
    for rot in ("TOTAL GROSS OPERATING PROFIT", "EBITDA BEFORE CAPITAL",
                "EBITDA AFTER CAPITAL", "EARNINGS BEFORE INCOME TAXES",
                "NET PROFIT"):
        assert f'"{rot}"' in src, f"la cascada perdio «{rot}»"


def test_los_ORDINALES_se_cuentan_sobre_LO_QUE_SE_EMITE():
    """⚠️ Es el error que degrada EN SILENCIO.

    `suma_de` son posiciones dentro del arreglo de filas que de verdad viaja, y
    ese arreglo se filtra: el modo compacto saca las lineas en cero, el ambito
    Hotel saca las tres del Club, `orden` saca las cuentas sin movimiento. Un
    indice escrito a mano queda bien el dia que se escribe y apunta al renglon
    de al lado en cuanto cambian los datos — y entonces el exportador descarta
    la formula sin decir nada y la celda vuelve a ser un numero.
    """
    src = TRES.read_text(encoding="utf-8")
    assert "const emitidas = filas.filter(f => f.tipo !== \"esp\");" in src
    assert "const cuerpo: FilaCuadro[] = emitidas.map(" in src


def test_cada_CAPITULO_del_cierre_declara_sus_formulas():
    """Capitulo por capitulo. Lo que se mira es el fragmento de cada uno, no el
    archivo entero: con un `in pagina` suelto, borrar la formula de un capitulo
    pasaria desapercibido porque otro la tiene."""
    s = _pagina()

    def bloque(desde: str, hasta: str) -> str:
        i = s.index(desde)
        return s[i:s.index(hasta, i + len(desde))]

    # El P&L completo y el Estado de Resultados: la variacion y los totales.
    pl = bloque("function cuadroPL(", "function cuadroSimple(")
    assert "resta: [cA, cB]" in pl
    assert "filas[filas.length - 1].suma_de" in pl

    estado = bloque("function cuadroEstado(", "function cuadroSummary(")
    assert "resta: [cA + bi * ancho, cB + bi * ancho]" in estado
    assert "COMPONENTES_ESTADO[f.code]" in estado

    summary = bloque("function cuadroSummary(", "function cuadroPL(")
    assert "resta: [base, base + 1]" in summary
    assert "filas[iTotalRev].suma_de = partesRev" in summary

    clase = bloque("function cuadroClase(", "El documento de cierre")
    assert "resta: [cA, cB]" in clase
    assert "filas[filas.length - 1].suma_de = orden.map(" in clase

    doce = bloque("doce: async () =>", "trescortes: async () =>")
    assert "suma_cols: vivos.map(" in doce

    formato = bloque("formato: async () =>", "revdet: async () =>")
    assert "suma_cols: cols.map(" in formato
    assert "componentesDelPL(emitidas)" in formato

    auditoria = bloque("auditoria: async () =>", "doce: async () =>")
    assert "resta: [1, 2]" in auditoria        # Dif. = motor − detalle
    assert "resta: [1, 4]" in auditoria        # Var = motor contra motor
    assert "componentesDelCuadre(i)" in auditoria


def test_las_LIBRERIAS_de_cuadros_tambien():
    """Tres hojas no se arman en la pantalla sino en `lib/`, y bajan igual."""
    armado = (FRONT / "lib/revenuePlanPaquete.ts").read_text(encoding="utf-8")
    assert "suma_de: cuerpo.map(" in armado
    assert "resta: [colDe(par[0], ci, desde)!," in armado

    pms = (FRONT / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    assert "suma_cols: anio.meses.map(" in pms          # la columna Total
    assert "suma_de: r.suma_de.map(ordinal)" in pms     # Total Ingresos
    assert "suma_de: ordenados.map(" in pms             # los canales del PMS

    memb = (FRONT / "components/MembresiasAnioTabla.tsx").read_text(encoding="utf-8")
    assert "suma_de: claves.map(" in memb
    assert "suma_cols: anio.meses.map(" in memb


def test_un_PORCENTAJE_no_se_suma():
    """⚠️ La tolerancia depende de la UNIDAD.

    Medio centavo en una columna de dolares es redondeo. En una de porcentaje,
    medio punto es una cifra: tres variaciones porcentuales pueden caer ahi por
    casualidad y escribirse como suma en una celda que es un COCIENTE. Un costo
    de A&B del periodo no es la suma de tres costos porcentuales.
    """
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app/export/cuadro_excel.py").read_text(encoding="utf-8")
    assert 'tol = 1e-9 if razon else CENTAVO' in src
    assert '== "pct"' in src
