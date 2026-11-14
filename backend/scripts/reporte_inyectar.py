# -*- coding: utf-8 -*-
"""Mete las páginas nuevas DENTRO del Master File, usando Excel.

    python reporte_inyectar.py "<master.xlsx>" "<paquete.xlsx>"

Owner, 2026-11-13: *«solo te pedí que la actualizaras»* · *«y mejoras el
reporte»*.

## Por qué por Excel y no por openpyxl

Porque openpyxl **destruye este libro**. La primera versión copiaba el Master y
le escribía adentro; al abrirlo, Excel lo reparó quitando siete rangos de datos
externos y la definición de la tabla, y el reporte entero quedó en `#REF!` y
`#VALUE!`. Las fórmulas que ya existían referencian las tablas `tGL`,
`tEstadisticas` y `tPosiciones` por nombre, y openpyxl no las conserva.

Un archivo que abre «reparado» y muestra ceros es peor que uno que no abre:
parece que funciona.

Acá el que guarda es **Excel**, a través de COM. Lo que Excel no entiende no
existe, así que nada se pierde: Power Query, tablas, gráficos y formato quedan
como estaban. Es la diferencia entre reescribir un libro desde afuera y
pedirle al programa que lo edite.

## Lo que hace, en orden

1. Respalda el Master con marca de tiempo. **Antes de tocar nada.**
2. Copia la hoja `AM11 Contexto` del paquete al Master.
3. Copia las seis páginas y las pega en `Reporte`, fila 514.
4. Corrige los pies: «de 9» → «de 15».
5. Recalcula y guarda.

⚠️ **El Master no puede estar abierto en Excel.** Si lo está, COM se engancha a
esa instancia y guarda encima de lo que el usuario tenga sin salvar. El script
lo detecta y se detiene.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: Dónde arrancan las páginas nuevas dentro de `Reporte`. La 513 queda en
#: blanco: el paso de página son 57 filas y así la impresión sigue cuadrando.
FILA_DESTINO = 514
#: La hoja del paquete y la fila desde la que se copia.
HOJA_PAGINAS = "Paginas nuevas"
PRIMERA_PAGINA = 3
HOJA_CONTEXTO = "AM11 Contexto"


def respaldar(ruta: Path) -> Path:
    """Una copia con fecha, antes de tocar el original.

    No es ceremonia: este script escribe sobre el archivo del que cuelga la
    presentación a los dueños, y un `Ctrl+Z` no alcanza después de guardar.
    """
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = ruta.with_name(f"{ruta.stem}__respaldo_{sello}{ruta.suffix}")
    shutil.copy2(ruta, destino)
    return destino


def reintentar(fn, *a, intentos=12, espera=1.0, **kw):
    """Llama a Excel insistiendo si está ocupado.

    ⚠️ Automatizar Excel por COM falla de forma TRANSITORIA, y de dos maneras
    que parecen errores de programación y no lo son:

    * `com_error -2147418111` — «La llamada fue rechazada por el destinatario»:
      Excel está recalculando y no atiende.
    * `AttributeError: <unknown>.Open` — el enlace tardío no resolvió el objeto
      porque la llamada anterior todavía no terminó.

    Las dos se arreglan esperando y volviendo a pedir. Sin esto el script falla
    a mitad de camino, con el libro ya modificado y sin guardar — el peor
    momento posible.
    """
    import time

    import pywintypes

    ultimo = None
    for i in range(intentos):
        try:
            return fn(*a, **kw)
        except (pywintypes.com_error, AttributeError) as e:
            ultimo = e
            time.sleep(espera * (1 + i * 0.5))
    raise RuntimeError(f"Excel no respondió tras {intentos} intentos: {ultimo}")


def main(master: str, paquete: str) -> None:
    import win32com.client as win32
    from win32com.client import constants as xl  # noqa: F401

    mruta = Path(master).resolve()
    pruta = Path(paquete).resolve()
    for p in (mruta, pruta):
        if not p.exists():
            raise SystemExit(f"No existe: {p}")

    resp = respaldar(mruta)
    print(f"Respaldo: {resp.name}")

    excel = win32.DispatchEx("Excel.Application")   # instancia PROPIA
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False
    abiertos = []
    try:
        wbM = reintentar(lambda: excel.Workbooks.Open(str(mruta)))
        abiertos.append(wbM)
        wbP = reintentar(lambda: excel.Workbooks.Open(str(pruta)))
        abiertos.append(wbP)

        hojas = {s.Name for s in wbM.Worksheets}
        if HOJA_CONTEXTO in hojas:
            print(f"  «{HOJA_CONTEXTO}» ya existía: se reemplaza.")
            reintentar(lambda: wbM.Worksheets(HOJA_CONTEXTO).Delete())

        # 1. La hoja de contexto, copiada entera al final del Master.
        reintentar(lambda: wbP.Worksheets(HOJA_CONTEXTO).Copy(
            None, wbM.Worksheets(wbM.Worksheets.Count)))
        print(f"  Hoja «{HOJA_CONTEXTO}» copiada al Master.")

        # ⚠️ Copiar una HOJA entre libros también deja referencias externas.
        #
        # AM11 nombra `'AM02 Resumen FY'` y `'AM10 Posiciones y FTE'`, que en el
        # paquete son hojas espejo vacías. Al copiarla, Excel conserva el
        # vínculo al paquete: `'[1]AM02 Resumen FY'!$C$29`. Esa celda vacía vale
        # 0, y un `IF(...>=0,"",...)` devuelve texto vacío que después revienta
        # en `FIXED()` con #VALUE!. El síntoma aparece lejos de la causa.
        #
        # Limpiar el prefijo deja la fórmula apuntando a la hoja local del
        # Master, que es la que tiene los datos.
        wsC = wbM.Worksheets(HOJA_CONTEXTO)
        for patron in (f"'{pruta.parent}\\[{pruta.name}]", f"[{pruta.name}]",
                       "[1]", "[2]", "[3]", "[4]"):
            reintentar(lambda p=patron: wsC.Cells.Replace(
                p, "", 2, 1, False, False, False, False))
        print(f"  Referencias externas de «{HOJA_CONTEXTO}», limpiadas.")

        # 2. Las páginas. Se copia el rango completo —valores, fórmulas y
        #    formato— y Excel reescribe las referencias entre hojas solo.
        wsP = wbP.Worksheets(HOJA_PAGINAS)
        ultima = wsP.Cells(wsP.Rows.Count, 2).End(-4162).Row   # xlUp
        origen = wsP.Range(f"A{PRIMERA_PAGINA}:S{ultima}")
        wsR = wbM.Worksheets("Reporte")
        reintentar(origen.Copy)
        reintentar(lambda: wsR.Range(f"A{FILA_DESTINO}").PasteSpecial(-4104))  # xlPasteAll
        excel.CutCopyMode = False
        n = ultima - PRIMERA_PAGINA + 1
        print(f"  {n} filas pegadas en «Reporte» desde la fila {FILA_DESTINO}.")

        # ⚠️ Al copiar un rango ENTRE libros, Excel convierte toda fórmula que
        # apunte a otra hoja del libro de ORIGEN en una referencia externa:
        #     'AM11 Contexto'!B41  →  '[paquete.xlsx]AM11 Contexto'!B41
        # y al cerrar el paquete esas referencias quedan en #REF!. Pasó: 98 de
        # golpe, todas las que miraban AM11.
        #
        # AM11 ya se copió al Master unas líneas más arriba, así que alcanza
        # con borrar el prefijo del archivo para que la fórmula vuelva a
        # apuntar a la hoja local. El Replace de Excel entiende fórmulas.
        pegado = wsR.Range(f"A{FILA_DESTINO}:S{FILA_DESTINO + n}")
        for patron in (f"'{pruta.parent}\\[{pruta.name}]", f"[{pruta.name}]",
                       "[1]", "[2]", "[3]", "[4]"):
            reintentar(lambda p=patron: pegado.Replace(
                p, "", 2, 1, False, False, False, False))
        print("  Referencias externas al paquete, limpiadas.")

        # 3. Los pies: el reporte ya no tiene nueve páginas.
        #
        # ⚠️ Se lee la columna ENTERA de un viaje. Pedir 513 celdas son 513
        # llamadas COM, y mientras Excel recalcula las rechaza con «La llamada
        # fue rechazada por el destinatario». Un rango completo es UNA llamada
        # y devuelve la matriz de una vez.
        col = reintentar(lambda: wsR.Range(f"I1:I{FILA_DESTINO - 1}").Value)
        tocados = 0
        for i, fila in enumerate(col, start=1):
            v = fila[0]
            if isinstance(v, str) and "Página" in v and "de 9" in v:
                wsR.Cells(i, 9).Value = v.replace("de 9", "de 15")
                tocados += 1
        print(f"  {tocados} pies corregidos de «de 9» a «de 15».")

        # ⚠️ Si el Master está abierto en otra instancia de Excel, éste lo abre
        # en SÓLO LECTURA y `Save()` no hace nada — sin avisar. Pasó: el script
        # imprimió «Guardado» y el archivo en disco seguía siendo el viejo.
        # Mentir sobre un guardado es peor que fallar.
        if wbM.ReadOnly:
            raise SystemExit(
                "\nEl Master está ABIERTO en Excel, así que se abrió en sólo "
                "lectura y guardar no haría nada.\nCerralo y volvé a correr "
                "esto; el respaldo que se acaba de hacer queda donde está.")
        reintentar(excel.CalculateFullRebuild)
        reintentar(wbM.Save)
        print(f"\nGuardado: {mruta.name}")

        # 4. Lo que importa de verdad: ¿quedó algún error en la hoja?
        # ⚠️ Se lee `.Text` y NO `.Value`.
        #
        # Por COM, una celda con error devuelve en `.Value` un objeto de error,
        # no la cadena «#REF!». Mirar `.Value` buscando textos que empiecen con
        # «#» no encuentra NADA aunque la hoja esté llena de errores: el script
        # imprimió «ninguna» con 97 #REF! adentro. Una verificación que sólo
        # sabe decir que sí es peor que no verificar.
        #
        # `.Text` devuelve lo que se ve en pantalla, que es lo que importa.
        errores = {}
        bloque = reintentar(
            lambda: wsR.Range(f"A1:S{FILA_DESTINO + n + 2}").Text)
        if isinstance(bloque, str):            # rango de una sola celda
            bloque = ((bloque,),)
        for fila in bloque:
            for v in (fila if isinstance(fila, tuple) else (fila,)):
                if isinstance(v, str) and v.startswith("#"):
                    errores[v] = errores.get(v, 0) + 1
        print(f"celdas con error en «Reporte»: {errores or 'ninguna'}")

    finally:
        for wb in abiertos:
            try:
                wb.Close(False)
            except Exception:
                pass
        excel.Quit()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
