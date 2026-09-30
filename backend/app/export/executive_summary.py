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
import re
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
#: Los cuadros. Owner, 2026-09-30, mirando el informe con las secciones nuevas:
#: *«esto se ve muy cargado… quisiera más simple, más pequeño»*.
#:
#: ⚠️ Baja de 9 a 8. El cuerpo se queda en 12 —eso lo pidió el owner y es lo que
#: se lee—; lo que recarga la página son diecisiete cuadros con la letra casi
#: del tamaño del párrafo que los presenta.
CUERPO_TABLA = 8

#: Cuánto alto de página le queda a un cuadro dibujado, en centímetros.
#:
#: Carta son 27,94 cm menos 2,2 de cada margen = 23,5. Se dejan dos para el
#: rótulo que lo presenta y el aire de abajo: un cuadro que ocupa hasta el
#: último milímetro empuja su propio título a la página anterior.
ALTO_UTIL = 21.5
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


#: Un número NEGATIVO dentro de la prosa, en cualquiera de las formas en que
#: este informe lo escribe: `-$25.4K`, `($1,234.50)`, `-19.8%`, `-3.8pp`.
#:
#: Owner, 2026-09-30: *«en este informe ejecutivo lo que es negativo debe ir en
#: rojo»*. En los cuadros ya iba; en el texto no, y el texto es donde el informe
#: dice lo que pasó. `-$300.7K` en medio de un párrafo se lee igual que
#: `$300.7K` si nada lo distingue — el guion se pierde entre las palabras.
_NEGATIVO = re.compile(
    r"\(\$[\d.,]+\)"            # ($1,234.50), la forma contable
    r"|-\s?\$[\d.,]+[KM]?"      # -$25.4K
    r"|-[\d.,]+\s?(?:%|pp)"      # -19.8% · -3.8pp
)


def _escribir(p, txt: str, negrita: bool):
    """El texto, partido para que los negativos salgan en rojo."""
    i = 0
    for m in _NEGATIVO.finditer(txt):
        for trozo, rojo in ((txt[i:m.start()], False), (m.group(), True)):
            if trozo:
                r = p.add_run(trozo)
                r.bold = negrita
                r.font.name = FUENTE
                r.font.size = Pt(CUERPO)
                r.font.color.rgb = ROJO if rojo else NEGRO
                _fuente_en_todo(r._element.get_or_add_rPr())
        i = m.end()
    if txt[i:]:
        r = p.add_run(txt[i:])
        r.bold = negrita
        r.font.name = FUENTE
        r.font.size = Pt(CUERPO)
        r.font.color.rgb = NEGRO
        _fuente_en_todo(r._element.get_or_add_rPr())


#: La sangría de la primera línea de cada párrafo.
#:
#: Owner, 2026-09-30: *«cada nuevo párrafo debe llevar sangría»*. Con el texto
#: justificado y sin espacio en blanco entre bloques, dos párrafos seguidos se
#: leen como uno: la sangría es lo que dice dónde empieza el siguiente.
SANGRIA = 0.75


def _p(doc, partes, justificar: bool = True):
    """Un párrafo. `partes` es texto, o una lista de (texto, negrita)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = INTERLINEA
    p.alignment = (WD_ALIGN_PARAGRAPH.JUSTIFY if justificar
                   else WD_ALIGN_PARAGRAPH.LEFT)
    # ⚠️ Sólo el cuerpo. Los rótulos de los cuadros pasan `justificar=False` y
    # con sangría quedarían desalineados del cuadro que presentan.
    if justificar:
        p.paragraph_format.first_line_indent = Cm(SANGRIA)
    for trozo in ([partes] if isinstance(partes, str) else partes):
        txt, negrita = (trozo, False) if isinstance(trozo, str) else trozo
        _escribir(p, txt, negrita)
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


#: Lo que NO se baja de mayúscula al suavizar un rótulo.
#:
#: ⚠️ `EBITDA` en «Ebitda» deja de ser una sigla y se lee como una palabra mal
#: escrita. Van también las que traen los nombres de cuenta del mayor.
SIGLAS = {
    "EBITDA", "GOP", "ADR", "REVPAR", "YTD", "P&L", "F&B", "A&B", "IT", "OTA",
    "OTAS", "USD", "CRC", "CCSS", "INS", "PMS", "SPA", "CAPEX", "IVA", "PAR",
    "POR", "AYB", "A", "Y", "B",
    # Códigos del PMS que son siglas, no palabras.
    "CPL", "OTA", "OTAS", "PMS", "ADR",
}

#: Las palabras que se quedan en minúscula dentro de un rótulo.
MENUDAS = {"and", "or", "of", "the", "on", "to", "for", "in", "de", "del", "la",
           "las", "el", "los", "y", "e", "o", "por", "con", "sin", "a"}


def suave(texto: str) -> str:
    """«TOTAL OVERHEAD EXPENSES» → «Total Overhead Expenses».

    Owner, 2026-09-30: *«que todos los cuadros queden en minúscula»*. Un cuadro
    entero en mayúscula grita, y con diecisiete cuadros el informe entero grita.

    ⚠️ **Sólo toca lo que viene GRITADO.** Un rótulo que ya está en mixto
    —«Club Madresal», «Garden View Deluxe-Tented Villa»— se queda como está: es
    el nombre propio que alguien escribió, y «arreglarlo» le cambiaría la
    capitalización a un dato.
    """
    letras = [c for c in texto if c.isalpha()]
    if not letras or sum(c.isupper() for c in letras) < len(letras) * 0.8:
        return texto

    def palabra(w: str, primera: bool) -> str:
        limpia = w.strip(".,()·/-")
        if limpia.upper() in SIGLAS:
            return w
        bajo = w.lower()
        if not primera and bajo in MENUDAS:
            return bajo
        # `Non-Deductible`, `Gain/Losses`: cada parte lleva su mayúscula.
        for sep in ("-", "/"):
            if sep in bajo:
                return sep.join(p.capitalize() if p else p
                                for p in bajo.split(sep))
        return bajo.capitalize()

    ws = texto.split(" ")
    return " ".join(palabra(w, i == 0 or not w.strip(".,()·/-"))
                    for i, w in enumerate(ws))


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


def _suavizar(encabezados, filas):
    """Los rótulos, sin gritar. Owner, 2026-09-30: *«que todos los cuadros
    queden en minúscula»*.

    ⚠️ Se aplica ACÁ, donde el texto entra al cuadro, y no en cada armador. Son
    diecisiete cuadros de cinco sitios distintos: con la regla repartida, el día
    que se agregue el dieciocho va a gritar y nadie se va a acordar de por qué.

    ⚠️ Toca los ENCABEZADOS y la primera columna. Las demás son montos ya
    formateados; `suave` los devolvería iguales igual, pero pasarlos sería
    afirmar que se puede recapitalizar un número.
    """
    encabezados = [(suave(h[0]), h[1]) if isinstance(h, tuple) else suave(h)
                   for h in encabezados]
    filas = [[suave(str(f[0]))] + list(f[1:]) if f else f for f in filas]
    return encabezados, filas


def _tabla(doc, encabezados, filas, anchos=None, resaltar=()):
    """Un cuadro. **Dibujado**, salvo que no se pueda.

    Owner, 2026-09-30: *«habíamos quedado que todos los cuadros debían
    convertirse en imágenes; favor revisá página por página»*.

    Era verdad a medias: sólo los quince desgloses de detalle se dibujaban. Los
    de la cascada, el flow-through, la tabla de tarifas y el mix seguían siendo
    tablas de Word, y son justo los que el owner ve primero. Ahora TODO pasa por
    acá, y acá se decide.

    ⚠️ `anchos` sigue siendo la misma lista en centímetros, y la regla de que
    quepan en los 16,79 útiles vale para los dos caminos.
    """
    return _cuadro_imagen(doc, encabezados, filas, anchos or [], resaltar)


def _tabla_word(doc, encabezados, filas, anchos=None, resaltar=()):
    """El cuadro como tabla de Word. El camino de respaldo de `_tabla`.

    ⚠️ Se usa cuando no hay fuente para dibujar —el contenedor no trae
    ninguna—. Un informe con un cuadro menos alineado se entrega; uno con un
    cuadro ilegible, no.

    `resaltar` son los índices de fila que van en negrita con fondo —los
    totales—. Los negativos salen en rojo, que es como se leen en el PDF.

    ⚠️ **Sin rejilla.** Antes usaba `Table Grid`, que dibuja una caja negra
    alrededor de cada celda: en un cuadro de doce filas son cien rayas y el
    número deja de ser lo que se ve primero. Un estado financiero se lee por
    filas, así que sólo hay rayas HORIZONTALES —finas, grises— más el
    encabezado y la línea del total. Las verticales no hacen falta: la columna
    la marca la alineación.
    """
    encabezados, filas = _suavizar(encabezados, filas)
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
        # ── El encabezado, en DOS líneas ──────────────────────────────────
        #
        # Owner, 2026-09-30, con una captura: *«esta vista se ve muy cargada y
        # está en la misma celda»*. Arriba la versión en una palabra —«Actual»,
        # «Budget», «Variación»— y abajo, chiquito, cuál es —«Final 2026»—.
        # Antes iba «ACTUAL Final 2026» de corrido, envuelto en la celda.
        rotulo, abajo = h if isinstance(h, tuple) else (h, "")
        r = p0.add_run(rotulo)
        r.bold = True
        r.font.name = FUENTE
        r.font.size = Pt(CUERPO_TABLA)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _fuente_en_todo(r._element.get_or_add_rPr())
        if abajo:
            salto = p0.add_run()
            salto.add_break()
            r2 = p0.add_run(abajo)
            r2.font.name = FUENTE
            r2.font.size = Pt(CUERPO_TABLA - 1)
            r2.font.color.rgb = RGBColor(0xD2, 0xDD, 0xD6)
            _fuente_en_todo(r2._element.get_or_add_rPr())
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


#: Los cinco desgloses que lleva cada corte, con la clave de `gasto-por-clase`.
#:
#: Owner, 2026-09-30: *«1.1.1 Detalle de Ingresos por departamento, 1.1.2
#: Detalle de Salary…»*, y lo mismo para el acumulado y para el año completo.
DETALLES = [
    ("Ingresos", "revenue"),
    ("Salary", "payroll"),
    ("Costo de ventas", "cost"),
    ("Opex", "opex"),
    ("Propiedad y capital", "property"),
]


def _cuadro_imagen(doc, encabezados, filas, anchos, resaltar=(),
                   ancho_cm: float | None = None):
    """El cuadro, DIBUJADO y pegado como imagen.

    Owner, 2026-09-30: *«quizás no quisiera agregar cuadros, quedan muy mal
    alineados. quiero que esos cuadros se conviertan en imágenes bien
    definidas»*.

    Una tabla de Word reparte el ancho sobrante con sus propias reglas: basta un
    rótulo largo para que una columna se ensanche, el resto se corra y dos
    cuadros seguidos dejen de coincidir. Dibujado, cada columna mide lo que se
    le dice y los quince desgloses salen idénticos entre sí.

    ⚠️ **Si no se puede dibujar, se arma la tabla de siempre.** Sin la fuente
    —el contenedor no trae ninguna— Pillow cae a su tipografía de mapa de bits.
    Un informe con un cuadro menos lindo se entrega; uno con un cuadro
    ilegible, no, y eso no se nota hasta que está impreso.
    """
    from app.export.tabla_imagen import dibujar_cuadro, hay_fuente

    if not hay_fuente():
        return _tabla_word(doc, encabezados, filas, anchos=anchos,
                           resaltar=set(resaltar))
    encabezados, filas = _suavizar(encabezados, filas)
    # ⚠️ `anchos` va en CENTÍMETROS, igual que en `_tabla`: es la misma regla
    # —han de caber en los 16,79 útiles— y una prueba la comprueba en los dos
    # caminos. El dibujo se coloca a su ancho real, sin reescalar.
    ancho_cm = ancho_cm or sum(anchos)
    png = dibujar_cuadro(encabezados, filas, anchos,
                         resaltar=set(resaltar), pt=CUERPO_TABLA)
    # ⚠️ Un dibujo NO se parte entre dos páginas: lo que no entra se pierde por
    # abajo sin avisar. Si el cuadro sale más alto que la caja, se coloca más
    # angosto para que quepa — más chico es peor que grande, pero recortado es
    # peor que las dos cosas.
    from PIL import Image
    im = Image.open(io.BytesIO(png))
    alto_cm = im.height / im.width * ancho_cm
    if alto_cm > ALTO_UTIL:
        ancho_cm *= ALTO_UTIL / alto_cm
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(io.BytesIO(png), width=Cm(ancho_cm))
    return p


def _renglones_del_detalle(datos: dict, clase: str, sid_a: str, sid_b: str,
                           meses: tuple[int, int]) -> list[tuple[str, float, float]]:
    """Los renglones de un desglose: rótulo, principal y presupuesto.

    ⚠️ Los doce meses de cada departamento vienen del MISMO agregador que da el
    flow-through, así que el desglose suma exactamente el total que el informe
    dijo dos párrafos antes. Una segunda consulta podría no hacerlo.
    """
    det = datos.get("detalle") or {}
    nombres = {**(datos.get("departamentos") or {}),
               **(datos.get("nombres_cuenta") or {})}
    a = (det.get(sid_a) or {}).get(clase) or {}
    b = (det.get(sid_b) or {}).get(clase) or {}
    desde, hasta = meses

    def total(serie) -> float:
        return sum(float(serie[i - 1]) for i in range(desde, hasta + 1)
                   if serie and i <= len(serie))

    out = []
    for code in sorted(set(a) | set(b)):
        va, vb = total(a.get(code) or []), total(b.get(code) or [])
        if abs(va) < 0.005 and abs(vb) < 0.005:
            continue      # una cuenta sin movimiento en ninguna de las dos
        out.append((f"{code} · {nombres.get(code, '')}".strip(" ·"), va, vb))
    # Lo más grande primero: lo que explica el número va arriba.
    out.sort(key=lambda r: -abs(r[1] if r[1] else r[2]))
    return out


def _seccion_detalle(doc, datos: dict, num: str, rotulo: str, clase: str,
                     sid_a: str, sid_b: str, meses: tuple[int, int],
                     rot_a: str, rot_b: str, periodo: str) -> None:
    """Un desglose por departamento, dibujado."""
    _h(doc, f"{num} Detalle de {rotulo} por departamento", nivel=3, color=NEGRO)
    filas = _renglones_del_detalle(datos, clase, sid_a, sid_b, meses)
    if not filas:
        _p(doc, f"Sin movimiento de {rotulo.lower()} en el período.")
        return
    cuerpo = [[r, usd(va), usd(vb), usd(va - vb)] for r, va, vb in filas]
    ta, tb = sum(r[1] for r in filas), sum(r[2] for r in filas)
    cuerpo.append(["TOTAL", usd(ta), usd(tb), usd(ta - tb)])
    _cuadro_imagen(
        doc,
        [("Departamento", ""), (rot_a, periodo), (rot_b, periodo),
         ("Variación", "")],
        # ⚠️ La primera columna, ANCHA: los nombres de cuenta del mayor son
        # largos —«8025 · Fines and Other Non-Deductible Expenses»— y en un
        # dibujo lo que no cabe se recorta, no se envuelve.
        cuerpo, anchos=[7.0, 3.2, 3.2, 3.2], resaltar={len(cuerpo) - 1})


def _acumular_room_stats(datos: dict, bloque: str, clave: str,
                         hasta: int) -> list[dict]:
    """El acumulado del año hasta `hasta`, por categoría o por canal.

    ⚠️ **Las tasas no se acumulan sumando.** Acá se suman los INGREDIENTES
    —noches, pax, ingreso, disponibles— y la ocupación y el ADR se recalculan
    sobre los totales del período. Promediar seis ADR mensuales le da el mismo
    peso a un mes de 20 noches que a uno de 150, y el número que sale no existe
    en ningún lado.

    ⚠️ Un mes sin cargar NO entra: un cero se lee como «no vendió», y con una
    propiedad que abrió a mitad de año eso convierte un acumulado incompleto en
    un mal semestre.
    """
    acc: dict[str, dict] = {}
    for m in (datos.get("room_stats") or {}).get("meses") or []:
        if not m.get("cargado") or int(m.get("month") or 0) > hasta:
            continue
        for f in m.get(bloque) or []:
            rot = str(f.get(clave) or "").strip() or "Sin asignar"
            d = acc.setdefault(rot, {"rotulo": rot, "noches": 0.0, "pax": 0.0,
                                     "revenue": 0.0, "disp": 0.0})
            d["noches"] += float(f.get("nights_occupied") or 0)
            d["pax"] += float(f.get("pax") or 0)
            d["revenue"] += float(f.get("revenue") or 0)
            d["disp"] += float(f.get("nights_available") or 0)
    return sorted(acc.values(), key=lambda d: -d["revenue"])


def _cuadro_room_stats(doc, datos: dict, bloque: str, clave: str,
                       rotulo: str) -> None:
    mes = int(datos.get("mes") or 12)
    filas = _acumular_room_stats(datos, bloque, clave, mes)
    if not filas:
        _pendiente(doc, rotulo,
                   "la estadística del PMS no está cargada para este escenario.")
        return
    cuerpo = []
    for d in filas:
        # El ADR se recalcula sobre los totales, nunca se promedia.
        adr = d["revenue"] / d["noches"] if d["noches"] else 0.0
        ocu = d["noches"] / d["disp"] if d["disp"] else None
        cuerpo.append([d["rotulo"], f"{d['noches']:,.0f}", f"{d['pax']:,.0f}",
                       usd(d["revenue"]), usd(adr),
                       pct(ocu) if ocu is not None else "—"])
    tn = sum(d["noches"] for d in filas)
    tr = sum(d["revenue"] for d in filas)
    td = sum(d["disp"] for d in filas)
    cuerpo.append(["TOTAL", f"{tn:,.0f}",
                   f"{sum(d['pax'] for d in filas):,.0f}", usd(tr),
                   usd(tr / tn if tn else 0.0),
                   pct(tn / td) if td else "—"])
    _cuadro_imagen(
        doc,
        [(rotulo, ""), ("Noches", "acumulado"), ("Pax", "acumulado"),
         ("Ingreso", "acumulado"), ("ADR", ""), ("Ocupación", "")],
        cuerpo, anchos=[5.4, 2.2, 1.9, 3.1, 2.1, 2.0],
        resaltar={len(cuerpo) - 1})


#: Cómo se llama cada concepto de membresía en el informe.
#:
#: ⚠️ En la base viajan como llave —`pendiente_firma`, `plan_pago`—. Una llave
#: en un informe a dueños se lee como un error de programa. Un concepto que no
#: esté acá sale con su llave en capitalizado y los guiones bajos como espacios:
#: mejor un rótulo imperfecto que una fila que desaparece.
CONCEPTOS_CLUB = {
    "activas": "Activas",
    "condicionados": "Condicionados",
    "pendiente_firma": "Pendientes de firma",
    "plan_pago": "En plan de pago",
    "excepcion": "Excepciones",
}


def _rotulo_concepto(clave: str) -> str:
    return CONCEPTOS_CLUB.get(clave, clave.replace("_", " ").capitalize())


def _cuadro_canales(doc, datos: dict, mes_ing: str) -> None:
    """Por dónde entraron las reservas: el mes y el acumulado.

    Owner, 2026-09-30: *«en el excel hay un tab de canales, traer ese acá,
    resumido YTD month»*.

    ⚠️ **Se agrupa por el código del PMS y no por el canal comercial.** Antes
    salían cuatro renglones —OTA, Direct Client, Inhouse y «Sin asignar»— y el
    más grande era «Sin asignar»: tres códigos que nadie clasificó todavía. Un
    cuadro cuyo renglón mayor se llama «sin asignar» no dice por dónde entró la
    reserva, dice que falta configurar algo. Con el código se lee EXPEDIA,
    BOOKING, PROMOCIONES — que es lo que el owner mira en el Excel.

    ⚠️ El ADR se recalcula sobre los totales del período. Promediar los ADR
    mensuales de un canal le daría el mismo peso a un mes de dos noches que a
    uno de cuarenta.
    """
    mes = int(datos.get("mes") or 12)
    acc: dict[str, dict] = {}
    for m in (datos.get("room_stats") or {}).get("meses") or []:
        n_mes = int(m.get("month") or 0)
        if not m.get("cargado") or n_mes > mes:
            continue
        for f in m.get("canales") or []:
            clave = (f.get("canal_code") or f.get("canal") or "—").strip()
            d = acc.setdefault(clave, {
                "rotulo": (f"{clave} · {f['canal']}" if f.get("canal") else clave),
                "cuenta": bool(f.get("cuenta_para_kpis", True)),
                "m_noc": 0.0, "m_rev": 0.0, "y_noc": 0.0, "y_rev": 0.0})
            noc, rev = float(f.get("nights_occupied") or 0), float(f.get("revenue") or 0)
            d["y_noc"] += noc
            d["y_rev"] += rev
            if n_mes == mes:
                d["m_noc"] += noc
                d["m_rev"] += rev
    if not acc:
        _pendiente(doc, "Canales",
                   "la estadística del PMS no está cargada para este escenario.")
        return

    def fila(d: dict) -> list:
        return [d["rotulo"],
                f"{d['m_noc']:,.0f}", usd(d["m_rev"]),
                usd(d["m_rev"] / d["m_noc"]) if d["m_noc"] else "—",
                f"{d['y_noc']:,.0f}", usd(d["y_rev"]),
                usd(d["y_rev"] / d["y_noc"]) if d["y_noc"] else "—"]

    filas = [fila(d) for d in sorted(acc.values(), key=lambda x: -x["y_rev"])]

    def total(solo_cuenta: bool) -> dict:
        ds = [d for d in acc.values() if d["cuenta"] or not solo_cuenta]
        return {"rotulo": "Total" if solo_cuenta else "Con todos los canales (PDF)",
                **{k: sum(d[k] for d in ds)
                   for k in ("m_noc", "m_rev", "y_noc", "y_rev")}}

    filas.append(fila(total(True)))
    resaltar = {len(filas) - 1}
    # ⚠️ La fila del PDF sólo si hay cortesías. Sin ellas repetiría el total y
    # se leería como que algo no cuadra.
    if any(not d["cuenta"] for d in acc.values()):
        filas.append(fila(total(False)))
    _tabla(doc,
           [("Canal", ""), ("Noches", mes_ing), ("Ingreso", mes_ing),
            ("ADR", mes_ing), ("Noches", "Acumulado"),
            ("Ingreso", "Acumulado"), ("ADR", "Acumulado")],
           filas, anchos=[4.4, 1.85, 2.4, 2.0, 1.85, 2.4, 1.85],
           resaltar=resaltar)


def _cuadro_membresias(doc, datos: dict) -> None:
    """Los socios del Club, como los cargó el mes.

    ⚠️ Es el MES, no el acumulado: la pregunta de una membresía es cuántos hay
    hoy. Sumar doce meses de socios daría una cifra doce veces más grande que
    el Club (owner, 2026-09-02, sobre el mismo renglón en el cierre)."""
    mes = int(datos.get("mes") or 12)
    meses = (datos.get("membresias") or {}).get("meses") or []
    actual = next((m for m in meses
                   if int(m.get("month") or 0) == mes and m.get("cargado")), None)
    if not actual:
        _pendiente(doc, "Membresías",
                   "no hay membresías cargadas para el mes del informe.")
        return
    cuerpo = [[_rotulo_concepto(str(c.get("concepto") or "")),
               f"{float(c.get('cantidad') or 0):,.0f}"]
              for c in (actual.get("conceptos") or [])]
    if not cuerpo:
        _pendiente(doc, "Membresías", "el mes no trae conceptos cargados.")
        return
    cuerpo.append(["TOTAL",
                   f"{sum(float(c.get('cantidad') or 0) for c in actual['conceptos']):,.0f}"])
    _cuadro_imagen(doc, [("Concepto", ""), ("Socios", "al cierre del mes")],
                   cuerpo, anchos=[7.0, 4.0], resaltar={len(cuerpo) - 1})


def _perspectivas(doc, datos: dict, act: dict, bud: dict, fcs: dict | None,
                  mes_ing: str, anio: int) -> None:
    """Lo que queda del año, con lo que el Forecast dice hoy.

    ⚠️ Sale del FORECAST y no del Actual: los meses que faltan no existen
    todavía. Y se dice lo que falta —del mes siguiente a diciembre—, no el año
    entero: el año entero ya está en 1.3, y repetirlo acá no contesta la
    pregunta de esta sección, que es qué viene.
    """
    _h(doc, "SECCIÓN 3 — Perspectivas para los meses siguientes", nivel=1)
    if not fcs:
        _pendiente(doc, "Perspectivas",
                   "no se eligió una versión de Forecast para esta corrida.")
        return
    mes = int(datos.get("mes") or 12)
    if mes >= 12:
        _p(doc, "El informe cierra diciembre: no quedan meses por proyectar.")
        return

    # Lo que falta = el año completo menos lo transcurrido.
    def resto(code: str) -> float:
        return linea(fcs["full"], code) - linea(fcs["ytd"], code)

    rev, eb = resto("TOTAL_REVENUES"), resto("EBITDA_BEFORE")
    rev_b = linea(bud["full"], "TOTAL_REVENUES") - linea(bud["ytd"], "TOTAL_REVENUES")
    eb_b = linea(bud["full"], "EBITDA_BEFORE") - linea(bud["ytd"], "EBITDA_BEFORE")
    faltan = 12 - mes
    vp = var_pct(rev, rev_b)
    _p(doc, [
        (f"Quedan {faltan} mes{'es' if faltan > 1 else ''} por delante. ", True),
        "Según el forecast vigente, de aquí a diciembre entrarían ",
        (f"{k(rev)} de ingreso", True),
        f" contra {k(rev_b)} presupuestados para ese mismo tramo",
        (f" ({vp * 100:+,.1f}%)" if vp is not None else ""),
        f", y el EBITDA antes de capital del tramo cerraría en {k(eb)} contra "
        f"{k(eb_b)}.",
    ])
    # ⚠️ Cuando el tramo que falta es IDÉNTICO al presupuesto, hay que decirlo.
    #
    # Pasa —y pasa en agosto 2026— porque el Forecast se armó como «los meses
    # cargados más el Budget para el resto»: nadie volvió a proyectar lo que
    # viene. Sin esta línea, la sección dice «+0,0%» y se lee como que el año
    # va a aterrizar clavado en el plan, que es la conclusión contraria a la
    # verdadera: todavía no se proyectó.
    if abs(rev - rev_b) < 0.01 and abs(eb - eb_b) < 0.01:
        _p(doc, [("⚠️ El tramo que falta es, hoy, el presupuesto. ", True),
                 "El forecast vigente arrastra el plan para los meses que "
                 "todavía no se cargaron: no es que se espere cerrar clavado "
                 "en el presupuesto, es que esos meses no se han vuelto a "
                 "proyectar. Mientras siga así, la lectura del año completo "
                 "es el presupuesto más lo que ya pasó."])

    _p(doc, "⚠️ Es la proyección vigente, no una promesa: son los meses que "
            "todavía no se cargaron. Lo que la mueve es lo mismo que movió el "
            "acumulado — ocupación, tarifa y la escala del gasto operativo—, y "
            "cada cierre la vuelve a medir.")


#: Los renglones del cuadro de volumen, con cómo se lee cada uno.
#:
#: Owner, 2026-09-30: *«acá debe haber un cuadro como imagen para hablar del
#: volumen, hay mucha información que se puede poner acá»*.
VOLUMEN = [
    ("Noches disponibles", lambda c: kpi(c, "rooms_available"), "num"),
    ("Noches vendidas", lambda c: kpi(c, "rooms_occupied"), "num"),
    ("% Ocupación", lambda c: kpi(c, "occupancy_pct"), "pct"),
    ("Huéspedes", lambda c: kpi(c, "guests"), "num"),
    # La razón que el encabezado no trae y que explica el volumen: cuánta gente
    # entra por noche vendida. Sube la ocupación de las camas sin mover la de
    # las habitaciones, y es lo que separa una noche de pareja de una de familia.
    #
    # ⚠️ Hubo aquí un renglón de «noches vendidas por día» y se sacó: los días
    # del período salían de dividir las disponibles entre las unidades, y las
    # unidades no viajan en el encabezado. Quedaba un 16 escrito a mano —el de
    # Amarena— que en cualquier otra propiedad habría dado un número creíble y
    # falso.
    ("Huéspedes por noche vendida",
     lambda c: (kpi(c, "guests") / kpi(c, "rooms_occupied")
                if kpi(c, "rooms_occupied") else 0.0), "raz"),
]


def _cuadro_volumen(doc, act: dict, bud: dict, mes_ing: str) -> None:
    """De dónde sale el volumen: el mes y el acumulado, contra el presupuesto.

    ⚠️ Las dos razones del pie NO se acumulan sumando: se recalculan sobre los
    totales del período, que es la misma regla de todo el informe.
    """
    def celda(v: float, fmt: str) -> str:
        return (pct(v) if fmt == "pct" else f"{v:,.2f}" if fmt == "raz"
                else f"{v:,.0f}")

    filas = []
    for rotulo, lee, fmt in VOLUMEN:
        fila = [rotulo]
        for corte in ("month", "ytd"):
            a, b = lee(act[corte]), lee(bud[corte])
            d = a - b
            fila += [celda(a, fmt), celda(b, fmt),
                     # La variación de un porcentaje va en PUNTOS, no en otro
                     # porcentaje: «+10.18pp» dice cuánto subió la ocupación;
                     # «+124%» dice otra cosa.
                     (f"{d * 100:+,.2f}pp" if fmt == "pct"
                      else f"{d:+,.2f}" if fmt == "raz" else f"{d:+,.0f}")]
        filas.append(fila)
    _tabla(doc,
           [("Indicador", ""), ("Real", mes_ing), ("Presupuesto", mes_ing),
            ("Variación", ""), ("Real", "Acumulado"),
            ("Presupuesto", "Acumulado"), ("Variación", "")],
           filas, anchos=[4.4, 1.95, 2.25, 1.95, 1.95, 2.25, 1.95])


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
    # ⚠️ El rótulo se parte en dos: la palabra que dice QUÉ es la columna, y
    # debajo cuál versión. `rot_a` llega como «ACTUAL Final 2026».
    def _dos(rot: str, palabra: str) -> tuple[str, str]:
        resto = rot.split(" ", 1)[1] if " " in rot else ""
        return (palabra, resto)

    cabezas = ["CUENTA", _dos(rot_a, "Forecast" if (fcs is not None and fcs is act)
                              else "Actual"),
               _dos(rot_b, "Budget"), "Variación",
               _dos(rot_c, "Forecast") if rot_c else ""]
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

        # ── El desglose por departamento ─────────────────────────────────
        #
        # ⚠️ Va DENTRO del corte y no en una sección aparte: el detalle de
        # agosto al lado del acumulado de agosto se lee como si fueran el
        # mismo período.
        ids = datos.get("ids") or {}
        sid_a = (ids.get("forecast") if principal is f else ids.get("actual")) \
            or ids.get("actual") or ""
        rango = (datos.get("rangos") or {}).get(corte) or (1, 12)
        for j, (rotulo_det, clase) in enumerate(DETALLES, start=1):
            _seccion_detalle(doc, datos, f"{num}.{j}", rotulo_det, clase,
                             sid_a, ids.get("budget") or "", rango,
                             "Forecast" if principal is f else "Actual",
                             "Budget", rotulo_corte)
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
    _cuadro_volumen(doc, act, bud, mes_ing)

    _h(doc, "2.2 Tarifa (calidad del ingreso)", nivel=2)
    _p(doc, f"La tarifa promedio acumulada es de {usd(kpi(ytd_a, 'adr'))} contra "
            f"{usd(kpi(ytd_b, 'adr'))} del presupuesto, y el RevPAR de "
            f"{usd(kpi(ytd_a, 'revpar'))} contra {usd(kpi(ytd_b, 'revpar'))}. "
            f"⚠️ El RevPAR se mide sobre el ingreso TOTAL por habitación "
            f"disponible, así que refleja todo lo que factura la propiedad y no "
            f"sólo la noche vendida.")
    if datos.get("adr_por_mes"):
        # ⚠️ El acumulado NO es el promedio de la columna (owner, 2026-09-30:
        # *«debe haber un YTD al final de cada columna»*). La tarifa y la
        # ocupación son razones: el promedio de seis ADR mensuales le da el
        # mismo peso a un mes de 20 noches que a uno de 202, y el número que
        # sale no existe en ningún lado. Sale del MISMO corte que el resto del
        # informe, que ya los trae ponderados.
        filas = [*datos["adr_por_mes"], [
            f"YTD {mes_ing}", usd(kpi(ytd_a, "adr")),
            pct(kpi(ytd_a, "occupancy_pct")),
            f"{kpi(ytd_a, 'rooms_occupied'):,.0f}"]]
        _tabla(doc, ["Mes", "Tarifa promedio", "Ocupación", "Noches vendidas"],
               filas, anchos=[4.15, 4.15, 4.15, 4.15],
               resaltar={len(filas) - 1})

    # ── 2.3 Revenue mix ──────────────────────────────────────────────────────
    _h(doc, "2.3 Composición del ingreso", nivel=2)
    mix = datos.get("mix") or []
    if mix:
        _p(doc, "Aporte de cada departamento en el acumulado, contra el "
                "presupuesto:")
        # ⚠️ La suma es de lo LISTADO, y por eso se llama «Total ingresos»: son
        # todas las líneas de ingreso del P&L, así que da el ingreso del
        # período. Si algún día se lista un subconjunto, el rótulo miente antes
        # que el número.
        tot = datos.get("mix_total")
        _tabla(doc, ["Departamento", "Acumulado real", "Presupuesto",
                     "Variación $", "Variación %"],
               [*mix, *([tot] if tot else [])],
               anchos=[5.4, 3.1, 3.1, 2.9, 2.2],
               resaltar={len(mix)} if tot else set())
    else:
        _pendiente(doc, "Composición del ingreso",
                   "el detalle por departamento no vino en esta corrida.")

    # ── 2.4 Revenue por tipo de habitación ───────────────────────────────────
    _h(doc, "2.4 Revenue por tipo de habitación", nivel=2)
    _cuadro_room_stats(doc, datos, "categorias", "room_type_name",
                       "Tipo de habitación")

    # ── 2.5 Análisis de canales ──────────────────────────────────────────────
    _h(doc, "2.5 Análisis de canales", nivel=2)
    _cuadro_canales(doc, datos, mes_ing)

    # ── 2.6 Membresías ───────────────────────────────────────────────────────
    _h(doc, "2.6 Membresías actuales", nivel=2)
    _cuadro_membresias(doc, datos)

    # ── 3.0 Perspectivas ─────────────────────────────────────────────────────
    _perspectivas(doc, datos, act, bud, fcs, mes_ing, anio)

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
