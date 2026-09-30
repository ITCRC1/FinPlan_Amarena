import type { DetalleCelda, Scenario } from "@/lib/api";
import type { Cuadro, ColumnaCuadro, FilaCuadro } from "@/lib/exportCuadro";
import { celdasDe, cortesDe, parDe, ROTULO_VAR, rotulosDeVersion, suma,
         vistaDe, type Corte, type Vista } from "@/lib/tresCortes";

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
 * ## ⚠️ En el full year, la primera columna NO es el Actual
 *
 * Owner, 2026-09-30: *«en el full year debes quitar la primera columna que dice
 * actual final por el Forecast Current»*.
 *
 * El Actual del año son los meses cargados y nada más, así que en el corte del
 * año completo repetía el YTD **al centavo** —en Salarios de Amarena, 57.464,79
 * en las dos columnas—. Dos columnas idénticas con rótulos distintos no dicen
 * que el año no terminó: se leen como dos cifras que casualmente coinciden.
 *
 * En ese lugar va el **Forecast Current**, que es el que contesta la pregunta
 * del corte: cómo va a cerrar el año. Los otros dos cortes no se tocan — ahí el
 * Actual es el dato.
 *
 * ## Una sola definición para la pantalla y para el Excel
 *
 * Las dos dibujan este `Cuadro`. Dos armados del mismo reporte empiezan iguales
 * y se separan en el primer arreglo que alguien hace de un lado.
 */

/** Los tres cortes de un mes. Reexportado para que la pantalla arme su fila de
 *  encabezado con exactamente los mismos que el cuadro. */
export const cortesDelCheckbook = (mes: number, anio?: number): Corte[] =>
  cortesDe(mes, anio);

/** Cuántas columnas ocupa un corte: una por columna de la vista, más la
 *  varianza si hay par que restar.
 *
 *  ⚠️ Recibe TODAS las versiones y la vista, no sólo las visibles. Con las
 *  visibles nada más, `parDe` no encuentra ningún FORECAST cuando el owner lo
 *  sacó de las ranuras, y el ancho del año completo sale uno menos que el del
 *  cuadro: los encabezados quedan corridos respecto de los números. */
export const anchoDelCorte = (
  c: Corte, versiones: { scenario_id: string }[], escenarios: Scenario[],
  vista?: Vista,
) => (vista?.columnas.length ?? versiones.length)
     + (parDe(c, versiones, escenarios, vista) ? 1 : 0);

export function cuadroCheckbookCortes(
  rotulo: string, datos: DetalleCelda, mes: number, escenarios: Scenario[],
  dept: string, deptos: Record<string, string>,
  opciones: {
    /** Las versiones que SON columnas, en orden. Sin esto salen las que traiga
     *  la respuesta, incluida la que se pide sólo para el full year. */
    visibles?: string[];
    /** Quién ocupa la primera columna en el corte del año completo. Es el
     *  Forecast Current: el Actual ahí repite el YTD. */
    actualDelFullYear?: string;
  } = {},
): Cuadro {
  // ⚠️ `todas` son las versiones que VINIERON —el Forecast Current se pide
  // aunque el owner lo haya sacado de las ranuras— y la vista dice cuáles
  // tienen columna y quién ocupa la primera del año completo. Antes se
  // recortaba a las visibles antes de calcular nada, y entonces `parDe` no
  // encontraba ningún FORECAST: el año completo se quedaba SIN columna de
  // varianza justo en el caso que se quiso habilitar.
  const todas = datos.versiones ?? [];
  const vista = vistaDe(todas, opciones.visibles, opciones.actualDelFullYear,
                        escenarios);
  // ⚠️ El año sale de la VERSIÓN, que es lo único que lo sabe acá: el detalle
  // de celda no lo trae. Owner, 2026-09-30: *«en algún lugar hay que poner el
  // año»*, y va en el rótulo del corte.
  const anio = escenarios.find(e => e.id === todas[0]?.scenario_id)?.year;
  const cortes = cortesDe(mes, anio);
  const doce = Array.from({ length: 12 }, (_, i) => i);
  /** El rótulo corto de cada versión: «Actual», «Budget», «Forecast». */
  const corto = rotulosDeVersion(todas, escenarios);

  /** El id de una versión ya resuelta por la vista. */
  const sidDe = (vi: number) => todas[vi]?.scenario_id ?? "";

  /** Qué versión ocupa la columna `col` en el corte `ci`. */
  const idDe = (col: number, ci: number) => sidDe(vista.vi(col, ci));

  /** ⚠️ `vi` es un índice de VERSIÓN, no una posición de columna: `celdasDe` ya
   *  aplicó la regla del año completo. Aplicarla otra vez la aplicaría dos
   *  veces. */
  const serie = (f: { series: Record<string, number[]> }, vi: number) =>
    f.series[sidDe(vi)] ?? [];

  // ⚠️ La misma limpieza que la vista de doce meses: una cuenta en cero en
  // TODAS las versiones y todo el año no dice nada, y son decenas.
  const vivas = (datos.filas ?? [])
    .filter(f => !dept || f.dept_code === dept)
    .filter(f => todas.some((_v, vi) => Math.abs(suma(serie(f, vi), doce)) >= 0.005));

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

  /** En qué columna está A LA VISTA la versión `vi` del corte `ci`, o `null` si
   *  ninguna la muestra. La variación apunta a las columnas que se ven, no a
   *  los índices de `versiones`: en el año completo la primera columna muestra
   *  el Forecast Current, y una fórmula que reste otras dos columnas diría algo
   *  que el cuadro no dice. */
  const colDe = (vi: number, ci: number, base: number) => {
    const j = vista.columnas.findIndex((_c, col) => vista.vi(col, ci) === vi);
    return j < 0 ? null : base + j;
  };

  const columnas: ColumnaCuadro[] = [
    { label: "Cuenta", ancho: 40, formato: "texto" },
    ...cortes.flatMap((c, ci) => {
      const base = 1 + cortes.slice(0, ci).reduce(
        (a, x) => a + vista.columnas.length
                  + (parDe(x, todas, escenarios, vista) ? 1 : 0), 0);
      const par = parDe(c, todas, escenarios, vista);
      return [
        // ⚠️ DOS líneas y la raya gruesa que abre el bloque: la misma cabecera
        // del P&L (owner, 2026-09-30).
        ...vista.columnas.map((_c, col) => ({
          label: corto(idDe(col, ci)),
          sub: c.titulo,
          ...(col === 0 ? { abre_grupo: true } : {}),
          ancho: 15, formato: "usd2" as const })),
        // ⚠️ La variación baja como FÓRMULA (owner, 2026-09-30). El par lo da
        // `parDe`, que en el año completo devuelve Forecast contra Budget.
        ...(par
          ? [{ label: ROTULO_VAR, ancho: 15, formato: "usd2" as const,
               ...(colDe(par[0], ci, base) !== null && colDe(par[1], ci, base) !== null
                 ? { resta: [colDe(par[0], ci, base)!,
                             colDe(par[1], ci, base)!] as [number, number] }
                 : {}) }]
          : []),
      ];
    }),
  ];

  const celdas = (de: (vi: number, meses: number[], ci: number) => number | null) =>
    celdasDe(cortes, todas, escenarios, de, vista);

  const filas: FilaCuadro[] = [];
  /** Los ordinales de los subtotales, para que el TOTAL sea su suma. */
  const subtotales: number[] = [];
  for (const [code, g] of grupos) {
    filas.push({
      label: g.nombre ? `${code} · ${g.nombre}` : code,
      // La banda del departamento es el rótulo del bloque, no su cierre.
      es_seccion: true, nivel: 0,
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
    // ⚠️ Acá el subtotal SÍ es la suma de lo que se ve —las mismas `g.filas`
    // que se acaban de escribir—, así que baja como `=X7+X8+X9`. En el P&L no
    // lo es: ahí el total lo calcula el motor y el cuadro puede no mostrar
    // todos sus componentes. El exportador igual lo comprueba antes de escribir
    // la fórmula, así que declararlo de más no cambia ningún número.
    const detalle = orden.map((_f, k) => filas.length - orden.length + k);
    subtotales.push(filas.length);
    filas.push({
      label: `Subtotal ${code}`, es_total: true, nivel: 1,
      suma_de: detalle,
      valores: celdas((vi, meses) =>
        g.filas.reduce((a, f) => a + suma(serie(f, vi), meses), 0)),
    });
    filas.push({ label: "", valores: [] });
  }
  filas.push({
    label: "TOTAL", es_total: true, nivel: 0,
    suma_de: subtotales,
    valores: celdas((vi, meses) =>
      vivas.reduce((a, f) => a + suma(serie(f, vi), meses), 0)),
  });

  return {
    titulo: `Checkbook · ${rotulo}${anio ? ` ${anio}` : ""}`
            + ` · mes, YTD y full year`,
    subtitulo: `${datos.versiones?.[0]?.fuente ?? ""} · USD — en el full year `
      + `la primera columna es el Forecast Current y la varianza es Forecast `
      + `contra Budget: el Actual del año todavía no existe, son los meses `
      + `cargados y nada más.`,
    hoja: `Checkbook ${rotulo}`.slice(0, 31),
    columnas, filas,
  };
}
