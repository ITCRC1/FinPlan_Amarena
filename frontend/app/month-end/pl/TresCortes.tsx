"use client";
/**
 * El P&L completo en los TRES cortes a la vez: mes, YTD y full year.
 *
 * Owner, 2026-09-29, entregando `Full P&L CWL YTD JULY 2026 & Full Year
 * Forecast.pdf`: *«quiero construir un archivo como este, un tab que presente
 * el mes actual, budget y Forecast, YTD y Full Year, con su varianza. es de
 * vital importancia»*.
 *
 * ## El hueco que llena
 *
 * | | qué compara | qué muestra |
 * |---|---|---|
 * | `12 meses` | una versión | 17 líneas de resumen |
 * | `Formato` | una versión | la cascada, **mes a mes** |
 * | `P&L Detail Full` | hasta 4 versiones | la cascada, en **un** corte |
 * | **este** | hasta 4 versiones | la cascada, en **los tres cortes** |
 *
 * Los tres juntos es lo que se manda a los dueños: el mes explica la ejecución,
 * el YTD la tendencia y el full year el aterrizaje. En tres pantallas nadie los
 * compara — y la pregunta de todo cierre es si lo del mes cambia el año.
 *
 * ## Acá sólo está la pantalla
 *
 * La aritmética, la regla de qué par se resta y el armado del archivo viven en
 * `lib/tresCortes`. Se puede correr contra las cifras del PDF sin abrir el
 * navegador —y se corrió: los seis indicadores dan idéntico en los dos
 * cortes— y el Excel de acá es el MISMO que arma el capítulo del Word.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getPLDetail, type EstadisticasCierre, type PLDetail,
         type Scenario } from "@/lib/api";
import { bajarCuadros } from "@/lib/exportCuadro";
import {
  celdasDe, cortesDe, cuadroTresCortes, esDelClub, estadisticasDeLosCortes, KPIS,
  parDe as parDeLib, PIE_ESTADISTICO, suma, usd, valorDe, type Corte,
} from "@/lib/tresCortes";

const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export default function TresCortes({ escenarios, ranuras, mes, compacto = true }: {
  escenarios: Scenario[];
  /** Los ids de los cuatro selectores de la pantalla, en orden. */
  ranuras: string[];
  /** El mes del cierre: define el corte «mes» y hasta dónde llega el YTD. */
  mes: number;
  /** Esconder las líneas que están en cero los doce meses en todas las
   *  versiones. Lo manda la pantalla: el interruptor es uno para todo. */
  compacto?: boolean;
}) {
  const [ambito, setAmbito] = useState("consolidado");
  const [datos, setDatos] = useState<PLDetail | null>(null);
  const [cargando, setCargando] = useState(false);
  /** El encabezado estadístico, por corte × versión. ⚠️ No se deriva de
   *  `datos`: sale de `/pl/{id}/estadisticas/`, que es el mismo endpoint del
   *  que lo saca el resto del cierre. */
  const [stats, setStats] = useState<(EstadisticasCierre | null)[][]>([]);
  const [error, setError] = useState<string | null>(null);

  const ids = useMemo(() => ranuras.filter(Boolean), [ranuras]);

  const cargar = useCallback(async () => {
    if (!ids.length) { setDatos(null); return; }
    setCargando(true); setError(null);
    try {
      // Una sola llamada: los tres cortes son tres formas de sumar el mismo
      // arreglo de doce, no tres consultas.
      setDatos(await getPLDetail(ambito, ids[0], ids.slice(1)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el P&L");
      setDatos(null);
    } finally { setCargando(false); }
  }, [ids, ambito]);

  useEffect(() => { cargar(); }, [cargar]);

  const cortes: Corte[] = useMemo(() => cortesDe(mes), [mes]);
  // `?? []` crea un arreglo nuevo en cada render, y de él cuelgan varios
  // `useMemo`: sin esto se recalculan siempre.
  const versiones = useMemo(() => datos?.versiones ?? [], [datos]);

  /** ⚠️ La regla del par vive en el lib: la pantalla, el Excel y el Word
   *  tienen que restar lo mismo. */
  const parDe = useCallback((c: Corte) => parDeLib(c, versiones, escenarios),
    [versiones, escenarios]);

  // El encabezado de los tres cortes. Se vuelve a pedir cuando cambian las
  // versiones o el mes del cierre — que es lo que mueve los rangos.
  useEffect(() => {
    let vivo = true;
    if (!versiones.length) { setStats([]); return; }
    estadisticasDeLosCortes(cortes, versiones)
      .then(r => { if (vivo) setStats(r); })
      .catch(() => { if (vivo) setStats([]); });
    return () => { vivo = false; };
  }, [cortes, versiones]);

  /** Las filas que se dibujan. Compacto esconde las que están en cero los doce
   *  meses en TODAS las versiones — una línea viva en una sola se queda. */
  const filas = useMemo(() => {
    const todas = datos?.filas ?? [];
    if (!compacto) return todas;
    const doce = Array.from({ length: 12 }, (_, i) => i);
    return todas.filter(f => f.tipo !== "det"
      || (f.series ?? []).some(s => s && suma(s, doce) !== 0));
  }, [datos, compacto]);

  const etiqueta = useCallback((sid: string) => {
    const s = escenarios.find(x => x.id === sid);
    return s ? `${s.type} ${s.version}` : sid.slice(0, 8);
  }, [escenarios]);

  /** ⚠️ El MISMO cuadro que arma el capítulo del Word. Dos copias se separan
   *  en el primer arreglo y nadie sabría cuál manda. */
  function bajar() {
    if (!datos) return;
    bajarCuadros(`FullPL_${MES3[mes - 1]}_${datos.year}`,
                 [cuadroTresCortes(datos, mes, escenarios, ambito, compacto, stats)])
      .catch(e => setError(e instanceof Error ? e.message : "No se pudo bajar"));
  }

  if (!ids.length) return <p style={P}>Elegí al menos una versión arriba.</p>;
  if (cargando && !datos) return <p style={P}>Cargando el P&L…</p>;
  if (error) return <p style={{ ...P, color: "var(--negative)" }}>{error}</p>;
  if (!datos) return <p style={P}>Sin datos.</p>;

  /** Dónde arranca cada corte dentro de la fila de celdas, para saber cuál
   *  lleva la línea divisoria y cuál es la columna de varianza. */
  const inicios = cortes.map((_, ci) => cortes.slice(0, ci).reduce(
    (a, x) => a + versiones.length + (parDe(x) ? 1 : 0), 0));
  const esVarianza = (i: number) => !inicios.some(
    ini => i >= ini && i < ini + versiones.length);
  const anchoTotal = 1 + cortes.reduce(
    (a, c) => a + versiones.length + (parDe(c) ? 1 : 0), 0);

  const pintar = (vals: (number | null)[], fuerte: boolean, top: boolean,
                  fmt: (n: number | null) => string = usd) =>
    vals.map((v, i) => (
      <td key={i} className="mono"
          style={{ ...TD, ...(inicios.includes(i) ? { borderLeft: BL } : {}),
                   ...(top ? { borderTop: BL } : {}),
                   fontWeight: fuerte ? 700 : 400,
                   fontStyle: esVarianza(i) ? "italic" : undefined,
                   color: v !== null && v < 0 ? "var(--negative)" : undefined }}>
        {fmt(v)}
      </td>
    ));

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 10 }}>
        <select value={ambito} onChange={e => setAmbito(e.target.value)} style={SEL}>
          <option value="consolidado">Consolidado</option>
          <option value="hotel">Hotel</option>
          <option value="club">Club</option>
        </select>
        <button onClick={bajar} style={{ ...SEL, cursor: "pointer", fontWeight: 600,
                  border: "none", background: "var(--accent-excel)", color: "#fff" }}>
          ⬇ Excel
        </button>
        <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
          El mes, el acumulado y los doce meses, del mismo año.{" "}
          <b>En el full year la varianza es Forecast contra Budget</b> — el
          Actual del año todavía no existe.
        </span>
      </div>

      <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: "100%" }}>
          <thead>
            <tr>
              <th rowSpan={2} style={{ ...TH, ...PEGA, textAlign: "left",
                    verticalAlign: "bottom", minWidth: 250 }}>
                ACCOUNT DESCRIPTION
              </th>
              {cortes.map(c => (
                <th key={c.clave} colSpan={versiones.length + (parDe(c) ? 1 : 0)}
                    style={{ ...TH, textAlign: "center", borderLeft: BL,
                             color: "var(--text-primary)", fontSize: 11.5 }}>
                  {c.titulo} {datos.year}
                </th>
              ))}
            </tr>
            <tr>
              {cortes.flatMap(c => {
                const par = parDe(c);
                return [
                  ...versiones.map((v, i) => (
                    <th key={`${c.clave}-${v.scenario_id}`}
                        style={{ ...TH, ...(i === 0 ? { borderLeft: BL } : {}) }}>
                      {etiqueta(v.scenario_id)}
                    </th>
                  )),
                  ...(par ? [
                    <th key={`${c.clave}-var`} style={{ ...TH, fontStyle: "italic" }}>
                      Var vs {etiqueta(versiones[par[1]].scenario_id)}
                    </th>] : []),
                ];
              })}
            </tr>
          </thead>
          <tbody>
            {/* El encabezado estadístico va DENTRO de la misma tabla y con las
                mismas columnas: es el denominador de todo lo que sigue. */}
            {KPIS.map(k => {
              const vals = celdasDe(cortes, versiones, escenarios,
                (vi, _m, ci) => k.calc(stats[ci]?.[vi] ?? null));
              // ⚠️ Una propiedad sin Club no lleva los tres renglones del Club
              // en blanco: tres filas vacías se leen como un dato que falta.
              if (esDelClub(k.rotulo) && vals.every(v => v === null)) return null;
              return (
                <tr key={k.rotulo}>
                  <td style={{ ...TD_ROT, ...PEGA, fontWeight: k.fuerte ? 700 : 400 }}
                      title={k.promEnRango
                        ? "En el YTD y en el full year es un promedio mensual, "
                          + "no un acumulado."
                        : undefined}>
                    {k.rotulo}
                    {k.promEnRango && (
                      <span style={{ color: "var(--text-secondary)", fontWeight: 400,
                                     fontSize: 10.5, marginLeft: 5 }}>prom.</span>
                    )}
                  </td>
                  {pintar(vals, !!k.fuerte, false, k.fmt)}
                </tr>
              );
            })}
            <tr><td colSpan={anchoTotal} style={{ height: 10 }} /></tr>

            {filas.map((f, fi) => {
              if (f.tipo === "esp") {
                return <tr key={fi}><td colSpan={anchoTotal} style={{ height: 8 }} /></tr>;
              }
              const seccion = f.tipo === "sec";
              const fuerte = f.tipo === "tot" || f.tipo === "sub";
              // ⚠️ Los encabezados de sección van sin números, no en cero: un
              // cero ahí se leería como «esta sección no tuvo movimiento».
              const vals = seccion
                ? celdasDe(cortes, versiones, escenarios, () => null)
                : celdasDe(cortes, versiones, escenarios,
                           (vi, meses) => valorDe(f, vi, meses));
              return (
                <tr key={fi} style={seccion ? { background: "var(--bg-elevated)" } : undefined}>
                  <td style={{ ...TD_ROT, ...PEGA,
                               fontWeight: fuerte || seccion ? 700 : 400,
                               textTransform: seccion ? "uppercase" : undefined,
                               fontSize: seccion ? 11 : undefined,
                               borderTop: f.tipo === "tot" ? BL : undefined }}>
                    {f.rotulo}
                  </td>
                  {pintar(vals, fuerte, f.tipo === "tot")}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ margin: "8px 2px 0", fontSize: 10.5, lineHeight: 1.5,
                  color: "var(--text-secondary)" }}>
        {PIE_ESTADISTICO}
      </p>
    </div>
  );
}


const BL = "2px solid var(--border-medium)";
const P: React.CSSProperties = { fontSize: 13, color: "var(--text-secondary)" };
const SEL: React.CSSProperties = {
  padding: "5px 10px", fontSize: 12.5, borderRadius: 5,
  border: "1px solid var(--border-medium)", background: "var(--bg-input)",
  color: "var(--text-primary)",
};
const TH: React.CSSProperties = {
  padding: "5px 9px", fontSize: 10.5, fontWeight: 600, textAlign: "right",
  textTransform: "uppercase", letterSpacing: ".03em", whiteSpace: "nowrap",
  color: "var(--text-secondary)", borderBottom: "1px solid var(--border-medium)",
  background: "var(--bg-surface)",
};
const TD: React.CSSProperties = {
  padding: "3px 9px", textAlign: "right", whiteSpace: "nowrap",
  borderBottom: "1px solid var(--border-subtle)",
};
const TD_ROT: React.CSSProperties = {
  padding: "3px 9px", whiteSpace: "nowrap",
  borderBottom: "1px solid var(--border-subtle)",
};
/** La columna del rótulo se queda quieta: con trece columnas de números, al
 *  llegar al full year ya no se sabe qué fila se está mirando. */
const PEGA: React.CSSProperties = {
  position: "sticky", left: 0, zIndex: 1, background: "var(--bg-surface)",
};
