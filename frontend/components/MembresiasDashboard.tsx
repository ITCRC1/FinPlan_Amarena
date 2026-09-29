"use client";
import { useCallback, useEffect, useState } from "react";

import { getMembresias, type MembresiasAnio, type Scenario } from "@/lib/api";
import {
  bajarElAnio, MembresiasAnioPie, MembresiasAnioTabla,
} from "@/components/MembresiasAnioTabla";

/**
 * Las membresías del club al pie del Dashboard — sólo lectura.
 *
 * Owner, 2026-09-29: *«puedes llevarte una copia de este cuadro ya depurado al
 * dashboard al final como parte de las estadisticas. que esten
 * sincronizado… cualquier cambio alla que se actualice automaticamente»*.
 *
 * ## Cómo se mantiene sincronizado
 *
 * No hay copia del dato: los dos leen `GET /membresias/`. Y no hay copia del
 * cuadro tampoco — la tabla y el Excel salen de `MembresiasAnioTabla`, que es
 * la única definición. Dos copias del mismo cuadro empiezan iguales y se
 * separan en el primer arreglo que alguien hace de un lado.
 *
 * Además se vuelve a pedir el año **cuando la pestaña recupera el foco**: es
 * el caso real de «cualquier cambio allá» — editar en Cierre de Mes y volver
 * acá, con las dos pantallas abiertas. Sin eso habría que recargar a mano,
 * que es justo lo que el pedido evita.
 *
 * ## ⚠️ Acá no se edita
 *
 * El conteo se carga en **Cierre de Mes · Membresías**, y punto. Dos lugares
 * donde escribir el mismo dato es cómo terminan conviviendo dos verdades.
 */
export default function MembresiasDashboard({ scenarioId, scenarios }: {
  scenarioId: string;
  scenarios: Scenario[];
}) {
  const [anio, setAnio] = useState<MembresiasAnio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState(true);

  /** Mismo criterio que los otros bloques del Dashboard: el principal
   *  primero, y si no tiene nada, el ACTUAL del mismo año — el Dashboard abre
   *  con el Budget y el conteo vive en el ACTUAL. */
  const cargar = useCallback(async () => {
    if (!scenarioId) { setAnio(null); return; }
    const principal = scenarios.find(s => s.id === scenarioId);
    const ids = [scenarioId, ...scenarios
      .filter(s => s.type === "ACTUAL" && s.id !== scenarioId
        && (!principal || s.year === principal.year)).map(s => s.id)];
    let ultimo: MembresiasAnio | null = null;
    for (const id of ids) {
      try {
        const r = await getMembresias(id);
        ultimo = ultimo ?? r;
        if (r.meses_cargados.length) { setAnio(r); setError(null); return; }
      } catch (e) {
        if (id === scenarioId) setError(e instanceof Error ? e.message : "error");
      }
    }
    setAnio(ultimo);
  }, [scenarioId, scenarios]);

  useEffect(() => { cargar(); }, [cargar]);

  // ⚠️ Al volver a la pestaña se vuelve a pedir. Es lo que hace que «cualquier
  // cambio allá» se vea acá sin recargar: se edita en el cierre, se vuelve, y
  // el cuadro ya está al día.
  useEffect(() => {
    const alVolver = () => { if (!document.hidden) cargar(); };
    window.addEventListener("focus", alVolver);
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      window.removeEventListener("focus", alVolver);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [cargar]);

  if (!scenarioId) return null;

  const cuerpo = () => {
    if (error) return <P tono="err">No se pudo leer las membresías: {error}</P>;
    if (!anio) return <P>Cargando las membresías…</P>;
    if (!anio.meses_cargados.length) {
      return <P>
        Todavía no hay ningún mes contado para {anio.year}. Se carga en{" "}
        <b>Cierre de Mes · Estadística de habitaciones · Membresías</b>.
      </P>;
    }
    return (
      <>
        <div style={{ padding: "10px 16px 0" }}><MembresiasAnioPie anio={anio} /></div>
        <div style={{ padding: "8px 16px 14px" }}>
          <MembresiasAnioTabla anio={anio} />
        </div>
        <div style={{ padding: "8px 16px", fontSize: 11, lineHeight: 1.5,
                      color: "var(--text-secondary)",
                      borderTop: "1px solid var(--border-subtle)" }}>
          Se carga en <b>Cierre de Mes · Estadística de habitaciones ·
          Membresías</b>; acá es sólo lectura y se actualiza solo al volver a
          esta pestaña. Las columnas en blanco son meses sin contar, no meses
          en cero.
        </div>
      </>
    );
  };

  return (
    <div style={{ marginTop: 16, background: "var(--bg-elevated)",
                  border: "1px solid var(--border-medium)", borderRadius: 8,
                  overflow: "hidden" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-medium)",
                    background: "rgba(36,83,196,.06)", display: "flex",
                    alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 230 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>
            Membresías del club · cuota de mantenimiento
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
            {anio ? anio.escenario : "Conteo del cobro por mes"}
          </div>
        </div>
        {anio && anio.meses_cargados.length > 0 && (
          <button onClick={() => bajarElAnio(anio).catch(e =>
                    setError(e instanceof Error ? e.message : "No se pudo bajar"))}
            style={{ padding: "5px 12px", fontSize: 12, fontWeight: 600,
                     borderRadius: 5, border: "none", cursor: "pointer",
                     background: "var(--accent-excel)", color: "#fff" }}>
            ⬇ Excel
          </button>
        )}
        <button onClick={() => setAbierto(a => !a)}
          style={{ padding: "4px 10px", fontSize: 11.5, cursor: "pointer",
                   borderRadius: 4, border: "1px solid var(--border-medium)",
                   background: "transparent", color: "var(--text-secondary)" }}>
          {abierto ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      {abierto && cuerpo()}
    </div>
  );
}

function P({ children, tono }: { children: React.ReactNode; tono?: "err" }) {
  return <p style={{ margin: 0, padding: "14px 16px", fontSize: 12.5,
                     color: tono === "err" ? "var(--negative)" : "var(--text-secondary)" }}>
    {children}
  </p>;
}
