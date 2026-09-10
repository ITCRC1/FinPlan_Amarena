# -*- coding: utf-8 -*-
"""El detalle por CANAL de la estadística de habitaciones real.

**Por qué existe (owner, 2026-09-09).** El PDF del PMS abre cada categoría por
agencia —CPL, DIRECTOS, EXPEDIA, RESONLINE— y hasta ahora ese detalle vivía
sólo mientras la pantalla estaba abierta: al guardar se escribían las filas por
categoría (`actual_room_stats`) y el canal se perdía.

Preguntando por el acumulado de abril a agosto quedó claro el costo: el mix de
canales histórico **no se puede reconstruir**, y es justo donde está lo que no
se ve en el total. En marzo 2026, CPL puso el **60.8% de las noches** con el
**0.7% del ingreso**; el ADR del mes pasa de $125.44 a $317.66 según se lo
cuente o no. Sin esta tabla, esa lectura existe un rato y después hay que
volver a subir los seis PDF.

## Cómo se relaciona con lo que ya había

`actual_room_stats` **sigue siendo la verdad del mes** por categoría: es lo que
leen el Room Stats, el P&L y los KPIs. Esta tabla es su APERTURA, y la suma de
sus filas de un mes tiene que dar la fila de `actual_room_stats` de ese mes.
Las dos se escriben en la misma transacción, desde el mismo endpoint, por eso
mismo.

⚠️ **No es una segunda fuente.** Si algún reporte empezara a leer el total
desde acá, cualquier diferencia de redondeo entre las dos tablas se volvería
una diferencia entre dos pantallas que dicen medir lo mismo.

## El canal

`canal_code` es el código **tal como lo imprime el PMS**, que es lo que el
archivo trae y lo único estable. A qué canal canónico pertenece —Travel Agent,
OTA, Direct Client, Website, INHOUSE— lo dice `market_codes`, con la regla que
ya rige ahí: un código sin canal no se adivina, se muestra vacío y se reporta.
"""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActualRoomStatCanal(Base):
    """Noches, pax e ingreso reales por (escenario, mes, categoría, canal)."""

    __tablename__ = "actual_room_stat_canales"
    __table_args__ = (
        UniqueConstraint("scenario_id", "month", "room_type_name", "canal_code",
                         name="uq_roomstat_canal"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), index=True)
    month: Mapped[int] = mapped_column(Integer)            # 1..12

    #: El MISMO literal que `actual_room_stats.room_type_name`. Es lo que ata
    #: la apertura con su total; un rótulo distinto la deja huérfana.
    room_type_name: Mapped[str] = mapped_column(String(120))

    #: El código de agencia tal como lo imprime el PMS («CPL», «RESONLINE»).
    canal_code: Mapped[str] = mapped_column(String(40), index=True)

    nights_occupied: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    pax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))

    def __repr__(self) -> str:
        return (f"<RoomStatCanal {self.month:02d} {self.room_type_name} "
                f"/{self.canal_code} {self.nights_occupied}n>")
