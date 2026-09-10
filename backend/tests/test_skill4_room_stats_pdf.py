# -*- coding: utf-8 -*-
"""El PDF del PMS de Amarena se lee, cuadra, y no se guarda.

El fixture es el archivo real de **marzo 2026** («03-MARZO 2026 - X
HABITACION.PDF», Skill4 Front Desk, entidad Mistico Beach Club). Los números
esperados están escritos a mano desde el propio PDF: si alguien cambia el
lector y el test sigue verde, es porque sigue leyendo lo que el archivo dice.

⚠️ **Lo que estos tests cuidan es que las columnas no se corran.** El PDF trae
Entradas y Estancias pegadas, para habitaciones y para clientes — cuatro
números seguidos que se parecen. Tomar la columna de al lado da un ADR
plausible y un reporte equivocado, y nada en la pantalla lo delataría. Por eso
se afirma columna por columna y no solo el total.
"""
from pathlib import Path

import pytest

from app.importers.skill4_room_stats_pdf import _num, leer_pdf_skill4

PDF = Path(__file__).parent / "fixtures" / "skill4_amarena_marzo_2026.pdf"

#: Del PDF, fila «TOTALES TIPO HAB» de cada categoría:
#: (ingreso, hab-entradas, hab-estancias, cli-entradas, cli-estancias, tarifa)
ESPERADO = {
    "BEACH FRONT DLXE VILLA":   (2481.43, 15, 21, 30, 42, 118.16),
    "BEACH FRONT MASTER VILLA": (3305.60, 7, 13, 15, 27, 254.28),
    "GARDEN VIEW DLXE VILLA":   (610.62, 12, 17, 25, 38, 35.92),
}


@pytest.fixture(scope="module")
def lectura():
    pytest.importorskip("pdfplumber")
    return leer_pdf_skill4(PDF.read_bytes())


def test_periodo_y_entidad(lectura):
    """El mes sale de «Desde:../Hasta:..», no de la fecha de impresión.

    El PDF trae «Fecha: 09/09/2026» arriba —cuándo se imprimió— y el período
    real es marzo. Leer la primera fecha que aparece archivaría marzo bajo
    septiembre.
    """
    assert (lectura.year, lectura.month) == (2026, 3)
    assert lectura.moneda == "USD"
    assert "Mistico" in lectura.entidad


def test_una_fila_por_categoria_y_agencia(lectura):
    assert len(lectura.filas) == 9
    assert {f.room_type_name for f in lectura.filas} == set(ESPERADO)
    beach = [f for f in lectura.filas if f.room_type_name == "BEACH FRONT DLXE VILLA"]
    assert {f.agencia for f in beach} == {
        "CPL", "DIRECTOS", "EXPEDIA HOTEL COLLECT", "RESONLINE"}


@pytest.mark.parametrize("categoria", sorted(ESPERADO))
def test_cada_columna_en_su_lugar(lectura, categoria):
    """Entradas ≠ Estancias: se afirman las cuatro por separado."""
    ingreso, hab_ent, hab_est, cli_ent, cli_est, tarifa = ESPERADO[categoria]
    t = next(x for x in lectura.por_tipo() if x["room_type_name"] == categoria)
    assert t["revenue"] == pytest.approx(ingreso, abs=0.01)
    assert t["hab_entradas"] == pytest.approx(hab_ent)
    assert t["nights_occupied"] == pytest.approx(hab_est)   # Estancias de Habitaciones
    assert t["cli_entradas"] == pytest.approx(cli_ent)
    assert t["pax"] == pytest.approx(cli_est)               # Estancias de Clientes
    # El ADR calculado tiene que dar la «Tarifa Prom.» que imprime el PDF.
    # Es la comprobación independiente de que las noches son las correctas:
    # con Entradas en vez de Estancias, este número no da.
    assert t["adr"] == pytest.approx(tarifa, abs=0.02)


def test_el_gran_total_del_archivo(lectura):
    assert lectura.total_general["ingreso_hospedaje"] == pytest.approx(6397.65, abs=0.01)
    assert lectura.total_general["hab_estancias"] == pytest.approx(51)
    assert lectura.total_general["cli_estancias"] == pytest.approx(107)


def test_resumen_estadistico(lectura):
    """Las dos cifras de habitaciones del resumen, que NO coinciden entre sí.

    496 es el inventario completo (16 × 31) y 238 lo que quedó disponible
    después de 258 bloqueadas. De ahí salen los dos porcentajes de ocupación
    del PDF, 10.28% y 21.43%. El lector devuelve las dos y no elige.
    """
    r = lectura.resumen
    assert (r.dias, r.capacidad_hab) == (31, 16)
    assert r.habitaciones_totales == 496
    assert r.habitaciones_disponibles == 238
    assert r.habitaciones_bloqueadas == 258
    assert r.ocupacion_sobre_total == pytest.approx(10.28, abs=0.01)
    assert r.ocupacion_sobre_disponibles == pytest.approx(21.43, abs=0.01)


def test_otros_ingresos_se_despejan_del_total(lectura):
    """«Total de Ingresos:» aparece tres veces en el resumen, con tres
    significados distintos, porque las dos columnas del PDF se aplanan en una
    sola línea. Otros ingresos se despeja restando en vez de leerse."""
    r = lectura.resumen
    assert r.ingreso_hospedaje == pytest.approx(6397.65, abs=0.01)
    assert r.ingreso_puntos_venta == pytest.approx(0.0, abs=0.01)
    assert r.ingreso_otros == pytest.approx(209.23, abs=0.01)
    assert r.ingreso_total_hotel == pytest.approx(6606.88, abs=0.01)


def test_el_archivo_cuadra(lectura):
    """La suma del detalle da los totales que el propio PDF declara.

    Son tres caminos independientes —detalle por agencia, «TOTALES TIPO HAB»
    y el resumen de la última página— y tienen que coincidir. Cuando no
    coinciden, la pantalla lo muestra en vez de guardar un mes torcido.
    """
    assert lectura.cuadre() == []


def test_un_archivo_de_varios_meses_se_rechaza(monkeypatch):
    """El reporte se procesa de a un mes. Un rango que cruza meses no se
    reparte por adivinanza: se rechaza con el rango a la vista."""
    from app.importers import skill4_room_stats_pdf as mod
    original = mod._texto
    monkeypatch.setattr(mod, "_texto", lambda b: [
        ln.replace("Hasta: 31/03/2026", "Hasta: 30/04/2026") for ln in original(b)])
    with pytest.raises(ValueError, match="mas de un mes"):
        leer_pdf_skill4(PDF.read_bytes())


def test_pdf_sin_filas_avisa_que_es_otro_reporte(monkeypatch):
    from app.importers import skill4_room_stats_pdf as mod
    monkeypatch.setattr(mod, "_texto", lambda b: ["Otro reporte cualquiera", "sin tablas"])
    with pytest.raises(ValueError, match="Estadistica de Explotacion"):
        leer_pdf_skill4(b"x")


@pytest.mark.parametrize("crudo,esperado", [
    ("1,460.00", 1460.0),      # americano
    ("1.460,00", 1460.0),      # europeo
    ("(120.00)", -120.0),      # negativo contable
    ("6397.65", 6397.65),
    ("0.00", 0.0),
    ("", 0.0),
])
def test_numeros_en_los_dos_formatos(crudo, esperado):
    """Los PDF del grupo mezclan separador americano y europeo. `1.460,00`
    leído como americano daría 1.46 — tres órdenes de magnitud menos."""
    assert _num(crudo) == pytest.approx(esperado)
