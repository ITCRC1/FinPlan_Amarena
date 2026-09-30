import type { DetalleCelda, Scenario } from "@/lib/api";
import type { Cuadro, ColumnaCuadro, FilaCuadro } from "@/lib/exportCuadro";
import { celdasDe, cortesDe, parDe, suma, type Corte } from "@/lib/tresCortes";

/**
 * El checkbook en los TRES cortes: mes, YTD y full year, con su varianza.
 *
 * Owner, 2026-09-30: *«en todas las opciones de los checkbooks, además de la
 * vista de 12 meses, quiero también tener la opción de comparar el actual
 * versus Budget del mes, YTD del mes y Budget, y Full year Forecast versus
 * Budget. en realidad que sean 2 vistas fijas: 12 meses, y mes-YTD-Full year.
 * eso para Opex, Salarios, Costo de ventas y Gastos de propiedad»*.
 *
 * ## Es la MISMA plantilla que el P&L en tres cortes
 *
 * `cortesDe`, `parDe`, `celdasDe` y `suma` salen de `lib/tresCortes` sin una
 * copia. El checkbook y el P&L tienen que cortar el año por los mismos meses y
 * restar el mismo par, o el detalle diría una variación y el reporte otra —
 * sobre los mismos datos, y sin que nada falle.
 *
 * ⚠️ De ahí viene también la regla del **full year**: la varianza es FORECAST
 * contra Budget, no Actual contra Budget. En el año completo el Actual son los
 * meses cargados y nada más, así que restarle doce meses de presupuesto da una
 * diferencia que parece un derrumbe y sólo dice que el año no terminó.
 *
 * ## Una sola definición para la pantalla y para el Excel
 *
 * Las dos dibujan este `Cuadro`. Dos armados del mismo reporte empiezan iguales
 * y se separan en el primer arreglo que alguien hace de un lado.
 */

/** Los tres cortes de un mes. Reexportado para que la pantalla arme su fila de
 *  encabezado con exactamente los mismos que el cuadro. */
export const cortesDelCheckbook = (mes: number): Corte[] => cortesDe(mes);

/** Cuántas columnas ocupa un corte: una por versión, más la varianza si hay par
 *  que restar. */
export const anchoDelCorte = (
  c: Corte, versiones: { scenario_id: string }[], escenarios: Scenario[],
) => versiones.length + (parDe(c, versiones, escenarios) ? 1 : 0);

export function cuadroCheckbookCortes(
  rotulo: string, datos: DetalleCelda, mes: number, escenarios: Scenario[],
  dept: string, deptos: Record<string, string>,
): Cuadro {
  const versiones = datos.versiones ?? [];
  const cortes = cortesDe(mes);
  const doce = Array.from({ length: 12 }, (_, i) => i);
  const etiqueta = (sid: string) => {
    const s = escenarios.find(x => x.id === sid);
    return s ? `${s.type} ${s.version}` : sid.slice(0, 8);
  };
  const serie = (f: { series: Record<string, number[]> }, vi: number) =>
    f.series[versiones[vi]?.scenario_id ?? ""] ?? [];

  // ⚠️ La misma limpieza que la vista de doce meses: una cuenta en cero en
  // TODAS las versiones y todo el año no dice nada, y son decenas.
  const vivas = (datos.filas ?? [])
    .filter(f => !dept || f.dept_code === dept)
    .filter(f => versiones.some((_, vi) => Math.abs(suma(serie(f, vi), doce)) >= 0.005));

  /** Por departamento, que es como se lee un checkbook: la 7065 aparece en
   *  cuatro y las cuatro se llaman «Cleaning Supplies». */
  const grupos = (() => {
    const out = new Map<string, { nombre: string; filas: typeof vivas }>();
    for (const f of vivas) {
      const g = out.get(f.dept_code)
        ?? { nombre: f.dept_name || deptos[f.dept_code] || "", filas: [] };
      g.filas.push(f);
      out.set(f.dept_code, g);
    }
    return [...out.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  })();

  const columnas: ColumnaCuadro[] = [
    { label: "Cuenta", ancho: 40, formato: "texto" },
    ...cortes.flatMap(c => [
      ...versiones.map(v => ({ label: `${c.titulo} · ${etiqueta(v.scenario_id)}`,
                               ancho: 15, formato: "usd2" as const })),
      ...(parDe(c, versiones, escenarios)
        ? [{ label: `${c.titulo} · Var`, ancho: 15, formato: "usd2" as const }]
        : []),
    ]),
  ];

  const celdas = (de: (vi: number, meses: number[]) => number | null) =>
    celdasDe(cortes, versiones, escenarios, de);

  const filas: FilaCuadro[] = [];
  for (const [code, g] of grupos) {
    filas.push({
      label: g.nombre ? `${code} · ${g.nombre}` : code,
      es_total: true, nivel: 0,
      valores: celdas((vi, meses) =>
        g.filas.reduce((a, f) => a + suma(serie(f, vi), meses), 0)),
    });
    // Lo más grande primero: lo que explica el número va arriba.
    const orden = [...g.filas].sort((a, b) =>
      Math.abs(suma(serie(b, 0), doce)) - Math.abs(suma(serie(a, 0), doce)));
    for (const f of orden) {
      filas.push({
        label: `${f.cuenta}  ${f.nombre}`, es_total: false, nivel: 1,
        valores: celdas((vi, meses) => suma(serie(f, vi), meses)),
      });
    }
    filas.push({
      label: `Subtotal ${code}`, es_total: true, nivel: 1,
      valores: celdas((vi, meses) =>
        g.filas.reduce((a, f) => a + suma(serie(f, vi), meses), 0)),
    });
    filas.push({ label: "", valores: [] });
  }
  filas.push({
    label: "TOTAL", es_total: true, nivel: 0,
    valores: celdas((vi, meses) =>
      vivas.reduce((a, f) => a + suma(serie(f, vi), meses), 0)),
  });

  return {
    titulo: `Checkbook · ${rotulo} · mes, YTD y full year`,
    subtitulo: `${datos.versiones?.[0]?.fuente ?? ""} · USD — la varianza del `
      + `full year es Forecast contra Budget: el Actual del año todavía no `
      + `existe.`,
    hoja: `Checkbook ${rotulo}`.slice(0, 31),
    columnas, filas,
  };
}
