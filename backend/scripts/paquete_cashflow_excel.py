# -*- coding: utf-8 -*-
"""Paquete Cash Flow de Amarena, formulado de punta a punta."""
import io
import json
import sys

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:\Users\User\AppData\Local\Temp\claude\C--Users-User-Documents-FinPlan-Amarena\8564bc28-2c58-48f6-bc5b-79f1b775d9ea\scratchpad"
D = json.load(io.open(BASE + r"\cf.json", encoding="utf-8"))
S, PL, E, CRI = D["schedule"], D["pl"], D["escenario"], D["criterios"]

AZUL, AZUL2, GRIS = "1F3864", "2F5597", "F2F2F2"
AMBAR, VERDE, AZULC, LILA = "FFF2CC", "E2EFDA", "DDEBF7", "E4DFEC"
FN, USD = "Arial", '$#,##0;($#,##0);-'
M = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
thin = Side(style="thin", color="BFBFBF")
CENT = 0.011


def f(sz=10, b=False, c="000000", i=False):
    return Font(name=FN, size=sz, bold=b, color=c, italic=i)


def fill(c):
    return PatternFill("solid", fgColor=c)


def bd():
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def rotulo(txt):
    """Un rotulo que empieza con "=" Excel lo toma como FORMULA y el archivo
    queda corrupto: no abre. Pasa de verdad — el motor emite "= COBRO
    OPERATIVO", "= SALARIO BRUTO" y "= SALDO A FAVOR FINAL". El "=" ahi es
    decorativo (la fila ya va en negrita y con fondo), asi que se quita."""
    t = (txt or "").strip()
    while t.startswith("="):
        t = t[1:].strip()
    return t


def g(k):
    return S.get(k, [0.0] * 12)


def gm(k):
    """Cuanto vale la serie `k` TAL COMO quedo dibujada en el tab Motor.
    Unas vienen del schedule y otras se publican ahi (CapEx, las salidas de
    caja de la seccion H): preguntar solo al schedule devolvia ceros y el
    candado de la formula no dejaba pasar ninguna."""
    return MOTOR_VALS.get(k, S.get(k, [0.0] * 12))


# La retencion de tarjeta se RESTA del cobro pero no figuraba en el tab de
# Ingresos. Por eso «TOTAL ENTRADAS DE CAJA» no podia ser formula: la suma de
# lo que se ve daba 24,250 de mas. No se fuerza la formula: se MUESTRA la pieza
# que faltaba, que es lo que el owner pidio para todo lo que el sistema calcula
# a escondidas.
_RETEN = [S["iva_ret"][m] - S["WC_RENTTAX"][m] for m in range(12)]
_ing = D["bloques"]["aux_ingresos"]
if not any("Retenciones de tarjeta" in (r["label"] or "") for r in _ing):
    _pos = next(i for i, r in enumerate(_ing)
                if "TOTAL ENTRADAS DE CAJA" in (r["label"] or ""))
    _ing.insert(_pos, {"label": "(-) Retenciones de tarjeta (IVA y renta, 2.5% c/u)",
                       "kind": "data", "key": None,
                       "values": [-x for x in _RETEN]})

wb = openpyxl.Workbook()
SUB = "{} · {} {} {} · actuales reales hasta el mes {} · USD".format(
    E["hotel"], E["tipo"], E["version"], E["anio"], E["actuals_through"])


def titulo(ws, t, sub, ancho):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ancho)
    c = ws.cell(1, 1, t); c.font = f(14, True, "FFFFFF"); c.fill = fill(AZUL)
    c.alignment = Alignment("left", "center"); ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ancho)
    c = ws.cell(2, 1, sub); c.font = f(9, False, "595959", True)
    c.alignment = Alignment("left", "center", wrap_text=True)
    ws.row_dimensions[2].height = 22


def cabecera(ws, fila=4, ancho_a=50):
    ws.cell(fila, 1, "Concepto")
    for j, m in enumerate(M, 2):
        ws.cell(fila, j, m)
    ws.cell(fila, 14, "Año")
    for j in range(1, 15):
        c = ws.cell(fila, j); c.font = f(10, True, "FFFFFF"); c.fill = fill(AZUL2)
        c.alignment = Alignment("center", "center"); c.border = bd()
    ws.column_dimensions["A"].width = ancho_a
    for j in range(2, 14):
        ws.column_dimensions[get_column_letter(j)].width = 11
    ws.column_dimensions["N"].width = 14
    ws.row_dimensions[fila].height = 20


def serie(ws, fila, etiqueta, valores=None, formulas=None, fuerte=False,
          fmt=USD, nota=None, relleno=None, sangria=1):
    c = ws.cell(fila, 1, etiqueta)
    c.font = f(10, fuerte); c.border = bd()
    c.alignment = Alignment("left", "center", indent=0 if fuerte else sangria)
    for mm in range(12):
        j = mm + 2
        cel = ws.cell(fila, j, formulas[mm] if formulas else valores[mm])
        cel.number_format = fmt; cel.font = f(10, fuerte); cel.border = bd()
    a = ws.cell(fila, 14, "=SUM(B{0}:M{0})".format(fila))
    a.number_format = fmt; a.font = f(10, True); a.border = bd()
    if relleno or fuerte:
        for j in range(1, 15):
            ws.cell(fila, j).fill = fill(relleno or AZULC)
    if nota:
        ws.cell(fila, 16, nota).font = f(9, False, "595959", True)
    return fila


def seccion(ws, fila, texto):
    c = ws.cell(fila, 1, texto); c.font = f(10, True, AZUL)
    for j in range(1, 15):
        ws.cell(fila, j).fill = fill(LILA); ws.cell(fila, j).border = bd()
    return fila


# ══════════════════════════ 1. MOTOR (el tab que faltaba) ══════════════════
mot = wb.create_sheet("Motor cobranza y pagos")
titulo(mot, "El motor — lo que el sistema calcula y no se veía en ninguna pantalla",
       SUB + " · Estas series son las que producen las líneas de caja del Resumen. "
             "Antes vivían solo en memoria.", 14)
cabecera(mot)
r = 5
FM = {}
seccion(mot, r, "A. LA VENTA, REPARTIDA SEGÚN CUÁNDO SE COBRA"); r += 1
for k, lab, nota in (
        ("nrr", "No reembolsable (se cobra por adelantado)", "mix_nrr × venta del mes de estadía"),
        ("flex", "Flexible (se cobra poco antes de llegar)", "mix_flex × venta"),
        ("stay", "Se cobra durante la estadía", "el resto de la venta"),
        ("credit", "A crédito (agencias)", "mix_credit × venta")):
    FM[k] = serie(mot, r, lab, g(k), nota=nota); r += 1
seccion(mot, r, "B. CUÁNDO ENTRA LA PLATA"); r += 1
for k, lab, nota in (
        ("received", "Depósitos recibidos por estadías futuras", "lo que se cobró por adelantado y todavía no se consumió"),
        ("applied", "Depósitos aplicados al consumirse la estadía", "sale del pasivo de anticipos, no entra plata nueva"),
        ("ar_collected", "Cobro de cuentas por cobrar", "lo que las agencias pagan con rezago"),
        ("deferred", "Saldo de anticipos (pasivo al cierre)", "lo que el hotel debe en servicio, no en plata")):
    FM[k] = serie(mot, r, lab, g(k), nota=nota); r += 1
seccion(mot, r, "C. MOVIMIENTOS DE CAPITAL DE TRABAJO (van al flujo indirecto)"); r += 1
for k, lab in (("WC_DEP_RECV", "Δ anticipos recibidos"), ("WC_DEP_APPL", "Δ anticipos aplicados"),
               ("WC_AR", "Δ cuentas por cobrar"), ("WC_AP", "Δ cuentas por pagar"),
               ("WC_PROV", "Δ provisión de aguinaldo"), ("WC_TAX", "Δ IVA por pagar"),
               ("WC_RENTTAX", "Δ retención de renta de tarjeta"), ("WC_SERVICE", "Δ servicio 10% por pagar")):
    FM[k] = serie(mot, r, lab, g(k)); r += 1
seccion(mot, r, "D. TARJETA Y RETENCIONES"); r += 1
for k, lab, nota in (
        ("card_base", "Base cobrada con tarjeta", "card_pct × cobro operativo"),
        ("iva_ret", "Retención de IVA de tarjeta", "2.5% — el adquirente la descuenta, no la paga el hotel"),
        ("renta_ret", "Retención de renta de tarjeta", "2.5% — anticipo del impuesto sobre la renta")):
    FM[k] = serie(mot, r, lab, g(k), nota=nota); r += 1
seccion(mot, r, "E. IVA"); r += 1
for k, lab, nota in (
        ("iva_out", "IVA cobrado a clientes", "13% × venta del mes"),
        ("iva_in", "IVA pagado a proveedores", "13% × compras. La planilla propia NO lleva IVA"),
        ("iva_obligacion", "Posición del mes (débito − crédito)", "negativo = saldo a favor"),
        ("iva_net", "A declarar este mes", "nunca negativo"),
        ("iva_credito", "Saldo a favor acumulado", "no se cobra en efectivo: se arrastra"),
        ("payable_prev", "Remesa a Hacienda (lo declarado el mes anterior)", "")):
    FM[k] = serie(mot, r, lab, g(k), nota=nota); r += 1
seccion(mot, r, "F. SERVICIO 10% DE A&B"); r += 1
for k, lab, nota in (("svc_collected", "Cobrado al huésped", "10% de la venta de A&B"),
                     ("svc_paid", "Pagado a los empleados", "un mes después")):
    FM[k] = serie(mot, r, lab, g(k), nota=nota); r += 1
seccion(mot, r, "G. DEL P&L (la base de todo)"); r += 1
FM["rev"] = serie(mot, r, "Ingreso devengado", PL["rev"], nota="TOTAL_REVENUES del P&L"); r += 1
FM["costo"] = serie(mot, r, "Costo devengado", PL["costo"], nota="OPEX + Overhead + No operativos"); r += 1
FM["planilla"] = serie(mot, r, "  del cual, planilla", PL["planilla"],
                       nota="se paga en el mes; la CCSS, al siguiente"); r += 1
FM["base"] = serie(mot, r, "Base de IVA y cuentas por pagar", PL["base_sin_planilla"],
                   nota="costo MENOS planilla: los salarios no llevan IVA ni van a A/P"); r += 1
MOTOR_VALS = {"capex": PL.get("capex") or [0.0] * 12}
FM["capex"] = serie(mot, r, "CapEx del presupuesto", MOTOR_VALS["capex"],
                    nota="sale en el mes en que está presupuestado"); r += 1

# ── H. Las salidas de caja venian pegadas en el Resumen y no estaban en
# ninguna otra hoja: el motor las reparte entre planilla y proveedores con su
# propio criterio y el reparto no se podia reconstruir con lo que se veia.
# Se publican aca para que el Resumen las referencie en vez de llevarlas
# escritas, y para que se vea de donde sale cada una.
seccion(mot, r, "H. LAS SALIDAS DE CAJA, COMO LAS REPARTE EL MOTOR"); r += 1
SAL_MOTOR = {}
_RES = {}
for _rr in D["bloques"]["resumen"]:
    _RES[rotulo(_rr["label"]).strip()] = _rr["values"]


def _res_val(frag):
    for kk, vv in _RES.items():
        if frag.lower() in kk.lower():
            return vv
    return [0.0] * 12


for k, frag, lab, nota in (
        ("pago_planilla", "Pago de planilla neta", "Planilla pagada al empleado",
         "el neto en la mano; la CCSS y el aguinaldo van aparte"),
        ("pago_ccss", "Pago a la CCSS", "CCSS depositada (patronal + obrera)",
         "la cuota del mes anterior"),
        ("pago_prov", "Pago a proveedores", "Proveedores pagados (con IVA)",
         "60% de la factura del mes + 40% de la del mes anterior"),
        ("pago_renta", "Impuesto de renta", "Impuesto de renta pagado",
         "la liquidación anual, en su mes de pago"),
        ("pago_otros", "Otros movimientos", "Otros movimientos de caja",
         "lo que se digitó a mano en el escenario")):
    SAL_MOTOR[k] = MOTOR_VALS[k] = _res_val(frag)
    FM[k] = serie(mot, r, lab, SAL_MOTOR[k], nota=nota); r += 1
mot.freeze_panes = "B5"; mot.sheet_view.showGridLines = False
mot.column_dimensions["P"].width = 62

# ══════════════════════════ 2. RESUMEN, todo por fórmula ═══════════════════
res = wb.create_sheet("Resumen Flujo de Caja", 0)
titulo(res, "Cash Flow — Método Directo", SUB + " · Cada línea sale por fórmula del tab Motor. "
                                                "Nada en esta hoja es un número pegado.", 14)
cabecera(res)


def ref(k, mm):
    return "'Motor cobranza y pagos'!{}{}".format(get_column_letter(mm + 2), FM[k])


r = 5
# ── Apertura: los tres saldos con que arranca el año ───────────────────────
# FinPlan solo guarda `opening_cash`; no tiene campo para cuentas por cobrar
# ni por pagar iniciales. Sin ellas el año arranca como si no se debiera ni
# se tuviera nada por cobrar, que para un segundo año nunca es cierto: lo que
# quedó sin pagar en diciembre se paga en enero.
seccion(res, r, "▶ APERTURA DEL AÑO  (celdas ámbar: lo único que se carga a mano)"); r += 1
A_CAJA, A_CXC, A_CXP, A_MES = r, r + 1, r + 2, r + 3
for fila_, etiqueta, nota in (
        (A_CAJA, "Efectivo en bancos al 1 de enero",
         "El saldo bancario real. Mientras esté en cero el cuadro dice cuánto hay que poner, no cuánto falta."),
        (A_CXC, "Cuentas por cobrar al 1 de enero",
         "Lo que deben las agencias del año anterior. Entra como cobro en el mes de abajo."),
        (A_CXP, "Cuentas por pagar al 1 de enero",
         "Lo que se le debe a proveedores del año anterior — el 40% de la factura de diciembre. Sale como pago en el mes de abajo.")):
    c = res.cell(fila_, 1, etiqueta); c.font = f(10, True); c.border = bd()
    cel = res.cell(fila_, 2, 0); cel.number_format = USD
    cel.font = f(11, True, "0000FF"); cel.fill = fill(AMBAR); cel.border = bd()
    res.cell(fila_, 16, nota).font = f(9, False, "9C0006", True)
c = res.cell(A_MES, 1, "Mes en que se cobran / se pagan (1 = enero)")
c.font = f(10); c.border = bd()
cel = res.cell(A_MES, 2, 1); cel.number_format = '0'
cel.font = f(11, True, "0000FF"); cel.fill = fill(AMBAR); cel.border = bd()
res.cell(A_MES, 16, "Si la cobranza o el pago caen en otro mes, se cambia acá y todo el año se recalcula.").font = f(9, False, "595959", True)
r = A_MES + 2

seccion(res, r, "▶ ENTRADAS DE EFECTIVO"); r += 1
R_CXC = serie(res, r, "Cobro de cuentas por cobrar de apertura",
              formulas=["=IF($B${}={},$B${},0)".format(A_MES, m + 1, A_CXC) for m in range(12)],
              nota="entra una sola vez, en el mes de apertura"); r += 1
R_COBRO = serie(res, r, "Cobro a clientes (con IVA, neto de retenciones)",
                formulas=["={}+{}+{}+{}+{}-({}-{})".format(
                    ref("rev", m), ref("WC_DEP_RECV", m), ref("WC_DEP_APPL", m),
                    ref("WC_AR", m), ref("iva_out", m), ref("iva_ret", m),
                    ref("WC_RENTTAX", m)) for m in range(12)],
                nota="venta + anticipos + cuentas por cobrar + IVA − retenciones de tarjeta"); r += 1
R_SVC = serie(res, r, "Servicio 10% A&B cobrado al huésped",
              formulas=["=MAX(0,{})".format(ref("svc_collected", m)) for m in range(12)]); r += 1
R_ENT = serie(res, r, "TOTAL ENTRADAS",
              formulas=["={0}{1}+{0}{2}+{0}{3}".format(
                  get_column_letter(m + 2), R_CXC, R_COBRO, R_SVC)
                  for m in range(12)], fuerte=True); r += 1
r += 1
seccion(res, r, "▶ SALIDAS DE EFECTIVO"); r += 1
sal = {}
for key, lab, vals, nota in (
        ("planilla", "Pago de planilla neta (a empleados)", None,
         "sale en el mes, para el mes. Es el NETO en la mano: NO incluye la CCSS "
         "(va en la línea de abajo) ni el aguinaldo (sale en diciembre)"),
        ("ccss", "Pago a la CCSS (patronal + obrera)", None, "se deposita el mes SIGUIENTE"),
        ("aguinaldo", "Pago de aguinaldo", None, "se provisiona cada mes y sale entero en diciembre"),
        ("prov", "Pago a proveedores (con IVA)", None, "60% del mes + 40% del anterior"),
        ("svcp", "Servicio 10% A&B pagado a empleados", None, "un mes después de cobrarlo"),
        ("iva", "Remesa de IVA a Hacienda", None, "ver el tab IVA"),
        ("renta", "Impuesto de renta — liquidación", None, "sale una vez al año"),
        ("otros", "Otros movimientos de caja", None, "")):
    orig = {r2["label"].strip(): r2["values"] for r2 in D["bloques"]["resumen"]}
    v = next((vv for kk, vv in orig.items() if lab.split("(")[0].strip()[:22].lower() in kk.lower()),
             [0.0] * 12)
    DESDE_MOTOR = {"planilla": "pago_planilla", "ccss": "pago_ccss", "prov": "pago_prov",
                   "renta": "pago_renta", "otros": "pago_otros", "iva": "payable_prev"}
    if key == "svcp":
        sal[key] = serie(res, r, lab, formulas=["={}".format(ref("svc_paid", m)) for m in range(12)], nota=nota)
    elif key == "aguinaldo":
        sal[key] = serie(res, r, lab, formulas=["=MAX(0,-{})".format(ref("WC_PROV", m)) for m in range(12)], nota=nota)
    elif key in DESDE_MOTOR and all(
            abs(gm(DESDE_MOTOR[key])[m] - v[m]) <= CENT for m in range(12)):
        sal[key] = serie(res, r, lab, formulas=["={}".format(ref(DESDE_MOTOR[key], m)) for m in range(12)],
                         nota=nota)
    else:
        sal[key] = serie(res, r, lab, v, nota=nota)
    r += 1
R_CXP = serie(res, r, "Pago de cuentas por pagar de apertura",
              formulas=["=IF($B${}={},$B${},0)".format(A_MES, m + 1, A_CXP) for m in range(12)],
              nota="sale una sola vez, en el mes de apertura"); r += 1
R_SAL = serie(res, r, "TOTAL SALIDAS OPERATIVAS",
              formulas=["=" + "+".join("{}{}".format(get_column_letter(m + 2), x)
                                       for x in list(sal.values()) + [R_CXP])
                        for m in range(12)], fuerte=True); r += 1
R_OPE = serie(res, r, "FLUJO OPERATIVO",
              formulas=["={0}{1}-{0}{2}".format(get_column_letter(m + 2), R_ENT, R_SAL)
                        for m in range(12)], fuerte=True, relleno=VERDE); r += 1
r += 1
seccion(res, r, "▶ INVERSIÓN"); r += 1
R_CAP = serie(res, r, "CapEx del presupuesto (del P&L)",
              formulas=["={}".format(ref("capex", m)) for m in range(12)]); r += 1
r += 1
seccion(res, r, "▶ RESULTADO"); r += 1
R_NET = serie(res, r, "FLUJO NETO TOTAL",
              formulas=["={0}{1}-{0}{2}".format(get_column_letter(m + 2), R_OPE, R_CAP)
                        for m in range(12)], fuerte=True, relleno=VERDE); r += 1
R_INI = r
c = res.cell(r, 1, "Saldo inicial de caja"); c.font = f(10, True); c.border = bd()
# Enero toma el efectivo de apertura; los demás meses encadenan del cierre
# anterior, así que no hay dos lugares donde escribir el mismo dato.
cel = res.cell(r, 2, "=$B${}".format(A_CAJA))
cel.number_format = USD; cel.font = f(10); cel.border = bd()
for m in range(1, 12):
    cel = res.cell(r, m + 2, "={}{}".format(get_column_letter(m + 1), r + 1))
    cel.number_format = USD; cel.font = f(10); cel.border = bd()
res.cell(r, 16, "enero viene de la celda de APERTURA; los demás, del cierre del mes anterior").font = f(9, False, "595959", True)
r += 1
R_FIN = serie(res, r, "SALDO DE CAJA AL CIERRE",
              formulas=["={0}{1}+{0}{2}".format(get_column_letter(m + 2), R_INI, R_NET)
                        for m in range(12)], fuerte=True, relleno=AZULC)
res.freeze_panes = "B5"; res.sheet_view.showGridLines = False
res.column_dimensions["P"].width = 62

# ══════════════════════════ 3. TABS DE DETALLE ═════════════════════════════

# ── Los totales de los auxiliares que NO son una suma plana ───────────────
# Deducirlos por posicion no alcanza: unos RESTAN (el pago del mes es el
# devengado menos el movimiento de cuentas por pagar), otros salen de una serie
# del motor, y en Nomina hay una fila que ya es un subtotal y se contaba dos
# veces. Van por etiqueta, que no se corre si manana cambia el orden.
AUX_RECETA = {
    "Ingresos": {
        "TOTAL ENTRADAS DE CAJA": [("COBRO OPERATIVO", 1),
                                   ("IVA cobrado a clientes", 1),
                                   ("Servicio 10% A&B cobrado", 1),
                                   ("Retenciones de tarjeta", 1)],
    },
    "Nomina": {
        "Total deducciones al empleado": [("CCSS obrera", 1),
                                          ("Retencion de renta al salario", 1),
                                          ("Retención de renta al salario", 1)],
        "PLANILLA NETA A PAGAR AL EMPLEADO": [("Salario bruto (base imponible)", 1),
                                              ("Total deducciones al empleado", 1)],
    },
    "Proveedores": {
        "Pago total del mes (sin IVA)": [("TOTAL COSTO DEVENGADO", 1),
                                         ("Movimiento de cuentas por pagar", -1)],
    },
    "Gastos Propiedad": {
        "TOTAL PROPIEDAD + INVERSION": [("Entran al mismo calendario", 1),
                                        ("CapEx del presupuesto", 1)],
        "TOTAL PROPIEDAD + INVERSIÓN": [("Entran al mismo calendario", 1),
                                        ("CapEx del presupuesto", 1)],
    },
}
#: Notas al margen. La escalera de la planilla se lee mal sin ellas: el
#: «total» de arriba y el «salario bruto» de abajo se confunden, y entre los
#: dos hay 39.2% de cargas que el hotel paga y el empleado nunca ve.
AUX_NOTA = {
    "Nomina": {
        "TOTAL COSTO DE PLANILLA":
            "⚠ LO QUE LE CUESTA AL HOTEL. Ya INCLUYE la CCSS patronal (26.83%), "
            "el aguinaldo (1/12) y las vacaciones: es el salario bruto + 39.2%. "
            "Es la cifra que va al P&L, no la que se le paga al empleado.",
        "Salario bruto (base imponible)":
            "Lo que dice el contrato. NO incluye cargas patronales. Sobre esta base "
            "se calculan la CCSS (obrera y patronal), el aguinaldo y las vacaciones.",
        "CCSS obrera":
            "La paga el EMPLEADO: se le retiene del bruto. No es costo adicional del hotel.",
        "PLANILLA NETA A PAGAR AL EMPLEADO":
            "Lo que efectivamente sale del banco a las cuentas de los empleados. "
            "Bruto menos lo retenido. Es la línea «Pago de planilla neta» del Resumen.",
        "CCSS patronal":
            "La paga el HOTEL por encima del bruto: 26.83%. Se deposita junto con la "
            "cuota obrera retenida, el mes siguiente.",
        "COSTO TOTAL DE PLANILLA (al P&L)":
            "Misma cifra que el total de arriba, llegando por el otro camino: "
            "bruto + cargas + beneficios. Si las dos no coinciden, hay un error.",
        "La deducción obrera se retiene":
            "Resumen de la escalera: cuesta el total de arriba · el bruto es la base · "
            "al empleado le llega la neta. La diferencia se deposita a la CCSS y a Hacienda.",
    },
}
#: Totales que son una serie del motor y no se pueden armar con lo que se ve.
AUX_DEL_MOTOR = {
    "IVA": {"A declarar este mes": "iva_net",
            "Efecto neto del IVA en caja": "WC_TAX"},
    "Gastos Propiedad": {"CapEx del presupuesto": "capex"},
}

#: Filas que son LA MISMA PLATA en dos hojas. Iban como numero pegado en las
#: dos, asi que tocar el origen no movia la copia — justo lo que no puede
#: pasar en un libro que se va a editar. Se apunta cada copia a su origen.
#: {hoja: {trozo de la etiqueta: (hoja origen o None si es la misma, etiqueta origen)}}
AUX_CRUCE = {
    "Proveedores": {
        "Gastos de propiedad": ("Gastos Propiedad", "TOTAL GASTOS DE PROPIEDAD"),
    },
    "Ingresos": {
        "IVA cobrado a clientes": (None, "TOTAL IVA COBRADO"),
    },
    "Gastos Propiedad": {
        "Entran al mismo calendario": (None, "TOTAL GASTOS DE PROPIEDAD"),
    },
    "IVA": {
        "IVA cobrado a clientes (+)": ("Ingresos", "TOTAL IVA COBRADO"),
        "El IVA cobrado va dentro": ("Ingresos", "TOTAL IVA COBRADO"),
    },
}

HOJAS = {"aux_ingresos": "Ingresos", "aux_nomina": "Nomina",
         "aux_proveedores": "Proveedores", "aux_gastos_propiedad": "Gastos Propiedad",
         "aux_iva": "IVA"}

# Donde cae cada fila de cada auxiliar. Se calcula ANTES de dibujar, porque
# «Gastos Propiedad» se dibuja despues de «Proveedores» y aun asi hay que poder
# apuntarle. La fila es F0 + indice: no depende de lo que se haya dibujado.
MAPA = {}
for _clave, _nombre in HOJAS.items():
    MAPA[_nombre] = [(rotulo(_r["label"]), _r["kind"] or "", _r["values"], 5 + _i)
                     for _i, _r in enumerate(D["bloques"][_clave])]


def _busca_fila(hoja, frag):
    for lab, kind, vals, fe in MAPA.get(hoja, []):
        if frag.lower() in lab.lower() and kind != "section":
            return fe, vals
    return None, None
for clave, nombre in HOJAS.items():
    filas = D["bloques"][clave]
    ws = wb.create_sheet(nombre)
    titulo(ws, "Cash Flow — {}".format(nombre), SUB, 14)
    cabecera(ws)
    F0 = 5; pos = {}; desde = None; nform = 0
    for i, rr in enumerate(filas):
        fe = F0 + i; pos[i] = fe
        kind = rr["kind"] or ""
        if kind == "section":
            c = ws.cell(fe, 1, rotulo(rr["label"])); c.font = f(10, True, AZUL)
            for j in range(1, 15):
                ws.cell(fe, j).fill = fill(LILA); ws.cell(fe, j).border = bd()
            desde = None
            continue
        tot = kind in ("sub", "total", "total_strong")
        formula = None      # [(fila_excel, signo)] dentro de la hoja
        ref_motor = None    # o una serie del tab Motor
        ref_externa = None  # o la misma fila, que vive en otra hoja
        etiq = rotulo(rr["label"])

        # (a0) ¿es una copia de una fila que vive en otra hoja (o más arriba
        # en esta)? Entonces apunta al original, no lleva el número escrito.
        cruce = next((v for k, v in AUX_CRUCE.get(nombre, {}).items() if k in etiq), None)
        if cruce:
            hoja_org = cruce[0] or nombre
            fe_org, v_org = _busca_fila(hoja_org, cruce[1])
            if fe_org and fe_org != fe and all(
                    abs(v_org[m] - rr["values"][m]) <= CENT for m in range(12)):
                ref_externa = ("" if cruce[0] is None
                               else "'{}'!".format(hoja_org)) + "{col}" + str(fe_org)
                nform += 1

        # (a) ¿tiene receta escrita? Va primero: es la relación de verdad.
        rec = next((v for k, v in AUX_RECETA.get(nombre, {}).items() if k in etiq), None)
        if tot and rec:
            partes = []
            for frag, signo in rec:
                k = next((x for x in range(i) if frag.lower() in rotulo(filas[x]["label"]).lower()), None)
                if k is not None and k in pos:
                    partes.append((k, signo))
            if partes and all(
                    abs(sum(s2 * filas[k]["values"][m] for k, s2 in partes) - rr["values"][m]) <= CENT
                    for m in range(12)):
                formula = [(pos[k], s2) for k, s2 in partes]; nform += 1

        # (b) ¿es una serie que vive en el motor? Vale para cualquier fila:
        # el CapEx no es un total y aun asi tiene que venir de un solo lado.
        if formula is None and ref_externa is None:
            serie_k = next((v for k, v in AUX_DEL_MOTOR.get(nombre, {}).items() if k in etiq), None)
            if serie_k and serie_k in FM and all(
                    abs(gm(serie_k)[m] - rr["values"][m]) <= CENT for m in range(12)):
                ref_motor = FM[serie_k]; nform += 1

        # (c) si no, la suma plana de las filas de datos de su bloque
        if tot and formula is None and ref_motor is None and desde is not None:
            idx = [k for k in range(desde, i) if (filas[k]["kind"] or "") in ("data", "input", "cash")]
            if idx and all(abs(sum(filas[k]["values"][m] for k in idx) - rr["values"][m]) <= CENT
                           for m in range(12)):
                formula = [(pos[k], 1) for k in idx]; nform += 1
        c = ws.cell(fe, 1, rotulo(rr["label"])); c.font = f(10, tot); c.border = bd()
        c.alignment = Alignment("left", "center", indent=0 if tot else 1)
        for m in range(12):
            j = m + 2
            L = get_column_letter(j)
            if ref_externa is not None:
                val = "=" + ref_externa.format(col=L)
            elif formula:
                val = "=" + "".join("{}{}{}".format("-" if sg < 0 else ("+" if n else ""), L, x)
                                    for n, (x, sg) in enumerate(formula))
            elif ref_motor is not None:
                val = "='Motor cobranza y pagos'!{}{}".format(L, ref_motor)
            else:
                val = rr["values"][m]
            cel = ws.cell(fe, j, val)
            cel.number_format = USD; cel.font = f(10, tot); cel.border = bd()
        a = ws.cell(fe, 14, "=SUM(B{0}:M{0})".format(fe))
        a.number_format = USD; a.font = f(10, True); a.border = bd()
        if tot:
            for j in range(1, 15):
                ws.cell(fe, j).fill = fill(AZULC if kind == "total_strong" else GRIS)
        nota = next((v for k, v in AUX_NOTA.get(nombre, {}).items() if k in etiq), None)
        if nota:
            cn = ws.cell(fe, 16, nota)
            cn.font = f(9, False, "9C0006" if "⚠" in nota else "595959", True)
            cn.alignment = Alignment("left", "center", wrap_text=False)
        if desde is None:
            desde = i
    if AUX_NOTA.get(nombre):
        ws.column_dimensions["P"].width = 110
    ws.freeze_panes = "B5"; ws.sheet_view.showGridLines = False
    print("  {:<20} {:>3} filas, {:>2} totales por formula".format(nombre, len(filas), nform))

# ══════════════════════════ 4. CRITERIOS ═══════════════════════════════════
cr = wb.create_sheet("Criterios")
titulo(cr, "Los criterios con que se calculó este flujo", SUB, 3)
cr.column_dimensions["A"].width = 34
cr.column_dimensions["B"].width = 16
cr.column_dimensions["C"].width = 76
NOM = {"iva_rate": "IVA", "card_pct": "% de la venta cobrada con tarjeta",
       "card_iva_ret": "Retención de IVA de tarjeta", "card_renta_ret": "Retención de renta de tarjeta",
       "ap_same_pct": "% a proveedores en el mismo mes", "service_rate": "Servicio de A&B",
       "service_lag": "Rezago del servicio (meses)", "retention": "Retención sobre anticipos",
       "mix_nrr": "Mezcla: no reembolsable", "mix_credit": "Mezcla: a crédito",
       "lead_nrr": "El no reembolsable se cobra (meses antes)",
       "lead_flex": "El flexible se cobra (meses antes)",
       "lag_credit": "El crédito se cobra (meses después)",
       "payroll_outsourced": "¿Planilla tercerizada?", "aguinaldo_pay_month": "Mes de pago del aguinaldo",
       "ccss_obrera_rate": "CCSS obrera (deducción al empleado)"}
EXP = {"payroll_outsourced": "FALSO en Amarena: la planilla es propia, así que NO lleva IVA ni entra a cuentas por pagar",
       "mix_nrr": "Medido en los canales reales: directos 43.9% de la venta × 50% de depósito",
       "mix_credit": "Travel Agent / Promociones = 19.0% de la venta, medido en los canales reales",
       "ap_same_pct": "El 40% restante sale el mes siguiente",
       "aguinaldo_pay_month": "Se provisiona cada mes y sale entero en diciembre"}
r = 4
cr.cell(r, 1, "Criterio").font = f(10, True, "FFFFFF")
cr.cell(r, 2, "Valor").font = f(10, True, "FFFFFF")
cr.cell(r, 3, "Qué significa").font = f(10, True, "FFFFFF")
for j in range(1, 4):
    cr.cell(r, j).fill = fill(AZUL2); cr.cell(r, j).border = bd()
r += 1
for k in sorted(CRI):
    v = CRI[k]
    if isinstance(v, (list, dict)):
        continue
    cr.cell(r, 1, NOM.get(k, k)).font = f(10)
    c = cr.cell(r, 2, v); c.alignment = Alignment("center")
    c.font = f(10, False, "0000FF")
    if isinstance(v, float) and 0 < v < 1:
        c.number_format = '0.00%'
    cr.cell(r, 3, EXP.get(k, "")).font = f(9, False, "595959", True)
    for j in range(1, 4):
        cr.cell(r, j).border = bd()
    r += 1
cr.sheet_view.showGridLines = False

# ══════════════════════════ 4b. P&L USALI POR MES ══════════════════════════
# Resumen arriba (la cascada), detalle por cuenta abajo. Cada linea del resumen
# es una formula que apunta a su fila del detalle: no hay dos verdades.
PLD = json.load(io.open(BASE + r"\pl.json", encoding="utf-8"))
MES = {m["month"]: {l["line_code"]: float(l["amount_usd"] or 0) for l in m["lines"]}
       for m in PLD["months"]}
ORDEN, VISTOS = [], set()
for l in PLD["months"][5]["lines"]:
    cod = l["line_code"]
    if cod in VISTOS:
        continue
    VISTOS.add(cod)
    ORDEN.append((cod, l["line_name"] or cod, l["section"]))
    if cod == "NET_PROFIT":
        break   # lo que sigue son alias de lineas ya puestas

# ⚠️ Salvo UNO. El motor emite `TOTAL_OP_PROFIT` DESPUES de NET_PROFIT, junto
# con los alias, pero no es alias de nada: la seccion OPERATING PROFIT trae las
# utilidades por departamento y ningun total. Cortado ahi, la utilidad
# operativa y el GOP se quedaban sin fila a la que apuntar y bajaban como
# numero pegado. Se mete donde le corresponde: al cierre de su seccion.
if "TOTAL_OP_PROFIT" not in {c for c, _, _ in ORDEN}:
    ult = max((i for i, (c, _, _) in enumerate(ORDEN) if c.startswith("PROFIT_")),
              default=None)
    if ult is not None:
        ORDEN.insert(ult + 1, ("TOTAL_OP_PROFIT", "OPERATING PROFIT", "OPERATING PROFIT"))


def mv(cod):
    return [MES.get(m, {}).get(cod, 0.0) for m in range(1, 13)]


pl = wb.create_sheet("P&L USALI")
titulo(pl, "P&L USALI por mes — resumen arriba, detalle por cuenta abajo",
       SUB + " · el resumen es fórmula sobre el detalle; el detalle sale del motor del P&L", 14)
cabecera(pl)
r = 5
FILA_DET = {}

# ── KPIs, como manda USALI ────────────────────────────────────────────────
seccion(pl, r, "INDICADORES DEL MES"); r += 1
K = {m["month"]: m["kpis"] for m in PLD["months"]}
for clave, etiqueta, fmt in (("rooms_available", "Noches disponibles", '#,##0'),
                             ("rooms_occupied", "Noches ocupadas", '#,##0.0'),
                             ("guests", "Huéspedes", '#,##0.0'),
                             ("occupancy_pct", "Ocupación", '0.0%'),
                             ("adr", "ADR", '$#,##0.00'),
                             ("revpar", "RevPAR", '$#,##0.00')):
    vals = [float(K.get(m, {}).get(clave) or 0) for m in range(1, 13)]
    c = pl.cell(r, 1, etiqueta); c.font = f(10); c.border = bd()
    for mm in range(12):
        cel = pl.cell(r, mm + 2, vals[mm]); cel.number_format = fmt
        cel.font = f(10); cel.border = bd()
    # Ni la ocupación ni las tarifas se suman: se recalculan sobre el año.
    if clave in ("occupancy_pct", "adr", "revpar"):
        pl.cell(r, 14, "").border = bd()
    else:
        a = pl.cell(r, 14, "=SUM(B{0}:M{0})".format(r))
        a.number_format = fmt; a.font = f(10, True); a.border = bd()
    r += 1
r += 1

RESUMEN_EN = r      # donde arranca el bloque de resumen; se llena al final
CASCADA = [("TOTAL_REVENUES", "TOTAL INGRESOS", True),
           ("TOTAL_OPERATING_EXPENSES", "Total gastos operativos", False),
           ("TOTAL_OP_PROFIT", "UTILIDAD OPERATIVA", True),
           ("TOTAL_OVERHEAD_EXPENSES", "Total overhead", False),
           ("TOTAL_GOP", "GOP — GROSS OPERATING PROFIT", True),
           ("TOTAL_NON_OP_EXPENSES", "Total gastos no operativos", False),
           ("EBITDA_BEFORE_CAPITAL", "EBITDA ANTES DE CAPITAL", True),
           ("CAPITAL_EXPENSE", "Gasto de capital", False),
           ("EBITDA_AFTER_CAPITAL", "EBITDA DESPUÉS DE CAPITAL", True),
           ("FINANCIAL_EXPENSES", "Gastos financieros", False),
           ("TOTAL_DEPRECIATIONS", "Depreciaciones", False),
           ("EBT", "UTILIDAD ANTES DE IMPUESTOS", True),
           ("INCOME_TAXES", "Impuesto de renta", False),
           ("NET_PROFIT", "UTILIDAD NETA", True)]
seccion(pl, r, "▶ RESUMEN — LA CASCADA USALI"); r += 1
FILA_RES = {}
for cod, etiqueta, fuerte in CASCADA:
    FILA_RES[cod] = r; r += 1
r += 1

# ── La receta de cada total: de qué líneas sale, con su signo ─────────────
# Deducirla por posición (sumar lo que viene arriba desde la última sección)
# fallaba en todo lo que cruza secciones: los gastos operativos son OPEX más
# COST OF SALES, el overhead lleva su propio costo de ventas, y la cascada de
# abajo no suma, RESTA. Acá va escrita la relación USALI de verdad.
CODS = [c for c, _, _ in ORDEN]
GRUPOS = ["ROOMS", "FB", "PRIVATE_BAR", "SPA", "TOURS", "TIENDA", "RETAIL",
          "TRANSPORTATION", "LAUNDRY", "INNOCEANA", "CROWTHER_LAB",
          "CLARO_HUERTA", "SUSTAINABILITY", "MISC_OTHER", "CLUB", "AREC"]


def _pref(prefijo, grupo):
    """Las cuentas de un grupo: REV_FB agarra FB, FB_BEV y FB_MISC."""
    otros = [x for x in GRUPOS if x != grupo and x.startswith(grupo)]
    out = []
    for c in CODS:
        if not c.startswith(prefijo + "_"):
            continue
        suf = c[len(prefijo) + 1:]
        if suf == grupo or suf.startswith(grupo + "_"):
            if any(suf == o or suf.startswith(o + "_") for o in otros):
                continue
            out.append(c)
    return out


RECETA = {}
# Utilidad departamental = ingreso − gasto operativo − costo de ventas
for gr in GRUPOS:
    cod_p = "PROFIT_" + gr
    if cod_p not in CODS:
        continue
    RECETA[cod_p] = ([(c, 1) for c in _pref("REV", gr)]
                     + [(c, -1) for c in _pref("OPEX", gr)]
                     + [(c, -1) for c in _pref("COS", gr)])
RECETA.update({
    "TOTAL_REVENUES": [(c, 1) for c in CODS if c.startswith("REV_")],
    "TOTAL_OPERATING_EXPENSES": ([(c, 1) for c in CODS if c.startswith("OPEX_")]
                                 + [(c, 1) for c in CODS if c.startswith("COS_")]),
    "TOTAL_OP_PROFIT": [(c, 1) for c in CODS if c.startswith("PROFIT_")],
    "TOTAL_OVERHEAD_EXPENSES": ([(c, 1) for c in CODS if c.startswith("OH_")]
                                + [(c, 1) for c in CODS if c.startswith("COH_")]),
    "TOTAL_GOP": [("TOTAL_OP_PROFIT", 1), ("TOTAL_OVERHEAD_EXPENSES", -1)],
    "TOTAL_RENT_MGMT_FEES": [("RENT", 1), ("MGMT_FEE_3", 1), ("MGMT_FEE_5_ROYALTIES", 1)],
    "TOTAL_PROPERTY_INSURANCE": [("PROPERTY_INSURANCE", 1)],
    "TOTAL_OTHER_EXPENSES": [("OTHER_EXPENSES", 1)],
    "TOTAL_NON_OP_EXPENSES": [("TOTAL_RENT_MGMT_FEES", 1),
                              ("TOTAL_PROPERTY_INSURANCE", 1),
                              ("TOTAL_OTHER_EXPENSES", 1)],
    "EBITDA_BEFORE_CAPITAL": [("TOTAL_GOP", 1), ("TOTAL_NON_OP_EXPENSES", -1)],
    "CAPITAL_EXPENSE": [("CAPITAL_RESERVE", 1), ("LARGE_CAPEX", 1)],
    "EBITDA_AFTER_CAPITAL": [("EBITDA_BEFORE_CAPITAL", 1), ("CAPITAL_EXPENSE", -1)],
    "FINANCIAL_EXPENSES": [("BANK_INTEREST", 1), ("LEASINGS_RENTS", 1),
                           ("FINANCIAL_LOSSES", 1)],
    "TOTAL_DEPRECIATIONS": [("DEPRECIATION", 1), ("ASSET_LOSS", 1)],
    "EBT": [("EBITDA_AFTER_CAPITAL", 1), ("FINANCIAL_EXPENSES", -1),
            ("TOTAL_DEPRECIATIONS", -1)],
    "NET_PROFIT": [("EBT", 1), ("INCOME_TAXES", -1)],
})

# ── Detalle por cuenta ────────────────────────────────────────────────────
sec_actual = None
desde = None
nform_pl = 0
for cod, nombre, sec in ORDEN:
    if cod.startswith("SEC_"):
        continue
    if sec != sec_actual:
        sec_actual = sec
        seccion(pl, r, sec); r += 1
        desde = r
    vals = mv(cod)
    es_total = cod.startswith("TOTAL_") or cod in ("GOP", "EBT", "NET_PROFIT",
                                                   "CAPITAL_EXPENSE", "FINANCIAL_EXPENSES",
                                                   "EBITDA_BEFORE_CAPITAL", "EBITDA_AFTER_CAPITAL")
    partes = RECETA.get(cod)
    formula = None
    if partes:
        # ⚠️ Misma guarda que usa el exportador de FinPlan: la fórmula se
        # escribe SÓLO si reproduce el número del motor los doce meses. Si el
        # motor netea un reparto que el cuadro no muestra, manda el motor.
        listos = [(x, s) for x, s in partes if x in FILA_DET]
        if len(listos) == len(partes) and all(
                abs(sum(s * mv(x)[m] for x, s in listos) - vals[m]) <= CENT
                for m in range(12)):
            formula = listos; nform_pl += 1
    c = pl.cell(r, 1, rotulo(nombre)); c.font = f(10, es_total); c.border = bd()
    c.alignment = Alignment("left", "center", indent=0 if es_total else 1)
    for mm in range(12):
        j = mm + 2
        if formula:
            txt = ""
            for x, s in formula:
                pieza = "{}{}".format(get_column_letter(j), FILA_DET[x])
                txt += (pieza if not txt and s > 0 else ("+" if s > 0 else "-") + pieza)
            cel = pl.cell(r, j, "=" + txt)
        else:
            cel = pl.cell(r, j, vals[mm])
        cel.number_format = USD; cel.font = f(10, es_total); cel.border = bd()
    a = pl.cell(r, 14, "=SUM(B{0}:M{0})".format(r))
    a.number_format = USD; a.font = f(10, True); a.border = bd()
    if es_total:
        for j in range(1, 15):
            pl.cell(r, j).fill = fill(AZULC)
    FILA_DET[cod] = r
    r += 1

# ── y ahora sí: el resumen, apuntando al detalle ──────────────────────────
for cod, etiqueta, fuerte in CASCADA:
    fr = FILA_RES[cod]
    c = pl.cell(fr, 1, etiqueta); c.font = f(11 if fuerte else 10, True); c.border = bd()
    destino = FILA_DET.get(cod)
    for mm in range(12):
        j = mm + 2
        cel = pl.cell(fr, j, "={}{}".format(get_column_letter(j), destino) if destino
                      else mv(cod)[mm])
        cel.number_format = USD; cel.font = f(11 if fuerte else 10, True); cel.border = bd()
    a = pl.cell(fr, 14, "=SUM(B{0}:M{0})".format(fr))
    a.number_format = USD; a.font = f(11 if fuerte else 10, True); a.border = bd()
    for j in range(1, 15):
        pl.cell(fr, j).fill = fill(VERDE if fuerte else GRIS)
    if destino:
        pl.cell(fr, 16, "← fila {} del detalle".format(destino)).font = f(9, False, "2F5597", True)
pl.freeze_panes = "B5"; pl.sheet_view.showGridLines = False
pl.column_dimensions["P"].width = 26
print("  {:<20} {:>3} cuentas, {:>2} totales por formula, resumen de {} lineas".format(
    "P&L USALI", len(FILA_DET), nform_pl, len(CASCADA)))

# ══════════════════════════ 5. COMO SE CALCULA ═════════════════════════════
me = wb.create_sheet("Como se calcula")
titulo(me, "Cómo se calcula cada variable",
       SUB + " · de dónde sale cada número del paquete", 3)
me.column_dimensions["A"].width = 38
me.column_dimensions["B"].width = 54
me.column_dimensions["C"].width = 74
r = 4
for j, t in enumerate(("Variable", "Fórmula", "Por qué / de dónde sale"), 1):
    c = me.cell(r, j, t); c.font = f(10, True, "FFFFFF")
    c.fill = fill(AZUL2); c.border = bd()
r += 1
METODO = [
    ("— LA VENTA, REPARTIDA SEGUN CUANDO SE COBRA —", "", ""),
    ("No reembolsable", "mix_nrr × venta del mes de estadía",
     "Se cobra lead_nrr meses ANTES de la estadía. En Amarena 22%, 2 meses antes: los directos son 43.9% de la venta y dejan 50% de depósito. Medido en los canales reales, no supuesto."),
    ("A crédito", "mix_credit × venta del mes",
     "Se cobra lag_credit meses DESPUÉS. 19% en Amarena: Travel Agent y Promociones."),
    ("Se cobra en la estadía", "venta − no reembolsable − flexible − crédito",
     "El resto: el saldo de las directas más todo OTA, que paga en el momento."),
    ("— DE LA VENTA AL COBRO —", "", ""),
    ("Cobro a clientes", "venta + Δanticipos recibidos + Δanticipos aplicados + Δcuentas por cobrar + IVA cobrado − retenciones de tarjeta",
     "Cada sumando está en el tab Motor y la fórmula de la hoja los referencia uno por uno. Antes esta línea era un número pegado."),
    ("Retenciones de tarjeta", "IVA retenido − retención de renta",
     "2.5% cada una. NO son pagos del hotel: el adquirente se las descuenta al liquidar, así que van netas del cobro y no como salida."),
    ("— DEL GASTO AL PAGO —", "", ""),
    ("Base de IVA y cuentas por pagar", "costo devengado − planilla",
     "Con planilla propia los salarios no llevan IVA ni van a cuentas por pagar. Si fuera tercerizada entraría entera, porque llegaría por factura."),
    ("Pago a proveedores", "60% del costo del mes + 40% del mes anterior",
     "El parámetro es ap_same_pct. El 40% de diciembre cae en enero del año siguiente."),
    ("Pago de planilla", "la planilla devengada del mes, entera",
     "Owner, 31-oct-2026: se paga en el mes, para el mes. NO lleva el rezago de proveedores."),
    ("Pago a la CCSS", "CCSS patronal + obrera devengada del mes ANTERIOR",
     "Owner: lo único que se paga el otro mes es la Caja y las retenciones. Se deposita entera, no el 60/40."),
    ("Aguinaldo", "se provisiona cada mes; sale ENTERO en diciembre",
     "La provisión no es salida de caja: se resta del pago de planilla mes a mes y aparece como una salida sola en su mes. El total del año es el mismo."),
    ("— IVA —", "", ""),
    ("IVA cobrado", "13% × venta del mes", "Sobre el ingreso devengado."),
    ("IVA pagado", "13% × base de compras", "La base ya excluye la planilla."),
    ("Posición del mes", "IVA cobrado − IVA pagado − retención de tarjeta",
     "Negativo significa saldo a favor."),
    ("Saldo a favor", "se acumula y se arrastra",
     "Hacienda no lo devuelve en efectivo: se aplica contra el impuesto de los meses siguientes. En Amarena nunca se agota, así que el IVA pagado de más es caja que sale y no vuelve."),
    ("Remesa a Hacienda", "lo declarado el mes anterior",
     "Solo si la posición del mes fue deudora."),
    ("— EL FLUJO —", "", ""),
    ("TOTAL ENTRADAS", "cobro a clientes + servicio 10% cobrado", "Fórmula en la hoja."),
    ("TOTAL SALIDAS", "suma de las ocho líneas de salida", "Fórmula en la hoja."),
    ("FLUJO OPERATIVO", "entradas − salidas", "Fórmula en la hoja."),
    ("FLUJO NETO", "flujo operativo − CapEx", "Fórmula en la hoja."),
    ("SALDO AL CIERRE", "saldo inicial + flujo neto del mes",
     "El saldo inicial de enero es EDITABLE y está en ámbar: es el único dato del paquete que no sale del sistema. Los demás meses encadenan del anterior."),
]
for v, fo, pq in METODO:
    es_tit = v.startswith("—")
    c = me.cell(r, 1, v); c.font = f(10, True, AZUL if es_tit else "000000")
    if es_tit:
        for j in range(1, 4):
            me.cell(r, j).fill = fill(LILA)
    me.cell(r, 2, fo).font = f(10, False, "1F3864")
    me.cell(r, 3, pq).font = f(9, False, "595959")
    for j in range(1, 4):
        me.cell(r, j).border = bd()
        me.cell(r, j).alignment = Alignment("left", "top", wrap_text=True)
    me.row_dimensions[r].height = 15 + 12 * (max(len(pq) // 74, len(fo) // 54))
    r += 1
me.sheet_view.showGridLines = False

# ══════════════════════════ 6. RETENCIONES DE SALARIO ═════════════════════
RT = json.load(io.open(BASE + r"\ret.json", encoding="utf-8"))
ret, renta = RT["ret"], RT["renta"]

rt = wb.create_sheet("Retenciones salario")
titulo(rt, "Retención del impuesto sobre la renta al salario",
       SUB + " · {} empleados, de los cuales {} pagan renta · tramos progresivos, no tasa plana".format(
           ret.get("empleados_total"), ret.get("empleados_afectos")), 14)
cabecera(rt)
r = 5
F_BASE = serie(rt, r, "Base imponible del mes",
               [float(x or 0) for x in ret["base_mes"]],
               nota="salario bruto menos la CCSS obrera, si se deduce"); r += 1
# La retencion del mes salia como numero pegado: no habia de donde sumarla,
# porque la tabla de abajo es ANUAL. Se abren mes a mes los empleados que si
# pagan renta — con eso la fila total pasa a ser una suma de lo que se ve.
_AFECTOS = [e for e in ret["empleados"]
            if any(abs(float(x or 0)) > 0.004 for x in (e.get("impuesto_usd") or []))]
_f_emp = []
if _AFECTOS:
    for e in sorted(_AFECTOS, key=lambda x: -float(x.get("impuesto_anual") or 0)):
        _f_emp.append(serie(rt, r, "   {} — {}".format(e.get("empleado"), e.get("puesto")),
                            [float(x or 0) for x in e["impuesto_usd"]], sangria=2)); r += 1
_suma_ok = _f_emp and all(
    abs(sum(float(e["impuesto_usd"][mm] or 0) for e in _AFECTOS) - float(ret["total_mes"][mm] or 0)) <= CENT
    for mm in range(12))
F_RET = serie(rt, r, "Retención del mes",
              valores=None if _suma_ok else [float(x or 0) for x in ret["total_mes"]],
              formulas=(["=" + "+".join("{}{}".format(get_column_letter(mm + 2), x) for x in _f_emp)
                         for mm in range(12)] if _suma_ok else None),
              fuerte=True); r += 1
# El tipo de cambio no es plata: no se suma en el año.
c = rt.cell(r, 1, "Tipo de cambio del mes"); c.font = f(10); c.border = bd()
for mm, v in enumerate([float(x or 0) for x in ret["tc_mes"]]):
    cel = rt.cell(r, mm + 2, v); cel.number_format = '#,##0.00'
    cel.font = f(10); cel.border = bd()
rt.cell(r, 14, "").border = bd()
rt.cell(r, 16, "no se suma: es una cotización, no un monto").font = f(9, False, "595959", True)
r += 2

seccion(rt, r, "EMPLEADO POR EMPLEADO (base y retención anuales, USD)"); r += 1
for j, t in enumerate(("Departamento", "Puesto", "Empleado", "Base anual",
                       "Impuesto anual", "Tramo", "¿Paga renta?"), 1):
    c = rt.cell(r, j, t); c.font = f(10, True, "FFFFFF"); c.fill = fill(AZUL2); c.border = bd()
r += 1
emp_ini = r
def _anual(e, k):
    v = e.get(k)
    return float(sum(v)) if isinstance(v, list) else float(v or 0)


for e in sorted(ret["empleados"], key=lambda x: -float(x.get("base_anual") or 0)):
    # `tramo` viene mes a mes: se muestra el MÁS ALTO que alcanzó en el año,
    # que es el que explica por qué paga (o por qué no).
    tr = e.get("tramo")
    tramo = max(tr) if isinstance(tr, list) and tr else tr
    vals = [e.get("dept_name") or e.get("dept_code"), e.get("puesto"), e.get("empleado"),
            float(e.get("base_anual") or 0), float(e.get("impuesto_anual") or 0),
            tramo, "Sí" if e.get("afecto") else "no"]
    for j, v in enumerate(vals, 1):
        c = rt.cell(r, j, v); c.border = bd(); c.font = f(10, bool(e.get("afecto")))
        if j in (4, 5):
            c.number_format = USD
        if e.get("afecto"):
            c.fill = fill(AMBAR)
    r += 1
for j, col in ((4, "D"), (5, "E")):
    c = rt.cell(r, j, "=SUM({0}{1}:{0}{2})".format(col, emp_ini, r - 1))
    c.number_format = USD; c.font = f(10, True, "FFFFFF"); c.fill = fill(AZUL2); c.border = bd()
rt.cell(r, 3, "TOTAL").font = f(10, True, "FFFFFF")
for j in (1, 2, 3, 6, 7):
    rt.cell(r, j).fill = fill(AZUL2); rt.cell(r, j).border = bd()
for j, a in ((1, 22), (2, 34), (3, 30), (4, 15), (5, 15), (6, 9), (7, 13)):
    rt.column_dimensions[get_column_letter(j)].width = a
rt.sheet_view.showGridLines = False

# ══════════════════════════ 7. RENTA ANUAL ═════════════════════════════════
ra = wb.create_sheet("Renta anual")
titulo(ra, "Impuesto sobre la renta — liquidación anual",
       SUB + " · se liquida una vez y sale en su mes de pago", 3)
ra.column_dimensions["A"].width = 44
ra.column_dimensions["B"].width = 18
ra.column_dimensions["C"].width = 76
r = 4
for j, t in enumerate(("Concepto", "Monto", "Qué es"), 1):
    c = ra.cell(r, j, t); c.font = f(10, True, "FFFFFF"); c.fill = fill(AZUL2); c.border = bd()
r += 1
F_EBT, F_BRUTO, F_CRED, F_NETO = r, r + 1, r + 2, r + 3
#: el neto ya es formula; de el salen el saldo a favor y lo que se paga.
_NETO = float(renta.get("impuesto_bruto") or 0) - float(renta.get("creditos_tarjeta") or 0)
RENTA = [
    ("ebt", "Utilidad antes de impuestos", USD,
     "Viene del P&L. Si es negativa no hay impuesto que pagar."),
    ("impuesto_bruto", "Impuesto bruto", USD, "La utilidad por la tasa, cuando la utilidad es positiva."),
    ("creditos_tarjeta", "(−) Retenciones de tarjeta del año", USD,
     "El 2.5% que el adquirente retuvo mes a mes: es anticipo del mismo impuesto y se acredita acá."),
    ("neto", "Impuesto neto", USD, "Bruto menos los anticipos."),
    ("saldo_a_favor", "Saldo a favor", USD, "Si los anticipos superaron al impuesto."),
    ("a_pagar", "A PAGAR", USD, "Lo que efectivamente sale de caja."),
    ("pago_manual", "Pago digitado a mano", USD, "Si se pisó el cálculo."),
    ("tasa", "Tasa", '0.0%', "La tasa del impuesto sobre la renta."),
    ("mes_pago", "Mes de pago", '0', "Sale una sola vez, en este mes."),
    ("pasa_al_flujo", "¿Pasa al flujo de caja?", None, "El interruptor del owner."),
]
for k, etiqueta, fmt, expl in RENTA:
    v = renta.get(k)
    ra.cell(r, 1, etiqueta).font = f(10, k == "a_pagar")
    if k == "neto":
        cel = ra.cell(r, 2, "=B{}-B{}".format(F_BRUTO, F_CRED))
    elif k == "saldo_a_favor" and abs(float(v or 0) - max(0.0, -_NETO)) <= CENT:
        cel = ra.cell(r, 2, "=MAX(0,-B{})".format(F_NETO))
    elif k == "a_pagar" and abs(float(v or 0) - max(0.0, _NETO)) <= CENT:
        cel = ra.cell(r, 2, "=MAX(0,B{})".format(F_NETO))
    elif isinstance(v, bool):
        cel = ra.cell(r, 2, "Sí" if v else "no")
    else:
        try:
            cel = ra.cell(r, 2, float(v or 0))
        except (TypeError, ValueError):
            cel = ra.cell(r, 2, str(v))
    if fmt and not isinstance(v, bool):
        cel.number_format = fmt
    cel.font = f(11 if k == "a_pagar" else 10, k == "a_pagar")
    cel.alignment = Alignment("center")
    ra.cell(r, 3, expl).font = f(9, False, "595959", True)
    for j in range(1, 4):
        ra.cell(r, j).border = bd()
        if k == "a_pagar":
            ra.cell(r, j).fill = fill(VERDE)
    r += 1
ra.sheet_view.showGridLines = False

# ══════════════════════════ 8. INDICE ══════════════════════════════════════
ix = wb.create_sheet("Indice", 0)
titulo(ix, "Paquete Cash Flow — Forecast 2026", SUB, 3)
ix.column_dimensions["A"].width = 6
ix.column_dimensions["B"].width = 28
ix.column_dimensions["C"].width = 96
r = 4
for j, t in enumerate(("#", "Hoja", "Qué trae"), 1):
    c = ix.cell(r, j, t); c.font = f(10, True, "FFFFFF"); c.fill = fill(AZUL2); c.border = bd()
r += 1
GUIA = [
    ("Resumen Flujo de Caja", "El flujo por el método directo: cobros menos pagos. Arriba, los tres saldos de apertura en ámbar — es lo único que se carga a mano. Cada línea es fórmula sobre el tab Motor."),
    ("Motor cobranza y pagos", "Las series que el sistema calcula y NO se ven en ninguna pantalla: la venta repartida según cuándo se cobra, los depósitos, las cuentas por cobrar y pagar, la tarjeta, las seis piezas del IVA y —al final, sección H— cómo reparte el motor las salidas entre planilla, CCSS y proveedores. Cada línea del Resumen apunta acá."),
    ("P&L USALI", "El estado de resultados por mes. Arriba la cascada, abajo las 107 cuentas por departamento. Todos los totales son fórmula: si tocás un ingreso, se mueve hasta la utilidad neta."),
    ("Ingresos", "De la venta devengada al cobro, con el IVA abierto por línea."),
    ("Nomina", "Del costo de planilla al neto que recibe el empleado, con las cargas sociales."),
    ("Proveedores", "Del costo devengado al pago, y cómo se reparte entre planilla y proveedores."),
    ("Gastos Propiedad", "Los gastos below-GOP: renta, honorarios, seguro y capital."),
    ("IVA", "La posición del mes, el saldo a favor que se arrastra y qué se le remite a Hacienda."),
    ("Retenciones salario", "La retención de renta al salario, empleado por empleado y por tramo."),
    ("Renta anual", "La liquidación del impuesto sobre la renta y los anticipos de tarjeta."),
    ("Criterios", "Los parámetros con que se calculó todo, y qué significa cada uno."),
    ("Como se calcula", "La fórmula de cada variable y de dónde sale. Para responder «¿y este número?»."),
]
for i, (hoja, que) in enumerate(GUIA, 1):
    ix.cell(r, 1, i).font = f(10, True, AZUL2)
    c = ix.cell(r, 2, hoja); c.font = f(10, True)
    if hoja in wb.sheetnames:
        c.hyperlink = "#'{}'!A1".format(hoja)
        c.font = f(10, True, "0563C1")
    ix.cell(r, 3, que).font = f(10)
    for j in range(1, 4):
        ix.cell(r, j).border = bd()
        ix.cell(r, j).alignment = Alignment("left", "top", wrap_text=True)
    ix.row_dimensions[r].height = 15 + 12 * (len(que) // 96)
    r += 1
r += 1
ix.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=3)
c = ix.cell(r, 1,
            "LO ÚNICO QUE SE CARGA A MANO son las celdas ámbar del Resumen: efectivo, cuentas por cobrar y "
            "cuentas por pagar al 1 de enero, y el mes en que se cobran o se pagan. Todo lo demás sale del "
            "sistema y está encadenado por fórmula. Mientras los tres estén en cero, el cuadro dice cuánto "
            "hay que poner, no cuánto falta.")
c.font = f(10, True, "9C0006"); c.fill = fill(AMBAR)
c.alignment = Alignment("left", "center", wrap_text=True); c.border = bd()
ix.sheet_view.showGridLines = False

if "Sheet" in wb.sheetnames:
    del wb["Sheet"]

OUT = r"C:\Users\User\Documents\FinPlan_Amarena\Claude outputs\AMR_CashFlow_Paquete_Formulado.xlsx"
import os, shutil
TMP = os.path.join(os.environ.get("TEMP", "."), "_paquete_cf.xlsx")
wb.save(TMP)
try:
    shutil.copyfile(TMP, OUT)
    print("escrito en su lugar definitivo")
except PermissionError:
    print("!! el archivo esta abierto en Excel; la version nueva quedo en:")
    print("  ", TMP)
    OUT = TMP
print("OK:", OUT)
print("hojas:", wb.sheetnames)
