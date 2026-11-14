# -*- coding: utf-8 -*-
"""Arma el PAQUETE de páginas nuevas para el reporte a dueños de Amarena.

    python reporte_armar.py "<master file.xlsx>" "<paquete.xlsx>"

Owner, 2026-11-13: *«necesito el mismo excel que adopte los cambios… y que
automatices todo para usarlo»*.

## ⚠️ Por qué este script NO toca el Master File

La primera versión copiaba el Master y le escribía las páginas adentro con
openpyxl. **Eso destruye el archivo**, y no de la forma que yo había anticipado.

Avisé que se perderían las conexiones de Power Query. Lo que no vi es que
openpyxl también suelta las **tablas** (`tGL`, `tEstadisticas`, `tPosiciones`),
y las fórmulas que ya existían las referencian por nombre. Al abrirlo, Excel
reparó el libro quitando siete rangos de datos externos y la definición de la
tabla, y el reporte entero quedó en `#REF!` y `#VALUE!`. Un archivo que abre
«reparado» y muestra ceros es peor que uno que no abre: parece que funciona.

Así que el Master **no se toca por código**. Este script produce un libro
aparte con dos hojas, para copiar a mano:

    AM11 Contexto     → clic derecho en la pestaña, «Mover o copiar» al Master
    Paginas nuevas    → seleccionar las filas, copiar, pegar en `Reporte`

Las fórmulas viajan en el portapapeles y siguen apuntando a `'AM02 Resumen
FY'`, `'AM07 Flow-through'`, `'AM10 Posiciones y FTE'` y `'AM11 Contexto'`:
una vez pegadas dentro del Master, resuelven solas.

## Lo que hay que hacer a mano, y es poco

1. Copiar la hoja `AM11 Contexto` al Master.
2. Pegar las páginas en `Reporte` **a partir de la fila 514** (la 513 queda en
   blanco como separación). El paso de página son 57 filas, igual que las
   nueve existentes, así que la impresión sigue cuadrando.
3. Buscar y reemplazar «de 9» por «de 15» en los pies de página: el reporte
   pasa de nueve páginas a quince y el pie mentiría.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import Workbook, load_workbook

from reporte_amarena_ampliado import (
    APAGADO, MARRON, ORO, PASO, celda, hoja_contexto,
)
import reporte_paginas_nuevas as P

#: La fila del Master donde empiezan las páginas nuevas. Se usa para que las
#: referencias relativas, si alguna quedara, caigan donde corresponde.
FILA_DESTINO = 514


def comprobar_master(ruta: str) -> None:
    """El paquete se arma a ciegas, pero al menos se verifica contra qué.

    Si el Master no tiene las hojas que las fórmulas nombran, lo que se entrega
    va a dar `#REF!` al pegarlo — y eso hay que saberlo ahora, no en la reunión.
    """
    wb = load_workbook(ruta, read_only=True)
    faltan = [h for h in ("AM02 Resumen FY", "AM07 Flow-through",
                          "AM10 Posiciones y FTE", "Reporte")
              if h not in wb.sheetnames]
    if faltan:
        raise SystemExit(
            "El Master File no tiene estas hojas, que las fórmulas necesitan: "
            + ", ".join(faltan))
    filas = wb["Reporte"].max_row
    wb.close()
    print(f"Master verificado: tiene las 4 hojas que hacen falta "
          f"y «Reporte» llega a la fila {filas}.")
    if filas >= FILA_DESTINO:
        print(f"  ⚠ «Reporte» ya pasa de la fila {FILA_DESTINO}: revisá dónde "
              f"pegar para no encimar nada.")


def hoja_paginas(wb):
    """Las seis páginas, en una hoja suelta lista para copiar y pegar."""
    ws = wb.create_sheet("Paginas nuevas")
    ws.sheet_view.showGridLines = False
    for col, an in (("A", 1.9), ("B", 11.4), ("N", 5.1), ("P", 24.3), ("S", 8.9)):
        ws.column_dimensions[col].width = an

    celda(ws, "B1", "PÁGINAS NUEVAS DEL REPORTE · copiá de la fila 3 hacia abajo",
          sz=12, b=True, color=MARRON)
    celda(ws, "B2",
          f"Pegalas en la hoja «Reporte» a partir de la fila {FILA_DESTINO}. "
          f"Las fórmulas apuntan a AM02, AM07, AM10 y AM11 por nombre de hoja, "
          f"así que resuelven solas una vez adentro del Master.",
          sz=9, color=APAGADO)
    return ws


def main(master: str, salida: str) -> None:
    comprobar_master(master)

    wb = Workbook()
    wb.remove(wb.active)

    # ⚠️ HOJAS ESPEJO, vacías y a propósito.
    #
    # Las fórmulas nombran `'AM02 Resumen FY'`, `'AM07 Flow-through'` y
    # `'AM10 Posiciones y FTE'`, que viven en el MASTER y no acá. Si el paquete
    # no las tiene, Excel al abrirlo no puede resolverlas y las convierte en
    # referencias a un libro externo: `'[1]AM10 Posiciones y FTE'!$D$15`. Esa
    # referencia ya viaja rota, y al pegarla en el Master queda en #REF!.
    # Pasó dos veces: 97 errores primero y 121 después.
    #
    # Con una hoja vacía del mismo nombre, Excel resuelve LOCAL en el paquete,
    # y al pegar en el Master vuelve a resolver local allá — donde la hoja sí
    # tiene datos. Es la diferencia entre una referencia a un archivo y una
    # referencia a una hoja.
    #
    # Estas hojas NO se copian al Master: sólo se copia `AM11 Contexto`.
    for espejo in ("AM02 Resumen FY", "AM07 Flow-through",
                   "AM10 Posiciones y FTE"):
        wb.create_sheet(espejo)

    ref, _fila_sens, primera_tc, _ = hoja_contexto(wb)
    ws = hoja_paginas(wb)

    r0 = 3
    P.pagina_turismo(ws, r0, ref)
    P.pagina_costa_rica(ws, r0 + PASO, ref)
    P.pagina_macro(ws, r0 + PASO * 2, ref, primera_tc)
    P.pagina_productividad(ws, r0 + PASO * 3)
    P.pagina_posiciones(ws, r0 + PASO * 4)
    P.pagina_riesgos(ws, r0 + PASO * 5, ref, primera_tc)

    wb.save(salida)

    formulas = sum(1 for f in ws.iter_rows() for c in f
                   if isinstance(c.value, str) and c.value.startswith("="))
    print(f"\nListo: {salida}")
    print(f"  · Hoja «AM11 Contexto» — copiala al Master")
    print(f"  · Hoja «Paginas nuevas» — 6 páginas, filas {r0} a {r0 + PASO*6}, "
          f"{formulas} fórmulas")
    print()
    print("CÓMO USARLO, en tres pasos:")
    print("  1. Clic derecho en la pestaña «AM11 Contexto» → Mover o copiar →")
    print("     elegí el Master File y marcá «Crear una copia».")
    print(f"  2. En «Paginas nuevas», seleccioná de la fila {r0} hasta el final,")
    print(f"     copiá, y pegá en «Reporte» en la fila {FILA_DESTINO}.")
    print("  3. En «Reporte», Buscar y reemplazar: «de 9» → «de 15» (los pies).")
    print()
    print("El Master NO se toca por código: openpyxl le suelta las tablas")
    print("(tGL, tEstadisticas, tPosiciones) y el reporte queda en #REF!.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
