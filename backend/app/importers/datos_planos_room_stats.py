# -*- coding: utf-8 -*-
"""Lector de la base plana de estadistica de habitaciones (Excel o CSV).

**Por que existe (owner, 2026-09-28).** El PDF de Skill4 trae UN mes y hay que
subirlo doce veces al ano. La propiedad ya mantiene un Excel —«SEGMENTACION
ACTUALIZADA», hoja `Datos (base plana)`— con la misma informacion de todos los
meses en una sola tabla. Owner: *«se podra configurar para que en vez de leer
el pdf, ahora lea el excel de datos, en la misma estructura»*.

Este lector devuelve **la misma `LecturaSkill4` que el lector de PDF**, una por
mes que traiga el archivo. Todo lo que viene despues —el calce de categorias,
el calce de canales, la pantalla, el guardado— no se entera de cual de los dos
caminos se uso.

## Forma del archivo

Una fila por mes x tipo de habitacion x agencia, con encabezado::

    Mes | Mes # | Ano | Tipo de Habitacion | Agencia | Ing.Hospedaje | Ing.AyB |
    Ing.Otros | Hab.Entradas | Hab.Estancias | Cli.Entradas | Cli.Estancias |
    Tarifa Prom.

Las columnas se buscan por NOMBRE, no por posicion: insertar una columna al
medio del Excel no puede cambiar que numero se lee. El encabezado se busca en
las primeras filas, asi que un titulo arriba de la tabla no molesta.

## ⚠️ Lo que este archivo NO trae

El PDF cierra con un resumen del hotel —capacidad, habitaciones disponibles,
bloqueadas, ingreso total— y `LecturaSkill4.cuadre()` lo usa para verificar
que el detalle leido suma lo mismo que el archivo declara. **La base plana no
tiene ese bloque**: es solo el detalle.

Eso significa que por este camino **no hay cuadre contra una segunda fuente**.
El PDF se auto-verifica por tres vias independientes; el Excel se cree entero.
Se devuelve el `Resumen` en cero —que es como se muestra un mes leido de la
base— y no se inventa: poner capacidad x dias ahi seria fabricar la cifra
justamente contra la que habria que contrastar.

Es un intercambio deliberado: menos verificacion a cambio de una sola carga en
vez de doce. La contra parte esta en `cuadre_interno()`, que verifica lo unico
verificable dentro del propio archivo — que la tarifa impresa de cada fila sea
el ingreso dividido las noches.
"""
from __future__ import annotations

import calendar
import io
import re

from app.importers.skill4_room_stats_pdf import FilaAgencia, LecturaSkill4, Resumen

#: Los nombres de columna que se esperan, normalizados. El valor es el atributo
#: de `FilaAgencia`; `None` = se usa para agrupar, no viaja a la fila.
_COLUMNAS = {
    "mes": None,
    "mes #": None,
    "ano": None,
    "tipo de habitacion": "room_type_name",
    "agencia": "agencia",
    "ing.hospedaje": "ingreso_hospedaje",
    "ing.ayb": "ingreso_ayb",
    "ing.otros": "ingreso_otros",
    "hab.entradas": "hab_entradas",
    "hab.estancias": "hab_estancias",
    "cli.entradas": "cli_entradas",
    "cli.estancias": "cli_estancias",
    "tarifa prom.": "tarifa_promedio",
}

#: Sin estas no se puede armar nada. `Mes #` y `Ano` se pueden deducir del
#: nombre del mes y del escenario, pero el tipo, la agencia y las dos cifras
#: que mueven el reporte son obligatorias.
_OBLIGATORIAS = ("tipo de habitacion", "agencia", "ing.hospedaje", "hab.estancias")

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _norm(t) -> str:
    """Un rotulo comparable: sin acentos, sin dobles espacios, en minuscula.

    ⚠️ Los encabezados llegan con acento o sin el segun quien haya guardado el
    archivo, y `Año` vs `Ano` es la diferencia entre encontrar la columna y no
    encontrarla.
    """
    if t is None:
        return ""
    t = str(t).strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ñ", "n"), (" ", " ")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


def _num(v) -> float:
    """Un numero de celda. Acepta lo que Excel deje pasar como texto.

    Reusa el criterio del lector de PDF: separador europeo o americano,
    negativos entre parentesis, simbolo de moneda. Una celda vacia es cero.
    """
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    from app.importers.skill4_room_stats_pdf import _num as num_pdf
    return num_pdf(str(v))


def _mes_de(fila: dict) -> int:
    """El mes de una fila. Primero `Mes #`, y si no el nombre.

    Se prefiere el numero porque no depende del idioma ni de la ortografia;
    el nombre es el respaldo para un archivo que no traiga la columna.
    """
    n = fila.get("mes #")
    if n not in (None, ""):
        try:
            m = int(float(n))
            if 1 <= m <= 12:
                return m
        except (TypeError, ValueError):
            pass
    nombre = _norm(fila.get("mes"))
    if nombre in _MESES:
        return _MESES[nombre]
    raise ValueError(f"no se entiende de que mes es la fila: {fila.get('mes')!r}")


def _filas_del_libro(file_bytes: bytes, nombre_archivo: str = "") -> list[list]:
    """Las celdas del archivo, como lista de filas.

    Acepta `.xlsx` y `.csv`. En un libro con varias hojas se busca la que
    tenga el encabezado: pedirle a la persona que renombre la hoja seria una
    fuente de error mas, y la hoja correcta se reconoce sola por sus columnas.
    """
    if nombre_archivo.lower().endswith(".csv"):
        import csv
        texto = file_bytes.decode("utf-8-sig", errors="replace")
        return [list(r) for r in csv.reader(io.StringIO(texto))]

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    mejor: list[list] = []
    for ws in wb.worksheets:
        filas = [list(f) for f in ws.iter_rows(values_only=True)]
        if _fila_del_encabezado(filas) is not None:
            return filas
        # Si ninguna califica se informa sobre la mas grande, que es donde la
        # persona seguramente esperaba que estuvieran los datos.
        if len(filas) > len(mejor):
            mejor = filas
    return mejor


def _fila_del_encabezado(filas: list[list]) -> int | None:
    """Indice de la fila de encabezado, o `None` si esta hoja no es.

    Se busca en las primeras 20 filas: los archivos del grupo suelen traer
    titulo, subtitulo y una linea en blanco antes de la tabla.
    """
    for i, f in enumerate(filas[:20]):
        nombres = {_norm(c) for c in f}
        if all(o in nombres for o in _OBLIGATORIAS):
            return i
    return None


def leer_datos_planos(file_bytes: bytes, nombre_archivo: str = "",
                      year_esperado: int | None = None) -> list[LecturaSkill4]:
    """Una `LecturaSkill4` por mes que traiga el archivo, en orden de mes.

    `year_esperado` es el ano del escenario. Si el archivo trae columna `Año`
    se valida contra ella; si no la trae, se usa el del escenario — igual que
    el PDF, que declara su propio periodo.

    ⚠️ **No agrupa filas repetidas en silencio.** Si el mismo mes, tipo y
    agencia aparecen dos veces, se suman y se avisa: puede ser legitimo (dos
    bloques del PMS) o puede ser una fila duplicada al copiar y pegar, y el
    total cuadra igual en los dos casos.
    """
    filas = _filas_del_libro(file_bytes, nombre_archivo)
    if not filas:
        raise ValueError("el archivo no tiene filas")

    i_cab = _fila_del_encabezado(filas)
    if i_cab is None:
        faltan = ", ".join(_OBLIGATORIAS)
        raise ValueError(
            "no se encontro la tabla: hace falta una fila de encabezado con las "
            f"columnas {faltan}")

    cab = [_norm(c) for c in filas[i_cab]]
    cuerpo = filas[i_cab + 1:]

    por_mes: dict[int, LecturaSkill4] = {}
    vistas: dict[tuple, int] = {}
    avisos: list[str] = []
    leidas = 0

    for n_fila, cruda in enumerate(cuerpo, start=i_cab + 2):
        d = {cab[j]: v for j, v in enumerate(cruda) if j < len(cab)}
        tipo = str(d.get("tipo de habitacion") or "").strip()
        agencia = str(d.get("agencia") or "").strip()
        if not tipo or not agencia:
            continue                      # fila vacia o de totales: se salta
        # ⚠️ Una fila de TOTAL dentro de la base plana duplicaria todo. La base
        # es detalle puro; cualquier rotulo de total se descarta y se avisa.
        if _norm(tipo).startswith("total") or _norm(agencia).startswith("total"):
            avisos.append(f"fila {n_fila}: se salto «{tipo} / {agencia}» "
                          "— la base plana no debe traer filas de total")
            continue

        mes = _mes_de(d)
        if "ano" in cab:
            ano = int(float(d.get("ano") or 0) or 0)
        else:
            ano = year_esperado or 0
        if year_esperado and ano and ano != year_esperado:
            raise ValueError(
                f"fila {n_fila}: el archivo dice ano {ano} y el escenario es "
                f"{year_esperado}")

        lec = por_mes.get(mes)
        if lec is None:
            lec = por_mes[mes] = LecturaSkill4(
                entidad="", year=ano or (year_esperado or 0), month=mes,
                moneda="USD", resumen=Resumen(
                    dias=calendar.monthrange(ano or year_esperado or 2000, mes)[1]))

        clave = (mes, _norm(tipo), _norm(agencia))
        if clave in vistas:
            avisos.append(
                f"fila {n_fila}: «{tipo} / {agencia}» ya aparecio en la fila "
                f"{vistas[clave]} para ese mes — las dos se sumaron")
        vistas.setdefault(clave, n_fila)

        lec.filas.append(FilaAgencia(
            room_type_name=tipo,
            agencia=agencia,
            ingreso_hospedaje=_num(d.get("ing.hospedaje")),
            ingreso_ayb=_num(d.get("ing.ayb")),
            ingreso_otros=_num(d.get("ing.otros")),
            hab_entradas=_num(d.get("hab.entradas")),
            hab_estancias=_num(d.get("hab.estancias")),
            cli_entradas=_num(d.get("cli.entradas")),
            cli_estancias=_num(d.get("cli.estancias")),
            tarifa_promedio=_num(d.get("tarifa prom.")),
        ))
        leidas += 1

    if not leidas:
        raise ValueError("se encontro el encabezado pero ninguna fila con datos")

    for lec in por_mes.values():
        lec.avisos_del_archivo = [a for a in avisos]   # type: ignore[attr-defined]

    return [por_mes[m] for m in sorted(por_mes)]


def cuadre_interno(lec: LecturaSkill4, tolerancia: float = 0.011) -> list[str]:
    """Lo unico verificable dentro de la base plana.

    El PDF se cuadra contra su propio resumen; acá no hay resumen. Lo que sí
    hay es la columna `Tarifa Prom.`, que el PMS imprime y que tiene que ser
    ingreso / noches. Es un control cruzado real: si alguien edito el ingreso
    o las noches a mano, la tarifa deja de cuadrar.

    ⚠️ No prueba que el archivo coincida con el PDF — nada en este camino lo
    prueba. Prueba que el archivo sea coherente consigo mismo.
    """
    avisos: list[str] = []
    for f in lec.filas:
        if not f.hab_estancias:
            if f.ingreso_hospedaje:
                avisos.append(
                    f"{f.room_type_name} / {f.agencia}: "
                    f"{f.ingreso_hospedaje:,.2f} de ingreso con cero noches")
            continue
        calc = round(f.ingreso_hospedaje / f.hab_estancias, 2)
        if f.tarifa_promedio and abs(calc - f.tarifa_promedio) > tolerancia:
            avisos.append(
                f"{f.room_type_name} / {f.agencia}: tarifa {f.tarifa_promedio:,.2f} "
                f"pero ingreso/noches da {calc:,.2f}")
        if f.hab_entradas > f.hab_estancias:
            avisos.append(
                f"{f.room_type_name} / {f.agencia}: {f.hab_entradas:,.0f} entradas "
                f"con {f.hab_estancias:,.0f} noches — una entrada da al menos una noche")
    return avisos
