/**
 * En qué COLUMNA del Excel cae cada ranura de versión.
 *
 * Owner, 2026-09-30: *«necesito que todos los tabs que bajan en ese archivo
 * estén formulados. Cada uno de ellos. Revisar los subtotales con los totales y
 * que todo lleve fórmula»*.
 *
 * Una columna de variación baja como `=Xn-Yn`, y para escribirla hay que saber
 * en qué letra quedó cada operando. Eso parece trivial y no lo es: los cuadros
 * del cierre tienen **dos formas distintas** de acomodar sus columnas, y
 * confundirlas da una fórmula que resta otras dos — que se ve exactamente igual
 * de confiable que la correcta.
 *
 * ⚠️ **Por qué vive acá y no adentro de la pantalla.** Es aritmética de
 * índices: el único error posible es silencioso —la hoja se abre, la fórmula
 * calcula, el número está mal— y sólo se descubre comparando contra el motor.
 * Acá se puede correr sin React y comprobarlo para todas las combinaciones de
 * ranuras, que es lo que hace `tests/test_columnas_de_ranura`.
 */

/** La ranura ocupada: `i` es su posición original (0-3) en el selector. */
export interface Ranura { i: number }

/**
 * Cuadros cuya cabecera arma `enOrden`: **las dos columnas de variación parten
 * la lista en el medio**, justo después de la última de las dos comparadas.
 *
 * ```
 * 0          1 … T        1+T      2+T      3+T … 2+U
 * [rótulo] [ranuras<T] [Var $] [Var %] [ranuras>=T]
 * ```
 *
 * Owner, sobre por qué van en el medio: al final del todo quedaban lejos de las
 * columnas que comparan — con cuatro escenarios había que cruzar la tabla
 * entera para leer el delta de la 1 contra la 2.
 *
 * Los usan el P&L completo y el Estado de Resultados.
 *
 * Devuelve `null` si esa ranura no tiene columna: entonces no se declara la
 * fórmula y queda el número, que al menos se puede revisar.
 */
export function colDeRanuraPartida(
  usadas: Ranura[], trasVariacion: number, i: number,
): number | null {
  const q = usadas.findIndex(u => u.i === i);
  return q < 0 ? null : (q < trasVariacion ? 1 + q : 3 + q);
}

/**
 * Cuadros con las dos columnas de variación **al final**:
 *
 * ```
 * 0          1 … U       1+U      2+U
 * [rótulo] [ranuras]  [Var $] [Var %]
 * ```
 *
 * Los usan las aperturas por departamento —ingreso, planilla, costo, opex y
 * propiedad—, donde no hay corte en el medio y la posición es `1 + q`.
 */
export function colDeRanuraAlFinal(
  usadas: Ranura[], i: number,
): number | null {
  const q = usadas.findIndex(u => u.i === i);
  return q < 0 ? null : 1 + q;
}

/**
 * Dónde se insertan las dos columnas de variación: justo después de la última
 * de las dos ranuras comparadas.
 *
 * ⚠️ Es la MISMA cuenta que hace la pantalla para dibujar la cabecera. Si la
 * fórmula usara una y el dibujo otra, la variación apuntaría a dos columnas que
 * no son las suyas.
 */
export function trasVariacionDe(
  usadas: Ranura[], varA: number, varB: number,
): number {
  const pos = usadas.findIndex(u => u.i === Math.max(varA, varB));
  return pos < 0 ? usadas.length : pos + 1;
}
