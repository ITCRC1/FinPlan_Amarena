"use client";
import type { MembresiasAnio } from "@/lib/api";
import { bajarCuadros, type Cuadro, type FilaCuadro } from "@/lib/exportCuadro";

/**
 * El cuadro del año de membresías — conceptos en filas, meses en columnas.
 *
 * Owner, 2026-09-29: *«puedes llevarte una copia de este cuadro ya depurado al
 * dashboard al final como parte de las estadisticas. que esten
 * sincronizado… cualquier cambio alla que se actualice automaticamente»*.
 *
 * ## ⚠️ Una sola tabla, dos pantallas
 *
 * Vive acá y no duplicada porque «sincronizado» no es que las dos consulten lo
 * mismo: es que **no puedan divergir**. Dos copias del mismo cuadro empiezan
 * iguales y se separan en el primer arreglo que alguien hace de un lado —y
 * cuando eso pasa, las dos se ven bien y nadie sabe cuál mirar.
 *
 * Lo mismo con el Excel: `cuadroDelAnio` es la única definición del archivo,
 * así que el que baja del cierre y el que baja del Dashboard son el mismo
 * papel.
 *
 * ## ⚠️ Un mes sin contar va en blanco, no en cero
 *
 * Con doce columnas a la vista, un cero dice «el club no tuvo membresías» y el
 * blanco dice «todavía no lo contamos». Junio y julio de 2026 son lo segundo.
 */

const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const n = (v: number) => v.toLocaleString("es-CR", { maximumFractionDigits: 0 });

/** El rótulo de `activas` lleva la fecha del cierre —«al 31 de agosto 2026»—
 *  y en un cuadro de doce columnas esa fecha es de un mes solo. Se recorta. */
const sinFecha = (rotulo: string) => rotulo.replace(/ al .*$/, "");

export function MembresiasAnioTabla({ anio, mesSel }: {
  anio: MembresiasAnio;
  /** Resalta esa columna. Sin él, ninguna. */
  mesSel?: number;
}) {
  // Los conceptos del primer mes contado: son los mismos todos los meses.
  const filas = (anio.meses.find(m => m.cargado) ?? anio.meses[0]).conceptos;
  return (
    <div className="fin-scroll-x" style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: "100%" }}>
        <thead>
          <tr>
            <th style={TH}>Concepto</th>
            {anio.meses.map(m => (
              <th key={m.month} style={{ ...TH, textAlign: "right",
                    ...(m.month === mesSel ? ACTUAL : {}) }}>
                {MES3[m.month - 1]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map(c => (
            <tr key={c.concepto}>
              <td style={TD_ROT}>{sinFecha(c.rotulo)}</td>
              {anio.meses.map(m => {
                // ⚠️ `null` y no 0: el mes no está contado.
                const v = m.cargado
                  ? (m.conceptos.find(x => x.concepto === c.concepto)?.cantidad ?? 0)
                  : null;
                return (
                  <td key={m.month} className="mono"
                      style={{ ...TD, ...(m.month === mesSel ? ACTUAL : {}) }}>
                    {v === null ? "" : n(v)}
                  </td>
                );
              })}
            </tr>
          ))}
          <tr>
            <td style={{ ...TD_ROT, fontWeight: 700,
                         borderTop: "2px solid var(--border-medium)" }}>Total</td>
            {anio.meses.map(m => (
              <td key={m.month} className="mono"
                  style={{ ...TD, fontWeight: 700,
                           borderTop: "2px solid var(--border-medium)",
                           ...(m.month === mesSel ? ACTUAL : {}) }}>
                {m.cargado ? n(m.total) : ""}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/** La línea de contexto: cuántos meses hay contados y cuáles. */
export function MembresiasAnioPie({ anio }: { anio: MembresiasAnio }) {
  const cargados = anio.meses.filter(m => m.cargado);
  return (
    <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
      {cargados.length
        ? `${cargados.length} mes(es) contado(s): ${
            cargados.map(m => MES3[m.month - 1]).join(" · ")}`
        : "Ningún mes contado todavía"}
    </span>
  );
}

/**
 * El cuadro para Excel. ⚠️ Es la ÚNICA definición del archivo: el que baja del
 * cierre y el que baja del Dashboard son el mismo papel, y es el mismo formato
 * que lee la subida.
 */
export function cuadroDelAnio(anio: MembresiasAnio): Cuadro {
  const claves = [...new Set(anio.meses.flatMap(m => m.conceptos.map(c => c.concepto)))];
  const filas: FilaCuadro[] = claves.map(clave => {
    const rot = anio.meses.find(m => m.conceptos.some(c => c.concepto === clave))
      ?.conceptos.find(c => c.concepto === clave)?.rotulo ?? clave;
    const valores = anio.meses.map(m =>
      // ⚠️ `null` deja la celda VACÍA. Un mes sin contar en cero diría que el
      // club no tuvo membresías ese mes.
      m.cargado ? (m.conceptos.find(c => c.concepto === clave)?.cantidad ?? 0) : null);
    return { label: rot, formato: "num",
             valores: [...valores,
                       valores.reduce<number>((a, v) => a + (v ?? 0), 0)] };
  });
  filas.push({
    label: "Total general", es_total: true, formato: "num",
    valores: [...anio.meses.map(m => (m.cargado ? m.total : null)),
              anio.meses.reduce((a, m) => a + (m.cargado ? m.total : 0), 0)],
  });
  return {
    titulo: `Ingresos cobro por cuota de mantenimiento · ${anio.year}`,
    subtitulo: `${anio.escenario} — se puede editar y volver a subir con el `
      + `botón «Subir Excel» del cierre. Las columnas en blanco son meses sin contar.`,
    hoja: `Membresías ${anio.year}`,
    columnas: [
      { label: "Concepto", ancho: 42, formato: "texto" },
      ...anio.meses.map(m => ({ label: `${MES3[m.month - 1]} ${anio.year}`,
                                ancho: 13, formato: "num" as const })),
      { label: "Acumulado", ancho: 15, formato: "num" },
    ],
    filas,
  };
}

export async function bajarElAnio(anio: MembresiasAnio) {
  await bajarCuadros(`Membresias_${anio.year}`, [cuadroDelAnio(anio)]);
}

const TH: React.CSSProperties = {
  padding: "5px 9px", fontSize: 10.5, fontWeight: 600, textAlign: "left",
  textTransform: "uppercase", letterSpacing: ".03em",
  color: "var(--text-secondary)", borderBottom: "1px solid var(--border-subtle)",
  whiteSpace: "nowrap",
};
const TD: React.CSSProperties = {
  padding: "4px 9px", textAlign: "right", whiteSpace: "nowrap",
  borderBottom: "1px solid var(--border-subtle)",
};
const TD_ROT: React.CSSProperties = {
  padding: "4px 9px", color: "var(--text-secondary)",
  borderBottom: "1px solid var(--border-subtle)", whiteSpace: "nowrap",
};
const ACTUAL: React.CSSProperties = { background: "rgba(36,83,196,.07)" };
