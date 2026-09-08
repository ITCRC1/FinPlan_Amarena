# -*- coding: utf-8 -*-
"""Completa `orden_plantilla.json` con las cuentas del mapeo que faltaban.

## El lazo que esto rompe

La plantilla del Detalle —la que el owner baja, llena y vuelve a subir— sólo
ofrece las cuentas que están en esta lista. La lista salió del archivo que el
owner mandó el 2026-08-14, y ese archivo traía las cancelaciones y los no-show
codificados como `4000`, la misma cuenta que Room Revenue.

Resultado: `4001` y `4002` nunca entraron a la lista, así que la plantilla nunca
las ofreció, así que no había dónde digitarlas — y sin fila donde digitarlas,
nunca entraban al archivo. El lazo se cierra solo.

## La regla para agregar, y por qué es esa

Se agrega una cuenta del mapeo si —y sólo si— su departamento **ya tiene esa
clase** en la lista. Es la misma baranda que ya vive en `scenarios_api`:

    Owner (2026-08-14): «Utilities no tiene planilla, solo Opex, de dónde
    sacaste eso».

El mapeo tiene reglas 6xxx para casi todo departamento «por si acaso»; su
estructura no. Sembrar todas las cuentas del mapeo le inventaría una sección de
planilla a Utilities. Acá se completan las clases que el departamento tiene, no
se le agregan clases.

Cada cuenta nueva se inserta **detrás de la última de su misma clase en su mismo
departamento**, para que caiga dentro de su sección y no al final de la hoja.
"""
import io
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ORDEN = RAIZ / "app" / "seed_data" / "orden_plantilla.json"

# (dept_code, cuenta, clase) — calculado cruzando el mapeo activo contra la
# lista, con la regla de arriba. Ver el encabezado.
NUEVAS = json.loads((pathlib.Path(__file__).parent / "orden_faltantes.json")
                    .read_text(encoding="utf-8"))


def main(aplicar: bool) -> int:
    datos = json.loads(ORDEN.read_text(encoding="utf-8"))
    orden = datos["orden"]
    ya = {(f["dept_code"], str(f["cuenta"])) for f in orden}
    antes = len(orden)

    puestas, saltadas, sin_lugar = 0, 0, []
    for dep, cta, nom, clase in NUEVAS:
        if (dep, str(cta)) in ya:
            saltadas += 1
            continue
        # Detrás de la última de la misma clase en el mismo departamento.
        pos = None
        for i, f in enumerate(orden):
            if f["dept_code"] == dep and str(f["cuenta"])[0] == str(cta)[0]:
                pos = i
        if pos is None:
            sin_lugar.append((dep, cta))
            continue
        orden.insert(pos + 1, {"dept_code": dep, "cuenta": str(cta),
                               "clase": clase})
        ya.add((dep, str(cta)))
        puestas += 1

    print("antes: %d filas" % antes)
    print("se agregan: %d   ya estaban: %d   sin lugar: %d"
          % (puestas, saltadas, len(sin_lugar)))
    if sin_lugar:
        print("   sin clase en su departamento (no se inventa): %s" % sin_lugar)
    print("despues: %d filas" % len(orden))

    # Comprobación: que las de Rooms hayan caído dentro de su sección de ingreso.
    r = [(i, f) for i, f in enumerate(orden) if f["dept_code"] == "0110"][:6]
    print()
    print("el arranque del departamento 0110, como queda:")
    for i, f in r:
        print("   %4d  %-6s %-8s %s" % (i, f["dept_code"], f["cuenta"],
                                        f["clase"]))

    if not aplicar:
        print()
        print("EN SECO: no se escribió el archivo.")
        return 0

    datos["orden"] = orden
    ORDEN.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print()
    print("escrito: %s" % ORDEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--aplicar" in sys.argv))
