# -*- coding: utf-8 -*-
"""Las membresías activas de enero a mayo 2026.

Owner, 2026-09-29, mandando el cuadro de facturación del club: *«siembra aca
solo las activas lo otro no lo tomes en cuenta y solo 2026»*.

    MES              ACTIVAS
    DICIEMBRE 2025        46   ← fuera: no es 2026
    ENERO 2026            62
    FEBRERO 2026          69
    MARZO 2026            74
    ABRIL 2026            83
    MAYO 2026             85

## Lo que el cuadro traía y NO se siembra

El cuadro original tiene además FACTURADO, MONTO PAGADO y MONTO PENDIENTE
($83.200 / $81.800 / $1.200 acumulados). El owner pidió expresamente que no
se tomen en cuenta, así que no entran: media tabla cargada y media inventada
es peor que una tabla que dice sólo lo que se sabe.

Diciembre 2025 tampoco entra. Este escenario es de 2026 y su mes 12 es
diciembre **2026**: meter ahí el conteo de 2025 pondría un dato de otro año
bajo un rótulo que dice 2026, y nada lo avisaría.

## Junio y julio no se tocan

El cuadro salta de mayo a —en el otro reporte— agosto. Junio y julio quedan
**sin cargar**, que no es lo mismo que en cero: un cero diría que el club se
quedó sin membresías activas dos meses y volvió con 92.

## ⚠️ Los otros cuatro conceptos

De enero a mayo sólo se conoce «activas». Los demás —condicionados, pendiente
de firma, plan de pago, excepción— no se escriben, así que esos meses se leen
con esos renglones en cero y el total igual a las activas. Es lo que se sabe;
se completan en la pantalla cuando la propiedad tenga el desglose.

Agosto ya quedó sembrado por la migración 145 y no se toca.

Revision ID: 146
Revises: 145
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "146"
down_revision = "145"
branch_labels = None
depends_on = None

#: (mes, activas). Sólo 2026 y sólo la columna ACTIVAS, como pidió el owner.
ACTIVAS_2026 = [(1, 62), (2, 69), (3, 74), (4, 83), (5, 85)]


def upgrade() -> None:
    conn = op.get_bind()
    escenario = conn.execute(sa.text("""
        SELECT id FROM scenarios
         WHERE hotel_id = 'AMA' AND year = 2026 AND type = 'ACTUAL'
         ORDER BY id LIMIT 1
    """)).scalar()
    if not escenario:
        return

    for mes, activas in ACTIVAS_2026:
        # `DO NOTHING`: si alguien ya cargó el mes en la pantalla, manda lo
        # suyo. Una migración no le pisa el trabajo a nadie.
        conn.execute(sa.text("""
            INSERT INTO membresias_mes (id, scenario_id, month, concepto, cantidad)
            VALUES (:id, :sc, :m, 'activas', :n)
            ON CONFLICT (scenario_id, month, concepto) DO NOTHING
        """).bindparams(id=str(uuid.uuid4()), sc=escenario, m=mes, n=activas))


def downgrade() -> None:
    conn = op.get_bind()
    for mes, activas in ACTIVAS_2026:
        # Sólo la fila que esta migración pudo haber creado, y sólo si sigue
        # con el valor que sembró: si alguien lo corrigió, se le respeta.
        conn.execute(sa.text("""
            DELETE FROM membresias_mes
             WHERE month = :m AND concepto = 'activas' AND cantidad = :n
        """).bindparams(m=mes, n=activas))
