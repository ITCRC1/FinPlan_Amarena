# -*- coding: utf-8 -*-
"""Bloque «cómo actualizar y estado» en la página 1 de Presentación.

El estándar pide estado visible y la secuencia de actualización arriba del
guion, y que los controles de aceptación se vean antes de publicar. Los tres
se calculan solos: no hay que acordarse de correrlos.
"""
import sys
import time
import win32com.client as win32

RUTA = r"C:\Users\User\Desktop\FINPLAN\Amarena\2026-11-11_Amarena_ Master File Budget 2027.xlsx"
HOJA = "Presentación"

TITULO = "CÓMO SE ACTUALIZA Y CÓMO SABER QUE CUADRA"
PASOS = ("Datos → Actualizar todo, esperar a que terminen las consultas de "
         "FinPlan, y leer los tres controles: si alguno dice REVISAR, el "
         "reporte no se presenta.")

# (fila, etiqueta, fórmula de la diferencia)
CONTROLES = [
    (53, "Puente de EBITDA: F26 + todos los efectos = B27",
     "'AM07 Flow-through'!$B$46"),
    (54, "EBITDA del resumen = EBITDA del puente (B27)",
     "'AM02 Resumen FY'!$C$29-'AM07 Flow-through'!$C$11"),
    (55, "P&L mensual: enero–diciembre suma al año",
     "SUM('AM03 P&L mensual'!$C$16:$N$16)-'AM03 P&L mensual'!$O$16"),
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


def main():
    excel = reintentar(lambda: win32.gencache.EnsureDispatch("Excel.Application"))
    excel.DisplayAlerts = False
    wb = reintentar(lambda: excel.Workbooks.Open(RUTA, UpdateLinks=0))
    if wb.ReadOnly:
        print("ABORTA: el libro está abierto en otra parte. Cerralo.")
        wb.Close(False)
        return 1
    try:
        ws = wb.Worksheets(HOJA)
        ws.Range("B51:M55").ClearContents()

        ws.Range("B51").Value = TITULO
        ws.Range("B51").Font.Bold = True
        ws.Range("B52").Value = PASOS

        for fila, etiqueta, dif in CONTROLES:
            ws.Range("B%d" % fila).Value = etiqueta
            # Un centavo de tolerancia: el modelo arrastra decimales.
            ws.Range("I%d" % fila).Formula = (
                '=IF(ABS(%s)<0.01,"OK · cuadra","REVISAR · difiere "'
                '&TEXT(%s,"$#,##0.00"))' % (dif, dif))
        print("escritos: título, pasos y %d controles" % len(CONTROLES))

        excel.CalculateFullRebuild()
        for fila, etiqueta, _ in CONTROLES:
            print("  %-48s %s" % (etiqueta[:48], ws.Range("I%d" % fila).Text))

        wb.Save()
        print("\nGUARDADO.")
    finally:
        wb.Close(True)
        excel.Quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
