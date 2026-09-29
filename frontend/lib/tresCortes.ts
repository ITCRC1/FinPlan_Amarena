import type { PLDetail, Scenario } from "@/lib/api";
import type { Cuadro, ColumnaCuadro, FilaCuadro } from "@/lib/exportCuadro";

/**
 * La aritmética de los tres cortes, sin una línea de pantalla.
 *
 * Vive aparte para poder correrla contra datos reales y contrastarla con el
 * PDF del owner. Una tabla financiera que sólo se puede verificar mirándola es
 * una tabla que nadie verifica.
 *
 * ## ⚠️ Los tres cortes son tres formas de sumar el MISMO arreglo de doce
 *
 * `/pl-detail/` devuelve los doce meses de cada fila. El mes es un índice, el
 * YTD son los primeros N, y el full year son los doce. No son tres consultas
 * ni tres plantillas: si lo fueran, podrían decir cosas distintas.
 *
 * ## ⚠️ Ocupación, ADR y RevPAR NO se suman
 *
 * Son razones. Se rederivan en cada corte con su numerador y su denominador —
 * por eso el endpoint manda los cuatro crudos por mes en vez del indicador ya
 * calculado. Sumar los ADR de siete meses da un número que no significa nada y
 * se ve perfectamente normal: en Amarena, $2.026 contra los $286 reales.
 */

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export const usd = (n: number | null) =>
  n === null ? "" : Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
        { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");
export const numero = (n: number | null) =>
  n === null ? "" : n ? n.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—";
export const pct = (n: number | null) =>
  n === null ? "" : n ? (n * 100).toFixed(2) + "%" : "—";

/** Un corte = qué meses entran. Los tres salen del mismo arreglo de doce. */
export interface Corte { clave: "mes" | "ytd" | "full"; titulo: string; meses: number[] }

/** Las filas del encabezado: se rederivan por corte, nunca se suman. */
export const KPIS: { rotulo: string; fmt: (n: number | null) => string;
              calc: (k: Crudos) => number | null; fuerte?: boolean }[] = [
  { rotulo: "Total available Rooms", fmt: numero, calc: k => k.disp },
  { rotulo: "Total Rooms Occupied", fmt: numero, calc: k => k.occ },
  { rotulo: "Total Guests", fmt: numero, calc: k => k.pax },
  { rotulo: "% Occupancy", fmt: pct, fuerte: true,
    calc: k => (k.disp ? k.occ / k.disp : null) },
  { rotulo: "Average Daily Room Only", fmt: usd, fuerte: true,
    calc: k => (k.occ ? k.ing / k.occ : null) },
  // ⚠️ RevPAR es **ingreso TOTAL** sobre habitaciones disponibles, no ingreso
  // de habitaciones. Owner (ver `pl_api._revpar`): *«revpar es total revenue
  // per available room»*. Mide cuánto rinde cada habitación disponible con
  // TODO lo que el hotel factura —spa, tours, A&B—, no sólo la noche. Es lo
  // que la literatura llama TRevPAR.
  //
  // Medido contra el PDF del owner (julio 2026): 248.437,33 / 930 = 267,14
  // exacto. Con el ingreso de habitaciones daba 112,52 — un número que se ve
  // perfectamente razonable y mide otra cosa.
  //
  // `null` si no se pudo leer el ingreso total: mejor vacío que el indicador
  // equivocado.
  { rotulo: "Total RevPAR", fmt: usd, fuerte: true,
    calc: k => (k.ingTotal === null || !k.disp ? null : k.ingTotal / k.disp) },
];

export interface Crudos {
  disp: number; occ: number; pax: number;
  /** Ingreso de HABITACIONES: el numerador del ADR. */
  ing: number;
  /** Ingreso TOTAL del corte: el numerador del RevPAR. `null` = no se pudo
   *  leer la fila «TOTAL REVENUES» del cuadro. */
  ingTotal: number | null;
}

export const suma = (a: number[] | undefined, meses: number[]) =>
  meses.reduce((t, i) => t + (a?.[i] ?? 0), 0);


/** Los tres cortes de un mes de cierre. El mes es un índice; el YTD son los
 *  primeros N; el full year son los doce. */
export function cortesDe(mes: number): Corte[] {
  return [
    { clave: "mes", titulo: MESES[mes - 1], meses: [mes - 1] },
    { clave: "ytd", titulo: `YTD ${MES3[mes - 1]}`,
      meses: Array.from({ length: mes }, (_, i) => i) },
    { clave: "full", titulo: "Full Year",
      meses: Array.from({ length: 12 }, (_, i) => i) },
  ];
}

/** Los cuatro numeradores y denominadores de un corte. ⚠️ Acá se SUMAN, que
 *  es lo correcto: son cantidades. Lo que no se suma es el indicador que sale
 *  de dividirlas — eso lo hace `KPIS`. */
export function crudosDe(
  k: { rooms_available: number[]; rooms_occupied: number[];
       guests: number[]; rooms_revenue: number[] } | undefined,
  meses: number[],
  /** Los doce meses de la fila «TOTAL REVENUES» de ESA versión. Sale del
   *  propio cuadro y no de otra consulta: así el RevPAR y el renglón de
   *  ingreso que está unas filas más abajo no pueden decir cosas distintas. */
  ingresoTotal?: number[] | null,
): Crudos {
  return {
    disp: suma(k?.rooms_available, meses), occ: suma(k?.rooms_occupied, meses),
    pax: suma(k?.guests, meses), ing: suma(k?.rooms_revenue, meses),
    ingTotal: ingresoTotal ? suma(ingresoTotal, meses) : null,
  };
}

/** El rótulo de la fila del ingreso total en la plantilla del owner.
 *
 *  ⚠️ Se compara normalizado y no por igualdad: la plantilla del backend lleva
 *  los rótulos del owner tal cual, erratas incluidas («Total Operationg
 *  expenses»), y este es el único que el encabezado necesita leer. Si no
 *  aparece, el RevPAR sale vacío en vez de salir mal. */
export const ROTULO_INGRESO_TOTAL = "total revenues";
export const esIngresoTotal = (rotulo: string) =>
  rotulo.trim().toLowerCase() === ROTULO_INGRESO_TOTAL;


/* ══════════════════ El cuadro: pantalla, Excel y Word ════════════════════ */

/** Qué par se resta en cada corte.
 *
 *  ⚠️ En el full year NO se usa el Actual: son los meses cargados y nada más,
 *  así que restarle doce meses de Budget da una diferencia que parece un
 *  derrumbe y sólo dice que el año no terminó. Se usa el Forecast, que es lo
 *  que el corte pregunta: cómo va a aterrizar. El PDF del owner hace lo mismo.
 *
 *  El tipo sale de `escenarios` y no del rótulo: el rótulo es texto libre. */
export function parDe(
  c: Corte, versiones: { scenario_id: string }[], escenarios: Scenario[],
): [number, number] | null {
  const tipoDe = (sid: string) => escenarios.find(s => s.id === sid)?.type ?? "";
  const iDe = (t: string) => versiones.findIndex(v => tipoDe(v.scenario_id) === t);
  const budget = iDe("BUDGET");
  if (budget < 0) return null;
  const contra = c.clave === "full" ? iDe("FORECAST") : iDe("ACTUAL");
  if (contra < 0 || contra === budget) return null;
  return [contra, budget];
}

/** El valor de una fila para una versión y un corte. */
export const valorDe = (
  f: { series: (number[] | null)[] }, vi: number, meses: number[],
) => (f.series?.[vi] ? suma(f.series[vi]!, meses) : null);

const resta = (vs: (number | null)[], par: [number, number] | null) =>
  par && vs[par[0]] !== null && vs[par[1]] !== null ? vs[par[0]]! - vs[par[1]]! : null;

/** Las celdas de una fila: cada corte, cada versión, y la varianza. */
export function celdasDe(
  cortes: Corte[], versiones: { scenario_id: string }[], escenarios: Scenario[],
  de: (vi: number, meses: number[]) => number | null,
): (number | null)[] {
  return cortes.flatMap(c => {
    const par = parDe(c, versiones, escenarios);
    const vs = versiones.map((_, i) => de(i, c.meses));
    return [...vs, ...(par ? [resta(vs, par)] : [])];
  });
}

/**
 * El cuadro completo, para el Excel de la pantalla Y para el capítulo del Word.
 *
 * ⚠️ UNA definición. El Word arma el mismo archivo que el botón: dos copias se
 * separan en el primer arreglo y nadie sabría cuál de los dos manda.
 */
export function cuadroTresCortes(
  datos: PLDetail, mes: number, escenarios: Scenario[], ambito: string,
  compacto = true,
): Cuadro {
  const cortes = cortesDe(mes);
  const versiones = datos.versiones ?? [];
  const etiqueta = (sid: string) => {
    const s = escenarios.find(x => x.id === sid);
    return s ? `${s.type} ${s.version}` : sid.slice(0, 8);
  };
  const doce = Array.from({ length: 12 }, (_, i) => i);
  const filas = (datos.filas ?? []).filter(f =>
    !compacto || f.tipo !== "det" || (f.series ?? []).some(x => x && suma(x, doce) !== 0));
  const totRev = (() => {
    const f = (datos.filas ?? []).find(x => esIngresoTotal(x.rotulo));
    return versiones.map((_, i) => f?.series?.[i] ?? null);
  })();

  const columnas: ColumnaCuadro[] = [
    { label: "ACCOUNT DESCRIPTION", ancho: 42, formato: "texto" },
    ...cortes.flatMap(c => [
      ...versiones.map(v => ({ label: `${c.titulo} · ${etiqueta(v.scenario_id)}`,
                               ancho: 16, formato: "usd2" as const })),
      ...(parDe(c, versiones, escenarios)
        ? [{ label: `${c.titulo} · Variance`, ancho: 16, formato: "usd2" as const }]
        : []),
    ]),
  ];

  const kpi: FilaCuadro[] = KPIS.map(k => ({
    label: k.rotulo, es_total: !!k.fuerte,
    formato: k.fmt === pct ? "pct" : k.fmt === numero ? "num" : "usd2",
    valores: celdasDe(cortes, versiones, escenarios,
      (vi, meses) => k.calc(crudosDe(versiones[vi]?.kpis, meses, totRev[vi]))),
  }));

  const cuerpo: FilaCuadro[] = filas.filter(f => f.tipo !== "esp").map(f => ({
    label: f.rotulo,
    es_total: f.tipo === "tot" || f.tipo === "sub" || f.tipo === "sec",
    formato: "usd2",
    // ⚠️ Los encabezados de sección van SIN números, no en cero: un cero ahí
    // se leería como «esta sección no tuvo movimiento».
    valores: f.tipo === "sec"
      ? celdasDe(cortes, versiones, escenarios, () => null)
      : celdasDe(cortes, versiones, escenarios, (vi, meses) => valorDe(f, vi, meses)),
  }));

  return {
    titulo: `Full P&L ${MESES[mes - 1]} ${datos.year} · mes, YTD y full year`,
    subtitulo: `${datos.escenario} · ${ambito} — la varianza del full year es `
      + `Forecast contra Budget: el Actual del año todavía no existe.`,
    hoja: `Full P&L ${MES3[mes - 1]}`,
    columnas, filas: [...kpi, { label: "", valores: [] }, ...cuerpo],
  };
}
