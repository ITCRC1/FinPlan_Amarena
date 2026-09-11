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


class _CatAlias(_Cat):
    def __init__(self, name, short_name, alias_pms="", units=4, code="RT01"):
        super().__init__(name, short_name, units, code)
        self.alias_pms = alias_pms


#: Los nombres REALES de Amarena contra los del PDF real de marzo 2026. Son
#: el caso que motivó el alias: el PMS parte «Beachfront» en dos palabras.
AMARENA_REAL = [
    _CatAlias("Garden View Deluxe-Tented Villa", "Garden View", "GARDEN VIEW DLXE VILLA", 8),
    _CatAlias("Beachfront Deluxe-Tented Villa", "BF Deluxe", "BEACH FRONT DLXE VILLA", 5),
    _CatAlias("Beachfront Master-Suite Tented Villa", "BF Master", "BEACH FRONT MASTER VILLA", 2),
    _CatAlias("Garden View Deluxe-Tented Villa · Accesible", "GV Accesible", "", 1),
]


@pytest.mark.parametrize("del_pdf,esperado", [
    ("GARDEN VIEW DLXE VILLA", "Garden View Deluxe-Tented Villa"),
    ("BEACH FRONT DLXE VILLA", "Beachfront Deluxe-Tented Villa"),
    ("BEACH FRONT MASTER VILLA", "Beachfront Master-Suite Tented Villa"),
])
def test_el_alias_resuelve_lo_que_el_parecido_no(del_pdf, esperado):
    """⚠️ Sin alias, DOS de estas tres quedan sin calce todos los meses.

    «BEACH FRONT DLXE VILLA» contra «Beachfront Deluxe-Tented Villa»: el PMS
    escribe «Beachfront» en dos palabras, así que para el comparador son
    tokens distintos y el parecido no llega al umbral. Es correcto que no
    adivine —adivinar archiva las noches en otra categoría y el total del
    hotel sigue cuadrando— pero obliga a elegir a mano en cada carga.
    """
    from app.api.room_stats_pdf_api import _calce
    cat, confianza = _calce(del_pdf, AMARENA_REAL)
    assert cat is not None and cat.name == esperado
    assert confianza == "alias"


def test_sin_alias_esas_mismas_no_calzan():
    """La contraparte del test de arriba: es lo que pasaba antes del alias."""
    from app.api.room_stats_pdf_api import _calce
    sin_alias = [_CatAlias(c.name, c.short_name, "", c.units) for c in AMARENA_REAL]
    for del_pdf in ("BEACH FRONT DLXE VILLA", "BEACH FRONT MASTER VILLA"):
        cat, confianza = _calce(del_pdf, sin_alias)
        assert confianza == "ninguno", f"{del_pdf} ya no necesita alias: revisar el test"


def test_el_alias_le_gana_al_parecido():
    """⚠️ Una decisión que una persona tomó no se recalcula por similitud.

    Si el parecido pudiera ganarle, renombrar una categoría en Master Data
    movería el calce de un mes para otro sin que nadie lo pida.
    """
    from app.api.room_stats_pdf_api import _calce
    cats = [
        _CatAlias("Garden View Deluxe-Tented Villa", "Garden", "BEACH FRONT DLXE VILLA", 8),
        _CatAlias("Beachfront Deluxe Villa", "Beachfront", "", 5),
    ]
    cat, confianza = _calce("BEACH FRONT DLXE VILLA", cats)
    assert confianza == "alias"
    assert cat.name == "Garden View Deluxe-Tented Villa"


def test_el_alias_se_aprende_al_guardar_y_no_en_otra_pantalla():
    """Un mapa que hay que ir a mantener a otro lado envejece peor que no
    tenerlo. El calce confirmado se guarda en el mismo momento."""
    pag = PAGINA.read_text(encoding="utf-8")
    assert "guardarAliasPms(" in pag
    guardado = pag[pag.index("async function guardar()"):pag.index("async function bajarExcel")]
    assert "guardarAliasPms" in guardado, "el alias no se aprende al guardar"
    # Y en su propio try: que falle el alias no puede tirar el mes ya guardado.
    assert guardado.index("saveRoomStatsEntry") < guardado.index("guardarAliasPms")


def test_guardar_el_alias_no_mueve_ninguna_cifra():
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def guardar_alias_pms"):]
    cuerpo = cuerpo[:cuerpo.index("# ─────")] if "# ─────" in cuerpo else cuerpo
    for campo in ("nights_occupied", "revenue", "pax", "ActualRoomStat"):
        assert campo not in cuerpo, f"el alias toca {campo}"


def test_una_categoria_ajena_no_se_crea_sola():
    """Guardar un alias para una categoría que no es de esta propiedad
    metería una categoría fantasma en Master Data."""
    src = API.read_text(encoding="utf-8")
    cuerpo = src[src.index("async def guardar_alias_pms"):]
    assert "desconocidas.append" in cuerpo
    assert "RoomTypeConfig(" not in cuerpo


def test_los_tres_alias_de_amarena_quedan_sembrados():
    """La migración los deja puestos para que la PRIMERA carga tampoco pida
    elegir: el owner ya vio y confirmó ese mapa.

    ⚠️ Por NOMBRE y no por código: los códigos son canónicos del grupo y los
    comparten todas las propiedades con nombres distintos.
    """
    mig = (BACKEND / "alembic/versions/141_alias_pms_de_las_categorias.py").read_text(encoding="utf-8")
    for nombre, alias in (
        ("Garden View Deluxe-Tented Villa", "GARDEN VIEW DLXE VILLA"),
        ("Beachfront Deluxe-Tented Villa", "BEACH FRONT DLXE VILLA"),
        ("Beachfront Master-Suite Tented Villa", "BEACH FRONT MASTER VILLA"),
    ):
        assert f'("{nombre}", "{alias}")' in mig
    assert "WHERE name = :nombre" in mig
    assert "dept_code" not in mig and "code = " not in mig


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

# ──────────────── 5. el mes se elige, y elegirlo no lo impone ───────────────
#
# Owner, 2026-09-10: *«debe darme la oportunidad de escoger un mes cuando
# subo»*. El mes elegido dice DONDE se guarda; el que manda sobre QUE se
# guarda sigue siendo el archivo. Las dos mitades se cuidan acá.

def test_el_mes_elegido_que_no_es_el_del_pdf_se_frena():
    """⚠️ El modo de falla es silencioso y por eso se valida en vez de obedecer.

    Guardar reemplaza el mes entero (`revenue_api` borra las filas del mes
    antes de escribir). Si el selector le ganara al archivo, subir el PDF de
    marzo con abril elegido pisaría un abril que ya estaba bien, con cifras de
    otro mes — y el resultado se ve perfectamente normal: doce meses cargados
    y totales que suman. Es el mismo motivo por el que ya existe la guarda del
    año, `skill4.ano_no_coincide`.
    """
    from app.api.room_stats_pdf_api import _validar_mes_elegido
    from app.errores import ErrorApi

    with pytest.raises(ErrorApi) as e:
        _validar_mes_elegido(4, 3)
    assert e.value.status_code == 422
    # El mensaje nombra LOS DOS meses: sin eso, quien lo ve no sabe si el que
    # está mal es el archivo o su elección.
    assert "Marzo" in e.value.detail and "Abril" in e.value.detail


def test_el_mes_elegido_que_coincide_pasa():
    from app.api.room_stats_pdf_api import _validar_mes_elegido
    _validar_mes_elegido(3, 3)      # no levanta


def test_sin_mes_elegido_el_lector_sigue_andando():
    """`None` = la pantalla no mandó mes. Se acepta y se usa el del archivo.

    El parámetro es opcional a propósito: hacerlo obligatorio habría roto todo
    cliente que ya llamaba al lector, y el lector no necesita el mes para
    leer — lo necesita para avisar.
    """
    from app.api.room_stats_pdf_api import _validar_mes_elegido
    _validar_mes_elegido(None, 3)   # no levanta


@pytest.mark.parametrize("mes", [0, 13, -1, 99])
def test_un_mes_fuera_del_almanaque_se_frena(mes):
    from app.api.room_stats_pdf_api import _validar_mes_elegido
    from app.errores import ErrorApi
    with pytest.raises(ErrorApi) as e:
        _validar_mes_elegido(mes, 3)
    assert e.value.status_code == 422


def test_el_lector_sigue_sin_escribir_con_el_mes_encima():
    """La guarda nueva no convirtió el lector en importador.

    Se repite la mirada de la prueba 1 sobre el cuerpo del endpoint porque el
    parámetro nuevo es justamente la clase de cambio que invita a «ya que
    estamos, guardémoslo».
    """
    src = API.read_text(encoding="utf-8")
    desde = src.index("async def leer_pdf_room_stats")
    hasta = src.index("@router.", desde)
    cuerpo = src[desde:hasta]
    for escritura in ("db.add(", "db.commit(", "db.delete(", "insert("):
        assert escritura not in cuerpo, f"el lector escribe: {escritura}"


def test_los_dos_errores_del_mes_estan_en_los_dos_idiomas():
    from app.errores import MENSAJES
    for clave in ("skill4.mes_no_coincide", "skill4.mes_invalido"):
        assert clave in MENSAJES, f"falta {clave} en el catálogo"
        assert MENSAJES[clave]["es"] and MENSAJES[clave]["en"]


def test_la_pantalla_ofrece_elegir_el_mes():
    """Sin selector, el mes lo decide el archivo y quien sube no ve cuál va a
    reemplazar antes de apretar Guardar."""
    src = PAGINA.read_text(encoding="utf-8")
    assert 'aria-label="Mes"' in src, "la pantalla no tiene selector de mes"
    assert "setMesSel" in src


def test_la_pantalla_manda_el_mes_al_lector():
    """El selector tiene que VIAJAR. Un selector que no se manda es peor que no
    tenerlo: da la impresión de que se eligió algo."""
    src = PAGINA.read_text(encoding="utf-8")
    assert "leerPdfRoomStats(scenarioId, f, mesSel)" in src
    cliente = (FRONT / "lib/api.ts").read_text(encoding="utf-8")
    assert 'form.append("mes"' in cliente


def test_el_mes_elegido_avisa_lo_que_va_a_reemplazar():
    """Si el mes ya tiene estadística, la pantalla lo dice ANTES de subir —y
    con cifras, no con un cartel genérico."""
    src = PAGINA.read_text(encoding="utf-8")
    assert "ya tiene estadística guardada" in src
    assert "reemplaza" in src


def test_el_mes_guardado_no_finge_el_detalle_del_pdf():
    """⚠️ Lo guardado son totales; el rótulo del PMS, su resumen de ocupación y
    los avisos de cuadre sólo existen en el archivo.

    Rellenar esos campos con ceros para poder pintar las tres vistas del mes
    haría que un mes guardado se lea como un mes sin ventas — el mismo error
    que `anio_room_stats` evita con `cargado: false`. Mientras las vistas no
    sepan pintar sin archivo, la pantalla dice CUÁNTO hay y no inventa el
    detalle.
    """
    src = PAGINA.read_text(encoding="utf-8")
    desde = src.index("const guardado = useMemo")
    hasta = src.index("const fueraDelAdr", desde)
    cuerpo = src[desde:hasta]
    for inventado in ("nombre_pdf", "resumen_pdf", "avisos_de_cuadre",
                      "hab_entradas", "cli_entradas"):
        assert inventado not in cuerpo, f"el mes guardado finge {inventado}"


def test_al_guardar_se_recarga_el_ano_y_no_se_descarta():
    """⚠️ Cargar varios meses de corrido depende de esto.

    Al guardar, la pantalla hacía `setAnio(null)` y ningún efecto volvía a
    pedir el año: quedaba nulo hasta abrir Acumulado o cambiar de escenario.
    Con el año nulo, el cartel del vacío no puede decir cuánto hay guardado y
    el selector no puede avanzar al primer mes que falta — o sea que después
    de guardar marzo seguía ofreciendo marzo.

    Owner, 2026-09-10: *«ya tengo de marzo a Agosto para subir»*. Son seis
    cargas seguidas; el avance solo es la diferencia entre seis y doce pasos.
    """
    src = PAGINA.read_text(encoding="utf-8")
    desde = src.index("async function guardar()")
    hasta = src.index("async function bajarExcel", desde)
    cuerpo = src[desde:hasta]
    assert "cargarAnio()" in cuerpo, "guardar no recarga el año"
    assert "setAnio(null)" not in cuerpo, "guardar descarta el año en vez de recargarlo"


def test_el_selector_avanza_solo_al_primer_mes_que_falta():
    """El default se acomoda al primer mes sin cargar, y deja de moverse en
    cuanto el usuario elige a mano: un selector que salta mientras alguien lo
    está usando es peor que un default imperfecto."""
    src = PAGINA.read_text(encoding="utf-8")
    assert "mesTocado" in src
    assert "anio.meses.find(m => !m.cargado)" in src
