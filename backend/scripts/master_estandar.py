# -*- coding: utf-8 -*-
"""Aplica el Estandar_Presupuesto_Hotelero_Macro_a_Micro.md al Master File.

Por COM: openpyxl le suelta las 18 tablas al archivo (ver la memoria
`el-master-file-no-se-toca-con-openpyxl`). Cada paso es idempotente: correrlo
dos veces deja lo mismo.
"""
import sys
import time
import win32com.client as win32

RUTA = r"C:\Users\User\Desktop\FINPLAN\Amarena\2026-11-11_Amarena_ Master File Budget 2027.xlsx"
HOJA = "Presentación"          # antes se llamaba "Reporte"
VIEJO = "Reporte"

# Página -> fila donde arranca -> título de la sección
PAGINAS = [
    (1, 1, "Carta a los dueños"),
    (2, 57, "Dashboard"),
    (3, 122, "Ingresos · de dónde viene el crecimiento"),
    (4, 179, "Flow-through y punto de equilibrio"),
    (5, 236, "Detalle por departamento"),
    (6, 315, "Hotel vs Madresal · flow-through"),
    (7, 372, "Conclusiones y próximos pasos"),
    (8, 429, "Anexo · Estado de resultados y honorarios CRC"),
    (9, 486, "Anexo · Datos mensuales y conciliación CRC"),
    (10, 543, "El turismo internacional en 2027"),
    (11, 600, "Costa Rica · el destino crece, pero desacelera"),
    (12, 657, "Costa Rica · indicadores económicos 2027"),
    (13, 714, "Productividad y eficiencia"),
    (14, 771, "Posiciones y FTE por departamento"),
    (15, 828, "Riesgos y análisis de sensibilidad"),
]
PIE = {9: ("I", 542), 10: ("J", 599), 11: ("J", 656), 12: ("J", 713),
       13: ("J", 770), 14: ("J", 827), 15: ("J", 884)}
ULTIMA_FILA = 884

# Orden físico del estándar (sección «Orden de las AM y trazabilidad»)
ORDEN = [HOJA, "00 Indice", "AM02 Resumen FY", "AM07 Flow-through",
         "AM08 Hotel vs Madresal", "AM01 Rooms KPIs", "AM01-1 Membresías Stats",
         "AM10 Posiciones y FTE", "AM04 Honorarios CRC", "AM06 Conciliación CRC",
         "AM11 Contexto", "AM05 Contrato y riesgos", "AM03 P&L mensual",
         "AM03-1 P&L USALI por depto", "AM09 Gastos por depto",
         "AM09-1 Checkbook OPEX", "AM99 Datos", "AM98 Mapeo", "Data Sources"]

# Índice: hoja, qué responde, siguiente nivel
INDICE = [
    (HOJA, "Guion completo de la reunión, de los KPI del año a las decisiones", "Cada bloque abre su AM"),
    ("00 Indice", "Menú de navegación por capa y sección", "Cualquier vista del maestro"),
    ("AM02 Resumen FY", "Ingresos, GOP, EBITDA y margen con comparativo y variación", "AM07 Flow-through"),
    ("AM07 Flow-through", "Puente reconciliado del EBITDA F26 al B27", "AM08, AM01 o AM09 según la variación"),
    ("AM08 Hotel vs Madresal", "Ingreso, GOP y EBITDA por unidad, con las asignaciones", "AM01 y AM01-1"),
    ("AM01 Rooms KPIs", "Noches, ocupación, ADR, RevPAR e ingreso de Rooms", "Estadisticas Rooms y AM03"),
    ("AM01-1 Membresías Stats", "Socios de cobro, ingreso y contribución del Club", "Estadisticas Club y AM03-1"),
    ("AM10 Posiciones y FTE", "Costo de planilla, FTE y variación por departamento", "Posiciones y Checkbook Planilla"),
    ("AM04 Honorarios CRC", "Honorarios por concepto, base de cálculo y calendario", "AM06 Conciliación CRC"),
    ("AM06 Conciliación CRC", "Diferencias entre contrato, presupuesto y cuenta registrada", "AM05 y GL"),
    ("AM11 Contexto", "Supuestos externos y sensibilidad del tipo de cambio", "Fuente de cada supuesto"),
    ("AM05 Contrato y riesgos", "Condiciones pendientes, impacto y decisiones requeridas", "Soporte contractual"),
    ("AM03 P&L mensual", "P&L consolidado enero–diciembre y FY por escenario", "AM03-1"),
    ("AM03-1 P&L USALI por depto", "P&L mensual por departamento y línea USALI", "AM09"),
    ("AM09 Gastos por depto", "Variación por departamento, categoría y cuenta", "AM09-1, planilla o GL"),
    ("AM09-1 Checkbook OPEX", "Partidas con importe mensual, cuenta, servicio y supuesto", "Checkbook OPEX"),
    ("AM99 Datos", "Base mensual normalizada que alimenta las vistas (oculta)", "AM98 y tablas de origen"),
    ("AM98 Mapeo", "Relación entre cuentas, departamentos y líneas de reporte", "GL y Data Sources"),
    ("Data Sources", "Fuente, versión, corte y responsable de cada insumo", "Archivo, exportación o consulta"),
]


def reintentar(fn, intentos=6, espera=2.0):
    """COM rechaza llamadas cuando Excel está ocupado; no es error de código."""
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            if i == intentos - 1:
                raise
            print("   ... reintento %d: %s" % (i + 1, str(e)[:70]))
            time.sleep(espera)


def main():
    excel = reintentar(lambda: win32.gencache.EnsureDispatch("Excel.Application"))
    excel.DisplayAlerts = False
    wb = reintentar(lambda: excel.Workbooks.Open(RUTA, UpdateLinks=0))
    if wb.ReadOnly:
        print("ABORTA: el libro está abierto en otra parte (ReadOnly). Cerralo.")
        wb.Close(False)
        return 1
    try:
        nombres = [s.Name for s in wb.Worksheets]

        # 1 - Reporte -> Presentación
        if VIEJO in nombres and HOJA not in nombres:
            wb.Worksheets(VIEJO).Name = HOJA
            print("1. renombrada «%s» -> «%s»" % (VIEJO, HOJA))
        else:
            print("1. ya se llama «%s»" % HOJA)
        ws = wb.Worksheets(HOJA)

        # 2 - Menú de 15 secciones en dos columnas, al inicio de cada página
        ws.Range("B41:I49").ClearContents()
        izq, der = PAGINAS[:8], PAGINAS[8:]
        for bloque, cols in ((izq, ("B", "C")), (der, ("H", "I"))):
            cn, ct = cols
            for i, (pag, fila, titulo) in enumerate(bloque):
                r = 41 + i
                ws.Range("%s%d" % (cn, r)).Value = pag
                celda = ws.Range("%s%d" % (ct, r))
                ws.Hyperlinks.Add(Anchor=celda, Address="",
                                  SubAddress="'%s'!A%d" % (HOJA, fila),
                                  TextToDisplay=titulo)
        ws.Range("B50").Value = ("Clic en una sección para ir a esa página · "
                                 "Ctrl+Inicio vuelve al contenido")
        print("2. menú reconstruido: %d secciones enlazadas al inicio de su página"
              % len(PAGINAS))

        # 3 - Pies: tres páginas nuevas decían «1, 2, 3 de 15»
        arregladas = []
        for pag in sorted(PIE):
            col, fila = PIE[pag]
            texto = "Reporte a dueños F26 vs B27 · Página %d de %d" % (pag, len(PAGINAS))
            if ws.Range("%s%d" % (col, fila)).Value != texto:
                arregladas.append(pag)
                ws.Range("%s%d" % (col, fila)).Value = texto
        print("3. pies corregidos: %s" % (arregladas or "ninguno hacía falta"))

        # 4 - El área de impresión cortaba en la 542: 6 páginas no salían
        ws.PageSetup.PrintArea = "$A$1:$N$%d" % ULTIMA_FILA
        # «Ajustar a N páginas de alto» no sirve acá: Excel reescala y mete dos
        # secciones en una hoja. Escala fija al 53% —el ancho A:N entra— y los
        # cortes los pone el salto manual de cada sección.
        # Medido exportando el PDF y contando páginas, no leyendo Pages.Count:
        #   fitW=1 + alto libre  -> 16 (la última sección se pasa por un pelo)
        #   fitW=1 + alto 15     -> 13 (en modo «ajustar alto» Excel se come
        #                               los saltos manuales y junta secciones)
        #   escala 48 fija       -> 15, una por sección. Es esta.
        ws.ResetAllPageBreaks()          # ⚠ esto devuelve la escala al 100%
        for _, fila, _ in PAGINAS[1:]:
            ws.HPageBreaks.Add(Before=ws.Rows(fila))
        ws.PageSetup.FitToPagesWide = False
        ws.PageSetup.FitToPagesTall = False
        ws.PageSetup.Zoom = 48           # por eso la escala va DESPUÉS
        print("4. impresión: área hasta la fila %d, %d páginas reales (esperadas %d)"
              % (ULTIMA_FILA, ws.PageSetup.Pages.Count, len(PAGINAS)))

        # 5 - Índice navegable
        idx = wb.Worksheets("00 Indice")
        for h in list(idx.Hyperlinks):
            h.Delete()
        idx.Cells.ClearContents()
        idx.Range("A1").Value = "Amarena Hotel & Madresal Beach Club · Master File Budget 2027"
        idx.Range("A2").Value = ("Recorrido de macro a micro. Cada hoja abre desde aquí "
                                 "y vuelve con el enlace de su celda A3.")
        for j, t in enumerate(["#", "Pestaña", "Qué responde", "Siguiente nivel"]):
            idx.Cells(4, j + 1).Value = t
        for i, (hoja, que, sig) in enumerate(INDICE):
            r = 5 + i
            idx.Cells(r, 1).Value = i + 1
            idx.Hyperlinks.Add(Anchor=idx.Cells(r, 2), Address="",
                               SubAddress="'%s'!A1" % hoja, TextToDisplay=hoja)
            idx.Cells(r, 3).Value = que
            idx.Cells(r, 4).Value = sig
        idx.Columns("A").ColumnWidth = 5
        idx.Columns("B").ColumnWidth = 30
        idx.Columns("C").ColumnWidth = 62
        idx.Columns("D").ColumnWidth = 38
        idx.Rows(4).Font.Bold = True
        idx.Range("A1").Font.Bold = True
        print("5. índice: %d hojas enlazadas" % len(INDICE))

        # 6 - Enlace de regreso en cada AM (A3 libre en todas menos AM03-1)
        vueltas = 0
        for hoja, _, _ in INDICE[2:]:
            h = wb.Worksheets(hoja)
            destino = None
            if str(h.Cells(3, 1).Value or "").startswith("<- Volver"):
                vueltas += 1
                continue
            for fila in (3, 4, 5):
                if h.Cells(fila, 1).Value in (None, ""):
                    destino = h.Cells(fila, 1)
                    break
            if destino is None:
                print("   AVISO %s: sin celda libre en A3:A5, queda sin enlace" % hoja)
                continue
            h.Hyperlinks.Add(Anchor=destino, Address="",
                             SubAddress="'%s'!A1" % HOJA,
                             TextToDisplay="<- Volver a Presentación")
            vueltas += 1
        print("6. enlaces de regreso: %d hojas" % vueltas)

        # 7 - Orden físico del estándar
        for i, nombre in enumerate(ORDEN):
            if nombre in nombres or nombre == HOJA:
                wb.Worksheets(nombre).Move(Before=wb.Worksheets(i + 1))
        print("7. pestañas reordenadas")

        # 8 - El libro abre en Presentación
        for s in wb.Worksheets:
            if s.Visible == -1:
                s.Activate()
                excel.ActiveWindow.ScrollRow = 1
                excel.ActiveWindow.ScrollColumn = 1
        ws.Activate()
        excel.ActiveWindow.ScrollRow = 1
        excel.ActiveWindow.ScrollColumn = 1
        ws.Range("A1").Select()
        print("8. el libro abre en Presentación, fila 1")

        wb.Save()
        print("\nGUARDADO.")
    finally:
        wb.Close(True)
        excel.Quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
