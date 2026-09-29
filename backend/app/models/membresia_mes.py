# -*- coding: utf-8 -*-
"""Las membresías del club, por mes — el cobro de la cuota de mantenimiento.

Owner, 2026-09-29: *«que aca incluyas este tab llamado MEMBRESIAS de la misma
forma en que esta la imagen. que se pueda actualizar manualmente por mes. o
que se pueda bajar o subir con un excel»*.

## Qué es y de dónde sale

No sale del PMS. Es un conteo que lleva la propiedad: cuántas membresías están
activas de cobro al cierre del mes, y en qué estado están las demás.

    Activas de cobro al 31 de agosto 2026     92
    Condicionados a 2da etapa club            33
    Pendiente de firma de contrato             2
    Plan de pago                               2
    Excepción «no paga»                        1
    ──────────────────────────────────────────────
    Total general                            130

⚠️ **El total NO se guarda.** Es la suma de los conceptos y se calcula al
mostrarlo. Guardarlo abriría la puerta a que el total y sus partes digan cosas
distintas —el modo de falla que no avisa— y a que alguien «corrija» el total
sin tocar los renglones.

## Por qué una fila por concepto y no cinco columnas

Los estados del cobro son de la propiedad y van a cambiar: hoy hay una segunda
etapa del club, mañana habrá una tercera. Con columnas, cada estado nuevo es
una migración; con filas, es un renglón.

⚠️ Un concepto que no esté en `CONCEPTOS` **no se descarta**: se muestra al
final. Esconder lo que no se reconoce haría desaparecer un conteo que alguien
cargó, y el total dejaría de cuadrar contra el papel sin que se vea por qué.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

#: Los conceptos canónicos, en el orden del reporte de la propiedad.
#: `clave` es lo que se persiste y no cambia; el rótulo se puede reescribir sin
#: tocar un solo dato guardado.
#:
#: ⚠️ El rótulo de `activas` lleva la FECHA del cierre, así que se arma al
#: mostrarlo —«al 31 de agosto 2026»—: guardarlo congelaría agosto dentro de la
#: fila de septiembre.
CONCEPTOS: list[tuple[str, str]] = [
    ("activas", "Activas de cobro al {cierre}"),
    ("condicionados", "Condicionados a 2da etapa club"),
    ("pendiente_firma", "Pendiente de firma de contrato"),
    ("plan_pago", "Plan de pago"),
    ("excepcion", "Excepción «no paga»"),
]


class MembresiaMes(Base):
    __tablename__ = "membresias_mes"
    __table_args__ = (
        UniqueConstraint("scenario_id", "month", "concepto",
                         name="uq_membresia_scenario_month_concepto"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    #: Sin `ondelete` no: si se borra el escenario, este conteo no tiene dueño.
    scenario_id: Mapped[str] = mapped_column(String(36), index=True)
    month: Mapped[int] = mapped_column(Integer)          # 1..12
    concepto: Mapped[str] = mapped_column(String(60))
    #: `Numeric` y no `Integer`: son conteos hoy, pero el día que la propiedad
    #: cargue un monto de cuota acá no hay que migrar el tipo.
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2),
                                              default=Decimal("0"))

    def __repr__(self) -> str:
        return f"<Membresia {self.month:02d} {self.concepto}={self.cantidad}>"
