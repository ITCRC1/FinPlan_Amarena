# -*- coding: utf-8 -*-
"""De qué está hecho el presupuesto, al lado de la cuenta, en el Excel del cierre.

Owner, 2026-09-30, sobre la 7105 de Rooms en el BUDGET Final 2026: *«tengo 3
líneas, Coral $600 para agosto, Fumigación $0 y Reservation fee $2000. Ocupo
abrir una columna a unas 3 columnas a la derecha de la última línea actual y
poner en la línea de la cuenta del excel la nota de lo que había en el
presupuesto. Esto ayuda a realizar el análisis con los dueños. Esto en el caso
de Opex; hay que intentar también para gastos de la propiedad y Payroll, sobre
todo para la cuenta 6000 de salarios: por lo menos poner las posiciones que
tienen salario, para usarlo como referencia en el momento en que se está
analizando con los dueños»*.

La hoja del checkbook muestra un TOTAL por (departamento, cuenta). De qué está
hecho vive un nivel más abajo, y sentado frente a un dueño ésa es la pregunta.
"""
import inspect
from decimal import Decimal
from pathlib import Path

from app.api import detalle_celda_api as api

FRONT = Path(__file__).resolve().parents[2] / "frontend"
CORTES = FRONT / "lib/checkbookCortes.ts"
CIERRE = FRONT / "app/month-end/pl/page.tsx"
API_TS = FRONT / "lib/api.ts"


# ── Cómo se lee la nota ──────────────────────────────────────────────────────

def test_el_monto_se_lee_sin_centavos_cuando_no_los_tiene():
    """`$600`, no `$600.00`. La nota se lee de corrido al lado de una tabla de
    montos; los centavos que no existen son ruido en una frase."""
    assert api._usd(600) == "$600"
    assert api._usd(2000) == "$2,000"
    assert api._usd(Decimal("1054.50")) == "$1,054.50"
    assert api._usd(0) == "$0"
    assert api._usd(None) == "$0"


def test_el_signo_va_antes_del_simbolo():
    """`-$600` y no `$-600`, que se lee como un precio mal escrito."""
    assert api._usd(-600) == "-$600"


def test_la_tasa_se_lee_como_porcentaje():
    """`driver_pct_or_rate` se guarda como fracción; la nota la lee como la
    escribió el usuario en el checkbook."""
    assert api._pct(Decimal("0.28")) == "28%"
    assert api._pct(Decimal("0.225")) == "22.50%"


def test_la_nota_reproduce_el_ejemplo_del_owner():
    """El caso exacto: 7105 · 0110 · BUDGET Final 2026, cerrando agosto.

    Coral lleva el año entre paréntesis porque agosto no es todo su
    presupuesto. Reservation Fee no, porque el mes ES el año."""
    subs = [
        api._Sub("Coral", Decimal("600"), Decimal("7200")),
        api._Sub("Fumigación Hotel", Decimal("0"), Decimal("0")),
        api._Sub("Reservation Fee", Decimal("2000"), Decimal("2000")),
    ]
    assert api._nota(subs, 8) == (
        "Coral $600 (año $7,200) · Reservation Fee $2,000 · Fumigación Hotel $0"
    )


def test_las_sublineas_en_CERO_se_listan_igual():
    """⚠️ La regla que hace útil la nota.

    Que la 7105 tuviera fumigación presupuestada en cero es información —se
    contempló y se decidió cero—, no ruido. Filtrarla haría que la nota diga
    MENOS de lo que el presupuesto dice, que es lo contrario de para qué
    existe."""
    subs = [api._Sub("Fumigación Hotel", Decimal("0"), Decimal("0"))]
    assert api._nota(subs, 8) == "Fumigación Hotel $0"


def test_lo_mas_grande_va_primero():
    """Lo que explica el número va arriba — el mismo criterio con el que el
    checkbook ordena sus cuentas dentro del departamento."""
    subs = [
        api._Sub("Chico", Decimal("10"), Decimal("10")),
        api._Sub("Grande", Decimal("900"), Decimal("900")),
    ]
    assert api._nota(subs, 1).startswith("Grande")


def test_sin_mes_la_nota_trae_el_ANIO_y_no_un_mes_cualquiera():
    """`mes=0` es «no me dijeron qué mes»: se muestra el año completo. Mostrar
    enero por defecto haría que la nota hable de otro período que el cuadro."""
    subs = [api._Sub("Coral", Decimal("600"), Decimal("7200"))]
    assert api._nota(subs, 0) == "Coral $7,200"


# ── De dónde sale ────────────────────────────────────────────────────────────

def test_la_nota_sale_del_BUDGET_y_de_ninguna_otra_version():
    """⚠️ Es «lo que había en el presupuesto».

    El actual no tiene sub-líneas —el mayor trae la cuenta y se acabó— y el
    forecast tiene las suyas, que son otra cosa. Sin Budget entre las versiones
    pedidas no hay nota: preferible a rotular el detalle del forecast como si
    fuera el presupuesto."""
    fuente = inspect.getsource(api.detalle_de_celda)
    assert 'esc.type == "BUDGET"' in fuente
    assert "_detalle_del_presupuesto" in fuente


def test_cada_clase_saca_el_detalle_de_SU_tabla():
    """Opex y below-GOP tienen `detail_desc`; la planilla tiene POSICIONES."""
    fuente = inspect.getsource(api._detalle_del_presupuesto)
    assert "OpexEntry" in fuente and "detail_desc" in fuente
    assert "NonOpEntry" in fuente
    assert "PayrollPosition" in fuente and "PayrollConceptEntry" in fuente


def test_el_costo_de_ventas_lleva_su_DRIVER_porque_no_tiene_sublineas():
    """⚠️ `CostEntry` no guarda detalle: guarda cómo se calcula la cifra.

    Inventarle sub-líneas sería inventar; dejar la columna vacía sería perder
    lo que sí explica su presupuesto. «28% de FOOD» es la respuesta."""
    fuente = inspect.getsource(api._detalle_del_presupuesto)
    assert "CostEntry" in fuente
    assert "REVENUE_LINE" in fuente and "_pct(" in fuente
    assert "_BASE_DEL_DRIVER" in inspect.getsource(api)


def test_la_planilla_NO_recalcula_el_salario():
    """El monto sale de `PayrollConceptEntry`, que es lo que el motor ya
    calculó —salario × FTE / TC del mes—.

    Rehacer esa cuenta acá daría una nota que no coincide con la celda que
    tiene al lado, y sobre los mismos datos, sin que nada falle."""
    fuente = inspect.getsource(api._detalle_del_presupuesto)
    assert "salary_amount" not in fuente, "se está recalculando el salario"
    assert "CONCEPTOS" in fuente, "los 17 conceptos son las cuentas 6xxx"


def test_la_planilla_usa_el_departamento_DEL_ASIENTO():
    """⚠️ La llave tiene que ser la misma que arma `_del_auxiliar`.

    Si acá subiera por la posición y allá por el asiento, la nota quedaría
    colgada de una fila que el cuadro no dibuja: no falla, no avisa, y la
    columna sale vacía sin que nada explique por qué."""
    fuente = inspect.getsource(api._detalle_del_presupuesto)
    assert 'r.dept_code or "") or propio' in fuente
    assert '_padre(str(r.dept_code or ""))' in inspect.getsource(api._del_auxiliar)


def test_el_below_GOP_se_resuelve_por_CUENTA_sola():
    """La clase 8 vive toda en el 0250 y no tiene departamento propio: su
    llave va con `""` y la fila la busca con ese respaldo."""
    fuente = inspect.getsource(api._detalle_del_presupuesto)
    assert 'anotar("", cuenta' in fuente
    assert 'detalle.get(("", cuenta)' in inspect.getsource(api.detalle_de_celda)


# ── Cómo llega a la hoja ─────────────────────────────────────────────────────

def test_la_columna_va_separada_por_dos_en_blanco():
    """Owner: *«a unas 3 columnas a la derecha de la última línea actual»*.

    Pegada al último monto se lee como una columna más del cuadro: el ojo
    busca un número a la derecha del rótulo y encuentra un párrafo."""
    src = CORTES.read_text(encoding="utf-8")
    assert src.count('{ label: "", ancho: 3, formato: "texto" }') == 2
    assert '{ label: "Detalle del presupuesto"' in src


def test_la_nota_va_SOLO_en_la_linea_de_la_cuenta():
    """Owner: *«poner en la línea de la cuenta»*.

    En el subtotal del departamento sería la mezcla de detalles de cuentas
    distintas, que no explica nada. `conDetalle` se llama en todas las filas
    para que el ancho cuadre, pero el texto sólo lo recibe una."""
    src = CORTES.read_text(encoding="utf-8")
    assert src.count("f.detalle") == 1


def test_la_columna_no_sale_si_no_hubo_Budget():
    """Una columna rotulada «Detalle del presupuesto» con todas las celdas
    vacías afirma que no hubo presupuesto — distinto de que no se pidió."""
    src = CORTES.read_text(encoding="utf-8")
    assert "opciones.notaDelPresupuesto && datos.detalle_de" in src


def test_la_celda_vacia_va_como_null_y_no_como_cadena():
    """⚠️ Los dos se ven vacíos, pero el exportador lee `null` como «no hay
    dato» y no le escribe fórmula. Con `""` la fila de subtotal intentaría
    sumar una cadena."""
    src = CORTES.read_text(encoding="utf-8")
    assert "[...valores, null, null, texto || null]" in src


def test_el_libro_del_cierre_pide_el_MES():
    """La nota muestra lo presupuestado para el mes que se cierra, que es
    contra lo que compara la columna del Actual. Sin el mes traería el año y
    se leería como si agosto hubiera presupuestado doce veces más."""
    src = CIERRE.read_text(encoding="utf-8")
    assert 'getDetalleDeCelda(ids, e.clase, "", mes)' in src
    assert "notaDelPresupuesto: true" in src
    assert "&mes=${mes}" in API_TS.read_text(encoding="utf-8")


def test_la_pantalla_de_checkbooks_NO_lleva_la_columna():
    """Ahí se abre la cuenta y se ve el detalle de verdad; la nota es para el
    archivo, que se lee frente a los dueños sin la app al lado."""
    for pagina in (FRONT / "app/month-end/checkbooks/page.tsx",
                   FRONT / "app/month-end/pl/Checkbooks.tsx"):
        assert "notaDelPresupuesto" not in pagina.read_text(encoding="utf-8"), (
            f"{pagina.name} activó la columna de la nota")
