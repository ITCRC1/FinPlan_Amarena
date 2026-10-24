"use client";
/**
 * El P&L USALI del cierre — el cuadro en español, con el detalle por cuenta.
 *
 * Owner, 2026-10-23, entregando `AMAREANA SEPTEMBER 2026 ACTUAL VERSUS
 * FORECAST.xlsx`: *«necesito que construyas el tab llamado P&L USALI SEPT, tal
 * cual; métemelo acá en cierre de mes como un sub tab más»*.
 *
 * ## Qué lo distingue de los cuadros que ya existían
 *
 * | | qué muestra |
 * |---|---|
 * | `P&L Statement` | la cascada del owner, en inglés, hasta el renglón |
 * | `Formato` | la misma cascada, mes a mes |
 * | **este** | la cascada en USALI **y las cuentas que la forman** |
 *
 * El detalle cuenta por cuenta ya se podía ver, pero **de a una celda por vez**:
 * había que tocar cada departamento y leer el panel. Acá está todo junto, que
 * es como el owner lo arma a mano para los dueños.
 *
 * ## ⚠️ Los montos NO se calculan acá
 *
 * El resumen viene reagrupado de las mismas líneas del P&L; el detalle, del
 * mismo mayor que alimenta el panel de celda. Si este cuadro recalculara la
 * cascada por su cuenta, el hotel tendría dos P&L que cuadran por dentro y no
 * entre sí — y el día que se separen, los dos van a seguir pareciendo
 * correctos. Por eso el bloque **CONTROL** está a la vista y no escondido.
 */
import { sembrarTres } from "@/lib/escenarioPreferido";
import { useCallback, useEffect, useState } from "react";

import { getPLUsali, type PLUsali, type PLUsaliDepto,
         type Scenario } from "@/lib/api";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const pct = (n: number) => (n ? (n * 100).toFixed(1) + "%" : "—");

const SEL: React.CSSProperties = {
  padding: "5px 9px", fontSize: 12, borderRadius: 5,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};

const TD: React.CSSProperties = {
  padding: "3px 9px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "3px 9px", fontSize: 11.5 };

const AMBITOS = [
  { id: "consolidado", rotulo: "Consolidado" },
  { id: "hotel", rotulo: "Hotel" },
  { id: "club", rotulo: "Club Madresal" },
];

/** El orden en que el owner lee el resumen. */
const BLOQUES = ["ingresos", "gastos_dept", "utilidad_dept", "no_distribuidos"];

export default function PLUsali({ escenarios, inicial, mes }: {
  escenarios: Scenario[];
  inicial?: string;
  /** El mes que se está cerrando, 1-12. */
  mes: number;
}) {
  const [scenarioId, setScenarioId] = useState<string>(inicial || "");
  const [ambito, setAmbito] = useState("consolidado");
  const [datos, setDatos] = useState<PLUsali | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (scenarioId || !escenarios.length) return;
    // El cierre se mira contra el ACTUAL; si la propiedad todavia no tiene uno,
    // cae en el primero que haya en vez de quedarse sin seleccion.
    const tres = sembrarTres(escenarios);
    setScenarioId(inicial || tres.actual || escenarios[0].id);
  }, [escenarios, inicial, scenarioId]);

  const cargar = useCallback(() => {
    if (!scenarioId) return;
    setCargando(true); setError(null);
    getPLUsali(scenarioId, mes, ambito)
      .then(setDatos)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudo cargar"))
      .finally(() => setCargando(false));
  }, [scenarioId, mes, ambito]);

  useEffect(() => { cargar(); }, [cargar]);

  if (!escenarios.length) return null;

  const operativos = (datos?.departamentos ?? []).filter(d => d.kind !== "OVERHEAD");
  const overhead = (datos?.departamentos ?? []).filter(d => d.kind === "OVERHEAD");
  const descuadra = !!datos
    && (Math.abs(datos.control.ingresos_dif) > 0.01
        || Math.abs(datos.control.gastos_dif) > 0.01);

  return (
    <div>
      {/* ── Encabezado ────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 9, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 12 }}>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
                style={SEL} aria-label="Versión">
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>
              {s.type} · {s.version} · {s.year}
            </option>
          ))}
        </select>
        <select value={ambito} onChange={e => setAmbito(e.target.value)}
                style={SEL} aria-label="Ámbito">
          {AMBITOS.map(a => <option key={a.id} value={a.id}>{a.rotulo}</option>)}
        </select>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          {mes ? `${MESES[mes - 1]} ${datos?.year ?? ""}` : "Año completo"}
          {" · cifras en USD"}
        </span>
        {cargando && <span style={{ fontSize: 11.5,
                                    color: "var(--text-secondary)" }}>Cargando…</span>}
      </div>

      {error && (
        <div style={{ padding: "8px 13px", fontSize: 12.5, borderRadius: 5,
                      background: "var(--bg-surface)",
                      borderLeft: "3px solid var(--negative)" }}>{error}</div>
      )}

      {datos && (
        <>
          {/* ── CONTROL: arriba, no escondido ────────────────────────────
              Los dos lados salen de orígenes distintos —el resumen de las
              líneas del P&L, el detalle del mayor—. Mientras cuadren esto es
              una línea gris; el día que no, es lo primero que se ve. */}
          <div style={{ marginBottom: 14, padding: "7px 12px", fontSize: 11.5,
                        borderRadius: 5, background: "var(--bg-surface)",
                        borderLeft: `3px solid ${descuadra
                          ? "var(--negative)" : "var(--positive)"}` }}>
            {descuadra ? <b>⚠️ El resumen y el detalle no cuadran. </b>
                       : <b>Resumen y detalle cuadran. </b>}
            Ingresos {usd(datos.control.ingresos_resumen)} vs{" "}
            {usd(datos.control.ingresos_detalle)}
            {" "}(dif. {usd(datos.control.ingresos_dif)}) · Gastos{" "}
            {usd(datos.control.gastos_resumen)} vs {usd(datos.control.gastos_detalle)}
            {" "}(dif. {usd(datos.control.gastos_dif)}).
          </div>

          {/* ── RESUMEN ──────────────────────────────────────────────── */}
          <Cuadro titulo="RESUMEN DEL P&L (USALI)">
            {BLOQUES.map(k => {
              const b = datos.resumen[k];
              if (!b) return null;
              return (
                <tbody key={k}>
                  <Seccion texto={b.titulo} />
                  {b.filas.map(f => (
                    <tr key={f.code}>
                      <td style={{ ...TDL, paddingLeft: 24 }}>{f.rotulo}</td>
                      <td className="mono" style={TD}>{usd(f.monto)}</td>
                      <td className="mono" style={{ ...TD, width: 70,
                                color: "var(--text-secondary)" }}>{pct(f.pct)}</td>
                    </tr>
                  ))}
                  <Total texto={`TOTAL ${b.titulo}`} monto={b.total} pct={b.pct} />
                </tbody>
              );
            })}
            <tbody>
              <tr><td colSpan={3} style={{ height: 10 }} /></tr>
              {datos.cascada.map(c => {
                const fuerte = c.rotulo === c.rotulo.toUpperCase();
                return (
                  <tr key={c.code}>
                    <td style={{ ...TDL, paddingLeft: fuerte ? 9 : 24,
                                 fontWeight: fuerte ? 700 : 400,
                                 borderTop: fuerte ? "1px solid var(--border-medium)" : undefined }}>
                      {c.rotulo}
                    </td>
                    <td className="mono" style={{ ...TD, fontWeight: fuerte ? 700 : 400,
                              borderTop: fuerte ? "1px solid var(--border-medium)" : undefined,
                              color: c.monto < 0 ? "var(--negative)" : undefined }}>
                      {usd(c.monto)}
                    </td>
                    <td className="mono" style={{ ...TD, color: "var(--text-secondary)",
                              borderTop: fuerte ? "1px solid var(--border-medium)" : undefined }}>
                      {pct(c.pct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Cuadro>

          {/* ── DETALLE POR DEPARTAMENTO ─────────────────────────────── */}
          <h3 style={{ fontSize: 13, fontWeight: 700, margin: "20px 0 8px" }}>
            DETALLE POR DEPARTAMENTO
          </h3>
          {!!operativos.length && (
            <Rotulo texto="DEPARTAMENTOS OPERATIVOS" />
          )}
          {operativos.map(d => <Depto key={d.dept_code} d={d} />)}
          {!!overhead.length && <Rotulo texto="GASTOS NO DISTRIBUIDOS" />}
          {overhead.map(d => <Depto key={d.dept_code} d={d} />)}
        </>
      )}
    </div>
  );
}

function Cuadro({ titulo, children }: {
  titulo: string; children: React.ReactNode;
}) {
  return (
    <div style={{ border: "1px solid var(--border-medium)", borderRadius: 7,
                  overflow: "hidden", background: "var(--bg-surface)" }}>
      <div style={{ padding: "7px 11px", fontSize: 12.5, fontWeight: 700,
                    background: "var(--bg-elevated)",
                    borderBottom: "1px solid var(--border-medium)" }}>
        {titulo}
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <colgroup>
          <col /><col style={{ width: 150 }} /><col style={{ width: 80 }} />
        </colgroup>
        {children}
      </table>
    </div>
  );
}

function Seccion({ texto }: { texto: string }) {
  return (
    <tr>
      <td colSpan={3} style={{ padding: "7px 9px 3px", fontSize: 11,
                               fontWeight: 700, letterSpacing: ".03em",
                               color: "var(--text-secondary)" }}>{texto}</td>
    </tr>
  );
}

function Total({ texto, monto, pct: p }: {
  texto: string; monto: number; pct: number;
}) {
  return (
    <tr>
      <td style={{ ...TDL, fontWeight: 700,
                   borderTop: "1px solid var(--border-subtle)" }}>{texto}</td>
      <td className="mono" style={{ ...TD, fontWeight: 700,
                borderTop: "1px solid var(--border-subtle)",
                color: monto < 0 ? "var(--negative)" : undefined }}>{usd(monto)}</td>
      <td className="mono" style={{ ...TD, fontWeight: 700,
                borderTop: "1px solid var(--border-subtle)",
                color: "var(--text-secondary)" }}>{pct(p)}</td>
    </tr>
  );
}

function Rotulo({ texto }: { texto: string }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".04em",
                  color: "var(--text-secondary)", margin: "14px 0 6px" }}>
      {texto}
    </div>
  );
}

/** Un departamento con sus secciones y sus cuentas. */
function Depto({ d }: { d: PLUsaliDepto }) {
  return (
    <div style={{ marginBottom: 12, border: "1px solid var(--border-medium)",
                  borderRadius: 7, overflow: "hidden",
                  background: "var(--bg-surface)" }}>
      <div style={{ padding: "6px 11px", fontSize: 12, fontWeight: 700,
                    background: "var(--bg-elevated)",
                    borderBottom: "1px solid var(--border-medium)",
                    display: "flex", justifyContent: "space-between", gap: 10 }}>
        <span>{d.dept_code} · {d.dept_name}</span>
        <span className="mono" style={{ fontWeight: 400,
                  color: "var(--text-secondary)" }}>
          gasto {usd(d.gasto)}
          {d.ingreso ? ` · utilidad ${usd(d.utilidad)}` : ""}
        </span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse",
                      tableLayout: "fixed" }}>
        <colgroup>
          <col style={{ width: 70 }} /><col />
          <col style={{ width: 140 }} /><col style={{ width: 70 }} />
        </colgroup>
        {d.secciones.map(s => (
          <tbody key={s.clase}>
            <tr>
              <td colSpan={4} style={{ padding: "6px 9px 2px", fontSize: 10.5,
                        fontWeight: 700, letterSpacing: ".03em",
                        color: "var(--text-secondary)" }}>{s.titulo}</td>
            </tr>
            {s.filas.map(f => (
              <tr key={s.clase + f.cuenta}>
                <td className="mono" style={{ ...TDL,
                          color: "var(--text-secondary)" }}>{f.cuenta}</td>
                <td style={TDL} title={f.nombre}>{f.nombre || "—"}</td>
                <td className="mono" style={TD}>{usd(f.monto)}</td>
                <td className="mono" style={{ ...TD,
                          color: "var(--text-secondary)" }}>{pct(f.pct)}</td>
              </tr>
            ))}
            <tr>
              <td />
              <td style={{ ...TDL, fontWeight: 600,
                        borderTop: "1px solid var(--border-subtle)" }}>
                Total {s.titulo.toLowerCase()}
              </td>
              <td className="mono" style={{ ...TD, fontWeight: 600,
                        borderTop: "1px solid var(--border-subtle)" }}>
                {usd(s.total)}
              </td>
              <td className="mono" style={{ ...TD, fontWeight: 600,
                        borderTop: "1px solid var(--border-subtle)",
                        color: "var(--text-secondary)" }}>{pct(s.pct)}</td>
            </tr>
          </tbody>
        ))}
      </table>
    </div>
  );
}
