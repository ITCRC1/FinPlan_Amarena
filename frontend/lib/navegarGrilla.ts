/**
 * Moverse por una grilla con el teclado, como en Excel.
 *
 * Owner, 2026-11-11, sobre el checkbook de OPEX: *«para editar hacer un
 * proceso extraño… debería dejar editar todo»*.
 *
 * Sin esto hay que hacer **clic en cada celda** para poder escribirla. En una
 * tabla de 352 filas por doce meses eso no es una molestia: es la diferencia
 * entre cargar un presupuesto y no cargarlo.
 *
 * Vive en `lib/` por la misma razón que `pegarGrilla.ts`: toda grilla de la
 * app debería moverse igual, y resolverlo pantalla por pantalla es cómo se
 * llegó a que cada tabla se comporte distinto.
 *
 * ## Cómo se direcciona una celda
 *
 * Por atributos en el DOM y no por índices en React. Una grilla de checkbook
 * intercala filas que NO son celdas —subtotales, totales, cabeceras de
 * cuenta— y además esconde los meses ya cerrados. Numerar las celdas en el
 * componente obliga a que esas excepciones se repitan acá; leerlas del DOM
 * hace que **lo que no está, simplemente no se visita**.
 */

/** La fila a la que pertenece la celda. Suele ser el id de la línea. */
export const ATTR_FILA = "data-gfila";
/** La columna, 0..n. En un checkbook, el mes. */
export const ATTR_COL = "data-gcol";

export type Rumbo = "izq" | "der" | "arriba" | "abajo";

/** Las flechas y el tabulador, traducidos a un rumbo. `null` si la tecla no mueve. */
export function rumboDeTecla(key: string, shift = false): Rumbo | null {
  switch (key) {
    case "ArrowLeft":  return "izq";
    case "ArrowRight": return "der";
    case "ArrowUp":    return "arriba";
    case "ArrowDown":  return "abajo";
    case "Tab":        return shift ? "izq" : "der";
    default:           return null;
  }
}

/**
 * Lleva el foco a la celda vecina. Devuelve `true` si había una.
 *
 * Horizontal: dentro de la MISMA fila. Si el mes de al lado está cerrado no
 * existe como celda, así que el foco no se mueve — y eso es correcto: una
 * celda cerrada no se edita, y saltársela en silencio haría escribir dos
 * meses más allá de donde el usuario cree que está.
 *
 * Vertical: la siguiente celda de la misma columna **en orden del documento**,
 * lo que cruza de cuenta en cuenta saltando subtotales sin saber que existen.
 */
export function moverFoco(desde: HTMLElement, rumbo: Rumbo): boolean {
  const grilla = desde.closest("table");
  if (!grilla) return false;

  const fila = desde.getAttribute(ATTR_FILA);
  const col = Number(desde.getAttribute(ATTR_COL));
  if (fila === null || !Number.isFinite(col)) return false;

  if (rumbo === "izq" || rumbo === "der") {
    const destino = col + (rumbo === "der" ? 1 : -1);
    const cel = grilla.querySelector<HTMLElement>(
      `[${ATTR_FILA}="${CSS.escape(fila)}"][${ATTR_COL}="${destino}"]`,
    );
    if (!cel) return false;
    cel.focus();
    return true;
  }

  // Arriba / abajo: toda la columna, en el orden en que está dibujada.
  const columna = Array.from(
    grilla.querySelectorAll<HTMLElement>(`[${ATTR_COL}="${col}"]`),
  );
  const i = columna.indexOf(desde);
  const destino = columna[i + (rumbo === "abajo" ? 1 : -1)];
  if (i < 0 || !destino) return false;
  destino.focus();
  return true;
}

/**
 * ¿Esta tecla debería abrir el editor y empezar a escribir?
 *
 * Un dígito, un signo menos, un punto o una coma: en Excel uno se para en la
 * celda y teclea. Las combinaciones con Ctrl/Alt/Meta quedan afuera — `Ctrl+V`
 * es pegar, no escribir una «v».
 */
export function tecleaUnNumero(e: {
  key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean;
}): boolean {
  if (e.ctrlKey || e.metaKey || e.altKey) return false;
  return e.key.length === 1 && /[0-9.,\-]/.test(e.key);
}
