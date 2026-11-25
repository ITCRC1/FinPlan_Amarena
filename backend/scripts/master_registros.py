# -*- coding: utf-8 -*-
"""Los dos registros tabulares que pide el estándar (secciones «Registro de
decisiones y pendientes» y «Registro de fuentes y archivos»).

El contenido NO se inventa: las decisiones y pendientes salen de los bullets
que ya están en AM05 §4 y §5, y las fuentes de lo que el libro ya usa. Lo que
el estándar pide y el archivo no sabe —la fecha objetivo— queda «por definir».
"""
import sys
import time
import win32com.client as win32

RUTA = r"C:\Users\User\Desktop\FINPLAN\Amarena\2026-11-11_Amarena_ Master File Budget 2027.xlsx"

CAB_DEC = ["ID", "Lámina o vista", "Decisión o dato faltante", "Impacto",
           "Responsable", "Fecha objetivo", "Estado", "Evidencia de cierre"]

# (id, lámina, decisión/pendiente, impacto, responsable, estado)
DECISIONES = [
    ("D-01", "Presentación · 07", "Aprobar o devolver el Budget 2027",
     "10 días hábiles: sin respuesta queda aprobado solo", "Dueños", "Abierta", ""),
    ("D-02", "AM09 · S&M", "Validar el plan de S&M y fijar el tope de pauta",
     "$215 000 (+234% vs F26); contrato dice $2 500/mes", "Dueños y CRC", "Abierta", ""),
    ("D-03", "AM03-1 · A&B", "Definir el futuro de A&B",
     "Budget en $0; F26 tuvo $14 311 de ingreso y $34 421 de gasto", "Dueños", "Abierta", ""),
    ("D-04", "AM01-1 · Club", "Presupuestar el costo de ventas del Club",
     "$8 879 en F26, $0 en el Budget, con ingreso +13%", "Contraloría", "Abierta", ""),
    ("D-05", "AM06 · Honorarios", "Pedir a CRC la conciliación de lo facturado vs contrato",
     "Management, marketing, mobilization y comisiones", "Contraloría", "Abierta", ""),
    ("D-06", "AM07 · Equilibrio", "Definir el fondeo del déficit de EBITDA 2027",
     "~$232 460 y la ruta al punto de equilibrio", "Dueños", "Abierta", ""),
    ("P-01", "AM06 · Honorarios", "Management fee F26 oct–dic a ~$10 930/mes",
     "Sobrestimado ~$8 800 contra el mínimo de $8 000", "Contraloría", "Pendiente", ""),
    ("P-02", "AM06 · Honorarios", "Marketing fee F26 en $18 000",
     "Por contrato $2 500/mes desde marzo = $25 000", "Contraloría", "Pendiente", ""),
    ("P-03", "AM06 · Honorarios", "Mobilization fee de $45 000 no aparece en el GL",
     "Confirmar si se pagó y dónde quedó registrado", "Contraloría", "Pendiente", ""),
    ("P-04", "AM09 · cta. 7080", "Comisiones «CRC» ≈15% del ingreso de Rooms",
     "Contrato topa en 10%; probable mezcla con OTA. Separar", "Contraloría", "Pendiente", ""),
    ("P-05", "AM03-1", "Private Bar, lavandería y misceláneos sin ingreso en el Budget",
     "Líneas con gasto y sin venta", "Contraloría", "Pendiente", ""),
    ("P-06", "AM09 · Servicios", "Agua $24 137 → $28 696 (1x) con el ingreso 2x; Seguridad a $0",
     "Revisar el supuesto de consumo y el de seguridad", "Contraloría", "Pendiente", ""),
    ("P-07", "AM10 · Planilla", "Planilla sin cafetería; capital, financieros y depreciación en $0",
     "$20 000 + $8 158 + $940 que el Budget no carga", "Contraloría", "Pendiente", ""),
]

CAB_FTE = ["ID", "Módulo", "Fuente o archivo", "Escenario y versión", "Corte",
           "Hoja, tabla o clave", "Responsable", "Estado", "Dónde se ve en el libro"]

FUENTES = [
    ("F-01", "P&L y GL", "FinPlan (backend) vía Power Query", "Actual 2026 · Forecast 2026 · Budget 2027 Working",
     "2026-11-11", "tGL → AM99 Datos", "Contraloría", "Confirmado", "AM03, AM03-1, AM09"),
    ("F-02", "Estadísticas de Rooms", "FinPlan · estadísticas", "Forecast 2026 y Budget 2027 Working",
     "2026-11-11", "tEstadisticas → Estadisticas Rooms", "Contraloría", "Confirmado", "AM01 Rooms KPIs"),
    ("F-03", "Membresías del Club", "FinPlan · estadísticas del Club", "Budget 2027 Working",
     "2026-11-13", "membresias_mes → Estadisticas Club", "Contraloría", "Confirmado", "AM01-1"),
    ("F-04", "Planilla", "FinPlan · posiciones y checkbook de planilla", "Forecast 2026 y Budget 2027 Working",
     "2026-11-11", "tPosiciones → Posiciones", "Contraloría", "Confirmado", "AM10"),
    ("F-05", "OPEX", "FinPlan · checkbook de OPEX", "Budget 2027 Working",
     "2026-11-13", "Checkbook OPEX", "Contraloría", "Confirmado", "AM09-1"),
    ("F-06", "Contrato", "Management Agreement CRC – Amarena", "Vigente",
     "Firma original", "Documento fuera del libro", "Contraloría", "Confirmado", "AM04, AM05, AM06"),
    ("F-07", "Contexto internacional y CR", "ONU Turismo, BCCR, ICT (web)", "Proyección 2027",
     "2026-11-13", "AM11 Contexto", "Contraloría", "Estimado", "Presentación · páginas 10 a 12"),
    ("F-08", "Ocupación y ADR de Jacó", "ICT o Cámara de Turismo del Pacífico Central", "—",
     "—", "—", "Contraloría", "Pendiente", "AM11 · comparativo de plaza sin fuente"),
]


def reintentar(fn, intentos=6, espera=2.0):
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            if i == intentos - 1:
                raise
            print("   ... reintento %d: %s" % (i + 1, str(e)[:70]))
            time.sleep(espera)


def tabla(ws, fila0, titulo, cabecera, filas, anchos):
    ws.Cells(fila0, 1).Value = titulo
    ws.Cells(fila0, 1).Font.Bold = True
    for j, t in enumerate(cabecera):
        c = ws.Cells(fila0 + 1, j + 1)
        c.Value = t
        c.Font.Bold = True
    for i, datos in enumerate(filas):
        for j, v in enumerate(datos):
            ws.Cells(fila0 + 2 + i, j + 1).Value = v
    for j, a in enumerate(anchos):
        ws.Columns(j + 1).ColumnWidth = a
    ult = fila0 + 1 + len(filas)
    ws.Range(ws.Cells(fila0 + 1, 1), ws.Cells(ult, len(cabecera))).VerticalAlignment = -4160
    return ult


def main():
    excel = reintentar(lambda: win32.gencache.EnsureDispatch("Excel.Application"))
    excel.DisplayAlerts = False
    wb = reintentar(lambda: excel.Workbooks.Open(RUTA, UpdateLinks=0))
    if wb.ReadOnly:
        print("ABORTA: el libro está abierto en otra parte. Cerralo.")
        wb.Close(False)
        return 1
    try:
        # 1 ─ Registro de decisiones y pendientes, al pie de AM05
        ws = wb.Worksheets("AM05 Contrato y riesgos")
        ws.Range("A49:L80").ClearContents()
        ult = tabla(ws, 49,
                    "6. Registro de decisiones y pendientes (una fila por punto; "
                    "las fechas las pone Contraloría)",
                    CAB_DEC, DECISIONES, [8, 22, 52, 48, 16, 14, 12, 26])
        print("AM05: %d filas de decisiones y pendientes, hasta la %d"
              % (len(DECISIONES), ult))

        # 2 ─ Registro de fuentes, debajo del log de Power Query
        ds = wb.Worksheets("Data Sources")
        ds.Range("A5:K30").ClearContents()
        ult = tabla(ds, 5,
                    "Registro de fuentes del estándar (una fila por insumo)",
                    CAB_FTE, FUENTES, [8, 26, 42, 42, 14, 34, 16, 13, 34])
        print("Data Sources: %d filas de fuentes, hasta la %d" % (len(FUENTES), ult))

        wb.Save()
        print("\nGUARDADO.")
    finally:
        wb.Close(True)
        excel.Quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
