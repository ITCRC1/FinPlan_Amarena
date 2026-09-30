# -*- coding: utf-8 -*-
"""Un cuadro financiero DIBUJADO, para pegarlo en el Word como imagen.

Owner, 2026-09-30, pidiendo las secciones de detalle: *«quizás no quisiera crear
o agregar cuadros, quedan muy mal alineados. quiero que esos cuadros se
conviertan en imágenes bien definidas»*.

## Qué se gana y qué se pierde

**Se gana la alineación.** Una tabla de Word reparte el ancho sobrante entre las
columnas con sus propias reglas: basta un rótulo largo para que una columna se
ensanche, el resto se corra y dos cuadros seguidos dejen de coincidir. Acá cada
columna mide lo que se le dice, al píxel, y quince cuadros de detalle salen
idénticos entre sí.

**Se pierde que el número se pueda seleccionar.** Una imagen no se copia, no se
busca con Ctrl+F y no se lee con un lector de pantalla. Por eso esto es para las
secciones de DETALLE —el desglose por departamento, que se mira— y no para los
cuadros de la cascada, que son los que alguien va a querer copiar a una hoja.

## ⚠️ La fuente viaja en el repo

Se dibuja en el servidor, y el contenedor no trae ninguna: `/usr/share/fonts`
está vacío. Sin el archivo, Pillow cae a su tipografía de mapa de bits y el
cuadro sale como una captura de 1998. Ver `assets/FUENTES.md`.

## ⚠️ Si la fuente no está, NO se dibuja

`hay_fuente()` devuelve `False` y quien llama arma una tabla de Word de toda la
vida. Un informe con un cuadro menos lindo se entrega; uno con un cuadro
ilegible, no — y la diferencia no se nota hasta que está impreso.
"""
from __future__ import annotations

import io
import pathlib

ASSETS = pathlib.Path(__file__).resolve().parent / "assets"

#: A cuántos píxeles por centímetro se dibuja.
#:
#: ⚠️ 120 px/cm son ~305 ppp a tamaño colocado: es donde el texto deja de verse
#: blando IMPRESO. A 60 se ve bien en pantalla y se nota en papel, que es donde
#: se lee este informe.
PX_CM = 120

#: Los mismos tonos del Word. Si se separan, el cuadro dibujado se lee como
#: pegado de otro documento.
VERDE_CAB = (0x2A, 0x4A, 0x33)
FONDO_TOTAL = (0xE4, 0xEB, 0xE6)
CEBRA = (0xF4, 0xF7, 0xF5)
RAYA = (0xC9, 0xD3, 0xCC)
TINTA = (0x1A, 0x1D, 0x21)
ROJO = (0xB3, 0x26, 0x1E)
BLANCO = (0xFF, 0xFF, 0xFF)


def _fuente(negrita: bool, px: int):
    from PIL import ImageFont
    nombre = "Tinos-Bold.ttf" if negrita else "Tinos-Regular.ttf"
    return ImageFont.truetype(str(ASSETS / nombre), px)


def hay_fuente() -> bool:
    """¿Se puede dibujar? Si no, quien llama arma una tabla de Word normal."""
    try:
        _fuente(False, 20)
        return True
    except Exception:
        return False


def _es_negativo(texto: str) -> bool:
    t = texto.strip()
    return t.startswith("(") or t.startswith("-")


def dibujar_cuadro(
    encabezados: list[str | tuple[str, str]],
    filas: list[list[str]],
    anchos_cm: list[float],
    resaltar: set[int] | None = None,
    pt: float = 9.0,
) -> bytes:
    """El cuadro como PNG. `filas` son cadenas YA formateadas, igual que en
    `_tabla` del Word: las dos leen el mismo texto y pintan el mismo rojo.

    `encabezados` admite `(arriba, abajo)` para la cabecera de dos líneas.
    """
    from PIL import Image, ImageDraw

    resaltar = resaltar or set()
    # 1 pt = 1/72 pulgada = 2.54/72 cm
    px = max(8, round(pt * 2.54 / 72 * PX_CM))
    f_normal, f_negrita = _fuente(False, px), _fuente(True, px)
    f_sub = _fuente(False, max(7, round(px * 0.85)))

    cols = [round(a * PX_CM) for a in anchos_cm]
    ancho = sum(cols)
    aire_x, aire_y = round(px * 0.55), round(px * 0.42)
    alto_fila = px + aire_y * 2
    dos_lineas = any(isinstance(h, tuple) and h[1] for h in encabezados)
    alto_cab = alto_fila + (px if dos_lineas else 0)
    alto = alto_cab + alto_fila * len(filas) + 2

    im = Image.new("RGB", (ancho, alto), BLANCO)
    d = ImageDraw.Draw(im)

    def recortar(texto: str, fuente, ancho: int) -> str:
        """El texto que CABE, con puntos suspensivos si sobra.

        ⚠️ Un dibujo no envuelve ni corta solo: sin esto, un rótulo largo sigue
        escribiéndose por encima de la celda de al lado. Se vio en el informe de
        agosto —«8025 · Fines and Other Non-Deductible Expenses» montado sobre
        su propio monto— y no hay forma de notarlo hasta mirar la imagen.
        """
        if d.textlength(texto, font=fuente) <= ancho:
            return texto
        while texto and d.textlength(texto + "…", font=fuente) > ancho:
            texto = texto[:-1]
        return (texto.rstrip() + "…") if texto else ""

    def escribir(x0: int, x1: int, y: int, texto: str, fuente, color, derecha: bool):
        if not texto:
            return
        texto = recortar(texto, fuente, x1 - x0 - aire_x * 2)
        w = d.textlength(texto, font=fuente)
        d.text((x1 - aire_x - w if derecha else x0 + aire_x, y), texto,
               font=fuente, fill=color)

    # ── La cabecera ───────────────────────────────────────────────────────
    d.rectangle([0, 0, ancho - 1, alto_cab - 1], fill=VERDE_CAB)
    x = 0
    for i, h in enumerate(encabezados):
        arriba, abajo = h if isinstance(h, tuple) else (h, "")
        derecha = i > 0
        escribir(x, x + cols[i], aire_y, arriba, f_negrita, BLANCO, derecha)
        if abajo:
            escribir(x, x + cols[i], aire_y + px, abajo, f_sub,
                     (0xD2, 0xDD, 0xD6), derecha)
        x += cols[i]

    # ── El cuerpo ─────────────────────────────────────────────────────────
    y = alto_cab
    detalle = 0
    for n, fila in enumerate(filas):
        total = n in resaltar
        if total:
            fondo = FONDO_TOTAL
        else:
            fondo = CEBRA if detalle % 2 else BLANCO
            detalle += 1
        d.rectangle([0, y, ancho - 1, y + alto_fila - 1], fill=fondo)
        # ⚠️ La raya de arriba del total es la que cierra el bloque; sin ella,
        # dos totales seguidos se leen como una sola banda.
        d.line([0, y, ancho - 1, y], fill=VERDE_CAB if total else RAYA,
               width=2 if total else 1)
        x = 0
        for i, txt in enumerate(fila[:len(cols)]):
            txt = "" if txt is None else str(txt)
            color = ROJO if _es_negativo(txt) else TINTA
            escribir(x, x + cols[i], y + aire_y, txt,
                     f_negrita if total else f_normal, color, i > 0)
            x += cols[i]
        y += alto_fila
    d.line([0, y - 1, ancho - 1, y - 1], fill=VERDE_CAB, width=2)

    salida = io.BytesIO()
    # `optimize` con paleta: un cuadro es texto sobre plano, así que baja de
    # ~700 KB a ~80 KB sin perder un píxel.
    im.convert("P", palette=Image.ADAPTIVE, colors=64).save(
        salida, "PNG", optimize=True)
    return salida.getvalue()
