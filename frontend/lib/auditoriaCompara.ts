import type { Auditoria, AuditoriaFila } from "@/lib/api";

/**
 * Poner la Auditoría de una versión al lado de otra.
 *
 * Owner, 2026-09-29: *«puedes poner a la par el budget o el forecast, la
 * versión que yo quiera para que compare el actual. algunas solamente serán
 * por cuenta total. no pasa nada. pero al menos comparar contra algo»*.
 *
 * ## Por qué esto vive aparte del render
 *
 * El cruce tiene tres casos y ninguno se ve mirando la pantalla: la cuenta que
 * coincide exacto, la que sólo coincide por total, y la que existe de un lado y
 * no del otro. Separado se puede correr contra datos de verdad.
 *
 * ## ⚠️ Nada se reclasifica acá
 *
 * Las dos auditorías salen del MISMO endpoint, así que el renglón del P&L al
 * que cae cada cuenta lo decidió `pl_engine.linea_de_fila` en los dos casos.
 * Este archivo sólo empareja por `departamento + cuenta`; si además tradujera o
 * reagrupara, una versión podría quedar clasificada distinto que la otra y la
 * comparación se vería perfectamente normal estando mal.
 */

/** La llave fina: el mismo desglose de los dos lados. */
const kExacta = (f: { dept_code: string; account_code: string; outlet?: string | null }) =>
  `${f.dept_code}|${f.account_code}|${f.outlet ?? ""}`;
/** La llave gruesa: la cuenta del departamento, sin desglose. */
const kCuenta = (f: { dept_code: string; account_code: string }) =>
  `${f.dept_code}|${f.account_code}`;

export interface FilaComparada extends AuditoriaFila {
  /** Lo que la otra versión tiene en esta cuenta.
   *
   *  `null` = no hay con qué comparar, o ya se comparó en la fila de arriba.
   *  ⚠️ No es cero. Un cero dice «la otra versión no tiene nada acá», que es
   *  una afirmación distinta y muchas veces falsa. */
  contra: number | null;
  /** El monto de la otra versión salió del TOTAL de la cuenta y no del mismo
   *  desglose. Pasa siempre que el presupuesto se digita por cuenta y el real
   *  llega por outlet — que es el caso que el owner ya daba por bueno. */
  porTotal: boolean;
  /** La otra versión tiene esta cuenta y ésta no. Es el renglón que no se ve de
   *  ninguna otra forma: lo presupuestado y no ejecutado. */
  soloContra: boolean;
}

export interface Indice {
  /** Por `dept|cuenta|outlet`. */
  exacto: Map<string, number>;
  /** Por `dept|cuenta`, sumando los desgloses. */
  porCuenta: Map<string, number>;
  /** Una fila de muestra por cuenta, para el nombre y la naturaleza de las que
   *  sólo existen del otro lado. */
  muestra: Map<string, AuditoriaFila>;
  /** El motor por renglón del P&L, para el cuadre. */
  porLinea: Map<string, number>;
}

/** El índice de la versión contra la que se compara. */
export function indiceDe(b: Auditoria | null): Indice | null {
  if (!b) return null;
  const ix: Indice = {
    exacto: new Map(), porCuenta: new Map(), muestra: new Map(), porLinea: new Map(),
  };
  for (const f of b.detalle) {
    // ⚠️ Las opciones del catálogo sin usar NO entran: son el inventario de
    // cuentas disponibles, no un monto presupuestado. Compararlas metería un
    // cero donde no hay nada.
    if (!f.movimiento) continue;
    const ke = kExacta(f), kc = kCuenta(f);
    ix.exacto.set(ke, (ix.exacto.get(ke) ?? 0) + f.monto);
    ix.porCuenta.set(kc, (ix.porCuenta.get(kc) ?? 0) + f.monto);
    if (!ix.muestra.has(kc)) ix.muestra.set(kc, f);
  }
  for (const f of b.cuadre) {
    if (f.linea && f.motor !== null) ix.porLinea.set(f.linea, f.motor);
  }
  return ix;
}

/**
 * El detalle de A con la columna de B al lado, más las cuentas que sólo están
 * en B.
 *
 * ⚠️ **El total de la cuenta se cuelga de UNA sola fila.** Si el real trae tres
 * outlets de la misma cuenta y el presupuesto la tiene sin desglosar, repetir
 * el total en las tres filas lo contaría tres veces — y la suma de la columna
 * daría el triple sin que ninguna fila se viera rara. Las otras van en blanco,
 * con su explicación.
 */
export function compararDetalle(
  a: AuditoriaFila[], ix: Indice | null,
): FilaComparada[] {
  if (!ix) {
    return a.map(f => ({ ...f, contra: null, porTotal: false, soloContra: false }));
  }

  /** Qué cuentas de B ya quedaron emparejadas, para no repetirlas al final. */
  const vistas = new Set<string>();
  /** A qué cuentas ya se les colgó el total, para no contarlo dos veces. */
  const totalPuesto = new Set<string>();

  const out: FilaComparada[] = a.map(f => {
    if (!f.movimiento) {
      return { ...f, contra: null, porTotal: false, soloContra: false };
    }
    const ke = kExacta(f), kc = kCuenta(f);
    vistas.add(kc);
    const exacto = ix.exacto.get(ke);
    if (exacto !== undefined) {
      return { ...f, contra: exacto, porTotal: false, soloContra: false };
    }
    const total = ix.porCuenta.get(kc);
    if (total !== undefined && !totalPuesto.has(kc)) {
      totalPuesto.add(kc);
      return { ...f, contra: total, porTotal: true, soloContra: false };
    }
    return { ...f, contra: null, porTotal: false, soloContra: false };
  });

  // ── Lo que la otra versión tiene y ésta no ────────────────────────────────
  //
  // Es el renglón que no aparece de ninguna otra forma: una partida
  // presupuestada y sin ejecutar no deja rastro en el real, así que sin esto la
  // auditoría no la puede mostrar. Va en cero del lado de acá, que es el dato.
  for (const [kc, monto] of ix.porCuenta) {
    if (vistas.has(kc) || Math.abs(monto) < 0.005) continue;
    const m = ix.muestra.get(kc);
    if (!m) continue;
    out.push({ ...m, monto: 0, contra: monto, porTotal: false, soloContra: true });
  }
  return out;
}

/** La diferencia de una fila. `null` cuando no hay contra qué restar — restar
 *  de la nada daría el monto entero disfrazado de variación. */
export const difDe = (f: { monto: number; contra: number | null }) =>
  f.contra === null ? null : f.monto - f.contra;

/** El total de una columna de comparación.
 *
 *  ⚠️ Suma sólo lo que tiene contraparte. Si sumara los `null` como cero, el
 *  total de B saldría más chico que la suma real de B cada vez que una cuenta
 *  no empareje — y se leería como un ahorro. */
export const sumaContra = (filas: FilaComparada[]) =>
  filas.reduce((t, f) => t + (f.contra ?? 0), 0);
