# -*- coding: utf-8 -*-
"""El mapeo dice lo mismo que la clase de la cuenta.

Port de CWL. Owner, 2026-11-10: «asegurate que 4 son ingresos, 5 costos,
6 planilla, 7 opex y 8 gastos de la propiedad y 9 stats».

El cálculo separa por el primer dígito (`pl_engine`); estas pruebas exigen que
el mapeo tampoco lo contradiga: ni el rótulo de origen (migración 150), ni que
una estadística (9xxx) se cuele en el P&L.
"""
import importlib.util
import json
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MAPEO = json.loads((RAIZ / "app" / "seed_data" / "mapping_pl.json").read_text(encoding="utf-8"))

ORIGEN = {"6": {"Payroll", "PAYROLL"}, "7": {"Opex", "OpEx", "Operating Expense"}}
#: lo que NO puede decir el origen de una fila de cada clase
ORIGEN_PROHIBIDO = {"4": {"Payroll", "PAYROLL", "Opex", "Cost"},
                    "5": {"Payroll", "PAYROLL", "Opex", "Revenue"},
                    "8": {"Payroll", "PAYROLL", "Opex", "Cost", "Revenue"}}


def test_ninguna_estadistica_esta_en_el_pl():
    assert not [x for x in MAPEO["account_mapping"] if str(x["account_code"]).startswith("9")]


def test_el_origen_de_planilla_y_opex_dice_su_clase():
    malas = [(x["source_department"], x["account_code"], x["source_origin"])
             for x in MAPEO["account_mapping"]
             if str(x["account_code"])[0] in ORIGEN
             and x["source_origin"] not in ORIGEN[str(x["account_code"])[0]]]
    assert not malas, malas[:10]


def test_ingreso_costo_y_propiedad_no_dicen_otra_clase():
    malas = [(x["source_department"], x["account_code"], x["source_origin"])
             for x in MAPEO["account_mapping"]
             if str(x["account_code"])[0] in ORIGEN_PROHIBIDO
             and x["source_origin"] in ORIGEN_PROHIBIDO[str(x["account_code"])[0]]]
    assert not malas, malas[:10]


def test_la_migracion_150_renombra_a_lo_que_dice_el_archivo():
    """Cada fila que la migración renombra tiene que existir en el archivo con el
    rótulo nuevo; si no, la semilla insertaría otra y quedarían dos."""
    ruta = RAIZ / "alembic" / "versions" / "150_origen_del_mapeo_segun_la_clase.py"
    spec = importlib.util.spec_from_file_location("m150", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    en_archivo = {(x["report_id"], x["source_department"], str(x["account_code"]), x["source_origin"])
                  for x in MAPEO["account_mapping"] if not x.get("vigente_desde")}
    assert len(mod.CAMBIOS) == 99
    for rep, dep, cta, viejo, nuevo in mod.CAMBIOS:
        assert (rep, dep, cta, nuevo) in en_archivo, (dep, cta, nuevo)
        assert (rep, dep, cta, viejo) not in en_archivo, (dep, cta, viejo)


def test_cada_fila_cae_en_la_categoria_de_su_clase():
    """La categoría que resulta de la sección del P&L (la que usa el mayor por
    mes) tampoco contradice el primer dígito de la cuenta."""
    from app.engine import gl_por_mes as g
    categoria = {"4": {"REVENUE", "ALLOCATIONS"}, "5": {"COST_OF_SALES"}, "6": {"PAYROLL"},
                 "7": {"OPERATING_EXPENSES"}, "8": {"BELOW_GOP"}}
    malas = [(x["source_department"], x["account_code"], x["report_section"])
             for x in MAPEO["account_mapping"]
             if g.categoria_de(str(x["account_code"]), x["report_section"])
             not in categoria[str(x["account_code"])[0]]]
    assert not malas, malas[:10]
