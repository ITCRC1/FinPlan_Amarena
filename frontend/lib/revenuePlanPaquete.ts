import {
  getChannelsConfig, getRackRates, getRevenueByRoomType, type Scenario,
} from "@/lib/api";
import type { Cuadro, FilaCuadro } from "@/lib/exportCuadro";
import {
  ES_PROMEDIO, filasDeIngresos, totalDeIngresos, valorDeIngresos,
  type FuenteIngresos, type VistaIngresos,
} from "@/lib/revenuePlanCortes";
import { celdasDe, cortesDe, parDe, vistaDe } from "@/lib/tresCortes";

/**
 * Las ocho hojas del armado de ingresos, listas para cualquier archivo.
 *
 * Owner, 2026-09-30: *«ahora hagamos merge al archivo de resumen ejecutivo.
 * agreguemos al final para tener ahora sí un consolidado»*.
 *
 * ## Por qué esto vive en una lib y no en la pantalla
 *
 * Lo bajan DOS lugares: el botón de Armado de ingresos y el paquete del cierre.
 * Con el armado escrito adentro de una pantalla, el otro archivo tendría que
 * reescribirlo — y dos versiones del mismo cuadro empiezan iguales y se separan
 * en el primer arreglo que alguien hace de un lado. Entonces el consolidado y
 * el suelto dirían cosas distintas de los mismos datos, y no habría forma de
 * saber cuál manda.
 *
 * ## ⚠️ Nada se recalcula acá
 *
 * Los tres cortes, el par que se resta y la agregación de cada vista salen de
 * `lib/tresCortes` y `lib/revenuePlanCortes`. Este archivo sólo pide los datos
 * y arma columnas.
 */

/** Las ocho, en el orden en que el owner las pidió. */
export const VISTAS_INGRESOS = [
  { key: "inventario", rotulo: "Inventario" },
  { key: "noches", rotulo: "Noches por categoría" },
  { key: "rack", rotulo: "Rack rates" },
  { key: "ocupacion", rotulo: "Ocupación" },
  { key: "pax", rotulo: "Pax" },
  { key: "canales", rotulo: "Canales de venta" },
  { key: "net", rotulo: "Net rate" },
  { key: "revenue", rotulo: "Total revenue" },
] as const;

/** Cómo se escribe cada vista. */
export const formatoDeVista = (v: VistaIngresos) =>
  v === "ocupacion" || v === "canales" ? "pct"
    : v === "rack" || v === "net" || v === "revenue" ? "usd" : "num";

/**
 * Lo cargado de cada versión: tres endpoints por una.
 *
 * ⚠️ `allSettled` en los nueve. Que a una versión le falte la configuración de
 * canales no puede dejar el archivo entero sin noches: lo que falte queda en
 * `null` y su celda sale vacía, que es distinto de un cero.
 */
export async function cargarFuentesIngresos(
  ids: string[],
): Promise<Record<string, FuenteIngresos>> {
  const out: Record<string, FuenteIngresos> = {};
  await Promise.all([...new Set(ids.filter(Boolean))].map(async id => {
    const [a, b, c] = await Promise.allSettled([
      getRevenueByRoomType(id), getRackRates(id), getChannelsConfig(id),
    ]);
    out[id] = {
      porTipo: a.status === "fulfilled" ? a.value : null,
      rack: b.status === "fulfilled" ? b.value : null,
      canales: c.status === "fulfilled" ? c.value : null,
    };
  }));
  return out;
}

export interface ArmadoDeIngresos {
  fuentes: Record<string, FuenteIngresos>;
  /** Las versiones que SON columnas, en orden: Actual, Budget, Forecast. */
  visibles: string[];
  /** Quién ocupa la primera columna del full year — el Forecast Current. El
   *  Actual del año repite el YTD. */
  actualDelFullYear: string;
  mes: number;
  escenarios: Scenario[];
  /** El nombre del mes, para el subtítulo. */
  rotuloMes: string;
}

/** Las versiones que viajan y cómo se dibujan.
 *
 * ⚠️ El Forecast Current entra en la lista aunque no sea columna. Con las
 * visibles nada más, `parDe` no encuentra ningún FORECAST cuando el owner lo
 * sacó de las ranuras y el año completo se queda SIN columna de varianza,
 * mostrando el forecast en la primera columna y sin nada contra qué leerlo.
 * Es la misma vista del P&L y de los checkbooks.
 */
function vistaDelArmado(a: ArmadoDeIngresos) {
  const todas = [...new Set([...a.visibles, a.actualDelFullYear]
    .filter(Boolean))].map(id => ({ scenario_id: id }));
  return {
    todas,
    vista: vistaDe(todas, a.visibles, a.actualDelFullYear, a.escenarios),
  };
}

/** Las filas de UNA vista, en los tres cortes. */
export function filasDelArmado(
  cual: VistaIngresos, a: ArmadoDeIngresos,
): FilaCuadro[] {
  const usadas = a.visibles.map(id => a.fuentes[id]).filter(Boolean);
  if (!usadas.length) return [];
  const cortes = cortesDe(a.mes);
  const { todas, vista } = vistaDelArmado(a);
  /** ⚠️ `vi` es un índice de VERSIÓN, no una posición de columna: `celdasDe` ya
   *  aplicó la regla del año completo. */
  const sidDe = (vi: number) => todas[vi]?.scenario_id ?? "";
  const base = filasDeIngresos(cual, usadas);
  const celdas = (de: (vi: number, meses: number[], ci: number) => number | null) =>
    celdasDe(cortes, todas, a.escenarios, de, vista);
  const mesesDe = (ms: number[]) => ms.map(i => i + 1);

  const cuerpo: FilaCuadro[] = base.map(f => ({
    label: f.label, es_total: false,
    valores: celdas((vi, ms) => {
      const fu = a.fuentes[sidDe(vi)];
      return fu ? valorDeIngresos(cual, fu, f.clave, mesesDe(ms)) : null;
    }),
  }));
  const pie: FilaCuadro = {
    label: "TOTAL", es_total: true,
    valores: celdas((vi, ms) => {
      const fu = a.fuentes[sidDe(vi)];
      return fu ? totalDeIngresos(cual, fu, base, mesesDe(ms)) : null;
    }),
  };
  return [...cuerpo, ...(pie.valores.some(v => v !== null) ? [pie] : [])];
}

/** El cuadro de UNA vista. */
export function cuadroDelArmado(
  cual: VistaIngresos, rotuloVista: string, filas: FilaCuadro[],
  a: ArmadoDeIngresos,
): Cuadro {
  const f = formatoDeVista(cual);
  const fmt = (f === "pct" ? "pct" : f === "usd" ? "usd2" : "num") as
    "pct" | "usd2" | "num";
  const cortes = cortesDe(a.mes);
  const { todas, vista } = vistaDelArmado(a);
  const idDe = (col: number, ci: number) =>
    todas[vista.vi(col, ci)]?.scenario_id ?? "";
  const etiqueta = (sid: string) => {
    const e = a.escenarios.find(x => x.id === sid);
    return e ? `${e.type} ${e.version}` : "";
  };
  return {
    titulo: `${rotuloVista} · mes, YTD y full year`,
    subtitulo: `${a.rotuloMes} — en el full year la primera columna es el `
      + `Forecast Current y la varianza es Forecast contra Budget.`
      // ⚠️ El aviso viaja a CADA hoja. En una suelta —impresa, o pegada en otro
      // lado— un promedio sin avisar se lee como un acumulado.
      + (ES_PROMEDIO(cual)
         ? ` Esta vista son razones: el valor de un corte de varios meses es un `
           + `promedio, no un acumulado.` : ""),
    // ⚠️ El nombre de la vista en la pestaña. Ocho hojas con el mismo nombre las
    // desempata Excel con un número y hay que abrirlas una por una.
    hoja: rotuloVista.slice(0, 31),
    columnas: [
      { label: cual === "canales" ? "Canal" : "Tipo de habitación",
        ancho: 34, formato: "texto" },
      ...cortes.flatMap((c, ci) => [
        ...vista.columnas.map((_c, col) => ({
          label: `${c.titulo} · ${etiqueta(idDe(col, ci))}`,
          ancho: 15, formato: fmt })),
        ...(parDe(c, todas, a.escenarios, vista)
          ? [{ label: `${c.titulo} · Var`, ancho: 15, formato: fmt }] : []),
      ]),
    ],
    filas,
  };
}

/** Las ocho hojas. Una vista sin filas no baja: una hoja vacía se lee como «no
 *  hay inventario», que es una afirmación. */
export function cuadrosDelArmado(a: ArmadoDeIngresos): Cuadro[] {
  const out: Cuadro[] = [];
  for (const v of VISTAS_INGRESOS) {
    const filas = filasDelArmado(v.key, a);
    if (filas.length) out.push(cuadroDelArmado(v.key, v.rotulo, filas, a));
  }
  return out;
}
