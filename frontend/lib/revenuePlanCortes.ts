import type { ChannelsConfig, RackRatesResponse, RevenueByRoomType } from "@/lib/api";
import { rtLabel } from "@/lib/api";

/**
 * El armado de ingresos en los TRES cortes: mes, YTD y full year.
 *
 * Owner, 2026-09-30, sobre la pantalla de Armado de ingresos: *«acá lo mismo
 * que en opex: mes, ytd y full year»*.
 *
 * ## ⚠️ Acá la mitad de las vistas NO se suman, y por eso esto existe aparte
 *
 * En el checkbook todo era plata: un corte es sumar meses. Acá conviven cinco
 * unidades distintas, y **cada una se agrega de una forma**:
 *
 * | vista | corte de varios meses |
 * |---|---|
 * | Noches · Pax · Total revenue | **suma** |
 * | Inventario | las unidades del ÚLTIMO mes — no se suman, son las mismas |
 * | Ocupación | noches ocupadas del período ÷ noches disponibles del período |
 * | Net rate | ingreso del período ÷ noches ocupadas del período |
 * | Rack rates · Canales | **promedio simple** de los meses del corte |
 *
 * Sumar doce ocupaciones da 700% y se ve perfectamente normal en una celda.
 * Promediar doce net rates le da el mismo peso a un mes con tres noches que a
 * uno lleno: en Amarena, que abre en junio, eso movía la tarifa del año.
 *
 * ⚠️ **Rack y Canales son un promedio de los meses CON valor**, y eso es una
 * aproximación. Una tarifa publicada y un mix de canales no tienen un
 * denominador natural acá —el mix se ponderaría por venta, que esta pantalla no
 * trae—. Se muestran con la marca «prom.» para que nadie los lea como un total.
 * Dejarlos en blanco era la alternativa, y un corte con dos vistas vacías no
 * contesta la pregunta que se hizo.
 *
 * ## ⚠️ Las filas se cruzan por CÓDIGO, no por id
 *
 * Cada versión tiene sus propios `room_type_id`: el mismo «BI02 · Beachfront
 * Deluxe-Tented Villa» es un id en el Actual y otro en el Budget. Cruzando por
 * id, el inventario salía **dos veces cada categoría** —cuatro filas con
 * números sólo en el Actual y otras cuatro sólo en el presupuesto— y la tabla
 * no se podía leer. Owner, 2026-09-30: *«que no se repita la misma línea de
 * inventario»*.
 *
 * El código es lo que significa lo mismo en las dos versiones. El id sólo
 * sirve adentro de una.
 *
 * ⚠️ **Los meses en cero quedan FUERA del promedio**, que es la misma regla que
 * el owner fijó para los socios del Club (2026-09-02: *«quiero que me des un
 * promedio de los meses y no que sume»*, sobre los meses con dato). Amarena
 * abre en junio: con los cinco meses cerrados adentro, el rack del YTD de
 * agosto daba **175** donde la tarifa real es 490, y el mix de OTA daba 17,5%
 * donde es 43%. Un cero ahí no es una tarifa baja: es que no hubo temporada.
 */

/** Lo que se cargó de UNA versión. Cualquiera puede faltar sin llevarse el
 *  resto: son tres endpoints distintos. */
export interface FuenteIngresos {
  porTipo: RevenueByRoomType | null;
  rack: RackRatesResponse | null;
  canales: ChannelsConfig | null;
}

export type VistaIngresos =
  | "inventario" | "noches" | "rack" | "ocupacion"
  | "pax" | "canales" | "net" | "revenue";

/** Las vistas cuyo valor de corte es un promedio y no un acumulado. */
export const ES_PROMEDIO = (v: VistaIngresos) =>
  v === "rack" || v === "canales" || v === "ocupacion" || v === "net";

const CLAVES = ["jan", "feb", "mar", "apr", "may", "jun",
                "jul", "aug", "sep", "oct", "nov", "dec"] as const;

export interface FilaIngresos { clave: string; label: string }

/** El promedio de los meses que TIENEN valor.
 *
 *  ⚠️ Los ceros quedan afuera. Amarena abre en junio: con enero-mayo adentro,
 *  el rack del YTD de agosto daba 175 donde la tarifa real es 490. Un cero no
 *  es una tarifa baja — es que no hubo temporada. */
const promedioVivo = (vs: number[]) => {
  const vivos = vs.filter(v => Math.abs(v) > 1e-9);
  return vivos.length ? vivos.reduce((a, n) => a + n, 0) / vivos.length : 0;
};

/** Las filas de una vista. Salen de la UNIÓN de las versiones: un tipo de
 *  habitación que sólo está en el presupuesto tiene que verse, y es justo el
 *  que interesa. */
export function filasDeIngresos(
  vista: VistaIngresos, fuentes: FuenteIngresos[],
): FilaIngresos[] {
  const out = new Map<string, string>();
  for (const f of fuentes) {
    if (vista === "rack") {
      // ⚠️ `code` es opcional en esta respuesta: la llave cae en el id, que
      // siempre está. Sin el respaldo, un hotel sin códigos dejaría todas las
      // filas bajo la llave `undefined` y se verían como una sola.
      for (const r of f.rack?.rooms ?? []) {
        out.set(r.code || r.room_type_id, rtLabel(r.code ?? "", r.name));
      }
    } else if (vista === "canales") {
      for (const c of f.canales?.channels ?? []) {
        out.set(`${c.label}|mix`, `${c.label} · mix`);
        out.set(`${c.label}|comm`, `${c.label} · comisión`);
      }
    } else {
      for (const rt of f.porTipo?.room_types ?? []) {
        out.set(claveRt(rt), rtLabel(rt.code, rt.name));
      }
    }
  }
  // Orden estable por código. Sin esto el orden lo fija la versión que se
  // cargó primero, y cambiar de Forecast reacomodaba las filas.
  return [...out.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([clave, label]) => ({ clave, label }));
}

/** La llave con la que una categoría se cruza ENTRE versiones.
 *
 *  ⚠️ El código, no el id: cada versión tiene sus propios ids para la misma
 *  categoría. El id queda de respaldo por si alguna no trae código — ahí se
 *  vuelve a duplicar, pero al menos no desaparece. */
const claveRt = (rt: { id: string; code?: string | null }) =>
  (rt.code || "").trim().toUpperCase() || rt.id;

/** El id que ESA versión le da a la categoría de esa llave. */
const idRt = (f: FuenteIngresos, clave: string) =>
  (f.porTipo?.room_types ?? []).find(rt => claveRt(rt) === clave)?.id ?? "";

/** Un campo de un tipo de habitación en un mes. */
const campo = (
  f: FuenteIngresos, rtId: string, mes: number,
  c: "units" | "nights_available" | "nights_occupied" | "occupancy_pct"
   | "revenue" | "adr" | "pax",
) => {
  const m = f.porTipo?.months.find(x => x.month === mes);
  const r = m?.rows.find(x => x.room_type_id === rtId);
  return r ? Number(r[c] ?? 0) : 0;
};

const sumaDe = (f: FuenteIngresos, rt: string, meses: number[],
                c: Parameters<typeof campo>[3]) =>
  meses.reduce((a, m) => a + campo(f, rt, m, c), 0);

/**
 * El valor de una fila para un corte.
 *
 * ⚠️ `meses` son 1..12. `null` cuando esa versión no tiene ese dato — no cero:
 * un presupuesto sin configuración de canales no es un mix en cero.
 */
export function valorDeIngresos(
  vista: VistaIngresos, f: FuenteIngresos, clave: string, meses: number[],
): number | null {
  if (!meses.length) return null;

  if (vista === "rack") {
    const r = (f.rack?.rooms ?? []).find(x => (x.code || x.room_type_id) === clave);
    if (!r) return null;
    return promedioVivo(meses.map(m => Number(r[CLAVES[m - 1]] ?? 0)));
  }

  if (vista === "canales") {
    const [label, cual] = clave.split("|");
    const c = (f.canales?.channels ?? []).find(x => x.label === label);
    if (!c) return null;
    const serie = cual === "mix" ? c.mix : c.comm;
    return promedioVivo(meses.map(m => Number(serie[m - 1] || 0)));
  }

  const rt = idRt(f, clave);
  if (!rt) return null;

  switch (vista) {
    case "inventario": {
      // ⚠️ Las unidades NO se suman: son las mismas todos los meses. El valor
      // del corte es el inventario al final del período.
      return campo(f, rt, meses[meses.length - 1], "units");
    }
    case "noches":  return sumaDe(f, rt, meses, "nights_occupied");
    case "pax":     return sumaDe(f, rt, meses, "pax");
    case "revenue": return sumaDe(f, rt, meses, "revenue");
    case "ocupacion": {
      const disp = sumaDe(f, rt, meses, "nights_available");
      return disp ? sumaDe(f, rt, meses, "nights_occupied") / disp : 0;
    }
    case "net": {
      // Ingreso ÷ noches del período. El promedio de doce tarifas le daría el
      // mismo peso a un mes con tres noches que a uno lleno.
      const noc = sumaDe(f, rt, meses, "nights_occupied");
      return noc ? sumaDe(f, rt, meses, "revenue") / noc : 0;
    }
  }
  return null;
}

/**
 * El TOTAL de una vista para un corte — la fila del pie.
 *
 * ⚠️ No es la suma de la columna en las vistas de razón. La ocupación total es
 * el total de noches ocupadas sobre el total de disponibles, no el promedio de
 * las ocupaciones por tipo: un tipo con dos villas pesaría igual que uno con
 * ocho. Y en rack y canales no hay total que valga, así que va `null`.
 */
export function totalDeIngresos(
  vista: VistaIngresos, f: FuenteIngresos, filas: FilaIngresos[], meses: number[],
): number | null {
  if (vista === "rack" || vista === "canales") return null;
  const rts = filas.map(x => idRt(f, x.clave)).filter(Boolean);
  const sum = (c: Parameters<typeof campo>[3]) =>
    rts.reduce((a, rt) => a + sumaDe(f, rt, meses, c), 0);
  switch (vista) {
    case "inventario":
      return rts.reduce(
        (a, rt) => a + campo(f, rt, meses[meses.length - 1], "units"), 0);
    case "noches":  return sum("nights_occupied");
    case "pax":     return sum("pax");
    case "revenue": return sum("revenue");
    case "ocupacion": {
      const d = sum("nights_available");
      return d ? sum("nights_occupied") / d : 0;
    }
    case "net": {
      const n = sum("nights_occupied");
      return n ? sum("revenue") / n : 0;
    }
  }
  return null;
}
