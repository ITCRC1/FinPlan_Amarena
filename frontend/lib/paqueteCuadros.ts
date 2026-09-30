/**
 * Qué capítulos entran en el paquete que se baja, y en qué orden.
 *
 * Owner, 2026-09-30: *«ocupo una opción para escoger qué tabs y en qué orden
 * van en el paquete de excel que se baja»* y, enseguida, *«tengo muchas tabs
 * que no necesito porque se repiten»*.
 *
 * ## Dos decisiones distintas, y por eso dos lugares
 *
 * | | dónde vive | qué gobierna |
 * |---|---|---|
 * | **Qué se ve** | `tab_enablement`, en la base | la pantalla, para todo el hotel |
 * | **Qué se baja** | acá, en el navegador | el archivo, para quien lo arma |
 *
 * Esconder un sub-tab es una decisión de la propiedad —la toma quien administra
 * y la ven todos—. Armar un paquete es de quien lo manda esa vez: el archivo
 * para la junta no lleva las mismas hojas que el que se revisa de puertas
 * adentro. Meter lo segundo en `tab_enablement` obligaría a apagar un reporte
 * para todos con tal de sacarlo de un Excel.
 *
 * ⚠️ **Pero lo escondido no se baja.** Un sub-tab que la propiedad apagó no
 * puede aparecer en el archivo: sería la pantalla diciendo una cosa y el
 * adjunto otra. El Word ya lo respetaba y el Excel no — de ahí las hojas
 * repetidas que el owner venía borrando a mano.
 *
 * ## El default es TODO lo visible, en el orden de la pantalla
 *
 * Sin elección guardada baja lo mismo que bajaba antes. Un default vacío haría
 * que el botón dejara de funcionar el día que esto se despliega, y nadie sabría
 * por qué.
 */

const LLAVE = "finplan.paquete.cuadros";

export interface Paquete {
  /** Las claves EXCLUIDAS a mano. Se guarda lo apagado y no lo prendido, para
   *  que un capítulo nuevo nazca adentro: al revés, se construye un reporte y
   *  no sale en ningún archivo hasta que alguien se acuerde de prenderlo. */
  fuera: string[];
  /** El orden elegido. Las claves que no estén acá van después, en el orden de
   *  la pantalla — así una vista nueva no desaparece ni se cuela primero. */
  orden: string[];
}

const VACIO: Paquete = { fuera: [], orden: [] };

export function leerPaquete(hotel: string): Paquete {
  try {
    const crudo = localStorage.getItem(`${LLAVE}.${hotel}`);
    if (!crudo) return VACIO;
    const p = JSON.parse(crudo);
    return {
      fuera: Array.isArray(p?.fuera) ? p.fuera.filter((x: unknown) => typeof x === "string") : [],
      orden: Array.isArray(p?.orden) ? p.orden.filter((x: unknown) => typeof x === "string") : [],
    };
  } catch {
    // Un `localStorage` bloqueado o con basura no puede dejar sin archivo: se
    // vuelve al default, que es todo lo visible.
    return VACIO;
  }
}

export function guardarPaquete(hotel: string, p: Paquete): void {
  try {
    localStorage.setItem(`${LLAVE}.${hotel}`, JSON.stringify(p));
  } catch { /* sin guardar, la elección vale para esta sesión y nada más */ }
}

/**
 * Los capítulos que entran, ya ordenados.
 *
 * @param vistas   todas las claves, en el orden de la pantalla
 * @param ocultos  las que la propiedad escondió (`tab_enablement`)
 * @param tiene    si esa clave sabe armar un cuadro
 */
export function capitulosDelPaquete(
  vistas: readonly string[], ocultos: readonly string[], p: Paquete,
  tiene: (k: string) => boolean,
): string[] {
  const dentro = vistas.filter(k =>
    tiene(k) && !ocultos.includes(k) && !p.fuera.includes(k));
  // ⚠️ Primero las que el usuario ordenó, y DESPUÉS el resto en el orden de la
  // pantalla. Si sólo se respetara `orden`, una vista nueva no saldría en
  // ningún archivo hasta que alguien volviera a abrir el panel.
  const puestas = p.orden.filter(k => dentro.includes(k));
  return [...puestas, ...dentro.filter(k => !puestas.includes(k))];
}

/** Mover una clave un lugar arriba o abajo dentro de la lista visible. */
export function mover(orden: string[], clave: string, paso: -1 | 1): string[] {
  const i = orden.indexOf(clave);
  const j = i + paso;
  if (i < 0 || j < 0 || j >= orden.length) return orden;
  const out = [...orden];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}
