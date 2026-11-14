# -*- coding: utf-8 -*-
"""Una sola tabla de membresías: se elimina `club_membership_stats`.

Owner, 2026-11-13: *«cómo me deshago de esas tablas viejas… me tienen hasta los
cojones»*. Tenía razón: esa tabla costó tres problemas distintos en una semana.

## Qué pasaba

Había **dos tablas de membresías conviviendo**:

* `club_membership_stats` — cuatro columnas fijas, con el **total guardado
  aparte** de sus partes.
* `membresias_mes` — una fila por concepto, nacida el 29-sep-2026 con el tab de
  MEMBRESÍAS, donde el total **es la suma**.

Nadie las conciliaba, así que decían cosas distintas sobre el mismo hecho y
ninguna avisaba:

* la pantalla del Club mostraba **Pagando 100** mientras las estadísticas
  decían **activas 125** para el mismo escenario — **$60.000 de ingreso del
  Club** de diferencia, porque la cuota se calcula como socios × precio;
* la tabla vieja llegó a tener `total = 0` junto a `pagando = 86`, dos números
  sobre el mismo mes que no podían ser ciertos a la vez;
* y el total del año del reporte salía de una y el desglose de la otra.

El modo de falla era siempre el mismo: **el total seguía cuadrando consigo
mismo**, así que no había error ni alerta. Sólo se veía comparando pantallas.

## Qué se hizo antes de borrar

Los seis consumidores pasaron a `membresias_mes` a través de
`estadisticas.membresias_puente.vista_legado`, que arma los cuatro campos de
siempre desde los conceptos: la pantalla del Club, el P&L, su detalle, el
clonado de escenarios, el importador del mayor y el Excel de detalle.

Se verificó que **ningún mes vivía sólo en la tabla vieja** antes de soltarla.
Y el owner decidió el número en disputa: manda el presupuesto, 100 pagando. Los
25 socios que no quedaban clasificados se cargaron como condicionados, para que
el total siga siendo 130 = 100 + 25 + 2 + 2 + 1.

⚠️ **La bajada no recupera los datos.** Rehace la tabla vacía, que es lo
honesto: reconstruir los cuatro campos desde los conceptos inventaría el
reparto que esta migración justamente vino a eliminar.
"""
import sqlalchemy as sa
from alembic import op

revision = "155"
down_revision = "154"
branch_labels = None
depends_on = None

TABLA = "club_membership_stats"


def upgrade() -> None:
    op.drop_table(TABLA)


def downgrade() -> None:
    # Se rehace la estructura, vacía. Ver el ⚠️ de arriba.
    op.create_table(
        TABLA,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36),
                  sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
                  index=True, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("condicionados", sa.Integer, nullable=False,
                  server_default="0"),
        sa.Column("pagando", sa.Integer, nullable=False, server_default="0"),
        sa.Column("acuerdo_pago", sa.Integer, nullable=False,
                  server_default="0"),
        sa.UniqueConstraint("scenario_id", "month",
                            name="uq_club_membership_stat"),
    )
