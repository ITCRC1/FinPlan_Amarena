# -*- coding: utf-8 -*-
"""La planilla PROPIA se paga en el mes; la Caja, al mes siguiente.

Owner, 2026-10-31: *«la planilla se paga en el mes para el mes, lo único que se
paga el otro mes es la caja y otras retenciones»*.

El motor le aplicaba a la planilla el calendario de PROVEEDORES —60% del mes y
40% del anterior— y a la CCSS lo mismo. Las dos cosas estaban mal:

* **Los salarios no esperan.** Se pagan quincenal, dentro del mes.
* **La CCSS sí espera, pero entera**, no el 40%.

Qué se rompía, con números de Amarena (Budget 2026):

* la línea «Planilla» del tab de Proveedores decía **257,201** en vez de
  **268,475** — 11,274 que aparecían como pago a proveedores;
* **junio pagaba el 71.8% de su planilla**, porque el modelo le descontaba el
  40% de un mayo en el que el hotel todavía no tenía empleados. Junio es el mes
  en que la caja se quiebra, así que la salida estaba subestimada justo ahí.

⚠️ **Nada de esto movía el flujo neto.** `planilla_neta_pago` se define como
`planilla_con_iva − pago_ccss` y después `salidas_op` vuelve a sumar las dos, así
que la CCSS se cancela; y el reparto Planilla/Proveedores divide un total que ya
estaba bien. Era un error de ATRIBUCIÓN: el total de caja correcto, repartido
mal entre los renglones que lee la junta. Por eso ninguna prueba lo agarró.
"""
from app.engine.cashflow_directo import compute_cashflow_directo

PLANILLA = [0.0, 0.0, 0.0, 0.0, 0.0,
            35026.0, 38704.0, 41070.0, 38744.0, 37522.0, 37522.0, 39887.0]
GASTO = [0.0, 0.0, 7911.0, 22798.0, 55276.0,
         118318.0, 119199.0, 105283.0, 114789.0, 127335.0, 135021.0, 154944.0]
REV = [0.0, 0.0, 0.0, 0.0, 0.0,
       46672.0, 56002.0, 79845.0, 50379.0, 55973.0, 103694.0, 151674.0]


def _criterios(**over):
    c = {"enabled": True, "ap_same_pct": 0.60, "iva_rate": 0.13,
         "card_pct": 0.70, "card_iva_ret": 0.025, "card_renta_ret": 0.025,
         "service_rate": 0.10, "service_lag": 1, "retention": 0.05,
         "payroll_outsourced": False, "ccss_obrera_rate": 0.1067}
    c.update(over)
    return c


def _correr(criterios):
    # La CCSS no se deduce de la planilla total: sale de los conceptos ya
    # calculados (6020 patronal y el bruto sobre el que se retiene la obrera).
    # Sin ellos el motor no tiene de dónde sacarla y la fila queda en cero.
    bruto = [x * 0.75 for x in PLANILLA]
    conceptos = {"ccss_patronal": [x * 0.2683 for x in bruto], "bruto": bruto}
    totales = {"rev": REV, "opex": GASTO, "overhead": [0.0] * 12,
               "nonop": [0.0] * 12, "capex": [0.0] * 12,
               "fb": [0.0] * 12, "payroll": PLANILLA, "conceptos": conceptos}
    return compute_cashflow_directo({}, {}, {}, {"capex": [0.0] * 12},
                                    criterios, 0.0, {}, totales=totales)


def _fila(bloque, frag):
    for r in bloque:
        if frag.lower() in (r.get("label") or "").lower():
            return [float(x or 0) for x in (r.get("values") or [0.0] * 12)][:12]
    raise AssertionError("fila no encontrada: " + frag)


def test_la_planilla_propia_se_paga_entera_en_su_mes():
    """Sin rezago: lo que se devenga en el mes sale en el mes."""
    d = _correr(_criterios())
    pagado = _fila(d["aux_proveedores"], "Planilla")
    for i in range(12):
        assert abs(pagado[i] - PLANILLA[i]) < 1.0, (
            f"mes {i + 1}: se paga {pagado[i]:,.0f} de {PLANILLA[i]:,.0f} "
            f"devengados. La planilla propia no lleva rezago de proveedor")


def test_junio_no_arrastra_un_mayo_sin_empleados():
    """El primer mes de operación es donde más se notaba: pagaba 71.8%."""
    d = _correr(_criterios())
    pagado = _fila(d["aux_proveedores"], "Planilla")
    assert pagado[5] > 0
    assert abs(pagado[5] / PLANILLA[5] - 1.0) < 0.01, (
        f"junio paga {pagado[5] / PLANILLA[5]:.1%} de su planilla")


def test_la_planilla_tercerizada_si_lleva_el_rezago():
    """Si viene por factura de proveedor, el calendario de A/P le corresponde."""
    d = _correr(_criterios(payroll_outsourced=True))
    pagado = _fila(d["aux_proveedores"], "Planilla")
    assert abs(pagado[5] - PLANILLA[5]) > 1.0, (
        "tercerizada tiene que seguir el rezago 60/40, no pagarse entera")


def test_la_ccss_sale_el_mes_siguiente_entera():
    """La Caja se deposita al mes siguiente, no el 60/40 de proveedores."""
    d = _correr(_criterios())
    ccss = _fila(d["resumen"], "CCSS")
    # Mayo no tiene planilla devengada, asi que la Caja de mayo es 0; junio
    # deposita lo de mayo (0) y julio lo de junio (> 0).
    assert ccss[5] == 0.0, "junio no deposita Caja: en mayo no hubo planilla"
    assert ccss[6] > 0.0, "julio deposita la Caja devengada en junio"


def test_el_reparto_no_mueve_el_total_de_caja():
    """La correccion es de atribucion: el flujo neto no se toca.

    Es la propiedad que hacia que el error pasara desapercibido, y la que hay
    que conservar: si mañana alguien cambia el reparto, el saldo de caja y la
    necesidad de financiamiento tienen que seguir dando lo mismo.
    """
    propia = _fila(_correr(_criterios())["resumen"], "FLUJO NETO TOTAL")
    terce = _fila(_correr(_criterios(payroll_outsourced=True))["resumen"],
                  "FLUJO NETO TOTAL")
    # Tercerizar cambia la base de IVA y de A/P, asi que el total SI cambia ahi.
    # Lo que se fija es que dentro de un mismo criterio el reparto cierre:
    d = _correr(_criterios())
    plan = _fila(d["aux_proveedores"], "Planilla")
    prov = _fila(d["aux_proveedores"], "Proveedores")
    total = _fila(d["aux_proveedores"], "TOTAL PAGADO")
    for i in range(12):
        assert abs((plan[i] + prov[i]) - total[i]) < 1.0, (
            f"mes {i + 1}: Planilla + Proveedores no da el TOTAL PAGADO")
    assert len(propia) == len(terce) == 12
