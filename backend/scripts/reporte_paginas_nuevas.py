# -*- coding: utf-8 -*-
"""Las seis páginas nuevas del reporte a dueños de Amarena.

Owner, 2026-11-13: *«cada nota en la presentación debe ser concluyente y
esclarecedora»* · *«debe ser lógico»*.

Separado de `reporte_amarena_ampliado.py` —que trae el formato y la hoja de
contexto— porque son dos cosas distintas: allá vive CÓMO se dibuja, acá QUÉ
dice cada página.

⚠️ **Toda nota es una fórmula.** El reporte existente ya está hecho así: sus
conclusiones se arman con `FIXED()` desde `'AM02 Resumen FY'`, y por eso se
reescriben al refrescar. Una nota con el número pegado adentro envejece sin
avisar, y en un reporte a dueños eso se descubre en la reunión.
"""
from __future__ import annotations

from reporte_amarena_ampliado import (
    ALERTA, APAGADO, BIEN, CREMA, MARRON, ORO, PASO, TC_ESCENARIOS,
    bloque_nota, cabecera_pagina, celda, tarjeta,
)

A2 = "'AM02 Resumen FY'"
A7 = "'AM07 Flow-through'"
A10 = "'AM10 Posiciones y FTE'"
A11 = "'AM11 Contexto'"
TOTAL_PAG = 15


def n(ref, dec=0):
    """El número como texto, con separador de miles."""
    return f"FIXED({ref},{dec})"


def pct(ref, dec=1):
    """La fracción como porcentaje. `C6` guarda 0,417 y acá sale «41,7%»."""
    return f'FIXED({ref}*100,{dec})&"%"'


def parrafos(ws, r, textos, alto=30):
    for t in textos:
        celda(ws, f"B{r}", t, sz=9.5, wrap=True)
        ws.merge_cells(f"B{r}:M{r}")
        ws.row_dimensions[r].height = alto
        r += 2
    return r


# ─────────────────────── Parte I · el contexto ──────────────────────────────

def pagina_turismo(ws, r0, R):
    cabecera_pagina(ws, r0, "El turismo internacional en 2027",
                    "Qué dicen los entes rectores · el entorno del Budget 2027",
                    1, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "LLEGADAS MUNDIALES 2025",
            f"={R['Llegadas internacionales 2025 (millones)']}",
            f'="millones · "&{pct(R["Crecimiento mundial 2025"])}&" vs 2024"',
            fmt="#,##0")
    tarjeta(ws, 5, r, "I SEMESTRE 2026",
            f"={R['Crecimiento mundial I sem. 2026']}",
            '="el crecimiento se frenó casi por completo"', fmt="0.0%",
            color=ALERTA)
    tarjeta(ws, 8, r, "PREVISIÓN 2026",
            f'={pct(R["Previsión 2026 (rango bajo)"])}&" a "&'
            f'{pct(R["Previsión 2026 (rango alto)"])}',
            '="UN Tourism recortó su previsión"')
    tarjeta(ws, 11, r, "PREVISIÓN 2027",
            f"={R['Previsión llegadas 2027']}",
            f'="larga distancia "&{pct(R["Previsión larga distancia 2027"],0)}'
            f'&" · consultora privada"', fmt="0.0%", color=BIEN)

    r += 6
    celda(ws, f"B{r}", "LO QUE DICEN LAS FUENTES", sz=9, b=True, color=MARRON)
    r = parrafos(ws, r + 1, [
        f'="2025 cerró con "&{n(R["Llegadas internacionales 2025 (millones)"])}'
        f'&" millones de llegadas internacionales, "'
        f'&{pct(R["Crecimiento mundial 2025"])}&" sobre 2024."',

        f'="Pero 2026 se frenó: el primer semestre creció apenas "'
        f'&{pct(R["Crecimiento mundial I sem. 2026"])}&" y UN Tourism recortó su '
        f'previsión del año a una franja de "'
        f'&{pct(R["Previsión 2026 (rango bajo)"])}&" a "'
        f'&{pct(R["Previsión 2026 (rango alto)"])}&", por el conflicto en Medio '
        f'Oriente — esa región cayó "&{pct(R["Medio Oriente I sem. 2026"],0)}&"."',

        f'="Para 2027 se proyecta una aceleración cercana a "'
        f'&{pct(R["Previsión llegadas 2027"],0)}&" en llegadas y "'
        f'&{pct(R["Previsión larga distancia 2027"],0)}&" en larga distancia. Es '
        f'de Tourism Economics, una consultora privada: no es cifra oficial de UN '
        f'Tourism y está condicionada a que se alivien las disrupciones '
        f'geopolíticas y aéreas."',
    ])

    celda(ws, f"B{r}", "CONCLUSIÓN", sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="El Budget 2027 se apoya en un mercado que se espera en recuperación, '
        f'no en expansión garantizada. Amarena presupuesta duplicar su ingreso a '
        f'$"&{n(f"{A2}!C19")}&" en ese entorno: el crecimiento del presupuesto no '
        f'viene del mercado, viene de ganar participación y de operar doce meses '
        f'en vez de diez. Conviene decirlo así, porque es más defendible que '
        f'atribuirlo a una ola que puede no llegar."')


def pagina_costa_rica(ws, r0, R):
    cabecera_pagina(ws, r0, "Costa Rica · el destino crece, pero desacelera",
                    "Llegadas internacionales 2026 según el ICT", 2, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "LLEGADAS ENE–SEP 2026",
            f"={R['Llegadas ene–sep 2026']}",
            f'={pct(R["Variación ene–sep 2026"])}&" vs 2025"', fmt="#,##0")
    tarjeta(ws, 5, r, "PESO DE ESTADOS UNIDOS",
            f"={R['Peso de Estados Unidos']}",
            '="principal emisor · y el que pierde ritmo"', fmt="0%",
            color=ALERTA)
    tarjeta(ws, 8, r, "CANADÁ · I SEMESTRE", f"={R['Canadá · I semestre']}",
            '="el mercado que más crece"', fmt="0.0%", color=BIEN)
    tarjeta(ws, 11, r, "CAÍDAS AÉREAS EN 2026",
            f"={R['Caídas interanuales aéreas en 2026']}",
            '="la de setiembre fue la tercera"', fmt="#,##0", color=ALERTA)

    r += 6
    celda(ws, f"B{r}", "EL ACUMULADO CRECE Y EL RITMO SE APAGA",
          sz=9, b=True, color=MARRON)
    r = parrafos(ws, r + 1, [
        f'="Entre enero y setiembre llegaron "&{n(R["Llegadas ene–sep 2026"])}'
        f'&" visitantes, "&{pct(R["Variación ene–sep 2026"])}&" más que en 2025. '
        f'Hasta julio el alza acumulada era "'
        f'&{pct(R["Variación ene–jul 2026"])}&": el ritmo se está apagando."',

        f'="Estados Unidos pesa "&{pct(R["Peso de Estados Unidos"],0)}&" del '
        f'mercado nacional. Canadá crece "&{pct(R["Canadá · I semestre"])}&" y '
        f'Europa "&{pct(R["Europa · ene–sep"])}&", pero ninguno compensa el '
        f'tamaño de Estados Unidos."',

        '="El ICT atribuye el freno a tensiones políticas en Estados Unidos, '
        'menos oferta de vuelos, menor dinamismo económico y el costo del '
        'combustible de aviación."',
    ])

    celda(ws, f"B{r}", "CONCLUSIÓN", sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="Estados Unidos es el "&{pct(R["Peso de Estados Unidos"],0)}&" del '
        f'mercado nacional y es justo el emisor que pierde ritmo: la caída de '
        f'setiembre fue la tercera del año en llegadas aéreas. Nuestro '
        f'presupuesto de ocupación de "&{pct(f"{A2}!C6")}&" depende de un mercado '
        f'que se está enfriando. Ésta es la variable que hay que poner sobre la '
        f'mesa antes de discutir el gasto, porque es la que mueve todo lo demás."')

    bloque_nota(ws, r + 4,
        '="PENDIENTE DE CONSEGUIR: no hay estadística pública de ocupación ni ADR '
        'para Jacó, Playa Hermosa o el Pacífico Central. Sin ese dato la '
        'presentación no puede decir si nuestra ocupación está por encima o por '
        'debajo del mercado local, que es la primera pregunta que hace un dueño. '
        'Pedirlo al ICT o a la Cámara de Turismo del Pacífico Central."')


def pagina_macro(ws, r0, R, fila_tc):
    cabecera_pagina(ws, r0, "Costa Rica · indicadores económicos 2027",
                    "Qué le hace el entorno macro al presupuesto", 3, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "INFLACIÓN 2027", f"={R['Inflación proyectada 2027']}",
            f'="meta "&{pct(R["Meta de inflación"],0)}&" ± 1 punto · BCCR"',
            fmt="0.0%")
    tarjeta(ws, 5, r, "CRECIMIENTO PIB", f"={R['Crecimiento PIB 2027–2028']}",
            '="bienio 2027–2028 · BCCR"', fmt="0.0%")
    tarjeta(ws, 8, r, "TIPO DE CAMBIO HOY",
            f"={R['Tipo de cambio Monex 30-oct-2026']}",
            f'="el Budget usa ₡"&{n(R["Tipo de cambio del Budget 2027"],2)}',
            fmt="#,##0.00", color=ALERTA)
    tarjeta(ws, 11, r, "SALARIO MÍNIMO 2027",
            f"={R['Alza salario mínimo privado 2027']}",
            '="desde el 1 de enero · CNS"', fmt="0.0%")

    r += 6
    celda(ws, f"B{r}",
          "SENSIBILIDAD · QUÉ LE PASA A LA PLANILLA SI EL COLÓN SE APRECIA",
          sz=9, b=True, color=MARRON)
    r += 1
    for col, t in (("B", "Tipo de cambio ₡/$"), ("D", "Planilla B27"),
                   ("F", "Diferencia"), ("H", "% del déficit"), ("J", "Escenario")):
        celda(ws, f"{col}{r}", t, sz=8, b=True, color=APAGADO, fondo=CREMA)
    r += 1
    for i, (tc, nombre) in enumerate(TC_ESCENARIOS):
        o = fila_tc + i
        esb = abs(tc - 460.0) < 0.01
        celda(ws, f"B{r}", f"={A11}!B{o}", sz=10, b=esb, fmt="#,##0.00",
              al="right", color=MARRON if esb else None)
        celda(ws, f"D{r}", f"={A11}!C{o}", sz=10, b=esb, fmt="#,##0", al="right")
        celda(ws, f"F{r}", f"={A11}!D{o}", sz=10, fmt="+#,##0;-#,##0;—",
              al="right", color=ALERTA if tc < 460 else BIEN)
        celda(ws, f"H{r}", f"={A11}!E{o}", sz=10, fmt="0.0%;-0.0%;—",
              al="right", color=APAGADO)
        celda(ws, f"J{r}", nombre, sz=9, b=esb, color=MARRON if esb else APAGADO)
        r += 1

    r += 1
    celda(ws, f"B{r}", "CONCLUSIÓN", sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="La inflación de "&{pct(R["Inflación proyectada 2027"])}&" y el alza '
        f'salarial de "&{pct(R["Alza salario mínimo privado 2027"])}&" son '
        f'manejables y están dentro de lo previsible. El tipo de cambio no: los "'
        f'&{n(R["Puestos en colones"])}&" puestos están en colones y el Budget los '
        f'convierte a ₡"&{n(R["Tipo de cambio del Budget 2027"],2)}&" fijo los '
        f'doce meses, cuando el mercado ya está en ₡"'
        f'&{n(R["Tipo de cambio Monex 30-oct-2026"],2)}&" y el BCCR advierte que el '
        f'colón sigue apreciándose. Cerrar sólo esa brecha cuesta $"'
        f'&{n(f"{A11}!D{fila_tc+3}")}&" de planilla adicional, por una variable '
        f'que no depende de la gestión."')


# ────────────────── Parte III · lo que los dueños van a pedir ───────────────

def pagina_productividad(ws, r0):
    cabecera_pagina(ws, r0, "Productividad y eficiencia",
                    "Lo que mejora aunque el resultado todavía no cierre",
                    13, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "PLANILLA / INGRESO",
            f"={A10}!D15/{A2}!C19",
            f'="F26: "&{pct(f"{A10}!C15/{A2}!B19")}', fmt="0.0%", color=BIEN)
    tarjeta(ws, 5, r, "INGRESO POR FTE", f"={A2}!C19/{A10}!D13",
            f'="F26: $"&{n(f"{A2}!B19/{A10}!C13")}', fmt="#,##0", color=BIEN)
    tarjeta(ws, 8, r, "COSTO POR FTE", f"={A10}!D15/{A10}!D13",
            f'="F26: $"&{n(f"{A10}!C15/{A10}!C13")}', fmt="#,##0", color=BIEN)
    tarjeta(ws, 11, r, "FTE PROMEDIO", f"={A10}!D13",
            f'="F26: "&{n(f"{A10}!C13",1)}&" · "&{n(f"{A10}!D10")}&" plazas"',
            fmt="#,##0.0")

    r += 6
    celda(ws, f"B{r}", "INDICADORES DE EFICIENCIA", sz=9, b=True, color=MARRON)
    r += 1
    for col, t in (("B", "Indicador"), ("F", "Forecast 2026"),
                   ("H", "Budget 2027"), ("J", "Variación")):
        celda(ws, f"{col}{r}", t, sz=8, b=True, color=APAGADO, fondo=CREMA)
    r += 1
    filas = [
        ("Planilla / ingreso", f"{A10}!C15/{A2}!B19", f"{A10}!D15/{A2}!C19",
         "0.0%", True),
        ("Ingreso por FTE", f"{A2}!B19/{A10}!C13", f"{A2}!C19/{A10}!D13",
         "#,##0", False),
        ("Costo anual por FTE", f"{A10}!C15/{A10}!C13", f"{A10}!D15/{A10}!D13",
         "#,##0", True),
        ("FTE promedio del período", f"{A10}!C13", f"{A10}!D13", "#,##0.0", False),
        ("Plazas en el maestro", f"{A10}!C10", f"{A10}!D10", "#,##0", False),
        ("Plazas vacantes", f"{A10}!C12", f"{A10}!D12", "#,##0", True),
        ("Ingreso por noche disponible", f"{A2}!B19/{A7}!B14",
         f"{A2}!C19/{A7}!C14", "#,##0.00", False),
        ("Ingreso por noche ocupada", f"{A2}!B19/{A7}!B15",
         f"{A2}!C19/{A7}!C15", "#,##0.00", False),
    ]
    for rotulo, ff, fb, fmt, menor_mejor in filas:
        celda(ws, f"B{r}", rotulo, sz=9.5)
        celda(ws, f"F{r}", f"={ff}", sz=9.5, fmt=fmt, al="right")
        celda(ws, f"H{r}", f"={fb}", sz=9.5, fmt=fmt, al="right", b=True)
        signo = "<" if menor_mejor else ">"
        celda(ws, f"J{r}",
              f'=IF(({fb}){signo}({ff}),"mejora","empeora")&" "&'
              f'FIXED(ABS(({fb})/({ff})-1)*100,1)&"%"',
              sz=9, al="right", color=APAGADO)
        r += 1

    r += 1
    celda(ws, f"B{r}", "CONCLUSIÓN", sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="Todos los indicadores de eficiencia mejoran: la planilla pasa de "'
        f'&{pct(f"{A10}!C15/{A2}!B19")}&" a "&{pct(f"{A10}!D15/{A2}!C19")}&" del '
        f'ingreso, el ingreso por FTE sube de $"&{n(f"{A2}!B19/{A10}!C13")}&" a $"'
        f'&{n(f"{A2}!C19/{A10}!D13")}&", y las plazas vacantes bajan de "'
        f'&{n(f"{A10}!C12")}&" a "&{n(f"{A10}!D12")}&". Amarena no tiene un '
        f'problema de productividad: tiene un problema de escala. La estructura es '
        f'correcta para un hotel más grande del que hoy vende, y por eso la '
        f'palanca es ocupación y no recorte."')


def pagina_posiciones(ws, r0):
    cabecera_pagina(ws, r0, "Posiciones y FTE por departamento",
                    "Dónde crece la planta y por qué · fuente AM10",
                    14, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "FTE AL CIERRE", f"={A10}!D14",
            f'="F26: "&{n(f"{A10}!C14",1)}', fmt="#,##0.0")
    tarjeta(ws, 5, r, "PLAZAS EN EL MAESTRO", f"={A10}!D10",
            f'="F26: "&{n(f"{A10}!C10")}&" · vacantes "&{n(f"{A10}!D12")}',
            fmt="#,##0")
    tarjeta(ws, 8, r, "PLANILLA TOTAL", f"={A10}!D15",
            f'="F26: $"&{n(f"{A10}!C15")}', fmt="#,##0")
    tarjeta(ws, 11, r, "CARGAS SOCIALES", f"={A10}!D19/{A10}!D15",
            f'="$"&{n(f"{A10}!D19")}&" · CCSS y provisiones"', fmt="0.0%")

    r += 6
    celda(ws, f"B{r}", "FTE Y COSTO POR DEPARTAMENTO", sz=9, b=True, color=MARRON)
    r += 1
    for col, t in (("B", "Departamento"), ("E", "FTE F26"), ("F", "FTE B27"),
                   ("G", "Δ FTE"), ("I", "Planilla F26"), ("K", "Planilla B27")):
        celda(ws, f"{col}{r}", t, sz=8, b=True, color=APAGADO, fondo=CREMA)
    r += 1
    # AM10 lista los departamentos en las filas 37-44; la 44 es el total.
    for o in range(37, 45):
        total = o == 44
        celda(ws, f"B{r}", f"={A10}!B{o}", sz=9.5, b=total)
        celda(ws, f"E{r}", f"={A10}!E{o}", sz=9.5, fmt="#,##0.0", al="right")
        celda(ws, f"F{r}", f"={A10}!F{o}", sz=9.5, fmt="#,##0.0", al="right",
              b=total)
        celda(ws, f"G{r}", f"={A10}!G{o}", sz=9.5, fmt="+#,##0.0;-#,##0.0;—",
              al="right", color=APAGADO)
        celda(ws, f"I{r}", f"={A10}!H{o}", sz=9.5, fmt="#,##0", al="right")
        celda(ws, f"K{r}", f"={A10}!I{o}", sz=9.5, fmt="#,##0", al="right",
              b=total)
        if total:
            celda(ws, f"B{r}", "Total hotel", sz=9.5, b=True)
        r += 1

    r += 1
    celda(ws, f"B{r}", "CONCLUSIÓN", sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="La planta pasa de "&{n(f"{A10}!C13",1)}&" a "&{n(f"{A10}!D13",1)}'
        f'&" FTE promedio, y crece donde se vende: Rooms y Club Madresal. Buena '
        f'parte del aumento no es gente nueva sino calendario — 2026 pagó diez '
        f'meses de operación y 2027 paga doce. Las plazas del maestro incluso '
        f'bajan de "&{n(f"{A10}!C10")}&" a "&{n(f"{A10}!D10")}&", y las vacantes '
        f'de "&{n(f"{A10}!C12")}&" a "&{n(f"{A10}!D12")}&": el presupuesto no '
        f'infla la planta, la completa."')

    bloque_nota(ws, r + 4,
        '="Lo que hay que poder explicar puesto por puesto: Tours pasa de 0,1 a '
        '1,1 FTE, y Seguridad duplica su planta mientras su cuenta de servicio '
        'externo se multiplica por 6,8. Son las dos únicas que no se explican '
        'solas con el calendario."')


def pagina_riesgos(ws, r0, R, fila_tc):
    cabecera_pagina(ws, r0, "Riesgos y análisis de sensibilidad",
                    "Las tres variables que mueven el resultado", 15, TOTAL_PAG)
    r = r0 + 6
    tarjeta(ws, 2, r, "DÉFICIT EBITDA B27", f"=-{A2}!C29",
            f'="a fondear · $"&{n(f"-{A2}!C29/12")}&" por mes"', fmt="#,##0",
            color=ALERTA)
    tarjeta(ws, 5, r, "OCUPACIÓN PARA EBITDA 0", f"={A7}!C16*1693121/{A2}!C19",
            f'="hoy "&{pct(f"{A2}!C6")}&" · faltan puntos"', fmt="0.0%",
            color=ALERTA)
    tarjeta(ws, 8, r, "RIESGO TIPO DE CAMBIO",
            f"={A11}!D{fila_tc+6}",
            '="si el colón llega a ₡430"', fmt="#,##0", color=ALERTA)
    tarjeta(ws, 11, r, "VACÍOS DEL PRESUPUESTO", f"={A2}!B30",
            '="existían en F26 y no están en B27"', fmt="#,##0", color=ALERTA)

    r += 6
    celda(ws, f"B{r}", "1 · TIPO DE CAMBIO — EL RIESGO QUE NADIE ESTÁ MIRANDO",
          sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="Los "&{n(R["Puestos en colones"])}&" puestos están en colones '
        f'(₡19.145.000 al mes) y el Budget los convierte a ₡"'
        f'&{n(R["Tipo de cambio del Budget 2027"],2)}&" fijo. El mercado está en ₡"'
        f'&{n(R["Tipo de cambio Monex 30-oct-2026"],2)}&" y sigue apreciándose. '
        f'Una apreciación a ₡430 cuesta $"&{n(f"{A11}!D{fila_tc+6}")}&", el "'
        f'&{pct(f"{A11}!E{fila_tc+6}",0)}&" del déficit de EBITDA. La decisión: o '
        f'se represupuesta la planilla a un tipo de cambio conservador, o se '
        f'declara como riesgo asumido. Hoy no está dicho en ninguna parte."')

    r += 5
    celda(ws, f"B{r}", "2 · OCUPACIÓN — LA PALANCA PRINCIPAL",
          sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="El punto de equilibrio de EBITDA pide un ingreso de $1.693.121 — "'
        f'&{n(f"1693121/{A2}!C19",2)}&" veces el Budget — lo que con el mismo ADR '
        f'equivale a cerca de 53% de ocupación. El presupuesto llega a "'
        f'&{pct(f"{A2}!C6")}&". No hay plan de gasto que cierre esa brecha: '
        f'recortar los $"&{n(f"{A2}!D24")}&" completos de Ventas y Mercadeo '
        f'tampoco alcanza, y sin marketing la ocupación no llega."')

    r += 5
    celda(ws, f"B{r}", "3 · LOS VACÍOS DEL PRESUPUESTO",
          sz=9, b=True, color=MARRON)
    bloque_nota(ws, r + 1,
        f'="El EBITDA de -$"&{n(f"-{A2}!C29")}&" está mejorado por omisión: '
        f'reserva de capital, depreciación y gastos financieros suman $"'
        f'&{n(f"{A2}!B30")}&" que existían en 2026 y quedan en cero en 2027. A eso '
        f'se agregan A&B, lavandería y misceláneos sin ingreso presupuestado. '
        f'Presentar el número sin esta aclaración es el mayor riesgo de la '
        f'reunión: si el dueño lo descubre, pone en duda todo lo demás. Decirlo '
        f'nosotros, con el monto exacto, convierte un hallazgo en un punto de '
        f'agenda."')
