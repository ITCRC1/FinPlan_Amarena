"use client";
/**
 * El cuadro de cierre del owner: Mes · YTD · Full Year, lado a lado.
 *
 * Owner, 2026-08-27, mostrando su formato: *«ese es un formato que suelo usar,
 * donde pongo el mes que cierro, pongo el acumulado y a la vez el Full Year,
 * con las líneas más importantes»*.
 *
 * **Por qué los tres a la vez y no un selector.** La otra vista ya tiene el
 * botón Mes/YTD/Año, y sirve para mirar UNO. Este cuadro sirve para otra cosa:
 * ver si lo que pasó en el mes ya movió el acumulado y si eso alcanza para
 * cambiar el año. Esa lectura necesita los tres en la misma línea de ojo —
 * saltar entre botones la rompe, que es justo por lo que el owner los tiene
 * juntos en su Excel.
 *
 * **Las líneas son las suyas**: los diez totales de la cascada más los cuatro
 * por naturaleza del pie. Sin el detalle por departamento, a propósito: para
 * eso está la vista Cascada.
 *
 * ⚠️ El bloque de abajo —planilla, opex, costo, propiedad— es un MEMO, no una
 * reconciliación. En el propio Excel del owner suma los cuatro y nada más: no
 * cierra contra la utilidad, porque son otro corte del mismo gasto. El cuadre
 * de verdad es el de la vista Cascada, que compara contra el motor.
 */
import type { PLDetail } from "@/lib/api";

const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

/** Los totales del cuadro del owner, en su orden. */
const CLAVE = [
  "TOTAL REVENUES",
  "Total Operationg expenses",
  "OPERATING PROFIT",
  "TOTAL OVERHEAD EXPENSES",
  "TOTAL GROSS OPERATING PROFIT",
  "TOTAL NON OP EXPENSES",
  "EBITDA BEFORE CAPITAL",
  "EBITDA AFTER CAPITAL",
  "EARNINGS BEFORE INCOME TAXES",
  "NET PROFIT",
];

const CLASES: [string, string][] = [
  ["payroll", "Total Payroll and Benefits"],
  ["opex", "Total Operating Expenses"],
  ["cost", "Total Cost"],
  ["property", "Total Property Expenses"],
];

const usd = (n: number | null) =>
  n === null || n === undefined ? "—"
    : Math.abs(n) < 0.005 ? "—"
      : (n < 0 ? "(" : "") + "$" + Math.abs(n).toLocaleString("en-US",
        { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (n < 0 ? ")" : "");
const num = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
const pctv = (n: number) => (n * 100).toFixed(1) + "%";

const TD: React.CSSProperties = {
  padding: "3px 7px", textAlign: "right", fontSize: 11.5, whiteSpace: "nowrap",
};
const TDL: React.CSSProperties = { padding: "3px 9px", fontSize: 12 };

/** Los tres cortes, en índices de mes (0..11). */
function ventanas(mes: number) {
  return [
    { id: "mes", rotulo: MESES[mes - 1], idx: [mes - 1] },
    { id: "ytd", rotulo: `YTD ${MESES[mes - 1]}`,
      idx: Array.from({ length: mes }, (_, i) => i) },
    { id: "full", rotulo: "Full Year",
      idx: Array.from({ length: 12 }, (_, i) => i) },
  ];
}

export default function Cierre({ datos, mes }: { datos: PLDetail; mes: number }) {
  const cortes = ventanas(mes);
  const hayB = !!datos.comparar;

  const suma = (serie: number[] | null | undefined, idx: number[]) =>
    serie ? idx.reduce((s, i) => s + (serie[i] ?? 0), 0) : null;

  /** Una fila del cuadro: para cada corte, A · B · Var $ · Var %. */
  const celdas = (a?: number[] | null, b?: number[] | null) =>
    cortes.map(c => {
      const va = suma(a, c.idx);
      const vb = hayB ? suma(b, c.idx) : null;
      const d = va !== null && vb !== null ? va - vb : null;
      // La variación PORCENTUAL sobre una base cero no existe. Mostrar «0%» o
      // «∞» sería inventar una lectura; el guión dice lo que pasa.
      const p = d !== null && vb ? d / Math.abs(vb) : null;
      return { va, vb, d, p };
    });

  const fila = (rotulo: string, a?: number[] | null, b?: number[] | null,
                fuerte = false) => {
    const cs = celdas(a, b);
    return (
      <tr key={rotulo} style={{ background: fuerte ? "var(--bg-subtle)" : undefined }}>
        <td style={{ ...TDL, fontWeight: fuerte ? 700 : 500 }}>{rotulo}</td>
        {cs.map((c, i) => (
          <_Bloque key={i} c={c} hayB={hayB} fuerte={fuerte} />
        ))}
      </tr>
    );
  };

  const porRotulo = (r: string) => datos.filas.find(f => f.rotulo === r);

  // Estadísticas: razones que se rederivan, nunca se suman (ver la vista Cascada).
  const stat = (etiqueta: string, f: (idx: number[], k: PLDetail["kpis"]) => number,
                fmt: (n: number) => string) => (
    <tr key={etiqueta}>
      <td style={{ ...TDL, fontWeight: 500 }}>{etiqueta}</td>
      {cortes.map((c, i) => (
        <td key={i} className="mono" colSpan={hayB ? 4 : 1}
            style={{ ...TD, fontWeight: 600 }}>
          {fmt(f(c.idx, datos.kpis))}
          {hayB && datos.comparar
            ? `   ·   ${fmt(f(c.idx, datos.comparar.kpis))}` : ""}
        </td>
      ))}
    </tr>
  );

  const sum = (idx: number[], s: number[]) => idx.reduce((t, i) => t + (s[i] ?? 0), 0);

  return (
    <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
      <table className="fin-table" style={{ minWidth: hayB ? 1500 : 760 }}>
        <thead>
          <tr>
            <th style={{ ...TDL, textAlign: "left" }} rowSpan={2}>ACCOUNT DESCRIPTION</th>
            {cortes.map(c => (
              <th key={c.id} colSpan={hayB ? 4 : 1}
                  style={{ ...TD, textAlign: "center", fontWeight: 800,
                           borderLeft: "2px solid var(--border-medium)" }}>
                {c.rotulo}
              </th>
            ))}
          </tr>
          <tr>
            {cortes.map(c => (
              <_Cab key={c.id} hayB={hayB} a={datos.escenario}
                    b={datos.comparar?.escenario} />
            ))}
          </tr>
        </thead>
        <tbody>
          {stat("Total available Rooms", (i, k) => sum(i, k.rooms_available), num)}
          {stat("Total Rooms Occupied", (i, k) => sum(i, k.rooms_occupied), num)}
          {stat("Total Guests", (i, k) => sum(i, k.guests), num)}
          {stat("% Occupancy", (i, k) => {
            const a = sum(i, k.rooms_available);
            return a ? sum(i, k.rooms_occupied) / a : 0;
          }, pctv)}
          {stat("Average Daily Room Only", (i, k) => {
            const o = sum(i, k.rooms_occupied);
            return o ? sum(i, k.rooms_revenue) / o : 0;
          }, n => usd(n))}
          {stat("Total RevPAR", (i, k) => {
            const a = sum(i, k.rooms_available);
            return a ? sum(i, k.rooms_revenue) / a : 0;
          }, n => usd(n))}

          <tr><td colSpan={1 + cortes.length * (hayB ? 4 : 1)} style={{ height: 9 }} /></tr>

          {CLAVE.map(r => {
            const f = porRotulo(r);
            return f ? fila(r, f.meses, f.meses_b, true) : null;
          })}

          <tr><td colSpan={1 + cortes.length * (hayB ? 4 : 1)} style={{ height: 9 }} /></tr>

          {CLASES.map(([k, r]) =>
            fila(r, datos.clases.a[k], datos.clases.b?.[k]))}
          {fila("Total Operating and Property Expenses",
            CLASES.map(([k]) => datos.clases.a[k])
              .reduce((s, x) => s.map((v, i) => v + (x?.[i] ?? 0)), Array(12).fill(0)),
            datos.clases.b
              ? CLASES.map(([k]) => datos.clases.b![k])
                .reduce((s, x) => s.map((v, i) => v + (x?.[i] ?? 0)), Array(12).fill(0))
              : null,
            true)}
        </tbody>
      </table>
    </div>
  );
}

function _Cab({ hayB, a, b }: { hayB: boolean; a: string; b?: string }) {
  const est: React.CSSProperties = { ...TD, fontSize: 10.5, fontWeight: 700,
                                     color: "var(--text-secondary)" };
  if (!hayB) return <th style={{ ...est, borderLeft: "2px solid var(--border-medium)" }}>{a}</th>;
  return (
    <>
      <th style={{ ...est, borderLeft: "2px solid var(--border-medium)" }}>{a}</th>
      <th style={est}>{b}</th>
      <th style={est}>Var $</th>
      <th style={est}>Var %</th>
    </>
  );
}

function _Bloque({ c, hayB, fuerte }: {
  c: { va: number | null; vb: number | null; d: number | null; p: number | null };
  hayB: boolean; fuerte: boolean;
}) {
  const col = (v: number | null) => v !== null && v < 0 ? "var(--negative)" : undefined;
  const base: React.CSSProperties = { ...TD, fontWeight: fuerte ? 700 : 400 };
  if (!hayB) {
    return <td className="mono" style={{ ...base, color: col(c.va),
      borderLeft: "2px solid var(--border-medium)" }}>{usd(c.va)}</td>;
  }
  return (
    <>
      <td className="mono" style={{ ...base, color: col(c.va),
        borderLeft: "2px solid var(--border-medium)" }}>{usd(c.va)}</td>
      <td className="mono" style={{ ...base, color: col(c.vb) }}>{usd(c.vb)}</td>
      <td className="mono" style={{ ...base, color: col(c.d) }}>{usd(c.d)}</td>
      <td className="mono" style={{ ...base, color: col(c.d) }}>
        {c.p === null ? "—" : (c.p * 100).toFixed(1) + "%"}
      </td>
    </>
  );
}
