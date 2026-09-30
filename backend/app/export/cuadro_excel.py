"""Exportador GENÉRICO de cuadros a Excel, con el formato de la casa.

**Por qué existe.** El owner pidió que todos los cuadros de todos los tabs se
puedan bajar a Excel con formato profesional. Son ~47 pantallas sin exportación
y ~11 más que exportan mal. Escribir 47 exportadores a mano no es viable: cada
uno son 200 líneas y todos se desincronizan del estilo con el tiempo.

**Y hay una razón técnica que cierra la discusión.** Las 10 pantallas que hoy
bajan Excel lo hacen desde el navegador con `xlsx` (SheetJS Community), que **no
escribe estilos de celda**: negrita, relleno, bordes y formato de moneda son de
la edición paga. Con esa librería, «formato profesional» es imposible por más
código que se escriba. Por eso esto vive en el servidor, con `openpyxl`.

**El contrato.** La pantalla manda lo que YA tiene renderizado:

    {
      "titulo": "Big Picture — Budget 2027",
      "subtitulo": "Corcovado · USD",          # opcional
      "columnas": [
        {"label": "Concepto", "ancho": 42, "formato": "texto"},
        {"label": "2026",     "ancho": 14, "formato": "usd"},
        {"label": "Var %",    "ancho": 10, "formato": "pct"},
      ],
      "filas": [
        {"label": "Ingresos",       "nivel": 0, "es_total": True,  "valores": [1000, 0.12]},
        {"label": "  Habitaciones", "nivel": 1, "es_total": False, "valores": [800, 0.10]},
      ],
    }

Los valores van como NÚMERO, nunca como texto ya formateado. Es la diferencia
entre un Excel que se puede sumar y uno que no — hoy `/reports/summary` manda
`"$1,234.00"` como cadena y el archivo resultante no sirve para nada.

Un libro puede llevar varios cuadros: cada uno es su hoja. Las pantallas con
tabs (allocations tiene 12 cuadros, cash flow directo 6) bajan todo de una.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from openpyxl.comments import Comment
from openpyxl.worksheet.hyperlink import Hyperlink

from app.export.excel_base import (
    C, align, border, fill, font, marco_total, merged_header, nombre_de_hoja,
    set_col_widths, workbook_to_bytes,
)

# Mismos formatos que `pl_full_detail_excel`, que es la referencia del repo:
# negativo en rojo y entre paréntesis, y el cero NO se imprime — una grilla
# llena de ceros esconde las cifras que sí importan.
FORMATOS = {
    "usd":   '#,##0;[Red](#,##0);""',
    "usd2":  '#,##0.00;[Red](#,##0.00);""',
    "pct":   '0.0%;[Red](0.0%);""',
    "num":   '#,##0;[Red](#,##0);""',
    "num1":  '#,##0.0;[Red](#,##0.0);""',
    "texto": None,
}

FILA_TITULO = 1
#: ⚠️ **El subtítulo YA NO se escribe en la hoja.**
#:
#: Owner, 2026-09-30: *«que no bajen en el excel los textos insertados. que
#: bajen limpios»*.
#:
#: Era prosa —«la varianza del full year es Forecast contra Budget: el Actual
#: del año todavía no existe…»— en una banda combinada sobre las columnas. En
#: pantalla explica; en una hoja de cálculo estorba: rompe el filtro, se lleva
#: el ancho de la primera columna al copiar, y aparece pegada arriba del cuadro
#: cuando alguien lo pega en otro lado.
#:
#: Sigue viajando: va en la hoja ÍNDICE, que es donde se lee una vez, y en el
#: Word, que es un documento y no una tabla.
#:
#: ⚠️ **La constante se queda en 2 y la fila queda EN BLANCO.** Bajarla a 1
#: subiría la tabla una fila, y hay un `test_sin_franja_el_cuadro_arranca_donde_
#: siempre` que defiende justamente lo contrario: media docena de pruebas —y de
#: macros de quien ya usa estos archivos— buscan la cabecera en la fila 4. Lo
#: que se pidió fue sacar el texto, no mover el cuadro.
FILA_SUBTITULO = 2
FILA_CABECERA = 4
PRIMERA_FILA = 5


def _kpis(ws, cuadro: dict, desde: int) -> int:
    """La franja de estadísticas, arriba del cuadro. Devuelve la fila siguiente.

    Owner, 2026-09-03: *«no están saliendo las estadísticas en cada tab»*.

    ⚠️ En la pantalla la franja se dibuja UNA vez arriba de los sub-tabs, así
    que se ve en todos. Acá **cada hoja se lee sola** —se imprime, se manda
    suelta— y sin las estadísticas al lado los montos no tienen contra qué
    leerse: 56.001 de ingreso con 132 noches vendidas dice algo muy distinto
    que con 400.

    Va en gris y compacta: es contexto, no el cuadro.
    """
    filas = cuadro.get("kpis") or []
    columnas = cuadro.get("kpis_columnas") or []
    if not filas or not columnas:
        return desde

    fila = desde
    c = ws.cell(fila, 1, "ESTADÍSTICAS")
    c.font = font(bold=True, size=9, color=C["navy_mid"])
    for i, col in enumerate(columnas, start=2):
        c = ws.cell(fila, i, col)
        c.font = font(bold=True, size=9, color=C["navy_mid"])
        c.alignment = align("right")
    fila += 1

    for f in filas:
        rot = str(f.get("label") or "")
        ws.cell(fila, 1, rot).font = font(size=9)
        # El formato lo decide el rótulo: la ocupación es un porcentaje y la
        # tarifa son dólares. Mandarlo por fila desde la pantalla sería una
        # tercera copia de la misma decisión.
        bajo = rot.lower()
        fmt = ("pct" if "%" in rot else
               "usd2" if ("adr" in bajo or "daily" in bajo or "revpar" in bajo
                          or "cuota" in bajo) else "num")
        for i, v in enumerate(f.get("valores") or [], start=2):
            celda = ws.cell(fila, i, v)
            celda.number_format = FORMATOS.get(fmt, FORMATOS["usd"])
            celda.alignment = align("right")
            celda.font = font(size=9)
        fila += 1
    return fila + 1          # una en blanco antes del cuadro


def _hoja(wb: Workbook, cuadro: dict, usados: set[str]):
    columnas = cuadro.get("columnas") or []
    filas = cuadro.get("filas") or []
    titulo = (cuadro.get("titulo") or "Cuadro").strip()
    n_col = max(1, len(columnas))

    ws = wb.create_sheet(nombre_de_hoja(cuadro.get("hoja") or titulo, usados))

    merged_header(ws, FILA_TITULO, 1, n_col, titulo, C["navy"], sz=13)

    # ⚠️ La cabecera del cuadro se corre hacia abajo lo que ocupe la franja.
    # Las constantes de fila eran fijas; con la franja delante, escribir la
    # tabla en la fila 4 la pisaría.
    FILA_CABECERA = _kpis(ws, cuadro, FILA_SUBTITULO + 2)
    PRIMERA_FILA = FILA_CABECERA + 1

    for i, col in enumerate(columnas, start=1):
        c = ws.cell(FILA_CABECERA, i, col.get("label", ""))
        c.fill = fill(C["navy_mid"])
        c.font = font(bold=True, color=C["white"], size=10)
        # La primera columna es la etiqueta de la fila; el resto son números.
        c.alignment = align("left" if i == 1 else "center", wrap=True)
        c.border = border()

    for j, f in enumerate(filas):
        fila = PRIMERA_FILA + j
        # ── Tres estados de fila, y son tres cosas distintas ─────────────────
        #
        # Owner, 2026-09-30, mostrando el tab que arregló a mano:
        #
        #   normal    rejilla fina gris, sin relleno, sin negrita
        #   sección   relleno pálido, negrita, raya arriba — SIN marco negro
        #   total     recuadro NEGRO medio + relleno + negrita
        #
        # ⚠️ Antes había sólo dos: el encabezado de sección compartía marcador
        # con el total, así que «REVENUES» salía con el mismo peso visual que
        # «NET PROFIT» y el ojo no encontraba dónde cierra cada bloque.
        es_seccion = bool(f.get("es_seccion"))
        es_total = bool(f.get("es_total")) and not es_seccion
        nivel = int(f.get("nivel") or 0)
        ultima_col = min(n_col, 1 + len(f.get("valores") or []))

        # La jerarquía va con SANGRÍA de Excel, no con espacios dentro del texto.
        # Con espacios, ordenar la columna o copiarla a otro lado se lleva la
        # sangría puesta y el nivel deja de significar nada. Es lo que hace hoy
        # `/reports/expenses`, que simula la jerarquía con espacios.
        etiqueta = ws.cell(fila, 1, f.get("label", ""))
        etiqueta.font = font(bold=es_total or es_seccion,
                             color=C["tinta"])
        etiqueta.alignment = Alignment(horizontal="left", vertical="center",
                                       indent=min(nivel, 8))
        etiqueta.border = border()
        if es_total:
            etiqueta.fill = fill(C["banda_total"])
            etiqueta.border = marco_total(True, n_col == 1)
        elif es_seccion:
            etiqueta.fill = fill(C["banda_seccion"])
            etiqueta.border = border(sides="all_top")

        # La fila puede pisar el formato de la columna. Hace falta cuando un mismo
        # cuadro mezcla unidades en la misma columna — el bloque de drivers del
        # Big Picture tiene noches, ocupación % y ADR en dólares, una debajo de
        # otra. Sin esto habría que partirlo en tres cuadros.
        fmt_fila = f.get("formato")

        for i, valor in enumerate(f.get("valores") or [], start=2):
            if i > n_col:
                break
            celda = ws.cell(fila, i, valor)
            fmt = FORMATOS.get(fmt_fila or columnas[i - 1].get("formato") or "usd",
                               FORMATOS["usd"])
            if fmt:
                celda.number_format = fmt
            # El texto se alinea a la izquierda: una columna de nombres de cuenta
            # alineada a la derecha es ilegible. Pasa en las pantallas de mapeo,
            # que son casi todas de texto (cuenta · departamento · línea del P&L).
            celda.alignment = align("left" if isinstance(valor, str) else "right")
            celda.font = font(bold=es_total or es_seccion,
                              color=C["tinta"])
            if es_total:
                # ⚠️ El negro sólo en los extremos. En todas las celdas, el
                # total saldría con la rejilla negra y parecería otra tabla.
                celda.border = marco_total(False, i == ultima_col)
                celda.fill = fill(C["banda_total"])
            elif es_seccion:
                celda.border = border(sides="all_top")
                celda.fill = fill(C["banda_seccion"])
            else:
                celda.border = border()

        # ⚠️ Si la fila trae menos valores que columnas, el marco se cortaría a
        # media tabla. Se completan las celdas que faltan con el mismo formato y
        # sin contenido: el recuadro tiene que llegar a la última columna.
        if es_total or es_seccion:
            for i in range(max(2, ultima_col + 1), n_col + 1):
                celda = ws.cell(fila, i)
                celda.fill = fill(C["banda_total"] if es_total
                                  else C["banda_seccion"])
                celda.border = (marco_total(False, i == n_col) if es_total
                                else border(sides="all_top"))

    set_col_widths(ws, {i: (col.get("ancho") or (38 if i == 1 else 14))
                        for i, col in enumerate(columnas, start=1)})
    # Congelar la cabecera y la columna de etiquetas: sin esto, un cuadro de 12
    # meses obliga a adivinar qué fila se está mirando al llegar a diciembre.
    ws.freeze_panes = ws.cell(PRIMERA_FILA, 2)

    # ── Que imprima en UNA hoja ──────────────────────────────────────────────
    #
    # Owner, 2026-08-27: «el Excel debe ser en una sola página sin separar». Un
    # cuadro de 12 meses son 14 columnas: en vertical y sin ajuste, Excel lo
    # parte en tres o cuatro hojas y los meses quedan repartidos entre papeles
    # distintos. Un reporte partido no se puede leer ni mandar.
    #
    # `fitToPage` en `sheet_properties.pageSetUpPr` es OBLIGATORIO: sin él,
    # `fitToWidth`/`fitToHeight` quedan escritos en el archivo y Excel los
    # ignora — se ve bien en el XML y sale partido igual.
    #
    # `fitToHeight = 0` es «las hojas de alto que haga falta». Se usa 1 porque
    # el pedido es una sola hoja; un cuadro larguísimo sale con letra chica,
    # que es preferible a que se parta.
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.4
    # El área de impresión se acota a lo escrito: sin esto, una celda tocada
    # por accidente lejos de la tabla arrastra hojas en blanco.
    ultima = PRIMERA_FILA + max(0, len(filas)) - 1
    if ultima >= FILA_TITULO:
        ws.print_area = f"A{FILA_TITULO}:{get_column_letter(n_col)}{ultima}"
    return ws


def _indice(wb: Workbook, cuadros: list[dict], nombres: list[str]) -> None:
    """La portada del libro: qué trae y en qué hoja está cada cosa.

    Owner, 2026-09-03: *«que baje bien profesional y claro»*, pidiendo que el
    Excel traiga todos los sub-tabs «tal como Word».

    ⚠️ El Word tiene su página de CONTENIDO; un libro de doce hojas sin índice
    obliga a recorrer las pestañas de abajo una por una, y los nombres van
    cortados a 31 caracteres —«Profit & Loss Statement YTD JU»—, así que ni
    siquiera se leen enteros. El índice es donde el título completo cabe.

    Va PRIMERO y con los nombres tal como quedaron, no como se pidieron: si dos
    cuadros se llamaban parecido, el libro los desambiguó y el índice tiene que
    mostrar el nombre real de la pestaña o no sirve para encontrarla.
    """
    ws = wb.create_sheet("Índice", 0)
    merged_header(ws, 1, 1, 3, "CONTENIDO", C["navy"], sz=13)
    for i, rotulo in enumerate(("#", "Hoja", "Cuadro"), start=1):
        c = ws.cell(3, i, rotulo)
        c.fill = fill(C["navy_mid"])
        c.font = font(bold=True, color=C["white"], size=10)
        c.alignment = align("left")
        c.border = border()
    for j, (cuadro, hoja) in enumerate(zip(cuadros, nombres)):
        fila = 4 + j
        titulo = (cuadro.get("titulo") or "Cuadro").strip()
        sub = (cuadro.get("subtitulo") or "").strip()
        #: La descripción de UNA línea que el owner escribió a mano
        #: (2026-09-30). El título completo y el subtítulo largo pasan a ser la
        #: NOTA de la celda: siguen estando —explican cómo se calcula cada
        #: tab— sin volver el índice una pared de texto.
        corta = (cuadro.get("descripcion") or "").strip() or titulo
        banda = _banda_del_bloque(hoja)
        for i, valor in enumerate((j + 1, hoja, corta), start=1):
            c = ws.cell(fila, i, valor)
            c.alignment = align("left")
            c.border = border()
            if banda:
                c.fill = fill(banda)
            c.font = font(size=10)
        # ── El nombre de la hoja, como LINK ───────────────────────────────
        #
        # Owner, 2026-09-30: *«cada nombre es un link a su hoja»*. Un libro de
        # dieciocho pestañas se recorre con el índice o no se recorre: las
        # lengüetas de abajo van cortadas a 31 caracteres y hay que buscarlas
        # una por una.
        #
        # ⚠️ El nombre va entre comillas simples. Sin ellas, una hoja con
        # espacios —«P&L Ago Consolidado»— rompe la referencia y Excel abre el
        # archivo diciendo que el link no es válido.
        celda = ws.cell(fila, 2)
        # ⚠️ `location` y NO `hyperlink = "#'Hoja'!A1"`. Asignando una cadena,
        # openpyxl la guarda como destino EXTERNO: Excel abre el archivo
        # avisando que el vínculo no es válido y el link no lleva a ningún lado.
        celda.hyperlink = Hyperlink(ref=celda.coordinate,
                                    location=f"'{hoja}'!A1")
        celda.font = font(size=10, color="1F4E79", underline="single")
        # ── La explicación larga, como NOTA ───────────────────────────────
        #
        # No se pierde: explica cómo se calcula cada tab. Pero en la celda
        # convertía el índice en una pared de texto (owner, 2026-09-30: una
        # descripción corta por hoja).
        largo = titulo + (f" · {sub}" if sub else "")
        if largo.strip() and largo.strip() != corta:
            ws.cell(fila, 3).comment = Comment(largo, "FinPlan", width=420,
                                               height=170)
    set_col_widths(ws, {1: 5, 2: 34, 3: 88})
    ws.freeze_panes = ws.cell(4, 1)


#: Con qué color se pinta cada bloque del índice.
#:
#: ⚠️ Por el nombre de la hoja y no por el orden: el paquete se puede reordenar
#: desde «Armar paquete», y con el orden las bandas quedarían repartidas al azar.
_BLOQUES = (
    ("P&L", "F3DFE0"),          #: los tres estados de resultados
    ("Checkbook", "EDE6D6"),    #: el detalle por cuenta
)
_BANDA_RESTO = "DCE9F2"         #: estadística y anexos


def _banda_del_bloque(hoja: str) -> str:
    for prefijo, color in _BLOQUES:
        if hoja.startswith(prefijo):
            return color
    return _BANDA_RESTO


def build_cuadros_workbook(cuadros: list[dict]) -> bytes:
    """Un libro con una hoja por cuadro, y un índice adelante."""
    wb = Workbook()
    wb.remove(wb.active)
    usados: set[str] = set()
    nombres: list[str] = []
    for cuadro in cuadros or []:
        nombres.append(_hoja(wb, cuadro, usados).title)
    # ⚠️ El índice sólo cuando hay VARIAS hojas. En un libro de una, una portada
    # que dice «1. esa hoja» es un clic de más para llegar al único cuadro.
    if len(nombres) > 1:
        _indice(wb, cuadros or [], nombres)
    if not wb.sheetnames:            # nunca devolver un libro sin hojas
        wb.create_sheet("Sin datos")
    return workbook_to_bytes(wb)
