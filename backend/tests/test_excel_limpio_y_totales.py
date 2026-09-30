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
    return wb, wb[[n for n in wb.sheetnames if "Full" in n][0]]


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
    assert ws.cell(total, 2).border.left.color.rgb[-6:] == "CBD5E0"


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
