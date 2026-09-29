# -*- coding: utf-8 -*-
"""El resumen del hotel que cierra el reporte del PMS, por mes.

Owner, 2026-09-29, pidiendo el Resumen Consolidado en el Dashboard: *«quiero
que pegues este reporte aca en el dashboard»*.

## Por qué existe

El PDF de Skill4 termina con un bloque que **no es por categoría**: es del
hotel entero.

    RESUMEN ESTADISTICO: Desde:01/03/2026 Hasta:31/03/2026 Total de Dias: 31
    Capacidad de Hab: 16 Total de Habitac: 496
    Total de Hab Disp: 238 Total Hab Bloq: 258
    Total de Ingresos del Hotel: 6606.88 (USD)

Hasta hoy ese bloque **se leía para cuadrar y se tiraba**. `actual_room_stats`
guarda por categoría, y las habitaciones disponibles y bloqueadas no son de
ninguna categoría: son del hotel. Sin ellas no hay «% Ocupación sobre
habitaciones disponibles», que es la ocupación que la propiedad mira — en
marzo 2026 da 21.4% contra el 10.3% sobre el inventario completo, porque ese
mes hubo 258 habitaciones-noche bloqueadas de 496.

## ⚠️ Disponibles y bloqueadas NO se calculan

Son un hecho operativo del mes: cuántas habitaciones estuvieron fuera de
servicio. No salen de multiplicar nada. Si no vienen en el archivo, se quedan
vacías y la ocupación sobre disponibles no se muestra — inventarlas como
«capacidad menos lo que no se vendió» daría un número que se ve razonable y
no significa nada.

## ⚠️ Sólo el PDF los trae

La base plana («Datos») es sólo el detalle por agencia. Un mes cargado desde
el Excel deja este resumen vacío, y eso es correcto: el archivo no lo dice.
"""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActualRoomStatMes(Base):
    __tablename__ = "actual_room_stats_mes"
    __table_args__ = (
        UniqueConstraint("scenario_id", "month", name="uq_roomstat_mes"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), index=True)
    month: Mapped[int] = mapped_column(Integer)

    #: Unidades del hotel según el PMS. Se guarda para poder CONTRASTARLA con
    #: `RoomTypeConfig`: si el PMS dice 16 y el Master Data dice 15, alguien
    #: tiene que enterarse. No se usa para calcular — el inventario manda
    #: desde Master Data (ver la migración 143).
    capacidad_hab: Mapped[int] = mapped_column(Integer, default=0)
    habitaciones_totales: Mapped[Decimal] = mapped_column(Numeric(12, 2),
                                                          default=Decimal("0"))
    habitaciones_disponibles: Mapped[Decimal] = mapped_column(Numeric(12, 2),
                                                              default=Decimal("0"))
    habitaciones_bloqueadas: Mapped[Decimal] = mapped_column(Numeric(12, 2),
                                                             default=Decimal("0"))

    #: Los puntos de venta NO vienen abiertos por agencia en el reporte, así
    #: que no están en `actual_room_stats`: sólo acá, a nivel hotel.
    ingreso_puntos_venta: Mapped[Decimal] = mapped_column(Numeric(14, 2),
                                                          default=Decimal("0"))
    ingreso_total_hotel: Mapped[Decimal] = mapped_column(Numeric(14, 2),
                                                         default=Decimal("0"))

    def __repr__(self) -> str:
        return (f"<RoomStatMes {self.month:02d} disp={self.habitaciones_disponibles}"
                f" bloq={self.habitaciones_bloqueadas}>")
