# -*- coding: utf-8 -*-
"""El rótulo con que el PMS nombra cada categoría, y a qué categoría es.

**Por qué existe (owner, 2026-09-10).** El PDF de Skill4 trae los nombres del
PMS y la base los de la propiedad, y no son los mismos textos. Hasta ahora ese
calce se resolvía en la pantalla, por archivo, y **moría al descartar el PDF**:
subir doce meses significaba tomar la misma decisión doce veces. Con seis meses
para cargar de una sentada, el owner pidió verlo y fijarlo en un lugar — «un
tab de mapping: las que salen en el pdf versus las que hay en master data».

Es el mismo patrón que `market_codes`, y por el mismo motivo: el rótulo del PMS
es el átomo que trae el archivo, y a qué cosa de la propiedad corresponde es
una decisión que se toma una vez y se guarda.

## Apunta al CÓDIGO, no al nombre

`room_type_code` y no `room_type_name`. El código es lo estable: es del grupo,
es igual en las cuatro propiedades y **no se cambia jamás** — el nombre sí se
edita cuando alguien quiere que se lea distinto. Un mapeo guardado contra el
nombre se rompería solo el día que se corrige una tilde en Master Data, y se
rompería en silencio: el rótulo dejaría de calzar y las noches volverían a caer
en «sin categoría».

⚠️ Al aplicarlo hay que resolver `código → nombre de hoy`, porque lo que se
guarda en `actual_room_stats.room_type_name` sigue siendo el nombre.

⚠️ **Un rótulo sin mapeo no se adivina.** Queda vacío y se reporta, igual que un
market code sin canal. La pantalla puede seguir proponiendo un parecido —eso
hace `_calce`—, pero propuesto y guardado son cosas distintas: lo propuesto se
muestra como «probable» y espera una confirmación.
"""
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmsRoomLabel(Base):
    """`(hotel, rótulo del PMS) -> código de categoría de la propiedad`."""

    __tablename__ = "pms_room_labels"
    __table_args__ = (
        UniqueConstraint("hotel_id", "label", name="uq_pms_room_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    hotel_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("hotels.id"), index=True)

    #: El texto TAL COMO lo imprime el PMS. Es lo que trae el archivo y lo
    #: único con lo que se puede volver a reconocer la fila el mes que viene.
    label: Mapped[str] = mapped_column(String(160))

    #: El código de `room_type_configs`. Ver el porqué en el docstring: el
    #: código no se mueve, el nombre sí.
    room_type_code: Mapped[str] = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"<PmsRoomLabel {self.label!r} -> {self.room_type_code}>"
