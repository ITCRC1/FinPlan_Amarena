# -*- coding: utf-8 -*-
"""El Owners Fee del Club deja de ser honorario: 8005/260 → 7716 Fees Madresal.

Owner, 2026-11-27: *«la 8005 para el 260 desaparece»*. Los honorarios del Club
pasan a ser gasto operativo del Club, con cuenta propia, y de paso nace la 7717
para las cuotas condominales.

## Qué cambia

  · `7716 Fees Madresal` y `7717 Cuotas Condominales`, las dos en el
    departamento 260 y en la línea `OPEX_CLUB`.
  · El mayor del 260 se RECODIFICA: las filas de 8005 pasan a 7716. Son
    $8.342,28 en tres meses — junio 2.490,43 · julio 3.451,85 · setiembre
    2.400,00.
  · La regla de mapeo `260 + 8005` se borra. La 8005 del **0250** no se toca.

⚠️ **Esto mueve plata de abajo del GOP a arriba.** Esos $8.342,28 eran
«Management Fees (3%)», que van después del GOP; como gasto operativo del Club
el **GOP baja** y la utilidad del Club baja lo mismo. El EBITDA no se mueve: es
una reclasificación, no un costo nuevo.

⚠️ **Contabilidad tiene que cargar 7716 de aquí en adelante.** Subir un mes
reemplaza el mes completo, así que si el archivo de Integrity vuelve a traer
8005 en el 260, esa plata entra sin regla de mapeo y queda fuera del reporte.

Va junto con `app/seed_data/mapping_pl.json`: sin eso el seed devolvería la
8005/260 en el próximo despliegue y borraría las dos nuevas (CLAUDE.md, «el SEED
manda»).

Revision ID: 161
Revises: 160
"""
import sqlalchemy as sa
from alembic import op

revision = "161"
down_revision = "160"
branch_labels = None
depends_on = None

REPORT = "P&L_DETAIL_OWNERS"
DEPTO = "Departamento de Club Madresal"
DEPT_CODE = "260"
VIEJA = "8005"
NUEVAS = [("7716", "Fees Madresal"), ("7717", "Cuotas Condominales")]

_ALTA = sa.text("""
    INSERT INTO account_mapping (
        id, active_status, report_id, report_line_code, report_line_name,
        report_section, display_order, source_origin, source_department,
        account_code, account_name_example, financial_nature,
        rollup_operator, sign_rule, notes, dept_code)
    SELECT gen_random_uuid()::text, 'YES', :report, 'OPEX_CLUB',
           'Club Madresal', 'OPERATING EXPENSES', 46, 'Operating Expense',
           :depto, :cuenta, :nombre, 'Expense', 'SUM',
           'Aggregate to line as positive display value; calculations '
           'subtract expense lines at subtotal level.',
           :nota, :dept_code
    WHERE NOT EXISTS (
        SELECT 1 FROM account_mapping
         WHERE report_id = :report AND dept_code = :dept_code
           AND account_code = :cuenta AND active_status = 'YES')
""")


def upgrade() -> None:
    nota = ("Agregado 2026-11-27: gasto operativo del Club. La 7716 recibe lo "
            "que estaba en 8005/260 (honorarios bajo GOP).")
    for cuenta, nombre in NUEVAS:
        op.execute(_ALTA.bindparams(report=REPORT, depto=DEPTO, cuenta=cuenta,
                                    nombre=nombre, nota=nota, dept_code=DEPT_CODE))

    # El mayor: la plata se mueve de cuenta, no de departamento ni de mes.
    op.execute(sa.text("""
        UPDATE actual_entries SET account_code = '7716',
                                  account_name = 'Fees Madresal'
         WHERE account_code = :vieja AND dept_code = :dept_code
    """).bindparams(vieja=VIEJA, dept_code=DEPT_CODE))

    # Y la regla que la mandaba a honorarios deja de existir. Solo la del 260:
    # la 8005 del 0250 sigue siendo el Management Fee de la propiedad.
    op.execute(sa.text("""
        DELETE FROM account_mapping
         WHERE report_id = :report AND dept_code = :dept_code
           AND account_code = :vieja
    """).bindparams(report=REPORT, dept_code=DEPT_CODE, vieja=VIEJA))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE actual_entries SET account_code = :vieja,
                                  account_name = 'OWNERS FEES'
         WHERE account_code = '7716' AND dept_code = :dept_code
    """).bindparams(vieja=VIEJA, dept_code=DEPT_CODE))
    op.execute(sa.text("""
        DELETE FROM account_mapping
         WHERE report_id = :report AND dept_code = :dept_code
           AND account_code IN ('7716', '7717')
    """).bindparams(report=REPORT, dept_code=DEPT_CODE))
