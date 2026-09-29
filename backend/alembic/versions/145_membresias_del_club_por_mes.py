# -*- coding: utf-8 -*-
"""Las membresías del club, por mes, y agosto 2026 sembrado.

Owner, 2026-09-29: *«que aca incluyas este tab llamado MEMBRESIAS de la misma
forma en que esta la imagen. que se pueda actualizar manualmente por mes. o que
se pueda bajar o subir con un excel»*.

## Qué es

El cobro de la cuota de mantenimiento del club. **No sale del PMS**: es un
conteo que lleva la propiedad y que hasta hoy vivía en una diapositiva.

    Activas de cobro al 31 de agosto 2026     92
    Condicionados a 2da etapa club            33
    Pendiente de firma de contrato             2
    Plan de pago                               2
    Excepción «no paga»                        1
    ──────────────────────────────────────────────
    Total general                            130

## Qué NO guarda

El **total**. Es la suma de los conceptos y se calcula al mostrarlo. Guardarlo
abre la puerta a que el total y sus partes digan cosas distintas —el modo de
falla que no avisa— y a que alguien «corrija» el total sin tocar los renglones.

Y el **rótulo** de cada concepto: se guarda la clave (`activas`), no el texto.
El de `activas` lleva la fecha del cierre —«al 31 de agosto 2026»— y guardarlo
congelaría agosto dentro de la fila de septiembre.

## La siembra

Agosto 2026 va con las cifras de arriba, que son las que el owner mandó.

⚠️ Se busca el escenario por hotel + año + tipo ACTUAL, **no por id**: un id
clavado acá ata la migración a la base de una propiedad y en cualquier otra no
encuentra nada o, peor, encuentra otra cosa. Si no hay un ACTUAL 2026, no se
siembra y listo: la pantalla arranca vacía y se carga a mano.

⚠️ Y **no pisa** lo que ya esté: si alguien cargó agosto antes de que esto
corra, manda lo suyo.

Revision ID: 145
Revises: 144
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "145"
down_revision = "144"
branch_labels = None
depends_on = None

#: (concepto, cantidad) de agosto 2026, tal como los mandó el owner.
AGOSTO_2026 = [
    ("activas", 92),
    ("condicionados", 33),
    ("pendiente_firma", 2),
    ("plan_pago", 2),
    ("excepcion", 1),
]


def upgrade() -> None:
    op.create_table(
        "membresias_mes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), nullable=False, index=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("concepto", sa.String(60), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 2), nullable=False,
                  server_default="0"),
        sa.UniqueConstraint("scenario_id", "month", "concepto",
                            name="uq_membresia_scenario_month_concepto"),
    )

    conn = op.get_bind()
    escenario = conn.execute(sa.text("""
        SELECT id FROM scenarios
         WHERE hotel_id = 'AMA' AND year = 2026 AND type = 'ACTUAL'
         ORDER BY id LIMIT 1
    """)).scalar()
    if not escenario:
        return

    for concepto, cantidad in AGOSTO_2026:
        # `ON CONFLICT DO NOTHING`: si alguien ya cargó agosto, manda lo suyo.
        conn.execute(sa.text("""
            INSERT INTO membresias_mes (id, scenario_id, month, concepto, cantidad)
            VALUES (:id, :sc, 8, :c, :n)
            ON CONFLICT (scenario_id, month, concepto) DO NOTHING
        """).bindparams(id=str(uuid.uuid4()), sc=escenario, c=concepto, n=cantidad))


def downgrade() -> None:
    op.drop_table("membresias_mes")
