# -*- coding: utf-8 -*-
"""El PDF del PMS se lee en Cierre de Mes, y leerlo NO es guardarlo.

Owner, 2026-09-09: *«la idea es que se suba el documento y se lea la
información pero que no se guarde — solo se tomen los datos y ya»* · *«esto
debe quedar en cierre de mes»* · *«Amarena no tiene Opera»*.

Tres cosas se cuidan acá y las tres fallan en silencio si se rompen:

1. **Que el endpoint de lectura no escriba.** Es literalmente lo que pidió el
   owner, y una línea de `db.add` agregada de paso lo convertiría en un
   importador sin que el nombre cambie.
2. **Que el calce de categorías se proponga y no se imponga.** El PDF trae los
   nombres del PMS y la base los de la propiedad. Guardar bajo el nombre del
   PMS deja el Room Stats en cero **sin ningún error** — el mismo modo de
   falla que documenta `revenue_api._canonical_room_types`.
3. **Que la pantalla esté en Cierre de Mes.** Es un paso del cierre, no una
   consulta.
"""
import json

import pytest

from ._rutas import BACKEND, FRONT

API = BACKEND / "app/api/room_stats_pdf_api.py"
PAGINA = FRONT / "app/month-end/room-stats/page.tsx"


# ─────────────────────────── 1. leer no es guardar ──────────────────────────

def test_el_endpoint_de_lectura_no_escribe_en_la_base():
    """⚠️ El pedido del owner es literal: se lee y no se guarda.

    Se mira el fuente y no el comportamiento a propósito: el día que alguien
    agregue un `db.add` «para no tener que apretar Guardar», el endpoint pasa
    a ser un importador con nombre de lector, y ninguna prueba de resultado lo
    notaría.
    """
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def leer_pdf_room_stats"):]
    for escritura in ("db.add(", "db.commit(", "db.delete(", "delete(", "insert("):
        assert escritura not in cuerpo, f"el lector escribe: {escritura}"


def test_el_lector_no_pasa_por_el_registro_de_subidas():
    """Ese registro existe para frenar reimports. Acá no hay import que frenar,
    y engancharlo haría que el mismo PDF no se pueda volver a MIRAR."""
    src = API.read_text(encoding="utf-8")
    assert "registro_de_subida" not in src


def test_la_pantalla_guarda_por_el_camino_de_la_carga_manual():
    """No hay tabla nueva ni endpoint de guardado nuevo: se guarda con el
    mismo `room-stats-entry` que la captura a mano. Un segundo camino de
    escritura a `actual_room_stats` es cómo terminan conviviendo dos verdades
    para el mismo mes."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "saveRoomStatsEntry(scenarioId, lectura.month, rows)" in pag
    assert "leerPdfRoomStats" in pag


# ───────────────────────── 2. el calce se propone ───────────────────────────

class _Cat:
    def __init__(self, name, short_name, units=4, code="RT01"):
        self.name, self.short_name, self.units, self.code = name, short_name, units, code


AMARENA = [
    _Cat("Beach Front Deluxe Villa", "BF Deluxe", 6, "RT01"),
    _Cat("Beach Front Master Villa", "BF Master", 4, "RT02"),
    _Cat("Garden View Deluxe Villa", "GV Deluxe", 6, "RT03"),
]


@pytest.mark.parametrize("del_pdf,esperado", [
    # Las tres del PDF real de marzo 2026. «DLXE» es la abreviatura del PMS:
    # sin el diccionario de sinónimos, ninguna calzaría.
    ("BEACH FRONT DLXE VILLA", "Beach Front Deluxe Villa"),
    ("BEACH FRONT MASTER VILLA", "Beach Front Master Villa"),
    ("GARDEN VIEW DLXE VILLA", "Garden View Deluxe Villa"),
])
def test_calce_exacto_con_las_categorias_de_la_propiedad(del_pdf, esperado):
    from app.api.room_stats_pdf_api import _calce
    cat, confianza = _calce(del_pdf, AMARENA)
    assert cat is not None and cat.name == esperado
    assert confianza == "exacto"


def test_las_dos_BEACH_FRONT_no_se_confunden_entre_si():
    """⚠️ Comparten tres de cuatro palabras. Un calce por «contiene» las
    cruzaría, y el ingreso de las Master entraría como Deluxe: el total del
    hotel seguiría cuadrando y el reporte por categoría estaría mal."""
    from app.api.room_stats_pdf_api import _calce
    deluxe, _ = _calce("BEACH FRONT DLXE VILLA", AMARENA)
    master, _ = _calce("BEACH FRONT MASTER VILLA", AMARENA)
    assert deluxe.name != master.name


def test_una_categoria_desconocida_queda_SIN_calce():
    """Sin equivalente, no se elige el «más parecido»: se devuelve `None` y lo
    resuelve una persona. Adivinar acá archiva las noches en la categoría
    equivocada."""
    from app.api.room_stats_pdf_api import _calce
    cat, confianza = _calce("PRESIDENTIAL PENTHOUSE", AMARENA)
    assert cat is None and confianza == "ninguno"


def test_un_parecido_parcial_se_marca_para_revisar():
    from app.api.room_stats_pdf_api import _calce
    cat, confianza = _calce("GARDEN VIEW VILLA", AMARENA)
    assert cat is not None and cat.name == "Garden View Deluxe Villa"
    assert confianza == "probable", "un calce por parecido tiene que pedir revisión"


def test_la_pantalla_no_deja_guardar_con_calces_pendientes():
    pag = PAGINA.read_text(encoding="utf-8")
    assert "faltanCalce === 0" in pag and "duplicadas.length === 0" in pag


def test_dos_filas_del_pdf_a_la_misma_categoria_se_frenan():
    """El guardado reemplaza el mes entero: dos filas al mismo destino harían
    que una pise a la otra y desaparezca."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "duplicadas" in pag
    src = API.read_text(encoding="utf-8")
    assert "usadas" in src


# ─────────────────────── 3. vive en Cierre de Mes ───────────────────────────

def test_el_tab_esta_en_el_menu_de_cierre_de_mes():
    nav = (FRONT / "components/TopNav.tsx").read_text(encoding="utf-8")
    assert '{ key: "monthEndRoomStats", href: "/month-end/room-stats" }' in nav
    grupo = nav[nav.index('key: "monthEnd",'):nav.index('key: "operationInsight"')]
    assert "monthEndRoomStats" in grupo, "el tab quedó fuera del menú de Cierre de Mes"


def test_tiene_rotulo_en_los_dos_idiomas():
    for idioma in ("es", "en"):
        textos = json.dumps(json.loads(
            (FRONT / f"messages/{idioma}.json").read_text(encoding="utf-8")))
        assert '"monthEndRoomStats"' in textos, f"sin rótulo en {idioma}"


def test_la_pagina_existe_en_la_ruta_del_menu():
    """Un tab en la barra apuntando a una URL que no existe da 404 y solo se
    descubre haciendo clic."""
    assert PAGINA.exists()


# ───────────────────── la dependencia queda declarada ───────────────────────

def test_pdfplumber_esta_fijado_en_requirements():
    """⚠️ Sin versión fija, cada build de Railway resuelve la suya — y este
    lector depende de que `extract_text` respete la fila."""
    req = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    assert "pdfplumber==" in req, "pdfplumber sin fijar (o sin declarar)"


def test_el_lector_no_usa_pypdf():
    """Medido contra el PDF de marzo 2026: pypdf devuelve el texto en orden de
    COLUMNA y no hay forma de saber qué número es de qué agencia."""
    src = (BACKEND / "app/importers/skill4_room_stats_pdf.py").read_text(encoding="utf-8")
    assert "import pdfplumber" in src
    assert "import pypdf" not in src
