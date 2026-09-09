# -*- coding: utf-8 -*-
"""
TODA CUENTA DE GASTO DE AMARENA TIENE CLASIFICACIÓN, O ESTÁ DICHO QUE NO.

## Por qué existe (2026-09-08)

El módulo de Break-Even de Amarena era **el mismo código que el de Corcovado,
byte por byte**, y aun así el tab salía vacío: lo que faltaba eran los DATOS.
`be_cost_classification` tenía **cero filas**, y eso no da error — el motor
trata cada monto sin regla como «100% fijo por defecto» y sigue. Con cero
reglas y cero costo variable el margen de contribución da **100%**, que es el
número más bonito del reporte y el más falso.

Estas dos semillas lo arreglan una vez. Esta prueba es la que impide que se
vuelva a romper de a poco.

## Cómo se rompe esto en el futuro, que es lo que la prueba caza

El catálogo de cuentas CRECE. Alguien agrega una cuenta a
`orden_plantilla.json` —la lista que la plantilla del Detalle le ofrece al
owner— y no toca la semilla del break-even. Entonces:

* la cuenta se puede digitar y entra al P&L;
* el break-even la cuenta **entera como fija**, sin decir nada;
* el equilibrio sube y el margen baja, y no hay forma de distinguir eso de un
  hotel que de verdad tiene más costo fijo.

Es exactamente la forma de fallar que el spec §2.6 declara inaceptable
(«nunca fallar en silencio»). Acá falla ruidoso.

## La lista de exclusiones es la otra mitad de la prueba

Una cuenta puede quedar fuera **a propósito**, pero entonces tiene que estar
escrita acá con su motivo. Y la prueba también reclama las exclusiones que ya
no corresponden: una lista de excepciones que nadie limpia termina tapando
justo lo que vino a documentar.

**No se resuelve agregando la cuenta a esta lista.** Si aparece una cuenta
nueva, lo que corresponde es clasificarla en
`app/seed_data/AMA/break_even/be_classification_seed.csv`; la lista de abajo es
para lo que de verdad no se sabe.
"""
import csv
import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SEMILLAS = RAIZ / "app" / "seed_data"
CARPETA = SEMILLAS / "AMA" / "break_even"

#: Los departamentos que Amarena opera y que NO están en `orden_plantilla.json`
#: —esa lista es la plantilla del Detalle, y el Club y el Área Recreativa no se
#: digitan ahí—. Sus cuentas salen del mapeo, que es donde sí están.
DEPTOS_FUERA_DE_LA_PLANTILLA = ("260", "270")

#: (dept_code, cuenta) -> por qué NO tiene regla. Cada una es una cuenta de
#: costo de ventas de un departamento que Corcovado no clasifica —no existe la
#: cuenta, y el departamento tampoco tiene un bloque de costo de ventas del que
#: copiar—. Inventarles «Variable» subiría el margen de contribución y bajaría
#: el equilibrio: el error se vería como una buena noticia (spec §2.6). Sin
#: regla, el motor las toma **100% fijas** y las muestra en «Por defecto: 100%
#: fijo», que es donde el owner las va a ver para decidir.
SIN_CLASIFICAR_A_PROPOSITO = {
    ("0155", "5500"): "Innoceana · Costos 1 — CWL no tiene 5500 ni costo de "
                      "ventas en Innoceana",
    ("0155", "5501"): "Innoceana · Costos 2 — ídem",
    ("0156", "5600"): "Crowther Lab · Costos 1 — CWL tiene el departamento en "
                      "`pending_classification`, sin ninguna regla",
    ("0156", "5601"): "Crowther Lab · Costos 2 — ídem",
    ("0205", "5360"): "Claro Huerta · Costos La Senda 1 — CWL tiene el "
                      "departamento en `pending_classification`",
    ("0205", "5361"): "Claro Huerta · Costos La Senda 2 — ídem",
    ("0205", "5362"): "Claro Huerta · Costos La Senda 3 — ídem",
    ("0205", "5363"): "Claro Huerta · Costos La Senda 4 — ídem",
    ("260", "5500"): "Club Madresal · Costos 1 — CWL no opera el Club: no hay "
                     "de dónde copiar el costo de ventas",
    ("260", "5501"): "Club Madresal · Costos 2 — ídem",
    ("270", "5600"): "Área Recreativa · Costos 1 — CWL no opera el Área "
                     "Recreativa",
    ("270", "5601"): "Área Recreativa · Costos 2 — ídem",
    # Ésta no es «no se sabe»: es una regla que NO debe existir.
    ("260", "8005"): "el Owners Fee es gasto de la propiedad (0250/8005). Con "
                     "dos reglas GL para `MGMT_FEE_3`, `_be_base` elige una por "
                     "el orden de la consulta y el fee de gerencia entero se le "
                     "acreditaría al Club",
}

#: Las cuentas del reparto (crédito de Cafetería y Lavandería). Corcovado
#: tampoco las clasifica: netean contra el gasto que reparten.
CUENTAS_DE_REPARTO = frozenset({"4900", "4901", "4999"})


def _clasificacion() -> list[dict]:
    with (CARPETA / "be_classification_seed.csv").open(
            encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _departamentos() -> list[dict]:
    with (CARPETA / "be_departments_seed.csv").open(
            encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _cuentas_de_gasto() -> set[tuple[str, str]]:
    """El universo que hay que clasificar: `(dept_code, cuenta)`.

    La plantilla del Detalle (`orden_plantilla.json`) **más** las cuentas de
    gasto del Club y del Área Recreativa, que no se digitan en esa plantilla.
    """
    orden = json.loads(
        (SEMILLAS / "orden_plantilla.json").read_text(encoding="utf-8"))["orden"]
    pares = {(r["dept_code"], r["cuenta"])
             for r in orden if r["clase"] != "Revenue"}

    mapeo = json.loads(
        (SEMILLAS / "mapping_pl.json").read_text(encoding="utf-8"))
    for r in mapeo["account_mapping"]:
        if str(r.get("active_status") or "").upper() != "YES":
            continue
        dept = str(r.get("dept_code") or "").strip()
        if dept in DEPTOS_FUERA_DE_LA_PLANTILLA and r.get("report_section") != "REVENUES":
            pares.add((dept, str(r.get("account_code") or "").strip()))
    return {(d, c) for d, c in pares if c not in CUENTAS_DE_REPARTO}


def test_las_dos_semillas_existen():
    """Una propiedad sin carpeta nace sin clasificación y el tab da 100% de MC."""
    assert (CARPETA / "be_departments_seed.csv").exists()
    assert (CARPETA / "be_classification_seed.csv").exists()


def test_toda_cuenta_de_gasto_tiene_regla_o_esta_dicho_por_que_no():
    """LA prueba. Una cuenta nueva sin clasificar rompe acá, no en producción."""
    con_regla = {(r["dept_code"], r["account"]) for r in _clasificacion()
                 if r["account"]}
    faltan = sorted(
        p for p in _cuentas_de_gasto()
        if p not in con_regla and p not in SIN_CLASIFICAR_A_PROPOSITO)
    assert not faltan, (
        "cuentas de gasto de Amarena SIN clasificación en el break-even: "
        f"{faltan}. El motor las va a tomar 100% fijas sin avisar. "
        "Clasificalas en app/seed_data/AMA/break_even/"
        "be_classification_seed.csv — y sólo si de verdad no se sabe, "
        "anotalas en SIN_CLASIFICAR_A_PROPOSITO con el motivo.")


def test_no_sobran_exclusiones():
    """Una excepción que ya no aplica tapa justo lo que vino a documentar."""
    con_regla = {(r["dept_code"], r["account"]) for r in _clasificacion()
                 if r["account"]}
    universo = _cuentas_de_gasto()
    sobran = sorted(p for p in SIN_CLASIFICAR_A_PROPOSITO
                    if p in con_regla or p not in universo)
    # (260, 8005) está en el universo y NO tiene regla: es correcta.
    assert not sobran, (
        f"exclusiones que ya no corresponden: {sobran}. O la cuenta ya está "
        "clasificada, o dejó de existir. Sacalas de SIN_CLASIFICAR_A_PROPOSITO.")


def test_el_club_y_el_area_recreativa_estan_clasificados():
    """Es lo que pidió el owner: los departamentos nuevos de cada propiedad.

    En Corcovado los dos están en `pending_classification` y sin una sola
    regla. Amarena SÍ los opera —el Club es el departamento más grande del
    hotel— y sin reglas su costo entero entraría como fijo.
    """
    filas = _clasificacion()
    for dept in DEPTOS_FUERA_DE_LA_PLANTILLA:
        assert sum(1 for r in filas if r["dept_code"] == dept) > 20, (
            f"el departamento {dept} casi no tiene reglas de clasificación")
    activos = {d["slug"]: d["status"] for d in _departamentos()}
    assert activos["club-madresal"] == "active"
    assert activos["area-recreativa"] == "active"


def test_la_llave_del_on_conflict_es_unica():
    """`(dept_code, account, pl_line)`: sin `pl_line` las filas LINEA chocan."""
    llaves = [(r["dept_code"], r["account"], r["pl_line"])
              for r in _clasificacion()]
    repetidas = sorted({k for k in llaves if llaves.count(k) > 1})
    assert not repetidas, (
        f"llaves repetidas en la semilla: {repetidas}. El `ON CONFLICT` del "
        "cargador las tomaría como la misma fila y se perdería una.")


def test_el_porcentaje_no_se_contradice_con_la_clase():
    """`Variable → 1.0` · `Fixed Cost → 0.0`, y siempre entre 0 y 1 (§1)."""
    malas = []
    for r in _clasificacion():
        pct = float(r["pct_variable"])
        esperado = 1.0 if r["original_class"] == "Variable" else 0.0
        if not 0 <= pct <= 1 or pct != esperado:
            malas.append((r["dept_code"], r["account"], r["original_class"], pct))
    assert not malas, f"clase y porcentaje se contradicen: {malas}"


def test_cada_regla_cae_en_un_departamento_que_la_semilla_declara():
    slugs = {d["slug"] for d in _departamentos()}
    huerfanas = sorted({r["be_department_slug"] for r in _clasificacion()}
                       - slugs)
    assert not huerfanas, (
        f"la clasificación referencia departamentos inexistentes: {huerfanas}. "
        "El cargador aborta antes de escribir, así que esto deja a Amarena SIN "
        "break-even.")


def test_cada_dept_code_de_una_regla_esta_en_su_departamento():
    """Sin esto el corte «Por Departamento» pierde plata sin que el total cambie.

    `_be_base` traduce el `dept_code` del GL a departamento del break-even con
    `be_department.dept_codes`. Un código que esté en una regla y no en la lista
    de su departamento hace que el monto entre al TOTAL y desaparezca del corte
    por departamento: las dos pantallas del mismo tab dejan de sumar lo mismo.
    """
    de_su_depto = {d["slug"]: {c.strip() for c in d["dept_codes"].split(",") if c.strip()}
                   for d in _departamentos()}
    malas = sorted({
        (r["be_department_slug"], r["dept_code"]) for r in _clasificacion()
        if r["dept_code"] and r["dept_code"] not in de_su_depto[r["be_department_slug"]]})
    assert not malas, f"dept_code fuera de su departamento: {malas}"


def test_una_sola_regla_gl_por_linea_de_debajo_del_gop():
    """El fee de gerencia, la reserva de capital y el impuesto se INYECTAN.

    `_be_base._completar_con_lo_que_calcula_el_pl` los busca por `pl_line`
    entre las reglas `GL` y se queda con **una** `(dept_code, account)`. Con dos
    candidatas, cuál gana lo decide el orden de la consulta — y con la
    equivocada el monto entero se le acredita a otro departamento.
    """
    bajo_gop = {"OWNER / NON-OP EXPENSES", "CAPITAL", "DEPRECIATION",
                "FINANCIAL EXPENSES", "TAX / NET PROFIT"}
    por_linea: dict[str, set] = {}
    for r in _clasificacion():
        if r["map_source"] == "GL" and r["section"] in bajo_gop:
            por_linea.setdefault(r["pl_line"], set()).add(
                (r["dept_code"], r["account"]))
    ambiguas = {k: sorted(v) for k, v in por_linea.items() if len(v) > 1}
    assert not ambiguas, f"más de una regla GL para la misma línea: {ambiguas}"


def test_el_impuesto_de_renta_queda_excluido_del_equilibrio():
    """§2.5: es función del resultado, no un costo fijo. Y por columna, no por texto."""
    excluidas = [r for r in _clasificacion()
                 if r["excluded_from_be"].lower() == "true"]
    assert [r["pl_line"] for r in excluidas] == ["INCOME_TAXES"]


def test_el_cargador_lee_la_carpeta_de_amarena():
    """La semilla no sirve de nada si el cargador mira otra carpeta."""
    from app import seed_break_even

    assert seed_break_even.carpeta("AMA") == CARPETA
    deptos, clases = seed_break_even.leer("AMA")
    assert len(deptos) == len(_departamentos())
    assert len(clases) == len(_clasificacion())


def test_el_script_manual_tambien_apunta_a_amarena():
    """Tenía `os.getenv('HOTEL_ID', 'CWL')`: sin la variable cargaba Corcovado."""
    import importlib

    mod = importlib.import_module("scripts.cargar_semilla_break_even")
    assert mod.SEMILLAS == CARPETA


@pytest.mark.parametrize("slug", ["private-bar", "tienda", "miscelaneos"])
def test_los_departamentos_sin_gasto_quedan_pendientes(slug):
    """No se marcan activos «por si acaso»: activo significa que tiene reglas."""
    estados = {d["slug"]: d["status"] for d in _departamentos()}
    assert estados[slug] == "pending_classification"
