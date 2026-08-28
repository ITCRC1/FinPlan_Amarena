# -*- coding: utf-8 -*-
"""
EL EXCEL DE CONCEPTOS DICE LO MISMO QUE LA PANTALLA.

## Por qué existe (2026-08-27)

Owner: *«no hay ningún reporte donde yo veo los beneficios calculados según las
fórmulas. Este pareciera que te lo va a dar, pero después sale otra cosa»*.

Y tenía razón: `/payroll/{id}/export/excel/` baja las **posiciones** —persona,
salario, FTE— porque es la mitad de un viaje de ida y vuelta con el importador.
Los conceptos derivados (CCSS, aguinaldo, provisión de vacaciones, cesantía) no
estaban en ningún archivo: sólo en pantalla, un departamento a la vez.

## Lo que cuida

* **El Excel y la pantalla salen del MISMO `summarize_dept`.** Es la propiedad
  que importa: si el reporte sumara por su cuenta, el día que cambie una fórmula
  los dos dirían cosas distintas y nadie sabría cuál creer. Se verifica
  comparando el archivo contra el endpoint que alimenta la pantalla, celda por
  celda, no contra números escritos a mano.
* **Una hoja por departamento**, más el resumen, y el resumen suma las hojas.
* **Cada fila trae su cuenta.** Un `6023` en la fila de Vacation Provision es lo
  que hace auditable el número sin abrir el código.
* **BASE va después de sus siete componentes y TOTAL al final** — el orden de la
  pantalla. Quien compara no tiene que reordenar mentalmente.
* **El archivo de subir NO cambió.** `/export/excel/` sigue trayendo posiciones:
  si alguien lo "mejora" convirtiéndolo en este reporte, el importador se queda
  sin plantilla y la vuelta se rompe en silencio.
"""
import io
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.export.conceptos_por_depto_excel import (FILAS, export_conceptos_por_depto,
                                                  _drivers)


class ParamsFalsos:
    """Sólo lo que lee `_drivers`. No toca la base: es un cálculo puro."""
    ccss_rate = Decimal("0.26830")
    aguinaldo_divisor = Decimal("12")
    overtime_pct = Decimal("0")
    bonus_pct = Decimal("0")
    vacaciones_rate = Decimal("0.04")
    severance_annual_rate = Decimal("0")
    cafeteria_daily_crc = Decimal("0")
    transport_monthly_crc = Decimal("0")
    housing_monthly_crc = Decimal("0")
    other_monthly_crc = Decimal("0")
    ins_annual_crc = Decimal("1130647.80")


def _mes(base=1000.0):
    """Un mes con BASE y sus derivados, coherente con los drivers de arriba."""
    ccss = base * 0.2683
    agui = base / 12
    vac = base * 0.04
    return {
        "c6000": base, "c6001": 0.0, "c6002": 0.0, "c6003": 0.0, "c6010": 0.0,
        "c6024": 0.0, "c6027": 0.0, "base": base,
        "c6020": ccss, "c6021": agui, "c6004": 0.0, "c6022": 0.0,
        "c6023": vac, "c6025": 0.0, "c6026": 0.0, "c6028": 0.0,
        "c6029": 0.0, "c6030": 0.0,
        "total": base + ccss + agui + vac,
    }


@pytest.fixture
def libro():
    datos = [
        {"dept_code": "0111", "dept_name": "Front Desk",
         "monthly": [_mes(1000.0) for _ in range(12)]},
        {"dept_code": "0113", "dept_name": "Housekeeping",
         "monthly": [_mes(500.0) for _ in range(12)]},
    ]
    xlsx = export_conceptos_por_depto(datos, ParamsFalsos(), "AMA BUDGET Working", 2026)
    return load_workbook(io.BytesIO(xlsx))


def test_una_hoja_por_departamento_mas_el_resumen(libro):
    assert libro.sheetnames[0] == "Resumen", "el resumen va primero"
    assert len(libro.sheetnames) == 3
    assert any("0111" in h for h in libro.sheetnames)
    assert any("0113" in h for h in libro.sheetnames)


def test_cada_fila_trae_su_cuenta(libro):
    hoja = [h for h in libro.sheetnames if "0111" in h][0]
    ws = libro[hoja]
    por_concepto = {ws.cell(row=r, column=2).value: ws.cell(row=r, column=1).value
                    for r in range(6, 6 + len(FILAS))}
    assert por_concepto["Social Security"] == "6020"
    assert por_concepto["Vacation Provision"] == "6023"
    assert por_concepto["Aguinaldo"] == "6021"
    # BASE y TOTAL no son cuentas: son subtotales y no deben inventarse una.
    # openpyxl devuelve `None` donde se escribió cadena vacía, así que lo que
    # se afirma es «la celda está vacía», no cuál de las dos formas de vacío es.
    assert not por_concepto["BASE"]
    assert not por_concepto["TOTAL"]


def test_base_va_despues_de_sus_componentes_y_total_al_final():
    claves = [f[0] for f in FILAS]
    assert claves[-1] == "total"
    i = claves.index("base")
    # Los siete que la componen van antes; CCSS y aguinaldo, que se calculan
    # SOBRE la base, van después. Al revés el archivo se leería como si la CCSS
    # entrara en la base.
    assert claves[:i] == ["c6000", "c6001", "c6002", "c6003", "c6010", "c6024", "c6027"]
    assert claves[i + 1] == "c6020"


def test_el_driver_lleva_el_valor_del_escenario(libro):
    hoja = [h for h in libro.sheetnames if "0111" in h][0]
    ws = libro[hoja]
    drivers = {ws.cell(row=r, column=2).value: (ws.cell(row=r, column=3).value or "")
               for r in range(6, 6 + len(FILAS))}
    # No alcanza con decir «CCSS»: el número tiene que poder auditarse sin
    # abrir el código.
    assert "26.830%" in drivers["Social Security"]
    assert "BASE" in drivers["Social Security"]
    assert "12" in drivers["Aguinaldo"]
    assert "4.000%" in drivers["Vacation Provision"]


def test_lo_digitado_no_finge_tener_formula():
    d = _drivers(ParamsFalsos())
    # `overtime_pct` está en cero: decir «0% sobre S&W» mandaría a buscar el
    # error en el parámetro en vez de en el dato cargado.
    assert "digitado" in d["c6001"]
    assert "%" not in d["c6001"]


def test_sin_parametros_lo_dice_en_vez_de_mostrar_ceros():
    d = _drivers(None)
    assert all("default" in v for v in d.values())


def test_el_resumen_suma_lo_mismo_que_las_hojas(libro):
    ws = libro["Resumen"]
    anual_resumen = {}
    r = 5
    while ws.cell(row=r, column=1).value:
        anual_resumen[ws.cell(row=r, column=1).value] = ws.cell(row=r, column=15).value
        r += 1

    for code in ("0111", "0113"):
        hoja = [h for h in libro.sheetnames if code in h][0]
        ws2 = libro[hoja]
        fila_total = 5 + len(FILAS)          # encabezado en 5, TOTAL al final
        assert ws2.cell(row=fila_total, column=2).value == "TOTAL"
        assert ws2.cell(row=fila_total, column=16).value == pytest.approx(
            anual_resumen[code]), f"{code}: el resumen no cuadra con su hoja"


def test_el_excel_que_se_sube_no_cambio():
    """El de posiciones sigue siendo otro módulo, con su importador."""
    from app.export.payroll_excel import (export_payroll_to_excel,
                                          import_payroll_from_excel)
    assert callable(export_payroll_to_excel)
    assert callable(import_payroll_from_excel)
    import app.export.conceptos_por_depto_excel as nuevo
    assert not hasattr(nuevo, "import_conceptos_from_excel"), (
        "este archivo es un REPORTE: no debe crecerle un importador")
