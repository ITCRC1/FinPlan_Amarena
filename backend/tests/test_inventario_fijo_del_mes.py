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


# ───────── 4. Las ocho medidas del reporte, no tres ────────────────────────

def test_se_guardan_las_ocho_medidas_del_reporte():
    """⚠️ El reporte del PMS trae OCHO columnas y se guardaban tres.

    Owner, 2026-09-28, pidiendo la estadistica en el Dashboard: *«una por tab
    del excel»*. Los tabs son ocho; el sistema tenia tres. Medido contra los
    seis meses de Amarena ya cargados, lo que se tiraba:

        Ing.Otros      mar-ago   $14,754.85
        Hab.Entradas   mar-ago          366
        Cli.Entradas   mar-ago          833

    Los $14,754 existian UNICAMENTE en el Excel que la propiedad mantiene a
    mano: el sistema no tenia como cuadrarlos ni como mostrarlos, y nada decia
    que faltaran.
    """
    from app.models.actual_room_stat import ActualRoomStat
    from app.models.actual_room_stat_canal import ActualRoomStatCanal
    for modelo in (ActualRoomStat, ActualRoomStatCanal):
        cols = set(modelo.__table__.columns.keys())
        for c in ("ingreso_ayb", "ingreso_otros", "hab_entradas", "cli_entradas"):
            assert c in cols, f"{modelo.__name__} no guarda {c}"


def test_no_mandar_una_medida_la_CONSERVA_y_no_la_pone_en_cero():
    """⚠️ El modo de falla que este `None` evita.

    La pantalla de carga MANUAL solo digita noches, pax e ingreso. Si mandara
    ceros en las otras cuatro, abrirla y guardar borraria los otros ingresos y
    las llegadas que trajo el archivo del PMS — y en esa pantalla esas cifras
    ni siquiera se ven, asi que nadie notaria que las toco.

    Es la misma regla que ya rige para `canales`: `None` es «no se de esto»,
    no «es cero».
    """
    from app.api.revenue_api import RoomStatCanalIn, RoomStatRowIn
    for modelo in (RoomStatRowIn, RoomStatCanalIn):
        for campo in ("ingreso_ayb", "ingreso_otros", "hab_entradas", "cli_entradas"):
            assert modelo.model_fields[campo].default is None, \
                f"{modelo.__name__}.{campo} tiene default 0: pisaria lo guardado"
    src = _cuerpo_del_guardado()
    assert "previas = {" in src and "previas_canal = {" in src
    assert "def _o(nuevo, anterior, campo" in src
    # Y lo previo se lee ANTES del borrado, que es lo que lo hace posible.
    assert src.index("previas = {") < src.index("delete(ActualRoomStat)")


def test_una_fila_con_solo_otros_ingresos_no_se_descarta():
    """⚠️ «Vacia» son las OCHO en cero.

    Mirando solo noches, pax e ingreso, una categoria que ese mes unicamente
    registro otros ingresos —o llegadas— se descartaba como si no existiera.
    """
    src = _cuerpo_del_guardado()
    assert "def _tiene_algo(r)" in src
    assert "r.ingreso_otros or r.hab_entradas or r.cli_entradas" in src
    assert "if not (c.nights_occupied or c.revenue or c.pax):" not in src


def test_la_migracion_144_es_aditiva_y_no_rellena_hacia_atras():
    """Las columnas nuevas quedan en 0 para lo ya cargado, y 0 ahi significa
    «esta carga es anterior a que se guardara», no «el hotel no tuvo otros
    ingresos». Rellenarlo requeriria releer los archivos, que la migracion no
    tiene."""
    m = (pathlib.Path(__file__).resolve().parent.parent
         / "alembic/versions/144_las_ocho_medidas_del_reporte_del_pms.py")
    src = m.read_text(encoding="utf-8")
    assert "op.add_column" in src
    assert 'server_default="0"' in src
    assert "UPDATE" not in src.upper().replace("UPGRADE", ""), \
        "la migracion inventa valores hacia atras"


# ───────── 5. El bloque del Dashboard ──────────────────────────────────────

BLOQUE = (pathlib.Path(__file__).resolve().parents[2]
          / "frontend/components/EstadisticaHabitaciones.tsx")
DASH = (pathlib.Path(__file__).resolve().parents[2]
        / "frontend/app/dashboard/page.tsx")


def test_hay_un_cuadro_por_cada_tab_del_excel():
    """Owner: *«una por tab del excel»*. Los tabs del reporte de segmentacion
    son ocho, y los ocho tienen que estar o el bloque contesta a medias."""
    src = BLOQUE.read_text(encoding="utf-8")
    for tab in ("Ing. Hospedaje", "Ing. A y B", "Ing. Otros", "Hab. Entradas",
                "Hab. Estancias", "Clientes Entradas", "Clientes Estancias",
                "Tarifa Promedio"):
        assert f'titulo: "{tab}"' in src, f"falta el cuadro {tab}"


def test_el_bloque_sigue_el_selector_del_dashboard():
    """*«dependiente lo que se escoja en la vista»*."""
    dash = DASH.read_text(encoding="utf-8")
    assert ("<EstadisticaHabitaciones scenarioId={mainId} scenarios={scenarios}"
            " month={month} />") in dash


def test_el_mes_sin_estadistica_va_vacio_y_no_en_cero():
    """⚠️ La regla que este proyecto repite: un cero dice «no hubo» y un vacio
    dice «no lo sabemos». Con seis de doce meses cargados, mirar diciembre no
    puede mostrar ceros como si el hotel no hubiera vendido."""
    src = BLOQUE.read_text(encoding="utf-8")
    assert "if (!meses.length) return null;" in src
    assert '{v === null ? "—" :' in src
    assert "no tiene estad\u00edstica cargada:" in src, \
        "no se avisa que el mes elegido esta vacio"


def test_el_full_year_de_un_actual_es_lo_cargado_y_se_dice():
    """Con seis meses subidos, «Full Year» son esos seis. No se proyecta a
    doce ni se divide: el pie dice cuantos meses hay adentro."""
    src = BLOQUE.read_text(encoding="utf-8")
    assert "mes(es) cargado(s)" in src
    assert "no una proyecci\u00f3n a doce" in src


def test_la_tarifa_promedio_del_periodo_se_recalcula_y_no_se_promedia():
    """⚠️ El ADR del periodo es ingreso acumulado / noches acumuladas.

    Promediar los ADR mensuales hace pesar igual a un mes de 20 noches y a uno
    de 202: en Amarena 2026 son $306.83 contra los $286.13 reales.
    """
    src = BLOQUE.read_text(encoding="utf-8")
    i = src.index("if (b.saca === null)")
    bloque = src[i:i + 400]
    assert 'suma(meses, clave, r => r.revenue)' in bloque
    assert 'suma(meses, clave, r => r.nights_occupied)' in bloque
    assert "/ meses.length" not in src, "se promedia en vez de recalcular"


def test_si_no_hay_estadistica_en_ningun_lado_se_dice_donde_se_sube():
    """Cuando NINGUN escenario del ano tiene estadistica, decirlo -y donde se
    sube- es mejor que ocho cuadros en cero, que se leen como un hotel sin
    ventas."""
    src = BLOQUE.read_text(encoding="utf-8")
    assert "No hay estadística de habitaciones cargada para" in src
    assert "Cierre de Mes" in src


def test_el_bloque_encuentra_el_ACTUAL_aunque_la_vista_sea_un_budget():
    """⚠️ El defecto que el owner vio: *«donde quedaron los cuadros... no los
    veo»*.

    La estadistica del PMS vive en el escenario ACTUAL y el Dashboard abre con
    el Budget en el selector principal. Colgando el bloque del principal a
    secas, la vista por defecto mostraba «este escenario no tiene estadistica»
    y los ocho cuadros no aparecian NUNCA.

    Se prueba el principal primero —si alguien carga estadistica en un
    Forecast, ese manda— y si no tiene, se cae al ACTUAL del mismo ano. Y se
    dice en el encabezado: leer el ACTUAL creyendo que es el Budget seria peor
    que no ver nada.
    """
    src = BLOQUE.read_text(encoding="utf-8")
    assert "const candidatos = useMemo" in src
    assert 's.type === "ACTUAL"' in src
    assert "s.year === principal.year" in src, \
        "caeria a un ACTUAL de otro ano"
    # El principal va PRIMERO.
    i = src.index("return [scenarioId, ...delAno")
    assert i > 0, "el principal no tiene prioridad"
    # Y se avisa cuando lo que se muestra no es el principal.
    assert "no es la versi\u00f3n principal" in src
    assert "setPrestado(id !== scenarioId)" in src


def test_la_columna_del_mes_no_existe_en_full_year():
    """En «Full Year» no hay un mes elegido, y una columna entera de guiones
    bajo un encabezado vacio es ruido que ademas empuja las otras dos."""
    src = BLOQUE.read_text(encoding="utf-8")
    assert "const hayMes = month > 0;" in src
    assert "...(hayMes ? [[rotMes, delMes]" in src
    # Ni el encabezado ni las celdas se escriben a mano: salen de `periodos`.
    assert "[delMes, ytd, full].map" not in src


def test_las_tarjetas_no_se_estiran_ni_recortan_la_primera_fila():
    """⚠️ Lo que el owner vio en pantalla: la primera fila cortada por la mitad
    en los cuadros sin nota.

    La rejilla estiraba todas las tarjetas a la altura de la mas alta, y el
    `overflow:hidden` que redondeaba el borde recortaba lo que sobraba. Se
    quitan las dos cosas: cada tarjeta mide lo que su contenido.
    """
    src = BLOQUE.read_text(encoding="utf-8")
    assert 'alignItems: "start"' in src
    i = src.index('key={b.clave} style={{ border:')
    assert 'overflow: "hidden"' not in src[i:i + 300], \
        "la tarjeta sigue recortando su contenido"


def test_el_rotulo_de_la_categoria_no_se_corta():
    """⚠️ Amarena tiene «Garden View Deluxe-Tented Villa» y la misma
    «· Accesible». Cortadas con puntos suspensivos las dos se leen igual y no
    hay forma de saber cual fila es cual."""
    src = BLOQUE.read_text(encoding="utf-8")
    i = src.index("const TD_ROT")
    bloque = src[i:i + 320]
    assert "textOverflow" not in bloque
    assert 'whiteSpace: "nowrap"' not in bloque
    assert 'wordBreak: "break-word"' in bloque


def test_se_avisa_que_una_carga_vieja_dejo_las_medidas_nuevas_en_cero():
    """⚠️ Cero en «Ing. Otros» dice «el hotel no tuvo otros ingresos», y lo
    que pasa es que esa carga es anterior a que se guardaran. Cuatro cuadros
    llenos de $0.00 afirman lo primero."""
    src = BLOQUE.read_text(encoding="utf-8")
    assert "const sinCargaNueva" in src
    assert "Guardar los N meses" in src
    assert "Un cero ac\u00e1 no" in src
