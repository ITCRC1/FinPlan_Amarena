# -*- coding: utf-8 -*-
"""El calce entre el rótulo del PMS y la categoría de la propiedad se GUARDA.

Owner, 2026-09-10: *«necesito que hagas un tab de mapping: las que salen en el
pdf versus las que hay en master data»*, dicho justo después de *«ya tengo de
marzo a Agosto para subir»*.

## Por qué persistir y no sólo mostrar

El calce se resolvía en la pantalla, por archivo, y moría al descartar el PDF.
Seis meses eran seis veces la misma decisión — y cada vez una oportunidad de
elegir distinto. Un calce que cambia de un mes a otro **parte la serie en dos**
sin que nada avise: el mes viejo quedó bajo una categoría y el nuevo bajo otra,
y los dos totales siguen cuadrando contra su propio archivo. Es exactamente el
modo de falla que este proyecto persigue.

Y hay una consecuencia de diseño que vale escribir: un tab de mapping que sólo
funcionara con un PDF en pantalla no agregaría nada sobre los desplegables que
ya están en línea. El tab tiene sentido **porque** el mapeo se guarda.

## Lo que se cuida acá

1. Que el mapeo guardado **decida** y el parecido sólo **proponga**.
2. Que apunte al CÓDIGO y no al nombre.
3. Que un código inexistente se rechace en vez de guardarse.
4. Que el sub-tab exista y no dependa de que haya un PDF cargado.
5. Que guardar el mes **recuerde** el calce de ese PDF.
"""
import pytest

from ._rutas import BACKEND, FRONT

API = BACKEND / "app/api/room_stats_pdf_api.py"
MODELO = BACKEND / "app/models/pms_room_label.py"
MIGRACION = BACKEND / "alembic/versions/141_mapeo_de_categorias_del_pms.py"
PAGINA = FRONT / "app/month-end/room-stats/page.tsx"
CLIENTE = FRONT / "lib/api.ts"


# ───────────────────── 1. el guardado decide, el parecido propone ───────────

def test_el_mapeo_guardado_le_gana_al_parecido():
    """⚠️ Si el parecido pudiera pisar una decisión guardada, el calce
    cambiaría solo el día que alguien edita un nombre en Master Data — y en
    silencio, porque el total del mes sigue cuadrando contra su archivo.

    Se mira el fuente: el orden entre «buscar en el mapeo» y «calcular el
    parecido» es la garantía, y un refactor que invirtiera el `if` no rompería
    ninguna prueba de resultado mientras la tabla esté vacía.
    """
    src = API.read_text(encoding="utf-8")
    desde = src.index("mapeo = await _mapeo_guardado(db)")
    hasta = src.index("filas.append(", desde)
    cuerpo = src[desde:hasta]
    pos_fijado = cuerpo.index("fijado = por_codigo.get")
    pos_calce = cuerpo.index("_calce(t[")
    assert pos_fijado < pos_calce, "el parecido se calcula antes que el mapeo guardado"
    # Y el parecido tiene que estar en el `else`, no correrse igual.
    assert "else:" in cuerpo[pos_fijado:pos_calce]


def test_un_calce_guardado_se_muestra_como_guardado():
    """`confianza` distingue los tres estados. Un guardado que se mostrara como
    «probable» invitaría a revisar de nuevo algo ya decidido."""
    src = API.read_text(encoding="utf-8")
    assert '"guardado"' in src


# ─────────────────────────── 2. apunta al código ────────────────────────────

def test_el_mapeo_apunta_al_codigo_y_no_al_nombre():
    """El código es del grupo y no se cambia; el nombre se edita.

    Un mapeo contra el nombre se rompe solo al corregir una tilde en Master
    Data, y se rompe en silencio: el rótulo deja de calzar y las noches vuelven
    a «sin categoría».
    """
    src = MODELO.read_text(encoding="utf-8")
    assert "room_type_code" in src
    assert "room_type_name" not in src.split('"""')[2], \
        "el modelo guarda el nombre, que es editable"


def test_la_migracion_es_141_sobre_140():
    src = MIGRACION.read_text(encoding="utf-8")
    assert 'revision = "141"' in src
    assert 'down_revision = "140"' in src
    assert "def downgrade" in src, "sin downgrade no se puede volver atrás"


def test_un_rotulo_apunta_a_una_sola_categoria():
    """Sin la llave única, dos filas contradictorias del mismo rótulo se
    resolverían por orden de lectura —o sea al azar— y las noches irían a una
    categoría distinta según el día."""
    src = MIGRACION.read_text(encoding="utf-8")
    assert "uq_pms_room_label" in src
    assert '["hotel_id", "label"]' in src


# ──────────────── 3. un código inexistente no se guarda ─────────────────────

def test_una_categoria_desconocida_se_rechaza():
    """Guardado apuntaría a la nada: el rótulo caería en «sin categoría» y la
    pantalla del mapeo no mostraría nada raro."""
    src = API.read_text(encoding="utf-8")
    assert "skill4.categoria_desconocida" in src
    desde = src.index("async def guardar_mapeo_pms")
    cuerpo = src[desde:desde + 2600]
    assert "if code not in codigos:" in cuerpo


def test_los_errores_del_mapeo_estan_en_los_dos_idiomas():
    from app.errores import MENSAJES
    for clave in ("skill4.categoria_desconocida", "skill4.rotulo_vacio"):
        assert clave in MENSAJES, f"falta {clave}"
        assert MENSAJES[clave]["es"] and MENSAJES[clave]["en"]


def test_borrar_es_mandar_el_codigo_vacio():
    """No hace falta un endpoint de borrado: el mismo PUT con código vacío
    saca el mapeo. Un segundo camino sería una segunda forma de equivocarse."""
    src = API.read_text(encoding="utf-8")
    desde = src.index("async def guardar_mapeo_pms")
    cuerpo = src[desde:desde + 2600]
    assert "if not code:" in cuerpo and "db.delete(fila)" in cuerpo


# ─────────────── 4. los dos lados, y sin depender del PDF ───────────────────

def test_el_endpoint_devuelve_LOS_DOS_lados():
    """Las dos preguntas frente a esta pantalla son distintas: «este rótulo del
    PDF a dónde va» y «esta categoría mía, la trae el archivo». La segunda es
    la que detecta una categoría que dejó de venir en el PMS y viene guardando
    cero sin que nadie lo note."""
    src = API.read_text(encoding="utf-8")
    desde = src.index("async def ver_mapeo_pms")
    cuerpo = src[desde:src.index("@router.put", desde)]
    for clave in ('"categorias"', '"mapeos"', '"huerfanos"',
                  '"categorias_sin_rotulo"'):
        assert clave in cuerpo, f"la respuesta no trae {clave}"


def test_los_huerfanos_no_se_limpian_solos():
    """Borrarlos en silencio dejaría el rótulo sin destino y las noches
    caerían en «sin categoría» sin explicación."""
    src = API.read_text(encoding="utf-8")
    desde = src.index("async def ver_mapeo_pms")
    cuerpo = src[desde:src.index("@router.put", desde)]
    assert "db.delete" not in cuerpo, "el GET del mapeo borra huérfanos"


def test_el_sub_tab_existe():
    src = PAGINA.read_text(encoding="utf-8")
    assert '"mapeo", "Mapping"' in src, "el sub-tab no está en la lista"
    assert "function Mapeo(" in src


def test_el_sub_tab_NO_depende_de_que_haya_pdf():
    """⚠️ Es la única vista que se puede abrir sin archivo, y tiene que serlo:
    la pregunta «a dónde va este rótulo» aparece justo cuando el PDF no está.

    Se comprueba que el render del mapeo esté ANTES del corte por `!lectura`
    que deja a las otras tres vistas en el cartel del vacío.
    """
    src = PAGINA.read_text(encoding="utf-8")
    pos_mapeo = src.index('vista === "mapeo"')
    pos_corte = src.index(": !lectura", pos_mapeo)
    assert pos_mapeo < pos_corte, "el mapeo cae dentro del corte por falta de PDF"


def test_el_cliente_tiene_las_dos_llamadas():
    src = CLIENTE.read_text(encoding="utf-8")
    assert "export async function getMapeoPms" in src
    assert "export async function guardarMapeoPms" in src


# ───────────── 5. guardar el mes recuerda el calce de ese PDF ───────────────

def test_al_guardar_el_mes_se_recuerda_el_calce():
    """Es el punto de todo esto: sin guardarlo, los meses que vienen vuelven a
    preguntar lo mismo."""
    src = PAGINA.read_text(encoding="utf-8")
    desde = src.index("async function guardar()")
    cuerpo = src[desde:src.index("async function bajarExcel", desde)]
    assert "guardarMapeoPms(aRecordar)" in cuerpo


def test_el_calce_se_recuerda_DESPUES_de_que_el_mes_entro():
    """Si la escritura del mes falla, el calce no puede quedar fijado por un
    intento que no guardó nada."""
    src = PAGINA.read_text(encoding="utf-8")
    desde = src.index("async function guardar()")
    cuerpo = src[desde:src.index("async function bajarExcel", desde)]
    pos_mes = cuerpo.index("saveRoomStatsEntry(")
    pos_calce = cuerpo.index("guardarMapeoPms(")
    assert pos_mes < pos_calce, "el calce se guarda antes que el mes"


def test_recordar_el_calce_no_puede_tumbar_el_guardado_del_mes():
    """El mes ya entró: que falle fijar el calce no puede mostrarse como si el
    mes no se hubiera guardado. Se traga y el calce queda para el sub-tab."""
    src = PAGINA.read_text(encoding="utf-8")
    desde = src.index("guardarMapeoPms(aRecordar)")
    assert "catch" in src[desde:desde + 220]
