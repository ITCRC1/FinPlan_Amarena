import type {
  DetalleCelda, EstadisticasCierre, GastoEscenario,
  PLDetail, PLDetailFila, Scenario,
} from "@/lib/api";
import type { Cuadro, ColumnaCuadro, FilaCuadro, FormatoCol } from "@/lib/exportCuadro";
import {
  componentesDelPL, OPERANDOS_DE_LA_CASCADA, resultadosDelPL, rotuloAmbito, suma,
} from "@/lib/tresCortes";

/**
 * El reporte de PLANNING: los doce meses de una versión y el año de todas.
 *
 * Owner, 2026-10-01, mirando el cierre y pidiéndolo para el Budget 2027:
 * *«quiero 12 meses, y full year para comparar con otras versiones»* · *«quizás
 * acá no necesitamos revisar mes, YTD o Full Year»* · *«ajustado todos los
 * reportes para que se pueda generar reportes para comparar todos. desde los
 * reportes, hasta los checkbooks»*.
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
 * ## ⚠️ Los CUATRO cuadros tienen las MISMAS columnas
 *
 * El P&L, las cinco aperturas, los cinco checkbooks y las estadísticas salen
 * todos de `armarCuadro`, con la misma `columnasPlanning`. No es economía de
 * líneas: es que la columna «Full Year» de la apertura de opex tiene que ser la
 * misma celda —mismo índice, misma fórmula, misma versión— que la del P&L. Con
 * dos constructores, el día que alguien agregue una versión comparada una de las
 * dos hojas apunta a la columna de al lado y resta las versiones cambiadas sin
 * que nada falle.
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

const DOCE = Array.from({ length: 12 }, (_, i) => i);

/** Dónde empieza el bloque de años, base 0 sobre `columnas`: el rótulo más los
 *  doce meses. */
const BASE_ANIO = 13;

/** Debajo de esto una celda es cero, y una fila entera de ceros se esconde. */
const CENTAVO = 0.005;

/** El rótulo corto de una versión: «BUDGET Working 2027». */
export function rotuloDeVersion(
  escenarios: Scenario[], id: string, caida = "",
): string {
  const e = escenarios.find(x => x.id === id);
  return e ? `${e.type} ${e.version} ${e.year}` : (caida || id.slice(0, 8));
}

/** Las versiones que trae cualquiera de los cuatro endpoints: lo único que se
 *  les pide es saber cómo se llaman. */
export interface VersionPlanning { scenario_id?: string; escenario?: string }

/** Cómo se llama cada versión, por su índice. */
export function nombradorDeVersiones(
  versiones: VersionPlanning[], escenarios: Scenario[],
): (vi: number) => string {
  return vi => rotuloDeVersion(
    escenarios, versiones[vi]?.scenario_id ?? "", versiones[vi]?.escenario);
}

/** Qué dos versiones se restan. Sin pedido, la principal contra la primera
 *  comparada; con una sola versión, ninguna. */
export function parPorDefecto(
  cuantas: number, pedido?: [number, number],
): [number, number] | undefined {
  if (pedido) return pedido;
  return cuantas > 1 ? [0, 1] : undefined;
}

/**
 * ⚠️ **Las columnas, una sola vez para los cuatro cuadros.**
 *
 * Doce meses de la versión principal, un año por versión y la variación. La
 * columna de año de la principal baja como `=SUM(B5:M5)`; la de las comparadas,
 * no, porque sus meses no están en la hoja.
 */
export function columnasPlanning(
  cuantas: number, nombre: (vi: number) => string,
  par: [number, number] | undefined, anchoRotulo = 34,
): ColumnaCuadro[] {
  const otras = Array.from({ length: Math.max(0, cuantas - 1) }, (_, i) => i + 1);
  return [
    { label: "Line Item", ancho: anchoRotulo, formato: "texto" },
    ...MESES.map((m, i) => ({
      label: m, sub: MES_LARGO[i], ancho: 13, formato: "usd2" as const,
      ...(i === 0 ? { abre_grupo: true } : {}),
    })),
    // ⚠️ El año de la versión principal ES la suma de sus doce meses, y baja
    // como `=SUM(B5:M5)`: es la celda que alguien va a querer ver moverse
    // cuando corrija un mes en la reunión.
    { label: "Full Year", sub: nombre(0), ancho: 16, formato: "usd2",
      abre_grupo: true, suma_cols: DOCE.map((_m, i) => 1 + i) },
    // ⚠️ Las demás versiones traen su año y NADA MÁS —sin `suma_cols`—: sus
    // doce meses no están en la hoja, así que la fórmula no tendría a qué
    // apuntar y el exportador la tiraría igual, en silencio.
    ...otras.map(vi => ({
      label: "Full Year", sub: nombre(vi), ancho: 16, formato: "usd2" as const,
    })),
    ...(par
      ? [{ label: "Variación", sub: `${nombre(par[0])} − ${nombre(par[1])}`,
           ancho: 16, formato: "usd2" as const,
           resta: [BASE_ANIO + par[0], BASE_ANIO + par[1]] as [number, number] }]
      : []),
  ];
}

/** Una fila antes de volverse celdas: los doce meses de la principal y el año de
 *  cada versión. La variación la calcula `armarCuadro`, para que no haya dos
 *  maneras de restar. */
export interface FilaPlanning {
  label: string;
  /** Los doce de la versión principal. `null` = esta fila no lleva números
   *  (encabezado de sección): un cero ahí se leería como «sin movimiento». */
  meses?: (number | null)[] | null;
  /** Uno por versión, en el orden en que vienen. */
  anios?: (number | null)[];
  es_total?: boolean;
  es_seccion?: boolean;
  nivel?: number;
  formato?: FormatoCol;
  suma_de?: number[];
  combina_filas?: [number, number][];
}

export interface OpcionesCuadro {
  titulo: string;
  subtitulo: string;
  hoja: string;
  anchoRotulo?: number;
}

/**
 * El `Cuadro` terminado. Los cuatro reportes de esta pantalla pasan por acá.
 *
 * ⚠️ La variación se calcula **de una sola manera**: `anios[a] − anios[b]`, con
 * el mismo par que le dio su `resta` a la columna. Si la pantalla restara por su
 * cuenta, el número y la fórmula del Excel podrían decir cosas distintas.
 */
export function armarCuadro(
  opciones: OpcionesCuadro, cuantas: number, nombre: (vi: number) => string,
  par: [number, number] | undefined, filas: FilaPlanning[],
): Cuadro {
  const columnas = columnasPlanning(cuantas, nombre, par, opciones.anchoRotulo);
  return {
    titulo: opciones.titulo,
    subtitulo: opciones.subtitulo,
    hoja: opciones.hoja.slice(0, 31),
    columnas,
    filas: filas.map((f): FilaCuadro => {
      // ⚠️ Una sección va SIN números, no en cero: un cero ahí se leería como
      // «este bloque no tuvo movimiento», que es una afirmación y no un hueco.
      if (f.meses === null) {
        return {
          label: f.label, es_seccion: f.es_seccion ?? true, nivel: f.nivel,
          formato: f.formato ?? "usd2",
          valores: columnas.slice(1).map(() => null),
        };
      }
      const anios = Array.from({ length: cuantas }, (_, vi) => f.anios?.[vi] ?? null);
      const d = par && anios[par[0]] !== null && anios[par[1]] !== null
        ? anios[par[0]]! - anios[par[1]]! : null;
      return {
        label: f.label,
        es_total: f.es_total, es_seccion: f.es_seccion, nivel: f.nivel,
        formato: f.formato ?? "usd2",
        suma_de: f.suma_de, combina_filas: f.combina_filas,
        valores: [
          ...DOCE.map(i => (f.meses ? f.meses[i] ?? 0 : null)),
          ...anios,
          ...(par ? [d] : []),
        ],
      };
    }),
  };
}

/* ═══════════════════════ 1 · El P&L ══════════════════════════════════════ */

/** Los doce meses de una fila para la versión `vi`, o `null` si no la trae. */
const mesesDe = (f: PLDetailFila, vi: number) => f.series?.[vi] ?? null;

/** El año de una fila para la versión `vi`. */
const anioDe = (f: PLDetailFila, vi: number) => {
  const s = mesesDe(f, vi);
  return s ? suma(s, DOCE) : null;
};

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
 * El cuadro del P&L. `datos` viene de `/reports/pl-detail/{ambito}/`, que ya
 * manda los doce meses de cada fila por versión — los cortes se arman acá y no
 * se le piden al servidor.
 */
export function cuadroPlanning(
  datos: PLDetail, escenarios: Scenario[], opciones: OpcionesPlanning,
): Cuadro {
  const { ambito, compacto = false } = opciones;
  const versiones = datos.versiones ?? [];
  const nombre = nombradorDeVersiones(versiones, escenarios);

  // ⚠️ El arreglo EMITIDO, aparte: los ordinales de `suma_de` se cuentan sobre
  // él. El modo compacto saca filas, así que un índice contado sobre `datos`
  // apunta a otra en cuanto cambian los datos — y el exportador descarta la
  // fórmula que no cuadra sin decir nada.
  const emitidas = (datos.filas ?? []).filter(f =>
    f.tipo !== "esp"
    && (!compacto || f.tipo !== "det"
        // ⚠️ El operando de una resta de la cascada NO se esconde por estar en
        // cero: sin la fila, `resultadosDelPL` no lo encuentra y el resultado
        // —NET PROFIT, el primero— baja como número pegado. Medido.
        || OPERANDOS_DE_LA_CASCADA.has(f.rotulo)
        || (f.series ?? []).some(s => s && suma(s, DOCE) !== 0)));

  const par = parPorDefecto(versiones.length, opciones.par);

  const filas: FilaPlanning[] = emitidas.map(f => {
    // ⚠️ Los encabezados de sección van SIN números, no en cero: un cero ahí se
    // leería como «esta sección no tuvo movimiento».
    if (f.tipo === "sec") return { label: f.rotulo, es_seccion: true, meses: null };
    return {
      label: f.rotulo,
      es_total: f.tipo === "tot" || f.tipo === "sub",
      meses: mesesDe(f, 0),
      anios: versiones.map((_v, vi) => anioDe(f, vi)),
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

  return armarCuadro({
    titulo: `Planning Report ${datos.year} · ${rotuloAmbito(ambito)} · doce meses y año`,
    subtitulo: `${nombre(0)} — los doce meses son de esta versión; el año, de `
      + `todas. La columna Full Year es la suma de sus meses.`,
    hoja: `Planning ${datos.year} ${rotuloAmbito(ambito)}`,
  }, versiones.length, nombre, par, filas);
}

/* ═════════════════ 2 · Las cinco aperturas por naturaleza ════════════════ */

/**
 * Las cinco aperturas del gasto y del ingreso, con el eje que usa cada una.
 *
 * ⚠️ El eje no es un detalle de presentación. El ingreso se abre por LÍNEA
 * porque un presupuesto de ingresos no tiene departamento; el gasto de propiedad
 * por CUENTA porque ahí todo cae en un solo departamento y abrirlo por depto
 * daría una fila. Es la misma regla del endpoint, y cambiarla de un lado deja la
 * pantalla leyendo claves que el servidor no indexó así.
 */
export const APERTURAS = [
  { clase: "revenue", rotulo: "Ingreso", eje: "por línea de ingreso" },
  { clase: "payroll", rotulo: "Planilla", eje: "por departamento" },
  { clase: "cost", rotulo: "Costo de ventas", eje: "por departamento" },
  { clase: "opex", rotulo: "Gastos operativos", eje: "por departamento" },
  { clase: "property", rotulo: "Gastos de propiedad", eje: "por cuenta" },
] as const;

export type ClaseApertura = (typeof APERTURAS)[number]["clase"];

/**
 * Una apertura: una fila por departamento (o línea, o cuenta) y el total abajo.
 *
 * `gastos` viene de `/gasto-por-clase/?detalle=true`, que ya manda los doce meses
 * de cada clave por versión.
 *
 * ⚠️ **El TOTAL suma las filas que se ven.** En modo compacto se esconden las
 * claves que están en cero en TODAS las versiones: esconderlas no mueve la suma,
 * así que la fórmula sigue cuadrando. Esconder una fila con número la rompería —
 * y el exportador se comería la fórmula sin avisar.
 */
export function cuadroApertura(
  clase: ClaseApertura, gastos: GastoEscenario[], deptos: Record<string, string>,
  escenarios: Scenario[], opciones: OpcionesPlanning,
): Cuadro {
  const { compacto = false } = opciones;
  const nombre = nombradorDeVersiones(gastos, escenarios);
  const par = parPorDefecto(gastos.length, opciones.par);
  const meta = APERTURAS.find(a => a.clase === clase)!;

  const serie = (vi: number, k: string): number[] =>
    gastos[vi]?.detalle?.[clase]?.[k] ?? [];
  const anio = (vi: number, k: string) => suma(serie(vi, k), DOCE);

  // El nombre de una cuenta 8xxx puede venir en cualquiera de las versiones: la
  // que no tuvo movimiento en esa cuenta no la nombra.
  const nombreCuenta = (k: string) => {
    for (const g of gastos) { const n = g.nombres_cuenta?.[k]; if (n) return n; }
    return "";
  };
  const rotulo = (k: string) => {
    const n = clase === "property" ? nombreCuenta(k) : deptos[k];
    return n ? `${k} · ${n}` : k;
  };

  const claves = Array.from(new Set(
    gastos.flatMap(g => Object.keys(g.detalle?.[clase] ?? {}))))
    .filter(k => !compacto
                 || gastos.some((_g, vi) => Math.abs(anio(vi, k)) >= CENTAVO))
    // De mayor a menor por lo que pesa en la versión principal: lo que mueve la
    // aguja arriba, que es como se lee un presupuesto.
    .sort((a, b) => Math.abs(anio(0, b)) - Math.abs(anio(0, a)) || a.localeCompare(b));

  const filas: FilaPlanning[] = claves.map(k => ({
    label: rotulo(k),
    meses: DOCE.map(i => serie(0, k)[i] ?? 0),
    anios: gastos.map((_g, vi) => anio(vi, k)),
  }));
  filas.push({
    label: `TOTAL ${meta.rotulo.toUpperCase()}`,
    es_total: true,
    suma_de: claves.map((_k, i) => i),
    meses: DOCE.map(i => claves.reduce((t, k) => t + (serie(0, k)[i] ?? 0), 0)),
    anios: gastos.map((_g, vi) => claves.reduce((t, k) => t + anio(vi, k), 0)),
  });

  const anio0 = gastos[0]?.year ?? "";
  return armarCuadro({
    titulo: `Planning ${anio0} · ${meta.rotulo} · ${meta.eje}`,
    subtitulo: `${nombre(0)} — los doce meses son de esta versión; el año, de `
      + `todas. El total es la suma de las filas que se ven.`,
    hoja: `Apertura ${meta.rotulo}`,
    anchoRotulo: 40,
  }, gastos.length, nombre, par, filas);
}

/* ═══════════════ 3 · Los checkbooks, cuenta por cuenta ═══════════════════ */

/**
 * El checkbook de una clase: cada cuenta del mayor, agrupada por departamento.
 *
 * `det` viene de `/gasto-por-clase/detalle-de-celda/` con la clave vacía, que es
 * «toda la clase»: trae cada cuenta con su departamento y sus doce meses por
 * versión. Es el mismo detalle que se abre al hacer clic en una celda del
 * cierre — el owner lo pidió también acá: *«desde los reportes, hasta los
 * checkbooks»*.
 *
 * ⚠️ **Cada fila lleva su departamento.** Sumando por cuenta a secas, la 7065 de
 * Habitaciones y la 7065 del Club caían en la misma fila y el resultado no era
 * de nadie (owner, 2026-09-03). Por eso el agrupador es el par (depto, cuenta).
 */
export function cuadroCheckbook(
  det: DetalleCelda, escenarios: Scenario[], opciones: OpcionesPlanning,
): Cuadro {
  const { compacto = false } = opciones;
  const versiones = det.versiones ?? [];
  const nombre = nombradorDeVersiones(versiones, escenarios);
  const par = parPorDefecto(versiones.length, opciones.par);
  const meta = APERTURAS.find(a => a.clase === det.clase);

  const serie = (f: { series: Record<string, number[]> }, vi: number): number[] =>
    f.series?.[versiones[vi]?.scenario_id ?? ""] ?? [];
  const anio = (f: { series: Record<string, number[]> }, vi: number) =>
    suma(serie(f, vi), DOCE);

  const visibles = (det.filas ?? []).filter(f =>
    !compacto || versiones.some((_v, vi) => Math.abs(anio(f, vi)) >= CENTAVO));

  // Por departamento, y dentro de cada uno por lo que pesa.
  const grupos = new Map<string, typeof visibles>();
  for (const f of visibles) {
    const k = `${f.dept_code}\u0000${f.dept_name}`;
    (grupos.get(k) ?? grupos.set(k, []).get(k)!).push(f);
  }

  const filas: FilaPlanning[] = [];
  /** Dónde quedó el subtotal de cada departamento: el TOTAL los suma a ellos,
   *  no a las cuentas, para no contar dos veces. */
  const subtotales: number[] = [];

  for (const [k, cuentas] of Array.from(grupos.entries())
         .sort((a, b) => a[0].localeCompare(b[0]))) {
    const [code, name] = k.split("\u0000");
    cuentas.sort((a, b) => Math.abs(anio(b, 0)) - Math.abs(anio(a, 0))
                           || a.cuenta.localeCompare(b.cuenta));
    filas.push({ label: `${code} · ${name || "(sin departamento)"}`,
                 es_seccion: true, meses: null });
    const desde = filas.length;
    for (const f of cuentas) {
      filas.push({
        label: `${f.cuenta} · ${f.nombre || ""}`.trim().replace(/ ·\s*$/, ""),
        nivel: 1,
        meses: DOCE.map(i => serie(f, 0)[i] ?? 0),
        anios: versiones.map((_v, vi) => anio(f, vi)),
      });
    }
    subtotales.push(filas.length);
    filas.push({
      label: `Total ${code}`,
      es_total: true,
      suma_de: cuentas.map((_c, i) => desde + i),
      meses: DOCE.map(i => cuentas.reduce((t, f) => t + (serie(f, 0)[i] ?? 0), 0)),
      anios: versiones.map((_v, vi) => cuentas.reduce((t, f) => t + anio(f, vi), 0)),
    });
  }

  filas.push({
    label: `TOTAL ${(meta?.rotulo ?? det.rotulo ?? det.clase).toUpperCase()}`,
    es_total: true,
    // ⚠️ Suma los SUBTOTALES, no las cuentas: sumar las dos cosas contaría cada
    // peso dos veces, y el exportador tiraría la fórmula por no cuadrar.
    suma_de: subtotales,
    meses: DOCE.map(i => visibles.reduce((t, f) => t + (serie(f, 0)[i] ?? 0), 0)),
    anios: versiones.map((_v, vi) => visibles.reduce((t, f) => t + anio(f, vi), 0)),
  });

  const fuente = versiones[0]?.fuente ? ` · ${versiones[0].fuente}` : "";
  return armarCuadro({
    titulo: `Planning · Checkbook ${meta?.rotulo ?? det.clase} · cuenta por cuenta`,
    subtitulo: `${nombre(0)}${fuente} — los doce meses son de esta versión; el `
      + `año, de todas. Cada fila lleva su departamento.`,
    hoja: `Checkbook ${meta?.rotulo ?? det.clase}`,
    anchoRotulo: 46,
  }, versiones.length, nombre, par, filas);
}

/* ════════════════════ 4 · Las estadísticas del año ═══════════════════════ */

/**
 * Qué estadística es cada fila y cómo se mira.
 *
 * ⚠️ **La unidad decide si el año se puede sumar.** Las noches y el ingreso sí;
 * la ocupación, el ADR y el RevPAR NO —son razones, y el promedio de doce
 * promedios no es el promedio del año—. Por eso el año de esas filas se le pide
 * al servidor con el período completo en vez de sumarse acá.
 *
 * No hace falta apagarles la fórmula a mano: el exportador escribe `=SUM(...)`
 * sólo cuando da lo mismo que el número que vino, así que en una fila de razón
 * se queda con el número. El resguardo está en el escritor, no en la confianza.
 */
export const ESTADISTICAS = [
  { campo: "rooms_available", rotulo: "Noches disponibles", formato: "num" },
  { campo: "rooms_occupied", rotulo: "Noches ocupadas", formato: "num" },
  { campo: "guests", rotulo: "Huéspedes", formato: "num" },
  { campo: "occupancy_pct", rotulo: "Ocupación %", formato: "pct", razon: true },
  { campo: "rooms_revenue", rotulo: "Ingreso de habitaciones", formato: "usd2" },
  { campo: "adr", rotulo: "ADR", formato: "usd2", razon: true },
  { campo: "revpar", rotulo: "RevPAR", formato: "usd2", razon: true },
  { campo: "revpar_bruto", rotulo: "RevPAR (ingreso total)", formato: "usd2", razon: true },
  { campo: "club_pagando", rotulo: "Club · socios pagando", formato: "num1", razon: true },
  { campo: "club_revenue", rotulo: "Club · ingreso", formato: "usd2" },
  { campo: "club_cuota_promedio", rotulo: "Club · cuota promedio", formato: "usd2", razon: true },
] as const;

export interface EstadisticasPlanning {
  /** Los doce meses de la versión principal: uno por mes, en orden. */
  meses: (EstadisticasCierre | null)[];
  /** El año completo de cada versión, pedido con el período entero. */
  anios: (EstadisticasCierre | null)[];
  versiones: VersionPlanning[];
}

/**
 * El cuadro de estadísticas. A diferencia de los otros tres, **el año no se suma
 * acá**: se le pide al servidor con `desde=1&hasta=12`, porque la ocupación, el
 * ADR y el promedio de socios del año no son la suma de los doce meses.
 *
 * Owner, 2026-09-02: *«cuando presentes un YTD socios pagando, quiero que me des
 * un promedio de los meses y no que sume»*. Ese promedio lo calcula el servidor
 * sobre los meses CON socios; rehacerlo acá sería una segunda definición.
 */
export function cuadroEstadisticas(
  datos: EstadisticasPlanning, escenarios: Scenario[], opciones: OpcionesPlanning,
): Cuadro {
  const { compacto = false } = opciones;
  const nombre = nombradorDeVersiones(datos.versiones, escenarios);
  const par = parPorDefecto(datos.versiones.length, opciones.par);

  const val = (e: EstadisticasCierre | null, campo: string): number | null => {
    const v = e ? (e as unknown as Record<string, number | null>)[campo] : null;
    return v === null || v === undefined ? null : Number(v);
  };

  const filas: FilaPlanning[] = ESTADISTICAS
    // El Club no existe en todas las propiedades, y una fila de guiones no dice
    // nada: `null` es «esta propiedad no tiene Club», distinto de cero socios.
    .filter(s => !compacto || datos.anios.some(a => val(a, s.campo) !== null))
    .map(s => ({
      label: s.rotulo,
      formato: s.formato as FormatoCol,
      meses: datos.meses.map(m => val(m, s.campo)),
      anios: datos.anios.map(a => val(a, s.campo)),
    }));

  const anio0 = datos.anios[0]?.year ?? datos.meses.find(Boolean)?.year ?? "";
  return armarCuadro({
    titulo: `Planning ${anio0} · Estadísticas · doce meses y año`,
    subtitulo: `${nombre(0)} — los doce meses son de esta versión; el año, de `
      + `todas. ⚠️ La ocupación, el ADR, el RevPAR y los socios del año NO son `
      + `la suma de los meses: se piden con el período completo.`,
    hoja: `Estadísticas`,
    anchoRotulo: 30,
  }, datos.versiones.length, nombre, par, filas);
}
