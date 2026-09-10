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
    desde = src.index("async def leer_pdf_room_stats")
    # Sólo el cuerpo de ESA función: el módulo tiene otros endpoints que sí
    # escriben —la casilla del ADR— y son legítimos.
    hasta = src.index("@router.", desde)
    cuerpo = src[desde:hasta]
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
    assert "saveRoomStatsEntry(scenarioId, lectura.month, rows, canales)" in pag
    assert "leerPdfRoomStats" in pag


def test_el_total_y_su_apertura_se_guardan_JUNTOS():
    """⚠️ Una sola llamada, una sola transacción.

    Si el detalle por canal se escribiera aparte, un fallo en la segunda
    escritura dejaría el mes con un total nuevo y un mix viejo — y el mix
    estaría describiendo un mes que ya no existe, sin que nada lo diga.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    assert pag.count("saveRoomStatsEntry(") == 1
    rev = (BACKEND / "app/api/revenue_api.py").read_text(encoding="utf-8")
    cuerpo = rev[rev.index("async def put_room_stats_entry"):]
    cuerpo = cuerpo[:cuerpo.index("@router.")]
    assert "ActualRoomStatCanal" in cuerpo
    # Un solo commit: los dos borrados y los dos insertados caen juntos.
    assert cuerpo.count("await db.commit()") == 1


def test_la_apertura_por_canal_no_se_toca_en_la_carga_manual():
    """`canales=None` (la pantalla de captura a mano) deja el detalle como
    estaba. Borrarlo por omisión perdería el mix de un mes que alguien sólo
    quiso corregir en un número."""
    rev = (BACKEND / "app/api/revenue_api.py").read_text(encoding="utf-8")
    assert "if body.canales is not None:" in rev
    assert "canales: list[RoomStatCanalIn] | None = None" in rev


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

def test_la_casilla_del_adr_no_toca_ningun_importe():
    """⚠️ Lo único que cambia es el DENOMINADOR del ADR.

    Si desmarcar un canal moviera noches o ingreso, el total dejaría de
    cuadrar contra el PDF y ya no se podría saber si la diferencia es del
    archivo o del filtro. La prueba mira el endpoint: sólo escribe la bandera.
    """
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def marcar_canal_para_kpis"):]
    # Sin el docstring: ahí los campos se NOMBRAN justamente para decir que no
    # se tocan, y buscarlos en el texto haría fallar a la explicación.
    codigo = cuerpo.split('"""')[2] if cuerpo.count('"""') >= 2 else cuerpo
    assert "fila.cuenta_para_kpis = bool(body.cuenta)" in codigo
    for campo in ("nights_occupied", "revenue", "pax"):
        assert campo not in codigo, f"la casilla del ADR toca {campo}"


def test_el_default_del_adr_no_mueve_nada_al_desplegar():
    """La columna nace en `true`: el día del deploy, ningún ADR cambia."""
    from app.models.market_code import MarketCode
    assert MarketCode.__table__.c.cuenta_para_kpis.default.arg is True
    mig = (BACKEND / "alembic/versions/139_room_stats_por_canal.py").read_text(encoding="utf-8")
    assert "server_default=sa.true()" in mig


def test_un_codigo_del_pms_sin_canal_no_se_adivina():
    """Misma regla que ya rige en `market_codes`: sin canal se muestra vacío y
    se reporta. Adivinarlo mandaría noches al canal equivocado y el total
    seguiría cuadrando."""
    from app.api.room_stats_pdf_api import _canal_info
    info = _canal_info("CPL", {})
    assert info["canal"] == "" and info["conocido"] is False
    # Y sin catalogar, cuenta para el ADR: no se le inventa una exclusión.
    assert info["cuenta_para_kpis"] is True


# ───────────────────────── el acumulado del año ─────────────────────────────

def test_el_ano_devuelve_los_ingredientes_y_no_las_tasas():
    """⚠️ El YTD de una tasa NO es el promedio de los meses.

    Por eso el endpoint manda noches, pax, ingreso y disponibles, y la
    división la hace quien muestra. Si el backend mandara el ADR de cada mes
    ya calculado, el acumulado sólo podría promediarlos — y un mes de 20
    noches pesaría igual que uno de 150.
    """
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def anio_room_stats"):]
    for ingrediente in ("nights_occupied", "pax", "revenue", "nights_available"):
        assert ingrediente in cuerpo
    for derivada in ('"adr"', '"revpar"', '"occupancy"'):
        assert derivada not in cuerpo, f"el backend ya calculó {derivada}"


def test_un_mes_sin_cargar_no_es_un_mes_en_cero():
    """Un cero dice «el hotel no vendió»; sin cargar dice «falta el PDF». Con
    una propiedad que abrió a mitad de año, confundirlos convierte un YTD
    incompleto en un mal semestre."""
    src = API.read_text(encoding="utf-8")
    assert '"cargado": cargado' in src
    assert '"meses_cargados"' in src
    pag = PAGINA.read_text(encoding="utf-8")
    assert "rayado" in pag, "la pantalla no distingue el mes sin cargar"


def test_las_noches_disponibles_se_recalculan_con_el_inventario_de_hoy():
    """Si alguien corrige las unidades en Master Data, la ocupación histórica
    tiene que corregirse con él — no quedarse con las de la importación."""
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def anio_room_stats"):]
    assert 'c["nights_available"] = u * dias' in cuerpo


def test_sin_apertura_el_adr_acumulado_usa_el_total_y_no_inventa():
    """Un mes cargado a mano no tiene detalle por canal. Ahí el ADR se calcula
    sobre el total: descontar «lo que suele ser cortesía» sería inventar."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "? abre.reduce<T3>" in pag and ": tot;" in pag


def test_un_canal_fuera_sale_de_LOS_TRES_indicadores():
    """Owner, 2026-09-09: «sí, saca todo».

    Primero fue sólo el ADR. Pero contar las cortesías deforma los tres a la
    vez: en marzo 2026 la ocupación es 10.28% con CPL y 4.03% sin él. Que un
    canal cuente para la ocupación y no para el ADR sería una tercera versión
    del mes, distinta de las otras dos.

    ⚠️ RevPAR casi no se mueve ($12.90 → $12.81) y eso confirma la lectura:
    el ingreso es el mismo, lo que estaba mal era repartirlo entre noches que
    nadie compró.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    # Acumulado: las tres tasas sobre `base`, ninguna sobre `tot`.
    assert 'case "ocupacion": return c.disp ? pct(c.base[0] / c.disp * 100)' in pag
    assert 'case "revpar":    return c.disp ? usd(c.base[2] / c.disp)' in pag
    assert 'case "adr":       return adrDe(c.base);' in pag
    # Mes: la vista por habitación, igual.
    assert "pct(baseCat[i][0] / d * 100)" in pag
    assert "usd(baseCat[i][2] / d)" in pag


def test_excluir_un_canal_no_cambia_lo_que_se_guarda():
    """⚠️ La base de los indicadores y lo que va a la base de datos son cosas
    distintas.

    Lo que se guarda son las cifras del ARCHIVO — si el guardado filtrara, el
    mes dejaría de cuadrar contra el PDF y el ingreso desaparecería del P&L.
    Lo que se filtra es el cálculo, y las dos bases se muestran juntas para
    poder conciliarlas.
    """
    pag = PAGINA.read_text(encoding="utf-8")
    guardado = pag[pag.index("async function guardar()"):pag.index("async function bajarExcel")]
    for filtrado in ("baseCat", "baseTot", "enAdr"):
        assert filtrado not in guardado, f"el guardado filtra por {filtrado}"
    assert "nights_occupied: f.nights_occupied" in guardado
    # Y la fila de conciliación existe en las dos vistas del mes.
    assert pag.count("Con todos los canales (PDF)") == 2


def test_ocupacion_y_revpar_no_existen_por_canal():
    """Un canal no tiene inventario propio: dividir su ingreso entre las
    noches disponibles del hotel da un número sin significado."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert 'MEDIDAS.filter(([k]) => k !== "ocupacion" && k !== "revpar")' in pag


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
