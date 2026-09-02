"use client";
/**
 * La auditoría del detalle: de qué está hecha cada línea del P&L.
 *
 * Owner, 2026-09-02, entregando `p&L auditoria 2026.xlsx`: *«el otro para ver
 * la auditoría de los detalles»*.
 *
 * Tres bloques, que son tres preguntas distintas:
 *
 * 1. **Cuadre** — por cada renglón del P&L, cuánto dice el motor, cuánto suma
 *    su detalle, y la diferencia. Es lo primero porque es lo único que puede
 *    estar MAL; el resto es información.
 * 2. **Detalle** — cuenta por cuenta, agrupado por departamento, con la
 *    naturaleza y el renglón al que cae.
 * 3. **Por departamento** — la matriz Ingresos / Costo / Payroll / Opex /
 *    Reparto / Bajo GOP / Total gasto.
 *
 * ⚠️ **Nada se calcula acá.** La atribución de cada monto a su línea la hace el
 * backend con `pl_engine.linea_de_fila`, que reusa las mismas funciones que
 * arman el P&L. Rehacerla en la pantalla daría una segunda verdad: una
 * auditoría que clasifica distinto que el motor **cuadra consigo misma** y da
 * el visto bueno justo cuando algo está mal.
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import { getAuditoria, type Auditoria as Datos, type AuditoriaFila,
         type Scenario } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const usd = (n: number) =>
  Math.abs(n) < 0.005 ? "—"
    : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "3px 9px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "3px 10px", fontSize: 11.5 };
const TH: React.CSSProperties = {
  ...TD, fontWeight: 700, borderBottom: "1px solid var(--border-medium)",
};

const SEL: React.CSSProperties = {
  padding: "5px 9px", fontSize: 12, borderRadius: 5,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};

function primeroDe(escenarios: Scenario[], tipo: string): string {
  return escenarios.find(s => s.type === tipo)?.id || escenarios[0]?.id || "";
}

export default function Auditoria({ escenarios, inicial, mesInicial = 12, compacto = true }: {
  escenarios: Scenario[];
  inicial?: string;
  mesInicial?: number;
  /** Esconder lo que está en cero. Lo manda la pantalla: el interruptor es uno
   *  solo para todos los sub-tabs. */
  compacto?: boolean;
}) {
  const [scenarioId, setScenarioId] = useState("");
  const [mes, setMes] = useState(mesInicial);
  const [datos, setDatos] = useState<Datos | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Sólo las líneas que NO cuadran. Es el modo en que se usa esta pantalla
   *  cuando ya se sabe que algo falla. */
  const [soloDif, setSoloDif] = useState(false);

  useEffect(() => {
    if (!escenarios.length) return;
    setScenarioId(x => x || inicial || primeroDe(escenarios, "ACTUAL"));
  }, [escenarios, inicial]);

  const cargar = useCallback(async () => {
    if (!scenarioId) return;
    setCargando(true); setError(null);
    try {
      setDatos(await getAuditoria(scenarioId, mes));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar la auditoría");
      setDatos(null);
    } finally { setCargando(false); }
  }, [scenarioId, mes]);

  useEffect(() => { cargar(); }, [cargar]);

  const cuadre = useMemo(() => {
    const filas = datos?.cuadre ?? [];
    if (soloDif) return filas.filter(f => Math.abs(f.dif) >= 0.005);
    // Compacto esconde lo que está en cero por los dos lados: un renglón sin
    // motor y sin detalle no dice nada.
    return compacto
      ? filas.filter(f => Math.abs(f.motor) >= 0.005 || Math.abs(f.detalle) >= 0.005)
      : filas;
  }, [datos, soloDif, compacto]);

  /** El detalle agrupado por departamento, para poder poner subtotales. */
  const porDepto = useMemo(() => {
    const out = new Map<string, { nombre: string; filas: AuditoriaFila[] }>();
    for (const f of datos?.detalle ?? []) {
      const g = out.get(f.dept_code) || { nombre: f.dept_name, filas: [] };
      g.filas.push(f);
      out.set(f.dept_code, g);
    }
    return [...out.entries()];
  }, [datos]);

  const columnas = datos?.columnas ?? [];
  const descuadres = (datos?.cuadre ?? []).filter(f => Math.abs(f.dif) >= 0.005);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 12 }}>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)} style={SEL}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>{s.type} · {s.version} · {s.year}</option>
          ))}
        </select>
        <select value={mes} onChange={e => setMes(Number(e.target.value))} style={SEL}>
          {MESES.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
        </select>
        <button onClick={() => setSoloDif(x => !x)}
          title="Dejar sólo los renglones cuyo detalle no suma lo que dice el motor"
          style={{ ...SEL, cursor: "pointer", fontWeight: 600,
                   background: soloDif ? "var(--brand)" : "var(--bg-surface)",
                   color: soloDif ? "#fff" : "var(--text-secondary)" }}>
          {soloDif ? "☑ Sólo lo que no cuadra" : "☐ Sólo lo que no cuadra"}
        </button>
        {cargando && <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>cargando…</span>}
        {error && <span style={{ fontSize: 12, color: "var(--negative)" }}>{error}</span>}
      </div>

      {/* ── El veredicto, arriba de todo ──────────────────────────────────── */}
      {datos && (
        <div style={{
          padding: "9px 14px", borderRadius: 8, marginBottom: 14, maxWidth: 900,
          border: "1px solid var(--border)",
          borderLeft: `4px solid ${descuadres.length ? "var(--negative)" : "var(--positive)"}`,
          fontSize: 12.5, lineHeight: 1.6, color: "var(--text-secondary)",
        }}>
          {descuadres.length
            ? <><b style={{ color: "var(--negative)" }}>
                {descuadres.length} renglón(es) no cuadran.
              </b>{" "}El detalle no suma lo que dice el P&L. Es lo que hay que revisar.</>
            : <><b style={{ color: "var(--positive)" }}>Todo cuadra.</b>{" "}
                Cada renglón del P&L es exactamente la suma de su detalle.</>}
          {datos.avisos.map((a, i) => (
            <div key={i} style={{ marginTop: 5 }}>· {a}</div>
          ))}
        </div>
      )}

      {/* ── 1. Cuadre ─────────────────────────────────────────────────────── */}
      <h3 style={{ fontSize: 13, fontWeight: 800, margin: "16px 0 6px" }}>
        Cuadre — motor contra detalle
      </h3>
      <div className="fin-scroll-x">
        <table style={{ borderCollapse: "collapse", minWidth: 560 }}>
          <thead><tr>
            <th style={{ ...TH, textAlign: "left", minWidth: 250 }}>Renglón</th>
            <th style={{ ...TH, minWidth: 120 }}>P&L (motor)</th>
            <th style={{ ...TH, minWidth: 120 }}>Suma del detalle</th>
            <th style={{ ...TH, minWidth: 110 }}>Dif.</th>
          </tr></thead>
          <tbody>
            {cuadre.map(f => {
              const mal = Math.abs(f.dif) >= 0.005;
              return (
                <tr key={f.linea} style={mal ? { background: "var(--bg-surface)" } : undefined}>
                  <td style={TDL}>
                    {f.nombre}
                    <span style={{ color: "var(--text-disabled)", marginLeft: 6, fontSize: 10.5 }}>
                      {f.linea}
                    </span>
                  </td>
                  <td style={TD}>{usd(f.motor)}</td>
                  <td style={TD}>{usd(f.detalle)}</td>
                  <td style={{ ...TD, fontWeight: mal ? 800 : 400,
                               color: mal ? "var(--negative)" : "var(--text-disabled)" }}>
                    {usd(f.dif)}
                  </td>
                </tr>
              );
            })}
            {!cuadre.length && (
              <tr><td colSpan={4} style={{ ...TDL, color: "var(--text-secondary)" }}>
                {soloDif ? "No hay diferencias." : "Sin datos para este mes."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── 2. Detalle ────────────────────────────────────────────────────── */}
      <h3 style={{ fontSize: 13, fontWeight: 800, margin: "24px 0 6px" }}>
        Detalle — cada cuenta y dónde cayó
      </h3>
      <div className="fin-scroll-x">
        <table style={{ borderCollapse: "collapse", minWidth: 700 }}>
          <thead><tr>
            <th style={{ ...TH, textAlign: "left", minWidth: 70 }}>Cuenta</th>
            <th style={{ ...TH, textAlign: "left", minWidth: 210 }}>Nombre</th>
            <th style={{ ...TH, textAlign: "left", minWidth: 110 }}>Naturaleza</th>
            <th style={{ ...TH, textAlign: "left", minWidth: 150 }}>Renglón del P&L</th>
            <th style={{ ...TH, minWidth: 110 }}>Monto US$</th>
          </tr></thead>
          <tbody>
            {porDepto.map(([code, g]) => (
              // ⚠️ `Fragment` con `key` y no `<>`: un arreglo de fragmentos sin
              // llave hace que React reordene mal las filas al cambiar de mes,
              // y se ven subtotales pegados al departamento equivocado.
              <Fragment key={code}>
                <tr style={{ background: "var(--bg-surface)" }}>
                  <td colSpan={5} style={{ ...TDL, fontWeight: 800 }}>
                    {code} · {g.nombre}
                  </td>
                </tr>
                {g.filas.map((f, i) => (
                  <tr key={`${code}-${i}`}>
                    <td style={{ ...TDL, paddingLeft: 22 }}>{f.account_code}</td>
                    <td style={TDL}>{f.account_name}{f.outlet ? ` · ${f.outlet}` : ""}</td>
                    <td style={TDL}>{f.tipo}</td>
                    <td style={{ ...TDL, color: f.linea ? undefined : "var(--negative)",
                                 fontWeight: f.linea ? 400 : 700 }}>
                      {f.linea || "⚠ no cae en ninguna línea"}
                    </td>
                    <td style={TD}>{usd(f.monto)}</td>
                  </tr>
                ))}
                <tr>
                  <td colSpan={4} style={{ ...TDL, textAlign: "right", fontWeight: 700 }}>
                    Subtotal {code}
                  </td>
                  <td style={{ ...TD, fontWeight: 700,
                               borderTop: "1px solid var(--border-medium)" }}>
                    {usd(g.filas.reduce((s, f) => s + f.monto, 0))}
                  </td>
                </tr>
              </Fragment>
            ))}
            {!porDepto.length && (
              <tr><td colSpan={5} style={{ ...TDL, color: "var(--text-secondary)" }}>
                Sin detalle por cuenta para este mes.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── 3. Matriz por departamento ────────────────────────────────────── */}
      <h3 style={{ fontSize: 13, fontWeight: 800, margin: "24px 0 6px" }}>
        Resumen por departamento
      </h3>
      <div className="fin-scroll-x">
        <table style={{ borderCollapse: "collapse", minWidth: 700 }}>
          <thead><tr>
            <th style={{ ...TH, textAlign: "left", minWidth: 230 }}>Departamento</th>
            {columnas.map(c => <th key={c} style={{ ...TH, minWidth: 108 }}>{c}</th>)}
            <th style={{ ...TH, minWidth: 118,
                         borderLeft: "2px solid var(--border-medium)" }}>Total gasto</th>
          </tr></thead>
          <tbody>
            {(datos?.departamentos ?? []).map(d => (
              <tr key={String(d.dept_code)}>
                <td style={TDL}>{d.dept_code} · {d.dept_name}</td>
                {columnas.map(c => (
                  <td key={c} style={TD}>{usd(Number(d[c] ?? 0))}</td>
                ))}
                <td style={{ ...TD, fontWeight: 700,
                             borderLeft: "2px solid var(--border-medium)" }}>
                  {usd(d.total_gasto)}
                </td>
              </tr>
            ))}
            {datos && (
              <tr style={{ fontWeight: 800,
                           borderTop: "1px solid var(--border-medium)" }}>
                <td style={TDL}>TOTAL</td>
                {columnas.map(c => (
                  <td key={c} style={TD}>{usd(datos.totales[c] ?? 0)}</td>
                ))}
                <td style={{ ...TD, borderLeft: "2px solid var(--border-medium)" }}>
                  {usd(datos.totales.total_gasto ?? 0)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {datos && (
        <p style={{ fontSize: 11.5, color: "var(--text-secondary)",
                    marginTop: 14, maxWidth: 820, lineHeight: 1.6 }}>
          ⚠️ <b>No aparece la cuenta contable local</b> (61011101 y compañía).{" "}
          {datos.nota_cuenta_local}
        </p>
      )}
    </div>
  );
}
