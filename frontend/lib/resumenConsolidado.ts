import type { AnioMes, AnioRoomStats } from "@/lib/api";
import type { Cuadro, FilaCuadro } from "@/lib/exportCuadro";

/**
 * La aritmética del Resumen Consolidado, sin una línea de pantalla.
 *
 * Vive aparte del componente a propósito: así se puede correr contra los datos
 * reales y contrastar renglón por renglón contra el cuadro que la propiedad
 * arma a mano. Una tabla financiera que sólo se puede verificar mirándola es
 * una tabla que nadie verifica.
 *
 * ## ⚠️ Las dos bases, y cuál manda
 *
 * Owner, 2026-09-29: *«Total habitaciones pagadas, total habitaciones
 * cortesias, total noches ocupadas con cortesias, no se usa para los
 * indicadores»*.
 *
 * Los indicadores —ocupación, ADR, RevPAR— van sobre las noches **pagadas**,
 * igual que el cierre. Antes iban sobre el total con cortesías, porque así los
 * calcula el archivo del PMS, y eso dejaba dos pantallas de la misma app
 * contestando distinto: el cierre decía ADR $317.66 para marzo y este cuadro
 * $125.44 — las dos bien según su base, y nada explicaba la diferencia.
 *
 * Las cifras del archivo **no se pierden**: van en su propio bloque al pie,
 * en gris. Sin ellas el cuadro dejaría de cuadrar contra el papel del PMS y
 * nadie podría explicar por qué.
 *
 * Y las tres noches van explícitas y en este orden —pagadas, cortesías, total—
 * porque la tercera es la suma de las dos primeras: así se ve de dónde sale
 * cada indicador sin restar de cabeza.
 *
 * ## ⚠️ El acumulado de una TASA se recalcula
 *
 * Cada renglón recibe un CONJUNTO de meses: uno para cada columna, todos para
 * el acumulado. Así el ADR del período sale de dividir los totales y no de
 * promediar las columnas — promediarlas haría pesar igual a marzo (51 noches)
 * y a agosto (218).
 */

export type Formato = "usd" | "num" | "pct";

/** Un renglón del cuadro. `valor` devuelve `null` cuando el dato no existe —
 *  que no es lo mismo que cero. */
export interface Renglon {
  clave: string;
  rotulo: string;
  formato: Formato;
  /** Sobre un conjunto de meses: un mes para las columnas, todos para el
   *  acumulado. Así una TASA se recalcula sola en vez de promediarse. */
  valor: (ms: AnioMes[], ctx: Ctx) => number | null;
  banda?: boolean;      // subtotal o separador
  tenue?: boolean;      // contexto, no cifra principal
  espacioAntes?: boolean;
}

export interface Ctx { unidades: number }

export const sum = (ms: AnioMes[], f: (m: AnioMes) => number) =>
  ms.reduce((a, m) => a + f(m), 0);

export const porCat = (m: AnioMes, campo: "revenue" | "ingreso_ayb" | "ingreso_otros"
                | "nights_occupied" | "pax" | "hab_entradas" | "cli_entradas") =>
  m.categorias.reduce((a, c) => a + ((c[campo] as number) ?? 0), 0);

/** Noches de cortesía: los canales que la propiedad dejó fuera de los
 *  indicadores. En Amarena es el CPL. */
export const nochesFuera = (m: AnioMes) =>
  m.canales.reduce((a, c) => a + (c.cuenta_para_kpis ? 0 : c.nights_occupied), 0);

/** Noches PAGADAS: las que entran a los indicadores.
 *
 *  ⚠️ Sin apertura por canal no se puede separar, y no se inventa: se usa el
 *  total. Descontar «lo que suele ser cortesía» sería fabricar un número. Un
 *  mes así se lee con pagadas = total y cortesías = 0, que es exactamente lo
 *  que se sabe de él. */
export const nochesPagadas = (m: AnioMes) =>
  m.canales.length
    ? m.canales.reduce((a, c) => a + (c.cuenta_para_kpis ? c.nights_occupied : 0), 0)
    : porCat(m, "nights_occupied");

/** Ingreso de las noches pagadas. Mismo criterio y mismo respaldo. */
export const ingresoPagado = (m: AnioMes) =>
  m.canales.length
    ? m.canales.reduce((a, c) => a + (c.cuenta_para_kpis ? c.revenue : 0), 0)
    : porCat(m, "revenue");

/** Las disponibles del período. `null` si algún mes no las trajo: sumar sólo
 *  los que sí daría un denominador que no corresponde al numerador. */
export const disponibles = (ms: AnioMes[]): number | null => {
  if (!ms.length || ms.some(m => !m.resumen)) return null;
  return sum(ms, m => m.resumen!.habitaciones_disponibles);
};

export const RENGLONES: Renglon[] = [
  { clave: "hosp", rotulo: "Ingreso Hospedaje", formato: "usd",
    valor: ms => sum(ms, m => porCat(m, "revenue")) },
  { clave: "ayb", rotulo: "Ingreso A y B", formato: "usd",
    valor: ms => sum(ms, m => porCat(m, "ingreso_ayb")) },
  { clave: "otros", rotulo: "Ingreso Otros", formato: "usd",
    valor: ms => sum(ms, m => porCat(m, "ingreso_otros")) },
  { clave: "totIng", rotulo: "Total Ingresos", formato: "usd", banda: true,
    valor: ms => sum(ms, m => porCat(m, "revenue") + porCat(m, "ingreso_ayb")
                            + porCat(m, "ingreso_otros")) },

  { clave: "habEnt", rotulo: "Habitaciones — Entradas", formato: "num",
    espacioAntes: true, valor: ms => sum(ms, m => porCat(m, "hab_entradas")) },
  // ⚠️ Owner, 2026-09-29: *«Total habitaciones pagadas, total habitaciones
  // cortesias, total noches ocupadas con cortesias, no se usa para los
  // indicadores»*.
  //
  // Los tres juntos y en este orden porque el tercero es la SUMA de los dos
  // primeros: así se ve de dónde sale cada indicador sin tener que restar de
  // cabeza. El renglón de arriba es el que manda — lo dice su propio rótulo,
  // no una nota al pie que nadie lee.
  { clave: "pagadas", rotulo: "Total habitaciones pagadas (base de los indicadores)",
    formato: "num", banda: true, valor: ms => sum(ms, nochesPagadas) },
  { clave: "cortesias", rotulo: "Total habitaciones cortesías", formato: "num",
    valor: ms => sum(ms, nochesFuera) },
  { clave: "habEst", rotulo: "Total noches ocupadas con cortesías — no entra a los indicadores",
    formato: "num", tenue: true,
    valor: ms => sum(ms, m => porCat(m, "nights_occupied")) },
  { clave: "cliEnt", rotulo: "Clientes — Entradas", formato: "num",
    valor: ms => sum(ms, m => porCat(m, "cli_entradas")) },
  { clave: "cliEst", rotulo: "Clientes — Estancias", formato: "num",
    valor: ms => sum(ms, m => porCat(m, "pax")) },

  { clave: "dias", rotulo: "Días del mes", formato: "num", tenue: true,
    espacioAntes: true, valor: ms => sum(ms, m => m.dias) },
  { clave: "cap", rotulo: "Capacidad de habitaciones", formato: "num", tenue: true,
    valor: (ms, c) => (ms.length ? c.unidades : null) },
  { clave: "capNoche", rotulo: "Total habitaciones-noche (capacidad)", formato: "num",
    tenue: true, valor: (ms, c) => sum(ms, m => c.unidades * m.dias) },
  { clave: "disp", rotulo: "Habitaciones disponibles", formato: "num", tenue: true,
    valor: ms => disponibles(ms) },
  { clave: "bloq", rotulo: "Habitaciones bloqueadas", formato: "num", tenue: true,
    valor: ms => (ms.length && ms.every(m => m.resumen)
      ? sum(ms, m => m.resumen!.habitaciones_bloqueadas) : null) },
  // ⚠️ Los tres indicadores van sobre las noches PAGADAS.
  //
  // Antes iban sobre el total con cortesías, porque así los calcula el archivo
  // del PMS. Eso dejaba dos pantallas de la misma app contestando distinto: el
  // cierre decía ADR $317.66 para marzo y este cuadro $125.44, las dos bien
  // según su base, y nada explicaba la diferencia. Owner: *«no se usa para los
  // indicadores»*.
  //
  // Las cifras del archivo no se pierden: van abajo, en su propio bloque.
  { clave: "ocupTot", rotulo: "% Ocupación s/ total habitaciones", formato: "pct",
    banda: true,
    valor: (ms, c) => {
      const cap = sum(ms, m => c.unidades * m.dias);
      return cap ? sum(ms, nochesPagadas) / cap : null;
    } },
  { clave: "ocupDisp", rotulo: "% Ocupación s/ habitaciones disponibles",
    formato: "pct", banda: true,
    valor: ms => {
      const d = disponibles(ms);
      return d ? sum(ms, nochesPagadas) / d : null;
    } },

  { clave: "adr", rotulo: "ADR — Tarifa promedio (Hospedaje / noches pagadas)",
    formato: "usd", espacioAntes: true,
    valor: ms => {
      const n = sum(ms, nochesPagadas);
      return n ? sum(ms, ingresoPagado) / n : null;
    } },
  { clave: "revpar", rotulo: "RevPAR (Hospedaje / total hab.-noche)", formato: "usd",
    valor: (ms, c) => {
      const cap = sum(ms, m => c.unidades * m.dias);
      return cap ? sum(ms, ingresoPagado) / cap : null;
    } },

  // ── La otra base, para cuadrar contra el papel ──────────────────────────
  //
  // ⚠️ Sin esto el cuadro dejaría de cuadrar contra el archivo del PMS y
  // nadie podría explicar por qué. Van en gris: son la conciliación, no el
  // indicador.
  { clave: "ocupConCort", rotulo: "% Ocupación con cortesías (archivo del PMS)",
    formato: "pct", tenue: true, espacioAntes: true,
    valor: (ms, c) => {
      const cap = sum(ms, m => c.unidades * m.dias);
      return cap ? sum(ms, m => porCat(m, "nights_occupied")) / cap : null;
    } },
  { clave: "adrConCort", rotulo: "ADR con cortesías (archivo del PMS)",
    formato: "usd", tenue: true,
    valor: ms => {
      const n = sum(ms, m => porCat(m, "nights_occupied"));
      return n ? sum(ms, m => porCat(m, "revenue")) / n : null;
    } },
];

/* ══════════════════════ El archivo ══════════════════════════════════════ */

const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/**
 * El cuadro del resumen del PMS, para el Excel.
 *
 * ⚠️ Vive acá y no adentro del componente porque lo bajan DOS botones: el del
 * propio cuadro en el Dashboard y el paquete del cierre (owner, 2026-09-30:
 * *«también quiero que incluyas estos 2 excels»*). Dos armados del mismo cuadro
 * empiezan iguales y se separan en el primer arreglo que alguien hace de un
 * lado — y entonces el archivo suelto y el del paquete dirían cosas distintas
 * de los mismos datos.
 */
export function cuadroResumenConsolidado(anio: AnioRoomStats): Cuadro {
  const cargados = anio.meses.filter(m => m.cargado);
  const ctx: Ctx = {
    unidades: (anio.room_types ?? []).reduce((a, r) => a + r.units, 0),
  };
  const filas: FilaCuadro[] = RENGLONES.map(r => ({
    label: r.rotulo,
    es_total: !!r.banda,
    formato: r.formato === "usd" ? "usd2" : r.formato === "pct" ? "pct" : "num",
    // ⚠️ Un mes sin cargar va en `null` y NO en cero: una columna en cero dice
    // que ese mes no tuvo movimiento, que es una afirmación distinta.
    valores: [...anio.meses.map(m => (m.cargado ? r.valor([m], ctx) : null)),
              r.valor(cargados, ctx)],
  }));
  return {
    titulo: `Resumen consolidado ${anio.year} · estadística del PMS`,
    subtitulo: `${anio.escenario} — los indicadores van sobre las noches`
      + ` pagadas; las cifras con cortesías del archivo del PMS, al pie.`
      + ` Las columnas en blanco son meses sin cargar.`,
    hoja: `Resumen PMS ${anio.year}`,
    columnas: [
      { label: "Indicador", ancho: 44, formato: "texto" },
      ...anio.meses.map(m => ({ label: `${MES3[m.month - 1]} ${anio.year}`,
                                ancho: 14, formato: "num" as const })),
      { label: "Total / Prom.", ancho: 16, formato: "num" },
    ],
    filas,
  };
}


/* ══════════════════ Los canales de verdad, del PMS ═══════════════════════ */

/**
 * El acumulado por CANAL del PMS: noches, pax, ingreso y ADR.
 *
 * Owner, 2026-09-30, tachando la hoja «Canales de venta» del paquete y
 * mandando la captura de la vista «Canal × habitación»: *«poner este nuevo tab
 * acá, y cambiar lo que sale actualmente como canales»*.
 *
 * ⚠️ **Lo que salía no eran los canales: era su CONFIGURACIÓN.** La hoja vieja
 * traía «Direct · mix 45%», «Travel Agency · comisión», que es lo que se
 * parametriza para calcular la tarifa neta — y para el Actual estaba vacía,
 * porque un actual no tiene mix presupuestado. Esto trae por dónde entraron las
 * reservas de verdad.
 *
 * ⚠️ **Las tasas se recalculan sobre los totales.** El ADR de un canal en el
 * acumulado es su ingreso sobre sus noches, no el promedio de sus ADR
 * mensuales: promediar le daría el mismo peso a un mes de dos noches que a uno
 * de cuarenta.
 *
 * ⚠️ **Un mes sin cargar no entra.** Un cero se lee como «ese canal no vendió»,
 * y con una propiedad que abrió a mitad de año eso convierte un acumulado
 * incompleto en un mal semestre.
 */
export function cuadroCanalesDelPms(anio: AnioRoomStats): Cuadro {
  const acc = new Map<string, {
    rotulo: string; cuenta: boolean; noches: number; pax: number; rev: number;
  }>();
  for (const m of anio.meses) {
    if (!m.cargado) continue;
    for (const c of m.canales ?? []) {
      const clave = c.canal_code || c.canal || "—";
      const d = acc.get(clave) ?? {
        // El código del PMS es el que el owner reconoce —«EXPEDIA HOTEL
        // COLLECT»—; el canal comercial va al lado porque es el que decide si
        // ese ingreso paga comisión.
        rotulo: c.canal ? `${clave} · ${c.canal}` : clave,
        cuenta: c.cuenta_para_kpis, noches: 0, pax: 0, rev: 0,
      };
      d.noches += c.nights_occupied ?? 0;
      d.pax += c.pax ?? 0;
      d.rev += c.revenue ?? 0;
      acc.set(clave, d);
    }
  }
  const filas: FilaCuadro[] = [...acc.values()]
    .sort((a, b) => b.rev - a.rev || b.noches - a.noches)
    .map(d => ({
      label: d.rotulo,
      valores: [d.cuenta ? "Sí" : "No", d.noches, d.pax, d.rev,
                d.noches ? d.rev / d.noches : null],
    }));
  // ⚠️ El TOTAL es el de las noches que CUENTAN, que es la base de todos los
  // indicadores del cierre. La fila de abajo trae el archivo entero para poder
  // cuadrar contra el PDF sin abrir la aplicación.
  const suma = (f: (d: { noches: number; pax: number; rev: number }) => number,
                solo?: boolean) =>
    [...acc.values()].filter(d => !solo || d.cuenta).reduce((a, d) => a + f(d), 0);
  const nb = suma(d => d.noches, true);
  const rb = suma(d => d.rev, true);
  const nt = suma(d => d.noches);
  const rt = suma(d => d.rev);
  filas.push({
    label: "TOTAL", es_total: true,
    valores: ["", nb, suma(d => d.pax, true), rb, nb ? rb / nb : null],
  });
  if (Math.abs(nt - nb) > 0.005) {
    filas.push({
      label: "Con todos los canales (PDF)",
      valores: ["", nt, suma(d => d.pax), rt, nt ? rt / nt : null],
    });
  }
  return {
    titulo: `Canales del PMS ${anio.year} · acumulado`,
    subtitulo: `${anio.escenario} — noches, pax e ingreso por dónde entró la `
      + `reserva. Los indicadores van sobre las noches que cuentan; las `
      + `cortesías se listan y se restan. Las tasas se recalculan sobre los `
      + `totales del período, no se promedian.`,
    hoja: `Canales PMS ${anio.year}`.slice(0, 31),
    columnas: [
      { label: "Canal", ancho: 34, formato: "texto" },
      { label: "Cuenta", ancho: 9, formato: "texto" },
      { label: "Noches", ancho: 12, formato: "num" },
      { label: "Pax", ancho: 11, formato: "num" },
      { label: "Ingreso", ancho: 16, formato: "usd2" },
      { label: "ADR", ancho: 14, formato: "usd2" },
    ],
    filas,
  };
}
