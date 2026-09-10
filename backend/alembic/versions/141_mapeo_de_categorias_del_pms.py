# -*- coding: utf-8 -*-
"""El calce entre el rótulo del PMS y la categoría de la propiedad se guarda.

Owner, 2026-09-10: *«necesito que hagas un tab de mapping: las que salen en el
pdf versus las que hay en master data»*, y *«ya tengo de marzo a Agosto para
subir»*.

El calce se resolvía en la pantalla y moría con el PDF: seis meses eran seis
veces la misma decisión, y cada vez una oportunidad de elegir distinto. Un
calce que cambia de un mes a otro parte la serie en dos sin que nada avise —el
mes viejo quedó bajo una categoría y el nuevo bajo otra, y los dos totales
siguen cuadrando contra su propio archivo.

`pms_room_labels` guarda `(hotel, rótulo del PMS) -> código de categoría`.
Apunta al CÓDIGO porque el código es del grupo y no se cambia; el nombre se
edita. Ver `app/models/pms_room_label.py`.

Aditiva y reversible: la tabla nace vacía y, mientras esté vacía, la lectura se
comporta igual que antes —propone por parecido y espera confirmación—.

Revision ID: 141
Revises: 140
"""
import sqlalchemy as sa
from alembic import op

revision = "141"
down_revision = "140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pms_room_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("hotel_id", sa.String(10),
                  sa.ForeignKey("hotels.id"), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("room_type_code", sa.String(20), nullable=False),
    )
    op.create_index("ix_pms_room_labels_hotel", "pms_room_labels", ["hotel_id"])
    # Un rótulo del PMS apunta a UNA categoría por propiedad. Sin esto, dos
    # filas contradictorias del mismo rótulo se resolverían por orden de
    # lectura —o sea al azar— y las noches irían a una categoría distinta
    # segun el dia.
    op.create_unique_constraint("uq_pms_room_label", "pms_room_labels",
                                ["hotel_id", "label"])


def downgrade() -> None:
    op.drop_constraint("uq_pms_room_label", "pms_room_labels", type_="unique")
    op.drop_index("ix_pms_room_labels_hotel", table_name="pms_room_labels")
    op.drop_table("pms_room_labels")
