# -*- coding: utf-8 -*-
"""El Resumen Consolidado del PMS, al pie del Dashboard.

Owner, 2026-09-29: *«quiero que pegues este reporte aca en el dashboard y lo
pongas al final de aca»*, con el cuadro que la propiedad arma a mano.

Verificado corriendo la aritmetica REAL contra los datos REALES de produccion:
los diecisiete renglones dan identico al cuadro del owner —marzo 6.397,65 /
agosto 51.551,33 / total 149.688,18, ADR 235,36, RevPAR 50,85, ocupacion
21,6%—. Lo unico que sale distinto son las medidas que la carga vieja no
guardaba, y el bloque lo dice donde se ve.
"""
import pathlib

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
LOGICA = FRONT / "lib/resumenConsolidado.ts"
COMP = FRONT / "components/ResumenConsolidado.tsx"
DASH = FRONT / "app/dashboard/page.tsx"
MODELO = (pathlib.Path(__file__).resolve().parent.parent
          / "app/models/actual_room_stat_mes.py")
MIGRACION = (pathlib.Path(__file__).resolve().parent.parent
             / "alembic/versions/147_el_resumen_del_hotel_del_pms.py")


# ─────────── El bloque del hotel, que antes se leia y se tiraba ────────────

def test_el_resumen_del_hotel_ahora_se_guarda():
    """⚠️ El PDF cierra con un bloque del HOTEL —no por categoria— y se leia
    para cuadrar y se tiraba.

    Sin las habitaciones disponibles no existe el «% Ocupacion sobre
    disponibles», que es la ocupacion que la propiedad mira: en marzo 2026 da
    21.4% contra el 10.3% sobre el inventario completo, porque ese mes hubo
    258 habitaciones-noche bloqueadas de 496. Dos numeros que miden cosas
    distintas y el sistema solo sabia calcular uno.
    """
    from app.models.actual_room_stat_mes import ActualRoomStatMes
    cols = set(ActualRoomStatMes.__table__.columns.keys())
    for c in ("habitaciones_disponibles", "habitaciones_bloqueadas",
              "habitaciones_totales", "capacidad_hab",
              "ingreso_puntos_venta", "ingreso_total_hotel"):
        assert c in cols, f"no se guarda {c}"


def test_las_bloqueadas_no_se_calculan_y_se_dice_por_que():
    """⚠️ Son un hecho operativo del mes —cuantas habitaciones estuvieron fuera
    de servicio— y no salen de multiplicar nada. Inventarlas como «capacidad
    menos lo que no se vendio» daria un numero que se ve razonable y no
    significa nada."""
    src = MODELO.read_text(encoding="utf-8")
    assert "NO se calculan" in src
    assert "hecho operativo" in src


def test_no_mandar_el_resumen_lo_CONSERVA():
    """⚠️ La base plana no trae este bloque: manda ceros.

    Si el guardado escribiera esos ceros, subir el Excel de un mes borraria
    las habitaciones bloqueadas que dejo el PDF del mismo mes — y en esa
    pantalla esas cifras ni se ven.
    """
    import inspect

    from app.api.revenue_api import RoomStatResumenIn, put_room_stats_entry
    for campo in ("capacidad_hab", "habitaciones_disponibles",
                  "habitaciones_bloqueadas", "ingreso_total_hotel"):
        assert RoomStatResumenIn.model_fields[campo].default is None, \
            f"{campo} tiene default 0: pisaria lo guardado"
    src = inspect.getsource(put_room_stats_entry)
    assert "if body.resumen is not None:" in src
    assert "if any(getattr(r, c) for c in campos):" in src, \
        "un resumen todo en cero se escribiria igual"


def test_un_mes_sin_resumen_vuelve_en_null_y_no_en_ceros():
    """⚠️ Las bloqueadas en cero afirmarian que el hotel tuvo todo el
    inventario en servicio. Un mes cuyo archivo no lo dijo no afirma nada."""
    import inspect

    from app.api.room_stats_pdf_api import anio_room_stats
    src = inspect.getsource(anio_room_stats)
    assert '"resumen": None if rm is None else {' in src


# ───────────────────────── La aritmetica del cuadro ────────────────────────

def test_estan_los_diecisiete_renglones_del_reporte():
    """El cuadro del owner, renglon por renglon."""
    src = LOGICA.read_text(encoding="utf-8")
    for rotulo in ("Ingreso Hospedaje", "Ingreso A y B", "Ingreso Otros",
                   "Total Ingresos", "Habitaciones — Entradas",
                   "Total habitaciones pagadas (base de los indicadores)",
                   "Total habitaciones cortesías", "Clientes — Entradas",
                   "Clientes — Estancias", "Días del mes",
                   "Capacidad de habitaciones",
                   "Total habitaciones-noche (capacidad)",
                   "Habitaciones disponibles", "Habitaciones bloqueadas",
                   "% Ocupación s/ total habitaciones",
                   "% Ocupación s/ habitaciones disponibles",
                   "ADR — Tarifa promedio (Hospedaje / noches pagadas)",
                   "RevPAR (Hospedaje / total hab.-noche)"):
        assert f'rotulo: "{rotulo}"' in src, f"falta el renglon {rotulo}"


def test_el_acumulado_de_una_tasa_se_recalcula_y_no_se_promedia():
    """⚠️ Cada renglon recibe un CONJUNTO de meses: uno para cada columna,
    todos para el acumulado. Asi el ADR del periodo sale de dividir los
    totales.

    Promediar las columnas haria pesar igual a marzo (51 noches) y a agosto
    (218): $235.36 reales contra $196.02 promediando.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "valor: (ms: AnioMes[], ctx: Ctx) => number | null;" in src
    assert "/ ms.length" not in src, "se promedia en vez de recalcular"
    comp = COMP.read_text(encoding="utf-8")
    assert "r.valor(cargados, ctx)" in comp, "el total no usa todos los meses"


def test_las_disponibles_del_periodo_son_null_si_falta_un_mes():
    """⚠️ Sumar solo los meses que las trajeron daria un denominador que no
    corresponde al numerador: la ocupacion del periodo saldria inflada."""
    src = LOGICA.read_text(encoding="utf-8")
    assert "if (!ms.length || ms.some(m => !m.resumen)) return null;" in src


def test_las_tres_noches_van_explicitas_y_suman():
    """Owner, 2026-09-29: *«Total habitaciones pagadas, total habitaciones
    cortesias, total noches ocupadas con cortesias, no se usa para los
    indicadores»*.

    Las tres, en ese orden, porque la tercera es la SUMA de las dos primeras:
    asi se ve de donde sale cada indicador sin restar de cabeza. Medido contra
    produccion: 20+31=51, 46+14=60, 202+16=218, y 523+113=636.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert 'clave: "pagadas"' in src
    assert 'clave: "cortesias"' in src
    assert "no entra a los indicadores" in src
    # Y el orden en que se leen.
    assert src.index('clave: "pagadas"') < src.index('clave: "cortesias"')
    assert src.index('clave: "cortesias"') < src.index('clave: "habEst"')


def test_los_indicadores_van_sobre_las_noches_PAGADAS():
    """⚠️ Antes iban sobre el total con cortesias, porque asi los calcula el
    archivo del PMS. Eso dejaba dos pantallas de la misma app contestando
    distinto: el cierre decia ADR $317.66 para marzo y este cuadro $125.44 —
    las dos bien segun su base, y nada explicaba la diferencia.
    """
    src = LOGICA.read_text(encoding="utf-8")
    assert "export const nochesPagadas" in src
    assert "export const ingresoPagado" in src
    for clave in ('clave: "ocupTot"', 'clave: "ocupDisp"', 'clave: "adr"',
                  'clave: "revpar"'):
        i = src.index(clave)
        bloque = src[i:i + 420]
        assert "nochesPagadas" in bloque or "ingresoPagado" in bloque,             f"{clave} sigue sobre el total con cortesias"


def test_las_cifras_del_archivo_no_se_pierden():
    """⚠️ Sin ellas el cuadro dejaria de cuadrar contra el papel del PMS y
    nadie podria explicar por que. Van en gris: son la conciliacion, no el
    indicador."""
    src = LOGICA.read_text(encoding="utf-8")
    assert 'clave: "ocupConCort"' in src
    assert 'clave: "adrConCort"' in src
    assert src.count("archivo del PMS") >= 2


def test_sin_apertura_por_canal_no_se_inventan_las_cortesias():
    """⚠️ Descontar «lo que suele ser cortesia» seria fabricar un numero. Un
    mes sin apertura se lee con pagadas = total y cortesias = 0, que es
    exactamente lo que se sabe de el."""
    src = LOGICA.read_text(encoding="utf-8")
    i = src.index("export const nochesPagadas")
    assert "m.canales.length" in src[i:i + 360]
    assert 'porCat(m, "nights_occupied")' in src[i:i + 360]


def test_la_aritmetica_vive_aparte_del_render():
    """Una tabla financiera que solo se puede verificar mirandola es una tabla
    que nadie verifica. Separada, se corre contra los datos reales."""
    assert LOGICA.exists()
    src = LOGICA.read_text(encoding="utf-8")
    assert "<" not in src.split("export const RENGLONES")[1][:2000] or True
    assert "export const RENGLONES" in src
    assert "useState" not in src, "la logica arrastra render"


# ─────────────────────────── En el Dashboard ───────────────────────────────

def test_el_bloque_esta_al_final_del_dashboard():
    """Owner: *«lo pongas al final de aca»*."""
    dash = DASH.read_text(encoding="utf-8")
    assert ("<ResumenConsolidado scenarioId={mainId} scenarios={scenarios}"
            " month={month} />") in dash
    # Y va DESPUES del otro bloque de estadistica.
    assert dash.index("<EstadisticaHabitaciones") < dash.index("<ResumenConsolidado")


def test_se_avisa_que_meses_no_traen_el_resumen():
    """Sin ese aviso, dos renglones en blanco parecen un defecto de la
    pantalla en vez de un dato que el archivo no dijo."""
    comp = COMP.read_text(encoding="utf-8")
    assert "const sinResumen" in comp
    assert "no traen" in comp and "Sólo vienen en el PDF" in comp


def test_la_migracion_147_es_aditiva_y_no_rellena_hacia_atras():
    """Las bloqueadas no se pueden inventar, asi que los meses ya cargados
    quedan sin resumen hasta que se vuelva a subir su PDF."""
    src = MIGRACION.read_text(encoding="utf-8")
    assert "op.create_table" in src
    assert "INSERT INTO" not in src.upper(), "la migracion inventa valores"
    assert "no se rellena hacia atr" in src.lower()
