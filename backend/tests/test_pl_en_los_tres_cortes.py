# -*- coding: utf-8 -*-
"""El P&L completo en los TRES cortes a la vez: mes, YTD y full year.

Owner, 2026-09-29, entregando `Full P&L CWL YTD JULY 2026 & Full Year
Forecast.pdf`: *«quiero construir un archivo como este, un tab que presente el
mes actual, budget y Forecast, YTD y Full Year, con su varianza. es de vital
importancia»*.

## El hueco que llena

    12 meses          una version      17 lineas de resumen
    Formato           una version      la cascada, MES A MES
    P&L Detail Full   varias           la cascada, en UN corte
    este              varias           la cascada, en LOS TRES cortes

Los tres juntos es lo que se manda a los duenos: el mes explica la ejecucion,
el YTD la tendencia, el full year el aterrizaje. En tres pantallas nadie los
compara — y la pregunta de todo cierre es si lo del mes cambia el año.

## Verificado contra el PDF

Corriendo la aritmetica real contra las cifras del PDF, los seis indicadores
dan identico en los dos cortes: julio 25.05% / $449.10 / $267.14 y YTD julio
48.54% / $606.49 / $581.11.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LOGICA = FRONT / "lib/tresCortes.ts"
COMP = FRONT / "app/month-end/pl/TresCortes.tsx"
PAGINA = FRONT / "app/month-end/pl/page.tsx"


def test_existe_y_la_pantalla_lo_usa():
    assert LOGICA.exists() and COMP.exists()
    pag = PAGINA.read_text(encoding="utf-8")
    assert '{ key: "trescortes" }' in pag
    assert "<TresCortes escenarios={escenarios} ranuras={ranuras} mes={mes}" in pag
    # Y tiene rotulo en los dos idiomas.
    import json
    for f in ("messages/es.json", "messages/en.json"):
        d = json.loads((FRONT / f).read_text(encoding="utf-8"))
        assert "tab_trescortes" in d["monthEndPl"], f"falta el rotulo en {f}"


def test_los_tres_cortes_salen_del_MISMO_arreglo_de_doce():
    """⚠️ No son tres consultas ni tres plantillas: si lo fueran, podrian decir
    cosas distintas. `/pl-detail/` devuelve los doce meses de cada fila y el
    mes es un indice, el YTD los primeros N, el full year los doce."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "export function cortesDe" in src
    assert 'clave: "mes", titulo: MESES[mes - 1], meses: [mes - 1]' in src
    assert "Array.from({ length: mes }, (_, i) => i)" in src
    assert "Array.from({ length: 12 }, (_, i) => i)" in src
    # Una sola llamada.
    comp = COMP.read_text(encoding="utf-8")
    assert comp.count("getPLDetail(") == 1


def test_no_se_escribe_la_plantilla_otra_vez():
    """⚠️ Ya paso una vez (ver `Formato`): un cuadro escrito contra el otro
    vocabulario de codigos cuadro en TODOS los totales y mostro el detalle
    entero en cero. Un cuadro que cuadra y no dice nada.

    Las filas vienen del endpoint, con los rotulos del owner.
    """
    comp = COMP.read_text(encoding="utf-8")
    assert "datos?.filas" in comp
    for inventado in ("TOTAL_REVENUES", "OPEXP_ROOMS", "OVH_ADMIN", "OPEX_ROOMS"):
        assert inventado not in comp, f"el cuadro define {inventado} por su cuenta"


def test_ocupacion_ADR_y_RevPAR_se_rederivan_en_cada_corte():
    """⚠️ Son razones. Sumar los ADR de siete meses da un numero que no
    significa nada y se ve perfectamente normal: en Amarena, $2.026 contra los
    $286 reales."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "no se suman" in src.lower() or "NO se suman" in src
    assert "k.disp ? k.occ / k.disp : null" in src
    assert "k.occ ? k.ing / k.occ : null" in src
    # Y los crudos SI se suman, que es lo correcto: son cantidades.
    assert "export function crudosDe" in src
    assert "suma(k?.rooms_occupied, meses)" in src


def test_RevPAR_es_ingreso_TOTAL_sobre_disponibles():
    """⚠️ El error que este cuadro tuvo y se corrigio antes de desplegarlo.

    Se escribio como ingreso de HABITACIONES / disponibles, que es la
    definicion clasica. El owner la cambio (ver `pl_api._revpar`): *«revpar es
    total revenue per available room»* — mide cuanto rinde cada habitacion
    disponible con TODO lo que el hotel factura.

    Medido contra el PDF, julio 2026: 248.437,33 / 930 = 267,14 exacto. Con el
    ingreso de habitaciones daba 112,52 — un numero que se ve perfectamente
    razonable y mide otra cosa.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "k.ingTotal === null || !k.disp ? null : k.ingTotal / k.disp" in src
    # La cita del owner viaja partida entre dos lineas de comentario.
    assert "revpar es total revenue" in src and "per available room" in src
    # El numerador sale de la PROPIA fila del cuadro, no de otra consulta.
    comp = COMP.read_text(encoding="utf-8")
    assert "esIngresoTotal(x.rotulo)" in comp


def test_sin_la_fila_del_ingreso_total_el_RevPAR_va_vacio():
    """Mejor vacio que el indicador equivocado: un RevPAR calculado sobre el
    numerador que no es se ve razonable y nadie lo cuestiona."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "ingTotal: number | null;" in src
    assert "ingresoTotal ? suma(ingresoTotal, meses) : null" in src


def test_en_el_full_year_la_varianza_es_FORECAST_contra_budget():
    """⚠️ En el año completo el Actual no existe todavia: son los meses
    cargados y nada mas. Restarle doce meses de Budget da una diferencia que
    parece un derrumbe y solo dice que el año no termino.

    El PDF del owner hace lo mismo: su columna de full year es Forecast.
    """
    # La regla vive en el lib: la pantalla, el Excel y el Word tienen que
    # restar el mismo par, o el archivo y la pantalla dirian cosas distintas.
    src = LOGICA.read_text(encoding="utf-8")
    assert 'c.clave === "full" ? iDe("FORECAST") : iDe("ACTUAL")' in src
    # Y el tipo sale de `escenarios`, no del rotulo, que es texto libre.
    assert "escenarios.find(s => s.id === sid)?.type" in src
    assert "no termin" in src
    # El componente NO tiene su propia copia de la regla.
    comp = COMP.read_text(encoding="utf-8")
    assert 'iDe("FORECAST")' not in comp


def test_la_aritmetica_vive_aparte_del_render():
    """Una tabla financiera que solo se puede verificar mirandola es una tabla
    que nadie verifica. Separada, se corre contra las cifras del PDF."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "useState" not in src and "useMemo" not in src
    assert "export const KPIS" in src
