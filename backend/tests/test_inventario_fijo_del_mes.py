# -*- coding: utf-8 -*-
"""El inventario del mes es master data: 16 unidades x los dias del mes.

Owner, 2026-09-28: *«las habitaciones disponibles siempre deben ser 16 por el
numero de dias del mes. no puede cambiar»* y *«estas son las habitaciones que
hay... no se puede subir otra con otro nombre»*.

Son dos reglas distintas y las dos fallaban en silencio:

1. Una categoria que no vendia ese mes no dejaba fila, y las noches
   disponibles se arman sumando filas: desaparecia del denominador.
2. `room_type_name` es texto libre: un rotulo nuevo del PMS creaba una quinta
   categoria fantasma con cero unidades — suma ingreso, no suma inventario.
"""
import inspect
import pathlib

API = pathlib.Path(__file__).resolve().parent.parent / "app/api"
REVENUE = API / "revenue_api.py"
ANIO = API / "room_stats_pdf_api.py"
MIGRACION = (pathlib.Path(__file__).resolve().parent.parent
             / "alembic/versions/143_el_inventario_del_mes_esta_completo.py")


def _cuerpo_del_guardado() -> str:
    from app.api.revenue_api import put_room_stats_entry
    return inspect.getsource(put_room_stats_entry)


# ───────── 1. El inventario no depende de lo que se haya vendido ───────────

def test_se_escribe_una_fila_por_cada_categoria_activa():
    """⚠️ El defecto medido en produccion.

    La Accesible de Amarena (1 unidad de 16) no vendio de marzo a julio, asi
    que esos meses no dejaba fila y el hotel figuraba con 15 unidades:

        mes     disponibles   deberian ser   ocupacion   deberia ser
        marzo       465            496          4.30%        4.03%
        julio       465            496         28.39%       26.61%

    El ingreso cuadra, las noches vendidas cuadran, el total cuadra. Solo el
    denominador esta mal, y la ocupacion y el RevPAR salen inflados sin un
    solo sintoma. Agosto —donde si vendio— sale bien, y eso lo esconde mas:
    la serie parece consistente.
    """
    src = _cuerpo_del_guardado()
    assert "for nm, units in canon.items():" in src, \
        "se sigue escribiendo solo lo que vino en el cuerpo"
    assert "enviadas.get(nm)" in src
    # Y el inventario sale del Master Data, no del cuerpo de la peticion.
    assert "nights_available=units * days" in src
    assert "(r.units or 0) * days" not in src, \
        "las noches disponibles siguen saliendo del `units` que manda la pantalla"


def test_el_units_sale_del_master_data_y_no_del_cuerpo():
    """Que la pantalla mande un `units` distinto no puede cambiar el
    inventario del hotel: el numero de habitaciones es de la propiedad."""
    src = _cuerpo_del_guardado()
    assert "canon = dict(await _canonical_room_types(db))" in src
    assert "units=units," in src
    assert "units=r.units," not in src


def test_un_cuerpo_entero_en_cero_limpia_el_mes_y_no_lo_deja_cargado():
    """⚠️ La otra cara de escribir filas en cero.

    `cargado` es «el mes tiene filas». Si un guardado vacio escribiera las
    cuatro categorias en cero, un mes que nadie subio pasaria a leerse como un
    mes sin ventas — que es otra cosa, y es exactamente lo que
    `anio_room_stats` viene evitando con `cargado: false`.
    """
    src = _cuerpo_del_guardado()
    assert "hay_algo = any(" in src
    assert "if hay_algo:" in src


def test_el_anio_completa_el_inventario_de_los_meses_ya_guardados():
    """Los meses que ya estan cargados no tienen que volver a subirse para
    que el denominador se corrija."""
    src = ANIO.read_text(encoding="utf-8")
    assert "if cargado:" in src
    assert '"nights_available": u * dias,' in src
    assert "completas.extend(por_nombre.values())" in src, \
        "una categoria fuera del Master Data desapareceria y con ella su ingreso"


def test_el_anio_no_inventa_categorias_en_un_mes_sin_cargar():
    """Solo se completa lo que ya tiene filas. Rellenar un mes vacio lo haria
    figurar como cargado."""
    src = ANIO.read_text(encoding="utf-8")
    i = src.index("if cargado:")
    # El bloque que completa vive DENTRO del `if cargado`.
    assert src[i:i + 900].count("por_nombre") >= 3


# ───────── 2. Solo entran las categorias que la propiedad tiene ────────────

def test_una_categoria_que_no_existe_se_rechaza():
    """Owner: *«estas son las habitaciones que hay... no se puede subir otra
    con otro nombre»*.

    ⚠️ `room_type_name` es texto libre en `actual_room_stats`. Un rotulo nuevo
    del PMS —o un calce mal hecho— creaba una quinta categoria con cero
    unidades: suma ingreso y no suma inventario, asi que baja el ADR del hotel
    y no mueve la ocupacion. Nada avisa.
    """
    src = _cuerpo_del_guardado()
    assert "room_stats.categoria_desconocida" in src
    assert "if r.room_type_name not in canon" in src


def test_tambien_se_valida_la_categoria_de_las_filas_por_canal():
    """Una apertura bajo una categoria que no existe queda huerfana: no la
    encuentra ninguna vista y su ingreso no aparece en el mix."""
    src = _cuerpo_del_guardado()
    assert "for c in (body.canales or [])" in src


def test_el_mensaje_dice_cuales_son_las_validas():
    """Un rechazo que no dice que poner obliga a adivinar."""
    from app.errores import MENSAJES
    m = MENSAJES["room_stats.categoria_desconocida"]
    assert "{desconocidas}" in m["es"] and "{validas}" in m["es"]
    assert "{desconocidas}" in m["en"] and "{validas}" in m["en"]


# ───────── 3. La migracion arregla lo que ya estaba guardado ───────────────

def test_la_migracion_no_toca_las_cifras_vendidas():
    """Solo agrega inventario. Si moviera noches, pax o ingreso, estaria
    reescribiendo lo que el PMS dijo."""
    src = MIGRACION.read_text(encoding="utf-8")
    i = src.index("SET units = :u, nights_available = :na")
    linea = src[i:src.index("WHERE", i)]
    for campo in ("nights_occupied", "revenue", "pax"):
        assert campo not in linea, f"la migracion reescribe {campo}"


def test_la_migracion_solo_toca_meses_que_ya_tienen_filas():
    src = MIGRACION.read_text(encoding="utf-8")
    assert "FROM actual_room_stats a" in src
    assert "SELECT DISTINCT a.scenario_id, a.month" in src


def test_la_migracion_usa_los_dias_del_ano_del_escenario():
    """⚠️ Febrero tiene 28 o 29 segun el ano. Clavar 28 —o tomar el ano
    corriente— deja el inventario de un bisiesto corto un dia por unidad."""
    src = MIGRACION.read_text(encoding="utf-8")
    assert "JOIN scenarios s ON s.id = a.scenario_id" in src
    assert "calendar.monthrange(int(year), int(month))[1]" in src


def test_al_leer_un_archivo_las_categorias_ausentes_van_en_cero():
    """⚠️ El mismo defecto del lado de la LECTURA.

    La pantalla arma su denominador con las filas que le llegan. Si el archivo
    no trajo una categoria y la respuesta tampoco la trae, la ocupacion que se
    muestra ANTES de guardar sale inflada igual que la guardada — y es
    justamente la pantalla donde alguien revisa el mes antes de aceptarlo.
    """
    src = ANIO.read_text(encoding="utf-8")
    i = src.index("ausentes = [c.name for c in categorias")
    bloque = src[i:i + 1400]
    assert "for c in categorias:" in bloque, \
        "las categorias ausentes se listan pero no se agregan"
    assert '"nights_available": c.units * dias' in bloque
    assert '"nights_occupied": 0.0' in bloque
    assert '"agencias": []' in bloque, \
        "una categoria que no vendio no puede traer apertura por canal"
