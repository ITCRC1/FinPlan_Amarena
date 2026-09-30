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
    «EBITDA Before Capital» y «Total Gross Operating Profit» son los MISMOS
    rotulos que usa el P&L de la pantalla y los que el owner tiene en su Excel.
    Traducirlos obligaria a comprobar que «Utilidad bruta operativa» y «Gross
    Operating Profit» son el mismo renglon.

    ⚠️ Se comprueba contra `CASCADA` y no contra el texto del documento: desde
    el 2026-09-30 los cuadros van DIBUJADOS, asi que sus rotulos ya no salen en
    el texto extraible. Es el precio de la alineacion que pidio el owner, y es
    justo por eso que la lista tiene que quedar defendida en alguna parte.
    """
    from app.export.executive_summary import CASCADA, suave
    rotulos = [suave(r) for r, _c, _f in CASCADA]
    for esperado in ("Total Revenues", "EBITDA Before Capital", "Net Profit",
                     "Total Gross Operating Profit"):
        assert esperado in rotulos, f"se tradujo el rotulo «{esperado}»"
    # Y la sigla NO se baja: «Ebitda» se lee como una palabra mal escrita.
    assert not any("Ebitda" in r for r in rotulos)


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


def test_la_SECCION_4_sigue_afuera():
    """Owner, 2026-09-30: *«solo vamos a dejar seccion 1 y 2 por ahora; quita
    todo lo demas»*.

    ⚠️ El «por ahora» era literal, y se cumplio: mas tarde el mismo dia pidio
    *«3.0 Perspectivas para los meses siguientes»*, asi que la 3 volvio. La 4
    —lo favorable, lo desfavorable y la exposicion cambiaria— sigue afuera.

    `SECCIONES` sigue existiendo y `_positivos_y_negativos` se sigue llamando:
    borrar el armado obligaria a reescribirlo, y dejarlo sin llamar lo
    convertiria en codigo muerto.
    """
    t = _texto(build_executive_summary(_datos()))
    for fuera in ("SECCIÓN 4", "4.1 Lo favorable", "4.2 Lo desfavorable",
                  "4.3 Tipo de cambio", "Actividad comercial del mes",
                  "Nota metodológica"):
        assert fuera not in t, f"quedo «{fuera}»"
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


# ═════════ Las secciones de detalle, 2026-09-30 ══════════════════════════════
#
# Owner: *«quiero agregar mas secciones. pero quizas no quisiera crear o agregar
# cuadros quedan muy mal alineados. quiero que esos cuadros se conviertan en
# imagenes bien definidas»*.

def _con_detalle():
    d = _datos()
    doce = lambda x: [x] * 12          # noqa: E731
    d["ids"] = {"actual": "A", "budget": "B", "forecast": "F"}
    d["rangos"] = {"month": (8, 8), "ytd": (1, 8), "full": (1, 12)}
    d["departamentos"] = {"0110": "Rooms", "0120": "F&B"}
    d["nombres_cuenta"] = {"8005": "Management Fees"}
    d["detalle"] = {
        "A": {"revenue": {"0110": doce(100.0), "0120": doce(40.0)},
              "payroll": {"0110": doce(30.0)}, "cost": {}, "opex": {},
              "property": {"8005": doce(10.0)}},
        "B": {"revenue": {"0110": doce(80.0)}, "payroll": {"0110": doce(25.0)},
              "cost": {}, "opex": {}, "property": {"8005": doce(9.0)}},
        "F": {"revenue": {"0110": doce(110.0)}, "payroll": {}, "cost": {},
              "opex": {}, "property": {}},
    }
    return d


def test_el_informe_trae_los_CINCO_desgloses_de_cada_corte():
    """1.x.1 a 1.x.5, para el mes, el acumulado y el ano completo."""
    t = _texto(build_executive_summary(_con_detalle()))
    for num in ("1.1", "1.2", "1.3"):
        for j, rotulo in enumerate(
                ("Ingresos", "Salary", "Costo de ventas", "Opex",
                 "Propiedad y capital"), start=1):
            assert f"{num}.{j} Detalle de {rotulo} por departamento" in t, \
                f"falta {num}.{j}"


def test_el_desglose_SUMA_lo_que_el_informe_ya_dijo():
    """⚠️ Sale del MISMO agregador que el flow-through. Una segunda consulta
    podria no sumar el total que el informe dijo dos parrafos antes, y en un
    documento en prosa eso no se nota."""
    from app.export.executive_summary import _renglones_del_detalle
    d = _con_detalle()
    filas = _renglones_del_detalle(d, "revenue", "A", "B", (1, 8))
    assert sum(f[1] for f in filas) == 8 * 140.0     # 100 + 40, ocho meses
    assert sum(f[2] for f in filas) == 8 * 80.0


def test_una_cuenta_sin_movimiento_NO_ocupa_una_fila():
    """Un cero en las dos versiones no dice nada, y son decenas."""
    from app.export.executive_summary import _renglones_del_detalle
    d = _con_detalle()
    d["detalle"]["A"]["revenue"]["0199"] = [0.0] * 12
    d["detalle"]["B"]["revenue"]["0199"] = [0.0] * 12
    filas = _renglones_del_detalle(d, "revenue", "A", "B", (1, 8))
    assert not any(f[0].startswith("0199") for f in filas)


def test_en_el_ANO_COMPLETO_el_desglose_es_del_FORECAST():
    """La misma regla del cuadro de arriba: el Actual del ano son los meses
    cargados."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'ids.get("forecast") if principal is f else ids.get("actual")' in src


def test_los_cuadros_de_detalle_se_DIBUJAN():
    """Una tabla de Word reparte el ancho sobrante con sus propias reglas: basta
    un rotulo largo para que una columna se ensanche y dos cuadros seguidos
    dejen de coincidir."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "from app.export.tabla_imagen import dibujar_cuadro, hay_fuente" in src
    assert "p.add_run().add_picture(io.BytesIO(png), width=Cm(ancho_cm))" in src


def test_sin_la_FUENTE_se_arma_la_tabla_de_siempre():
    """⚠️ El contenedor no trae ninguna fuente. Sin el archivo, Pillow cae a su
    tipografia de mapa de bits y el cuadro sale ilegible — y eso no se nota
    hasta que esta impreso. Un informe con un cuadro menos lindo se entrega."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "if not hay_fuente():" in src
    assert "return _tabla_word(doc, encabezados, filas, anchos=anchos," in src


def test_la_FUENTE_viaja_en_el_repo():
    assets = pathlib.Path(__file__).resolve().parents[1] / "app/export/assets"
    for f in ("Tinos-Regular.ttf", "Tinos-Bold.ttf", "FUENTES.md"):
        assert (assets / f).exists(), f"falta {f}"
    from app.export.tabla_imagen import hay_fuente
    assert hay_fuente(), "la fuente esta pero Pillow no la carga"


def test_el_cuadro_dibujado_es_un_PNG_de_verdad():
    from app.export.tabla_imagen import dibujar_cuadro
    png = dibujar_cuadro([("Dept", ""), ("Actual", "Agosto")],
                         [["Rooms", "$100.00"], ["TOTAL", "$100.00"]],
                         [6.0, 4.0], resaltar={1})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image
    import io as _io
    im = Image.open(_io.BytesIO(png))
    # 10 cm a 120 px/cm: el ancho tiene que dar ~1200 px, o no se imprime bien.
    assert im.width == 1200, im.width


def test_la_SECCION_3_dice_lo_que_FALTA_y_no_el_ano_entero():
    """El ano entero ya esta en 1.3. La pregunta de esta seccion es que viene."""
    t = _texto(build_executive_summary(_con_detalle()))
    assert "SECCIÓN 3 — Perspectivas para los meses siguientes" in t
    assert "Quedan" in t and "por delante" in t


def test_cuando_el_forecast_ARRASTRA_el_presupuesto_el_informe_lo_dice():
    """⚠️ Pasa de verdad —agosto 2026—: el Forecast se armo como «los meses
    cargados mas el Budget para el resto». Sin decirlo, la seccion escribe
    «+0,0%» y se lee como que el ano va a aterrizar clavado en el plan, que es
    la conclusion contraria a la verdadera: todavia no se proyecto."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "if abs(rev - rev_b) < 0.01 and abs(eb - eb_b) < 0.01:" in src
    assert "El tramo que falta es, hoy, el presupuesto." in src


# ═════════ Menos peso en la pagina, 2026-09-30 ═══════════════════════════════
#
# Owner, mirando el informe con las secciones nuevas: *«esto se ve muy cargado…
# quisiera mas simple, quizas todo este bien, solo mas pequeno. que todos los
# cuadros queden en minuscula y mas pequenas»*.

def test_los_cuadros_van_MAS_CHICOS_que_el_cuerpo():
    """⚠️ El cuerpo se queda en 12 —eso lo pidio el owner y es lo que se lee—.
    Lo que recarga la pagina son diecisiete cuadros con la letra casi del tamano
    del parrafo que los presenta."""
    from app.export.executive_summary import CUERPO, CUERPO_TABLA
    assert CUERPO == 12
    assert CUERPO_TABLA == 8


def test_un_rotulo_GRITADO_se_baja_a_titulo():
    from app.export.executive_summary import suave
    assert suave("TOTAL OVERHEAD EXPENSES") == "Total Overhead Expenses"
    assert suave("FINES AND OTHER NON-DEDUCTIBLE EXPENSES") == \
        "Fines and Other Non-Deductible Expenses"
    assert suave("EXCHANGE GAIN/LOSSES") == "Exchange Gain/Losses"
    assert suave("INTEREST ON LOANS") == "Interest on Loans"


def test_una_SIGLA_no_se_baja():
    """«Ebitda» se lee como una palabra mal escrita, no como una sigla."""
    from app.export.executive_summary import suave
    assert suave("EBITDA BEFORE CAPITAL") == "EBITDA Before Capital"
    assert suave("ADR") == "ADR"
    assert suave("OTA") == "OTA"


def test_un_rotulo_que_YA_esta_en_mixto_no_se_toca():
    """⚠️ Es el nombre propio que alguien escribio: «arreglarlo» le cambiaria la
    capitalizacion a un dato."""
    from app.export.executive_summary import suave
    for t in ("Club Madresal", "Garden View Deluxe-Tented Villa",
              "Total available Rooms", "Owners Fees"):
        assert suave(t) == t


def test_la_regla_de_la_caja_esta_en_UN_solo_lugar():
    """Son diecisiete cuadros de cinco sitios distintos: con la regla repartida,
    el dia que se agregue el dieciocho va a gritar y nadie se va a acordar de
    por que."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "def _suavizar(encabezados, filas):" in src
    assert src.count("encabezados, filas = _suavizar(encabezados, filas)") == 2


def test_un_rotulo_que_NO_cabe_se_RECORTA_y_no_se_monta():
    """⚠️ Un dibujo no envuelve ni corta solo: sin esto, un rotulo largo sigue
    escribiendose por encima de la celda de al lado.

    Se vio en el informe de agosto —«8025 · Fines and Other Non-Deductible
    Expenses» montado sobre su propio monto— y no hay forma de notarlo hasta
    mirar la imagen.
    """
    from app.export.tabla_imagen import dibujar_cuadro
    import io as _io
    from PIL import Image
    largo = "8025 · Fines and Other Non-Deductible Expenses y algo mas todavia"
    png = dibujar_cuadro([("Cuenta", ""), ("Actual", "Ago")],
                         [[largo, "$11,659.17"]], [4.0, 4.0])
    im = Image.open(_io.BytesIO(png)).convert("RGB")
    # La franja donde empieza la columna del monto tiene que estar limpia: si el
    # rotulo se monto, ahi hay tinta del rotulo.
    x = round(4.0 * 120)          # el borde entre las dos columnas
    fila = round(im.height * 0.72)
    ventana = [im.getpixel((x - i, fila)) for i in range(1, 12)]
    assert all(sum(p) > 700 for p in ventana), \
        "el rotulo llego hasta el borde de la columna: se monta con el monto"
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app/export/tabla_imagen.py").read_text(encoding="utf-8")
    assert "def recortar(texto: str, fuente, ancho: int) -> str:" in src


# ═════════ La pasada pagina por pagina, 2026-09-30 ═══════════════════════════

def test_los_NEGATIVOS_de_la_PROSA_van_en_rojo():
    """Owner: *«en este informe ejecutivo lo que es negativo debe ir en rojo»*.

    En los cuadros ya iba; en el texto no, y el texto es donde el informe dice
    lo que paso. `-$300.7K` en medio de un parrafo se lee igual que `$300.7K`
    si nada lo distingue: el guion se pierde entre las palabras.
    """
    from app.export.executive_summary import _NEGATIVO
    for t in ("-$300.7K", "($1,234.50)", "-19.8%", "-3.8pp", "- $25.4K"):
        assert _NEGATIVO.search(t), f"no detecto «{t}» como negativo"
    for t in ("+19.3%", "$300.7K", "3.81pp", "234.6%"):
        assert not _NEGATIVO.search(t), f"pinto de rojo «{t}», que es positivo"
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "def _escribir(p, txt: str, negrita: bool):" in src
    assert "r.font.color.rgb = ROJO if rojo else NEGRO" in src


def test_cada_parrafo_lleva_SANGRIA():
    """Owner: *«cada nuevo parrafo debe llevar sangria»*. Con el texto
    justificado y sin linea en blanco entre bloques, dos parrafos seguidos se
    leen como uno.

    ⚠️ Solo el cuerpo: los rotulos de los cuadros pasan `justificar=False` y con
    sangria quedarian desalineados del cuadro que presentan.
    """
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "SANGRIA = 0.75" in src
    assert "if justificar:" in src
    assert "p.paragraph_format.first_line_indent = Cm(SANGRIA)" in src


def test_TODOS_los_cuadros_se_dibujan():
    """Owner: *«habiamos quedado que todos los cuadros debian convertirse en
    imagenes; favor revisa pagina por pagina»*.

    Era verdad a medias: solo los quince desgloses se dibujaban. Los de la
    cascada, el flow-through, la tabla de tarifas y el mix seguian siendo
    tablas de Word — y son los que el owner ve primero.
    """
    src = DOCX_MOD.read_text(encoding="utf-8")
    cuerpo = src[src.index("def _tabla(doc,"):src.index("def _tabla_word(doc,")]
    assert "return _cuadro_imagen(doc, encabezados, filas, anchos or [], resaltar)" in cuerpo
    # Y el documento no arma NINGUNA tabla de Word por su cuenta: el unico
    # camino a `_tabla_word` es el respaldo sin fuente.
    assert src.count("_tabla_word(") == 2


def test_un_cuadro_ALTO_se_achica_para_que_quepa():
    """⚠️ Un dibujo NO se parte entre dos paginas: lo que no entra se pierde por
    abajo sin avisar. Mas chico es peor que grande; recortado es peor que las
    dos cosas."""
    from app.export.executive_summary import ALTO_UTIL
    assert ALTO_UTIL == 21.5
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "if alto_cm > ALTO_UTIL:" in src
    assert "ancho_cm *= ALTO_UTIL / alto_cm" in src


def test_la_SECCION_2_1_trae_su_cuadro_de_volumen():
    """Owner: *«aca debe haber un cuadro como imagen para hablar del volumen,
    hay mucha informacion que se puede poner aca»*."""
    from app.export.executive_summary import VOLUMEN
    rotulos = [r for r, _f, _fmt in VOLUMEN]
    assert "Noches vendidas" in rotulos and "% Ocupación" in rotulos
    assert "Huéspedes por noche vendida" in rotulos
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "_cuadro_volumen(doc, act, bud, mes_ing)" in src


def test_el_cuadro_de_volumen_NO_inventa_los_dias_del_periodo():
    """⚠️ Hubo un renglon de «noches vendidas por dia» y se saco: los dias
    salian de dividir las disponibles entre las unidades, y las unidades no
    viajan en el encabezado. Quedaba un 16 escrito a mano —el de Amarena— que
    en cualquier otra propiedad habria dado un numero creible y falso."""
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert '"rooms_available") / 16' not in src


def test_la_tabla_de_tarifas_cierra_con_el_ACUMULADO():
    """Owner: *«debe haber un YTD al final de cada columna»*.

    ⚠️ Y NO es el promedio de la columna: la tarifa y la ocupacion son razones.
    El promedio de seis ADR mensuales le da el mismo peso a un mes de 20 noches
    que a uno de 202. Sale del mismo corte que el resto del informe.
    """
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert 'f"YTD {mes_ing}", usd(kpi(ytd_a, "adr"))' in src


def test_el_TOTAL_del_mix_es_el_del_MOTOR_y_el_cuadro_SUMA():
    """Owner: *«sumas al final de este cuadro»*.

    ⚠️ El total es `TOTAL_REVENUES`, el mismo renglon que el informe dijo dos
    paginas antes. Sumar los renglones de la lista cerraria contra si mismo y
    contra nada mas: medido en agosto 2026, la lista da 301.944,67 y el P&L dice
    306.124,86 — se le escapan cuatro lineas que nadie declaro en
    `RENGLONES_MIX`. Lo que falta se MUESTRA, o el cuadro obliga a sacar la
    calculadora.
    """
    api = API.read_text(encoding="utf-8")
    assert 'ta = linea(act["ytd"], "TOTAL_REVENUES")' in api
    assert '"Otras líneas de ingreso"' in api
    assert 'mix_total = ["Total ingresos"' in api


def test_los_canales_van_por_CODIGO_del_PMS_y_no_por_canal_comercial():
    """Owner: *«en el excel hay un tab de canales, traer ese aca, resumido YTD
    month»*.

    ⚠️ Antes salian cuatro renglones y el MAYOR se llamaba «Sin asignar»: tres
    codigos que nadie clasifico. Un cuadro cuyo renglon mayor dice «sin
    asignar» no dice por donde entro la reserva, dice que falta configurar algo.
    """
    src = DOCX_MOD.read_text(encoding="utf-8")
    assert "def _cuadro_canales(doc, datos: dict, mes_ing: str)" in src
    assert 'clave = (f.get("canal_code") or f.get("canal") or "—").strip()' in src
    # El mes y el acumulado, en el mismo cuadro.
    assert '"m_noc": 0.0, "m_rev": 0.0, "y_noc": 0.0, "y_rev": 0.0' in src
    # Y la fila del PDF solo si hay cortesias, o repetiria el total.
    assert 'if any(not d["cuenta"] for d in acc.values()):' in src
