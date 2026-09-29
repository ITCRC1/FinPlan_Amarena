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
    assert "estadisticasDeLosCortes(cortesDe(mes), d.versiones ?? [])" in pag
    assert 'cuadroTresCortes(d, mes, escenarios, "consolidado", compacto, stats)' in pag


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
