"use client";
/**
 * Planning Report — los doce meses de una versión y el año de todas.
 *
 * Owner, 2026-10-01: *«necesito crear esta vista de cierre para Budget 2027…
 * por qué no creás un tab llamado Planning Report»* · *«quiero 12 meses, y full
 * year para comparar con otras versiones»* · *«quizás acá no necesitamos
 * revisar mes, YTD o Full Year»* · *«ajustado todos los reportes para que se
 * pueda generar reportes para comparar todos. desde los reportes, hasta los
 * checkbooks»*.
 *
 * ## Por qué no alcanzaba con la pantalla del cierre
 *
 * El cierre contesta «cómo vamos»: parte el año en mes, acumulado y año, y vive
 * colgado del mes que se cierra. Planning contesta «cómo queda el año», y ahí el
 * acumulado a octubre no dice nada — lo que se mira es la estacionalidad mes a
 * mes y el total contra la versión anterior. Por eso acá no hay selector de mes
 * ni de corte: son los doce meses, siempre.
 *
 * ## Los cuatro niveles, con las MISMAS columnas
 *
 * | vista | de dónde sale | qué abre |
 * |---|---|---|
 * | P&L | `/reports/pl-detail/` | la cascada completa, por ámbito |
 * | Aperturas | `/gasto-por-clase/?detalle=true` | depto · línea · cuenta |
 * | Checkbooks | `/gasto-por-clase/detalle-de-celda/` | cuenta del mayor |
 * | Estadísticas | `/pl/{id}/estadisticas/` | noches, ocupación, ADR, Club |
 *
 * Las cuatro pasan por `armarCuadro`, así que la columna «Full Year» es la misma
 * celda en todas: se puede bajar el libro entero y comparar hoja contra hoja.
 *
 * ## ⚠️ La tabla que se ve es el MISMO objeto que baja al Excel
 *
 * `cuadroPlanning` y sus hermanas devuelven un `Cuadro`, y `Tabla` lo dibuja. No
 * hay una tabla en JSX y otra en el exportador: no pueden decir cosas distintas,
 * que es el defecto que este proyecto ya pagó una vez (owner, 2026-08-27: «el
 * excel no baja lo que está viendo»).
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getDetalleDeCelda, getEstadisticasCierre, getGastoPorClase, getPLDetail,
  getScenarios,
  type DetalleCelda, type EstadisticasCierre, type GastoEscenario,
  type PLDetail, type Scenario,
} from "@/lib/api";
import { bajarCuadros, type Cuadro } from "@/lib/exportCuadro";
import { HOTEL_ID } from "@/lib/hotel";
import {
  APERTURAS, cuadroApertura, cuadroCheckbook, cuadroEstadisticas, cuadroPlanning,
  type ClaseApertura,
} from "@/lib/planningReport";
import { useEscenarioDe } from "@/lib/escenarioPreferido";
import IrA from "@/components/IrA";
import Tabla from "./Tabla";

const AMBITOS = [
  { id: "consolidado", rotulo: "Consolidado", ayuda: "Hotel + Club Madresal" },
  { id: "hotel", rotulo: "Hotel", ayuda: "Sin el Club Madresal" },
  { id: "club", rotulo: "Club Madresal", ayuda: "Sólo el departamento 260" },
] as const;

const VISTAS = [
  { id: "pl", rotulo: "P&L", ayuda: "La cascada completa, por ámbito" },
  { id: "aperturas", rotulo: "Aperturas", ayuda: "Por departamento, línea y cuenta" },
  { id: "checkbooks", rotulo: "Checkbooks", ayuda: "Cuenta por cuenta del mayor" },
  { id: "estadisticas", rotulo: "Estadísticas", ayuda: "Noches, ocupación, ADR, Club" },
] as const;

/** Cuántas versiones se pueden comparar contra la principal. */
const COMPARAR = 3;

const DOCE = Array.from({ length: 12 }, (_, i) => i + 1);

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
  const [vista, setVista] = useState<string>("pl");
  const [ambito, setAmbito] = useState<string>("consolidado");
  const [clase, setClase] = useState<ClaseApertura>("opex");
  const [compacto, setCompacto] = useState(true);

  const [pl, setPl] = useState<PLDetail | null>(null);
  const [gastos, setGastos] = useState<
    { escenarios: GastoEscenario[]; departamentos: Record<string, string> } | null>(null);
  const [libro, setLibro] = useState<Record<string, DetalleCelda>>({});
  const [stats, setStats] = useState<
    { meses: (EstadisticasCierre | null)[]; anios: (EstadisticasCierre | null)[] } | null>(null);

  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bajando, setBajando] = useState(false);

  useEffect(() => {
    getScenarios(HOTEL_ID)
      .then(setEscenarios)
      .catch(e => setError(e instanceof Error ? e.message : "no se pudo cargar"));
  }, []);

  const otros = useMemo(() => comparar.filter(Boolean), [comparar]);
  const ids = useMemo(
    () => (principal ? [principal, ...otros] : []), [principal, otros]);

  /** Las estadísticas: los doce meses de la principal, uno por llamada, y el año
   *  de cada versión con el período completo.
   *
   *  ⚠️ El año NO se suma acá. La ocupación, el ADR y el promedio de socios del
   *  año no son la suma de los doce meses, y el servidor ya sabe calcularlos
   *  sobre el período: rehacerlo del lado de la pantalla sería una segunda
   *  definición de la misma cifra. */
  const cargarStats = useCallback(async () => {
    const unoNulo = async (id: string, d: number, h: number) =>
      getEstadisticasCierre(id, d, h).catch(() => null);
    const [meses, anios] = await Promise.all([
      Promise.all(DOCE.map(m => unoNulo(ids[0], m, m))),
      Promise.all(ids.map(id => unoNulo(id, 1, 12))),
    ]);
    return { meses, anios };
  }, [ids]);

  const cargar = useCallback(async () => {
    if (!principal) return;
    setCargando(true);
    setError(null);
    try {
      if (vista === "pl") setPl(await getPLDetail(ambito, principal, otros));
      else if (vista === "aperturas") {
        const g = await getGastoPorClase(ids, true);
        setGastos({ escenarios: g.escenarios, departamentos: g.departamentos ?? {} });
      } else if (vista === "checkbooks") {
        setLibro({ [clase]: await getDetalleDeCelda(ids, clase, "", 0) });
      } else {
        setStats(await cargarStats());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "no se pudo cargar");
    } finally {
      setCargando(false);
    }
  }, [vista, ambito, clase, principal, otros, ids, cargarStats]);

  useEffect(() => { cargar(); }, [cargar]);

  const cuadro: Cuadro | null = useMemo(() => {
    const op = { ambito, compacto };
    try {
      if (vista === "pl") return pl ? cuadroPlanning(pl, escenarios, op) : null;
      if (vista === "aperturas") {
        return gastos
          ? cuadroApertura(clase, gastos.escenarios, gastos.departamentos,
                           escenarios, op)
          : null;
      }
      if (vista === "checkbooks") {
        const d = libro[clase];
        return d ? cuadroCheckbook(d, escenarios, op) : null;
      }
      return stats
        ? cuadroEstadisticas({ ...stats, versiones: stats.anios.map((a, i) => ({
            scenario_id: ids[i], escenario: a?.escenario })) }, escenarios, op)
        : null;
    } catch {
      return null;
    }
  }, [vista, pl, gastos, libro, stats, clase, escenarios, ambito, compacto, ids]);

  /**
   * El Excel de la vista que se está mirando, COMPLETA.
   *
   * En la pantalla se mira un ámbito —o una clase— por vez; en un libro que se
   * manda, todos juntos son la comparación que el owner hace igual, y pedirle
   * que baje cinco archivos es pedirle que uno se olvide.
   */
  async function bajar() {
    if (!principal) return;
    setBajando(true);
    setError(null);
    try {
      const cuadros: Cuadro[] = [];
      const op = { compacto };
      if (vista === "pl") {
        for (const a of AMBITOS) {
          const d = a.id === ambito ? pl
            : await getPLDetail(a.id, principal, otros).catch(() => null);
          if (d) cuadros.push(cuadroPlanning(d, escenarios, { ...op, ambito: a.id }));
        }
      } else if (vista === "aperturas") {
        let g = gastos;
        if (!g) {
          const r = await getGastoPorClase(ids, true);
          g = { escenarios: r.escenarios, departamentos: r.departamentos ?? {} };
        }
        for (const a of APERTURAS) {
          cuadros.push(cuadroApertura(a.clase, g.escenarios, g.departamentos,
                                      escenarios, { ...op, ambito }));
        }
      } else if (vista === "checkbooks") {
        for (const a of APERTURAS) {
          const d = libro[a.clase]
            ?? await getDetalleDeCelda(ids, a.clase, "", 0).catch(() => null);
          if (d) cuadros.push(cuadroCheckbook(d, escenarios, { ...op, ambito }));
        }
      } else {
        const s = stats ?? await cargarStats();
        cuadros.push(cuadroEstadisticas(
          { ...s, versiones: s.anios.map((a, i) => ({ scenario_id: ids[i],
                                                      escenario: a?.escenario })) },
          escenarios, { ...op, ambito }));
      }
      const e = escenarios.find(s => s.id === principal);
      const v = VISTAS.find(x => x.id === vista)?.rotulo ?? vista;
      await bajarCuadros(
        `Planning_${v}_${e?.year ?? ""}_${e?.type ?? ""}_${e?.version ?? ""}`,
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
  const grupo: React.CSSProperties = {
    display: "inline-flex", borderRadius: 6, overflow: "hidden",
    border: "1px solid var(--border-medium)",
  };

  return (
    <div style={{ padding: "18px 22px" }}>
      <IrA esc={principal} />

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                    marginBottom: 12 }}>
        <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Planning Report</h1>
        <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
          doce meses de una versión · el año, de todas
        </span>

        <nav aria-label="Nivel" style={grupo}>
          {VISTAS.map((v, i) => (
            <button key={v.id} onClick={() => setVista(v.id)} title={v.ayuda}
              style={{ ...btn(v.id === vista),
                       borderLeft: i ? "1px solid var(--border-medium)" : "none" }}>
              {v.rotulo}
            </button>
          ))}
        </nav>

        <button onClick={bajar} disabled={!cuadro || bajando}
          style={{ padding: "5px 12px", fontSize: 12, borderRadius: 4, fontWeight: 600,
                   border: "none", cursor: cuadro ? "pointer" : "not-allowed",
                   background: "var(--accent-excel)", color: "#fff" }}>
          {bajando ? "Bajando…"
            : vista === "pl" ? "⬇ Excel (los tres ámbitos)"
              : vista === "estadisticas" ? "⬇ Excel"
                : "⬇ Excel (las cinco clases)"}
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

      {/* El segundo eje depende del nivel: el P&L se mira por ámbito y las
          aperturas y los checkbooks, por clase de cuenta. Las estadísticas no
          tienen segundo eje. */}
      {vista === "pl" && (
        <nav aria-label="Ámbito" style={{ ...grupo, marginBottom: 12 }}>
          {AMBITOS.map((a, i) => (
            <button key={a.id} onClick={() => setAmbito(a.id)} title={a.ayuda}
              style={{ ...btn(a.id === ambito),
                       borderLeft: i ? "1px solid var(--border-medium)" : "none" }}>
              {a.rotulo}
            </button>
          ))}
        </nav>
      )}
      {(vista === "aperturas" || vista === "checkbooks") && (
        <nav aria-label="Clase" style={{ ...grupo, marginBottom: 12 }}>
          {APERTURAS.map((a, i) => (
            <button key={a.clase} onClick={() => setClase(a.clase)} title={a.eje}
              style={{ ...btn(a.clase === clase),
                       borderLeft: i ? "1px solid var(--border-medium)" : "none" }}>
              {a.rotulo}
            </button>
          ))}
        </nav>
      )}

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
          <Tabla cuadro={cuadro} />
        </>
      )}
      {!cargando && !cuadro && !error && (
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Sin datos para esta vista.
        </div>
      )}
    </div>
  );
}
