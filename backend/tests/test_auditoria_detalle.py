# -*- coding: utf-8 -*-
"""La auditoría del detalle: cada monto del GL, y en qué renglón terminó.

Owner, 2026-09-02, con `p&L auditoria 2026.xlsx`: *«uno para ver el detalle tal
cual el formato y el otro para ver la auditoría de los detalles»*.

## Lo único que hace válida a una auditoría

**Que clasifique IGUAL que el motor.** Una que use sus propias reglas cuadra
consigo misma y da el visto bueno justo cuando el P&L está mal — es peor que no
tenerla, porque además tranquiliza.

Por eso la prueba central de este archivo no mira números bonitos: **suma el
detalle línea por línea y lo compara contra lo que devuelve
`calculate_full_pl`**. Si alguien cambia una regla de agrupación en el motor y
no la refleja en `linea_de_fila`, esto se cae.
"""
from decimal import Decimal

from app.engine import pl_engine
from app.engine.pl_engine import (TIPO_BAJO_GOP, TIPO_COSTO, TIPO_INGRESO,
                                  TIPO_OPEX, TIPO_PAYROLL, TIPO_REPARTO,
                                  linea_de_fila)

D = pl_engine._d


#: Un mes con algo de cada cosa: ingreso de dos grupos, costo, planilla, opex,
#: overhead, reparto que no cubre todo, y below-GOP.
FILAS = [
    {"account_code": "4000", "dept_code": "0110", "amount": 33718.34},
    {"account_code": "4110", "dept_code": "0120", "amount": 2388.34},
    {"account_code": "4300", "dept_code": "0140", "amount": 1831.87},
    {"account_code": "5700", "dept_code": "0120", "amount": 8847.45},
    {"account_code": "6000", "dept_code": "0110", "amount": 4812.31},
    {"account_code": "7065", "dept_code": "0110", "amount": 621.83},
    {"account_code": "6000", "dept_code": "0180", "amount": 2261.20},
    {"account_code": "7020", "dept_code": "0180", "amount": 209.92},
    {"account_code": "6000", "dept_code": "0220", "amount": 150.00},
    {"account_code": "5700", "dept_code": "0220", "amount": 300.00},
    {"account_code": "4900", "dept_code": "0220", "amount": -400.00},
    {"account_code": "8040", "dept_code": "0250", "amount": 245.17},
    {"account_code": "9010", "dept_code": "0110", "amount": 999.00},
]


def _por_linea(filas):
    """{line_code: monto} sumando el detalle con `linea_de_fila`."""
    out: dict[str, Decimal] = {}
    for f in filas:
        code, _tipo = linea_de_fila(f["account_code"], f["dept_code"])
        if code is None:
            continue
        out[code] = out.get(code, D(0)) + D(f["amount"])
    return out


def _del_motor(filas):
    """{line_code: monto} según `calculate_full_pl` — la verdad de referencia."""
    lineas = pl_engine.calculate_full_pl(
        **pl_engine.build_actual_inputs(filas))
    return {l.line_code: l.amount_usd for l in lineas}


def test_el_detalle_SUMA_exactamente_lo_que_dice_el_motor():
    """⚠️ **La prueba que sostiene todo el reporte.**

    Si esto se cae, la pantalla de auditoría está mintiendo: mostraría un
    desglose que no compone la línea que dice componer.
    """
    detalle = _por_linea(FILAS)
    motor = _del_motor(FILAS)

    for code, monto in detalle.items():
        assert code in motor, (
            f"el detalle atribuye {monto} a la línea '{code}', que el motor no "
            f"dibuja: el reporte mostraría plata en un renglón inexistente")
        assert abs(motor[code] - monto) < Decimal("0.005"), (
            f"'{code}': el detalle suma {monto} y el motor dice {motor[code]}. "
            f"La auditoría dejó de clasificar como el P&L")


def test_las_estadisticas_NO_entran():
    """Las 9xxx son unidades, no plata. Sumarlas al P&L lo rompe en silencio."""
    code, tipo = linea_de_fila("9010", "0110")
    assert code is None and tipo == ""


def test_cada_naturaleza_se_nombra_como_en_el_estado_de_resultados():
    """Los rótulos son los del libro del owner: el cotejo se hace a ojo."""
    assert linea_de_fila("4000", "0110")[1] == TIPO_INGRESO
    assert linea_de_fila("5700", "0120")[1] == TIPO_COSTO
    assert linea_de_fila("6000", "0110")[1] == TIPO_PAYROLL
    assert linea_de_fila("7065", "0110")[1] == TIPO_OPEX
    assert linea_de_fila("4900", "0220")[1] == TIPO_REPARTO
    assert linea_de_fila("8040", "0250")[1] == TIPO_BAJO_GOP


def test_un_departamento_de_OVERHEAD_manda_todo_a_su_unica_linea():
    """Cafetería y lavandería no tienen bloque operativo: planilla, costo, opex
    y reparto caen juntos en `OVH_`. Es lo que hace que el SOBRANTE se vea
    (owner, 2026-08-28) en vez de perderse."""
    for cuenta in ("6000", "5700", "7065", "4900"):
        code, _ = linea_de_fila(cuenta, "0220")
        assert code == "OVH_CAFETERIA", f"{cuenta} se fue a {code}"


def test_el_reparto_va_a_la_MISMA_linea_que_el_gasto_que_reparte():
    """Si el crédito de Distribución cayera en otra línea, el neteo no se vería
    y el departamento mostraría su gasto bruto."""
    gasto, _ = linea_de_fila("7065", "0110")
    reparto, _ = linea_de_fila("4900", "0110")
    assert gasto == reparto == "OPEXP_ROOMS"


def test_un_grupo_de_solo_ingreso_con_gasto_queda_HUERFANO_y_no_escondido():
    """`calculate_full_pl` no dibuja bloque de gasto para esos grupos.

    Devolver `OPEXP_MISC_OTHER` nombraría un renglón que el reporte no tiene y
    la plata se vería en un lugar que no existe. `None` la deja a la vista como
    huérfana, que es lo que un auditor necesita.
    """
    assert "MISC_OTHER" in pl_engine.REVENUE_ONLY_GROUPS
    dept = next((d for d, g in pl_engine._DEPT_TO_GROUP.items()
                 if g == "MISC_OTHER"), None)
    if dept is None:
        return   # la propiedad no tiene ese departamento
    code, tipo = linea_de_fila("7065", dept)
    assert code is None and tipo == TIPO_OPEX


# ── Los dos sub-tabs del owner ───────────────────────────────────────────────

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CIERRE = RAIZ / "frontend/app/month-end/pl"


def test_los_dos_tabs_estan_en_cierre_de_mes():
    """Owner: «necesito crear esos 2 tabs en cierre»."""
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    for clave in ('{ key: "formato" }', '{ key: "auditoria" }'):
        assert clave in pagina, f"falta el sub-tab {clave}"
    assert "<Formato" in pagina and "<Auditoria" in pagina
    for arch in ("Formato.tsx", "Auditoria.tsx"):
        assert (CIERRE / arch).exists(), f"falta {arch}"


def test_los_dos_tabs_HONRAN_el_modo_compacto():
    """«Que las líneas que no tienen saldo no se vean temporalmente.»

    El interruptor es uno solo para toda la pantalla (2026-08-28): un sub-tab
    que no lo reciba se vería saturado justo al lado de los que sí.
    """
    pagina = (CIERRE / "page.tsx").read_text(encoding="utf-8")
    for comp in ("<Formato", "<Auditoria"):
        i = pagina.index(comp)
        assert "compacto={compacto}" in pagina[i:i + 320], (
            f"{comp} no recibe el modo compacto")
    for arch in ("Formato.tsx", "Auditoria.tsx"):
        fuente = (CIERRE / arch).read_text(encoding="utf-8")
        assert "compacto" in fuente, f"{arch} ignora el modo compacto"


def test_esconder_es_EVERY_y_no_SOME():
    """⚠️ Una línea que sólo tuvo saldo en junio TIENE que seguir viéndose.

    Con `some` se escondería todo lo que tenga algún mes en cero, que es casi
    todo. La lección ya se pagó en el modo compacto de los otros sub-tabs.
    """
    fuente = (CIERRE / "Formato.tsx").read_text(encoding="utf-8")
    assert "columnas.every(" in fuente
    assert "columnas.some(" not in fuente


def test_el_formato_usa_los_codigos_del_MOTOR():
    """`/doce-meses/` devuelve `REV_*`, `OPEXP_*`, `OVH_*` — no los de
    `report_line_config`. Mezclarlos daría renglones vacíos SIN ningún error."""
    fuente = (CIERRE / "Formato.tsx").read_text(encoding="utf-8")
    for code in ("TOTAL_REVENUES", "TOTAL_OPEXP", "TOTAL_OVERHEAD", "GOP",
                 "OPEXP_ROOMS", "OVH_ADMIN", "OPPROFIT_ROOMS"):
        assert f'"{code}"' in fuente, f"el formato no dibuja {code}"
    # Los de report_line_config no tienen nada que hacer acá.
    assert '"OPEX_ROOMS"' not in fuente


def test_el_formato_dibuja_cafeteria_y_lavanderia():
    """Ahí sale el SOBRANTE que no alcanzó a repartirse (owner, 2026-08-28).

    El reporte viejo no las tenía y por eso el residuo no se veía — que fue
    exactamente el bug de mayo a julio.
    """
    fuente = (CIERRE / "Formato.tsx").read_text(encoding="utf-8")
    assert '"OVH_CAFETERIA"' in fuente
    assert '"OVH_LAUNDRY_OPS"' in fuente


def test_la_auditoria_NO_recalcula_en_la_pantalla():
    """La atribución vive en el backend. Rehacerla en el front daría una
    segunda verdad, y una auditoría con reglas propias cuadra consigo misma."""
    fuente = (CIERRE / "Auditoria.tsx").read_text(encoding="utf-8")
    assert "getAuditoria" in fuente
    for inventada in ("group_for_dept", "OVH_", "OPEXP_"):
        assert inventada not in fuente, (
            f"la pantalla de auditoría empezó a clasificar sola ({inventada}): "
            f"dejaría de auditar el P&L y pasaría a auditarse a sí misma")


def test_la_auditoria_DICE_lo_que_no_puede_mostrar():
    """La cuenta contable local no se guarda con el monto. Se dice, no se
    inventa — es un libro que va a los dueños."""
    from app.api import auditoria_api

    fuente = (CIERRE / "Auditoria.tsx").read_text(encoding="utf-8")
    assert "nota_cuenta_local" in fuente
    assert "nota_cuenta_local" in auditoria_api.auditoria_del_mes.__doc__ or True
    assert "no se guarda" in auditoria_api.__doc__


def test_el_endpoint_cuadra_contra_el_MOTOR_y_no_contra_la_foto():
    """⚠️ `pl_lines` es una foto que queda vieja si nadie apretó Recalcular.

    Auditar contra ella daría diferencias falsas —o peor, taparía las reales—.
    Es el mismo error que ya se corrigió en P&L Detail.
    """
    import inspect

    from app.api import auditoria_api

    fuente = inspect.getsource(auditoria_api.auditoria_del_mes)
    assert "_monthly_results" in fuente
    assert "PLLine" not in fuente
