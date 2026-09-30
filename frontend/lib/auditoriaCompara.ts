import type { Auditoria, AuditoriaFila } from "@/lib/api";

/**
 * Poner la Auditoría de una versión al lado de otra.
 *
 * Owner, 2026-09-29: *«puedes poner a la par el budget o el forecast, la
 * versión que yo quiera para que compare el actual. algunas solamente serán
 * por cuenta total. no pasa nada. pero al menos comparar contra algo»*.
 *
 * ## Los dos lados no hablan el mismo idioma, y eso es el problema entero
 *
 * El real llega del mayor: departamento `0110`, cuenta `4000`. El presupuesto
 * llega de los checkbooks, y **el ingreso no tiene ni cuenta ni departamento**
 * — la llave es el GRUPO (`ROOMS`), y el departamento va vacío (ver
 * `auditoria_api._asientos_del_checkbook`). Emparejar sólo por cuenta dejaba
 * todos los ingresos sin comparar mientras los gastos cuadraban, que es
 * exactamente lo que el owner vio: *«por que los gastos salen y los ingresos no
 * salen para ninguno»*.
 *
 * Por eso el cruce baja por TRES niveles, del más fino al más grueso:
 *
 * 1. el mismo desglose — `departamento + cuenta + outlet`;
 * 2. el total de la cuenta — `departamento + cuenta`;
 * 3. **el renglón del P&L** — lo que queda de esa línea sin emparejar.
 *
 * El nivel 3 es el que salva al ingreso: los dos lados caen en `REV_ROOMS`
 * porque lo decidió el mismo motor, aunque uno diga `4000` y el otro `ROOMS`.
 *
 * ## ⚠️ Lo que se reparte es el RESTO, nunca el total otra vez
 *
 * Cada nivel consume lo que toma. Si dos cuentas de una línea ya emparejaron
 * por código y una tercera baja al nivel de línea, recibe **lo que sobra** y no
 * el total de la línea — si recibiera el total, la columna sumaría de más y
 * ninguna fila se vería rara. Blindado: la columna tiene que dar exactamente el
 * total de la otra versión.
 *
 * ## ⚠️ Nada se reclasifica acá
 *
 * Las dos auditorías salen del MISMO endpoint, así que a qué renglón del P&L
 * cae cada monto lo decidió `pl_engine.linea_de_fila` de los dos lados. Este
 * archivo sólo empareja; si además tradujera o reagrupara, una versión podría
 * quedar clasificada distinto que la otra y la comparación se vería
 * perfectamente normal estando mal.
 */

const CERO = 0.005;

/** La llave fina: el mismo desglose de los dos lados. */
const kExacta = (f: { dept_code: string; account_code: string; outlet?: string | null }) =>
  `${f.dept_code}|${f.account_code}|${f.outlet ?? ""}`;
/** La llave gruesa: la cuenta del departamento, sin desglose. */
const kCuenta = (f: { dept_code: string; account_code: string }) =>
  `${f.dept_code}|${f.account_code}`;

export interface FilaComparada extends AuditoriaFila {
  /** Lo que la otra versión tiene acá.
   *
   *  `null` = no hay con qué comparar, o ya se comparó más arriba.
   *  ⚠️ No es cero. Un cero dice «la otra versión no tiene nada acá», que es
   *  una afirmación distinta y muchas veces falsa. */
  contra: number | null;
  /** El monto salió del TOTAL de la cuenta y no del mismo desglose. */
  porTotal: boolean;
  /** El monto salió del RENGLÓN del P&L: la otra versión no tiene esa cuenta
   *  con ese código. Es el caso del ingreso presupuestado, que viene por grupo
   *  (`ROOMS`) y no por cuenta (`4000`). */
  porLinea: boolean;
  /** La otra versión tiene esto y ésta no. Es el renglón que no se ve de
   *  ninguna otra forma: lo presupuestado y no ejecutado. */
  soloContra: boolean;
}

/** Una cuenta de la otra versión, con lo que le queda por emparejar. */
interface Bolsa {
  dept: string; linea: string; muestra: AuditoriaFila;
  /** Por desglose, para el nivel 1. */
  exacto: Map<string, number>;
  /** Lo que todavía no se le asignó a ninguna fila. */
  resto: number;
}

export interface Indice {
  bolsas: Map<string, Bolsa>;
  /** El motor por renglón del P&L, para el cuadre de arriba. */
  porLinea: Map<string, number>;
}

/** El índice de la versión contra la que se compara. */
export function indiceDe(b: Auditoria | null): Indice | null {
  if (!b) return null;
  const ix: Indice = { bolsas: new Map(), porLinea: new Map() };
  for (const f of b.detalle) {
    // ⚠️ Las opciones del catálogo sin usar NO entran: son el inventario de
    // cuentas disponibles, no un monto presupuestado. Compararlas metería un
    // cero donde no hay nada.
    if (!f.movimiento) continue;
    const kc = kCuenta(f);
    const bolsa = ix.bolsas.get(kc) ?? {
      dept: f.dept_code, linea: f.linea ?? "", muestra: f,
      exacto: new Map<string, number>(), resto: 0,
    };
    const ke = kExacta(f);
    bolsa.exacto.set(ke, (bolsa.exacto.get(ke) ?? 0) + f.monto);
    bolsa.resto += f.monto;
    ix.bolsas.set(kc, bolsa);
  }
  for (const f of b.cuadre) {
    if (f.linea && f.motor !== null) ix.porLinea.set(f.linea, f.motor);
  }
  return ix;
}

/** Saca de una bolsa lo que se le asigna a una fila, y lo descuenta. */
function tomar(b: Bolsa, monto: number): number {
  b.resto -= monto;
  return monto;
}

/**
 * El detalle de A con la columna de B al lado, más lo que sólo está en B.
 *
 * ⚠️ **Cada monto de B se entrega UNA sola vez.** Si el real trae tres outlets
 * de la misma cuenta y el presupuesto la tiene sin desglosar, repetir el total
 * en las tres filas lo contaría tres veces — y la suma de la columna daría el
 * triple sin que ninguna fila se viera rara.
 */
export function compararDetalle(
  a: AuditoriaFila[], ix: Indice | null,
): FilaComparada[] {
  const limpia = (f: AuditoriaFila): FilaComparada =>
    ({ ...f, contra: null, porTotal: false, porLinea: false, soloContra: false });
  if (!ix) return a.map(limpia);

  // Copia de trabajo: el índice se reusa entre renders y no se puede vaciar.
  const bolsas = new Map<string, Bolsa>();
  for (const [k, b] of ix.bolsas) bolsas.set(k, { ...b, exacto: new Map(b.exacto) });

  /** Las bolsas de un renglón del P&L que todavía tienen resto.
   *
   *  `dept` vacío = la otra versión no dice de qué departamento es. Le pasa al
   *  ingreso presupuestado, y es justo el que hay que poder emparejar: si se
   *  exigiera el mismo departamento, no encontraría ninguno. */
  const deLaLinea = (dept: string, linea: string) =>
    [...bolsas.values()].filter(b =>
      b.linea === linea && Math.abs(b.resto) >= CERO
      && (b.dept === dept || b.dept === ""));

  const out: FilaComparada[] = a.map(f => {
    if (!f.movimiento) return limpia(f);
    const r = limpia(f);
    const bolsa = bolsas.get(kCuenta(f));

    // ── 1. El mismo desglose ────────────────────────────────────────────────
    const exacto = bolsa?.exacto.get(kExacta(f));
    if (bolsa && exacto !== undefined && Math.abs(exacto) >= CERO) {
      bolsa.exacto.delete(kExacta(f));
      r.contra = tomar(bolsa, exacto);
      return r;
    }
    // ── 2. El total de la cuenta ────────────────────────────────────────────
    if (bolsa && Math.abs(bolsa.resto) >= CERO) {
      bolsa.exacto.clear();
      r.contra = tomar(bolsa, bolsa.resto);
      r.porTotal = true;
      return r;
    }
    // ── 3. El renglón del P&L ───────────────────────────────────────────────
    //
    // Acá empareja el ingreso: los dos lados caen en `REV_ROOMS` porque lo
    // decidió el mismo motor, aunque uno diga `4000` y el otro `ROOMS`.
    //
    // ⚠️ **Sólo baja acá la cuenta que la otra versión NO tiene.** Si la tiene
    // y ya se agotó arriba, esta fila queda en blanco y punto: dejarla bajar
    // haría que el segundo outlet de una cuenta ya comparada se llevara el
    // presupuesto de OTRA cuenta de la misma línea. La columna seguiría
    // sumando bien —por eso no se nota— pero la plata estaría en la fila
    // equivocada, que es el peor error de una auditoría.
    const resto = f.linea && !bolsa ? deLaLinea(f.dept_code, f.linea) : [];
    if (resto.length) {
      let suma = 0;
      for (const b of resto) { b.exacto.clear(); suma += tomar(b, b.resto); }
      r.contra = suma;
      r.porLinea = true;
      return r;
    }
    return r;
  });

  // ── Lo que la otra versión tiene y ésta no ────────────────────────────────
  //
  // Una partida presupuestada y sin ejecutar no deja rastro en el real, así que
  // sin esto la auditoría no la puede mostrar — y es de las que más interesan.
  // Va en cero del lado de acá, que es el dato.
  for (const b of bolsas.values()) {
    if (Math.abs(b.resto) < CERO) continue;
    out.push({
      ...b.muestra, monto: 0, contra: b.resto,
      porTotal: false, porLinea: false, soloContra: true,
    });
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
