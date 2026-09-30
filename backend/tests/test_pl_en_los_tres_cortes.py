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
    # Una sola llamada PARA DIBUJAR: los tres cortes salen del mismo arreglo.
    #
    # ⚠️ Desde el 2026-09-30 hay una segunda, y es de otra cosa: al bajar el
    # archivo se piden tambien los otros dos AMBITOS —Hotel y Club—, que son
    # otro corte del P&L y no otro corte del tiempo. Lo que este guard defiende
    # es que el mes, el YTD y el año NO sean tres consultas.
    comp = COMP.read_text(encoding="utf-8")
    assert "getPLDetail(ambito, ids[0], ids.slice(1))" in comp
    assert comp.count("getPLDetail(") == 2
    assert "for (const a of AMBITOS)" in comp


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


def test_el_encabezado_NO_se_calcula_en_el_cliente():
    """⚠️ Ocupacion, ADR, RevPAR y los socios son razones y promedios con reglas
    finas que ya viven en `/pl/{id}/estadisticas/`. Rederivarlas aca seria una
    segunda verdad — y una segunda verdad sobre un ADR no cuadra contra nada,
    asi que nadie la ve.

    Owner, 2026-09-29: *«tener cuidado como se calculan los promedios como
    ADR»*.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "export async function estadisticasDeLosCortes" in src
    assert "getEstadisticasCierre(v.scenario_id, desde, hasta)" in src
    # `calc` solo LEE: si aparece una division es que se fabrico otro indicador.
    ini = src.index("export const KPIS")
    bloque = src[ini:src.index("];", ini)]
    for k in ("rooms_available", "rooms_occupied", "guests", "occupancy_pct",
              "adr", "revpar", "club_pagando", "club_pagando_cierre",
              "club_cuota_promedio"):
        assert f"e?.{k} ?? null" in bloque, f"falta el renglon de {k}"
    for linea in (l for l in bloque.splitlines() if "calc:" in l):
        assert "/" not in linea, f"hay una division en KPIS: {linea.strip()}"
    # Un corte por llamada, y el rango sale del PROPIO corte.
    assert "export const rangoDe" in src
    assert "[c.meses[0] + 1, c.meses[c.meses.length - 1] + 1]" in src


def test_el_ADR_es_el_de_las_estadisticas_y_el_RevPAR_es_TRevPAR():
    """⚠️ Los dos errores que este cuadro tuvo y se corrigieron.

    * El **RevPAR** se escribio como ingreso de HABITACIONES / disponibles, que
      es la definicion clasica. El owner la cambio (ver `pl_api._revpar`):
      *«revpar es total revenue per available room»*. Contra el PDF, julio
      2026: 248.437,33 / 930 = 267,14. Con el ingreso de habitaciones daba
      112,52 — un numero perfectamente razonable que mide otra cosa.
    * El **ADR** derivado (ingreso/noches) NO es el del reporte: `REV_ROOMS`
      arrastra ingresos que no son noches vendidas e infla la tarifa en
      silencio ($274,38 contra $255,44 en julio).

    Tomando los dos del endpoint, los dos quedan bien por construccion.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "e?.adr ?? null" in src and "e?.adr_derivado" not in src
    assert "e?.revpar ?? null" in src and "e?.revpar_bruto" not in src
    assert "revpar es total revenue" in src and "per available room" in src
    # Y ya no queda el numerador que se leia de la fila del cuadro.
    assert "ingTotal" not in src and "esIngresoTotal" not in src
    comp = COMP.read_text(encoding="utf-8")
    assert "esIngresoTotal" not in comp


def test_los_socios_de_un_periodo_son_un_PROMEDIO_de_los_meses_con_socios():
    """Owner, 2026-09-29: *«El estadistico de socios pagando y socios de
    cierre. si es YTD se pone promedio mensual igual que full Year y la cuota
    promedio tambien. total sobre total socios»*.

    ⚠️ Las tres reglas viven en el backend (`pl_api`, lineas ~705-760) y el
    cuadro las LEE:

    * `club_pagando` — promedio de los meses CON socios. Amarena abrio el Club
      en marzo: contar enero y febrero en cero bajaria el promedio de 103 a 74.
      Sumar daria 516 socios donde hay 72.
    * `club_pagando_cierre` — el saldo del ultimo mes, que contesta otra
      pregunta. En un mes suelto coincide con el promedio.
    * `club_cuota_promedio` — ingreso del Club / socios-mes. Ponderada, que es
      exactamente «total sobre total».
    """
    src = LOGICA.read_text(encoding="utf-8")
    for rotulo in ("Socios pagando (Club)", "Socios al cierre del mes",
                   "Cuota promedio por socio"):
        assert rotulo in src, f"falta el renglon «{rotulo}»"
    # Un corte de varios meses lleva promedio, y hay que decirlo.
    assert "promEnRango" in src
    comp = COMP.read_text(encoding="utf-8")
    assert "prom." in comp and "promedio mensual" in comp
    assert "PIE_ESTADISTICO" in comp, "el pie que explica el promedio no se dibuja"


def test_sin_Club_los_tres_renglones_no_van_en_blanco():
    """Tres filas vacias se leen como un dato que falta, no como «esta
    propiedad no tiene Club». Y el `null` del backend NO se vuelve cero: un
    cero dice «no hay socios» donde en realidad no hay Club."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "export const esDelClub" in src
    assert "!esDelClub(KPIS[i].rotulo)" in src
    # La pantalla usa la MISMA regla, no una copia.
    comp = COMP.read_text(encoding="utf-8")
    assert "esDelClub(k.rotulo) && vals.every(v => v === null)" in comp
    assert "const esDelClub" not in comp, "la pantalla tiene su propia copia"


def test_el_Word_pide_el_mismo_encabezado_que_la_pantalla():
    """El capitulo arma el mismo cuadro que el boton — incluido el encabezado.
    Si el Word lo derivara por su cuenta, el archivo y la pantalla podrian
    decir cosas distintas justo en la fila que mas se mira."""
    pag = PAGINA.read_text(encoding="utf-8")
    # ⚠️ Y se pide UNA vez para los tres ambitos: el encabezado es de la
    # propiedad, no del ambito.
    assert "stats = stats ?? await estadisticasDeLosCortes(cortesDe(mes)," in pag
    assert "cuadroTresCortes(d, mes, escenarios, a.clave, compacto," in pag


def test_en_el_full_year_la_varianza_es_FORECAST_contra_budget():
    """⚠️ En el año completo el Actual no existe todavia: son los meses
    cargados y nada mas. Restarle doce meses de Budget da una diferencia que
    parece un derrumbe y solo dice que el año no termino.

    El PDF del owner hace lo mismo: su columna de full year es Forecast.
    """
    # La regla vive en el lib: la pantalla, el Excel y el Word tienen que
    # restar el mismo par, o el archivo y la pantalla dirian cosas distintas.
    src = LOGICA.read_text(encoding="utf-8")
    # ⚠️ Desde el 2026-09-30 el contra del ano completo es el CAMPEON de la
    # vista —quien ocupa su primera columna— y solo cae en `iDe("FORECAST")` si
    # la vista no da uno. Antes se buscaba el primer FORECAST de la lista, que
    # puede no ser el que se ve: con dos forecast cargados la columna decia uno
    # y la varianza restaba el otro.
    cuerpo = src[src.index("export function parDe"):src.index("export interface Vista")]
    assert 'iDe("ACTUAL")' in cuerpo
    assert 'tipoDe(versiones[j]?.scenario_id ?? "") === "FORECAST"' in cuerpo
    assert 'iDe("FORECAST")' in cuerpo
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


def test_la_franja_y_el_cuadro_quedan_ALINEADOS():
    """Owner, 2026-09-30: *«necesito que esto quede super alineado»*.

    ⚠️ **Dos tablas HTML distintas no se alinean solas.** Cada una reparte el
    ancho entre sus columnas segun su propio contenido, asi que con los mismos
    datos quedan corridas — y corridas se leen como una sola, con cada numero
    bajo el encabezado del vecino, que es peor que si estuvieran lejos.

    Se alinean cuando coinciden las TRES cosas:

      1. el mismo numero de columnas —por eso la franja tambien lleva su
         varianza, que antes no tenia—;
      2. el mismo ancho, declarado en un solo lugar;
      3. `table-layout: fixed`, que es lo que hace que el navegador OBEDEZCA el
         ancho en vez de estirar la columna del texto mas largo.
    """
    lib = LOGICA.read_text(encoding="utf-8")
    assert "export const ANCHO_ROTULO" in lib and "export const ANCHO_DATO" in lib

    franja = (FRONT / "app/month-end/pl/Estadisticas.tsx").read_text(encoding="utf-8")
    comp = COMP.read_text(encoding="utf-8")
    for fuente, quien in ((franja, "la franja"), (comp, "el cuadro")):
        assert 'tableLayout: "fixed"' in fuente, f"{quien} no fija el ancho"
        assert "<colgroup>" in fuente, f"{quien} no declara sus columnas"
        assert "ANCHO_ROTULO" in fuente and "ANCHO_DATO" in fuente, \
            f"{quien} usa un ancho propio"
    # La franja gano su columna de varianza, con la MISMA regla del par.
    assert "parDe(c, versiones, escenarios)" in franja
    assert "Var" in franja


def test_la_varianza_de_la_franja_sale_de_los_numeros_CRUDOS():
    """⚠️ `valor` ya viene formateado —«27.31%», «$514.31»— y de un texto no se
    saca una diferencia. Por eso cada fila declara su `crudo`.

    Y el formato de la diferencia es el suyo: entre 40,73 % y 25,00 % hay 15,73
    **pp**, y escribirlo con `%` invita a leerlo como un crecimiento del 15,73 %,
    que es otra cosa.
    """
    franja = (FRONT / "app/month-end/pl/Estadisticas.tsx").read_text(encoding="utf-8")
    assert "crudo?: (d: EstadisticasCierre) => number | null;" in franja
    assert 'dif: n => (n * 100).toFixed(2) + "pp"' in franja
    # Sin uno de los dos lados no hay resta: restar de la nada daria el valor
    # entero disfrazado de variacion.
    assert "xa === null || xb === null ? null : xa - xb" in franja


# ═════════ Lo que se rompio y lo que se blindo, 2026-09-30 ═══════════════════

def test_la_vista_se_declara_ANTES_de_usarse():
    """⚠️ Esto se cayo en produccion sin que nada lo dijera.

    La funcion que en el ano completo pone el Forecast Current en la primera
    columna estaba declarada DESPUES de `columnas`, que es quien la usa. Un
    `const` no existe hasta su linea: armar las columnas tiraba «Cannot access
    'viDe' before initialization», y las tres hojas del P&L —Consolidado, Hotel
    y Club— se caian del Excel y del Word. La pantalla atrapa el fallo por
    capitulo, asi que el archivo bajaba con tres tabs menos y sin un error a la
    vista.

    TypeScript NO lo marca: la zona muerta temporal es de ejecucion, no de
    tipos, y `tsc --noEmit` pasaba limpio.
    """
    src = LOGICA.read_text(encoding="utf-8")
    cuerpo = src[src.index("export function cuadroTresCortes"):]
    declara = cuerpo.index("const vista = vistaDe(")
    usa = cuerpo.index("const columnas: ColumnaCuadro[]")
    assert declara < usa, "la vista se usa antes de declararse: el cuadro no se arma"


def test_la_VARIANZA_del_cuadro_baja_como_FORMULA():
    """Owner, 2026-09-30, auditando el Excel: *«los subtotales, totales y
    variaciones deben ser formulas reales»*.

    Un Excel de junta se toca: alguien corrige un actual en una celda y espera
    que la variacion se mueva con el. Con el numero puesto no se mueve, y la
    hoja queda diciendo dos cosas distintas sin que nada avise.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "resta: [colDe(par[0], ci, base)!," in src


def test_la_formula_apunta_a_la_columna_QUE_MUESTRA_cada_operando():
    """⚠️ No al indice en `versiones`.

    En el ano completo la primera columna puede estar mostrando OTRA version
    —el Forecast Current que eligio el usuario— y entonces `=C-D` restaria dos
    columnas que no son las del calculo. Si el operando no esta a la vista no
    hay formula y queda el numero: una celda sin formula se puede revisar; una
    formula que resta lo que no es, no.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "const colDe = (vi: number, ci: number, base: number)" in src
    assert "vista.vi(col, ci) === vi" in src
    assert "colDe(par[0], ci, base) !== null" in src


# ═════════ Quitar el Forecast de las ranuras, 2026-09-30 ═════════════════════
#
# Owner, senalando la ranura 3: *«por ahora voy a quitar la vista del
# comparativo contra el forecast, pero quiero que sea facil de poder
# instalarlo. si dejo la opcion vacio creo que funciona, pero debes considerar
# que en el comparativo full year debe ser Forecast y no debe ser la version
# Actual Final para que contenga los 12 meses»*.

def test_el_forecast_del_ANO_COMPLETO_se_pide_aunque_no_este_en_una_ranura():
    """⚠️ Sin sus doce meses, la primera columna del ano completo es el Actual
    —2.928 noches disponibles donde el ano tiene 5.824— y la caida contra el
    Budget solo significa que el ano no termino.

    Por eso el Forecast Current se PIDE siempre y viaja sin columna propia:
    sacarlo de una ranura deja de compararlo, no rompe el ano.
    """
    comp = COMP.read_text(encoding="utf-8")
    assert "const ids = useMemo(() => {" in comp
    assert "return [...visibles, forecastFull];" in comp
    pagina = (FRONT / "app/month-end/pl/page.tsx").read_text(encoding="utf-8")
    assert "const idsDelPL = useCallback(() => {" in pagina
    assert "return [...puestas, actualFullPL];" in pagina


def test_lo_que_VIAJA_no_es_lo_que_se_DIBUJA():
    """Si el forecast de apoyo tuviera columna, volveria a aparecer en los tres
    cortes — que es justo lo que se quiso quitar."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "export interface Vista {" in src
    assert "columnas: number[];" in src
    assert "vi: (col: number, ci: number) => number;" in src
    comp = COMP.read_text(encoding="utf-8")
    # La pantalla cuenta columnas por la vista, no por las versiones: con el de
    # apoyo contado, todas las divisorias y la columna de varianza se corren.
    assert "versiones.length + (parDe" not in comp
    assert "vista.columnas.length + (parDe" in comp


def test_el_ROTULO_de_la_primera_columna_del_ano_sale_de_la_vista():
    """Con el rotulo de la ranura, la columna diria «ACTUAL Final» encima de
    doce meses de forecast — que es peor que no hacer el cambio."""
    comp = COMP.read_text(encoding="utf-8")
    assert "etiqueta(versiones[vista.vi(col, ci)]?.scenario_id ?? \"\")" in comp
    src = LOGICA.read_text(encoding="utf-8")
    # ⚠️ Desde el 2026-09-30 el rotulo es CORTO —«Actual», «Budget»,
    # «Forecast»— y el periodo va en la segunda linea, pero sale de la misma
    # vista: la primera columna del ano dice «Forecast» porque la vista dice
    # que ahi esta el forecast.
    assert "corto(versiones[vista.vi(col, ci)].scenario_id)" in src


def test_si_el_Forecast_Current_no_cabe_se_usa_CUALQUIER_forecast():
    """Con las cuatro ranuras llenas el backend corta la quinta version en
    silencio. Un forecast de una ranura sigue siendo mejor que el Actual: tiene
    los doce meses."""
    src = LOGICA.read_text(encoding="utf-8")
    assert 'versiones.findIndex(v => tipoDe(v.scenario_id) === "FORECAST")' in src
    assert "const campeon = full >= 0" in src


def test_sin_NINGUN_forecast_el_ano_completo_no_inventa_una_varianza():
    """El ultimo escalon. Restarle doce meses de Budget al Actual da un derrumbe
    que solo dice que el ano no termino: mejor sin columna de varianza."""
    src = LOGICA.read_text(encoding="utf-8")
    cuerpo = src[src.index("export function parDe"):src.index("export interface Vista")]
    assert "if (contra < 0 || contra === budget) return null;" in cuerpo


def test_volver_a_instalarlo_es_elegirlo_en_la_ranura():
    """«quiero que sea facil de poder instalarlo». No hay bandera ni
    configuracion: la ranura ES el interruptor."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "visibles?: string[]" in src
    comp = COMP.read_text(encoding="utf-8")
    assert "const visibles = useMemo(() => ranuras.filter(Boolean)" in comp


def test_la_cabecera_del_cuadro_va_en_DOS_lineas():
    """Owner, 2026-09-30, con una captura: *«esta vista se ve muy cargada y esta
    en la misma celda… podras ver que se usan 2 celdas»*.

    Arriba la version en una palabra, abajo el periodo. Y la raya gruesa en la
    primera columna de cada bloque, que es lo que separa el mes del acumulado y
    del ano.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "sub: c.titulo," in src
    assert '...(col === 0 ? { abre_grupo: true } : {}),' in src
    assert "label: ROTULO_VAR," in src


def test_dos_versiones_del_MISMO_TIPO_no_se_llaman_igual():
    """⚠️ Pasa de verdad: un forecast en una ranura y el Forecast Current
    ocupando el ano completo. Dos columnas que dicen «Forecast» no se
    distinguen, y el rotulo corto dejaria de identificar la version, que es lo
    unico que tiene que hacer."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "export function rotulosDeVersion(" in src
    assert "repetido.has(e.type) ? `${base} ${e.version}` : base" in src


def test_el_rotulo_corto_es_UNO_para_todos_los_armados():
    """El P&L, los checkbooks y el armado bajan al mismo archivo: tres tablas
    que llaman distinto a la misma version se leen como versiones distintas."""
    for ruta in ("lib/tresCortes.ts", "lib/checkbookCortes.ts",
                 "lib/revenuePlanPaquete.ts"):
        s = (FRONT / ruta).read_text(encoding="utf-8")
        assert "ROTULO_VAR" in s, f"{ruta} escribe su propio rotulo de varianza"
        if "tresCortes" not in ruta:
            assert "rotulosDeVersion" in s, f"{ruta} arma su propio rotulo corto"
