"use client";
/**
 * Planning Report — los doce meses de una versión y el año de todas.
 *
 * Owner, 2026-10-01: *«necesito crear esta vista de cierre para Budget 2027…
 * por qué no creás un tab llamado Planning Report»* · *«quiero 12 meses, y full
 * year para comparar con otras versiones»* · *«quizás acá no necesitamos
 * revisar mes, YTD o Full Year»*.
 *
 * ## Por qué no alcanzaba con la pantalla del cierre
 *
 * El cierre contesta «cómo vamos»: parte el año en mes, acumulado y año, y vive
 * colgado del mes que se cierra. Planning contesta «cómo queda el año», y ahí el
 * acumulado a octubre no dice nada — lo que se mira es la estacionalidad mes a
 * mes y el total contra la versión anterior. Por eso acá no hay selector de mes
 * ni de corte: son los doce meses, siempre.
 *
 * ## ⚠️ La tabla que se ve es el MISMO objeto que baja al Excel
 *
 * `cuadroPlanning` devuelve un `Cuadro` y esta pantalla lo dibuja. No hay una
 * tabla en JSX y otra en el exportador: no pueden decir cosas distintas, que es
 * el defecto que este proyecto ya pagó una vez (owner, 2026-08-27: «el excel no
 * baja lo que está viendo»).
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getPLDetail, getScenarios, type PLDetail, type Scenario } from "@/lib/api";
import { bajarCuadros, type Cuadro } from "@/lib/exportCuadro";
import { HOTEL_ID } from "@/lib/hotel";
import { cuadroPlanning, rotuloDeVersion } from "@/lib/planningReport";
import { useEscenarioDe } from "@/lib/escenarioPreferido";
import IrA from "@/components/IrA";

const AMBITOS = [
  { id: "consolidado", rotulo: "Consolidado", ayuda: "Hotel + Club Madresal" },
  { id: "hotel", rotulo: "Hotel", ayuda: "Sin el Club Madresal" },
  { id: "club", rotulo: "Club Madresal", ayuda: "Sólo el departamento 260" },
] as const;

/** Cuántas versiones se pueden comparar contra la principal. */
const COMPARAR = 3;

const usd = (n: number | null | undefined) =>
  n === null || n === undefined ? ""
    : Math.abs(n) < 0.005 ? "—"
      : (n < 0 ? "(" : "") + Math.abs(n).toLocaleString("en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");

const TD: React.CSSProperties = {
  padding: "4px 10px", textAlign: "right", fontSize: 12, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = {
  padding: "4px 10px", fontSize: 12, whiteSpace: "nowrap", textAlign: "left",
};

export default function PlanningReportPage() {
  const [escenarios, setEscenarios] = useState<Scenario[]>([]);
  /** ⚠️ La regla COMPARTIDA, no una propia. Owner, 2026-08-14: «Lo dejo en
   *  Working 2027 y aparece en Working 2035» — cada pantalla traía su «el año
   *  más nuevo» copiado a mano, y el día que nacieron los Working 2028-2035
   *  todos los reportes se fueron a 2035 sin que nada fallara.
   *
   *  El rol «budget» abre en Budget Working 2027, que es para lo que existe
   *  esta pantalla, y recuerda lo que se elija. */
  const [principal, setPrincipal] = useEscenarioDe(
    "planning/report:budget", escenarios, "budget", undefined, true);
  const [comparar, setComparar] = useState<string[]>(Array(COMPARAR).fill(""));
  const [ambito, setAmbito] = useState<string>("consolidado");
  const [compacto, setCompacto] = useState(true);
  const [datos, setDatos] = useState<PLDetail | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bajando, setBajando] = useState(false);

  useEffect(() => {
    getScenarios(HOTEL_ID)
      .then(setEscenarios)
      .catch(e => setError(e instanceof Error ? e.message : "no se pudo cargar"));
  }, []);

  const otros = useMemo(() => comparar.filter(Boolean), [comparar]);

  const cargar = useCallback(async () => {
    if (!principal) return;
    setCargando(true);
    setError(null);
    try {
      setDatos(await getPLDetail(ambito, principal, otros));
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo cargar");
      setDatos(null);
    } finally {
      setCargando(false);
    }
  }, [ambito, principal, otros]);

  useEffect(() => { cargar(); }, [cargar]);

  const cuadro: Cuadro | null = useMemo(
    () => (datos ? cuadroPlanning(datos, escenarios, { ambito, compacto }) : null),
    [datos, escenarios, ambito, compacto]);

  async function bajar() {
    if (!principal) return;
    setBajando(true);
    setError(null);
    try {
      // Las TRES vistas en un archivo. En la pantalla se mira una por vez; en un
      // libro que se manda, las tres juntas son la comparación que el owner hace
      // igual, y pedirle que baje tres archivos es pedirle que uno se olvide.
      const cuadros: Cuadro[] = [];
      for (const a of AMBITOS) {
        const d = a.id === ambito ? datos
          : await getPLDetail(a.id, principal, otros).catch(() => null);
        if (d) cuadros.push(cuadroPlanning(d, escenarios, { ambito: a.id, compacto }));
      }
      const e = escenarios.find(s => s.id === principal);
      await bajarCuadros(
        `Planning_Report_${e?.year ?? ""}_${e?.type ?? ""}_${e?.version ?? ""}`,
        cuadros);
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo bajar el Excel");
    } finally {
      setBajando(false);
    }
  }

  const btn = (activo: boolean): React.CSSProperties => ({
    padding: "5px 12px", fontSize: 12, fontWeight: 600, border: "none",
    cursor: activo ? "default" : "pointer",
    background: activo ? "var(--brand)" : "var(--bg-surface)",
    color: activo ? "#fff" : "var(--text-primary)",
  });

  return (
    <div style={{ padding: "18px 22px" }}>
      <IrA esc={principal} />

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                    marginBottom: 12 }}>
        <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Planning Report</h1>
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          doce meses de una versión · el año, de todas
        </span>

        <nav aria-label="Ámbito" style={{ display: "inline-flex", borderRadius: 6,
             overflow: "hidden", border: "1px solid var(--border-medium)" }}>
          {AMBITOS.map((a, i) => (
            <button key={a.id} onClick={() => setAmbito(a.id)} title={a.ayuda}
              style={{ ...btn(a.id === ambito),
                       borderLeft: i ? "1px solid var(--border-medium)" : "none" }}>
              {a.rotulo}
            </button>
          ))}
        </nav>

        <button onClick={bajar} disabled={!datos || bajando}
          style={{ padding: "5px 12px", fontSize: 12, borderRadius: 4, fontWeight: 600,
                   border: "none", cursor: datos ? "pointer" : "not-allowed",
                   background: "var(--accent-excel)", color: "#fff" }}>
          {bajando ? "Bajando…" : "⬇ Excel (los tres ámbitos)"}
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
                    marginBottom: 14 }}>
        <select value={principal} onChange={e => setPrincipal(e.target.value)}
          className="fin-input" style={{ fontSize: 12.5, padding: "5px 8px" }}>
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>{s.year} · {s.type} {s.version}</option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>vs</span>
        {comparar.map((c, i) => (
          <select key={i} value={c}
            onChange={e => setComparar(v => v.map((x, j) => (j === i ? e.target.value : x)))}
            className="fin-input" style={{ fontSize: 12.5, padding: "5px 8px" }}>
            <option value="">{i === 0 ? "— sin comparación —" : "— +versión —"}</option>
            {escenarios
              .filter(s => s.id !== principal
                           && !comparar.some((o, j) => o === s.id && j !== i))
              .map(s => (
                <option key={s.id} value={s.id}>{s.year} · {s.type} {s.version}</option>
              ))}
          </select>
        ))}
        <label style={{ fontSize: 12, display: "inline-flex", alignItems: "center",
                        gap: 5, color: "var(--text-secondary)" }}>
          <input type="checkbox" checked={compacto}
                 onChange={e => setCompacto(e.target.checked)} />
          Esconder las líneas en cero
        </label>
      </div>

      {error && (
        <div style={{ padding: 10, borderRadius: 5, fontSize: 12.5, marginBottom: 12,
                      background: "var(--bg-warning)" }}>{error}</div>
      )}
      {cargando && (
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Cargando…</div>
      )}

      {!cargando && cuadro && (
        <>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 10 }}>
            {cuadro.subtitulo}
          </div>
          <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
            <table className="fin-table"
                   style={{ minWidth: 300 + cuadro.columnas.length * 92 }}>
              <thead>
                <tr>
                  {cuadro.columnas.map((c, i) => (
                    <th key={i}
                        style={{ ...(i ? TD : TDL),
                                 borderLeft: c.abre_grupo
                                   ? "2px solid var(--border-medium)" : undefined }}>
                      <div>{c.label}</div>
                      {c.sub && (
                        <div style={{ fontWeight: 400, fontSize: 10.5,
                                      color: "var(--text-secondary)" }}>{c.sub}</div>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cuadro.filas.map((f, i) => (
                  <tr key={i} style={{
                    background: f.es_seccion ? "var(--bg-elevated)"
                      : f.es_total ? "var(--bg-subtle)" : undefined,
                  }}>
                    <td style={{ ...TDL,
                      fontWeight: f.es_seccion || f.es_total ? 700 : 400,
                      paddingLeft: f.es_seccion || f.es_total ? 10 : 24 }}>
                      {f.label}
                    </td>
                    {f.valores.map((v, j) => (
                      <td key={j} className="mono" style={{ ...TD,
                        fontWeight: f.es_total ? 700 : 400,
                        borderLeft: cuadro.columnas[j + 1]?.abre_grupo
                          ? "2px solid var(--border-medium)" : undefined,
                        color: typeof v === "number" && v < 0
                          ? "var(--negative)" : undefined,
                      }}>
                        {typeof v === "number" ? usd(v) : (v ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
