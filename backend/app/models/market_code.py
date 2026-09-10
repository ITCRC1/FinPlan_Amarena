# -*- coding: utf-8 -*-
"""Los market codes de Opera, y a qué canal pertenece cada uno.

**Por qué existe (owner, 2026-08-14).** En el sistema convivían TRES listas de
canales que no se hablaban entre sí:

1. `SalesChannelConfig` — **TA / OTA / DIRECT**. Es la que mueve plata: lleva el
   mix % y la comisión % que arman el Net Factor.
2. Los canales del mix (`seed_data/<HOTEL_ID>/canales_mix.json`) — «Travel
   Agency», «Direct Client + Website», «OTA»,
   «Other / In-House». La del mix por canal.
3. Los **KPI Groups de Opera** —Travel Agent, Direct Client, Website, OTA,
   INHOUSE— sobre 13 market codes. La realidad operativa que sale del PMS.

Tres verdades sobre lo mismo. El owner mandó su tabla de Market Codes y pidió
ponerla **debajo de Sales Channels, más detallada**: o sea que el market code es
el átomo y lo demás son agrupaciones suyas.

Con esto:

    market code  →  canal (KPI group)  →  canal de comisión (TA/OTA/DIRECT)
    TAFIT           Travel Agent          TA
    WEB             Website               DIRECT
    OTA             OTA                   OTA

El modelo de comisión deja de ser una lista aparte: pasa a ser un **rollup** de
esta. Y las estadísticas ganan sus dos dimensiones de una vez —`SEGMENT` es el
market code y `CHANNEL` es el KPI group—, que era justo lo que las tenía
bloqueadas.

⚠️ Un market code **sin canal** no se adivina ni se descarta: se muestra vacío y
se reporta. Adivinarlo mandaría noches al canal equivocado y el total seguiría
cuadrando, que es la forma de fallar que este proyecto viene persiguiendo.
"""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

#: Los canales (KPI groups). Es la lista canónica desde 2026-08-14: sale del PMS
#: y es la que el owner ya usa para leer su negocio.
CANALES = ("Travel Agent", "Direct Client", "Website", "OTA", "INHOUSE")

#: A qué canal de COMISIÓN rueda cada uno. Es el puente con el modelo que mueve
#: plata (`SalesChannelConfig`), que solo distingue tres.
#:
#: `Website` va a DIRECT porque la venta por web propia no paga comisión de
#: intermediario; `INHOUSE` también, pero por otro motivo: es uso interno y no
#: debería tener ingreso que comisionar.
CANAL_A_COMISION = {
    "Travel Agent": "TA",
    "OTA": "OTA",
    "Direct Client": "DIRECT",
    "Website": "DIRECT",
    "INHOUSE": "DIRECT",
}


class MarketCode(Base):
    __tablename__ = "market_codes"

    #: El código tal como viene de Opera. Es la LLAVE y no se mueve — igual que
    #: los códigos de tipo de habitación.
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), default="")

    #: El canal al que pertenece. VACÍO es un estado válido y visible: significa
    #: «nadie lo ha decidido todavía», no «no tiene».
    canal: Mapped[str] = mapped_column(String(40), default="", index=True)

    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    #: ¿Este código entra a la BASE de los indicadores? (owner, 2026-09-09:
    #: primero *«que el CPL no forme parte del ADR global»*, después *«sí,
    #: saca todo»*).
    #:
    #: Las cortesías y el uso interno no son venta, y contarlas deforma los
    #: tres indicadores a la vez. En marzo 2026 CPL puso el 60.8% de las
    #: noches con el 0.7% del ingreso:
    #:
    #: | | Con CPL | Sin CPL |
    #: |---|---|---|
    #: | Ocupación | 10.28% | 4.03% |
    #: | ADR | $125.44 | $317.66 |
    #: | RevPAR | $12.90 | $12.81 |
    #:
    #: RevPAR casi no se mueve, y ese es el punto: el ingreso es el mismo, lo
    #: que estaba mal era repartirlo entre noches que nadie compró.
    #:
    #: ⚠️ **No cambia lo que se GUARDA.** `actual_room_stats` sigue teniendo
    #: las noches, los pax y el ingreso del archivo, y sigue cuadrando contra
    #: el PDF. Esto mueve la base con la que se CALCULAN los indicadores, y
    #: las dos bases se muestran juntas para poder conciliarlas. Default
    #: `True`: sin que nadie desmarque nada, todo indicador es el de siempre.
    cuenta_para_kpis: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def canal_comision(self) -> str:
        """El canal de comisión al que rueda. Vacío si no tiene canal."""
        return CANAL_A_COMISION.get(self.canal, "")

    def __repr__(self) -> str:
        return f"<MarketCode {self.code} → {self.canal or '(sin canal)'}>"
