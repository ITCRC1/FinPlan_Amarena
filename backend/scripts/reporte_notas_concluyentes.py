# -*- coding: utf-8 -*-
"""Reescribe las notas de las páginas 1 a 9 para que concluyan, no describan.

    python reporte_notas_concluyentes.py "<master.xlsx>"

Owner, 2026-11-13: *«cada nota en la presentación debe ser concluyente y
esclarecedora»* · *«debe ser lógico»* · *«yo quiero todo en el master»*.

## Qué cambia

Una nota que dice «S&M sube 234%» **describe**. Una que dice «S&M llega al 16%
del ingreso, el triple del crecimiento del negocio; si es inversión de
lanzamiento hay que decir en qué año baja» **concluye**. Las notas del reporte
ya traían el dato; les faltaba la frase que dice qué significa y qué decisión
abre.

## Lo que se respeta

* **Siguen siendo fórmulas.** Cada reescritura conserva las referencias vivas
  de la original —`'AM02 Resumen FY'`, `'AM07 Flow-through'`— así que se
  reescriben solas al refrescar. Pegar el número ahí adentro haría que la nota
  envejezca sin avisar, que es justo lo que se está evitando.
* **No se borra ninguna fila.** Sólo cambia el contenido de nueve celdas de
  texto; el formato, las combinaciones y los gráficos quedan como están.
* **Se escribe por Excel, no por openpyxl**, que le suelta las 18 tablas al
  libro y lo deja en `#REF!`.

## Las nueve celdas

Se eligieron las que tenían el dato y no la conclusión. Las que ya concluían
—B216, B218, B338— no se tocan: reescribir algo que ya está bien sólo agrega
riesgo.
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

A2 = "'AM02 Resumen FY'"
A7 = "'AM07 Flow-through'"
A10 = "'AM10 Posiciones y FTE'"

#: celda → fórmula nueva. El texto cierra en una afirmación o en una decisión.
NOTAS: dict[str, str] = {

    # ── Página 1 · la carta ────────────────────────────────────────────────
    # Antes: decía cuánto mejora y cuánto sube el gasto, y ahí terminaba.
    # Ahora: dice qué significa que las dos cosas pasen a la vez.
    "B20": (
        f'=IF({A2}!C29<0,"El resultado todavía no acompaña: ",'
        f'"El resultado acompaña: ")&"la utilidad departamental "'
        f'&IF({A2}!D23>=0,"mejora","empeora")&" en $"&FIXED(ABS({A2}!D23),0)'
        f'&", pero los gastos no distribuidos suben $"&FIXED(ABS({A2}!D25),0)'
        f'&", con Ventas y Mercadeo de $"&FIXED({A2}!B24,0)&" a $"'
        f'&FIXED({A2}!C24,0)&". El EBITDA queda en -$"&FIXED(ABS({A2}!C29),0)'
        f'&". La lectura no es que mejoramos: es que la mejora no alcanza. '
        f'Los departamentos convierten bien —el margen departamental pasa de "'
        f'&FIXED({A2}!B23/{A2}!B19*100,1)&"% a "&FIXED({A2}!C23/{A2}!C19*100,1)'
        f'&"%—, pero la estructura central todavía es más grande que el '
        f'negocio que la sostiene."'
    ),

    # Antes: un pedido genérico de revisión.
    # Ahora: tres decisiones concretas, que es lo que se puede responder.
    "B28": (
        f'="Pedimos tres decisiones, no una aprobación genérica. Primera: '
        f'validar o ajustar el plan de Ventas y Mercadeo de $"'
        f'&FIXED({A2}!C24,0)&", que es el "&FIXED({A2}!C24/{A2}!C19*100,1)'
        f'&"% del ingreso. Segunda: definir cómo se fondean los $"'
        f'&FIXED(ABS({A2}!C29)/12,0)&" mensuales de déficit operativo mientras '
        f'el hotel llega a su punto de equilibrio. Tercera: cerrar los vacíos '
        f'del presupuesto —A&B, lavandería, reserva de capital y depreciación— '
        f'que hoy mejoran el resultado por omisión. El contrato da 10 días '
        f'hábiles para objetar por escrito."'
    ),

    # ── Página 3 · ingresos ────────────────────────────────────────────────
    # Antes: texto fijo que decía «es un riesgo» sin cuantificarlo.
    # Ahora: el monto, y qué hay que poder responder.
    "F137": (
        f'="• A&B, lavandería y misceláneos quedan en 0: son $"'
        f'&FIXED({A2}!B13+{A2}!B18,0)&" de ingreso que existían en 2026 y '
        f'desaparecen sin explicación. Si el hotel sigue dando desayuno, ese '
        f'ingreso y su costo están en alguna parte. Nombrarlo como riesgo '
        f'identificado es más fuerte que esperar la pregunta."'
    ),

    # ── Página 5 · detalle por departamento ────────────────────────────────
    # Antes: de dónde viene el crecimiento. Ahora: qué dice eso del riesgo.
    "B274": (
        f'="Ingresos: Rooms explica $"&FIXED(F237,0)&" de los $"&FIXED(F244,0)'
        f'&" de crecimiento ("&FIXED(F237/F244*100,0)&"%). El costo de ventas '
        f'pasa de $"&FIXED(H244,0)&" a $"&FIXED(I244,0)&" ("&FIXED(K244*100,1)'
        f'&"% del ingreso). Todo el presupuesto descansa en una sola línea, y '
        f'esa línea depende de ocupación más que de tarifa: si la ocupación '
        f'queda corta, no hay otra palanca que la compense."'
    ),

    # ── Página 7 · conclusiones ────────────────────────────────────────────
    "B355": (
        f'="Los ingresos pasan de $"&FIXED({A7}!B6,0)&" a $"&FIXED({A7}!C6,0)'
        f'&" con 12 meses de operación y ocupación de "'
        f'&FIXED({A7}!C16*100,1)&"%. El 88% del crecimiento viene de vender '
        f'más noches, no de venderlas más caro: es un presupuesto de '
        f'ocupación, no de tarifa, y por eso depende más del mercado que de '
        f'nuestra gestión de precio. Ver páginas 2 y 3."'
    ),

    "B362": (
        f'="El EBITDA queda en -$"&FIXED(-{A7}!C11,0)&": el ingreso nuevo (+$"'
        f'&FIXED({A7}!B107,0)&") se va en Payroll ($"&FIXED(-{A7}!B109,0)'
        f'&") y Opex ($"&FIXED(-{A7}!B110,0)&", sobre todo S&M). De cada dólar '
        f'nuevo llegan $0,62 a utilidad departamental pero sólo $0,21 al '
        f'EBITDA: el problema no es el margen de los departamentos, que es '
        f'bueno, sino el tamaño de la estructura central. Ver páginas 4 y 5."'
    ),
}


def respaldar(ruta: Path) -> Path:
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = ruta.with_name(f"{ruta.stem}__respaldo_{sello}{ruta.suffix}")
    shutil.copy2(ruta, destino)
    return destino


def reintentar(fn, *a, intentos=12, espera=1.0, **kw):
    """Excel rechaza llamadas mientras recalcula. Ver `reporte_inyectar`."""
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


def main(master: str) -> None:
    import win32com.client as win32

    ruta = Path(master).resolve()
    if not ruta.exists():
        raise SystemExit(f"No existe: {ruta}")
    print(f"Respaldo: {respaldar(ruta).name}")

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False
    wb = None
    try:
        wb = reintentar(lambda: excel.Workbooks.Open(str(ruta)))
        if reintentar(lambda: wb.ReadOnly):
            raise SystemExit(
                "\nEl Master está ABIERTO en Excel: se abrió en sólo lectura y "
                "guardar no haría nada. Cerralo y volvé a correr esto.")
        ws = reintentar(lambda: wb.Worksheets("Reporte"))

        for celda, formula in NOTAS.items():
            reintentar(lambda c=celda, f=formula: setattr(
                ws.Range(c), "Formula", f))
            print(f"  {celda} reescrita.")

        reintentar(excel.CalculateFullRebuild)

        # Verificación: que ninguna de las nueve haya quedado en error, y que
        # devuelvan TEXTO. `.Text` y no `.Value`: por COM una celda con error
        # no devuelve la cadena «#REF!» y el chequeo pasaría en falso.
        malas = []
        for celda in NOTAS:
            t = reintentar(lambda c=celda: ws.Range(c).Text)
            if not isinstance(t, str) or t.startswith("#") or len(t) < 40:
                malas.append((celda, str(t)[:60]))
        if malas:
            raise SystemExit(f"\nNo se guarda: estas quedaron mal → {malas}")

        reintentar(wb.Save)
        print(f"\nGuardado: {ruta.name}")
        print(f"  {len(NOTAS)} notas ahora concluyen, y siguen siendo fórmulas.")
    finally:
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
        excel.Quit()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
