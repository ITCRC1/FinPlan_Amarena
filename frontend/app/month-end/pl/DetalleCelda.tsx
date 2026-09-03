"use client";
/**
 * De qué está hecha una celda del cuadro, sin salir de la pantalla.
 *
 * Owner, 2026-09-03: *«¿será posible que se pueda hacer link? Toco la línea de
 * Rooms Revenue y me abre el detalle, sin ir… si abro payroll de Rooms se me
 * despliegan los GL que suman eso, como un cuadro sin salir a la otra ventana…
 * así voy presentando y puedo ver los detalles de una vez»*.
 *
 * **Está pensado para presentar.** Por eso abre encima y se cierra con Escape o
 * tocando afuera: en una reunión, irse a otra pantalla y volver cuesta el hilo
 * de lo que se estaba diciendo.
 *
 * ## Las tres versiones, cuenta por cuenta
 *
 * Cada fila es una cuenta del mayor y cada columna una versión, así que la
 * comparación es cuenta contra cuenta. El corte —mes o acumulado— es el mismo
 * que el del cuadro de atrás: si el cuadro dice julio, esto dice julio.
 *
 * ⚠️ **Un presupuesto no tiene el mayor CARGADO, pero sí está amarrado a él**
 * (owner: «el presupuesto debe tener GL, siempre debe estar conectado a un
 * GL»): cada línea del checkbook lleva su cuenta y los conceptos de planilla
 * SON cuentas. Lo que cambia es la tabla de donde sale, y por eso cada columna
 * dice su `fuente` — mezclarlas sin decirlo sería peor que no mostrarlas.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getDetalleDeCelda, type DetalleCelda as Datos } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "4px 10px", textAlign: "right", fontSize: 12, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "4px 10px", fontSize: 12 };

export interface Celda {
  clase: string;
  /** Departamento, cuenta o línea. Vacío = la clase entera. */
  clave: string;
  titulo: string;
}

export default function DetalleCelda({ celda, scenarioIds, mes, horizonte, onCerrar }: {
  celda: Celda;
  scenarioIds: string[];
  mes: number;
  horizonte: "month" | "ytd" | "full";
  onCerrar: () => void;
}) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    setDatos(null); setError(null);
    getDetalleDeCelda(scenarioIds, celda.clase, celda.clave)
      .then(d => { if (vivo) setDatos(d); })
      .catch(e => { if (vivo) setError(e instanceof Error ? e.message : "No se pudo cargar"); });
    return () => { vivo = false; };
  }, [scenarioIds, celda.clase, celda.clave]);

  // Escape cierra. En una presentación, buscar la X con el mouse se nota.
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onCerrar]);

  /** Los meses del corte, LOS MISMOS que el cuadro de atrás.
   *
   *  ⚠️ Si acá se sumara el año entero mientras el cuadro muestra julio, los
   *  números no cerrarían con la celda que se tocó — y el desplegable existe
   *  justamente para explicar esa celda. */
  const meses = useMemo(() => {
    if (horizonte === "month") return [mes - 1];
    if (horizonte === "ytd") return Array.from({ length: mes }, (_, i) => i);
    return Array.from({ length: 12 }, (_, i) => i);
  }, [horizonte, mes]);

  const suma = useCallback((serie: number[] | undefined) =>
    (serie ?? []).reduce((a, i, idx) => meses.includes(idx) ? a + i : a, 0),
  [meses]);

  const versiones = datos?.versiones ?? [];
  const filas = useMemo(() => {
    const f = (datos?.filas ?? []).map(x => ({
      ...x, total: versiones.reduce((a, v) => a + Math.abs(suma(x.series[v.scenario_id])), 0),
    }));
    // Lo más grande primero: en una presentación, lo que explica el número
    // tiene que estar arriba y no a diez filas de distancia.
    return f.filter(x => x.total >= 0.005).sort((a, b) => b.total - a.total);
  }, [datos, versiones, suma]);

  const rotuloCorte = horizonte === "month" ? `${MESES[mes - 1]}`
    : horizonte === "ytd" ? `YTD ${MESES[mes - 1]}` : "Año completo";

  return (
    <div
      onClick={onCerrar}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(15,20,28,0.55)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}>
      {/* ⚠️ `stopPropagation`: sin esto, tocar DENTRO del cuadro lo cierra —
          incluido el gesto de seleccionar un número para copiarlo. */}
      <div onClick={e => e.stopPropagation()} style={{
        background: "var(--bg-surface)", borderRadius: 12,
        border: "1px solid var(--border-medium)",
        boxShadow: "0 18px 50px rgba(0,0,0,0.35)",
        maxWidth: 1080, width: "100%", maxHeight: "86vh",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{
          padding: "13px 18px", borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap",
        }}>
          <b style={{ fontSize: 14.5 }}>{celda.titulo}</b>
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {datos?.rotulo} · {rotuloCorte}
          </span>
          <button onClick={onCerrar} title="Cerrar (Esc)" style={{
            marginLeft: "auto", border: "none", background: "transparent",
            fontSize: 20, cursor: "pointer", color: "var(--text-secondary)",
            lineHeight: 1,
          }}>×</button>
        </div>

        <div style={{ padding: "12px 18px 18px", overflow: "auto" }}>
          {!datos && !error && (
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>cargando…</p>
          )}
          {error && <p style={{ fontSize: 12.5, color: "var(--negative)" }}>{error}</p>}

          {datos && (
            <>
              <div className="fin-scroll-x">
                <table style={{ borderCollapse: "collapse", minWidth: 520, width: "100%" }}>
                  <thead>
                    <tr>
                      <th style={{ ...TDL, textAlign: "left", fontWeight: 800,
                                   position: "static",
                                   borderBottom: "2px solid var(--text-primary)" }}>
                        Cuenta
                      </th>
                      {versiones.map(v => (
                        <th key={v.scenario_id} style={{
                          ...TD, fontWeight: 800, position: "static",
                          borderBottom: "2px solid var(--text-primary)",
                        }}>
                          {v.escenario}
                          <div style={{ fontWeight: 400, fontSize: 10,
                                        color: "var(--text-secondary)" }}>
                            {v.fuente}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filas.map(f => (
                      <tr key={f.cuenta}>
                        <td style={TDL}>
                          <span className="mono" style={{ color: "var(--text-secondary)",
                                                          marginRight: 7 }}>
                            {f.cuenta}
                          </span>
                          {f.nombre}
                        </td>
                        {versiones.map(v => {
                          const x = suma(f.series[v.scenario_id]);
                          return (
                            <td key={v.scenario_id} className="mono" style={{
                              ...TD, color: x < 0 ? "var(--negative)" : undefined,
                            }}>{usd(x)}</td>
                          );
                        })}
                      </tr>
                    ))}
                    {/* El total tiene que dar EXACTAMENTE la celda que se tocó.
                        Si no da, el desplegable está explicando otra cosa. */}
                    <tr style={{ background: "var(--bg-elevated, #EDF1F5)" }}>
                      <td style={{ ...TDL, fontWeight: 800,
                                   borderTop: "2px solid var(--text-primary)" }}>
                        TOTAL
                      </td>
                      {versiones.map(v => {
                        const x = filas.reduce(
                          (a, f) => a + suma(f.series[v.scenario_id]), 0);
                        return (
                          <td key={v.scenario_id} className="mono" style={{
                            ...TD, fontWeight: 800,
                            borderTop: "2px solid var(--text-primary)",
                            color: x < 0 ? "var(--negative)" : undefined,
                          }}>{usd(x)}</td>
                        );
                      })}
                    </tr>
                    {!filas.length && (
                      <tr><td colSpan={versiones.length + 1}
                              style={{ ...TDL, color: "var(--text-secondary)" }}>
                        No hay detalle por cuenta para este corte.
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {versiones.some(v => v.agregado) && (
                <p style={{ fontSize: 11.5, color: "var(--text-secondary)",
                            marginTop: 10, lineHeight: 1.6 }}>
                  ⚠️ En las versiones marcadas <b>Auxiliar</b>, el ingreso se
                  presupuesta por <b>línea</b> y algunas líneas agrupan varias
                  cuentas del mayor —<code>ROOMS</code> son la 4000, la 4001 y
                  la 4002—. Esa fila sale con el nombre de la línea y no con una
                  cuenta: elegir una de las que agrupa sería inventarla.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
