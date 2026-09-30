# -*- coding: utf-8 -*-
"""El Excel de los cuadros: limpio, y con los totales visibles.

Owner, 2026-09-30, mirando el archivo bajado: *«quiero que todos los que son
totales bajen con el relleno bien claro. ademas que no bajen en el excel los
textos insertados. que bajen limpios»*.

Son dos cosas distintas y las dos venian mal:

* el relleno de los totales era `F0F4F8`, tan palido que sobre el blanco de
  Excel no se distingue — un total se leia como una fila mas;
* el subtitulo bajaba como una banda combinada de PROSA sobre las columnas.

Este cuadro es el que usan TODOS los botones de Excel que pasan por
`bajarCuadros`: el P&L en tres cortes, el checkbook, el armado de ingresos, la
auditoria y los capitulos del cierre.
"""
import io
import pathlib

from openpyxl import load_workbook

from app.export.cuadro_excel import build_cuadros_workbook
from app.export.excel_base import C

SUBTITULO = ("ACTUAL Final 2026 · consolidado — la varianza del full year es "
             "Forecast contra Budget: el Actual del año todavía no existe.")


def _cuadro():
    return {
        "titulo": "Full P&L Agosto 2026 · mes, YTD y full year",
        "subtitulo": SUBTITULO,
        "hoja": "Full P&L Ago",
        "columnas": [
            {"label": "ACCOUNT DESCRIPTION", "ancho": 40, "formato": "texto"},
            {"label": "Agosto · ACTUAL", "ancho": 15, "formato": "usd2"},
            {"label": "Agosto · BUDGET", "ancho": 15, "formato": "usd2"},
        ],
        "filas": [
            {"label": "Rooms", "valores": [54134.0, 40000.0]},
            {"label": "F&B", "valores": [6455.64, 5000.0]},
            {"label": "TOTAL REVENUES", "es_total": True,
             "valores": [79845.14, 66922.0]},
            {"label": "Total Operationg expenses", "es_total": True,
             "valores": [53006.21, 72077.59]},
        ],
    }


def _hoja(cuadros=None):
    blob = build_cuadros_workbook(cuadros or [_cuadro()])
    wb = load_workbook(io.BytesIO(blob))
    # La primera hoja es siempre el Índice; la que interesa es la siguiente.
    return wb, wb[[n for n in wb.sheetnames if n != "Índice"][0]]


def _relleno(celda) -> str:
    try:
        return (celda.fill.fgColor.rgb or "")[-6:]
    except Exception:
        return ""


def test_la_PROSA_no_baja_en_la_hoja():
    """⚠️ En pantalla el subtitulo explica; en una hoja de calculo estorba:
    rompe el filtro, se lleva el ancho de la primera columna al copiar, y
    aparece pegado arriba del cuadro cuando alguien lo pega en otro lado."""
    _, ws = _hoja()
    textos = [str(ws.cell(r, c).value or "")
              for r in range(1, 12) for c in range(1, 4)]
    assert not any(SUBTITULO[:40] in t for t in textos), \
        "el subtitulo sigue bajando a la hoja"
    # El TITULO si se queda: identifica la hoja, y sin el un archivo con seis
    # pestañas no se sabe de que mes es.
    assert any("Full P&L Agosto 2026" in t for t in textos)


def test_el_cuadro_NO_se_movio_de_fila():
    """⚠️ Quitar la banda podia subir la tabla una fila, y eso rompe mas de lo
    que arregla: media docena de pruebas —y las macros de quien ya usa estos
    archivos— buscan la cabecera en la fila 4. Lo que se pidio fue sacar el
    texto, no mover el cuadro."""
    _, ws = _hoja()
    assert ws.cell(4, 1).value == "ACCOUNT DESCRIPTION"
    assert ws.cell(2, 1).value in (None, ""), "la fila del subtitulo no quedo vacia"


def test_los_totales_bajan_con_relleno_VISIBLE():
    """`F0F4F8` sobre blanco no se distingue: en pantalla se adivina y al
    imprimir en blanco y negro desaparece."""
    _, ws = _hoja()
    total = next(r for r in range(1, 12)
                 if str(ws.cell(r, 1).value or "").startswith("TOTAL REVENUES"))
    normal = next(r for r in range(1, 12)
                  if str(ws.cell(r, 1).value or "") == "Rooms")
    for col in (1, 2, 3):
        assert _relleno(ws.cell(total, col)) == C["total_fill"], \
            f"la columna {col} del total no lleva relleno"
        assert _relleno(ws.cell(normal, col)) != C["total_fill"], \
            "una fila normal quedo con el relleno de total"
    # Y sigue en negrita: el relleno acompaña, no reemplaza.
    assert ws.cell(total, 1).font.bold


def test_el_relleno_es_CLARO_y_no_una_banda_oscura():
    """⚠️ Claro pero visible. Un total oscuro obligaria a poner el texto en
    blanco, y el cuadro pasaria a tener tantas bandas como bloques."""
    rgb = C["total_fill"]
    r, g, b = (int(rgb[i:i + 2], 16) for i in (0, 2, 4))
    luz = (r + g + b) / 3
    assert luz > 190, "el relleno de total quedo oscuro"
    assert luz < 245, "el relleno de total no se distingue del blanco"


def test_el_total_va_en_un_RECUADRO_negro():
    """Owner, 2026-09-30, mostrando el tab que arreglo a mano: recuadro exterior
    NEGRO medio arriba, abajo y en los extremos; las verticales internas finas y
    grises, como el resto.

    ⚠️ El negro va SOLO en los extremos. En todas las celdas, el total saldria
    con la rejilla negra y pareceria otra tabla.
    """
    _, ws = _hoja()
    total = next(r for r in range(1, 12)
                 if str(ws.cell(r, 1).value or "").startswith("TOTAL REVENUES"))
    primera, ultima = ws.cell(total, 1), ws.cell(total, 3)
    for c in (primera, ws.cell(total, 2), ultima):
        assert c.border.top.style == "medium" and c.border.top.color.rgb[-6:] == "000000"
        assert c.border.bottom.style == "medium"
    assert primera.border.left.style == "medium"   # el marco, a la izquierda
    assert ultima.border.right.style == "medium"   # y a la derecha
    # Las verticales de adentro se quedan finas y grises.
    assert ws.cell(total, 2).border.left.style == "thin"
    # ⚠️ Contra la PALETA, no contra un literal: los dos se escribian a mano y
    # al retocar la paleta quedaron dos grises casi iguales en la misma hoja.
    assert ws.cell(total, 2).border.left.color.rgb[-6:] == C["raya"]


def test_el_subtitulo_sigue_viajando_en_el_INDICE():
    """No se pierde: se mueve a donde se lee una vez. Un archivo de seis
    pestañas sin nada que diga de que version es cada una no se puede archivar."""
    wb, _ = _hoja([_cuadro(), {**_cuadro(), "hoja": "Otra", "titulo": "Otro"}])
    assert len(wb.sheetnames) >= 3, "no se genero la hoja indice"
    indice = wb[wb.sheetnames[0]]
    # ⚠️ Desde el 2026-09-30 la explicacion larga va como NOTA de la celda y no
    # como texto: en la celda convertia el indice en una pared de texto, y el
    # owner pidio una descripcion corta por hoja. Sigue estando.
    notas = [indice.cell(r, 3).comment.text
             for r in range(1, 12) if indice.cell(r, 3).comment]
    assert any(SUBTITULO[:30] in t for t in notas), \
        "el subtitulo se perdio: no esta en la hoja, ni en el indice, ni en su nota"


def test_el_INDICE_lleva_link_a_cada_hoja():
    """Un libro de dieciocho pestañas se recorre con el indice o no se recorre:
    las lenguetas van cortadas a 31 caracteres y hay que buscarlas una por una.

    ⚠️ El nombre va entre comillas simples en la referencia. Sin ellas, una hoja
    con espacios —«P&L Ago Consolidado»— rompe el link y Excel abre el archivo
    diciendo que no es valido.
    """
    wb, _ = _hoja([_cuadro(), {**_cuadro(), "hoja": "Otra", "titulo": "Otro"}])
    indice = wb[wb.sheetnames[0]]
    con_link = [indice.cell(r, 2) for r in range(1, 12)
                if indice.cell(r, 2).hyperlink]
    assert len(con_link) >= 2, "las hojas del indice no son links"
    assert all(c.hyperlink.location.startswith("'") for c in con_link)


# ═════════ Formulas de verdad, 2026-09-30 ════════════════════════════════════
#
# Owner, auditando el archivo: *«los subtotales, totales y variaciones deben ser
# formulas reales»*. Un Excel de junta se toca: alguien corrige un actual en una
# celda y espera que la variacion se mueva con el. Con el numero puesto no se
# mueve, y la hoja queda diciendo dos cosas distintas sin que nada avise.

def _con_var():
    return {
        "titulo": "Tres cortes", "hoja": "Tres cortes",
        "columnas": [
            {"label": "CUENTA", "formato": "texto"},
            {"label": "Ago · ACTUAL", "formato": "usd2"},
            {"label": "Ago · BUDGET", "formato": "usd2"},
            {"label": "Ago · Variance", "formato": "usd2", "resta": [1, 2]},
        ],
        "filas": [
            {"label": "Rooms", "valores": [100.0, 80.0, 20.0]},
            {"label": "F&B", "valores": [40.0, 30.0, 10.0]},
            {"label": "TOTAL", "es_total": True, "valores": [140.0, 110.0, 30.0],
             "suma_de": [0, 1]},
        ],
    }


def test_la_VARIACION_baja_como_formula():
    wb, ws = _hoja([_con_var()])
    # Las filas arrancan en la 5: titulo (1), subtitulo en blanco (2), (3),
    # cabecera (4).
    assert ws.cell(5, 4).value == "=B5-C5"
    assert ws.cell(6, 4).value == "=B6-C6"


def test_la_formula_apunta_a_las_columnas_QUE_SE_VEN():
    """`resta` son indices base 0 sobre `columnas`, y la columna 0 es el rotulo
    de la fila: [1, 2] es B menos C, no A menos B."""
    wb, ws = _hoja([_con_var()])
    assert ws.cell(5, 4).value.startswith("=B"), ws.cell(5, 4).value


def test_un_TOTAL_que_CUADRA_baja_como_suma():
    wb, ws = _hoja([_con_var()])
    assert ws.cell(7, 2).value == "=B5+B6"
    assert ws.cell(7, 3).value == "=C5+C6"


def test_un_TOTAL_que_NO_cuadra_se_queda_con_SU_NUMERO():
    """⚠️ Esto es lo que impide que el archivo diga algo que el sistema no dice.

    El total del P&L lo calcula el motor, no la pantalla. Si el cuadro no
    muestra todos sus componentes —o los muestra netos de un reparto—
    `=SUMA(...)` daria OTRA cifra, y nadie lo notaria porque una formula se ve
    mas confiable que un numero. Owner, 2026-09-30: *«el Consolidado NO debe
    cambiar de valor»*.
    """
    cu = _con_var()
    cu["filas"][2]["valores"] = [999.0, 110.0, 889.0]   # el motor dice 999
    wb, ws = _hoja([cu])
    assert ws.cell(7, 2).value == 999.0, "la formula piso el numero del motor"


def test_sin_resta_ni_suma_de_la_celda_sigue_siendo_EL_NUMERO():
    """La mayoria de los cuadros no declaran nada, y tienen que salir igual que
    siempre."""
    wb, ws = _hoja()
    assert isinstance(ws.cell(5, 2).value, (int, float))


def test_la_franja_de_estadisticas_NO_repite_los_rotulos_de_columna():
    """Owner, 2026-09-30: *«necesito que esto quede super alineado»*.

    ⚠️ Los repetia, y era justo lo que se veia torcido: el rotulo de una columna
    de tres cortes —«AGOSTO 2026 · ACTUAL Final»— es mas largo que la celda, y
    sin relleno detras Excel lo derrama sobre la vecina. En la hoja salia
    «O 2026ACTUAL Final»: dos rotulos pisados y corridos respecto de la cabecera
    de abajo. La cabecera de verdad esta dos filas mas abajo, en las MISMAS
    columnas.
    """
    cu = _con_var()
    cu["kpis_columnas"] = [c["label"] for c in cu["columnas"][1:]]
    cu["kpis"] = [{"label": "Noches vendidas", "valores": [202, 124, 78]}]
    wb, ws = _hoja([cu])
    franja = [ws.cell(4, i).value for i in range(2, 5)]
    assert franja == [None, None, None], f"la franja repite rotulos: {franja}"
    assert ws.cell(4, 1).value == "ESTADÍSTICAS"


def test_la_franja_cae_en_LAS_MISMAS_columnas_que_el_cuadro():
    """Cada estadistica encima de su corte y de su version, incluida la columna
    de variacion. Con una columna de menos por corte la franja se iba
    corriendo: el ADR del Budget del mes caia encima de la variacion."""
    cu = _con_var()
    cu["kpis_columnas"] = [c["label"] for c in cu["columnas"][1:]]
    cu["kpis"] = [{"label": "Noches vendidas", "valores": [202, 124, 78]}]
    wb, ws = _hoja([cu])
    assert [ws.cell(5, i).value for i in range(2, 5)] == [202, 124, 78]
    # Y la cabecera del cuadro, justo debajo, con las mismas tres columnas.
    assert [ws.cell(7, i).value for i in range(2, 5)] == [
        "Ago · ACTUAL", "Ago · BUDGET", "Ago · Variance"]


def _es_marco(celda) -> bool:
    """El recuadro del total: medio y NEGRO.

    ⚠️ «Medio» no alcanza para distinguirlo. El encabezado de seccion tambien
    lleva una raya media arriba, pero GRIS: es la que cierra el bloque anterior.
    Lo que separa un total de una seccion es el color.
    """
    b = celda.border
    return any(l and l.style == "medium" and (l.color.rgb or "")[-6:] == C["marco"]
               for l in (b.top, b.bottom, b.left, b.right))


def test_NINGUNA_fila_normal_lleva_el_recuadro_negro():
    """El otro lado de la regla del owner. Si una fila de detalle lleva marco,
    el recuadro deja de significar «aca cierra un bloque» y el ojo pierde la
    referencia — que es exactamente lo que pasaba cuando el encabezado de
    seccion compartia marcador con el total.
    """
    wb, ws = _hoja()
    filas_total = {r for r in range(1, 20)
                   if str(ws.cell(r, 1).value or "").upper().startswith("TOTAL")}
    for r in range(5, 12):
        if r in filas_total or not ws.cell(r, 1).value:
            continue
        for c in range(1, 4):
            assert not _es_marco(ws.cell(r, c)),                 f"la fila {r} ({ws.cell(r, 1).value}) lleva marco de total"


def test_la_SECCION_no_es_un_total():
    """Banda palida, negrita y una raya media GRIS arriba —la que cierra el
    bloque anterior—, pero SIN el recuadro negro: es el rotulo del bloque que
    empieza, no su cierre."""
    cu = _con_var()
    cu["filas"].insert(0, {"label": "REVENUES", "es_seccion": True,
                           "es_total": True, "valores": [None, None, None]})
    wb, ws = _hoja([cu])
    assert ws.cell(5, 1).value == "REVENUES"
    for c in range(1, 5):
        assert not _es_marco(ws.cell(5, c)), "la seccion salio con marco de total"
    assert ws.cell(5, 1).border.top.style == "medium"
    assert ws.cell(5, 1).border.top.color.rgb[-6:] == C["raya"]
    assert _relleno(ws.cell(5, 1)) == C["banda_seccion"]


# ═════════ La cabecera en dos lineas, 2026-09-30 ═════════════════════════════
#
# Owner, con una captura de como la quiere: *«esta vista se ve muy cargada y
# esta en la misma celda… podras ver que se usan 2 celdas cada una tiene su
# varianza. y ademas se identifica con una linea gruesa lo que es Agosto, YTD
# Agosto y Full Year»*.

def _dos_lineas():
    cu = _con_var()
    for c, sub, abre in zip(cu["columnas"][1:],
                            ["Agosto", "Agosto", ""], [True, False, False]):
        c["sub"] = sub
        if abre:
            c["abre_grupo"] = True
    cu["columnas"][1]["label"] = "Actual"
    cu["columnas"][2]["label"] = "Budget"
    cu["columnas"][3]["label"] = "Variance"
    return cu


def test_la_cabecera_va_en_DOS_filas():
    """Arriba la version, abajo el periodo. Antes iba todo junto dentro de una
    celda —«Agosto · ACTUAL Final»— partido en dos renglones que por separado no
    significan nada."""
    wb, ws = _hoja([_dos_lineas()])
    assert [ws.cell(4, i).value for i in range(1, 5)] == [
        "CUENTA", "Actual", "Budget", "Variance"]
    assert [ws.cell(5, i).value for i in range(2, 5)] == ["Agosto", "Agosto", None]
    # Y la tabla arranca una fila mas abajo.
    assert ws.cell(6, 1).value == "Rooms"


def test_sin_periodos_la_cabecera_NO_gana_una_fila_en_blanco():
    """⚠️ Un cuadro sin cortes —el mapeo de cuentas, los anexos— no tiene por
    que crecer una fila. Y hay macros de quien ya usa estos archivos que buscan
    la cabecera donde siempre estuvo."""
    wb, ws = _hoja()
    assert ws.cell(4, 1).value == "ACCOUNT DESCRIPTION"
    assert ws.cell(5, 1).value == "Rooms"


def test_la_raya_GRUESA_separa_los_bloques():
    """Sin ella, nueve columnas de montos son nueve columnas de montos: no se ve
    donde termina el mes y empieza el acumulado.

    ⚠️ Baja por TODAS las filas. Una raya que se corta debajo del encabezado no
    separa nada.
    """
    wb, ws = _hoja([_dos_lineas()])
    for fila in (4, 5, 6, 7):
        assert ws.cell(fila, 2).border.left.style == "medium", \
            f"la fila {fila} perdio la raya del bloque"
    # Y las columnas de adentro del bloque se quedan finas.
    assert ws.cell(6, 3).border.left.style == "thin"


def test_la_cabecera_es_CLARA_con_letra_oscura():
    """Owner: *«no se si ese azul funciona, podrias quizas bajarle el tono un
    poco para que se vea mas nitido»*.

    ⚠️ A 10 pt el blanco sobre color pierde definicion — es justo lo que se lee
    como «no se ve nitido». La referencia que mando es cabecera clara con el
    rotulo en azul y el periodo en negro.
    """
    wb, ws = _hoja([_dos_lineas()])
    assert _relleno(ws.cell(4, 2)) == C["cab_tabla"]
    assert ws.cell(4, 2).font.color.rgb[-6:] == C["cab_texto"]
    assert ws.cell(5, 2).font.color.rgb[-6:] == C["cab_sub"]
    # Claro de verdad: el relleno tiene que ser mas claro que la banda de total.
    assert C["cab_tabla"] > C["banda_total"]


def test_NINGUNA_hoja_baja_con_la_cuadricula_de_Excel():
    """Owner: *«quitar el grid de la vista de excel en todas las tabs»*.

    El cuadro ya trae sus propias rayas; encima la cuadricula del programa, que
    sigue hasta el borde de la pantalla, hace que la tabla no tenga fin.
    """
    wb, _ = _hoja([_dos_lineas(), {**_cuadro(), "hoja": "Otra", "titulo": "Otro"}])
    for nombre in wb.sheetnames:
        assert wb[nombre].sheet_view.showGridLines is False, \
            f"la hoja «{nombre}» baja con la cuadricula"


# ═════════ La formula tiene que VERSE, 2026-09-30 ════════════════════════════
#
# Owner, mirando el Excel bajado: *«no pusiste los calculos de las
# varianzas… actual menos Budget»* y *«los checkbooks no tienen subtotales ni
# totales, hay que volver a poner todo eso»*.
#
# Estaban. Como formula, y en blanco.

def _celda_cruda(blob: bytes, hoja: str, ref: str) -> str:
    import re
    import zipfile
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(blob))
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    libro = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    for h in libro.iter(f"{NS}sheet"):
        if h.get("name") == hoja:
            t = rels[h.get(f"{R}id")]
            xml = z.read("xl/" + t.lstrip("/").removeprefix("xl/")).decode()
            m = re.search(r'<c r="%s".*?</c>' % ref, xml, re.S)
            return m.group() if m else ""
    return ""


def test_la_formula_baja_CON_su_resultado():
    """⚠️ `openpyxl` escribe `<f>B5-C5</f><v></v>`: la formula, y un resultado
    VACIO. Excel deberia calcularlo al abrir —el libro sale con
    `fullCalcOnLoad`— pero si el usuario tiene el calculo en Manual, o lo abre
    en un visor que no evalua, la celda sale EN BLANCO.

    Le paso al owner con las varianzas del P&L y con los subtotales de los
    checkbooks: estaban, y no se veian. Un archivo de Excel de verdad guarda
    las dos cosas.
    """
    blob = build_cuadros_workbook([_con_var()])
    celda = _celda_cruda(blob, "Tres cortes", "D5")
    assert "<f>B5-C5</f>" in celda, celda
    assert "<v>20</v>" in celda, f"la formula bajo sin resultado: {celda}"


def test_el_SUBTOTAL_tambien_baja_con_su_resultado():
    blob = build_cuadros_workbook([_con_var()])
    celda = _celda_cruda(blob, "Tres cortes", "B7")
    assert "<f>B5+B6</f>" in celda, celda
    assert "<v>140</v>" in celda, f"el subtotal bajo sin resultado: {celda}"


def test_si_la_inyeccion_falla_el_libro_sale_IGUAL():
    """⚠️ Un archivo con las formulas sin resultado se arregla con F9; uno
    corrupto no se abre. El camino de escape devuelve el libro tal cual."""
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app/export/cuadro_excel.py").read_text(encoding="utf-8")
    cuerpo = src[src.index("def _con_resultados("):src.index("def build_cuadros_workbook(")]
    assert "except Exception:" in cuerpo and "return blob" in cuerpo


def test_un_libro_NO_arrastra_las_formulas_del_anterior():
    """El diccionario es de modulo: sin limpiarlo, el segundo libro escribiria
    resultados de celdas del primero."""
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app/export/cuadro_excel.py").read_text(encoding="utf-8")
    assert "_VALORES_DE_FORMULA.clear()" in src
