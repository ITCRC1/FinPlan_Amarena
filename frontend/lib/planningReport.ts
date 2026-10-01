import type { PLDetail, PLDetailFila, Scenario } from "@/lib/api";
import type { Cuadro, ColumnaCuadro, FilaCuadro } from "@/lib/exportCuadro";
import { componentesDelPL, resultadosDelPL, rotuloAmbito, suma } from "@/lib/tresCortes";

/**
 * El reporte de PLANNING: los doce meses de una versión y el año de todas.
 *
 * Owner, 2026-10-01, mirando el cierre y pidiéndolo para el Budget 2027:
 * *«quiero 12 meses, y full year para comparar con otras versiones»* · *«quizás
 * acá no necesitamos revisar mes, YTD o Full Year»*.
 *
 * ## Por qué esta forma y no la del cierre
 *
 * El cierre contesta «cómo vamos»: por eso parte el año en mes, acumulado y año,
 * y repite las versiones en cada corte. Planning contesta otra cosa —«cómo queda
 * el año»— y ahí el acumulado a octubre no significa nada: lo que se mira es la
 * estacionalidad mes a mes y el total contra la versión anterior.
 *
 * ```
 *  rótulo │ Ene  Feb  …  Dic │ FY versión A │ FY versión B │ Variación
 *         └── sólo la A ─────┘└──────── todas las versiones ─────────┘
 * ```
 *
 * Quince columnas con dos versiones, contra las treinta y nueve que saldrían de
 * abrir cada mes por versión. El owner eligió esta: *«igual de legible que la
 * pantalla de hoy»*.
 *
 * ## ⚠️ Una definición para la pantalla y para el Excel
 *
 * Devuelve un `Cuadro`, que es lo que come `bajarCuadros`. La pantalla dibuja
 * **ese mismo objeto**: no hay una tabla en JSX y otra en el exportador, así que
 * no pueden decir cosas distintas. Es la misma regla que ya siguen el P&L de
 * tres cortes y los checkbooks.
 *
 * ## ⚠️ La columna del año es una FÓRMULA
 *
 * `suma_cols` sobre los doce meses: en el Excel baja como `=SUM(B5:M5)` y se
 * mueve si alguien corrige un mes. Las otras columnas de año —las de las
 * versiones comparadas— se quedan como número, porque sus doce meses no están
 * en la hoja y una fórmula no tendría a qué apuntar.
 */

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                   "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

/** El rótulo corto de una versión: «BUDGET Working 2027». */
export function rotuloDeVersion(
  escenarios: Scenario[], id: string, caida = "",
): string {
  const e = escenarios.find(x => x.id === id);
  return e ? `${e.type} ${e.version} ${e.year}` : (caida || id.slice(0, 8));
}

/** Los doce meses de una fila para la versión `vi`, o `null` si no la trae. */
const mesesDe = (f: PLDetailFila, vi: number) => f.series?.[vi] ?? null;

/** El año de una fila para la versión `vi`. */
const anioDe = (f: PLDetailFila, vi: number) => {
  const s = mesesDe(f, vi);
  return s ? suma(s, DOCE) : null;
};

const DOCE = Array.from({ length: 12 }, (_, i) => i);

export interface OpcionesPlanning {
  /** El ámbito, para el título y el nombre de la hoja. */
  ambito: string;
  /** Qué dos versiones se restan, por su índice en `datos.versiones`.
   *  Sin esto, la principal contra la primera comparada. */
  par?: [number, number];
  /** Esconde las filas de detalle que están en cero en TODAS las versiones.
   *  Un presupuesto en construcción tiene muchas. */
  compacto?: boolean;
}

/**
 * El cuadro completo. `datos` viene de `/reports/pl-detail/{ambito}/`, que ya
 * manda los doce meses de cada fila por versión — los cortes se arman acá y no
 * se le piden al servidor.
 */
export function cuadroPlanning(
  datos: PLDetail, escenarios: Scenario[], opciones: OpcionesPlanning,
): Cuadro {
  const { ambito, compacto = false } = opciones;
  const versiones = datos.versiones ?? [];
  const nombre = (vi: number) =>
    rotuloDeVersion(escenarios, versiones[vi]?.scenario_id ?? "",
                    versiones[vi]?.escenario);

  // ⚠️ El arreglo EMITIDO, aparte: los ordinales de `suma_de` se cuentan sobre
  // él. El modo compacto saca filas, así que un índice contado sobre `datos`
  // apunta a otra en cuanto cambian los datos — y el exportador descarta la
  // fórmula que no cuadra sin decir nada.
  const emitidas = (datos.filas ?? []).filter(f =>
    f.tipo !== "esp"
    && (!compacto || f.tipo !== "det"
        || (f.series ?? []).some(s => s && suma(s, DOCE) !== 0)));

  /** Dónde empieza el bloque de años, base 0 sobre `columnas`. */
  const BASE_ANIO = 13;
  const par = opciones.par
    ?? (versiones.length > 1 ? [0, 1] as [number, number] : undefined);

  const columnas: ColumnaCuadro[] = [
    { label: "Line Item", ancho: 34, formato: "texto" },
    ...MESES.map((m, i) => ({
      label: m, sub: MES_LARGO[i], ancho: 13, formato: "usd2" as const,
      ...(i === 0 ? { abre_grupo: true } : {}),
    })),
    // ⚠️ El año de la versión principal ES la suma de sus doce meses, y baja
    // como `=SUM(B5:M5)`: es la celda que alguien va a querer ver moverse
    // cuando corrija un mes en la reunión.
    { label: "Full Year", sub: nombre(0), ancho: 16, formato: "usd2",
      abre_grupo: true, suma_cols: DOCE.map((_m, i) => 1 + i) },
    // Las demás versiones traen su año y nada más: sus doce meses no están en
    // la hoja, así que una fórmula no tendría a qué apuntar.
    ...versiones.slice(1).map((_v, i) => ({
      label: "Full Year", sub: nombre(i + 1), ancho: 16, formato: "usd2" as const,
    })),
    ...(par
      ? [{ label: "Variación", sub: `${nombre(par[0])} − ${nombre(par[1])}`,
           ancho: 16, formato: "usd2" as const,
           resta: [BASE_ANIO + par[0], BASE_ANIO + par[1]] as [number, number] }]
      : []),
  ];

  const filas: FilaCuadro[] = emitidas.map(f => {
    // ⚠️ Los encabezados de sección van SIN números, no en cero: un cero ahí se
    // leería como «esta sección no tuvo movimiento».
    if (f.tipo === "sec") {
      return {
        label: f.rotulo, es_seccion: true, formato: "usd2" as const,
        valores: columnas.slice(1).map(() => null),
      };
    }
    const meses = mesesDe(f, 0);
    const anios = versiones.map((_v, vi) => anioDe(f, vi));
    const d = par && anios[par[0]] !== null && anios[par[1]] !== null
      ? anios[par[0]]! - anios[par[1]]! : null;
    return {
      label: f.rotulo,
      es_total: f.tipo === "tot" || f.tipo === "sub",
      formato: "usd2" as const,
      valores: [
        ...DOCE.map(i => (meses ? meses[i] ?? 0 : null)),
        ...anios,
        ...(par ? [d] : []),
      ],
    };
  });

  // ⚠️ Los subtotales suman el detalle que tienen arriba y los cinco resultados
  // de la cascada lo RESTAN. Es la MISMA tabla que usa el P&L del cierre
  // (`componentesDelPL` / `resultadosDelPL`): dos copias se separan en el primer
  // renglón que alguien agregue de un lado.
  componentesDelPL(emitidas).forEach((comp, i) => {
    if (comp) filas[i].suma_de = comp;
  });
  resultadosDelPL(emitidas).forEach((comb, i) => {
    if (comb) filas[i].combina_filas = comb;
  });

  return {
    titulo: `Planning Report ${datos.year} · ${rotuloAmbito(ambito)}`
            + ` · doce meses y año`,
    subtitulo: `${nombre(0)} — los doce meses son de esta versión; el año, de `
      + `todas. La columna Full Year es la suma de sus meses.`,
    hoja: `Planning ${datos.year} ${rotuloAmbito(ambito)}`.slice(0, 31),
    columnas,
    filas,
  };
}
