# -*- coding: utf-8 -*-
"""Lector del PDF de Skill4 Front Desk — «Estadistica de Explotacion
Totalizada por Tipo de Habitacion, Detallada por Agencia».

**Por que existe.** El Room Stats real de Corcovado sale de un Excel de Opera
(`room_stats_importer.py`). **Amarena no tiene Opera**: su PMS es Skill4, y lo
que emite es este PDF, uno por mes. Sin este lector, las noches y el ingreso
por categoria de Amarena solo entran a mano, fila por fila.

**El archivo NO se guarda.** Se lee en memoria, se devuelven las filas y el
PDF se descarta. Del archivo solo queda nombre, tamano y checksum en el
registro de subidas (`registro_dep.py`), que es lo que frena el reimport.

## Forma del archivo

Pagina(s) de detalle — una linea por agencia, agrupadas por categoria::

    Seleccion: Desde:01/03/2026 Hasta: 31/03/2026 Moneda:USD
    Tipo de Habitacion:BEACH FRONT DLXE VILLA
    CPL         0.09 0.00 0.00  9 11 15 17    0.01
    DIRECTOS  407.09 0.00 0.00  4  6  9 13   67.85
    TOTALES TIPO HAB: 2481.43 0.00 0.00 15 21 30 42 118.16
    ...
    TOTALES GENERALES: 6397.65 0.00 0.00 34 51 70 107 125.44

Las ocho columnas numericas son, en orden: Ing.Hospedaje, Ing.AyB, Ing.Otros,
Habitaciones-Entradas, Habitaciones-Estancias, Clientes-Entradas,
Clientes-Estancias, Tarifa Promedio.

⚠️ **«Entradas» y «Estancias» no son lo mismo y confundirlas cambia el
reporte.** Entradas = cuantas reservas/huespedes ingresaron; Estancias =
noches. Lo que el Room Stats llama `nights_occupied` son las **Estancias de
Habitaciones**, y lo que llama `pax` son las **Estancias de Clientes**
(noches-huesped) — que es la cifra que se divide por las noches para dar el
ratio huespedes/habitacion. Tomar «Entradas» daria un ADR y un ratio que
parecen razonables y estan mal.

Ultima pagina — resumen estadistico del hotel (no por categoria)::

    RESUMEN ESTADISTICO: Desde:01/03/2026 Hasta:31/03/2026 Total de Dias: 31
    Capacidad de Hab: 16 Total de Habitac: 496
    Total de Hab Disp: 238 Total Hab Bloq: 258
    Total de Ingresos del Hotel: 6606.88 (USD)

Ese resumen **no se importa**: se usa para CUADRAR. Si la suma del detalle no
da el total del resumen, el archivo y lo leido se separaron y hay que avisar,
no adivinar (mismo criterio que el bloque de verificacion del GL).

⚠️ **Las noches disponibles NO salen del PDF por categoria.** El resumen las
da solo a nivel hotel, y ademas en dos versiones que no coinciden: 496
(inventario completo) y 238 (descontando 258 bloqueadas). El Room Stats las
calcula como `units x dias` desde `RoomTypeConfig`, igual que la carga manual
(`put_room_stats_entry`), y este lector no las inventa: devuelve las dos
cifras del resumen para mostrarlas y punto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO

#: Etiqueta con la que el PDF abre cada bloque de categoria. Se corta antes de
#: la vocal acentuada: el acento viaja distinto segun quien genere el PDF.
_TIPO = "Tipo de Habitaci"
_TOT_TIPO = "TOTALES TIPO HAB"
_TOT_GRAL = "TOTALES GENERALES"

#: `1.460,00` (europeo) y `1,460.00` (americano) conviven en los PDF del grupo.
_NUM = r"-?\(?\d[\d.,]*\)?"
#: Una fila de datos = un rotulo + exactamente 8 numeros al final.
_FILA = re.compile(r"^(?P<rotulo>\S.*?)\s+(?P<nums>(?:" + _NUM + r"\s+){7}" + _NUM + r")\s*$")
_PERIODO = re.compile(r"Desde:\s*(\d{2})/(\d{2})/(\d{4}).*?Hasta:\s*(\d{2})/(\d{2})/(\d{4})")


def _num(s: str) -> float:
    """`'1,460.00'`, `'1.460,00'`, `'(120.00)'` -> float. Vacio -> 0.0."""
    s = (s or "").strip().replace("\xa0", " ")
    if not s:
        return 0.0
    negativo = s.startswith("(") and s.endswith(")")
    if negativo:
        s = s[1:-1]
    s = s.replace("$", "").replace(" ", "")
    if "," in s and "." in s:
        # el separador decimal es el que aparece MAS A LA DERECHA
        s = (s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".")
             else s.replace(",", ""))
    elif "," in s:
        entero, _, dec = s.rpartition(",")
        s = entero.replace(",", "") + "." + dec if len(dec) <= 2 else s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if negativo else v


@dataclass
class FilaAgencia:
    """Una linea del detalle: categoria x agencia."""
    room_type_name: str
    agencia: str
    ingreso_hospedaje: float
    ingreso_ayb: float
    ingreso_otros: float
    hab_entradas: float
    hab_estancias: float      # <- noches ocupadas
    cli_entradas: float
    cli_estancias: float      # <- noches-huesped (el `pax` del Room Stats)
    tarifa_promedio: float


@dataclass
class Resumen:
    """El bloque estadistico de la ultima pagina. Solo para cuadrar y mostrar."""
    dias: int = 0
    capacidad_hab: int = 0
    habitaciones_totales: int = 0       # capacidad x dias (496)
    habitaciones_disponibles: int = 0   # descontando bloqueadas (238)
    habitaciones_bloqueadas: int = 0
    ocupacion_sobre_total: float = 0.0
    ocupacion_sobre_disponibles: float = 0.0
    ingreso_hospedaje: float = 0.0
    ingreso_puntos_venta: float = 0.0
    ingreso_otros: float = 0.0
    ingreso_total_hotel: float = 0.0


@dataclass
class LecturaSkill4:
    entidad: str = ""
    year: int = 0
    month: int = 0
    moneda: str = "USD"
    filas: list[FilaAgencia] = field(default_factory=list)
    #: Totales que el propio PDF declara por categoria (`TOTALES TIPO HAB`).
    totales_declarados: dict = field(default_factory=dict)
    total_general: dict = field(default_factory=dict)
    resumen: Resumen = field(default_factory=Resumen)

    def por_tipo(self) -> list[dict]:
        """Suma el detalle por categoria — el orden es el del PDF.

        Se suma el detalle en vez de leer la fila `TOTALES TIPO HAB` a
        proposito: asi `cuadre()` compara dos caminos distintos y una linea
        que no se haya podido leer aparece como diferencia en vez de pasar
        inadvertida.
        """
        acc: dict = {}
        for f in self.filas:
            a = acc.setdefault(f.room_type_name, {
                "room_type_name": f.room_type_name, "revenue": 0.0, "ingreso_ayb": 0.0,
                "ingreso_otros": 0.0, "nights_occupied": 0.0, "pax": 0.0,
                "hab_entradas": 0.0, "cli_entradas": 0.0, "agencias": 0})
            a["revenue"] += f.ingreso_hospedaje
            a["ingreso_ayb"] += f.ingreso_ayb
            a["ingreso_otros"] += f.ingreso_otros
            a["nights_occupied"] += f.hab_estancias
            a["pax"] += f.cli_estancias
            a["hab_entradas"] += f.hab_entradas
            a["cli_entradas"] += f.cli_entradas
            a["agencias"] += 1
        for a in acc.values():
            a["revenue"] = round(a["revenue"], 2)
            a["ingreso_ayb"] = round(a["ingreso_ayb"], 2)
            a["ingreso_otros"] = round(a["ingreso_otros"], 2)
            a["adr"] = round(a["revenue"] / a["nights_occupied"], 2) if a["nights_occupied"] else 0.0
        return list(acc.values())

    def cuadre(self, tolerancia: float = 0.05) -> list[str]:
        """Diferencias entre lo leido y lo que el PDF declara. Lista vacia = cuadra.

        Tres comparaciones independientes: cada categoria contra su fila
        `TOTALES TIPO HAB`, el gran total contra `TOTALES GENERALES`, y el
        ingreso de hospedaje contra el resumen de la ultima pagina.
        """
        avisos: list[str] = []
        for t in self.por_tipo():
            dec = self.totales_declarados.get(t["room_type_name"])
            if not dec:
                continue
            for campo, leido, esperado in (
                ("ingreso", t["revenue"], dec["ingreso_hospedaje"]),
                ("noches", t["nights_occupied"], dec["hab_estancias"]),
                ("pax", t["pax"], dec["cli_estancias"]),
            ):
                if abs(leido - esperado) > tolerancia:
                    avisos.append(
                        t["room_type_name"] + ": " + campo +
                        " leido {:,.2f} != {:,.2f} del total del archivo".format(leido, esperado))
        if self.total_general:
            leido = round(sum(f.ingreso_hospedaje for f in self.filas), 2)
            esperado = self.total_general["ingreso_hospedaje"]
            if abs(leido - esperado) > tolerancia:
                avisos.append("TOTALES GENERALES: ingreso leido "
                              "{:,.2f} != {:,.2f} del archivo".format(leido, esperado))
        if self.resumen.ingreso_hospedaje:
            leido = round(sum(f.ingreso_hospedaje for f in self.filas), 2)
            if abs(leido - self.resumen.ingreso_hospedaje) > tolerancia:
                avisos.append("Resumen estadistico: hospedaje {:,.2f} != {:,.2f}".format(
                    leido, self.resumen.ingreso_hospedaje))
        return avisos


def _texto(file_bytes: bytes) -> list[str]:
    """Lineas del PDF, en orden de lectura.

    ⚠️ Se usa **pdfplumber y no pypdf**: medido contra el PDF de marzo 2026 de
    Amarena, pypdf devuelve el texto en orden de COLUMNA (todos los ingresos
    juntos, despues todas las noches), y ahi no hay forma de saber que numero
    es de que agencia. pdfplumber respeta la fila.
    """
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover - dependencia fijada en requirements
        raise RuntimeError(
            "Falta pdfplumber — es la dependencia que lee el PDF de Skill4") from e
    lineas: list[str] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            lineas.extend(texto.splitlines())
    return lineas


def _campos(nums: str) -> list[float]:
    return [_num(x) for x in nums.split()]


def _resumen(lineas: list[str]) -> Resumen:
    """El bloque de la ultima pagina.

    ⚠️ Viene en DOS COLUMNAS que `extract_text` aplana en una sola linea, asi
    que `Total de Ingresos:` aparece tres veces con tres significados
    (hospedaje, puntos de venta, otros). Por eso se busca cada dato por su
    etiqueta unica, y «otros ingresos» se despeja del total del hotel en vez
    de leerse — que es la unica forma de no agarrar el numero del vecino.
    """
    r = Resumen()
    todo = "\n".join(lineas)

    def _uno(patron: str, defecto: float = 0.0) -> float:
        m = re.search(patron, todo, re.IGNORECASE)
        return _num(m.group(1)) if m else defecto

    r.dias = int(_uno(r"Total de D[ií]as:\s*(\d+)"))
    r.capacidad_hab = int(_uno(r"Capacidad de Hab:\s*(\d+)"))
    r.habitaciones_totales = int(_uno(r"Total de Habitac:\s*(\d+)"))
    r.habitaciones_disponibles = int(_uno(r"Total de Hab Disp:\s*(\d+)"))
    r.habitaciones_bloqueadas = int(_uno(r"Total Hab Bloq:\s*(\d+)"))
    r.ocupacion_sobre_total = _uno(r"Sobre el Total de Habitaciones:\s*([\d.,]+)")
    r.ocupacion_sobre_disponibles = _uno(r"Sobre Habitaciones Disponibles:\s*([\d.,]+)")
    r.ingreso_total_hotel = _uno(r"Total de Ingresos del Hotel:\s*([\d.,]+)")
    # Hospedaje: el `Total de Ingresos:` que va SOLO en su linea (columna izquierda).
    for ln in lineas:
        m = re.match(r"^\s*Total de Ingresos:\s*([\d.,]+)\s*$", ln, re.IGNORECASE)
        if m:
            r.ingreso_hospedaje = _num(m.group(1))
            break
    # Puntos de venta: comparte linea con «Sobre Habitaciones Disponibles».
    m = re.search(r"Sobre Habitaciones Disponibles:\s*[\d.,]+\s+Total de Ingresos:\s*([\d.,]+)",
                  todo, re.IGNORECASE)
    if m:
        r.ingreso_puntos_venta = _num(m.group(1))
    if r.ingreso_total_hotel:
        r.ingreso_otros = round(
            r.ingreso_total_hotel - r.ingreso_hospedaje - r.ingreso_puntos_venta, 2)
    return r


def leer_pdf_skill4(file_bytes: bytes) -> LecturaSkill4:
    """Lee el PDF y devuelve el detalle por categoria x agencia + el resumen.

    No toca la base ni guarda el archivo: entra `bytes`, sale una `LecturaSkill4`.
    """
    lineas = _texto(file_bytes)
    if not lineas:
        raise ValueError("El PDF no tiene texto legible (¿es un escaneo?)")

    out = LecturaSkill4()
    tipo_actual = ""
    for ln in lineas:
        ln = ln.replace("\xa0", " ").rstrip()
        if not ln.strip():
            continue

        if not out.entidad and "Entidad:" in ln:
            out.entidad = ln.split("Entidad:", 1)[1].strip()

        if not out.year:
            m = _PERIODO.search(ln)
            if m:
                d1, m1, y1, d2, m2, y2 = (int(x) for x in m.groups())
                if (y1, m1) != (y2, m2):
                    raise ValueError(
                        "El archivo abarca mas de un mes ({:02d}/{:02d}/{} a "
                        "{:02d}/{:02d}/{}). Se procesa un mes por archivo.".format(
                            d1, m1, y1, d2, m2, y2))
                out.year, out.month = y1, m1
        if "Moneda:" in ln:
            mm = re.search(r"Moneda:\s*([A-Z]{3})", ln)
            if mm:
                out.moneda = mm.group(1)

        if _TIPO in ln and ":" in ln:
            tipo_actual = ln.split(":", 1)[1].strip()
            continue

        m = _FILA.match(ln)
        if not m:
            continue
        rotulo = m.group("rotulo").strip().rstrip(":").strip()
        v = _campos(m.group("nums"))
        if len(v) != 8:
            continue
        datos = {
            "ingreso_hospedaje": v[0], "ingreso_ayb": v[1], "ingreso_otros": v[2],
            "hab_entradas": v[3], "hab_estancias": v[4],
            "cli_entradas": v[5], "cli_estancias": v[6], "tarifa_promedio": v[7],
        }
        if rotulo.upper().startswith(_TOT_GRAL):
            out.total_general = datos
        elif rotulo.upper().startswith(_TOT_TIPO):
            if tipo_actual:
                out.totales_declarados[tipo_actual] = datos
        elif tipo_actual:
            out.filas.append(FilaAgencia(room_type_name=tipo_actual, agencia=rotulo, **datos))

    if not out.filas:
        raise ValueError(
            "No se encontro ninguna fila de agencia. ¿Es el reporte «Estadistica de "
            "Explotacion Totalizada por Tipo de Habitacion» de Skill4?")
    if not out.year:
        raise ValueError("No se pudo leer el periodo (linea «Desde:.. Hasta:..») del PDF")
    out.resumen = _resumen(lineas)
    return out


def nombre_del_mes(month: int) -> str:
    return ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][month]
