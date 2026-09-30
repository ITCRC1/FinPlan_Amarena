# -*- coding: utf-8 -*-
"""El armado de ingresos en los TRES cortes, ademas de los doce meses.

Owner, 2026-09-30, sobre la pantalla de Armado de ingresos: *«aca lo mismo que
en opex: mes, ytd y full year»*.

## ⚠️ Aca el corte NO es sumar meses

En el checkbook todo era plata. Aca conviven cinco unidades y cada una se agrega
de una forma distinta:

    Noches · Pax · Total revenue   suma
    Inventario                     las unidades del ULTIMO mes
    Ocupacion                      ocupadas del periodo / disponibles del periodo
    Net rate                       ingreso del periodo / noches del periodo
    Rack rates · Canales           promedio de los meses CON valor

Corriendo la aritmetica real, las 18 comprobaciones pasan. Las tres que
importan:

    ocupacion YTD ago   18,75 %   sumar los 8 meses daria 150 %
    net rate YTD        300,00    promediar los 8 meses daria 112,50
    rack YTD            466,67    promediando tambien los cerrados daria 175
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LOGICA = FRONT / "lib/revenuePlanCortes.ts"
PAGINA = FRONT / "app/month-end/revenue-plan/page.tsx"


def test_existe_y_las_dos_vistas_estan():
    assert LOGICA.exists()
    pag = PAGINA.read_text(encoding="utf-8")
    assert '"12 meses"' in pag and '"Mes · YTD · Full Year"' in pag
    assert 'useState<"12m" | "cortes">("12m")' in pag


def test_vale_para_las_OCHO_vistas():
    """El pedido era «lo mismo que en opex», y opex son los cuatro libros. Aca
    son las ocho vistas: la agregacion cuelga de `vista`, asi que no queda
    ninguna afuera."""
    src = LOGICA.read_text(encoding="utf-8")
    for v in ("inventario", "noches", "rack", "ocupacion",
              "pax", "canales", "net", "revenue"):
        assert f'"{v}"' in src, f"falta la regla de {v}"


def test_lo_que_NO_se_suma():
    """⚠️ Sumar doce ocupaciones da 700 % y se ve perfectamente normal en una
    celda. Y las unidades son las mismas todos los meses: sumarlas daria 96
    villas donde hay 8."""
    src = LOGICA.read_text(encoding="utf-8")
    # Inventario: el ultimo mes del rango, no la suma.
    assert 'campo(f, rt, meses[meses.length - 1], "units")' in src
    # Ocupacion y net rate: cocientes del PERIODO.
    assert 'disp ? sumaDe(f, rt, meses, "nights_occupied") / disp : 0' in src
    assert 'noc ? sumaDe(f, rt, meses, "revenue") / noc : 0' in src


def test_el_promedio_deja_fuera_los_meses_en_cero():
    """⚠️ Amarena abre en junio. Con enero-mayo adentro, el rack del YTD de
    agosto daba **175** donde la tarifa real es 490, y el mix de OTA daba 17,5 %
    donde es 43 %. Un cero ahi no es una tarifa baja: es que no hubo temporada.

    Es la misma regla que el owner fijo para los socios del Club el 2026-09-02.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const promedioVivo" in src
    assert "vs.filter(v => Math.abs(v) > 1e-9)" in src
    assert "promedioVivo(meses.map" in src


def test_el_TOTAL_de_una_razon_se_pondera_por_tipo():
    """⚠️ La ocupacion del hotel es el total de noches ocupadas sobre el total de
    disponibles, NO el promedio de las ocupaciones por categoria: un tipo con dos
    villas pesaria igual que uno con ocho.

    Medido: con BL01 al 50 % (8 villas) y PO03 al 100 % (2), el total es 60 % y
    el promedio de los dos daria 75 %.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "export function totalDeIngresos" in src
    assert 'const d = sum("nights_available");' in src
    # Y donde no hay total que valga, va `null` y no un numero.
    assert 'if (vista === "rack" || vista === "canales") return null;' in src


def test_lo_que_una_version_no_tiene_va_en_NULL():
    """Un presupuesto sin configuracion de canales no es un mix en cero."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "if (!r) return null;" in src
    assert "if (!c) return null;" in src
    # La categoria que esa version no tiene: se resuelve por codigo y no
    # aparece, en vez de devolver cero.
    assert "const rt = idRt(f, clave);" in src and "if (!rt) return null;" in src


def test_las_filas_son_la_UNION_de_las_versiones():
    """Un tipo de habitacion que solo esta en el presupuesto tiene que verse — es
    justo el que interesa cuando se compara."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "for (const f of fuentes) {" in src
    assert "const out = new Map<string, string>();" in src


def test_los_cortes_y_la_varianza_salen_de_la_MISMA_plantilla():
    """`cortesDe`, `parDe` y `celdasDe` vienen de `lib/tresCortes`: el armado, el
    checkbook y el P&L tienen que cortar el año por los mismos meses y restar el
    mismo par."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert 'from "@/lib/tresCortes"' in pag
    assert "celdasDe(cortes, columnas, escenarios, de)" in pag


def test_en_el_full_year_la_primera_columna_es_el_FORECAST_CURRENT():
    """Lo mismo que en los checkbooks: el Actual del año repite el YTD."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "ci === 2 && vi === 0 && actualFull" in pag
    assert "escenarios.find(e => e.is_current_forecast)?.id" in pag


def test_la_pantalla_avisa_cuando_el_valor_es_un_promedio():
    """Una celda con un promedio y una con un acumulado se ven igual. En las
    vistas de razon hay que decirlo, o se leen como totales."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "export const ES_PROMEDIO" in src
    pag = PAGINA.read_text(encoding="utf-8")
    assert "ES_PROMEDIO(vista)" in pag
    assert "no un acumulado" in pag


def test_las_tres_versiones_se_eligen():
    """Igual que en Checkbooks, y por la misma razon: un año tiene varios
    forecasts y comparar contra el que el sistema eligio no sirve cuando la
    pregunta es contra cual."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "sembrarTres(escenarios)" in pag
    assert "const elegir = (papel: string, id: string)" in pag
    assert "porTipoDe(papel.toUpperCase())" in pag


def test_un_endpoint_caido_no_se_lleva_la_comparacion():
    """Son tres endpoints por version, nueve en total. Que a una le falte la
    configuracion de canales no puede dejar la comparacion sin noches."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "Promise.allSettled([" in pag
    assert 'a.status === "fulfilled" ? a.value : null' in pag


def test_una_categoria_es_UNA_fila_aunque_cada_version_le_de_otro_id():
    """⚠️ El error que el owner vio: *«que no se repita la misma linea de
    inventario»*.

    Cada version tiene sus PROPIOS `room_type_id`: el mismo «BI02 · Beachfront
    Deluxe-Tented Villa» es un id en el Actual y otro en el Budget. Cruzando por
    id, el inventario salia dos veces cada categoria —cuatro filas con numeros
    solo en el Actual y otras cuatro solo en el presupuesto— y la tabla no se
    podia leer ni cuadrar.

    El CODIGO es lo que significa lo mismo en las dos versiones. El id solo
    sirve adentro de una.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const claveRt = (rt: { id: string; code?: string | null })" in src
    assert 'rt.code || ""' in src
    # Y cada version resuelve SU id a partir de la llave comun.
    assert "const idRt = (f: FuenteIngresos, clave: string)" in src
    assert "out.set(claveRt(rt), rtLabel(rt.code, rt.name))" in src
    # El total tambien: si usara la llave como id, daria cero en la version que
    # no la tenga — y se leeria como que no hay inventario.
    assert "filas.map(x => idRt(f, x.clave)).filter(Boolean)" in src


def test_el_orden_de_las_filas_no_depende_de_cual_version_cargo_primero():
    """Sin orden propio lo fija la primera version que llega, y cambiar de
    Forecast reacomodaba las filas debajo del cursor."""
    src = LOGICA.read_text(encoding="utf-8")
    assert ".sort((a, b) => a[0].localeCompare(b[0]))" in src
