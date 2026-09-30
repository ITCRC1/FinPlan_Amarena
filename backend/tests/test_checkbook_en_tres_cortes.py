# -*- coding: utf-8 -*-
"""El checkbook en los TRES cortes, ademas de los doce meses.

Owner, 2026-09-30: *«en todas las opciones de los checkbooks, ademas de la
vista de 12 meses, quiero tambien tener la opcion de comparar el actual versus
Budget del mes, YTD del mes y Budget, y Full year Forecast versus Budget. en
realidad que sean 2 vistas fijas: 12 meses y mes-YTD-Full year. eso para opex,
Salarios, costo de ventas y Gastos propiedad»*.

## Las dos vistas contestan preguntas distintas

    12 meses              como se reparte el año, una version a la vez
    Mes · YTD · Full Year como va contra el presupuesto, las tres juntas

## Verificado corriendo la aritmetica

Con un actual cargado hasta agosto (115/mes), un budget de 108 y un forecast de
111, las quince comprobaciones pasan:

    mes      115   108   111   var   +7     (actual - budget)
    YTD      920   864   888   var  +56     (actual - budget)
    full     920  1296  1332   var  +36     (FORECAST - budget)

El full year es el que importa: `920 - 1296 = -376` pareceria un derrumbe y solo
diria que el año no termino.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LOGICA = FRONT / "lib/checkbookCortes.ts"
COMP = FRONT / "app/month-end/pl/Checkbooks.tsx"
PAGINA = FRONT / "app/month-end/checkbooks/page.tsx"


def test_existe_y_las_dos_vistas_estan():
    assert LOGICA.exists()
    pag = PAGINA.read_text(encoding="utf-8")
    assert '"12 meses"' in pag and '"Mes · YTD · Full Year"' in pag
    assert 'useState<"12m" | "cortes">("12m")' in pag
    comp = COMP.read_text(encoding="utf-8")
    assert 'vista === "cortes"' in comp and 'vista === "12m"' in comp


def test_vale_para_los_CUATRO_libros():
    """El pedido nombra los cuatro. La vista cuelga de `clase`, que es lo que
    ya elige el sub-tab, asi que no hay ninguno que se quede afuera."""
    comp = COMP.read_text(encoding="utf-8")
    for clase in ("opex", "payroll", "cost", "property"):
        assert f'clase: "{clase}"' in comp
    # Y el Excel baja los cuatro tambien en la vista de cortes.
    pag = PAGINA.read_text(encoding="utf-8")
    assert 'if (vista === "cortes") {' in pag
    assert "for (const [clase, rotulo] of LIBROS)" in pag


def test_los_cortes_salen_de_la_MISMA_plantilla_que_el_P_and_L():
    """⚠️ `cortesDe`, `parDe`, `celdasDe` y `suma` salen de `lib/tresCortes` sin
    una copia. El checkbook y el P&L tienen que cortar el año por los mismos
    meses y restar el mismo par, o el detalle diria una variacion y el reporte
    otra sobre los mismos datos, y sin que nada falle."""
    src = LOGICA.read_text(encoding="utf-8")
    assert 'from "@/lib/tresCortes"' in src
    # ⚠️ Desde el 2026-09-30 se le pasa tambien la VISTA: es lo que dice cuales
    # versiones tienen columna y quien ocupa la primera del ano completo.
    assert "celdasDe(cortes, todas, escenarios, de, vista)" in src
    # Y NO se reimplementan aca.
    for propio in ("function cortesDe", "function parDe", "function celdasDe"):
        assert propio not in src, f"{propio} se reescribio en el checkbook"


def test_en_el_full_year_la_varianza_es_FORECAST_contra_budget():
    """⚠️ En el año completo el Actual son los meses cargados y nada mas.
    Medido: 920 contra 1.296 de budget da -376, que parece un derrumbe y solo
    dice que el año no termino. La regla vive en `parDe`, que es de donde sale
    tambien la del P&L."""
    src = LOGICA.read_text(encoding="utf-8")
    # El rotulo viaja partido entre dos lineas de plantilla, asi que se busca
    # la regla en el encabezado del modulo.
    assert "no Actual contra Budget" in src
    comp = COMP.read_text(encoding="utf-8")
    assert "en el full year la varianza es Forecast contra Budget" in comp


def test_la_comparacion_pide_LAS_TRES_versiones():
    """Sin las tres no hay comparacion: el mes y el YTD necesitan Actual y
    Budget, y el full year necesita Forecast.

    ⚠️ Salen de `sembrarTres` —la regla del owner— y no de un `find` por tipo:
    `GET /scenarios/` ordena por año descendente, asi que el primer BUDGET de la
    lista es el Working 2035 y la comparacion abriria contra un presupuesto
    real, vacio y de otro año, sin que nada fallara.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    assert "sembrarTres(escenarios)" in pag
    assert "[tres.actual, tres.budget, tres.forecast].filter(Boolean)" in pag
    # Y se avisa cuando falta alguna, en vez de dibujar una columna en blanco.
    assert "Falta alguna de las tres: sin Budget no hay varianza" in pag


def test_la_pantalla_y_el_EXCEL_dibujan_EL_MISMO_cuadro():
    """Dos armados del mismo reporte empiezan iguales y se separan en el primer
    arreglo que alguien hace de un lado."""
    comp = COMP.read_text(encoding="utf-8")
    assert "cuadroCheckbookCortes(rotuloLibro, datos, mes, escenarios, dept, deptos," in comp
    assert "cuadro.columnas.map" in comp and "cuadro.filas.map" in comp
    pag = PAGINA.read_text(encoding="utf-8")
    assert "cuadroCheckbookCortes(rotulo, d, mes, escenarios" in pag
    # Y con LAS MISMAS opciones: si el archivo no llevara el Forecast Current,
    # su full year mostraria el Actual donde la pantalla muestra el forecast.
    assert "{ visibles, actualDelFullYear: actualFull }" in pag


def test_el_mes_arranca_en_el_corte_del_forecast():
    """Sin eso habria que elegirlo a mano cada vez para ver algo que no este
    vacio: el mes del cierre es justamente hasta donde hay actuales."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "f?.actuals_through || new Date().getMonth() + 1" in pag


def test_la_vista_de_doce_meses_sigue_intacta():
    """Es una vista NUEVA al lado, no un reemplazo: los doce meses siguen siendo
    como se mira el reparto del año."""
    comp = COMP.read_text(encoding="utf-8")
    assert "{vista === \"12m\" && versiones.map(v => {" in comp
    assert "actuals_through ?? 0" in comp, "se perdio la marca de mes real"


def test_las_TRES_versiones_se_pueden_elegir():
    """Owner, 2026-09-30: *«tienes que darme la opcion para escoger la version
    de forecast que quiero comparar»* y, preguntado por las otras dos, *«si
    editable todos»*.

    Un año tiene varios forecasts —uno por cierre— y `sembrarTres` elige uno
    solo. Comparar contra el que el sistema eligio no sirve cuando la pregunta
    es contra cual.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    assert '[["actual", "Actual"], ["budget", "Budget"],' in pag
    assert '["forecast", "Forecast"]] as const).map' in pag
    assert "const elegir = (papel: string, id: string)" in pag
    # La semilla sigue mandando hasta que alguien elige.
    assert "elegidas?.forecast ?? semilla.forecast" in pag


def test_cada_selector_ofrece_SOLO_su_tipo():
    """⚠️ Ofrecer las treinta y pico del hotel en el selector del Forecast
    dejaria elegir un Budget como forecast — y la varianza del full year, que es
    Forecast contra Budget, restaria un presupuesto de otro presupuesto sin que
    nada fallara."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "escenarios.filter(e => e.type === tipo)" in pag
    assert "porTipo(papel.toUpperCase())" in pag


def test_la_eleccion_arranca_en_null_y_no_en_la_semilla():
    """⚠️ Sembrar el estado directamente lo congelaria con la lista VACIA del
    primer render —los escenarios llegan despues— y los tres selectores
    abririan en blanco."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "useState<Record<string, string> | null>(null)" in pag


def test_en_el_full_year_la_primera_columna_es_el_FORECAST_CURRENT():
    """Owner, 2026-09-30: *«en el full year debes quitar la primera columna que
    dice actual final por el Forecast Current»*.

    ⚠️ El Actual del año son los meses cargados y nada mas, asi que en el corte
    del año completo repetia el YTD **al centavo** — en Salarios de Amarena,
    57.464,79 en las dos columnas. Dos columnas identicas con rotulos distintos
    no dicen que el año no termino: se leen como dos cifras que casualmente
    coinciden.

    Medido: con el Actual cargado hasta agosto (920) y un Forecast Current de
    116/mes, el full year pasa a 1.392 y el mes y el YTD siguen mostrando el
    Actual.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const idDe = (col: number, ci: number) => sidDe(vista.vi(col, ci));" in src
    # Solo el corte 2 (full year) y solo la columna 0.
    # La regla ya no se escribe aca: sale de `vistaDe`, en el lib.
    assert "vistaDe(todas, opciones.visibles, opciones.actualDelFullYear," in src
    pag = PAGINA.read_text(encoding="utf-8")
    assert "escenarios.find(e => e.is_current_forecast)?.id" in pag


def test_el_forecast_current_se_PIDE_pero_no_es_una_columna_propia():
    """Si entrara como una version mas, los tres cortes tendrian cuatro columnas
    y el mes mostraria un forecast que nadie pidio."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "[...new Set([...visibles, actualFull].filter(Boolean))]" in pag
    comp = COMP.read_text(encoding="utf-8")
    # La pantalla ya no recorta las versiones por su cuenta: usa la MISMA vista
    # que el cuadro, o mide un ancho distinto del que el cuadro trae.
    assert "vistaDe(versiones, visibles, actualDelFullYear, escenarios)" in comp
    assert "anchoDelCorte(c, versiones, escenarios, vistaCb)" in comp


def test_el_current_lo_marca_el_BACKEND_no_el_nombre():
    """`is_current_forecast` es el target de los uploads. Adivinarlo por el
    nombre —«Current» en el texto— fallaria en silencio el dia que alguien
    renombre una version."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert 'e.is_current_forecast' in pag
    # Y si no hay ninguno marcado, se usa el elegido en vez de dejar la columna
    # vacia.
    assert "|| tres.forecast || \"\"" in pag


# ═════════ Formulas de verdad, 2026-09-30 ════════════════════════════════════

def test_el_SUBTOTAL_del_checkbook_es_la_suma_de_lo_que_se_ve():
    """Aca el subtotal SI es la suma de las filas que el cuadro acaba de
    escribir, asi que baja como `=X7+X8+X9`.

    ⚠️ En el P&L no lo es: ahi el total lo calcula el motor y el cuadro puede no
    mostrar todos sus componentes. El exportador igual comprueba la suma contra
    el numero antes de escribir la formula, asi que declararlo no puede cambiar
    ninguna cifra.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "suma_de: detalle," in src
    assert "suma_de: subtotales," in src


def test_la_VARIANZA_del_checkbook_baja_como_FORMULA():
    src = LOGICA.read_text(encoding="utf-8")
    assert "resta: [colDe(par[0], ci, base)!," in src
    assert "const colDe = (vi: number, ci: number, base: number)" in src


# ═════════ El forecast fuera de las ranuras, 2026-09-30 ══════════════════════

def test_el_ancho_del_corte_se_mide_con_LA_MISMA_vista_que_el_cuadro():
    """⚠️ Con las visibles nada mas, `parDe` no encuentra ningun FORECAST cuando
    el owner lo saca de las ranuras: el ano completo salia SIN columna de
    varianza, mostrando el forecast en la primera columna y sin nada contra que
    leerlo. Y la pantalla medi­a un ancho mientras el cuadro traia otro, asi que
    los encabezados de corte quedaban corridos respecto de los numeros.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const vista = vistaDe(todas, opciones.visibles," in src
    assert "parDe(c, todas, escenarios, vista)" in src
    # Y `anchoDelCorte` recibe TODAS las versiones mas la vista.
    assert "vista?: Vista," in src
    assert "(vista?.columnas.length ?? versiones.length)" in src
    pantalla = (FRONT / "app/month-end/pl/Checkbooks.tsx").read_text(encoding="utf-8")
    assert "anchoDelCorte(c, versiones, escenarios, vistaCb)" in pantalla
    assert "vistaDe(versiones, visibles, actualDelFullYear, escenarios)" in pantalla


def test_la_regla_del_ano_se_aplica_UNA_vez():
    """`celdasDe` ya resuelve la version con la vista. Si `serie()` volviera a
    aplicar la regla, se aplicaria dos veces y el ano completo leeria la serie
    equivocada."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "const serie = (f: { series: Record<string, number[]> }, vi: number) =>" in src
    assert "f.series[sidDe(vi)] ?? []" in src
