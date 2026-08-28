"use client";
/**
 * P&L Detail — Consolidado · Hotel · Club.
 *
 * Owner, 2026-08-27, entregando `BUDGET 2026-AMA formato.xlsx`: *«creálos en
 * Reporting con la información de presupuesto Budget 2026»*.
 *
 * Son las tres primeras hojas de ese libro. La cuarta —`P&L Full Detail`— ya
 * existía en `/reports/pl-full-detail`.
 *
 * **Una pantalla y no tres.** Los tres reportes son la misma cascada con un
 * ámbito distinto (el Hotel es el Consolidado menos el Club). Tres pantallas
 * serían tres verdades que hay que mantener sincronizadas a mano, y la primera
 * vez que se agregue una línea de ingreso dos se quedan viejas sin avisar. En
 * el menú igual aparecen como tres entradas, que es como el owner los pide.
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getScenarios, getPLDetail, type Scenario, type PLDetail } from "@/lib/api";
import { HOTEL_ID } from "@/lib/hotel";
import { useEscenarioDe } from "@/lib/escenarioPreferido";
import IrA from "@/components/IrA";
import { bajarCuadros, type FilaCuadro } from "@/lib/exportCuadro";

const AMBITOS = [
  { id: "consolidado", rotulo: "Consolidado", ayuda: "Hotel + Club Madresal" },
  { id: "hotel", rotulo: "Hotel", ayuda: "Sin el Club Madresal" },
  { id: "club", rotulo: "Club Madresal", ayuda: "Sólo el departamento 260" },
] as const;

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const usd = (n: number | null) =>
  n === null || n === undefined ? "—"
    : n === 0 ? "—"
      : (n < 0 ? "(" : "") + "$" + Math.abs(n).toLocaleString("en-US",
        { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "3px 8px", textAlign: "right", fontSize: 12, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "3px 10px", fontSize: 12.5 };

export default function PLDetailPage() {
  const sp = useSearchParams();
  const inicial = (sp.get("ambito") || "consolidado") as typeof AMBITOS[number]["id"];
  const [ambito, setAmbito] = useState<string>(
    AMBITOS.some(a => a.id === inicial) ? inicial : "consolidado");
  const [escenarios, setEscenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useEscenarioDe(
    "reports/pl-detail:budget", escenarios, "budget", undefined, true);
  const [datos, setDatos] = useState<PLDetail | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // El `?ambito=` de la dirección es lo que hace que las TRES entradas del menú
  // lleguen a esta misma pantalla mostrando cada una lo suyo.
  useEffect(() => {
    const a = sp.get("ambito");
    if (a && AMBITOS.some(x => x.id === a)) setAmbito(a);
  }, [sp]);

  useEffect(() => { getScenarios(HOTEL_ID).then(setEscenarios).catch(() => setEscenarios([])); }, []);

  const cargar = useCallback(async () => {
    if (!scenarioId) return;
    setCargando(true); setError(null);
    try {
      setDatos(await getPLDetail(ambito, scenarioId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el reporte");
      setDatos(null);
    } finally { setCargando(false); }
  }, [ambito, scenarioId]);

  useEffect(() => { cargar(); }, [cargar]);

  const act = AMBITOS.find(a => a.id === ambito)!;

  /** El mismo cuadro que se ve, bajado tal cual.
   *
   *  Se arma desde `datos.filas` y no desde el DOM: lo que baja tiene que ser el
   *  dato, no lo que quedó pintado. Y va con el bloque de control adentro —si
   *  el reporte no cuadra, el que abra el archivo lo tiene que ver ahí. */
  const [bajando, setBajando] = useState(false);
  const bajar = useCallback(async () => {
    if (!datos) return;
    setBajando(true);
    try {
      const filas: FilaCuadro[] = datos.filas
        .filter(f => f.tipo !== "esp")
        .map(f => ({
          label: f.rotulo,
          nivel: f.tipo === "det" ? 1 : 0,
          es_total: f.tipo === "tot" || f.tipo === "sec",
          valores: f.meses === null
            ? Array(13).fill(null)
            : [...f.meses, f.full],
        }));
      filas.push({ label: "", valores: Array(13).fill(null) });
      filas.push({
        label: `CONTROL · ingresos ${datos.control.ingresos} · gastos ${datos.control.gastos}`
             + ` · utilidad ${datos.control.utilidad} · diferencia ${datos.control.diferencia}`,
        es_total: true, valores: Array(13).fill(null),
      });
      await bajarCuadros(`PL_Detail_${act.rotulo}_${datos.year}`, [{
        titulo: `P&L Detail — ${act.rotulo}`,
        subtitulo: `${datos.escenario} · ${act.ayuda} · USD`,
        hoja: act.rotulo,
        columnas: [{ label: "ACCOUNT DESCRIPTION", ancho: 46, formato: "texto" },
                   ...MESES.map(m => ({ label: m, formato: "usd2" as const })),
                   { label: "Full Year", formato: "usd2" as const }],
        filas,
      }]);
    } finally { setBajando(false); }
  }, [datos, act]);

  return (
    <div style={{ padding: "18px 22px", maxWidth: "100%" }}>
      <IrA esc={scenarioId} />

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
                    marginBottom: 14 }}>
        <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0,
                     color: "var(--text-primary)" }}>
          P&amp;L Detail — {act.rotulo}
        </h1>

        <nav aria-label="Ámbito" style={{
          display: "inline-flex", borderRadius: 6, overflow: "hidden",
          border: "1px solid var(--border-medium)",
        }}>
          {AMBITOS.map((a, i) => (
            <button key={a.id} onClick={() => setAmbito(a.id)} title={a.ayuda}
              aria-current={a.id === ambito ? "true" : undefined}
              style={{
                padding: "6px 13px", fontSize: 12, fontWeight: 600, border: "none",
                borderLeft: i === 0 ? "none" : "1px solid var(--border-medium)",
                cursor: a.id === ambito ? "default" : "pointer",
                background: a.id === ambito ? "var(--brand)" : "var(--bg-surface)",
                color: a.id === ambito ? "#fff" : "var(--text-primary)",
              }}>{a.rotulo}</button>
          ))}
        </nav>

        <button onClick={bajar} disabled={!datos || bajando}
          style={{ padding: "5px 12px", fontSize: 12, borderRadius: 4, fontWeight: 600,
                   border: "none", cursor: datos ? "pointer" : "not-allowed",
                   background: "var(--accent-excel)", color: "#fff" }}>
          {bajando ? "Bajando…" : "⬇ Excel"}
        </button>

        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
          className="fin-input" style={{ fontSize: 12.5, padding: "5px 8px" }}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>
              {s.year} · {s.type} {s.version}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div style={{ padding: 10, borderRadius: 5, fontSize: 12.5, marginBottom: 12,
                      background: "var(--bg-warning)", color: "var(--text-primary)" }}>
          {error}
        </div>
      )}

      {cargando && <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Cargando…</div>}

      {!cargando && datos && (
        <>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 10 }}>
            {datos.escenario} · {act.ayuda} · USD
          </div>

          {datos.club && (
            <div style={{ marginBottom: 14, fontSize: 12.5 }}>
              <strong>Membresías al cierre:</strong>{" "}
              total {datos.club.cierre.total} · condicionados {datos.club.cierre.condicionados}
              {" "}· pagando {datos.club.cierre.pagando} · en acuerdo {datos.club.cierre.acuerdo_pago}
            </div>
          )}

          <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
            <table className="fin-table" style={{ minWidth: 1250 }}>
              <thead>
                <tr>
                  <th style={{ ...TDL, textAlign: "left" }}>ACCOUNT DESCRIPTION</th>
                  {MESES.map(m => <th key={m} style={TD}>{m}</th>)}
                  <th style={{ ...TD, fontWeight: 800 }}>Full Year</th>
                </tr>
              </thead>
              <tbody>
                {datos.filas.map((f, i) => {
                  if (f.tipo === "esp") {
                    return <tr key={i}><td colSpan={14} style={{ height: 7 }} /></tr>;
                  }
                  const fuerte = f.tipo === "tot";
                  const fondo = f.tipo === "sec" ? "var(--bg-elevated)"
                    : fuerte ? "var(--bg-subtle)" : undefined;
                  return (
                    <tr key={i} style={{ background: fondo }}>
                      <td style={{
                        ...TDL,
                        fontWeight: f.tipo === "sec" || fuerte ? 700 : 400,
                        paddingLeft: f.tipo === "det" ? 24 : 10,
                      }}>{f.rotulo}</td>
                      {f.meses === null
                        ? <td colSpan={13} />
                        : <>
                          {f.meses.map((v, j) => (
                            <td key={j} className="mono" style={{
                              ...TD, fontWeight: fuerte ? 700 : 400,
                              color: v < 0 ? "var(--negative)" : undefined,
                            }}>{usd(v)}</td>
                          ))}
                          <td className="mono" style={{
                            ...TD, fontWeight: 800,
                            color: (f.full ?? 0) < 0 ? "var(--negative)" : undefined,
                          }}>{usd(f.full)}</td>
                        </>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* El cuadre del owner, con la diferencia CALCULADA. Si algún día no
              cierra, se ve — que es para lo que existe. */}
          <div style={{
            marginTop: 16, padding: "10px 14px", borderRadius: 6, fontSize: 12.5,
            border: "1px solid var(--border-medium)", background: "var(--bg-surface)",
            display: "flex", gap: 22, flexWrap: "wrap", alignItems: "center",
          }}>
            <strong>Control</strong>
            <span>Ingresos {usd(datos.control.ingresos)}</span>
            <span>Gastos {usd(datos.control.gastos)}</span>
            <span>Utilidad {usd(datos.control.utilidad)}</span>
            <span style={{
              fontWeight: 700,
              color: Math.abs(datos.control.diferencia) < 0.01
                ? "var(--positive)" : "var(--negative)",
            }}>
              Diferencia {datos.control.diferencia.toFixed(2)}
              {Math.abs(datos.control.diferencia) < 0.01 ? " ✓" : " ⚠"}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
