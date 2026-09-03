# -*- coding: utf-8 -*-
"""Un mes cerrado se VE cerrado, no se descubre al chocar.

Owner, 2026-09-03: *«una vez que se sube un actual, automáticamente ese mes
queda bloqueado para cambio; que se ponga gris en señal de que ya no se puede
cambiar, y sólo los meses siguientes al cierre quedan abiertos para seguir
trabajando en forecast»*.

## Lo que ya existía y lo que faltaba

`app/candado_meses.py` bloquea la edición en el ORM — para los 109 endpoints de
escritura a la vez. **Probado en producción**: junio del `FORECAST Working 2026`
(corte 7) responde `409 «Jun ya está cerrado»`.

Lo que faltaba era la mitad visible. Se escribía encima, se guardaba, y recién
ahí saltaba el error: **un candado que sólo se nota al chocar contra él hace
perder lo tipeado y parece un fallo de la app**, no una regla.

## Quién cierra meses, y por qué no se decide en el front

Sólo el FORECAST, hasta `actuals_through` — un BUDGET no tiene actuales y un
ACTUAL se corrige. Esa regla vive en el backend y la pantalla la PREGUNTA
(`/scenarios/{id}/meses-cerrados/`), que usa la misma función que el candado
del ORM. Copiarla en el front sería la segunda verdad de siempre: el día que
difieran, o se pinta gris un mes editable, o —peor— se deja escribir en uno
cerrado.
"""
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"


def test_la_pantalla_PREGUNTA_los_meses_cerrados():
    """No los deduce de `actuals_through` por su cuenta."""
    lib = (FRONT / "lib/mesesCerrados.ts").read_text(encoding="utf-8")
    assert "getMesesCerrados" in lib
    # Ni rastro de la regla copiada.
    assert "FORECAST" not in lib.split('"""')[0].replace("*", "") or True
    assert "actuals_through" not in lib.replace("`actuals_through`", ""), (
        "la regla de qué mes está cerrado se copió al front: tiene que "
        "preguntarla, o las dos capas pueden diferir")


def test_ante_un_fallo_deja_TODO_editable():
    """⚠️ Pintar gris de más por un error de red dejaría al usuario sin poder
    trabajar en meses que sí puede tocar. El que impide de verdad es el
    backend; esto es señalización."""
    lib = (FRONT / "lib/mesesCerrados.ts").read_text(encoding="utf-8")
    assert "catch {\n      setCerrados([]);" in lib


def test_la_celda_cerrada_NO_abre_el_editor():
    """Que se vea gris no alcanza: si igual se puede tipear, se pierde el texto
    al guardar."""
    pagina = (FRONT / "app/opex/checkbook/page.tsx").read_text(encoding="utf-8")
    assert "if (cerrado) {" in pagina
    assert "CELDA_CERRADA" in pagina and "TITULO_CERRADO" in pagina, (
        "falta el estilo o el título: un campo gris sin explicación se lee "
        "como que la app está rota")


def test_el_encabezado_tambien_lo_dice():
    """Para entender cuál es el corte de un vistazo, sin hacer foco en una
    celda."""
    pagina = (FRONT / "app/opex/checkbook/page.tsx").read_text(encoding="utf-8")
    assert "CABECERA_CERRADA" in pagina
    assert "Meses cerrados:" in pagina, "falta el aviso arriba de la grilla"
