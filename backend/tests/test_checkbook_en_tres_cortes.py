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
    assert "celdasDe(cortes, versiones, escenarios, de)" in src
    # Y NO se reimplementan aca.
    for propio in ("function cortesDe", "function parDe", "function celdasDe"):
        assert propio not in src, f"{propio} se reescribio en el checkbook"


def test_en_el_full_year_la_varianza_es_FORECAST_contra_budget():
    """⚠️ En el año completo el Actual son los meses cargados y nada mas.
    Medido: 920 contra 1.296 de budget da -376, que parece un derrumbe y solo
    dice que el año no termino. La regla vive en `parDe`, que es de donde sale
    tambien la del P&L."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "Forecast contra Budget" in src
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
    assert "falta alguna de las tres versiones del año" in pag


def test_la_pantalla_y_el_EXCEL_dibujan_EL_MISMO_cuadro():
    """Dos armados del mismo reporte empiezan iguales y se separan en el primer
    arreglo que alguien hace de un lado."""
    comp = COMP.read_text(encoding="utf-8")
    assert "cuadroCheckbookCortes(rotuloLibro, datos, mes, escenarios, dept, deptos)" in comp
    assert "cuadro.columnas.map" in comp and "cuadro.filas.map" in comp
    pag = PAGINA.read_text(encoding="utf-8")
    assert "cuadroCheckbookCortes(rotulo, d, mes, escenarios" in pag


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
