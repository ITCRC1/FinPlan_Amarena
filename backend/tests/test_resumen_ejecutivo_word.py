# -*- coding: utf-8 -*-
"""El Resumen Ejecutivo mensual en Word.

Owner, 2026-09-30, entregando el `Executive Summary` de CWL: *«usa este formato
como estandar y prepara uno igual para agosto en Amarena. quiero el informe en
word»*.

## Lo que este archivo defiende

El informe se lee como prosa, y una prosa no cuadra contra nada: si una frase
dice un numero distinto del cuadro que tiene debajo, no hay forma de notarlo. Por
eso todo lo que se afirma sale del MISMO agregador que el cierre, y por eso las
frases se arman con la variacion en la mano.
"""
import io
import pathlib

import pytest

from app.export.executive_summary import (
    build_executive_summary, k, pct, usd, var_pct,
)

API = pathlib.Path(__file__).resolve().parents[1] / "app/api/executive_summary_api.py"
DOCX_MOD = pathlib.Path(__file__).resolve().parents[1] / "app/export/executive_summary.py"


def _col(rev, gop, ebitda, neto, occ, adr, noc=100.0, disp=300.0, sid="x",
         corte="ytd"):
    return {
        "__sid": sid, "__corte": corte,
        "kpis": {"rooms_available": disp, "rooms_occupied": noc, "guests": noc * 2,
                 "occupancy_pct": occ, "adr": adr, "revpar": rev / disp},
        "lines": [
            {"line_code": "TOTAL_REVENUES", "amount_usd": rev},
            {"line_code": "TOTAL_OPEXP", "amount_usd": rev * 0.5},
            {"line_code": "TOTAL_OP_PROFIT", "amount_usd": rev * 0.5},
            {"line_code": "TOTAL_OVERHEAD", "amount_usd": rev * 0.3},
            {"line_code": "GOP", "amount_usd": gop},
            {"line_code": "TOTAL_NON_OP", "amount_usd": rev * 0.05},
            {"line_code": "EBITDA_BEFORE", "amount_usd": ebitda},
            {"line_code": "EBITDA_AFTER", "amount_usd": ebitda * 0.9},
            {"line_code": "EBT", "amount_usd": neto * 1.1},
            {"line_code": "NET_PROFIT", "amount_usd": neto},
            {"line_code": "REV_ROOMS", "amount_usd": rev * 0.6},
            {"line_code": "REV_TOURS", "amount_usd": rev * 0.2},
        ],
    }


def _version(mult=1.0, sid="x"):
    return {
        "scenario_id": sid, "type": "ACTUAL", "version": "Final", "year": 2026,
        "month": _col(277_856 * mult, -45_851, -63_673, -99_140, 0.2731, 514.31,
                      sid=sid, corte="month"),
        "ytd": _col(3_973_720 * mult, 968_084, 762_972, 213_040, 0.4583, 599.41,
                    noc=3341, disp=7290, sid=sid, corte="ytd"),
        "full": _col(5_040_287 * mult, 709_847, 430_693, -213_072, 0.4474, 596.82,
                     noc=4483, disp=10020, sid=sid, corte="full"),
    }


def _datos():
    act, bud = _version(1.0, "a"), _version(0.907, "b")
    bud["type"] = "BUDGET"
    fcs = _version(0.98, "f")
    fcs["type"] = "FORECAST"
    gasto = {("a", "month"): 100.0, ("b", "month"): 90.0}

    def totales(col, clave):
        if clave == "TOTAL_REVENUES":
            return next(l["amount_usd"] for l in col["lines"]
                        if l["line_code"] == "TOTAL_REVENUES")
        base = {"TOTAL_PAYROLL": 1_506_428, "TOTAL_OPEX_ONLY": 1_017_695,
                "TOTAL_COST": 481_511, "TOTAL_PROPERTY": 755_043}[clave]
        return base * (1.0 if col["__sid"] == "a" else 0.92)

    return {
        "propiedad": "Amarena Canvas Hotel", "mes": 8, "anio": 2026,
        "actual": act, "budget": bud, "forecast": fcs,
        "rotulos": {"actual": "ACTUAL Final 2026", "budget": "BUDGET Final 2026",
                    "forecast": "FORECAST Working 2026"},
        "totales": totales,
        "mix": [["Rooms", "$2,021,430.00", "$1,890,670.00", "$130,760.00", "+6.9%"]],
        "adr_por_mes": [["08", "$514.31", "27.31%", "254"]],
        "positivos": [("Ingreso total",
                       "El ingreso llegó a $3.974M contra $3.605M presupuestados.")],
        "negativos": [("Costo de ventas",
                       "El costo de ventas cerró por encima del plan.")],
    }


def _texto(blob: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(blob))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for fila in t.rows:
            partes += [c.text for c in fila.cells]
    return "\n".join(partes)


def test_el_informe_se_genera_y_es_un_docx():
    blob = build_executive_summary(_datos())
    assert blob[:2] == b"PK", "no es un .docx"
    assert len(blob) > 10_000


def test_trae_las_secciones_del_formato_del_owner():
    """El PDF que el owner dio como estandar: portada, introduccion, los tres
    cortes numerados, los drivers y los positivos/negativos.

    ⚠️ **En espanol.** Owner, 2026-09-30, señalando el boton: *«esto debe ser en
    español»*. El PDF modelo estaba en ingles y de ahi venia el primer armado,
    pero el formato es la ESTRUCTURA —portada, los tres cortes, el
    flow-through, lo bueno y lo malo—, no el idioma: el informe lo lee la junta
    aca.
    """
    t = _texto(build_executive_summary(_datos()))
    assert "RESUMEN EJECUTIVO MENSUAL" in t
    assert "AGOSTO 2026" in t
    assert "Amarena Canvas Hotel" in t
    assert "INTRODUCCIÓN" in t
    for titulo in ("1.1 Agosto 2026 — el mes contra el presupuesto",
                   "1.2 Acumulado a Agosto 2026 — contra el presupuesto",
                   "1.3 Proyección del año completo 2026 contra el presupuesto",
                   "SECCIÓN 2 — De qué depende el resultado",
                   "2.1 Volumen (demanda)", "2.2 Tarifa (calidad del ingreso)",
                   "2.3 Composición del ingreso"):
        assert titulo in t, f"falta «{titulo}»"
    # Y no quedo prosa en ingles suelta.
    for ingles in ("Total Revenue reached", "above Budget", "versus Budget",
                   "Monthly Performance", "Overall Positive"):
        assert ingles not in t, f"quedo en ingles: «{ingles}»"


def test_los_ROTULOS_de_los_cuadros_se_quedan_en_ingles():
    """⚠️ A proposito, y es lo unico que no se traduce. «Total available Rooms»,
    «EBITDA BEFORE CAPITAL» y «GROSS OPERATING PROFIT» son los MISMOS rotulos
    que usa el P&L de la pantalla y los que el owner tiene en su Excel.
    Traducirlos obligaria a comprobar que «Utilidad bruta operativa» y «GROSS
    OPERATING PROFIT» son el mismo renglon."""
    t = _texto(build_executive_summary(_datos()))
    for rotulo in ("Total available Rooms", "Average Daily Room Only",
                   "TOTAL REVENUES", "EBITDA BEFORE CAPITAL", "NET PROFIT"):
        assert rotulo in t, f"se tradujo el rotulo «{rotulo}»"


def test_la_prosa_dice_LOS_NUMEROS_del_cuadro():
    """⚠️ Lo que este informe no puede hacer es decir en el texto algo distinto
    de lo que muestra el cuadro de al lado. Una prosa no cuadra contra nada: la
    discrepancia no se ve, y el que la encuentre deja de creerle a los dos.

    Por eso cada frase se arma con la variacion ya calculada.
    """
    t = _texto(build_executive_summary(_datos()))
    # El ingreso del mes y su variacion, en la escala del owner.
    assert "$277.9K" in t
    assert "$3.974M" in t        # el YTD
    assert "27.31%" in t         # la ocupacion del mes
    assert "$599.41" in t        # el ADR acumulado


def test_en_el_full_year_la_columna_principal_es_el_FORECAST():
    """⚠️ El Actual del año son los meses cargados. Compararlo contra doce meses
    de presupuesto mostraria una caida que solo significa que el año no ha
    terminado — y en un informe a duenos eso se lee como un derrumbe."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'principal = f if (corte == "full" and f) else a' in src
    assert "el año no" in src


def test_los_positivos_y_negativos_se_ORDENAN_por_tamano():
    """Un informe que siempre comenta los mismos seis renglones habla del mes en
    que se escribio la plantilla, no del mes que se esta cerrando."""
    src = API.read_text(encoding="utf-8")
    assert "porte.sort(key=lambda x: -abs(x[0]))" in src


def test_en_gasto_MENOS_es_favorable():
    """⚠️ Con la regla del ingreso, un sobrecosto entraria en la lista de
    positivos. Es el error clasico de una tabla de variaciones."""
    src = API.read_text(encoding="utf-8")
    assert "ga <= gb" in src, "el gasto se evalua con la regla del ingreso"
    docx = DOCX_MOD.read_text(encoding="utf-8")
    # Y en el flow-through el signo es el del EFECTO sobre la utilidad.
    assert 'efecto = (a - b) if clave == "TOTAL_REVENUES" else -(a - b)' in docx


def test_SOLO_van_las_secciones_1_y_2():
    """Owner, 2026-09-30: *«solo vamos a dejar seccion 1 y 2 por ahora; quita
    todo lo demas»*.

    ⚠️ El «por ahora» es literal: `SECCIONES` sigue existiendo y
    `_positivos_y_negativos` se sigue llamando. Borrar el armado obligaria a
    reescribirlo, y dejarlo sin llamar lo convertiria en codigo muerto.
    """
    t = _texto(build_executive_summary(_datos()))
    for fuera in ("SECCIÓN 3", "SECCIÓN 4", "4.1 Lo favorable",
                  "4.2 Lo desfavorable", "4.3 Tipo de cambio",
                  "Actividad comercial del mes", "Nota metodológica"):
        assert fuera not in t, f"quedo «{fuera}»"
    # Lo que si se queda.
    assert "1.1 Agosto 2026" in t and "SECCIÓN 2" in t
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'SECCIONES = ("1", "2")' in src


def test_la_regla_del_ano_completo_NO_se_perdio():
    """⚠️ Vivia en la nota metodologica del final, que se saco. Sin ella un
    Actual de ocho meses contra doce de presupuesto se lee como un derrumbe, asi
    que subio a su propio corte —1.3—, que es donde se lee la columna."""
    t = _texto(build_executive_summary(_datos()))
    assert "la columna principal es el Forecast" in t
    assert "que el año no ha terminado" in t


def test_dividir_entre_cero_NO_inventa_un_porcentaje():
    """Un presupuesto en cero no hace que la variacion sea del 100%: no hay
    porcentaje que dar, y escribir uno inventa una magnitud."""
    assert var_pct(100.0, 0.0) is None
    assert var_pct(100.0, 50.0) == pytest.approx(1.0)


def test_la_escala_cambia_en_el_millon():
    """El PDF mezcla miles y millones a proposito: `$3,973,720.59` en medio de
    una frase no se lee."""
    assert k(277_856.93) == "$277.9K"
    assert k(3_973_720.59) == "$3.974M"
    assert k(-99_140.96) == "-$99.1K"
    assert k(None) == "n/d"


def test_los_numeros_salen_del_MOTOR_y_no_se_recalculan():
    """⚠️ Si el resumen derivara sus propias cifras, el dia que difieran del
    cierre nadie sabria cual mando."""
    src = API.read_text(encoding="utf-8")
    assert "from app.api.pl_api import get_pl_compare" in src
    assert "from app.api.gasto_por_clase_api import gasto_por_clase" in src
    # Y no hay una segunda suma de la cascada.
    assert "_aggregate_selected" not in src


def test_un_mes_sin_noches_NO_entra_en_la_tabla_de_tarifas():
    """Su ADR es cero por falta de operacion, no por tarifa baja, y en una tabla
    de tarifas un cero se lee como un desplome. Amarena cierra cinco meses."""
    src = API.read_text(encoding="utf-8")
    assert 'if not float(kp.get("rooms_occupied") or 0):' in src
    assert "continue" in src


def test_el_endpoint_esta_montado():
    """Un modulo de export que nadie incluye no da error: simplemente no existe
    la ruta, y el boton del front devuelve 404 sin que nada lo avise."""
    from app.api.executive_summary_api import router
    assert [r.path for r in router.routes] == ["/reports/executive-summary/word/"]
    main = (pathlib.Path(__file__).resolve().parents[1] / "app/main.py").read_text(
        encoding="utf-8")
    assert "executive_summary_router" in main
    assert "app.include_router(executive_summary_router" in main


def test_con_base_NEGATIVA_no_se_escribe_porcentaje():
    """⚠️ El error que este informe tuvo con los numeros reales de Amarena.

    El EBITDA de agosto mejoro de -203,8K a -122,7K —81,1K a favor— y la formula
    da **-39,8%**, que se lee como un deterioro del 40%. La frase decia «above
    plan» y el parentesis decia lo contrario, en el mismo renglon.

    Con base negativa manda la palabra, que no se puede leer al reves.
    """
    assert var_pct(-122_660.0, -203_773.0) is None
    assert var_pct(100.0, 0.0) is None
    assert var_pct(306_124.0, 180_516.0) == pytest.approx(0.6959, rel=1e-3)


def test_el_informe_real_no_contradice_su_propio_texto():
    """Con los tres renglones de utilidad en negativo —el caso de Amarena en
    agosto— ninguna frase puede llevar un porcentaje que apunte al otro lado."""
    d = _datos()
    for corte in ("month", "ytd", "full"):
        for v in (d["actual"], d["budget"], d["forecast"]):
            for ln in v[corte]["lines"]:
                if ln["line_code"] in ("EBITDA_BEFORE", "NET_PROFIT", "GOP"):
                    ln["amount_usd"] = -abs(ln["amount_usd"])
    t = _texto(build_executive_summary(d))
    assert "RESUMEN EJECUTIVO MENSUAL" in t   # se genera igual
    assert "n/d%" not in t


def test_la_tipografia_es_la_que_pidio_el_owner():
    """Owner, 2026-09-30: *«el reporte debe ser en Times New Roman, letra 12,
    justificado, espacio 1.5, y entre titulos un espacio adicional»*."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'FUENTE = "Times New Roman"' in src
    assert "CUERPO = 12" in src
    assert "INTERLINEA = 1.5" in src
    assert "AIRE_TITULO" in src
    # Y de verdad queda escrito en el documento.
    import io
    from docx import Document
    doc = Document(io.BytesIO(build_executive_summary(_datos())))
    normal = doc.styles["Normal"]
    assert normal.font.name == "Times New Roman"
    assert normal.font.size.pt == 12
    assert normal.paragraph_format.line_spacing == 1.5


def test_el_aire_entre_titulos_NO_es_un_parrafo_vacio():
    """⚠️ Un párrafo vacío se descoloca en cuanto alguien edita arriba, y en
    Word se arrastra al pegar. El aire va como `space_before` del propio
    titulo."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "p.paragraph_format.space_before = Pt(AIRE_TITULO" in src


def test_los_NEGATIVOS_van_en_rojo():
    """⚠️ `f\"${-1234.5:,.2f}\"` da `$-1,234.50`: el signo queda escondido entre el
    simbolo y el numero, se pierde de vista en una columna y —lo que importa
    aca— no se puede detectar para pintarlo.

    Por eso los negativos salen entre PARENTESIS, que es ademas la convencion
    contable y la del PDF del owner.
    """
    assert usd(-1234.5) == "($1,234.50)"
    assert usd(1234.5) == "$1,234.50"
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "def _es_negativo(texto: str) -> bool:" in src
    assert "if _es_negativo(str(v)):" in src
    assert "r.font.color.rgb = ROJO" in src


def test_los_numeros_de_las_tablas_van_a_la_DERECHA():
    """Es lo unico que alinea las unidades entre si: con el texto centrado, un
    $1,234.50 y un $12.00 no comparten ninguna columna de digitos."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "p.alignment = (WD_ALIGN_PARAGRAPH.RIGHT if i" in src
    # El encabezado se alinea como su columna, o la columna se lee torcida.
    assert "p0.alignment = (WD_ALIGN_PARAGRAPH.RIGHT if i" in src
    # Y la celda no hereda el 1,5 del cuerpo.
    assert "p.paragraph_format.line_spacing = 1.0" in src


# ═════════ La presentacion, 2026-09-30 ═══════════════════════════════════════
#
# Owner: *«metete a la website de Amarena y mete imagenes a la presentacion en
# el inicio para que se vea super lindo. debes mejorar el diseno de los cuadros
# se ven raros»*.

def test_el_informe_sale_AUNQUE_falten_las_fotos():
    """⚠️ Las fotos son estetica; el informe es el trabajo. Si el directorio de
    assets no esta —un deploy a medias, un checkout sin LFS— el informe se
    genera igual, sin portada, y no revienta."""
    import app.export.executive_summary as mod
    viejo = mod.ASSETS
    try:
        mod.ASSETS = pathlib.Path("no/existe/en/ningun/lado")
        blob = build_executive_summary(_datos())
        assert blob[:2] == b"PK"
    finally:
        mod.ASSETS = viejo


def test_las_fotos_estan_en_el_REPO_y_no_se_bajan_al_generar():
    """El informe se arma en el servidor. Bajar las fotos de la web cada vez lo
    dejaria sin portada el dia que el sitio no conteste, y un documento a
    duenos sin portada se nota."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "urllib" not in src and "requests" not in src
    assets = pathlib.Path(__file__).resolve().parents[1] / "app/export/assets"
    for foto in ("logo.png", "portada.jpg", "propiedad.jpg", "habitacion.jpg"):
        assert (assets / foto).exists(), f"falta {foto}"


def test_el_LOGO_no_es_blanco():
    """El del sitio es blanco con transparencia, porque alla va sobre una foto
    oscura. Sobre el papel blanco del informe seria invisible: la primera
    portada salio con un hueco donde deberia ir la marca."""
    from PIL import Image
    assets = pathlib.Path(__file__).resolve().parents[1] / "app/export/assets"
    px = Image.open(assets / "logo.png").convert("RGBA")
    tintas = [px.getpixel((x, y))[:3]
              for x in range(0, px.width, 7) for y in range(0, px.height, 7)
              if px.getpixel((x, y))[3] > 200]
    assert tintas, "el logo no tiene trazo opaco"
    assert max(sum(t) / 3 for t in tintas) < 200, \
        "el logo sigue siendo claro: no se veria sobre el papel"


def test_en_el_ANO_COMPLETO_no_se_repite_la_columna_del_forecast():
    """En el ano completo la columna principal YA ES el Forecast. La quinta
    repetia el mismo numero al lado, en la misma fila."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "if fcs is None or fcs is act:" in src
    assert "cabezas, anchos = cabezas[:4]" in src


def test_las_verticales_de_los_cuadros_van_en_NIL():
    """⚠️ Word RESERVA el ancho del borde y no lo rellena: un borde vertical,
    aunque sea del mismo color del relleno, deja una franja sin pintar entre
    columna y columna. Se midio en el PDF: 1,57 pt de hueco con un borde de
    1,5 pt. Esa franja blanca ERA la raya que el owner veia como «rara»."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert '_borde(celda, "left", 0, color)' in src
    assert '_borde(celda, "right", 0, color)' in src


def test_el_orden_de_los_hijos_de_tcPr_y_tblPr_se_respeta():
    """⚠️ Word IGNORA en silencio un hijo que llegue fuera del orden del
    esquema: no da error, no avisa, simplemente no aplica. Con `w:shd` escrito
    antes que `w:tcBorders` los bordes de celda no se aplicaban y no habia
    manera de tapar la costura por mas que se le cambiara color y grosor."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "_ORDEN_TCPR" in src and "_ORDEN_TBLPR" in src
    from app.export.executive_summary import _ORDEN_TCPR, _ORDEN_TBLPR
    assert _ORDEN_TCPR.index("tcBorders") < _ORDEN_TCPR.index("shd")
    assert _ORDEN_TBLPR.index("tblBorders") < _ORDEN_TBLPR.index("tblCellMar")


def test_el_encabezado_se_REPITE_cuando_el_cuadro_cruza_la_pagina():
    """Un cuadro de veinte filas cruza la pagina, y sin esto la mitad de abajo
    queda como una lista de numeros sin columnas."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'OxmlElement("w:tblHeader")' in src
    assert 'OxmlElement("w:cantSplit")' in src


def test_un_cuadro_CORTO_no_se_parte_entre_dos_paginas():
    """El flow-through son ocho filas y quedaba cortado: una fila al pie de una
    pagina y las otras siete al principio de la siguiente.

    ⚠️ Solo los cortos. Un cuadro de treinta filas marcado como inseparable
    Word lo empuja entero y deja una pagina en blanco."""
    from app.export.executive_summary import CABE_ENTERO
    assert CABE_ENTERO == 10
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "if len(tabla.rows) > CABE_ENTERO:" in src
    assert "return" in src


def test_los_anchos_de_columna_CABEN_en_la_pagina():
    """21,59 cm de carta menos 2,4 de cada margen = 16,79 cm utiles. Cuando
    sumaban mas, Word los reescalaba solo y los encabezados se partian."""
    import re
    src = DOCX_MOD.read_text(encoding="utf-8")
    for crudo in re.findall(r"anchos=\[([0-9.,\s]+)\]", src):
        suma = sum(float(x) for x in crudo.split(",") if x.strip())
        assert suma <= 16.79, f"anchos=[{crudo}] suma {suma:.2f} cm"


def test_la_tabla_de_tarifas_dice_el_MES_con_su_nombre():
    """El informe se lee en espanol; un «03» en la primera columna parece un
    codigo."""
    api = API.read_text(encoding="utf-8")
    assert 'MESES[m["month"] - 1], usd(float(kp.get("adr") or 0)),' in api
    assert "MESES," in api.split("from app.export.executive_summary import")[1][:200]


# ═════════ Sin comparación contra el Forecast, 2026-09-30 ════════════════════
#
# Owner: *«quitar la opción de comparación versus forecast»*, la misma regla que
# acababa de pedir para la pantalla.

def test_el_mes_y_el_ACUMULADO_no_traen_columna_de_forecast():
    """Se compara contra el PRESUPUESTO y nada más."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "f if principal is f else None," in src
    t = _texto(build_executive_summary(_datos()))
    assert "Actual · Presupuesto\n" in t or "Actual · Presupuesto" in t
    assert "Actual · Presupuesto · Forecast" not in t


def test_el_ANO_COMPLETO_sigue_siendo_el_FORECAST():
    """⚠️ No es una comparación: es la columna principal. El Actual del año son
    los meses cargados, y restarle doce de presupuesto da un derrumbe que sólo
    dice que el año no terminó.

    Quitar el forecast de las comparaciones y quitarlo del año completo son dos
    cosas distintas; la segunda dejaría el informe sin proyección.
    """
    t = _texto(build_executive_summary(_datos()))
    assert "Forecast · Presupuesto" in t
    assert "la columna principal es el Forecast" in t


def test_se_fue_el_parrafo_CONTRA_EL_FORECAST():
    t = _texto(build_executive_summary(_datos()))
    assert "Contra el forecast" not in t
    assert "Frente al forecast" not in t


def test_la_PORTADA_dice_contra_que_se_compara():
    """Callar el forecast dejaría sin explicar por qué el año completo no es el
    Actual."""
    t = _texto(build_executive_summary(_datos()))
    assert "contra" in t.split("Generado por FinPlan")[1][:200]
    assert "el año completo," in t.split("Generado por FinPlan")[1][:200]
