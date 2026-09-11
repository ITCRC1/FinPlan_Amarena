"use client";
/**
 * Cierre de mes · Estadística de habitaciones desde el PDF del PMS.
 *
 * Owner, 2026-09-09: *«la idea es que se suba el documento y se lea la
 * información pero que no se guarde — solo se tomen los datos y ya»* · *«esto
 * debe quedar en cierre de mes»* · *«Amarena no tiene Opera»* · *«por qué no
 * ponemos las habitaciones en columnas y en filas CPL, directos, expedia»* ·
 * *«debe haber un check box para que el CPL no forme parte del ADR global»* ·
 * *«cuál es la vista limpia donde se pueda ver todo rápido acumulado»*.
 *
 * ## Cuatro vistas del mismo dato
 *
 * | Vista | Pregunta que contesta |
 * |---|---|
 * | Por canal | ¿De dónde vino el mes? Mix de noches vs. mix de plata |
 * | Por habitación | ¿Qué se guarda? Es fila por fila lo que va a la base |
 * | Canal × habitación | El cruce completo, para auditar contra el PDF |
 * | Acumulado | El año: meses en columnas, YTD al final |
 *
 * ⚠️ **Las cuatro salen del mismo dato y ninguna guarda su propio total.** Si
 * cada una sumara por su cuenta, tarde o temprano dirían cosas distintas del
 * mismo mes — y no habría forma de saber cuál tiene razón.
 *
 * ## Subir no es guardar
 *
 * El PDF se lee en memoria y se descarta; `/room-stats/leer-pdf/` no escribe
 * una sola fila. Guardar es un paso aparte y va por el mismo endpoint que la
 * carga manual. En el medio, una persona confirma a qué categoría de Master
 * Data va cada categoría del PMS: sin ese paso, un nombre que no calza
 * archiva las noches bajo un rótulo que el reporte no busca y **nada avisa**.
 *
 * ## El ADR y las cortesías
 *
 * En marzo 2026 CPL puso el 60.8% de las noches con el 0.7% del ingreso: el
 * ADR del mes es $125.44 con ese canal adentro y $317.66 sin él. La casilla
 * «En ADR» decide cuáles entran, y la decisión se guarda en `market_codes`
 * para que valga en todos los meses.
 *
 * ⚠️ **Desmarcar un canal NO mueve noches, pax ni ingreso.** Sólo cambia el
 * denominador del ADR. Los totales siguen siendo los del archivo y siguen
 * cuadrando contra el PDF; si el ingreso se moviera, un ADR distinto al del
 * documento dejaría de poder explicarse.
 */
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  asignarCanalPms, getAnioRoomStats, getRoomStatsEntry, getScenarios,
  guardarAliasPms, leerPdfRoomStats, marcarCanalParaKpis, saveRoomStatsEntry,
  type AnioMes, type AnioRoomStats,
  type PdfRoomStatsLectura, type RoomStatCanalIn,
  type Scenario,
} from "@/lib/api";
import { bajarCuadros, type Cuadro } from "@/lib/exportCuadro";
import { useEscenarioDe } from "@/lib/escenarioPreferido";
import { HOTEL_ID } from "@/lib/hotel";

const MES3 = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

type Vista = "canal" | "habitacion" | "matriz" | "acumulado";
type Medida = "noches" | "ocupacion" | "pax" | "ingreso" | "adr" | "revpar";

/** Ocupación y RevPAR se dividen por noches disponibles, y un canal no tiene
 *  inventario propio: por canal no significan nada. */
const MEDIDAS: [Medida, string][] = [
  ["noches", "Noches ocupadas"], ["ocupacion", "% Ocupación"], ["pax", "Pax"],
  ["ingreso", "Ingreso"], ["adr", "ADR"], ["revpar", "RevPAR"],
];
const MEDIDAS_CANAL = MEDIDAS.filter(([k]) => k !== "ocupacion" && k !== "revpar");

/** Los canales (KPI groups), en el mismo orden que `market_code.py::CANALES`.
 *  Vacío es una opción: significa «nadie lo decidió», no «no tiene». */
const CANALES = ["Travel Agent", "Direct Client", "Website", "OTA", "INHOUSE"];

const SEL: React.CSSProperties = {
  padding: "5px 9px", fontSize: 12.5, borderRadius: 6,
  border: "1px solid var(--border-medium)",
  background: "var(--bg-surface)", color: "var(--text-primary)",
};
const TH: React.CSSProperties = {
  textAlign: "right", padding: "6px 10px", fontSize: 10.5, fontWeight: 600,
  textTransform: "uppercase", letterSpacing: ".05em",
  color: "var(--text-secondary)", background: "var(--bg-elevated)",
  borderBottom: "1px solid var(--border-medium)", whiteSpace: "nowrap",
};
const TD: React.CSSProperties = {
  textAlign: "right", padding: "6px 10px", fontSize: 12.5,
  fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
  borderTop: "1px solid var(--border-subtle)",
};

const n = (v: number, d = 0) =>
  v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = (v: number) => `$${n(v, 2)}`;
const pct = (v: number) => `${n(v, 2)}%`;

/** Triple [noches, pax, ingreso] — la unidad con la que se suma todo acá. */
type T3 = [number, number, number];
const cero: () => T3 = () => [0, 0, 0];
const mas = (a: T3, b: T3): T3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const adrDe = (b: T3) => (b[0] ? usd(b[2] / b[0]) : "—");

/** El mes leído, ya agregado. Lo calcula la página UNA vez y lo reciben las
 *  tres vistas del mes: que cada una sumara por su cuenta es cómo terminan
 *  mostrando totales distintos del mismo archivo. */
interface MesAgregado {
  canales: string[];
  porCat: T3[];      // total por categoría, tal cual el archivo
  baseCat: T3[];     // sólo los canales que cuentan para el ADR
  porCan: T3[];      // total por canal
  total: T3;
  baseTot: T3;
  disp: number[];    // noches disponibles por categoría (units × días)
  dispTot: number;
  filtra: boolean;   // ¿hay algún canal fuera del ADR?
}
/** Los ingredientes de una celda del acumulado. La división la hace quien
 *  muestra, para que el YTD de una tasa no salga de promediar meses. */
interface Ingredientes { tot: T3; base: T3; disp: number }

type MapaAdr = Record<string, boolean>;

/** Lo que las vistas del mes pintan. Puede venir de un PDF recién leído o
 *  **reconstruido de la base** para un mes ya guardado.
 *
 *  ⚠️ `desdeLaBase` no es cosmético: lo guardado NO incluye el resumen del
 *  PDF —habitaciones bloqueadas, otros ingresos, total del hotel— porque eso
 *  nunca se archivó. Pintar esas filas en cero diría que el hotel no tuvo
 *  otros ingresos, que es distinto de «no lo sabemos». */
type LecturaEnPantalla = PdfRoomStatsLectura & { desdeLaBase?: boolean };
type CalceComp = (p: { i: number; comoCelda: boolean }) => React.ReactElement;

export default function CierreRoomStatsPage() {
  const [escenarios, setEscenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useEscenarioDe(
    "month-end/room-stats", escenarios, "actual");

  const [vista, setVista] = useState<Vista>("habitacion");
  /** El mes donde va a guardar. Es una eleccion explicita y no algo que se
   *  deduzca del archivo: el guardado REEMPLAZA el mes entero, asi que quien
   *  sube tiene que ver de antemano cual va a pisar. El backend igual compara
   *  este mes contra el que declara el PDF y frena si no coinciden. */
  const [mesSel, setMesSel] = useState<number>(new Date().getMonth() + 1);
  /** ¿El usuario ya eligió mes a mano? Mientras no, el default se acomoda al
   *  primer mes que falta (ver el efecto más abajo). Después no se mueve más:
   *  un selector que salta solo mientras alguien lo usa es peor que un default
   *  imperfecto. */
  const mesTocado = useRef(false);
  const [lectura, setLectura] = useState<PdfRoomStatsLectura | null>(null);
  /** ¿El mes que está en pantalla ya se guardó en ESTA sesión? La lectura
   *  sigue viva —las cuatro vistas la usan— pero el botón no debe invitar a
   *  guardar de nuevo como si faltara.
   *
   *  ⚠️ No confundir con `guardado` (más abajo), que es lo que la BASE ya
   *  tiene para el mes elegido. Una cosa es «lo acabo de guardar yo», otra
   *  «esto es lo que hay archivado». */
  const [reciénGuardado, setReciénGuardado] = useState(false);
  const [calce, setCalce] = useState<Record<string, string>>({});
  const [abierta, setAbierta] = useState<Record<string, boolean>>({});
  const [categorias, setCategorias] = useState<{ name: string; units: number }[]>([]);
  /** Qué canal cuenta para el ADR, por código. Espejo de `market_codes`. */
  const [enAdr, setEnAdr] = useState<Record<string, boolean>>({});
  /** Código del PMS → canal. Vacío = todavía nadie lo decidió. */
  const [canalDe, setCanalDe] = useState<Record<string, string>>({});

  const [anio, setAnio] = useState<AnioRoomStats | null>(null);
  const [medida, setMedida] = useState<Medida>("ingreso");
  const [filas, setFilas] = useState<"habitacion" | "canal">("habitacion");

  const [leyendo, setLeyendo] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const archivo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getScenarios(HOTEL_ID).then(setEscenarios)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudieron cargar los escenarios"));
  }, []);

  /** El catálogo de categorías, del MISMO endpoint que la carga manual: así el
   *  desplegable no puede ofrecer un rótulo que el guardado no acepte. */
  useEffect(() => {
    if (!scenarioId || !lectura) return;
    let vivo = true;
    getRoomStatsEntry(scenarioId, lectura.month)
      .then(r => { if (vivo) setCategorias(r.rows.map(x => ({ name: x.room_type_name, units: x.units }))); })
      .catch(() => { if (vivo) setCategorias([]); });
    return () => { vivo = false; };
  }, [scenarioId, lectura]);

  const cargarAnio = useCallback(() => {
    if (!scenarioId) return;
    getAnioRoomStats(scenarioId).then(setAnio)
      .catch(e => setError(e instanceof Error ? e.message : "No se pudo cargar el año"));
  }, [scenarioId]);

  // El ano se carga con el escenario y no solo al abrir Acumulado: es de donde
  // sale saber si el mes elegido YA tiene estadistica guardada. Sin eso, el
  // selector no puede avisar que subir ahi reemplaza algo.
  useEffect(() => { cargarAnio(); }, [cargarAnio]);

  /** El default útil es el PRIMER MES SIN CARGAR, no el mes calendario.
   *
   *  Cerrar es completar lo que falta: con enero–agosto cargados el que sigue
   *  es septiembre, y con marzo faltando en medio el que sigue es marzo. El mes
   *  calendario acierta sólo cuando no hay atraso, y acá justamente se está
   *  llenando hacia atrás. Si están los doce, se queda donde estaba. */
  useEffect(() => {
    if (!anio || mesTocado.current) return;
    const falta = anio.meses.find(m => !m.cargado);
    if (falta) setMesSel(falta.month);
  }, [anio]);
  useEffect(() => { if (vista === "acumulado") cargarAnio(); }, [vista, cargarAnio]);

  /** La casilla del ADR también se conoce sin PDF.
   *
   *  ⚠️ `enAdr` sólo se llenaba al leer un archivo, y lo que falta se lee
   *  como `?? true`. Mirando un mes archivado eso decía que TODOS los canales
   *  entran al ADR —el CPL incluido— y la base filtrada salía igual a la del
   *  archivo, sin que nada avisara. Se siembra de lo guardado, y sin pisar lo
   *  que el usuario ya tocó en esta pantalla. */
  useEffect(() => {
    if (!anio) return;
    setEnAdr(prev => {
      const falta = anio.meses.flatMap(m => m.canales)
        .filter(c => !(c.canal_code in prev));
      if (!falta.length) return prev;
      return { ...prev, ...Object.fromEntries(
        falta.map(c => [c.canal_code, c.cuenta_para_kpis])) };
    });
    // El canal viaja en el mismo endpoint. Lo que el usuario ya eligió en
    // esta pantalla manda: `prev` va último.
    setCanalDe(prev => ({ ...Object.fromEntries(
      anio.meses.flatMap(m => m.canales).map(c => [c.canal_code, c.canal])), ...prev }));
  }, [anio]);

  const leer = useCallback(async (f: File) => {
    if (!scenarioId) { setError("Elegí primero la versión donde va el mes."); return; }
    setLeyendo(true); setError(null); setOk(null); setLectura(null); setReciénGuardado(false);
    try {
      const r = await leerPdfRoomStats(scenarioId, f, mesSel);
      setLectura(r);
      setCalce(Object.fromEntries(r.filas.map(x => [x.nombre_pdf, x.room_type_name ?? ""])));
      setEnAdr(Object.fromEntries(r.canales.map(c => [c.canal_code, c.cuenta_para_kpis])));
      setCanalDe(m => ({ ...Object.fromEntries(
        r.canales.map(c => [c.canal_code, c.canal])), ...m }));
      setAbierta({});
      if (vista === "acumulado") setVista("habitacion");
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo leer el PDF");
    } finally {
      setLeyendo(false);
      if (archivo.current) archivo.current.value = "";  // se puede volver a subir
    }
  }, [scenarioId, vista, mesSel]);

  /** La casilla del ADR. Se persiste al instante: es una decisión de la
   *  propiedad, no de este mes, y tiene que valer para todos los meses. */
  async function alternarAdr(code: string, cuenta: boolean) {
    setEnAdr(m => ({ ...m, [code]: cuenta }));   // optimista: la tabla responde ya
    try {
      await marcarCanalParaKpis(code, cuenta);
      if (anio) cargarAnio();
    } catch (e) {
      setEnAdr(m => ({ ...m, [code]: !cuenta }));  // se revierte si no guardó
      setError(e instanceof Error ? e.message : "No se pudo guardar el canal");
    }
  }

  /** A qué canal pertenece un código del PMS.
   *
   *  Se persiste al instante, igual que la casilla del ADR: es una decisión
   *  de la propiedad y no de este mes.
   *
   *  ⚠️ Esto NO mueve ninguna cifra guardada. Cambia a qué cubo de comisión
   *  rueda el código y, por ahí, el mix y el Net Rate — que es exactamente
   *  por qué un canal equivocado es caro: el total sigue cuadrando y nada
   *  avisa. Por eso vacío («— sin decidir —») es una opción legítima y no
   *  se propone ninguna por parecido del nombre. */
  async function elegirCanal(code: string, canal: string) {
    const antes = canalDe[code] ?? "";
    setCanalDe(m => ({ ...m, [code]: canal }));   // optimista
    try {
      await asignarCanalPms(code, canal);
      if (anio) cargarAnio();
    } catch (e) {
      setCanalDe(m => ({ ...m, [code]: antes }));  // se revierte si no guardó
      setError(e instanceof Error ? e.message : "No se pudo guardar el canal");
    }
  }

  /** El mes YA GUARDADO, con la forma de una lectura, para que las vistas
   *  no tengan que saber de dónde vino el dato.
   *
   *  ⚠️ Sin esto, cerrar un mes lo volvía invisible: las tres vistas sólo
   *  sabían pintar desde el PDF en memoria, así que al recargar la pantalla
   *  quedaban vacías aunque el mes estuviera archivado, y la única salida
   *  era volver a subir el archivo para MIRAR algo que ya estaba. */
  const guardadoComoLectura = useMemo<LecturaEnPantalla | null>(() => {
    const m = anio?.meses?.[mesSel - 1];
    if (!m || !m.cargado) return null;
    return {
      guardado: false, desdeLaBase: true,
      archivo: "", entidad: "", scenario_id: anio!.scenario_id,
      year: anio!.year, month: m.month, mes_nombre: MESES[m.month - 1],
      moneda: "USD", dias_del_mes: m.dias,
      filas: m.categorias.map(c => {
        const ags = m.canales.filter(x => x.room_type_name === c.room_type_name);
        return {
          nombre_pdf: c.room_type_name, room_type_name: c.room_type_name,
          room_type_code: "", confianza: "exacto" as const,
          units: c.units, nights_available: c.nights_available,
          nights_occupied: c.nights_occupied, pax: c.pax, revenue: c.revenue,
          adr: c.nights_occupied ? c.revenue / c.nights_occupied : 0,
          hab_entradas: 0, cli_entradas: 0,
          agencias: ags.map(a => ({
            agencia: a.canal_code, revenue: a.revenue,
            nights_occupied: a.nights_occupied, pax: a.pax,
            hab_entradas: 0, cli_entradas: 0,
            tarifa_promedio: a.nights_occupied ? a.revenue / a.nights_occupied : 0,
            canal_code: a.canal_code, canal: a.canal,
            canal_comision: a.canal_comision,
            cuenta_para_kpis: a.cuenta_para_kpis, conocido: a.conocido,
          })),
          actual_guardado: null,
        };
      }),
      canales: [...new Map(m.canales.map(a => [a.canal_code, a])).values()].map(a => ({
        agencia: a.canal_code, nights_occupied: 0, pax: 0, revenue: 0,
        hab_entradas: 0, cli_entradas: 0, adr: 0,
        canal_code: a.canal_code, canal: a.canal,
        canal_comision: a.canal_comision,
        cuenta_para_kpis: a.cuenta_para_kpis, conocido: a.conocido,
      })),
      categorias_sin_calce: [], categorias_ausentes_en_el_pdf: [],
      mes_ya_tiene_datos: true, avisos_de_cuadre: [],
      totales: { nights_occupied: 0, pax: 0, revenue: 0, adr: 0,
                 nights_available_config: 0 },
      // Nunca se archivó: se deja en cero y las vistas NO lo dibujan.
      resumen_pdf: {
        dias: m.dias, capacidad_hab: 0, habitaciones_totales: 0,
        habitaciones_disponibles: 0, habitaciones_bloqueadas: 0,
        ocupacion_sobre_total: 0, ocupacion_sobre_disponibles: 0,
        ingreso_hospedaje: 0, ingreso_puntos_venta: 0, ingreso_otros: 0,
        ingreso_total_hotel: 0,
      },
    };
  }, [anio, mesSel]);

  /** Lo que se está mirando: el PDF recién leído si lo hay, si no lo guardado. */
  const enPantalla: LecturaEnPantalla | null = lectura ?? guardadoComoLectura;

  /** A qué categoría va cada fila. Desde un PDF lo dice el calce; desde la
   *  base ya viene resuelto. */
  const destinoDe = useCallback((f: { nombre_pdf: string; room_type_name: string | null }) =>
    calce[f.nombre_pdf] || f.room_type_name || "", [calce]);

  // ── el mes en pantalla, agregado de una sola forma ────────────────────
  const mes = useMemo(() => {
    if (!enPantalla) return null;
    const canales = enPantalla.canales.map(c => c.canal_code);
    const porCat: T3[] = enPantalla.filas.map(f => [f.nights_occupied, f.pax, f.revenue]);
    const baseCat: T3[] = enPantalla.filas.map(f =>
      f.agencias.reduce<T3>((a, ag) => (enAdr[ag.canal_code] ?? ag.cuenta_para_kpis)
        ? mas(a, [ag.nights_occupied, ag.pax, ag.revenue]) : a, cero()));
    const porCan: T3[] = canales.map(code =>
      enPantalla.filas.reduce<T3>((a, f) => {
        const ag = f.agencias.find(x => x.canal_code === code);
        return ag ? mas(a, [ag.nights_occupied, ag.pax, ag.revenue]) : a;
      }, cero()));
    const total = porCat.reduce(mas, cero());
    const baseTot = baseCat.reduce(mas, cero());
    const disp = enPantalla.filas.map((f) => {
      const dest = destinoDe(f);
      return (categorias.find(c => c.name === dest)?.units ?? f.units)
        * enPantalla.dias_del_mes * (dest ? 1 : 0);
    });
    return { canales, porCat, baseCat, porCan, total, baseTot, disp,
             dispTot: disp.reduce((a, v) => a + v, 0),
             filtra: canales.some(c => !(enAdr[c] ?? true)) };
  }, [enPantalla, enAdr, destinoDe, categorias]);

  /** Lo que la base ya tiene en el mes elegido. Sale de `/anio/`, que es el
   *  MISMO endpoint que alimenta Acumulado — no una segunda fuente.
   *
   *  ⚠️ Solo los totales. La apertura por canal guardada existe, pero las tres
   *  vistas del mes se pintan con campos que solo trae el PDF —el rotulo del
   *  PMS, su resumen de ocupacion, los avisos de cuadre—, y rellenarlos con
   *  ceros haria que un mes guardado se lea como un mes sin ventas. Mientras
   *  esas vistas no sepan pintar sin archivo, aca se dice cuanto hay y no se
   *  finge el detalle. */
  const guardado = useMemo(() => {
    const m = anio?.meses?.[mesSel - 1];
    if (!m || !m.cargado) return null;
    const noches = m.categorias.reduce((a, c) => a + c.nights_occupied, 0);
    const pax = m.categorias.reduce((a, c) => a + c.pax, 0);
    const ingreso = m.categorias.reduce((a, c) => a + c.revenue, 0);
    const disp = m.categorias.reduce((a, c) => a + c.nights_available, 0);
    return { noches, pax, ingreso, disp, canales: m.canales.length };
  }, [anio, mesSel]);

  /** Los canales que la propiedad decidió dejar fuera.
   *
   *  Sale de `enAdr` —ya sembrado de lo guardado—, así que vale mirando un
   *  PDF, un mes archivado o el acumulado. Antes se sacaba de `mes`, que no
   *  existe en Acumulado: ahí el aviso nunca aparecía.
   *
   *  ⚠️ Antes el filtro sólo tocaba ocupación, ADR y RevPAR, y las columnas
   *  de noches, pax e ingreso seguían trayendo el canal. Eso dejaba dos bases
   *  MEZCLADAS en la misma fila: el ADR no se podía reconstruir dividiendo el
   *  ingreso de al lado entre las noches de al lado, y la diferencia se leía
   *  como un error de cálculo. Owner, 2026-09-10: «hay que sacar los CPL en
   *  todos los tabs una vez que se decide quitar el check». */
  const canalesFuera = useMemo(
    () => Object.entries(enAdr).filter(([, v]) => !v).map(([k]) => k).sort(),
    [enAdr]);

  /** Los códigos que el PMS trajo y todavía nadie clasificó. */
  const sinCanal = useMemo(() => {
    const vistos = new Set<string>([
      ...(anio?.meses ?? []).flatMap(m => m.canales.map(c => c.canal_code)),
      ...(enPantalla?.canales ?? []).map(c => c.canal_code),
    ]);
    return [...vistos].filter(c => !(canalDe[c] ?? "")).sort();
  }, [anio, enPantalla, canalDe]);

  const duplicadas = useMemo(() => {
    const c: Record<string, number> = {};
    Object.values(calce).forEach(v => { if (v) c[v] = (c[v] ?? 0) + 1; });
    return Object.entries(c).filter(([, k]) => k > 1).map(([v]) => v);
  }, [calce]);
  const faltanCalce = (lectura?.filas ?? []).filter(f => !calce[f.nombre_pdf]).length;
  const puedeGuardar = !!lectura && !leyendo && !guardando
    && faltanCalce === 0 && duplicadas.length === 0;

  async function guardar() {
    if (!lectura || !scenarioId) return;
    setGuardando(true); setError(null); setOk(null);
    try {
      const rows = lectura.filas.map(f => ({
        room_type_name: calce[f.nombre_pdf],
        units: categorias.find(c => c.name === calce[f.nombre_pdf])?.units ?? f.units,
        nights_occupied: f.nights_occupied, revenue: f.revenue, pax: f.pax,
      }));
      // La apertura por canal viaja con el mismo guardado: si se escribiera
      // aparte, el mix podría quedar describiendo un mes que ya cambió.
      const canales: RoomStatCanalIn[] = lectura.filas.flatMap(f =>
        f.agencias.map(a => ({
          room_type_name: calce[f.nombre_pdf], canal_code: a.canal_code,
          nights_occupied: a.nights_occupied, pax: a.pax, revenue: a.revenue,
        })));
      const r = await saveRoomStatsEntry(scenarioId, lectura.month, rows, canales);
      // El calce que se acaba de confirmar se RECUERDA para el mes que viene.
      // Va despues de guardar y en su propio try: que el alias no se pueda
      // escribir no puede tirar abajo un mes que ya entro bien.
      try {
        await guardarAliasPms(lectura.filas
          .filter(f => calce[f.nombre_pdf])
          .map(f => ({ room_type_name: calce[f.nombre_pdf], alias_pms: f.nombre_pdf })));
      } catch { /* el mes ya esta guardado; el alias se reintenta solo la proxima */ }
      setOk(`Guardado: ${lectura.mes_nombre} ${lectura.year} · ${r.rows_saved} categoría(s)`
            + `${r.canales_saved ? `, ${r.canales_saved} línea(s) de canal` : ""}. `
            + "El PDF no se almacenó.");
      // ⚠️ La lectura NO se descarta (owner, 2026-09-10: «tengo que subir 4
      // veces para que todos los tabs se actualicen»).
      //
      // Antes acá iba `setLectura(null)`, y al guardar las tres vistas del
      // mes —por canal, por habitación, el cruce— se quedaban vacías con un
      // cartel que decía «Subí el PDF de Abril para ver esta vista». O sea:
      // justo despues de revisar el mes, la pantalla lo escondia y parecia
      // pedir una subida por pestaña. Una sola lectura alimenta las cuatro y
      // tiene que seguir en pantalla despues de guardar; para limpiarla esta
      // el boton Descartar, que es una decision de quien mira.
      setReciénGuardado(true);
      // Se RECARGA el ano, no se descarta. Descartarlo dejaba la pantalla sin
      // saber que el mes recien guardado ya esta: el cartel del vacio no podia
      // decir cuanto hay, y el selector no podia avanzar al mes que sigue —
      // que es todo el punto cuando se cargan varios meses de corrido.
      cargarAnio();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally { setGuardando(false); }
  }

  async function bajarExcel() {
    const cuadros: Cuadro[] = [];
    // Baja lo que se está VIENDO: el PDF si lo hay, si no el mes guardado.
    // Atarlo a `lectura` dejaba el botón contestando «no hay nada leído»
    // con la tabla llena en pantalla.
    const src = enPantalla;
    if (src && mes) {
      cuadros.push({
        titulo: `Estadística de habitaciones · ${src.mes_nombre} ${src.year}`,
        subtitulo: src.desdeLaBase
          ? `Guardado en esta versión · ${src.moneda}`
          : `${src.entidad} · ${src.moneda} · leído de ${src.archivo}`,
        hoja: `Canal ${src.mes_nombre}`.slice(0, 31),
        columnas: [
          { label: "Canal", ancho: 30, formato: "texto" },
          { label: "Cuenta", ancho: 9, formato: "texto" },
          { label: "Noches", ancho: 12, formato: "num" },
          { label: "Pax", ancho: 10, formato: "num" },
          { label: "Ingreso", ancho: 16, formato: "usd2" },
          { label: "ADR", ancho: 14, formato: "usd2" },
        ],
        filas: [
          ...mes.canales.map((code, i) => ({
            label: code, valores: [(enAdr[code] ?? true) ? "Sí" : "No",
              mes.porCan[i][0], mes.porCan[i][1], mes.porCan[i][2],
              mes.porCan[i][0] ? mes.porCan[i][2] / mes.porCan[i][0] : 0],
          })),
          // El TOTAL es el de la pantalla —la base—, y debajo va la otra
          // para que la hoja se pueda cuadrar contra el PDF sin la app.
          { label: "TOTAL", es_total: true, valores: ["", mes.baseTot[0], mes.baseTot[1],
            mes.baseTot[2], mes.baseTot[0] ? mes.baseTot[2] / mes.baseTot[0] : 0] },
          ...(mes.filtra ? [{ label: "Con todos los canales (PDF)",
            valores: ["", mes.total[0], mes.total[1], mes.total[2],
                      mes.total[0] ? mes.total[2] / mes.total[0] : 0] }] : []),
        ],
      });
    }
    if (!cuadros.length) { setError("No hay nada leído para bajar."); return; }
    try { await bajarCuadros(`RoomStats_PMS_${src?.year}_${String(src?.month).padStart(2, "0")}`, cuadros); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo generar el Excel"); }
  }

  // ── el calce, visible sólo cuando hay algo que decidir ────────────────
  function Calce({ i, comoCelda }: { i: number; comoCelda: boolean }) {
    const f = enPantalla!.filas[i];
    const sel = destinoDe(f);
    // `alias` y `exacto` no piden nada: el primero porque alguien ya lo
    // decidio para esta propiedad, el segundo porque los nombres coinciden.
    const pide = !sel || (f.confianza !== "exacto" && f.confianza !== "alias");
    const rotulo = comoCelda ? (sel || "— sin categoría —") : f.nombre_pdf;
    return (
      <>
        <button onClick={() => setAbierta(a => ({ ...a, [f.nombre_pdf]: !a[f.nombre_pdf] }))}
          title={sel ? `Va a «${sel}» — clic para cambiar` : "Sin categoría — clic para elegir"}
          style={{ background: "none", border: "none", padding: 0, font: "inherit",
                   color: "inherit", cursor: "pointer",
                   borderBottom: `1px dotted ${pide ? "var(--negative)" : "var(--text-disabled)"}` }}>
          {rotulo}
        </button>
        {(pide || abierta[f.nombre_pdf]) && (
          <>
            <select value={sel} style={{ ...SEL, padding: "3px 6px", fontSize: 11,
                        width: "100%", marginTop: 4,
                        borderColor: sel ? "var(--border-medium)" : "var(--negative)" }}
              onChange={e => setCalce(c => ({ ...c, [f.nombre_pdf]: e.target.value }))}
              aria-label={`Categoría para ${f.nombre_pdf}`}>
              <option value="">— elegir —</option>
              {categorias.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            {!sel && <span style={{ display: "block", marginTop: 3, fontSize: 9.5,
                                    fontWeight: 600, textTransform: "uppercase",
                                    color: "var(--negative)" }}>sin calce</span>}
            {sel && f.confianza === "alias" && (
              <span style={{ display: "block", marginTop: 3, fontSize: 9.5, fontWeight: 600,
                             textTransform: "uppercase", color: "var(--positive)" }}>
                recordado
              </span>)}
            {sel && f.confianza === "probable" && (
              <span style={{ display: "block", marginTop: 3, fontSize: 9.5, fontWeight: 600,
                             textTransform: "uppercase", color: "var(--warning)" }}>
                por parecido
              </span>)}
          </>
        )}
      </>
    );
  }

  const pega: React.CSSProperties = {
    position: "sticky", left: 0, zIndex: 2, textAlign: "left",
    minWidth: 178, borderRight: "1px solid var(--border-medium)",
  };

  return (
    <div className="pag pag-ancha" style={{ padding: "14px 20px 34px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9,
                    flexWrap: "wrap", marginBottom: 12 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
          Estadística de habitaciones · PDF del PMS
        </h1>
        <select value={scenarioId} onChange={e => setScenarioId(e.target.value)}
                style={SEL} aria-label="Versión">
          {escenarios.map(s => (
            <option key={s.id} value={s.id}>{s.type} · {s.version} · {s.year}</option>
          ))}
        </select>
        <select value={mesSel}
                onChange={e => { mesTocado.current = true; setMesSel(Number(e.target.value)); }}
                style={SEL} aria-label="Mes" disabled={leyendo || !!lectura}
                title={lectura
                  ? "Hay un PDF leído en pantalla. Apretá Descartar para cambiar de mes: el calce de categorías es de este archivo y se perdería."
                  : "El mes donde se va a guardar. Subir reemplaza el mes entero."}>
          {MESES.map((n, i) => (
            <option key={i + 1} value={i + 1}>
              {n}{(anio?.meses_cargados ?? []).includes(i + 1) ? " · cargado" : ""}
            </option>
          ))}
        </select>
        <label style={{ ...SEL, cursor: leyendo ? "wait" : "pointer", fontWeight: 600,
                        background: "var(--brand)", color: "#fff", border: "none" }}>
          {leyendo ? "Leyendo…" : "Subir PDF"}
          <input ref={archivo} type="file" accept="application/pdf,.pdf" hidden
                 disabled={leyendo || !scenarioId}
                 onChange={e => { const f = e.target.files?.[0]; if (f) leer(f); }} />
        </label>
        {lectura && (
          <>
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>
              {lectura.mes_nombre} {lectura.year}
            </span>
            <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
              {lectura.entidad} · {lectura.moneda}
            </span>
            <span style={{ fontSize: 10.5, padding: "3px 8px", borderRadius: 4,
                           fontWeight: 600, textTransform: "uppercase",
                           background: lectura.avisos_de_cuadre.length
                             ? "rgba(185,58,46,.12)" : "rgba(20,107,92,.12)",
                           color: lectura.avisos_de_cuadre.length
                             ? "var(--negative)" : "var(--positive)" }}>
              {lectura.avisos_de_cuadre.length ? "No cuadra" : "Cuadra"}
            </span>
          </>
        )}
        {/* Sin PDF en pantalla pero con el mes archivado: se dice de dónde
            salen los números, porque el cuadre contra el archivo ya no
            se puede rehacer desde acá. */}
        {!lectura && enPantalla?.desdeLaBase && (
          <>
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>
              {enPantalla.mes_nombre} {enPantalla.year}
            </span>
            <span style={{ fontSize: 10.5, padding: "3px 8px", borderRadius: 4,
                           fontWeight: 600, textTransform: "uppercase",
                           background: "rgba(20,107,92,.12)", color: "var(--positive)" }}>
              Guardado
            </span>
          </>
        )}
      </div>

      {error && <Aviso tono="err">{error}</Aviso>}
      {ok && <Aviso tono="ok">{ok}</Aviso>}
      {sinCanal.length > 0 && (
        <Aviso tono="info">
          <b>{sinCanal.length === 1 ? "Un código del PMS no tiene canal"
              : `${sinCanal.length} códigos del PMS no tienen canal`}</b>{" "}
          ({sinCanal.join(" · ")}). Se guardan y se ven acá igual, pero no
          ruedan al mix de canales ni al Net Rate hasta que se les asigne uno.
          Se elige en la vista <b>Por canal</b>, en la columna «Canal».{" "}
          No se adivina: el canal decide si ese ingreso paga comisión.
        </Aviso>
      )}
      {canalesFuera.length > 0 && (
        <Aviso tono="warn">
          <b>{canalesFuera.join(" · ")}</b>{" "}
          {canalesFuera.length > 1 ? "no cuentan" : "no cuenta"}: los números de
          las cuatro vistas {canalesFuera.length > 1 ? "los" : "lo"} excluyen —
          noches, pax, ingreso, ocupación, ADR y RevPAR.{" "}
          <b>Lo que se guarda no cambia:</b> a la base van las cifras del archivo,
          y la fila «Con todos los canales (PDF)» de cada cuadro las muestra para
          poder cuadrar contra el PMS.
        </Aviso>
      )}
      {lectura?.avisos_de_cuadre.length ? (
        <Aviso tono="err">
          <b>El archivo y lo leído no cuadran.</b> No guardes esto sin revisar el PDF:
          <ul style={{ margin: "6px 0 0 18px" }}>
            {lectura.avisos_de_cuadre.map(a => <li key={a}>{a}</li>)}
          </ul>
        </Aviso>
      ) : null}
      {lectura?.mes_ya_tiene_datos && (
        <Aviso tono="warn">
          {lectura.mes_nombre} ya tiene estadística en esta versión. Guardar
          <b> reemplaza el mes completo</b>.
        </Aviso>
      )}

      {/* sub-tabs */}
      <div role="tablist" style={{ display: "flex", gap: 2, alignItems: "flex-end",
                                   borderBottom: "1px solid var(--border-medium)" }}>
        {([["canal", "Por canal"], ["habitacion", "Por habitación"],
           ["matriz", "Canal × habitación"], ["acumulado", "Acumulado"]] as [Vista, string][])
          .map(([k, r]) => (
          <button key={k} role="tab" aria-selected={vista === k} onClick={() => setVista(k)}
            style={{ background: "none", border: "none", padding: "7px 15px",
                     font: "inherit", fontSize: 12.5, cursor: "pointer", marginBottom: -1,
                     color: vista === k ? "var(--text-primary)" : "var(--text-secondary)",
                     fontWeight: vista === k ? 600 : 400,
                     borderBottom: `2px solid ${vista === k ? "var(--brand)" : "transparent"}` }}>
            {r}
          </button>
        ))}
        {vista === "acumulado" && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 7, paddingBottom: 4 }}>
            <select value={medida} onChange={e => setMedida(e.target.value as Medida)}
                    style={{ ...SEL, padding: "4px 8px", fontSize: 12 }} aria-label="Medida">
              {(filas === "canal" ? MEDIDAS_CANAL : MEDIDAS).map(([k, r]) =>
                <option key={k} value={k}>{r}</option>)}
            </select>
            <select value={filas} onChange={e => {
                      const v = e.target.value as "habitacion" | "canal";
                      setFilas(v);
                      if (v === "canal" && (medida === "ocupacion" || medida === "revpar"))
                        setMedida("ingreso");
                    }}
                    style={{ ...SEL, padding: "4px 8px", fontSize: 12 }} aria-label="Filas">
              <option value="habitacion">por habitación</option>
              <option value="canal">por canal</option>
            </select>
          </div>
        )}
      </div>

      <div className="fin-scroll-x"
           style={{ border: "1px solid var(--border-medium)", borderTop: "none",
                    borderRadius: "0 0 8px 8px", overflowX: "auto",
                    background: "var(--bg-surface)" }}>
        {vista === "acumulado"
          ? <Acumulado anio={anio} medida={medida} filas={filas} enAdr={enAdr} pega={pega} />
          : !enPantalla
            ? <div style={{ padding: "26px 16px", fontSize: 12.5,
                            color: "var(--text-secondary)" }}>
                <p style={{ margin: 0 }}>
                  Subí el PDF de <strong>{MESES[mesSel - 1]}</strong> para ver esta
                  vista. El acumulado del año se puede mirar sin subir nada.
                </p>
                {guardado ? (
                  <p style={{ margin: "9px 0 0" }}>
                    {MESES[mesSel - 1]} <strong>ya tiene estadística guardada</strong>:{" "}
                    {guardado.noches.toLocaleString("es-CR")} noches ·{" "}
                    {guardado.pax.toLocaleString("es-CR")} pax ·{" "}
                    {usd(guardado.ingreso)}
                    {guardado.noches ? ` · ADR ${usd(guardado.ingreso / guardado.noches)}` : ""}
                    {guardado.canales ? ` · ${guardado.canales} fila(s) por canal` : " · sin apertura por canal"}.
                    {" "}Subir el PDF de este mes <strong>reemplaza</strong> eso.
                  </p>
                ) : (
                  <p style={{ margin: "9px 0 0" }}>
                    {MESES[mesSel - 1]} todavía no tiene estadística en esta versión.
                  </p>
                )}
              </div>
            : vista === "canal"   ? <PorCanal {...{ mes: mes!, enAdr, alternarAdr,
                                                    canalDe, elegirCanal, pega }} />
            : vista === "matriz"  ? <Matriz {...{ lectura: enPantalla, mes: mes!, enAdr, pega, Calce }} />
            :                       <PorHabitacion {...{ lectura: enPantalla, mes: mes!, pega, Calce }} />}
      </div>

      {enPantalla && (
        <div style={{ marginTop: 13, display: "flex", gap: 9, alignItems: "center",
                      flexWrap: "wrap" }}>
          {/* Guardar solo tiene sentido con un PDF leído: mirando lo archivado
              no hay nada nuevo que escribir. */}
          {lectura && <button onClick={guardar} disabled={!puedeGuardar}
            style={{ ...SEL, padding: "8px 16px", fontWeight: 600,
                     cursor: puedeGuardar ? "pointer" : "not-allowed",
                     background: !puedeGuardar ? "var(--bg-elevated)"
                                 : reciénGuardado ? "var(--bg-surface)" : "var(--positive)",
                     border: reciénGuardado && puedeGuardar ? "1px solid var(--border-medium)" : "none",
                     color: !puedeGuardar ? "var(--text-disabled)"
                            : reciénGuardado ? "var(--text-secondary)" : "#fff" }}>
            {guardando ? "Guardando…"
             : reciénGuardado ? `✓ ${lectura.mes_nombre} guardado — volver a guardar`
             : `Guardar ${lectura.mes_nombre} ${lectura.year}`}
          </button>}
          <button onClick={bajarExcel} style={{ ...SEL, cursor: "pointer", fontWeight: 600,
                    border: "none", background: "var(--accent-excel)", color: "#fff" }}>
            ⬇ Excel
          </button>
          {lectura && <button onClick={() => { setLectura(null); setReciénGuardado(false); setOk(null); setError(null); }}
                  style={{ ...SEL, cursor: "pointer" }}>Descartar</button>}
          {enPantalla.desdeLaBase && (
            <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
              Mostrando lo guardado de {enPantalla.mes_nombre}. Para cambiarlo,
              subí el PDF de ese mes.
            </span>)}
          <span style={{ fontSize: 11.5, color: "var(--negative)" }}>
            {duplicadas.length ? `Dos categorías van a «${duplicadas[0]}» — una pisaría a la otra.`
             : faltanCalce ? `${faltanCalce} categoría(s) sin calce en Master Data${
                 vista === "canal" ? " — miralo en «Por habitación»" : ""}.`
             : ""}
          </span>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── Vista 1 · Por canal ────────────────────────── */
function PorCanal({ mes, enAdr, alternarAdr, canalDe, elegirCanal, pega }: {
  mes: MesAgregado; enAdr: MapaAdr;
  alternarAdr: (code: string, cuenta: boolean) => void;
  canalDe: Record<string, string>;
  elegirCanal: (code: string, canal: string) => void;
  pega: React.CSSProperties;
}) {
  const { canales, porCan, total, baseTot, filtra } = mes;
  return (
    <table style={{ borderCollapse: "separate", borderSpacing: 0, minWidth: "100%" }}>
      <thead>
        <tr>
          <th style={{ ...TH, ...pega, textAlign: "left", background: "var(--bg-elevated)" }}>Canal</th>
          <th style={{ ...TH, textAlign: "center", width: 62 }}
              title="Marcado = este canal cuenta para ocupación, ADR y RevPAR">Cuenta</th>
          <th style={{ ...TH, textAlign: "left", width: 150 }}
              title="A qué canal pertenece este código del PMS. Define si el ingreso paga comisión.">
            Canal
          </th>
          <th style={TH}>Noches</th><th style={TH}>% noches</th>
          <th style={TH}>Pax</th>
          <th style={TH}>Ingreso</th><th style={TH}>% ingreso</th>
          <th style={TH}>ADR</th>
        </tr>
      </thead>
      <tbody>
        {canales.map((code, i) => {
          const [no, pa, ing] = porCan[i];
          const dentro = enAdr[code] ?? true;
          // El reparto se lee sobre la BASE: un canal excluido no tiene
          // parte de un total del que no forma parte, y darle una haría que
          // las de los demás no sumen 100.
          const pn = dentro && baseTot[0] ? no / baseTot[0] * 100 : 0;
          const pi = dentro && baseTot[2] ? ing / baseTot[2] * 100 : 0;
          const tenue = dentro ? {} : { color: "var(--text-disabled)" };
          return (
            <tr key={code}>
              <td style={{ ...TD, ...pega, ...tenue, background: "var(--bg-surface)",
                           fontStyle: dentro ? "normal" : "italic",
                           boxShadow: dentro ? undefined : "inset 3px 0 0 var(--warning)" }}>
                {code}
              </td>
              <td style={{ ...TD, textAlign: "center" }}>
                <input type="checkbox" checked={dentro}
                  onChange={e => alternarAdr(code, e.target.checked)}
                  aria-label={`Incluir ${code} en los indicadores`}
                  style={{ width: 14, height: 14, accentColor: "var(--brand)", cursor: "pointer" }} />
              </td>
              <td style={{ ...TD, textAlign: "left" }}>
                <select value={canalDe[code] ?? ""}
                  onChange={e => elegirCanal(code, e.target.value)}
                  aria-label={`Canal de ${code}`}
                  style={{ ...SEL, padding: "3px 6px", fontSize: 11, width: "100%",
                           borderColor: (canalDe[code] ?? "")
                             ? "var(--border-medium)" : "var(--warning)" }}>
                  <option value="">— sin decidir —</option>
                  {CANALES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </td>
              <td style={{ ...TD, ...tenue }}>{n(no)}</td>
              <td style={{ ...TD, ...tenue, position: "relative" }}>
                <i style={{ position: "absolute", left: 0, bottom: 3, height: 3,
                            width: `${pn.toFixed(1)}%`, borderRadius: 2,
                            background: dentro ? "rgba(36,83,196,.16)" : "rgba(99,92,83,.14)" }} />
                <span style={{ position: "relative" }}>{dentro ? pct(pn) : "—"}</span>
              </td>
              <td style={{ ...TD, ...tenue }}>{n(pa)}</td>
              <td style={{ ...TD, ...tenue }}>{usd(ing)}</td>
              <td style={{ ...TD, ...tenue, position: "relative" }}>
                <i style={{ position: "absolute", left: 0, bottom: 3, height: 3,
                            width: `${pi.toFixed(1)}%`, borderRadius: 2,
                            background: dentro ? "rgba(36,83,196,.16)" : "rgba(99,92,83,.14)" }} />
                <span style={{ position: "relative" }}>{dentro ? pct(pi) : "—"}</span>
              </td>
              <td style={{ ...TD, ...tenue }}>{no ? usd(ing / no) : "—"}</td>
            </tr>
          );
        })}
        <Total celdas={["TOTAL", "", "", n(baseTot[0]), pct(100), n(baseTot[1]),
                        usd(baseTot[2]), pct(100), adrDe(baseTot)]} pega={pega} />
        {/* ⚠️ La única fila con la otra base. Sin ella el cuadre contra el PDF
            no se puede hacer desde la pantalla, y el total filtrado se lee
            como si el archivo dijera eso. */}
        {filtra && (
          <Stat celdas={["Con todos los canales (PDF)", "", "", n(total[0]), "",
                         n(total[1]), usd(total[2]), "", adrDe(total)]}
                pega={pega} primera />
        )}
      </tbody>
    </table>
  );
}

/* ──────────────────────── Vista 2 · Por habitación ──────────────────────── */
function PorHabitacion({ lectura, mes, pega, Calce }: {
  lectura: LecturaEnPantalla; mes: MesAgregado;
  pega: React.CSSProperties; Calce: CalceComp;
}) {
  const { baseCat, total, baseTot, disp, dispTot, filtra } = mes;
  const r = lectura.resumen_pdf;
  return (
    <table style={{ borderCollapse: "separate", borderSpacing: 0, minWidth: "100%" }}>
      <thead>
        <tr>
          <th style={{ ...TH, ...pega, textAlign: "left", background: "var(--bg-elevated)" }}>
            Categoría (PDF)
          </th>
          <th style={{ ...TH, textAlign: "left" }}>Va a (Master Data)</th>
          <th style={TH}>Noches disp.</th><th style={TH}>Noches ocup.</th>
          <th style={TH}>% Ocup.</th><th style={TH}>Pax</th>
          <th style={TH}>Ingreso</th><th style={TH}>ADR</th>
          <th style={TH}>RevPAR</th><th style={TH}>Ya guardado</th>
        </tr>
      </thead>
      <tbody>
        {lectura.filas.map((f, i) => {
          // ⚠️ La fila entera va sobre la BASE. Con `porCat` acá y `baseCat`
          // en las tasas, el ADR de la fila no salía de dividir el ingreso de
          // al lado entre las noches de al lado.
          const [no, pa, ing] = baseCat[i];
          const d = disp[i];
          return (
            <tr key={f.nombre_pdf}>
              <td style={{ ...TD, ...pega, background: "var(--bg-surface)", fontWeight: 500 }}>
                {f.nombre_pdf}
              </td>
              <td style={{ ...TD, textAlign: "left" }}><Calce i={i} comoCelda /></td>
              <td style={{ ...TD, color: d ? undefined : "var(--text-disabled)" }}>
                {d ? n(d) : "—"}
              </td>
              <td style={TD}>{n(no)}</td>
              <td style={TD}>{d ? pct(baseCat[i][0] / d * 100) : "—"}</td>
              <td style={TD}>{n(pa)}</td>
              <td style={TD}>{usd(ing)}</td>
              <td style={TD}>{adrDe(baseCat[i])}</td>
              <td style={TD}>{d ? usd(baseCat[i][2] / d) : "—"}</td>
              <td style={{ ...TD, color: "var(--text-secondary)", fontSize: 11.5 }}>
                {f.actual_guardado
                  ? `${n(f.actual_guardado.nights_occupied)} n · ${usd(f.actual_guardado.revenue)}`
                  : "—"}
              </td>
            </tr>
          );
        })}
        <Total pega={pega} celdas={["TOTAL", "", n(dispTot), n(baseTot[0]),
          dispTot ? pct(baseTot[0] / dispTot * 100) : "—", n(baseTot[1]), usd(baseTot[2]),
          adrDe(baseTot), dispTot ? usd(baseTot[2] / dispTot) : "—", ""]} />
        {/* ⚠️ Las dos bases juntas: sin esta fila, la ocupación de la pantalla
            y la del PDF no se pueden conciliar y una de las dos parece un error. */}
        {filtra && (
          <Stat pega={pega} primera celdas={["Con todos los canales (PDF)", "",
            n(dispTot), n(total[0]),
            dispTot ? pct(total[0] / dispTot * 100) : "—", n(total[1]), usd(total[2]),
            adrDe(total), dispTot ? usd(total[2] / dispTot) : "—", ""]} />
        )}
        {/* El PDF no abre estas por categoría: son del hotel. */}
        {/* ⚠️ Estas salen del resumen del PDF y NO se archivan. Mirando un
            mes guardado no existen, y dibujarlas en cero diría que el hotel
            no tuvo otros ingresos — que es distinto de «no lo sabemos». */}
        {!lectura.desdeLaBase && <>
          <Stat pega={pega} celdas={["Habitaciones-noche (inventario)", "",
            n(r.habitaciones_totales), "", "", "", "", "", "", ""]} />
          <Stat pega={pega} celdas={["Habitaciones disponibles", "",
            n(r.habitaciones_disponibles), "", "", "", "", "", "", ""]} />
          <Stat pega={pega} celdas={["Habitaciones bloqueadas", "",
            n(r.habitaciones_bloqueadas), "", "", "", "", "", "", ""]} />
          <Stat pega={pega} celdas={["% Ocupación s/ disponibles", "", "",
            "", pct(r.ocupacion_sobre_disponibles), "", "", "", "", ""]} />
          <Stat pega={pega} celdas={["Otros ingresos", "", "", "", "", "",
            usd(r.ingreso_otros), "", "", ""]} />
          <Stat pega={pega} celdas={["Ingreso total del hotel", "", "", "", "", "",
            usd(r.ingreso_total_hotel), "", "", ""]} />
        </>}
      </tbody>
    </table>
  );
}

/* ─────────────────── Vista 3 · Canal × habitación ───────────────────────── */
function Matriz({ lectura, mes, enAdr, pega, Calce }: {
  lectura: LecturaEnPantalla; mes: MesAgregado;
  enAdr: MapaAdr; pega: React.CSSProperties; Calce: CalceComp;
}) {
  const { canales, porCat, baseCat, total, baseTot, filtra } = mes;
  const MED = ["Noches", "Pax", "Ingreso", "ADR"];
  const g0 = { borderLeft: "1px solid var(--border-medium)" };

  const celdas = (v: T3 | null, base?: T3, tot = false) => {
    const f = tot ? { background: "rgba(36,83,196,.045)" } : {};
    if (!v) return [0, 1, 2, 3].map(i =>
      <td key={i} style={{ ...TD, ...(i === 0 ? g0 : {}), ...f, color: "var(--text-disabled)" }}>—</td>);
    const [no, pa, ing] = v;
    return [
      <td key="n" style={{ ...TD, ...g0, ...f }}>{n(no)}</td>,
      <td key="p" style={{ ...TD, ...f }}>{n(pa)}</td>,
      <td key="i" style={{ ...TD, ...f }}>{usd(ing)}</td>,
      <td key="a" style={{ ...TD, ...f }}>{adrDe(base ?? v)}</td>,
    ];
  };

  return (
    <table style={{ borderCollapse: "separate", borderSpacing: 0, minWidth: "100%" }}>
      <thead>
        <tr>
          <th rowSpan={2} style={{ ...TH, ...pega, textAlign: "left", verticalAlign: "bottom",
                                   background: "var(--bg-elevated)" }}>Canal</th>
          {lectura.filas.map((f, i) => (
            <th key={f.nombre_pdf} colSpan={4}
                style={{ ...TH, ...g0, textAlign: "center", fontSize: 11,
                         color: "var(--text-primary)", textTransform: "none",
                         letterSpacing: ".03em" }}>
              <Calce i={i} comoCelda={false} />
            </th>
          ))}
          <th colSpan={4} style={{ ...TH, ...g0, textAlign: "center", fontSize: 11,
                                   color: "var(--text-primary)", background: "#E3E7F1" }}>
            TOTAL
          </th>
        </tr>
        <tr>
          {[...lectura.filas, null].map((_, g) => MED.map((m, i) => (
            <th key={`${g}-${m}`} style={{ ...TH, ...(i === 0 ? g0 : {}) }}>{m}</th>
          )))}
        </tr>
      </thead>
      <tbody>
        {canales.map((code) => {
          const dentro = enAdr[code] ?? true;
          const fila = lectura.filas.reduce<T3>((a, f) => {
            const ag = f.agencias.find(x => x.canal_code === code);
            return ag ? mas(a, [ag.nights_occupied, ag.pax, ag.revenue]) : a;
          }, cero());
          return (
            <tr key={code}>
              <td style={{ ...TD, ...pega, background: "var(--bg-surface)", fontWeight: 500,
                           fontStyle: dentro ? "normal" : "italic",
                           color: dentro ? undefined : "var(--text-secondary)",
                           boxShadow: dentro ? undefined : "inset 3px 0 0 var(--warning)" }}>
                {code}
              </td>
              {lectura.filas.map((f) => {
                const ag = f.agencias.find(x => x.canal_code === code);
                return (
                  <Fragment key={`${code}-${f.nombre_pdf}`}>
                    {celdas(ag ? [ag.nights_occupied, ag.pax, ag.revenue] : null)}
                  </Fragment>
                );
              })}
              <Fragment key={`${code}-tot`}>{celdas(fila, undefined, true)}</Fragment>
            </tr>
          );
        })}
        <tr>
          <td style={{ ...TD, ...pega, fontWeight: 700, background: "var(--bg-elevated)",
                       borderTop: "2px solid var(--border-medium)" }}>TOTAL</td>
          {baseCat.map((v, g) => (
            <Fragment key={g}>{celdas(v)}</Fragment>
          ))}
          <Fragment>{celdas(baseTot, undefined, true)}</Fragment>
        </tr>
        {/* La otra base, para cuadrar contra el archivo. Las filas de arriba
            ya muestran el canal excluido; esto dice cuánto suma. */}
        {filtra && (
          <tr>
            <td style={{ ...TD, ...pega, background: "var(--bg-elevated)",
                         color: "var(--text-secondary)", fontSize: 12 }}>
              Con todos los canales (PDF)
            </td>
            {porCat.map((v, g) => (
              <Fragment key={g}>{celdas(v)}</Fragment>
            ))}
            <Fragment>{celdas(total, undefined, true)}</Fragment>
          </tr>
        )}
      </tbody>
    </table>
  );
}

/* ─────────────────────────── Vista 4 · Acumulado ────────────────────────── */
function Acumulado({ anio, medida, filas, enAdr, pega }: {
  anio: AnioRoomStats | null; medida: Medida;
  filas: "habitacion" | "canal"; enAdr: MapaAdr; pega: React.CSSProperties;
}) {
  if (!anio) {
    return <p style={{ padding: "26px 16px", margin: 0, fontSize: 12.5,
                       color: "var(--text-secondary)" }}>Cargando el año…</p>;
  }
  if (!anio.meses_cargados.length) {
    return <p style={{ padding: "26px 16px", margin: 0, fontSize: 12.5,
                       color: "var(--text-secondary)" }}>
      Esta versión todavía no tiene ningún mes de estadística guardado.
    </p>;
  }
  if (filas === "canal" && !anio.hay_apertura_por_canal) {
    return <p style={{ padding: "26px 16px", margin: 0, fontSize: 12.5,
                       color: "var(--text-secondary)" }}>
      Los meses guardados no traen apertura por canal — se cargaron a mano o antes
      de que el detalle se guardara. Volvé a subir el PDF de esos meses para verlos
      por canal.
    </p>;
  }

  const dentro = (c: { canal_code: string; cuenta_para_kpis: boolean }) =>
    enAdr[c.canal_code] ?? c.cuenta_para_kpis;
  const fuera = [...new Set(anio.meses.flatMap(m => m.canales)
    .filter(c => !dentro(c)).map(c => c.canal_code))];

  /** Filas de la dimensión elegida, en orden estable. */
  const claves: string[] = filas === "canal"
    ? [...new Set(anio.meses.flatMap(m => m.canales.map(c => c.canal_code)))]
    : anio.room_types.map(r => r.name);

  /** Los ingredientes de un mes para una fila. `null` = mes sin cargar. */
  function celda(m: AnioMes, clave: string): Ingredientes | null {
    if (!m.cargado) return null;
    let tot = cero(), base = cero(), disp = 0;
    if (filas === "canal") {
      m.canales.filter(c => c.canal_code === clave).forEach(c => {
        tot = mas(tot, [c.nights_occupied, c.pax, c.revenue]);
      });
      // La fila ES el canal: se muestra entera aunque esté excluida —para eso
      // se mira esta vista, para ver cuánto es lo que se sacó. Lo que NO lo
      // incluye es el TOTAL de abajo (ver `totalMes`).
      base = tot;
    } else {
      m.categorias.filter(c => c.room_type_name === clave).forEach(c => {
        tot = mas(tot, [c.nights_occupied, c.pax, c.revenue]);
        disp += c.nights_available;
      });
      const abre = m.canales.filter(c => c.room_type_name === clave);
      // ⚠️ Sin apertura no se puede filtrar el ADR: se usa el total y se dice.
      // Descontar «lo que suele ser cortesía» sería inventar un número.
      base = abre.length
        ? abre.reduce<T3>((a, c) => dentro(c)
            ? mas(a, [c.nights_occupied, c.pax, c.revenue]) : a, cero())
        : tot;
    }
    return { tot, base, disp };
  }

  function totalMes(m: AnioMes): Ingredientes | null {
    if (!m.cargado) return null;
    let tot = cero(), base = cero(), disp = 0;
    m.categorias.forEach(c => {
      tot = mas(tot, [c.nights_occupied, c.pax, c.revenue]);
      disp += c.nights_available;
    });
    base = m.canales.length
      ? m.canales.reduce<T3>((a, c) => dentro(c)
          ? mas(a, [c.nights_occupied, c.pax, c.revenue]) : a, cero())
      : tot;
    return { tot, base, disp };
  }

  /** ⚠️ Las SEIS medidas van sobre la BASE, no sólo las tres tasas.
   *
   *  Un canal que no cuenta no cuenta en ninguna: mostrar las noches con el
   *  canal adentro y el ADR con el canal afuera dejaba dos bases en la misma
   *  columna, y el ADR no se podía reconstruir de las celdas de al lado. */
  const valor = (c: Ingredientes | null) => {
    if (!c) return null;
    switch (medida) {
      case "noches":    return n(c.base[0]);
      case "pax":       return n(c.base[1]);
      case "ingreso":   return usd(c.base[2]);
      case "adr":       return adrDe(c.base);
      case "ocupacion": return c.disp ? pct(c.base[0] / c.disp * 100) : "—";
      case "revpar":    return c.disp ? usd(c.base[2] / c.disp) : "—";
    }
  };

  /** ⚠️ El YTD de una TASA se recalcula sobre los totales, nunca promediando
   *  los meses: un mes de 20 noches pesaría igual que uno de 150. */
  const acumular = (celdas: (Ingredientes | null)[]): Ingredientes =>
    celdas.filter((c): c is Ingredientes => !!c).reduce<Ingredientes>(
      (a, c) => ({ tot: mas(a.tot, c.tot), base: mas(a.base, c.base),
                   disp: a.disp + c.disp }),
      { tot: cero(), base: cero(), disp: 0 });

  const ultimo = anio.meses_cargados[anio.meses_cargados.length - 1];
  const rayado = {
    background: "repeating-linear-gradient(135deg, transparent, transparent 5px,"
      + " rgba(99,92,83,.055) 5px, rgba(99,92,83,.055) 10px)",
  };
  const ytdCol = { background: "#E3E7F1", fontWeight: 600 };

  return (
    <table style={{ borderCollapse: "separate", borderSpacing: 0, minWidth: "100%" }}>
      <thead>
        <tr>
          <th style={{ ...TH, ...pega, textAlign: "left", background: "var(--bg-elevated)" }}>
            {filas === "canal" ? "Canal" : "Categoría"}
          </th>
          {anio.meses.map(m => (
            <th key={m.month} style={{ ...TH, ...(m.cargado ? {} : rayado) }}>
              {MES3[m.month - 1]}
            </th>
          ))}
          <th style={{ ...TH, ...ytdCol, borderLeft: "1px solid var(--border-medium)" }}>
            YTD {MES3[ultimo - 1]}
          </th>
        </tr>
      </thead>
      <tbody>
        {claves.map(clave => {
          const cs = anio.meses.map(m => celda(m, clave));
          // Un canal fuera de la base se marca igual que en las otras vistas:
          // sus cifras son reales pero NO están en el TOTAL de abajo.
          const afuera = filas === "canal" && fuera.includes(clave);
          return (
            <tr key={clave}>
              <td style={{ ...TD, ...pega, background: "var(--bg-surface)", fontWeight: 500,
                           fontStyle: afuera ? "italic" : "normal",
                           color: afuera ? "var(--text-secondary)" : undefined,
                           boxShadow: afuera ? "inset 3px 0 0 var(--warning)" : undefined }}>
                {clave}{afuera ? " · fuera" : ""}
              </td>
              {cs.map((c, i) => (
                <td key={i} style={{ ...TD, ...(c ? {} : rayado) }}>{valor(c) ?? ""}</td>
              ))}
              <td style={{ ...TD, ...ytdCol, borderLeft: "1px solid var(--border-medium)" }}>
                {valor(acumular(cs))}
              </td>
            </tr>
          );
        })}
        {(() => {
          const ts = anio.meses.map(totalMes);
          const ytd = acumular(ts);
          const pie = (rotulo: string, fn: (c: Ingredientes) => string) => (
            <tr key={rotulo}>
              <td style={{ ...TD, ...pega, background: "var(--bg-elevated)",
                           color: "var(--text-secondary)", fontSize: 12 }}>{rotulo}</td>
              {ts.map((c, i) => (
                <td key={i} style={{ ...TD, background: "var(--bg-elevated)",
                                     color: "var(--text-secondary)", ...(c ? {} : rayado) }}>
                  {c ? fn(c) : ""}
                </td>
              ))}
              <td style={{ ...TD, background: "#E9ECF4", fontWeight: 600,
                           borderLeft: "1px solid var(--border-medium)" }}>{fn(ytd)}</td>
            </tr>
          );
          return (
            <>
              <tr>
                <td style={{ ...TD, ...pega, fontWeight: 700, background: "var(--bg-elevated)",
                             borderTop: "2px solid var(--border-medium)" }}>TOTAL</td>
                {ts.map((c, i) => (
                  <td key={i} style={{ ...TD, fontWeight: 700, background: "var(--bg-elevated)",
                                       borderTop: "2px solid var(--border-medium)",
                                       ...(c ? {} : rayado) }}>{valor(c) ?? ""}</td>
                ))}
                <td style={{ ...TD, background: "#D6DCEB", fontWeight: 700,
                             borderTop: "2px solid var(--border-medium)",
                             borderLeft: "1px solid var(--border-medium)" }}>
                  {valor(ytd)}
                </td>
              </tr>
              {pie("Noches disponibles", c => n(c.disp))}
              {pie("Noches ocupadas", c => n(c.base[0]))}
              {pie("% Ocupación", c => c.disp ? pct(c.base[0] / c.disp * 100) : "—")}
              {pie("Ingreso", c => usd(c.base[2]))}
              {pie("ADR", c => adrDe(c.base))}
              {pie("RevPAR", c => c.disp ? usd(c.base[2] / c.disp) : "—")}
              {/* La otra base, en una línea: es el cuadre contra el PMS. */}
              {fuera.length > 0 && pie("Con todos los canales (PDF)",
                c => `${n(c.tot[0])} n · ${usd(c.tot[2])} · ADR ${adrDe(c.tot)}`)}
            </>
          );
        })()}
      </tbody>
    </table>
  );
}

/* ─────────────────────────────── piezas ─────────────────────────────────── */
function Total({ celdas, pega }: { celdas: string[]; pega: React.CSSProperties }) {
  return (
    <tr>
      {celdas.map((c, i) => (
        <td key={i} style={{ ...TD, fontWeight: 700, background: "var(--bg-elevated)",
                             borderTop: "2px solid var(--border-medium)",
                             ...(i === 0 ? { ...pega, textAlign: "left" } : {}) }}>
          {c}
        </td>
      ))}
    </tr>
  );
}

function Stat({ celdas, pega, primera }: {
  celdas: string[]; pega: React.CSSProperties; primera?: boolean;
}) {
  return (
    <tr>
      {celdas.map((c, i) => (
        <td key={i} style={{ ...TD, background: "var(--bg-elevated)",
                             color: "var(--text-secondary)",
                             ...(primera ? { borderTop: "2px solid var(--border-medium)" } : {}),
                             ...(i === 0 ? { ...pega, textAlign: "left", fontSize: 12 } : {}) }}>
          {c}
        </td>
      ))}
    </tr>
  );
}

function Aviso({ tono, children }: {
  tono: "err" | "warn" | "ok" | "info"; children: React.ReactNode;
}) {
  const color = { err: "var(--negative)", warn: "var(--warning)",
                  ok: "var(--positive)", info: "var(--border-medium)" }[tono];
  return (
    <div style={{ margin: "0 0 9px", padding: "8px 13px", fontSize: 12.5, lineHeight: 1.5,
                  borderRadius: 5, background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderLeft: `3px solid ${color}` }}>
      {children}
    </div>
  );
}
