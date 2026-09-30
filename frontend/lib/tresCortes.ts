import { getEstadisticasCierre, type EstadisticasCierre, type PLDetail,
         type Scenario } from "@/lib/api";
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
 * ## ⚠️ El encabezado estadístico NO se calcula acá
 *
 * Sale de `/pl/{id}/estadisticas/?desde=&hasta=`, una llamada por corte y por
 * versión — el mismo endpoint del que lo saca el resto del cierre. Rederivarlo
 * en el cliente sería una segunda verdad, y hay cuatro reglas finas que no se
 * adivinan mirando los números:
 *
 * * **Nada de esto se suma.** Son razones: sumar los ADR de siete meses da algo
 *   que no significa nada y se ve perfectamente normal —en Amarena, $2.026
 *   contra los $286 reales—. El ADR del período se pondera por noches
 *   ocupadas, no es el promedio simple de los meses.
 * * **El ADR es el de las estadísticas**, no ingreso sobre noches. Los dos
 *   existen y no dan lo mismo: `REV_ROOMS` arrastra ingresos que no son noches
 *   vendidas e infla la tarifa en silencio.
 * * **RevPAR es ingreso TOTAL sobre disponibles**, no ingreso de habitaciones.
 *   Owner, 2026-09-08 (ver `pl_api._revpar`): *«revpar es total revenue
 *   per available room»*. Mide cuánto rinde cada habitación disponible con
 *   TODO lo que el hotel factura —spa, tours, A&B—, no sólo la noche; es lo
 *   que la literatura llama TRevPAR. Contra el PDF del owner, julio 2026:
 *   248.437,33 / 930 = 267,14 exacto. Con el ingreso de habitaciones daba
 *   112,52 — un número que se ve perfectamente razonable y mide otra cosa.
 * * **Los socios de un período son el PROMEDIO de los meses CON socios.**
 *   Owner, 2026-09-02: *«cuando presentes un YTD socios pagando, quiero que me
 *   des un promedio de los meses y no que sume»*. Amarena abrió el Club en
 *   marzo: contar enero y febrero en cero bajaría el promedio de 103 a 74, y
 *   sumar daría 516 socios donde hay 72. La cuota es total sobre total:
 *   ingreso del Club ÷ socios-mes, ponderada.
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

/** Las filas del encabezado estadístico.
 *
 *  ⚠️ `calc` sólo LEE el corte que ya vino calculado del backend. Si alguna vez
 *  aparece acá una división, es que se está fabricando un segundo indicador. */
export const KPIS: {
  rotulo: string;
  fmt: (n: number | null) => string;
  calc: (e: EstadisticasCierre | null) => number | null;
  fuerte?: boolean;
  /** En un corte de varios meses el número es un promedio mensual, no un
   *  acumulado. La pantalla lo dice al pasar el mouse; el archivo, al pie. */
  promEnRango?: boolean;
}[] = [
  { rotulo: "Total available Rooms", fmt: numero, calc: e => e?.rooms_available ?? null },
  { rotulo: "Total Rooms Occupied", fmt: numero, calc: e => e?.rooms_occupied ?? null },
  { rotulo: "Total Guests", fmt: numero, calc: e => e?.guests ?? null },
  { rotulo: "% Occupancy", fmt: pct, fuerte: true, calc: e => e?.occupancy_pct ?? null },
  { rotulo: "Average Daily Room Only", fmt: usd, fuerte: true, calc: e => e?.adr ?? null },
  { rotulo: "Total RevPAR", fmt: usd, fuerte: true, calc: e => e?.revpar ?? null },
  // ── El Club ────────────────────────────────────────────────────────────────
  // ⚠️ `null` —no cero— cuando la propiedad no tiene Club: un cero se lee como
  // «no hay socios» donde en realidad no hay Club. Por eso `?? null` y no `?? 0`.
  { rotulo: "Socios pagando (Club)", fmt: numero, promEnRango: true,
    calc: e => e?.club_pagando ?? null },
  // Otra pregunta: «cuántos socios hay hoy». En un mes suelto coincide con el
  // promedio, así que la diferencia sólo se ve en YTD y en el full year.
  { rotulo: "Socios al cierre del mes", fmt: numero,
    calc: e => e?.club_pagando_cierre ?? null },
  { rotulo: "Cuota promedio por socio", fmt: usd, fuerte: true, promEnRango: true,
    calc: e => e?.club_cuota_promedio ?? null },
];

/** El ancho de las columnas, compartido por la franja de estadísticas y por el
 *  cuadro que va debajo.
 *
 *  Owner, 2026-09-30: *«necesito que esto quede súper alineado»*.
 *
 *  ⚠️ **Dos tablas HTML distintas no se alinean solas.** Cada una reparte el
 *  ancho entre sus columnas según su propio contenido, así que con los mismos
 *  datos quedan corridas —y es peor que si estuvieran lejos: se leen como una
 *  sola y cada número cae bajo el encabezado del vecino.
 *
 *  Se alinean cuando las tres cosas coinciden: el MISMO número de columnas
 *  —por eso la franja también lleva su varianza—, el MISMO ancho, y
 *  `table-layout: fixed`, que es lo que hace que el navegador obedezca el ancho
 *  en vez de estirar la columna del texto más largo. */
export const ANCHO_ROTULO = 250;
export const ANCHO_DATO = 116;

/** Los tres renglones que sólo existen si la propiedad tiene Club.
 *
 *  ⚠️ Una definición: la pantalla y el archivo tienen que esconder los MISMOS
 *  renglones, o el Excel llevaría tres filas en blanco que la pantalla no
 *  muestra y que se leen como un dato que falta. */
export const esDelClub = (rotulo: string) =>
  rotulo.startsWith("Socios") || rotulo.startsWith("Cuota");

/** El rango de meses de un corte, tal como lo pide el endpoint (1-12).
 *
 *  ⚠️ Sale del propio corte y no de una tabla aparte: el encabezado y el cuerpo
 *  del cuadro tienen que estar mirando exactamente los mismos meses. */
export const rangoDe = (c: Corte): [number, number] =>
  [c.meses[0] + 1, c.meses[c.meses.length - 1] + 1];

/** El encabezado de cada corte × cada versión. Una llamada por celda.
 *
 *  Una versión que falle queda en `null` y sus celdas salen vacías — mejor un
 *  hueco que un cero que se lee como «no hubo». */
export async function estadisticasDeLosCortes(
  cortes: Corte[], versiones: { scenario_id: string }[],
): Promise<(EstadisticasCierre | null)[][]> {
  return Promise.all(cortes.map(c => {
    const [desde, hasta] = rangoDe(c);
    return Promise.all(versiones.map(v =>
      getEstadisticasCierre(v.scenario_id, desde, hasta).catch(() => null)));
  }));
}

/** Lo que va al pie del cuadro y del Word: las dos reglas que un número del
 *  encabezado no puede contar por sí solo. */
export const PIE_ESTADISTICO =
  "El encabezado es de la propiedad completa y no se acumula: en un corte de "
  + "varios meses la ocupación, el ADR y el RevPAR se rederivan sobre los "
  + "totales del período, los socios son el promedio mensual de los meses con "
  + "socios, y la cuota es el ingreso del Club dividido entre los socios-mes.";

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

/** Las celdas de una fila: cada corte, cada versión, y la varianza.
 *
 *  `de` recibe también el índice del corte, que es lo que necesitan las filas
 *  del encabezado: su valor no se saca de los meses, sino del corte ya
 *  calculado por el backend para ese rango. */
export function celdasDe(
  cortes: Corte[], versiones: { scenario_id: string }[], escenarios: Scenario[],
  de: (vi: number, meses: number[], ci: number) => number | null,
): (number | null)[] {
  return cortes.flatMap((c, ci) => {
    const par = parDe(c, versiones, escenarios);
    const vs = versiones.map((_, i) => de(i, c.meses, ci));
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
  /** El encabezado por corte × versión, de `estadisticasDeLosCortes`. Sin él
   *  las filas del encabezado salen VACÍAS, no en cero: el archivo diría que
   *  el hotel no vendió nada. */
  stats?: (EstadisticasCierre | null)[][],
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

  const kpi: FilaCuadro[] = KPIS.map((k): FilaCuadro => ({
    label: k.rotulo, es_total: !!k.fuerte,
    formato: k.fmt === pct ? "pct" : k.fmt === numero ? "num" : "usd2",
    valores: celdasDe(cortes, versiones, escenarios,
      (vi, _m, ci) => k.calc(stats?.[ci]?.[vi] ?? null)),
  })).filter((f, i) => !esDelClub(KPIS[i].rotulo)
                       || f.valores.some(v => v !== null));

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
      + `Forecast contra Budget: el Actual del año todavía no existe. `
      + PIE_ESTADISTICO,
    hoja: `Full P&L ${MES3[mes - 1]}`,
    columnas, filas: [...kpi, { label: "", valores: [] }, ...cuerpo],
  };
}
