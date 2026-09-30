"use client";
/**
 * El panel para armar el paquete: qué hojas bajan y en qué orden.
 *
 * Owner, 2026-09-30: *«ocupo una opción para escoger qué tabs y en qué orden
 * van en el paquete de excel que se baja»* · *«tengo muchas tabs que no
 * necesito porque se repiten»*.
 *
 * ⚠️ **Lo que la propiedad escondió no aparece acá.** No es que esté apagado y
 * se pueda prender: no es una opción del paquete. Mostrarlo daría a entender
 * que se puede meter en el archivo un reporte que la pantalla no muestra.
 *
 * La elección vive en el navegador (`lib/paqueteCuadros`) y no en la base: es
 * de quien arma el archivo esa vez, no de la propiedad.
 */
import { useEffect, useState } from "react";

import {
  capitulosDelPaquete, guardarPaquete, leerPaquete, mover, type Paquete,
} from "@/lib/paqueteCuadros";

export default function PaqueteCuadros({ vistas, ocultos, tiene, rotulo,
                                         hotel, onCerrar, onCambio }: {
  /** Todas las claves, en el orden de la pantalla. */
  vistas: readonly string[];
  ocultos: readonly string[];
  tiene: (k: string) => boolean;
  rotulo: (k: string) => string;
  hotel: string;
  onCerrar: () => void;
  onCambio: () => void;
}) {
  const [p, setP] = useState<Paquete>({ fuera: [], orden: [] });
  useEffect(() => { setP(leerPaquete(hotel)); }, [hotel]);

  /** Los candidatos: con capítulo y no escondidos por la propiedad. */
  const posibles = vistas.filter(k => tiene(k) && !ocultos.includes(k));
  /** Los elegidos, en su orden — el mismo cálculo que usa la descarga. */
  const dentro = capitulosDelPaquete(vistas, ocultos, p, tiene);
  const lista = [...dentro, ...posibles.filter(k => !dentro.includes(k))];

  function aplicar(nuevo: Paquete) {
    setP(nuevo);
    guardarPaquete(hotel, nuevo);
    onCambio();
  }

  const alternar = (k: string) => aplicar({
    ...p,
    fuera: p.fuera.includes(k) ? p.fuera.filter(x => x !== k) : [...p.fuera, k],
  });

  const correr = (k: string, paso: -1 | 1) => aplicar({
    // ⚠️ Se ordena sobre la lista COMPLETA de candidatos y no sólo sobre los
    // elegidos: si no, apagar uno y volver a prenderlo lo mandaría al final.
    ...p, orden: mover([...lista], k, paso),
  });

  return (
    <div style={{ border: "1px solid var(--border-medium)", borderRadius: 8,
                  background: "var(--bg-surface)", padding: "12px 14px",
                  marginBottom: 12, maxWidth: 560 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                    marginBottom: 8, flexWrap: "wrap" }}>
        <b style={{ fontSize: 13 }}>Qué hojas bajan, y en qué orden</b>
        <button onClick={() => aplicar({ ...p, fuera: [] })} style={CHICO}>
          Todas
        </button>
        <button onClick={() => aplicar({ ...p, fuera: [...posibles] })} style={CHICO}>
          Ninguna
        </button>
        <button onClick={() => aplicar({ fuera: p.fuera, orden: [] })} style={CHICO}>
          Orden original
        </button>
        <button onClick={onCerrar} style={{ ...CHICO, marginLeft: "auto" }}>
          Cerrar
        </button>
      </div>

      <div style={{ maxHeight: 320, overflowY: "auto" }}>
        {lista.map((k, i) => {
          const puesto = !p.fuera.includes(k);
          return (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 8,
                                  padding: "3px 2px", fontSize: 12.5,
                                  opacity: puesto ? 1 : 0.5 }}>
              <input type="checkbox" checked={puesto} onChange={() => alternar(k)} />
              <span style={{ width: 22, textAlign: "right",
                             color: "var(--text-secondary)", fontSize: 11 }}>
                {puesto ? dentro.indexOf(k) + 1 : "—"}
              </span>
              <span style={{ flex: 1 }}>{rotulo(k)}</span>
              <button onClick={() => correr(k, -1)} disabled={i === 0}
                      style={FLECHA} title="Subir">↑</button>
              <button onClick={() => correr(k, 1)} disabled={i === lista.length - 1}
                      style={FLECHA} title="Bajar">↓</button>
            </div>
          );
        })}
        {!lista.length && (
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0 }}>
            No hay ningún cuadro que bajar con las versiones puestas arriba.
          </p>
        )}
      </div>

      <p style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.5,
                  margin: "9px 0 0" }}>
        Vale para el Excel y para el Word. Se guarda en este navegador, así que
        es tuyo y no cambia lo que ven los demás. Las vistas que la propiedad
        escondió no aparecen acá: para volver a bajarlas hay que mostrarlas en{" "}
        <b>Vistas</b>.
      </p>
    </div>
  );
}

const CHICO: React.CSSProperties = {
  padding: "3px 9px", fontSize: 11.5, borderRadius: 5, cursor: "pointer",
  border: "1px solid var(--border-medium)", background: "transparent",
  color: "var(--text-secondary)",
};
const FLECHA: React.CSSProperties = {
  width: 22, height: 20, fontSize: 11, cursor: "pointer", borderRadius: 4,
  border: "1px solid var(--border-medium)", background: "transparent",
  color: "var(--text-secondary)", lineHeight: 1,
};
