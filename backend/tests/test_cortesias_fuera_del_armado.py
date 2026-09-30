# -*- coding: utf-8 -*-
"""Las estancias de cortesia NO cuentan en el desglose por categoria.

Owner, 2026-09-30, viendo 218 noches en el armado de ingresos y 202 en el
encabezado estadistico del mismo archivo: *«hay que sacar, si se puede, las
estancias que son complementary»*.

## Lo que pasaba

La regla YA existia: un market code se marca con `cuenta_para_kpis = False`
desde la pantalla del PMS, y ahi mismo dice «CPL no cuenta: los numeros de las
cuatro vistas lo excluyen». `scenario_stats` —lo que alimenta el encabezado— ya
salia sin esas noches.

El desglose por categoria, no. `actual_room_stats` guarda el TOTAL del PDF, y
`_room_stats_from_actuals` lo devolvia tal cual. En agosto 2026 de Amarena son
16 noches de CPL con ingreso cero: el armado decia 218 noches y ADR $236,47
donde el cierre dice 202 y $255,20. Dos numeros para la misma pregunta, en
hojas vecinas del mismo libro.

## ⚠️ Lo guardado no cambia

`actual_room_stats` sigue siendo el archivo y sigue cuadrando contra el PDF.
Esto mueve la base con la que se MUESTRA el desglose, que es la misma que ya
usaban los indicadores.
"""
import pathlib

API = (pathlib.Path(__file__).resolve().parents[1] / "app/api/revenue_api.py")


def _src() -> str:
    return API.read_text(encoding="utf-8")


def test_el_desglose_le_RESTA_lo_que_no_cuenta():
    src = _src()
    assert "async def _cortesia(" in src
    assert "fuera = await _cortesia(scenario_id, db)" in src
    # Y se resta en los dos armados: el mes a mes y el anual.
    assert src.count('q.get("noches", 0.0)') == 1
    assert 'sum(v["noches"] for v in q)' in src


def test_las_DISPONIBLES_no_se_tocan():
    """⚠️ La habitacion estuvo disponible aunque la noche se haya regalado.
    Restarlas subiria la ocupacion en vez de bajarla."""
    src = _src()
    cuerpo = src[src.index("async def _room_stats_from_actuals"):]
    cuerpo = cuerpo[:cuerpo.index("@router.get")]
    assert 'na = float(rec.nights_available) if rec else 0.0' in cuerpo
    assert 'na = float(rec.nights_available) - ' not in cuerpo
    assert 'nights_available) for s in stats if s.room_type_name == nm)\n' in cuerpo


def test_un_codigo_SIN_canal_asignado_SI_cuenta():
    """⚠️ Un market code que nadie clasifico todavia es una venta a la que le
    falta el canal, no una cortesia: descontarlo seria borrar ingreso real.

    En Amarena hay tres asi —CAST CENTRAL AMERICA, PROMOCIONES, RESONLINE— y
    entre los tres son la mayor parte del mes.
    """
    src = _src()
    assert "if mc is None or mc.cuenta_para_kpis:" in src
    assert "continue" in src.split("if mc is None or mc.cuenta_para_kpis:")[1][:40]


def test_la_regla_es_la_MISMA_que_la_del_PMS():
    """No se inventa un criterio nuevo: se lee `cuenta_para_kpis`, que es el que
    el owner marca en la pantalla del PMS. Con dos criterios, el dia que
    desmarque otro codigo el armado seguiria contandolo."""
    src = _src()
    assert "mc.cuenta_para_kpis" in src
    modelo = (pathlib.Path(__file__).resolve().parents[1]
              / "app/models/market_code.py").read_text(encoding="utf-8")
    assert "cuenta_para_kpis: Mapped[bool]" in modelo


# ═════════ Los canales de verdad reemplazan a su configuracion ═══════════════

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"


def test_la_hoja_de_CANALES_trae_los_del_PMS_y_no_la_configuracion():
    """Owner, 2026-09-30, tachando la hoja «Canales de venta»: *«poner este
    nuevo tab aca, y cambiar lo que sale actualmente como canales»*.

    ⚠️ Lo que salia no eran los canales: era su CONFIGURACION —«Direct · mix
    45%», «Travel Agency · comision»—, que es lo que se parametriza para
    calcular la tarifa neta. Para el Actual salia VACIA, porque un actual no
    tiene mix presupuestado.
    """
    lib = (FRONT / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    assert "export function cuadroCanalesDelPms(" in lib
    paquete = (FRONT / "lib/revenuePlanPaquete.ts").read_text(encoding="utf-8")
    assert '{ key: "canales", rotulo: "Canales de venta" },' not in paquete
    pagina = (FRONT / "app/month-end/pl/page.tsx").read_text(encoding="utf-8")
    assert '{ key: "canalespms", rotulo: "Canales del PMS" },' in pagina
    assert "cuadroCanalesDelPms(a)" in pagina


def test_el_ADR_por_canal_NO_se_promedia():
    """El ADR de un canal en el acumulado es su ingreso sobre sus noches.
    Promediar le daria el mismo peso a un mes de dos noches que a uno de
    cuarenta."""
    lib = (FRONT / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    cuerpo = lib[lib.index("export function cuadroCanalesDelPms"):]
    assert "d.noches ? d.rev / d.noches : null" in cuerpo
    assert "/ 12" not in cuerpo and "length" not in cuerpo.split("filas.push")[0]


def test_el_TOTAL_son_las_noches_que_CUENTAN():
    """Y debajo va el archivo entero, para poder cuadrar contra el PDF sin
    abrir la aplicacion."""
    lib = (FRONT / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    cuerpo = lib[lib.index("export function cuadroCanalesDelPms"):]
    assert 'label: "TOTAL", es_total: true' in cuerpo
    assert '"Con todos los canales (PDF)"' in cuerpo
    # La cortesia se LISTA —no se esconde— con su columna que dice que no cuenta.
    assert 'd.cuenta ? "Sí" : "No"' in cuerpo


def test_un_mes_sin_cargar_NO_entra():
    """Un cero se lee como «ese canal no vendio», y con una propiedad que abrio
    a mitad de ano eso convierte un acumulado incompleto en un mal semestre."""
    lib = (FRONT / "lib/resumenConsolidado.ts").read_text(encoding="utf-8")
    cuerpo = lib[lib.index("export function cuadroCanalesDelPms"):]
    assert "if (!m.cargado) continue;" in cuerpo
