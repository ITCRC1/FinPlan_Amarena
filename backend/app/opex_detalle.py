# -*- coding: utf-8 -*-
"""El rango oficial de sub-líneas de una cuenta de OPEX: 800 a 810.

Owner, 2026-11-12: *«debe ir de 800 a 810»*.

## Por qué esto existe

El rango está escrito en el CLAUDE.md desde el principio —«cada cuenta 7xxx
puede tener hasta 11 líneas de detalle (800 a 810)»— y **ninguna de las cuatro
rutas que crean una línea lo conocía**. Cada una inventaba su propio código:

| ruta | qué ponía |
|---|---|
| «+10 líneas» | `max(código)+1`, sin techo → 811, 812, 813… |
| «Abrir cuentas del catálogo» | fijo `001` |
| Subir Excel, fila sin código | contador `001, 002, 003…` |
| Carga de actuales del GL | cadena vacía |

El resultado, en Amarena: una cuenta con **101 filas** y dos numeraciones
conviviendo dentro de la misma cuenta. Y el defecto más feo era el del botón:
al pedir el máximo hacía `int(código)`, que con una cadena vacía revienta; el
`except` dejaba el máximo en **cero** y arrancaba una segunda serie desde 001
al lado de la que ya estaba.

Arreglarlo en cada ruta por separado es cómo se llegó hasta acá. Vive en un
módulo propio para que una ruta nueva no tenga que acordarse de nada: pide el
próximo código y recibe uno válido, o `None` si la cuenta ya está llena.
"""
from __future__ import annotations

#: Primera y última sub-línea. Once por cuenta.
PRIMERO = 800
ULTIMO = 810

#: Los once, en orden. Es la lista contra la que se valida y se completa.
CODIGOS: list[str] = [str(n) for n in range(PRIMERO, ULTIMO + 1)]


def es_valido(code: str | None) -> bool:
    return (code or "").strip() in CODIGOS


def libres(existentes) -> list[str]:
    """Los códigos de 800-810 que esta cuenta todavía no usa, en orden.

    Lo que venga fuera del rango —un `001` viejo, una cadena vacía— no cuenta
    como ocupado: justamente lo que se quiere es poder reubicarlo adentro.
    """
    usados = {(c or "").strip() for c in existentes}
    return [c for c in CODIGOS if c not in usados]


def siguiente(existentes) -> str | None:
    """El próximo código libre, o `None` si la cuenta ya tiene los once.

    ⚠️ **Devuelve `None` en vez de seguir contando.** El botón viejo entregaba
    811 y el usuario lo veía como una línea más, igual a las otras; el archivo
    de Excel la traía de vuelta y el desorden quedaba fijado. Que no haya cupo
    es una respuesta legítima: once sub-líneas es el límite, y pedir la número
    doce es un error que conviene ver en el momento, no tres meses después en
    un reporte que no cuadra.
    """
    disponibles = libres(existentes)
    return disponibles[0] if disponibles else None


def varios(existentes, cuantos: int) -> list[str]:
    """Hasta `cuantos` códigos libres. Devuelve menos si no alcanzan.

    Pedir diez cuando quedan tres entrega tres. Fallar entero obligaría al
    usuario a adivinar cuántas caben antes de pedirlas.
    """
    return libres(existentes)[:max(0, cuantos)]
