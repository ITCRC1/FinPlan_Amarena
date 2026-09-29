import type { AnioMes } from "@/lib/api";

/**
 * La aritmética del Resumen Consolidado, sin una línea de pantalla.
 *
 * Vive aparte del componente a propósito: así se puede correr contra los datos
 * reales y contrastar renglón por renglón contra el cuadro que la propiedad
 * arma a mano. Una tabla financiera que sólo se puede verificar mirándola es
 * una tabla que nadie verifica.
 *
 * ## ⚠️ Este cuadro NO filtra las cortesías
 *
 * Reproduce lo que dice el **archivo del PMS**: las 51 noches de marzo, no las
 * 20 que quedan al sacar el CPL. Es el papel contra el que la propiedad
 * cuadra, y por eso lleva su propio renglón de cortesías — para que la
 * diferencia con el cierre se vea en vez de parecer un error.
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

/** Noches de los canales que la propiedad dejó fuera de los indicadores. */
export const nochesFuera = (m: AnioMes) =>
  m.canales.reduce((a, c) => a + (c.cuenta_para_kpis ? 0 : c.nights_occupied), 0);

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
  { clave: "habEst", rotulo: "Habitaciones — Estancias (noches)", formato: "num",
    banda: true, valor: ms => sum(ms, m => porCat(m, "nights_occupied")) },
  { clave: "cliEnt", rotulo: "Clientes — Entradas", formato: "num",
    valor: ms => sum(ms, m => porCat(m, "cli_entradas")) },
  { clave: "cliEst", rotulo: "Clientes — Estancias", formato: "num",
    valor: ms => sum(ms, m => porCat(m, "pax")) },
  { clave: "fuera", rotulo: "Habitaciones — cortesías (fuera de los indicadores)",
    formato: "num", tenue: true, valor: ms => sum(ms, nochesFuera) },

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
  { clave: "ocupTot", rotulo: "% Ocupación s/ total habitaciones", formato: "pct",
    banda: true,
    valor: (ms, c) => {
      const cap = sum(ms, m => c.unidades * m.dias);
      return cap ? sum(ms, m => porCat(m, "nights_occupied")) / cap : null;
    } },
  { clave: "ocupDisp", rotulo: "% Ocupación s/ habitaciones disponibles",
    formato: "pct", banda: true,
    valor: ms => {
      const d = disponibles(ms);
      return d ? sum(ms, m => porCat(m, "nights_occupied")) / d : null;
    } },

  { clave: "adr", rotulo: "ADR — Tarifa promedio (Hospedaje / noches)",
    formato: "usd", espacioAntes: true,
    valor: ms => {
      const n = sum(ms, m => porCat(m, "nights_occupied"));
      return n ? sum(ms, m => porCat(m, "revenue")) / n : null;
    } },
  { clave: "revpar", rotulo: "RevPAR (Hospedaje / total hab.-noche)", formato: "usd",
    valor: (ms, c) => {
      const cap = sum(ms, m => c.unidades * m.dias);
      return cap ? sum(ms, m => porCat(m, "revenue")) / cap : null;
    } },
];
