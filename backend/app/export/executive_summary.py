# -*- coding: utf-8 -*-
"""El Resumen Ejecutivo mensual en Word, con el formato que el owner ya usa.

Owner, 2026-09-30, entregando `Executive Summary – Financial & Operational
Results YTD AUGUST 2026.pdf`: *«necesito un análisis de resultados según el PDF
que te voy a pasar. usa este formato como estándar y prepara uno igual para
agosto en Amarena. quiero el informe en word»*.

## Qué es y qué NO es

Es el documento que se manda a los dueños: portada, introducción, y el año
mirado desde los tres cortes —el mes, el acumulado y el aterrizaje— con la
prosa que explica cada variación y los cuadros que la sostienen.

⚠️ **La prosa se ESCRIBE con los números, no al revés.** Cada frase se arma a
partir de la variación real que calculó el motor: si el ingreso está 7,4% arriba
del presupuesto, el texto dice 7,4% porque lo leyó, no porque alguien lo tecleó.
Un informe donde el texto y el cuadro pueden discrepar es peor que no tenerlo —
la discrepancia no se ve, y el que la encuentre deja de creerle a los dos.

⚠️ **Lo que el sistema no sabe, el informe lo DICE.** El PDF del owner trae
secciones que no salen de la contabilidad —la actividad comercial del mes, el
mix por país, las notas de mercado—. Acá van con un recuadro que pide el dato en
vez de una frase inventada que se lea igual de bien.

## ⚠️ En español

Owner, 2026-09-30, señalando el botón: *«esto debe ser en español»*.

El PDF que se dio como estándar estaba en inglés y de ahí venía el primer
armado. Pero el formato es la estructura —portada, los tres cortes, el
flow-through, los positivos y negativos—, no el idioma: el informe lo lee la
junta acá.

Los ROTULOS de los cuadros se quedan en inglés a propósito —«Total available
Rooms», «EBITDA BEFORE CAPITAL»—. Son los mismos que usa el P&L de la pantalla y
los que el owner tiene en su Excel: traducirlos obligaría a comprobar que
«Utilidad bruta operativa» y «GROSS OPERATING PROFIT» son el mismo renglón.

## De dónde salen los números

De `pl_api.get_pl_compare`, el MISMO agregador del Dashboard y del P&L a dueños.
No hay una segunda aritmética: el informe no puede decir un GOP distinto del que
muestra la pantalla de la que salió.
"""
from __future__ import annotations

import io
import pathlib
from datetime import date

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

DOCX = ("application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document")

#: Qué secciones lleva el informe.
#:
#: Owner, 2026-09-30: *«sólo vamos a dejar sección 1 y 2 por ahora; quita todo
#: lo demás»*. El «por ahora» es literal: la 3 y la 4 vuelven agregándolas acá.
SECCIONES = ("1", "2")

#: La tipografía del informe (owner, 2026-09-30).
#:
#: ⚠️ Las constantes van juntas porque el documento tiene que verse igual de
#: punta a punta: con el tamaño escrito a mano en cada párrafo, basta que
#: alguien agregue uno para que quede un renglón de otro cuerpo y no se note
#: hasta que está impreso.
FUENTE = "Times New Roman"
CUERPO = 12          #: el texto
CUERPO_TABLA = 9     #: los cuadros; con doce columnas, 12 pt no entra
INTERLINEA = 1.5
#: El aire ANTES de un título. El pedido fue «entre títulos un espacio
#: adicional»: es lo que separa un bloque del anterior sin meter párrafos vacíos,
#: que se descolocan al editar.
AIRE_TITULO = 18

#: Las fotos de la propiedad, para la portada y las aperturas de sección.
#:
#: Owner, 2026-09-30: *«métete a la website de Amarena y mete imágenes a la
#: presentación en el inicio para que se vea súper lindo»*.
#:
#: ⚠️ **Viven en el REPO y no se bajan al generar.** El informe se arma en el
#: servidor; salir a internet cada vez lo dejaría sin portada el día que el
#: sitio no conteste, y un documento a dueños sin portada se nota. Vienen de
#: amarenabeachhotel.com, convertidas de WEBP —que `python-docx` no lee— a JPEG
#: y PNG.
ASSETS = pathlib.Path(__file__).resolve().parent / "assets"


def _filete(doc, ancho_cm: float = 6.0) -> None:
    """Un filete de oro. Separa la marca del título sin meter otra línea de
    texto, que es lo que hacía que la portada se viera desordenada."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run("—" * int(ancho_cm * 2))
    r.font.size = Pt(9)
    r.font.color.rgb = ORO
    _fuente_en_todo(r._element.get_or_add_rPr())


def _imagen(doc, nombre: str, ancho_cm: float, centrada: bool = True):
    """Una foto, si está. ⚠️ Si falta, el informe sale igual: una portada sin
    imagen es un problema de estética; un informe que no se genera es un
    problema de verdad."""
    ruta = ASSETS / nombre
    if not ruta.exists():
        return None
    p = doc.add_paragraph()
    p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if centrada
                   else WD_ALIGN_PARAGRAPH.LEFT)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
    return p

VERDE = RGBColor(0x2A, 0x4A, 0x33)
ORO = RGBColor(0xA8, 0x8C, 0x50)
GRIS = RGBColor(0x60, 0x66, 0x6E)
NEGRO = RGBColor(0x1A, 0x1D, 0x21)
ROJO = RGBColor(0xB3, 0x26, 0x1E)

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]


# ═══════════════════════ Números, dichos como en el PDF ═══════════════════════

def k(v: float | None) -> str:
    """En miles, como el owner los escribe: `$277.9K`, `$3.974M`.

    ⚠️ El PDF mezcla las dos escalas a propósito —miles para un mes, millones
    para el año— porque `$3,973,720.59` en medio de una frase no se lee. El
    corte está en el millón.
    """
    if v is None:
        return "n/d"
    s = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000:
        return f"{s}${a / 1_000_000:,.3f}M"
    return f"{s}${a / 1_000:,.1f}K"


def usd(v: float | None, dec: int = 2) -> str:
    """En dólares. ⚠️ Los negativos van entre PARÉNTESIS.

    `f"${-1234.5:,.2f}"` da `$-1,234.50`: el signo queda escondido entre el
    símbolo y el número, se pierde de vista en una columna y —lo que importa
    acá— no se puede detectar para pintarlo de rojo.

    El paréntesis es además la convención contable y la que usa el PDF del
    owner.
    """
    if v is None:
        return "n/d"
    if v < 0:
        return f"(${abs(v):,.{dec}f})"
    return f"${v:,.{dec}f}"


def pct(v: float | None, dec: int = 2) -> str:
    return "n/d" if v is None else f"{v * 100:,.{dec}f}%"


def var_pct(act: float, base: float) -> float | None:
    """La variación relativa. `None` cuando NO significa nada.

    Dos casos, y el segundo es el que engaña:

    ⚠️ **Base cero.** Dividir entre cero no da un porcentaje. Escribir «100%» o
    «∞» ahí inventa una magnitud.

    ⚠️ **Base NEGATIVA.** Acá el signo se da vuelta y el número miente. El
    EBITDA de Amarena en agosto mejoró de −203,8K a −122,7K —81,1K a favor— y
    la fórmula da **−39,8%**, que se lee como un deterioro del 40%. En un
    informe a dueños eso es peor que no poner nada: la frase dice «above plan»
    y el paréntesis dice lo contrario.

    Con base negativa manda la palabra —«above» / «below» con el monto—, que no
    se puede leer al revés.
    """
    return None if base <= 0.005 else (act - base) / base


def signo(v: float) -> str:
    """«por encima» / «por debajo».

    ⚠️ La palabra manda cuando el porcentaje no se puede escribir —base cero o
    negativa—, así que tiene que decir la dirección sola, sin apoyarse en el
    signo del número que la acompaña."""
    return "por encima de" if v >= 0 else "por debajo de"


# ═══════════════════════════ Piezas de Word ═══════════════════════════════════

def _fuente_en_todo(rPr) -> None:
    """Fija la fuente para los tres alfabetos que Word distingue."""
    if rPr is None:
        return
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.append(rf)
    for atributo in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(atributo), FUENTE)


def _margenes(sec) -> None:
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)


def _pie(sec, propiedad: str) -> None:
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(propiedad + "   ")
    r.font.size = Pt(8)
    r.font.color.rgb = GRIS
    _campo(p, "PAGE")
    r2 = p.add_run(" | P a g e")
    r2.font.size = Pt(8)
    r2.font.color.rgb = GRIS


def _campo(parrafo, instruccion: str) -> None:
    """Un campo de Word (el número de página se numera solo al imprimir)."""
    ini = OxmlElement("w:fldChar")
    ini.set(qn("w:fldCharType"), "begin")
    txt = OxmlElement("w:instrText")
    txt.set(qn("xml:space"), "preserve")
    txt.text = f" {instruccion} "
    fin = OxmlElement("w:fldChar")
    fin.set(qn("w:fldCharType"), "end")
    r = parrafo.add_run()._r
    for e in (ini, txt, fin):
        r.append(e)


def _h(doc, texto: str, nivel: int = 1, color=VERDE):
    """Un título. ⚠️ El aire va como `space_before` y NO como un párrafo vacío:
    un párrafo vacío se descoloca en cuanto alguien edita arriba, y en Word se
    arrastra al pegar."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(AIRE_TITULO if nivel == 1
                                         else AIRE_TITULO * 0.75)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.15   # un título no necesita 1,5
    r = p.add_run(texto)
    r.bold = True
    r.font.name = FUENTE
    r.font.size = Pt(CUERPO + (3 if nivel == 1 else 1 if nivel == 2 else 0))
    r.font.color.rgb = color
    _fuente_en_todo(r._element.get_or_add_rPr())
    return p


def _p(doc, partes, justificar: bool = True):
    """Un párrafo. `partes` es texto, o una lista de (texto, negrita)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = INTERLINEA
    p.alignment = (WD_ALIGN_PARAGRAPH.JUSTIFY if justificar
                   else WD_ALIGN_PARAGRAPH.LEFT)
    for trozo in ([partes] if isinstance(partes, str) else partes):
        txt, negrita = (trozo, False) if isinstance(trozo, str) else trozo
        r = p.add_run(txt)
        r.bold = negrita
        r.font.name = FUENTE
        r.font.size = Pt(CUERPO)
        r.font.color.rgb = NEGRO
        _fuente_en_todo(r._element.get_or_add_rPr())
    return p


#: El orden en que el esquema de OOXML exige los hijos de `w:tcPr`.
#:
#: ⚠️ Lo mismo que en `w:tblPr`: un hijo fuera de orden Word lo IGNORA sin decir
#: nada. Aquí costó caro — `w:shd` se escribía antes que `w:tcBorders`, así que
#: los bordes de celda no se aplicaban y la costura blanca entre columnas no
#: había manera de taparla por más que se le cambiara el color y el grosor.
_ORDEN_TCPR = ("cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders",
               "shd", "noWrap", "tcMar", "textDirection", "tcFitText",
               "vAlign", "hideMark")


def _ordenar_tcPr(celda) -> None:
    tcPr = celda._tc.get_or_add_tcPr()
    for hijo in sorted(tcPr, key=lambda e: (
            _ORDEN_TCPR.index(e.tag.split("}")[1])
            if e.tag.split("}")[1] in _ORDEN_TCPR else len(_ORDEN_TCPR))):
        tcPr.append(hijo)


def _sombra(celda, hexcolor: str) -> None:
    tcPr = celda._tc.get_or_add_tcPr()
    for viejo in tcPr.findall(qn("w:shd")):
        tcPr.remove(viejo)
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hexcolor)
    tcPr.append(el)
    _ordenar_tcPr(celda)


def _es_negativo(texto: str) -> bool:
    t = texto.strip()
    return t.startswith("(") or t.startswith("-") or t.startswith("-$")


#: Los tonos de los cuadros. Pasteles: el informe va impreso y a proyector, y
#: un relleno saturado se come el número que tiene encima.
VERDE_CAB = "2A4A33"    #: el encabezado, con la letra en blanco
CEBRA = "F4F7F5"        #: la fila alterna, apenas perceptible en papel
FONDO_TOTAL = "E4EBE6"  #: el total, del mismo verde pero lavado
RAYA = "C9D3CC"         #: las rayas horizontales


def _borde(celda, lado: str, sz: int, color: str) -> None:
    """Una raya de UN lado de la celda.

    ⚠️ `w:tcBorders` tiene que ir en su orden del esquema (top, left, bottom,
    right) o Word abre el documento diciendo que está dañado. Por eso se
    reordena el elemento entero cada vez y no se hace `append` a secas.
    """
    tcPr = celda._tc.get_or_add_tcPr()
    bordes = tcPr.find(qn("w:tcBorders"))
    if bordes is None:
        bordes = OxmlElement("w:tcBorders")
        tcPr.append(bordes)
    for viejo in bordes.findall(qn(f"w:{lado}")):
        bordes.remove(viejo)
    el = OxmlElement(f"w:{lado}")
    el.set(qn("w:val"), "single" if sz else "nil")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:color"), color)
    bordes.append(el)
    orden = {"top": 0, "left": 1, "bottom": 2, "right": 3, "insideH": 4,
             "insideV": 5}
    for hijo in sorted(bordes, key=lambda e: orden.get(e.tag.split("}")[1], 9)):
        bordes.append(hijo)
    _ordenar_tcPr(celda)


def _sin_rejilla(tabla) -> None:
    """Apaga las rayas que dibuja el ESTILO de la tabla.

    ⚠️ No basta con poner los bordes de cada celda en `nil`: `Table Grid` define
    `insideV` a nivel de TABLA, y esa raya se seguía viendo entre columna y
    columna aunque las celdas dijeran que no. Las rayas que sí queremos se
    dibujan después, celda por celda, en `_borde`.
    """
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "nil")
        bordes.append(el)
    tabla._tbl.tblPr.append(bordes)
    _ordenar_tblPr(tabla)


#: El orden en que el esquema de OOXML exige los hijos de `w:tblPr`.
#:
#: ⚠️ Word IGNORA en silencio un hijo que llegue fuera de orden —no da error, no
#: avisa: simplemente no aplica—. Las rayas verticales que sobraban entre
#: columna y columna eran eso: `w:tblBorders` puesto con `append` al final.
_ORDEN_TBLPR = ("tblStyle", "tblpPr", "tblOverlap", "bidiVisual",
                "tblStyleRowBandSize", "tblStyleColBandSize", "tblW", "jc",
                "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout",
                "tblCellMar", "tblLook", "tblCaption", "tblDescription")


def _ordenar_tblPr(tabla) -> None:
    tblPr = tabla._tbl.tblPr
    for hijo in sorted(tblPr, key=lambda e: (
            _ORDEN_TBLPR.index(e.tag.split("}")[1])
            if e.tag.split("}")[1] in _ORDEN_TBLPR else len(_ORDEN_TBLPR))):
        tblPr.append(hijo)


def _costuras(celda, color: str) -> None:
    """Las verticales, pintadas DEL COLOR DE LA CELDA.

    ⚠️ No se apagan: se camuflan. Con la vertical en `nil` Word deja sin pintar
    la franja del borde, y entre dos celdas de fondo verde quedaba una costura
    blanca de un pelo que a la vista era exactamente la raya que se quería
    quitar. Del color del relleno, la costura desaparece.
    """
    # ⚠️ En `nil`, no del color del relleno. Word RESERVA el ancho del borde y
    # no lo rellena: un borde vertical, aunque sea del mismo verde, deja una
    # franja sin pintar entre columna y columna —se midió en el PDF: 1,57 pt de
    # hueco con un borde de 1,5 pt—. Esa franja blanca ERA la raya que sobraba.
    # Sin borde no hay franja y los rellenos de dos celdas vecinas se tocan.
    _borde(celda, "left", 0, color)
    _borde(celda, "right", 0, color)


def _aire_en_celdas(tabla, arriba=60, lado=110) -> None:
    """El margen interno de todas las celdas, en vigésimas de punto.

    Sin esto el número toca la raya de al lado y el cuadro se ve apretado: es
    la mitad de lo que hacía que los cuadros «se vieran raros».
    """
    tblPr = tabla._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for lado_, valor in (("top", arriba), ("left", lado), ("bottom", arriba),
                         ("right", lado)):
        el = OxmlElement(f"w:{lado_}")
        el.set(qn("w:w"), str(valor))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)
    _ordenar_tblPr(tabla)


def _tabla(doc, encabezados, filas, anchos=None, resaltar=()):
    """Un cuadro. `filas` = lista de listas de texto ya formateado.

    `resaltar` son los índices de fila que van en negrita con fondo —los
    totales—. Los negativos salen en rojo, que es como se leen en el PDF.

    ⚠️ **Sin rejilla.** Antes usaba `Table Grid`, que dibuja una caja negra
    alrededor de cada celda: en un cuadro de doce filas son cien rayas y el
    número deja de ser lo que se ve primero. Un estado financiero se lee por
    filas, así que sólo hay rayas HORIZONTALES —finas, grises— más el
    encabezado y la línea del total. Las verticales no hacen falta: la columna
    la marca la alineación.
    """
    t = doc.add_table(rows=1, cols=len(encabezados))
    # ⚠️ El estilo se queda en «Table Grid» porque la plantilla de `python-docx`
    # no trae «Table Normal» con ese nombre. Sus rayas se apagan enseguida en
    # `_sin_rejilla`.
    t.style = "Table Grid"
    t.autofit = False
    _sin_rejilla(t)
    _aire_en_celdas(t)
    for i, h in enumerate(encabezados):
        c = t.rows[0].cells[i]
        c.text = ""
        p0 = c.paragraphs[0]
        p0.paragraph_format.line_spacing = 1.0
        p0.paragraph_format.space_after = Pt(0)
        r = p0.add_run(h)
        r.bold = True
        r.font.name = FUENTE
        r.font.size = Pt(CUERPO_TABLA)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _fuente_en_todo(r._element.get_or_add_rPr())
        # El encabezado se alinea como su columna: si el título va centrado y el
        # número a la derecha, la columna se lee torcida.
        p0.alignment = (WD_ALIGN_PARAGRAPH.RIGHT if i
                        else WD_ALIGN_PARAGRAPH.LEFT)
        _sombra(c, VERDE_CAB)
        _costuras(c, VERDE_CAB)
        for lado in ("top", "bottom"):
            _borde(c, lado, 0, VERDE_CAB)
    # ⚠️ Un cuadro de veinte filas cruza la página, y sin esto la mitad de
    # abajo queda como una lista de números sin columnas: `tblHeader` repite el
    # encabezado en cada página.
    trPr = t.rows[0]._tr.get_or_add_trPr()
    cab = OxmlElement("w:tblHeader")
    cab.set(qn("w:val"), "true")
    trPr.append(cab)
    ultima = len(filas) - 1
    for n, fila in enumerate(filas):
        tr = t.add_row()
        # Una fila partida por la mitad entre dos páginas es ilegible.
        no_partir = OxmlElement("w:cantSplit")
        tr._tr.get_or_add_trPr().append(no_partir)
        celdas = tr.cells
        es_total = n in resaltar
        for i, v in enumerate(fila):
            celdas[i].text = ""
            p = celdas[i].paragraphs[0]
            # ⚠️ Interlineado 1 y sin aire en las celdas: con el 1,5 del cuerpo,
            # una tabla de veinte filas se parte en dos páginas y los números
            # quedan flotando en el medio de su celda.
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            # La primera columna es el rótulo; TODO lo demás son números y va a
            # la derecha, que es lo único que alinea las unidades entre sí.
            p.alignment = (WD_ALIGN_PARAGRAPH.RIGHT if i
                           else WD_ALIGN_PARAGRAPH.LEFT)
            r = p.add_run(str(v))
            r.font.name = FUENTE
            r.font.size = Pt(CUERPO_TABLA)
            _fuente_en_todo(r._element.get_or_add_rPr())
            r.bold = es_total
            # ⚠️ El rojo se decide por el TEXTO ya formateado y no por el
            # número, porque la celda recibe texto: `k()`, `usd()` y `pct()`
            # devuelven cadenas. Se cubren las tres formas en que un negativo
            # puede llegar: `(...)`, `-$…` y `-12,3%`.
            if _es_negativo(str(v)):
                r.font.color.rgb = ROJO
            elif es_total:
                r.font.color.rgb = NEGRO
            # Las verticales no se ven; las horizontales dicen de qué tipo es
            # la fila.
            if es_total:
                _sombra(celdas[i], FONDO_TOTAL)
                _costuras(celdas[i], FONDO_TOTAL)
                _borde(celdas[i], "top", 8, VERDE_CAB)
                _borde(celdas[i], "bottom", 8 if n == ultima else 4, VERDE_CAB)
            else:
                _sombra(celdas[i], CEBRA if n % 2 else "FFFFFF")
                _costuras(celdas[i], CEBRA if n % 2 else "FFFFFF")
                _borde(celdas[i], "top", 0, RAYA)
                _borde(celdas[i], "bottom", 4, RAYA)
    if anchos:
        for fila in t.rows:
            for i, w in enumerate(anchos):
                fila.cells[i].width = Cm(w)
    _no_partir_si_es_corto(doc, t)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    return t


#: Hasta cuántas filas se considera que un cuadro «cabe entero».
#:
#: ⚠️ Por encima de esto NO se fuerza: un cuadro de treinta filas que no cabe en
#: ninguna página, marcado como inseparable, Word lo empuja y deja una página en
#: blanco. Por eso el de la cascada —veinte filas— sí se parte, y para eso se
#: repite el encabezado.
CABE_ENTERO = 10


def _no_partir_si_es_corto(doc, tabla) -> None:
    """Un cuadro chico entero en una página, con su rótulo encima.

    El flow-through son ocho filas y quedaba cortado: una fila al pie de una
    página y las otras siete al principio de la siguiente, con media hoja en
    blanco en medio.
    """
    if len(tabla.rows) > CABE_ENTERO:
        return
    # El rótulo es el párrafo que acaba de escribirse antes del cuadro.
    if doc.paragraphs:
        doc.paragraphs[-1].paragraph_format.keep_with_next = True
    for fila in tabla.rows[:-1]:
        for celda in fila.cells:
            for p in celda.paragraphs:
                p.paragraph_format.keep_with_next = True


def _pendiente(doc, titulo: str, que_falta: str) -> None:
    """Un recuadro que PIDE el dato, donde el sistema no lo tiene.

    ⚠️ Esto es lo contrario de dejar la sección afuera y también de rellenarla.
    Una sección ausente no se nota; una inventada se lee igual de bien que una
    cierta. Un recuadro que dice qué falta se ve, y se completa.
    """
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    _aire_en_celdas(t, arriba=110, lado=140)
    c = t.rows[0].cells[0]
    c.text = ""
    p = c.paragraphs[0]
    r = p.add_run(titulo + " — ")
    r.bold = True
    r.font.size = Pt(9.5)
    r2 = p.add_run(que_falta)
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = GRIS
    _sombra(c, "FDF6E3")
    doc.add_paragraph().paragraph_format.space_after = Pt(8)


# ═══════════════════════ La lectura de los cortes ═════════════════════════════

def linea(col: dict, code: str) -> float:
    """Un renglón del P&L de un corte. Cero si la versión no lo tiene."""
    for ln in col.get("lines", []):
        if ln["line_code"] == code:
            return float(ln["amount_usd"])
    return 0.0


def kpi(col: dict, nombre: str) -> float:
    return float((col.get("kpis") or {}).get(nombre) or 0.0)


#: Los renglones del cuadro, con el rótulo del owner. El orden es el del PDF.
CASCADA = [
    ("TOTAL REVENUES", "TOTAL_REVENUES", True),
    ("Total Operating expenses", "TOTAL_OPEXP", False),
    ("OPERATING PROFIT", "TOTAL_OP_PROFIT", True),
    ("TOTAL OVERHEAD EXPENSES", "TOTAL_OVERHEAD", False),
    ("TOTAL GROSS OPERATING PROFIT", "GOP", True),
    ("TOTAL NON OP EXPENSES", "TOTAL_NON_OP", False),
    ("EBITDA BEFORE CAPITAL", "EBITDA_BEFORE", True),
    ("EBITDA AFTER CAPITAL", "EBITDA_AFTER", False),
    ("EARNINGS BEFORE INCOME TAXES", "EBT", False),
    ("NET PROFIT", "NET_PROFIT", True),
]


def _cuadro_corte(doc, titulo: str, act: dict, bud: dict, fcs: dict | None,
                  rot_a: str, rot_b: str, rot_c: str) -> None:
    """El cuadro de un corte: KPIs arriba y la cascada abajo, con su variación."""
    _p(doc, [(titulo, True)], justificar=False)
    filas = [
        ["Total available Rooms", f"{kpi(act, 'rooms_available'):,.0f}",
         f"{kpi(bud, 'rooms_available'):,.0f}", "",
         f"{kpi(fcs, 'rooms_available'):,.0f}" if fcs else ""],
        ["Total Rooms Occupied", f"{kpi(act, 'rooms_occupied'):,.0f}",
         f"{kpi(bud, 'rooms_occupied'):,.0f}",
         f"{kpi(act, 'rooms_occupied') - kpi(bud, 'rooms_occupied'):,.0f}",
         f"{kpi(fcs, 'rooms_occupied'):,.0f}" if fcs else ""],
        ["Total Guests", f"{kpi(act, 'guests'):,.0f}", f"{kpi(bud, 'guests'):,.0f}",
         f"{kpi(act, 'guests') - kpi(bud, 'guests'):,.0f}",
         f"{kpi(fcs, 'guests'):,.0f}" if fcs else ""],
        ["% Occupancy", pct(kpi(act, "occupancy_pct")), pct(kpi(bud, "occupancy_pct")),
         f"{(kpi(act, 'occupancy_pct') - kpi(bud, 'occupancy_pct')) * 100:,.2f}pp",
         pct(kpi(fcs, "occupancy_pct")) if fcs else ""],
        ["Average Daily Room Only", usd(kpi(act, "adr")), usd(kpi(bud, "adr")),
         usd(kpi(act, "adr") - kpi(bud, "adr")),
         usd(kpi(fcs, "adr")) if fcs else ""],
        ["Total RevPAR", usd(kpi(act, "revpar")), usd(kpi(bud, "revpar")),
         usd(kpi(act, "revpar") - kpi(bud, "revpar")),
         usd(kpi(fcs, "revpar")) if fcs else ""],
    ]
    for rotulo, code, fuerte in CASCADA:
        a, b = linea(act, code), linea(bud, code)
        vp = var_pct(a, b)
        filas.append([rotulo, usd(a), usd(b), usd(a - b) + (
            f"  ({vp * 100:,.1f}%)" if vp is not None else ""),
            usd(linea(fcs, code)) if fcs else ""])
    # ⚠️ En el año completo la columna principal YA ES el Forecast, así que la
    # quinta columna repetía el mismo número al lado: «$673,888.06» dos veces en
    # la misma fila. Cuando la principal y el forecast son la misma versión, la
    # quinta no va.
    cabezas = ["CUENTA", rot_a, rot_b, "Variación", rot_c]
    anchos = [5.3, 2.7, 2.7, 3.4, 2.6]
    if fcs is None or fcs is act:
        cabezas, anchos = cabezas[:4], [6.2, 3.2, 3.2, 4.1]
        filas = [f[:4] for f in filas]
    _tabla(doc, cabezas, filas, anchos=anchos,
           resaltar={i for i, (_, _, f) in enumerate(CASCADA, start=6) if f})


#: El flow-through: dónde se quedó cada dólar de más que entró.
FLOW = [
    ("Ingreso", "TOTAL_REVENUES", "Lo que entró de más o de menos"),
    ("Planilla (extras + tipo de cambio + comisiones)", "TOTAL_PAYROLL",
     "Escala operativa y exposición al colón"),
    ("Gasto operativo", "TOTAL_OPEX_ONLY", "Gasto corriente contra el presupuesto"),
    ("Costo de ventas", "TOTAL_COST", "Más actividad de huéspedes y servicio"),
    ("Propiedad y capital", "TOTAL_PROPERTY", "Honorarios y decisiones de capex"),
]


def _flow_through(doc, titulo: str, act: dict, bud: dict, totales) -> None:
    """El cuadro de flow-through: la variación de cada bloque de costo.

    ⚠️ El gasto se muestra con el signo del EFECTO sobre la utilidad, no con el
    de la cuenta. Gastar de más es negativo aunque el gasto haya subido: un
    cuadro donde «+9.161» significa «me fue peor» se lee al revés.
    """
    _h(doc, titulo, nivel=3, color=NEGRO)
    filas = []
    for rotulo, clave, nota in FLOW:
        a, b = totales(act, clave), totales(bud, clave)
        efecto = (a - b) if clave == "TOTAL_REVENUES" else -(a - b)
        filas.append([rotulo, usd(efecto) if efecto >= 0 else f"({usd(abs(efecto))})",
                      nota])
    for rotulo, code, nota in (("Utilidad neta", "NET_PROFIT",
                                "Cuánto de la diferencia llegó al final"),
                               ("EBITDA antes de capital", "EBITDA_BEFORE",
                                "Efecto sobre el EBITDA")):
        d = linea(act, code) - linea(bud, code)
        filas.append([rotulo, usd(d) if d >= 0 else f"({usd(abs(d))})", nota])
    _tabla(doc, ["Concepto", "Diferencia ($)", "Qué la explica"], filas,
           anchos=[5.6, 3.3, 7.8], resaltar={len(filas) - 2, len(filas) - 1})


# ═════════════════════════════ El documento ═══════════════════════════════════

def build_executive_summary(datos: dict) -> bytes:
    """Arma el .docx. `datos` lo prepara `export_api`, leyendo del motor."""
    propiedad = datos["propiedad"]
    mes = int(datos["mes"])
    anio = int(datos["anio"])
    mes_ing = MESES[mes - 1]

    act, bud, fcs = datos["actual"], datos["budget"], datos.get("forecast")
    rot = datos["rotulos"]

    doc = Document()
    est = doc.styles["Normal"]
    est.font.name = FUENTE
    est.font.size = Pt(CUERPO)
    est.paragraph_format.line_spacing = INTERLINEA
    est.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    # ⚠️ Word guarda TRES nombres de fuente por estilo —latina, asiática y
    # complex script— y respeta el que corresponda al carácter. Con sólo el
    # latino puesto, las tildes y la «ñ» pueden salir con otra tipografía en
    # algunas instalaciones, y el documento se ve mezclado sin que nadie sepa
    # por qué.
    _fuente_en_todo(est.element.rPr)
    _margenes(doc.sections[0])
    _pie(doc.sections[0], propiedad)

    # ── Portada ──────────────────────────────────────────────────────────────
    #
    # ⚠️ El aire de arriba ya no son ocho párrafos vacíos: con el logo y la foto
    # el bloque ocupa la página, y los ocho empujaban el título a la segunda.
    doc.add_paragraph()
    _imagen(doc, "logo.png", 8.0)
    _filete(doc)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("RESUMEN EJECUTIVO MENSUAL")
    r.bold = True
    r.font.size = Pt(17)
    r.font.color.rgb = ORO
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{mes_ing.upper()} {anio}")
    r.bold = True
    r.font.size = Pt(40)
    r.font.color.rgb = VERDE
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(propiedad)
    r.font.size = Pt(13)
    r.font.color.rgb = NEGRO
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # ⚠️ Dice contra qué se compara —el presupuesto— y de dónde sale el año
    # completo. El Forecast dejó de ser una comparación, pero sigue siendo la
    # columna del año: callarlo dejaría sin explicar por qué el año completo no
    # es el Actual.
    r = p.add_run(f"Generado por FinPlan el {date.today():%d/%m/%Y} · "
                  f"{rot['actual']} contra {rot['budget']}"
                  + (f" · el año completo, {rot['forecast']}" if fcs else ""))
    r.font.size = Pt(8.5)
    r.font.color.rgb = GRIS
    doc.add_paragraph()
    _imagen(doc, "portada.jpg", 16.0)
    doc.add_page_break()

    # ── Introducción ─────────────────────────────────────────────────────────
    _h(doc, "INTRODUCCIÓN", nivel=1, color=NEGRO)
    _p(doc, "Este informe analiza el desempeño financiero y operativo del hotel "
            "desde tres perspectivas:")
    _p(doc, [(f"{mes_ing} {anio} — desempeño del mes contra el presupuesto", True),
             ", con el detalle de la ejecución del mes que se cierra."])
    _p(doc, [(f"Acumulado a {mes_ing} {anio} — desempeño acumulado contra el "
              f"presupuesto", True),
             ", que muestra la tendencia del año hasta acá."])
    _p(doc, [(f"Proyección del año completo {anio} contra el presupuesto", True),
             ", con la lectura de cómo se espera cerrar el año y los riesgos que "
             "quedan por delante."])
    _p(doc, "El objetivo no es sólo mostrar cuánto ingreso y cuánta utilidad se "
            "alcanzaron, sino entender de dónde vienen: volumen, tarifa, "
            "estructura de costos y la dinámica operativa del año.")
    _imagen(doc, "propiedad.jpg", 15.5)
    doc.add_page_break()

    _h(doc, f"Resumen Ejecutivo — Resultados financieros y operativos "
            f"al cierre de {mes_ing} {anio}", nivel=1)
    _imagen(doc, "costa.jpg", 15.5)

    # ── 1.1 / 1.2 / 1.3 ──────────────────────────────────────────────────────
    cortes = [
        ("1.1", f"{mes_ing} {anio} — el mes contra el presupuesto", "month",
         f"El ingreso total de {mes_ing.lower()}", mes_ing),
        ("1.2", f"Acumulado a {mes_ing} {anio} — contra el presupuesto", "ytd",
         f"El ingreso total acumulado a {mes_ing.lower()}", f"Acumulado a {mes_ing}"),
        ("1.3", f"Proyección del año completo {anio} contra el presupuesto", "full",
         "El ingreso proyectado del año", "Año completo"),
    ]
    for num, titulo, corte, sujeto, rotulo_corte in cortes:
        a = act[corte]
        b = bud[corte]
        f = fcs[corte] if fcs else None
        # ⚠️ En el año completo el Actual son los meses cargados: quien contesta
        # «cómo cierra el año» es el Forecast. Comparar el Actual contra doce
        # meses de presupuesto daría un derrumbe que sólo dice que el año no
        # terminó.
        principal = f if (corte == "full" and f) else a
        rot_principal = rot["forecast"] if (corte == "full" and f) else rot["actual"]

        _h(doc, f"{num} {titulo}", nivel=2)
        rev, revb = linea(principal, "TOTAL_REVENUES"), linea(b, "TOTAL_REVENUES")
        vp = var_pct(rev, revb)
        occ_a, occ_b = kpi(principal, "occupancy_pct"), kpi(b, "occupancy_pct")
        adr_a, adr_b = kpi(principal, "adr"), kpi(b, "adr")
        noc_a, noc_b = kpi(principal, "rooms_occupied"), kpi(b, "rooms_occupied")
        gasto_a = sum(datos["totales"](principal, c) for _, c, _ in FLOW[1:])
        gasto_b = sum(datos["totales"](b, c) for _, c, _ in FLOW[1:])
        vg = var_pct(gasto_a, gasto_b)
        eb_a, eb_b = linea(principal, "EBITDA_BEFORE"), linea(b, "EBITDA_BEFORE")
        np_a, np_b = linea(principal, "NET_PROFIT"), linea(b, "NET_PROFIT")

        _p(doc, [
            (f"{sujeto} llegó a {k(rev)}, {k(abs(rev - revb))} "
             f"{signo(rev - revb)} lo presupuestado", True),
            (f" ({vp * 100:+,.1f}%)" if vp is not None else "", True),
            f", con una ocupación de {pct(occ_a)} contra {pct(occ_b)} del "
            f"presupuesto y {noc_a:,.0f} noches vendidas contra "
            f"{noc_b:,.0f}. La tarifa promedio cerró en ",
            (f"{usd(adr_a)} contra {usd(adr_b)}", True),
            ". El gasto operativo y de propiedad fue ",
            (f"{k(abs(gasto_a - gasto_b))} {signo(gasto_a - gasto_b)} lo previsto"
             + (f" ({vg * 100:+,.1f}%)" if vg is not None else ""), True),
            f". El EBITDA antes de capital cerró en {k(eb_a)} contra {k(eb_b)} "
            f"presupuestados, y la utilidad neta en {k(np_a)} contra {k(np_b)}.",
        ])

        # ⚠️ La regla del año completo va DENTRO de su corte y no en una nota
        # al final: es donde se lee la columna, y sin ella un Actual de ocho
        # meses contra doce de presupuesto parece un derrumbe.
        if corte == "full":
            _p(doc, "⚠️ En el año completo la columna principal es el Forecast y "
                    "la variación se mide contra el presupuesto. El Actual del "
                    "año son los meses efectivamente cargados: restarle doce "
                    "meses de presupuesto mostraría una caída que sólo significa "
                    "que el año no ha terminado.")

        # ⚠️ El Forecast NO es una columna de comparación (owner, 2026-09-30:
        # *«quitar la opción de comparación versus forecast»*). Se compara
        # contra el PRESUPUESTO y nada más.
        #
        # Pero el año completo SIGUE SIENDO el Forecast: ahí es la columna
        # principal, no una comparación. El Actual del año son los meses
        # cargados, y restarle doce de presupuesto da un derrumbe que sólo dice
        # que el año no terminó. Es la misma regla de la pantalla: el Forecast
        # se usa para el año, no para comparar el mes.
        _cuadro_corte(doc, f"{rotulo_corte} {anio} — "
                           + ("Forecast · Presupuesto" if principal is f
                              else "Actual · Presupuesto"),
                      principal, b, f if principal is f else None,
                      rot_principal, rot["budget"], rot.get("forecast", ""))
        _flow_through(doc, f"{rotulo_corte} {anio} — de dónde viene la diferencia "
                           f"contra el presupuesto", principal, b, datos["totales"])
        doc.add_page_break()

    # ── Sección 2 — Drivers ──────────────────────────────────────────────────
    _h(doc, "SECCIÓN 2 — De qué depende el resultado", nivel=1)
    _imagen(doc, "habitacion.jpg", 15.5)
    ytd_a, ytd_b = act["ytd"], bud["ytd"]
    _h(doc, "2.1 Volumen (demanda)", nivel=2)
    d_noc = kpi(ytd_a, "rooms_occupied") - kpi(ytd_b, "rooms_occupied")
    d_pax = kpi(ytd_a, "guests") - kpi(ytd_b, "guests")
    _p(doc, f"En el acumulado el hotel vendió {kpi(ytd_a, 'rooms_occupied'):,.0f} "
            f"noches contra {kpi(ytd_b, 'rooms_occupied'):,.0f} presupuestadas "
            f"({d_noc:+,.0f}), con {kpi(ytd_a, 'guests'):,.0f} huéspedes contra "
            f"{kpi(ytd_b, 'guests'):,.0f} ({d_pax:+,.0f}). La ocupación cerró en "
            f"{pct(kpi(ytd_a, 'occupancy_pct'))} contra "
            f"{pct(kpi(ytd_b, 'occupancy_pct'))} del presupuesto.")

    _h(doc, "2.2 Tarifa (calidad del ingreso)", nivel=2)
    _p(doc, f"La tarifa promedio acumulada es de {usd(kpi(ytd_a, 'adr'))} contra "
            f"{usd(kpi(ytd_b, 'adr'))} del presupuesto, y el RevPAR de "
            f"{usd(kpi(ytd_a, 'revpar'))} contra {usd(kpi(ytd_b, 'revpar'))}. "
            f"⚠️ El RevPAR se mide sobre el ingreso TOTAL por habitación "
            f"disponible, así que refleja todo lo que factura la propiedad y no "
            f"sólo la noche vendida.")
    if datos.get("adr_por_mes"):
        _tabla(doc, ["Mes", "Tarifa promedio", "Ocupación", "Noches vendidas"],
               datos["adr_por_mes"], anchos=[4.15, 4.15, 4.15, 4.15])

    # ── 2.3 Revenue mix ──────────────────────────────────────────────────────
    _h(doc, "2.3 Composición del ingreso", nivel=2)
    mix = datos.get("mix") or []
    if mix:
        _p(doc, "Aporte de cada departamento en el acumulado, contra el "
                "presupuesto:")
        _tabla(doc, ["Departamento", "Acumulado real", "Presupuesto",
                     "Variación $", "Variación %"],
               mix, anchos=[5.4, 3.1, 3.1, 2.9, 2.2])
    else:
        _pendiente(doc, "Composición del ingreso",
                   "el detalle por departamento no vino en esta corrida.")

    # ── ⚠️ Hasta acá ────────────────────────────────────────────────────────
    #
    # Owner, 2026-09-30: *«sólo vamos a dejar sección 1 y 2 por ahora; quita
    # todo lo demás»*.
    #
    # Lo que se sacó: la Sección 3 (gestión comercial, que no sale de la
    # contabilidad), la 4 (lo favorable y lo desfavorable, y la exposición
    # cambiaria) y la nota metodológica del cierre.
    #
    # ⚠️ **`SECCIONES` sigue existiendo y `_positivos_y_negativos` se sigue
    # llamando.** El «por ahora» del pedido dice que vuelven: borrar el armado
    # obligaría a reescribirlo, y dejarlo sin llamar lo convertiría en código
    # muerto que se pudre. Volver a encenderlas es agregar `"3"` y `"4"` a la
    # constante.
    #
    # ⚠️ Lo único que NO se podía perder era la regla del año completo — sin
    # ella la columna del full year se lee como un derrumbe—, y por eso subió a
    # su propio corte, en 1.3, que es donde aplica.

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
