# -*- coding: utf-8 -*-
"""Membresias del club: el cobro de la cuota de mantenimiento.

Owner, 2026-09-29: *«que aca incluyas este tab llamado MEMBRESIAS de la misma
forma en que esta la imagen. que se pueda actualizar manualmente por mes. o que
se pueda bajar o subir con un excel»*.

No sale del PMS: es un conteo que lleva la propiedad y que vivia en una
diapositiva. Es la unica pestaña del cierre donde se ESCRIBE a mano.
"""
import io
import pathlib

import pytest
from openpyxl import Workbook

from app.api.membresias_api import (
    _cierre, _concepto_de, _leer_libro, _mes, _numero, _rotulo,
)
from app.models.membresia_mes import CONCEPTOS

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend"
COMP = FRONT / "components/Membresias.tsx"
PAGINA = FRONT / "app/month-end/room-stats/page.tsx"
MIGRACION = (pathlib.Path(__file__).resolve().parent.parent
             / "alembic/versions/145_membresias_del_club_por_mes.py")

MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


class _Fila:
    def __init__(self, concepto, cantidad):
        self.concepto, self.cantidad = concepto, cantidad


# ───────────────────────── Lo que NO se guarda ─────────────────────────────

def test_el_total_no_se_guarda_se_suma():
    """⚠️ Guardar el total abre la puerta a que el total y sus partes digan
    cosas distintas —el modo de falla que no avisa— y a que alguien «corrija»
    el total sin tocar los renglones."""
    from app.models.membresia_mes import MembresiaMes
    cols = set(MembresiaMes.__table__.columns.keys())
    assert "total" not in cols
    assert cols == {"id", "scenario_id", "month", "concepto", "cantidad"}
    assert _mes([], 2026, 8)["total"] == 0


def test_el_rotulo_con_fecha_se_arma_al_mostrarlo():
    """⚠️ «Activas de cobro al 31 de agosto 2026» lleva la fecha del cierre.

    Guardarlo congelaria agosto dentro de la fila de septiembre: el renglon de
    septiembre diria «al 31 de agosto» con el numero de septiembre.
    """
    assert _rotulo("activas", 2026, 8) == "Activas de cobro al 31 de agosto 2026"
    assert _rotulo("activas", 2026, 9) == "Activas de cobro al 30 de septiembre 2026"
    # Y febrero sigue al calendario, no a una constante.
    assert _cierre(2026, 2).startswith("28 de febrero")
    assert _cierre(2028, 2).startswith("29 de febrero")


def test_un_concepto_desconocido_no_se_esconde():
    """Esconderlo haria desaparecer un conteo que alguien cargo, y el total
    dejaria de cuadrar contra el papel sin que se vea por que."""
    m = _mes([_Fila("activas", 92), _Fila("inventado", 5)], 2026, 8)
    claves = [c["concepto"] for c in m["conceptos"]]
    assert "inventado" in claves
    assert m["conceptos"][-1]["desconocido"] is True
    assert m["total"] == 97, "el desconocido no entro al total"


def test_un_mes_sin_cargar_no_es_un_mes_en_cero():
    """⚠️ La regla que este proyecto repite. Con doce meses a la vista, un cero
    dice «el club no tuvo membresias» y el blanco dice «todavia no lo
    contamos»."""
    assert _mes([], 2026, 3)["cargado"] is False
    assert _mes([_Fila("activas", 0)], 2026, 3)["cargado"] is True
    src = COMP.read_text(encoding="utf-8")
    assert "if (!m.cargado) return null;" in src, "el Excel bajaria ceros"


# ─────────────────────── El viaje de ida y vuelta ──────────────────────────

def _libro_de_descarga():
    """Lo que produce el boton «Excel del año», tal cual."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Ingresos cobro por cuota de mantenimiento · 2026"])
    ws.append([])
    ws.append(["Concepto"] + [f"{m} 2026" for m in MES3] + ["Acumulado"])
    ws.append(["Activas de cobro al 31 de agosto 2026"] + [None] * 7 + [92]
              + [None] * 4 + [92])
    ws.append(["Condicionados a 2da etapa club"] + [None] * 7 + [33]
              + [None] * 4 + [33])
    ws.append(["Pendiente de firma de contrato"] + [None] * 7 + [2]
              + [None] * 4 + [2])
    ws.append(["Plan de pago"] + [None] * 7 + [2] + [None] * 4 + [2])
    ws.append(["Excepción «no paga»"] + [None] * 7 + [1]
              + [None] * 4 + [1])
    ws.append(["Total general"] + [None] * 7 + [130] + [None] * 4 + [130])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_el_excel_que_baja_es_el_que_sube():
    """El archivo de la descarga tiene que volver a entrar sin tocarlo. Si el
    formato de ida y el de vuelta no son el mismo papel, la funcion de subir no
    sirve para nada."""
    filas = _leer_libro(_libro_de_descarga(), "x.xlsx")
    cab, cuerpo = filas[0], filas[1:]
    assert any("Ago" in str(c) for c in cab), "no se encontro la cabecera de meses"
    rotulos = [str(f[0]) for f in cuerpo if f and f[0]]
    for clave, _plantilla in CONCEPTOS:
        assert any(_concepto_de(r) == clave for r in rotulos), f"se perdio {clave}"


def test_el_rotulo_de_activas_se_reconoce_venga_el_mes_que_venga():
    """⚠️ Su rotulo cambia con el mes. Reconocerlo por igualdad exacta haria
    que un archivo bajado en septiembre no encuentre la fila de agosto."""
    for mes in ("31 de agosto 2026", "30 de septiembre 2026", "28 de febrero 2027"):
        assert _concepto_de(f"Activas de cobro al {mes}") == "activas"
    assert _concepto_de("activas") == "activas", "la clave cruda tambien entra"
    # Las comillas del rotulo no pueden cambiar el resultado.
    assert _concepto_de('Excepcion "no paga"') == "excepcion"
    assert _concepto_de("Excepción «no paga»") == "excepcion"


def test_la_fila_del_total_no_se_importa():
    """⚠️ Si «Total general» entrara como un concepto mas, el mes quedaria al
    doble y seguiria cuadrando consigo mismo."""
    assert _concepto_de("Total general") is None
    assert _concepto_de("TOTAL") is None


def test_una_celda_vacia_no_es_un_cero():
    """⚠️ Es lo que hace que subir el archivo con un solo mes tocado no se
    lleve los otros once por delante."""
    assert _numero(None) is None
    assert _numero("") is None
    assert _numero(0) == 0.0
    assert _numero("92") == 92.0
    assert _numero("1,130") == 1130.0


def test_rechaza_un_libro_sin_la_tabla():
    wb = Workbook()
    wb.active.append(["esto", "no", "es"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="no se encontr"):
        _leer_libro(buf.getvalue(), "x.xlsx")


def test_el_importador_no_borra_los_meses_que_el_archivo_no_trae():
    """⚠️ Bajar el Excel, tocar agosto y volver a subirlo no puede llevarse los
    otros once por delante."""
    import inspect

    from app.api import membresias_api as api
    src = inspect.getsource(api.importar_membresias)
    assert "meses_con_dato = sorted({m for v in leido.values() for m in v})" in src
    assert "for mes in meses_con_dato:" in src


def test_un_rotulo_desconocido_en_el_excel_se_reporta_y_no_se_adivina():
    """⚠️ Adivinar a que concepto se parece mandaria el conteo al renglon
    equivocado y el total seguiria dando lo mismo."""
    import inspect

    from app.api import membresias_api as api
    src = inspect.getsource(api.importar_membresias)
    assert "membresias.concepto_desconocido" in src
    assert "desconocidos.append(rotulo)" in src


# ─────────────────────────── La migracion ──────────────────────────────────

def test_la_migracion_siembra_agosto_con_las_cifras_del_owner():
    src = MIGRACION.read_text(encoding="utf-8")
    for concepto, cantidad in (("activas", 92), ("condicionados", 33),
                               ("pendiente_firma", 2), ("plan_pago", 2),
                               ("excepcion", 1)):
        assert f'("{concepto}", {cantidad})' in src


def test_la_migracion_busca_el_escenario_y_no_clava_un_id():
    """⚠️ Un id clavado ata la migracion a la base de una propiedad: en
    cualquier otra no encuentra nada o, peor, encuentra otra cosa."""
    src = MIGRACION.read_text(encoding="utf-8")
    assert "WHERE hotel_id = 'AMA' AND year = 2026 AND type = 'ACTUAL'" in src
    assert "49dfca0d" not in src, "hay un id de escenario clavado"
    assert "ON CONFLICT (scenario_id, month, concepto) DO NOTHING" in src, \
        "la siembra pisaria lo que alguien ya haya cargado"


def test_la_migracion_genera_el_id():
    """⚠️ `id` es un String(36) con default de PYTHON, no de servidor: un
    INSERT crudo que lo omita revienta con NOT NULL y se lleva el deploy."""
    src = MIGRACION.read_text(encoding="utf-8")
    assert "id=str(uuid.uuid4())" in src


# ─────────────────────────── La pantalla ───────────────────────────────────

def test_la_pestana_esta_en_el_cierre():
    pag = PAGINA.read_text(encoding="utf-8")
    assert '["membresias", "Membresías"]' in pag
    assert "<Membresias scenarioId={scenarioId} mesSel={mesSel} SEL={SEL} />" in pag


def test_los_avisos_del_pms_no_salen_en_membresias():
    """Los codigos sin canal y el CPL son del reporte del PMS y no tienen nada
    que ver con el conteo. Y la barra de Guardar del archivo al lado del
    Guardar del mes serian dos botones con el mismo nombre haciendo cosas
    distintas."""
    pag = PAGINA.read_text(encoding="utf-8")
    for guarda in ('{vista !== "membresias" && sinCanal.length > 0 && (',
                   '{vista !== "membresias" && canalesFuera.length > 0 && (',
                   '{vista !== "membresias" && enPantalla && ('):
        assert guarda in pag, f"falta la guarda: {guarda}"


def test_el_total_no_es_un_input():
    """Dejarlo editable abre la puerta a que el total y sus partes digan cosas
    distintas."""
    src = COMP.read_text(encoding="utf-8")
    i = src.index("Total general")
    assert "<input" not in src[i:i + 600]
    assert "{n(totalEditado)}" in src


def test_cambiar_de_mes_descarta_lo_que_se_estaba_escribiendo():
    """⚠️ Dejar el borrador vivo haria que lo escrito para agosto se guarde
    sobre septiembre."""
    src = COMP.read_text(encoding="utf-8")
    assert "useEffect(() => { setBorrador(null); setOk(null); }, [mesSel]);" in src


# ──────────────── La siembra de enero a mayo (migracion 146) ───────────────

MIG146 = (pathlib.Path(__file__).resolve().parent.parent
          / "alembic/versions/146_membresias_activas_de_enero_a_mayo.py")


def test_se_siembran_las_activas_de_enero_a_mayo():
    """Owner: *«siembra aca solo las activas lo otro no lo tomes en cuenta y
    solo 2026»*, con el cuadro de facturacion del club."""
    src = MIG146.read_text(encoding="utf-8")
    for mes, activas in ((1, 62), (2, 69), (3, 74), (4, 83), (5, 85)):
        assert f"({mes}, {activas})" in src, f"falta el mes {mes}"


def test_diciembre_2025_NO_entra():
    """⚠️ El escenario es de 2026 y su mes 12 es diciembre **2026**.

    Meter ahi el conteo de diciembre 2025 (46) pondria un dato de otro año
    bajo un rotulo que dice 2026, y nada lo avisaria: el numero se ve
    razonable y encaja en la serie.
    """
    src = MIG146.read_text(encoding="utf-8")
    assert "(12, 46)" not in src
    assert "46" not in src.split("ACTIVAS_2026 = ")[1].split("]")[0]


def test_solo_se_siembra_activas_y_no_el_resto_del_cuadro():
    """El cuadro traia FACTURADO, PAGADO y PENDIENTE. El owner pidio que no se
    tomen en cuenta: media tabla cargada y media inventada es peor que una
    tabla que dice solo lo que se sabe."""
    src = MIG146.read_text(encoding="utf-8")
    cuerpo = src.split("def upgrade")[1]
    assert "'activas'" in cuerpo
    for otro in ("condicionados", "plan_pago", "pendiente_firma", "excepcion"):
        assert otro not in cuerpo, f"se sembro {otro}, que el cuadro no traia"


def test_junio_y_julio_quedan_sin_cargar():
    """⚠️ El cuadro salta de mayo a agosto. Un cero en junio y julio diria que
    el club se quedo sin membresias activas dos meses y volvio con 92."""
    src = MIG146.read_text(encoding="utf-8")
    assert "(6, " not in src.split("ACTIVAS_2026 = ")[1].split("]")[0]
    assert "(7, " not in src.split("ACTIVAS_2026 = ")[1].split("]")[0]


def test_la_siembra_no_pisa_lo_que_alguien_cargo():
    src = MIG146.read_text(encoding="utf-8")
    assert "ON CONFLICT (scenario_id, month, concepto) DO NOTHING" in src
    assert "id=str(uuid.uuid4())" in src
    assert "49dfca0d" not in src, "hay un id de escenario clavado"
