# 56 — Dossiers reales del smoke (2026-10-27) — para auditar calidad

> Export literal de `data/cache_dossiers_v2.json` (OKLO/RKLB/ACHR). ¿El análisis agrega valor o alucina? ¿Los números tienen fuente? ¿Bull/bear son sustantivos? Tesis del doc 49.


## OKLO — veredicto Verificador: **REVIEW** · convicción analista 0.3

**Negocio/cuello:** Oklo es un desarrollador pre-revenue de microrreactores rápidos (Aurora, 15-75 MWe) con modelo "build-own-operate" (vende energía vía PPA, no reactores), más unidades de combustible (HALEU/reciclado) y radioisótopos. La tesis de cuello de botella es la capacidad firme baseload para data centers de IA y la escasez de combustible HALEU. Oklo no controla un cuello hoy: no tiene licencia comercial NRC, ni planta operando, ni ingresos. Su posición es la de una opción con mucho efectivo sobre la licencia y el despliegue: el piloto Aurora-INL va por la vía de autorización del DOE (Reactor Pilot Program), no por una licencia comercial de la NRC. Aviso de procedencia: me quedé sin cupo de búsquedas después de la primera. La evidencia llega hasta el Q4-2025 (reportado el 17-mar-2026). No pude verificar Q1/Q2-2026 ni qué explica la caída de ~$64 a $27.37.

**Valuación que exige el precio:** El DATA PACK no trae owner-FCF, g_D ni T*/burden: no hay calculadora contra la cual contrastar, y no invento un T*. Cuenta propia: market cap de US$5.09B (186M acciones × US$27.37) menos caja de ~US$2.3-2.5B (C1 neto de la quema estimada de 2026, no verificada) da un EV de ~US$2.6-2.8B por una cartera sin ingresos. Como referencia de orden de magnitud (supuesto, no calculadora): si cada GWe operativo bajo PPA vale ~US$1-1.5B de EV descontado, el precio pide ~2 GWe creíbles hacia 2032-2035, es decir, decenas de unidades Aurora, más que el solo piloto INL. Además hay dilución: la base pasó a ~186M acciones después de un ATM de US$1.5B, y el capex de las plantas comerciales casi seguro va a exigir más capital o financiamiento de proyectos.


**Bull:** Oklo es la opción mejor capitalizada de microrreactores para data centers. Con ~US$2.4B de caja (C1) y una quema operativa de ~US$70-80M/año en 2025 (C2), tiene varios años de pista para llegar a la criticidad de Aurora-INL por la vía del DOE (C4), que es más rápida que la de la NRC. Después de una caída de ~58% desde marzo (C7), el EV de ~US$2.7B cotiza a ~1x caja: si el piloto opera y aparecen PPAs firmes con hyperscalers, el mercado vuelve a pagar la opción.

_Supuestos:_ ['Aurora-INL alcanza la criticidad o la operación piloto bajo autorización DOE hacia 2027-2028', 'La quema de caja de 2026-27 se queda debajo de ~US$300M/año, sin un capex de proyecto que obligue a otra dilución grande antes del primer hito', 'Al menos un PPA vinculante (no MOU) con un hyperscaler o una utility antes de 2028', 'El suministro de HALEU se resuelve para las primeras unidades (DOE/reciclado)']


**Bear:** Oklo es una historia de financiamiento, no de energía. Tiene ingresos cero (C5), una pérdida operativa que se multiplicó en 2025 (C2, C9) y un plan que depende de que nunca falte capital barato: levantó US$1.5B vía ATM cuando la acción estaba alta (C1), mientras los fundadores vendían ~US$232M cada uno sin comprar (C6). La caída de US$64 a US$27 (C7) cierra esa ventana. El costo de las plantas comerciales (FOAK) se va a llevar la caja y va a forzar dilución a precios bajos. El precedente de la industria de SMR (sobrecostos, demoras de licencia, la denegación previa de la NRC a Oklo en 2022) dice que los cronogramas se estiran, y los PPAs no firmes no sostienen valor.

_Supuestos:_ ['El capex FOAK por unidad y la escalada de costos superan la caja disponible antes de generar ingresos', 'Las licencias comerciales de la NRC (más allá del piloto DOE) se demoran más allá de 2029', 'Los acuerdos con data centers siguen siendo no vinculantes', 'Hay nueva emisión de equity o convertibles a precios cercanos o inferiores a los actuales']


**Falsador:** Aurora-INL alcanza la criticidad o la operación piloto bajo autorización DOE y Oklo firma al menos un PPA vinculante, manteniendo caja de más de US$1.5B sin una nueva emisión de equity mayor al 15% de la base. (límite 2028-06-30) — qué lo mataría: Que al 2028-06-30 Aurora-INL no haya alcanzado la criticidad, o que Oklo haya emitido más de ~28M acciones nuevas (más del 15%) antes de tener ingresos: la tesis bull de "opción financiada" cae.


**Claims (9)** [tesis_soporte=['C1', 'C2', 'C4', 'C8']]:

- `C1` [declaracion_empresa/central/company_statement] Oklo terminó 2025 con ~US$1.4B en caja y valores negociables, y en enero de 2026 levantó US$1.182B netos, con lo que completó su programa ATM de US$1.5B.
    fuente: https://www.alpha-sense.com/earnings/oklo/ · cita: Cash and marketable securities of $1.4 billion at the end of 2025, with an additional $1.182 billion raised net of fees in the first month of 2026, completing t
- `C2` [declaracion_empresa/central/company_statement] Pérdida operativa de US$139.3M en el año 2025 y caja usada en operación de US$82.2M (US$69.2M ajustada).
    fuente: https://www.alpha-sense.com/earnings/oklo/ · cita: Operating loss of $139.3 million for full year 2025 ... Cash used in operating activities of $82.2 million for full year 2025
- `C3` [declaracion_empresa/soporte/company_statement] La compensación en acciones de 2025 fue US$41.8M, y US$29.1M de ingreso por intereses redujeron la pérdida antes de impuestos a US$110.2M.
    fuente: https://www.alpha-sense.com/earnings/oklo/ · cita: Non-cash stock-based compensation expense of $41.8 million ... interest and dividend income of $29.1 million
- `C4` [declaracion_empresa/central/company_statement] Aurora-INL firmó una OTA con el DOE bajo el Reactor Pilot Program, obtuvo la aprobación del DOE del Nuclear Safety Design Agreement, siguió con la construcción (voladuras) y contrató a Siemens Energy para la conversión de potencia.
    fuente: https://www.alpha-sense.com/earnings/oklo/ · cita: Aurora-INL executed its DOE Other Transaction Agreement under the Reactor Pilot Program, received DOE approval of the Nuclear Safety Design Agreement
- `C5` [hecho/soporte/media_report] Ingresos de US$0 y EPS de -US$0.27 en el Q4-2025, contra un consenso de -US$0.17. Erró el EPS en 3 de los últimos 4 trimestres.
    fuente: https://www.quiverquant.com/news/OKLO+($OKLO)+Releases+Q4+2025+Earnings · cita: The company reported earnings of -$0.27 per share, missing estimates of -$0.17 by $0.10. The company also reported revenue of $0
- `C6` [hecho/soporte/media_report] Los cofundadores (CEO DeWitte, COO Cochran) aparecen con ventas de insiders por ~US$232M (82 ventas, 0 compras), y el CFO con ~US$20.7M.
    fuente: https://www.quiverquant.com/news/OKLO+($OKLO)+Releases+Q4+2025+Earnings · cita: JACOB DEWITTE (Co-Founder, CEO) has made 0 purchases and 82 sales selling 2,577,788 shares for an estimated $232,013,692.
- `C7` [hecho/soporte/media_report] Tras el reporte del Q4-2025, la acción cerró en el aftermarket en ~US$64.61. El DATA PACK la marca hoy en US$27.37 (-58%).
    fuente: https://www.investing.com/news/transcripts/earnings-call-transcript-oklo-inc-q4-2025-reports-strategic-advances-93CH-4567156 · cita: Oklo's stock rose 8.24% in aftermarket trading, closing at $64.61.
- `C8` [inferencia/central/hypothesis] Market cap de ~US$5.09B. Con caja pro forma de ~US$2.3-2.5B (C1 menos la quema de 2026), el EV implícito queda en ~US$2.6-2.8B, todo atribuible a la opción de desplegar reactores.
    fuente: https://www.alpha-sense.com/earnings/oklo/ · cita: Cash and marketable securities of $1.4 billion at the end of 2025, with an additional $1.182 billion raised net of fees
- `C9` [hecho/secundaria/confirmed_by_filing] Con ~US$1.4B de caja, el Q1-2025 ya mostraba una pérdida neta de US$9.8M y un déficit acumulado de US$144.9M; el gasto se aceleró fuerte durante 2025.
    fuente: https://www.sec.gov/Archives/edgar/data/1849056/000162828025025166/Financial_Report.xlsx · cita: For the three months ended March 31, 2025, the Company had a net loss of $9,810, loss from operations of $17,874

**Red flags (4):** insider_selling[media]; dilucion[alta]; pre_revenue_y_errores_de_estimacion[media]; brecha_informativa[alta]

**Catalizadores:** Resultados del Q3-2026: ritmo de quema, caja remanente, guía (2026-11); Hitos de autorización DOE del Reactor Pilot Program para Aur (2026-2027); Conversión de acuerdos con data centers o utilities en PPAs  (2026-2027); Nuevo programa ATM o emisión de deuda o convertibles para el (2026-2027)

**Motivos del Verificador:** ['tesis se apoya en declaración de empresa (C1)', 'tesis se apoya en declaración de empresa (C2)', 'tesis se apoya en declaración de empresa (C4)']


## RKLB — veredicto Verificador: **REVIEW** · convicción analista 0.3

**Negocio/cuello:** Rocket Lab (RKLB) está integrada verticalmente en lanzamiento (el cohete chico Electron, HASTE para pruebas hipersónicas y Neutron, un cohete medio aún en desarrollo) y en sistemas espaciales (satélites, componentes y buses, y adquisiciones orientadas a defensa). El cuello de botella al que apunta es la escasez de lanzamiento dedicado no-SpaceX y de proveedores de constelaciones para defensa de EE.UU. (SDA, Golden Dome). Hoy es el segundo lanzador occidental por cadencia en small launch, pero su posición en el segmento medio-pesado depende enteramente de que Neutron funcione. Aviso de procedencia: el límite de búsquedas cortó la investigación después de una sola fuente primaria (el 8-K del 3T25). Todo lo demás figura como analyst_prior o hypothesis.

**Valuación que exige el precio:** Market cap de USD 37.700m (precio 59,04 × 598,5m de acciones) contra una facturación anualizada de unos USD 620m: unas 60 veces ventas. El data pack no trae owner-FCF ni g_D ni T*/burden, así que no hay contraste con esas calculadoras. Cuenta propia (hypothesis): tomo un EV de unos USD 36.700m (supone caja neta de alrededor de USD 1.000m, dato no verificado), un costo de capital del 10% y una salida a 25 veces FCF. Con eso, el precio exige unos USD 3.100m de FCF en el año 8 (36,7 × 1,1^8 / 25). Con margen FCF del 20%, eso equivale a unos USD 15.000m de facturación en 2033: unas 25 veces la actual, más de 50% anual compuesto durante 8 años y sin más dilución. El precio ya da por hecho que Neutron funciona, que RKLB queda como el segundo proveedor occidental de lanzamiento medio y que se vuelve un contratista prime de constelaciones de defensa.


**Bull:** RKLB es el único competidor occidental creíble de SpaceX con integración vertical real. Electron ya genera escala y margen (37% bruto). Neutron abre el mercado de lanzamiento medio y de constelaciones, y sistemas espaciales convierte la demanda SDA/Golden Dome en contratos de cientos de millones. La convexidad viene del operating leverage cuando Neutron vuele con cadencia.

_Supuestos:_ ['Neutron vuela con éxito en 2026 y llega a más de 10 lanzamientos por año hacia 2028.', 'La facturación crece más de 50% anual compuesto hasta unos USD 15.000m en 8 años.', 'El margen FCF converge al 20% o más.', 'La dilución adicional queda por debajo del 3% anual.', 'Defensa de EE.UU. (SDA, Golden Dome, NSSL) adjudica volumen recurrente.']


**Bear:** El precio descuenta un desenlace que todavía no existe. Neutron no voló y viene con demoras. El lanzamiento medio es un mercado donde Falcon 9 reutilizable fija el precio y donde también entran Stoke, Relativity y Firefly. Encima, la empresa financia su crecimiento con ATM: la dilución es la forma recurrente de pago. Un fallo o un retraso de Neutron, o una desaceleración de defensa, comprime un múltiplo de unas 60 veces ventas hacia el de un contratista aeroespacial (5–10 veces).

_Supuestos:_ ['Neutron se demora hasta 2027 o falla en su primer vuelo.', 'Precio por kg sostenido por debajo del break-even de Neutron frente a Falcon 9 y rideshare.', 'Nuevas emisiones ATM o convertibles de más de USD 1.000m.', 'El margen de sistemas espaciales se diluye por la integración de las adquisiciones.']


**Falsador:** Neutron completa con éxito su primer lanzamiento orbital en 2026. (límite 2026-12-31) — qué lo mataría: Si al 2026-12-31 Neutron no hizo un vuelo orbital exitoso, se cae la tesis de lanzamiento medio que justifica el múltiplo de unas 60 veces ventas.


**Claims (7)** [tesis_soporte=['C1', 'C2', 'C3']]:

- `C1` [hecho/central/confirmed_by_filing] En el 3T25 la facturación fue un récord de USD 155m (+48% interanual), con margen bruto GAAP récord del 37%.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: Posts Record Quarterly Revenue of $155m, Representing 48% Year-on-Year Growth at Record Gross Margins
- `C2` [declaracion_empresa/central/company_statement] La empresa firmó 17 contratos de lanzamiento Electron en el 3T25, un récord trimestral, y espera cerrar 2025 con más de 20 lanzamientos.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: Secured 17x Electron launch contracts in Q3, 2025 – a record-breaking quarter ... remains on track to close out the year with 20+ launches.
- `C3` [declaracion_empresa/soporte/company_statement] El management dice tener un backlog récord en lanzamiento y hace M&A estratégico alineado con Golden Dome y las futuras constelaciones de la SDA.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: record backlog of contracts for our launch services business, and well-timed, strategic M&A in growth areas that are well-aligned with next-generation defense p
- `C4` [declaracion_empresa/soporte/company_statement] En el trimestre hubo dos misiones HASTE (hipersónicas) seguidas, lo que confirma demanda de defensa para pruebas suborbitales.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: Successfully launched two back-to-back HASTE missions across the quarter
- `C5` [estimacion/central/analyst_prior] El primer lanzamiento de Neutron, antes previsto para 2025, se habría pasado a 2026. No pude verificarlo en esta sesión.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: (no verificado en el extracto; recuerdo del analista sobre el call del 3T25)
- `C6` [inferencia/central/analyst_prior] Desde 2024 hubo dilución relevante por ATM y convertibles: hoy hay 598,5m de acciones, contra unas 490m que recuerdo de 2024 (dato no verificado).
    fuente: https://finance.yahoo.com/quote/RKLB · cita: shares_outstanding = 598459739 (data pack)
- `C7` [inferencia/central/hypothesis] Con un market cap de USD 37.700m y una facturación anualizada del 3T25 de unos USD 620m (155×4), la acción cotiza a unas 60 veces ventas.
    fuente: https://www.sec.gov/Archives/edgar/data/1819994/000181999425000020/rklb-11102025ex991.htm · cita: Record Quarterly Revenue of $155m; market_cap 37,747,630,080 (data pack)

**Red flags (4):** valuacion_extrema[alta]; dilucion[alta]; riesgo_ejecucion_producto[alta]; evidencia_incompleta[media]

**Catalizadores:** Primer lanzamiento orbital de Neutron (2026 (según la empresa; fecha no verificada)); Resultados del 4T25 y guía 2026 (backlog, cadencia de Electr (2026-02/03); Adjudicaciones SDA (Tranche 3) y Golden Dome (2026); Nuevos programas ATM o deuda convertible (2026)

**Motivos del Verificador:** ['tesis se apoya en declaración de empresa (C2)', 'tesis se apoya en declaración de empresa (C3)']


## ACHR — veredicto Verificador: **REVIEW** · convicción analista 0.3

**Negocio/cuello:** Archer Aviation fabrica el Midnight, un avión eléctrico de despegue vertical (eVTOL) pensado como taxi aéreo urbano. Hoy no tiene ingresos recurrentes relevantes. Se mueve en dos frentes: (1) la certificación de tipo de la FAA, donde dice ser la primera en cerrar la Fase 3 de 4 y estar ya en ensayos finales de cumplimiento desde abril de 2026; (2) el programa comercial 'Launch Edition' con Abu Dhabi Aviation, más trabajo de defensa (avión híbrido y autónomo con Anduril) y operaciones iniciales en EE.UU. bajo el programa piloto eIPP. El cuello de botella del sector es regulatorio: el certificado de tipo de la FAA y la capacidad de producir en serie. Archer no controla ningún insumo escaso. Su ventaja sería llegar primero al certificado con la caja suficiente para no depender de ampliaciones de capital forzadas. Ojo: no tenemos datos del 2T26 (la búsqueda llegó al límite), así que los números de caja son de marzo de 2026 o anteriores.

**Valuación que exige el precio:** A US$4,24 la empresa vale US$3.270M de market cap, unas 1,6 veces el valor contable tangible por acción de marzo de 2026 (US$2,64, C2). Ese valor contable ya debe ser menor por el consumo de caja del 2T y 3T, que no pudimos verificar. Si la caja actual está entre US$1.600M y 1.800M (supuesto: consumo trimestral de ~US$120M a 150M, en línea con un opex de US$120M a 140M por trimestre en el pasado), el mercado paga entre US$1.500M y 1.700M por la opción tecnológica y regulatoria. No hay FCF del dueño positivo ni T*/burden calculable en el data pack: el precio no se puede justificar por flujos actuales. Lo que exige es: (a) certificado de tipo de la FAA hacia 2027-28 (C5), y (b) que la caja alcance hasta ese momento con poca dilución adicional. Con un consumo de unos US$550M por año, la caja dura unos 3 años. Alcanza para llegar al certificado, pero no para fabricar en serie sin capital nuevo.


**Bull:** Archer es la candidata más avanzada en la certificación FAA de eVTOL en EE.UU. (Fase 3 cerrada, ensayos finales desde abril de 2026). Tiene caja suficiente para llegar al certificado sin una ampliación de capital desesperada. Tras la caída de 35% desde mayo, el valor empresa de ~US$1.500M a 1.700M es una opción barata sobre: operaciones iniciales pagas en los Emiratos y bajo el eIPP, contratos de defensa con Anduril (híbrido/autónomo) y la vidriera de los Juegos Olímpicos LA28.

_Supuestos:_ ['Certificado de tipo FAA entre el 4T27 y el 2T28, sin rediseños mayores', 'Consumo de caja de US$500M a 600M por año; la liquidez de ~US$2.000M (C1) alcanza hasta el certificado', 'Primeras adjudicaciones de defensa con fondos reales en 2026-27', 'Abu Dhabi Aviation y el eIPP generan ingresos iniciales, aunque sean pequeños, y validan la operación']


**Bear:** Archer es una empresa pre-ingresos, con pérdidas crecientes (C7) y dilución permanente (ampliaciones de capital, acciones a proveedores, C8, C10). Su calendario de hitos se viene corriendo: 'lanzamiento comercial en los Emiratos en 2025' terminó en 'pilotos en 2026', y el certificado quedó para 2027-28. Aun con el certificado, la fabricación en serie, la infraestructura de vertipuertos y la economía por asiento son inciertas y requieren mucho capital: la caja actual no alcanza para escalar. El precio de US$4,24 sigue en 1,6 veces el valor contable tangible de una empresa que lo quema a ~US$500M por año.

_Supuestos:_ ['El certificado de tipo se demora más allá de 2028 o exige cambios de diseño', 'El consumo de caja sube a más de US$600M por año al pasar a producción y operaciones', 'Nueva ampliación de capital importante antes del certificado, con la acción baja', 'La demanda de taxis aéreos y el precio por pasaje no permiten márgenes positivos con volúmenes razonables']


**Falsador:** Archer llega al certificado de tipo de la FAA con caja propia y sin una dilución que destruya el valor por acción. (límite 2027-06-30) — qué lo mataría: Que al 30/06/2027 la liquidez reportada sea menor a US$1.000M sin certificado de tipo a la vista, o que las acciones en circulación superen los 900M (más de 17% de dilución desde las 770M actuales).


**Claims (10)** [tesis_soporte=['C1', 'C2', 'C4', 'C5', 'C10']]:

- `C1` [declaracion_empresa/central/company_statement] Archer cerró el 4T25 con ~US$2.000M de liquidez.
    fuente: https://www.investors.archer.com/news/news-details/2026/Archer-Announces-Fourth-Quarter-and-Full-Year-2025-Results-US-and-UAE-Air-Taxi-Pilot-Programs-On-Track-for-2026/default.aspx · cita: Ended Quarter With ~$2 Billion i[n liquidity]
- `C2` [hecho/central/confirmed_by_filing] Valor contable tangible neto de ~US$2.000M (US$2,64 por acción) al 31/03/2026, con 757.911.866 acciones en circulación.
    fuente: https://www.sec.gov/Archives/edgar/data/0001824502/000110465926061198/tm2614600-1_424b5.htm · cita: Our net tangible book value of our Class A common stock as of March 31, 2026 was approximately $2.0 billion, or $2.64 per share.
- `C3` [hecho/soporte/confirmed_by_filing] Valor contable tangible neto de ~US$2.100M (US$2,85 por acción) al 31/12/2025; la acción cotizaba a US$6,76 el 04/03/2026.
    fuente: https://www.sec.gov/Archives/edgar/data/1824502/000110465926024208/tm268065-1_424b5.htm · cita: Our net tangible book value of our Class A common stock as of December 31, 2025 was approximately $2.1 billion, or $2.85 per share.
- `C4` [declaracion_empresa/central/company_statement] Archer dice ser la primera en cerrar la Fase 3 del proceso de certificación de tipo de la FAA (4 fases) para eVTOL.
    fuente: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000035/archerq126earningspressr.htm · cita: Record FAA certification progress as the first to close Phase 3 of the FAA's 4-phase Type Certification process for eVTOL aircraft
- `C5` [estimacion/central/media_report] La fase final de ensayos de cumplimiento empezó en abril de 2026; según estimaciones, llevaría 18 a 24 meses (certificado de tipo hacia fines de 2027 o 1S28).
    fuente: https://www.fool.com/investing/2026/09/13/where-will-archer-be-by-this-time-next-year/ · cita: It began this final phase in April 2026, and estimates suggest it could take 18 to 24 months to complete.
- `C6` [declaracion_empresa/soporte/company_statement] La empresa espera iniciar operaciones en EE.UU. en 2026 bajo el programa piloto eIPP de la Casa Blanca, y prevé adjudicaciones por fases en defensa (avión híbrido/autónomo) más adelante en el año.
    fuente: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000035/archerq126earningspressr.htm · cita: US operations expected to begin this year under the White House's eVTOL Integration Pilot Program (eIPP)
- `C7` [hecho/soporte/media_report] Las pérdidas trimestrales se ampliaron en el 1T26 por los costos de certificación y desarrollo.
    fuente: https://zagdaily.com/zag-air/archer-pushes-ahead-on-faa-certification-as-losses-deepen/ · cita: even as its quarterly losses widened amid mounting certification and development costs
- `C8` [hecho/secundaria/media_report] En marzo de 2026, Archer emitió acciones a proveedores y registró acciones para reventa.
    fuente: https://www.investing.com/news/sec-filings/archer-aviation-files-for-resale-of-shares-and-announces-vendor-stock-issuance-93CH-4545721 · cita: The issuance of these vendor shares is expected to occur on or about March 10, 2026.
- `C9` [declaracion_empresa/soporte/company_statement] Archer empezó a cobrar pagos bajo su acuerdo definitivo con Abu Dhabi Aviation (Launch Edition).
    fuente: https://investors.archer.com/news/news-details/2025/Archers-Midnight-Showcases-In-Country-eVTOL-Flight-Test-Campaign-in-UAE-as-Part-of-Its-Commercial-Launch-Edition-Program/default.aspx · cita: Archer has now begun receiving payments under its definitive agreement with Abu Dhabi Aviation (ADA) related to its Launch Edition program.
- `C10` [inferencia/soporte/hypothesis] Inferencia de dilución: ~737M acciones al cierre de 2025 (US$2.100M / US$2,85), 757,9M al 31/03/26 y 770M según el data pack. Son ~4,5% en unos 10 meses. Mientras tanto, la acción cayó de US$6,52 (13/05/26) a US$4,24 (-35%).
    fuente: https://www.sec.gov/Archives/edgar/data/0001824502/000110465926061198/tm2614600-1_424b5.htm · cita: On May 13, 2026, the last reported sale price of our Class A common stock was $6.52 per share.

**Red flags (4):** dilución continua[alta]; pérdidas crecientes sin ingresos[alta]; hitos que se corren / dependencia de declaraciones de la empresa[media]; falta de datos del 2T26[media]

**Catalizadores:** Resultados del 3T26: caja, consumo de caja y estado del eIPP (2026-11); Primeras operaciones en EE.UU. bajo el eIPP (2026-12-31); Adjudicaciones por fases del programa de defensa híbrido/aut (2026-4T a 2027-1S); Avance de los ensayos finales de cumplimiento de la FAA (vue (2027); Nuevas ampliaciones de capital o programa ATM (continuo)

**Motivos del Verificador:** ['tesis se apoya en declaración de empresa (C1)', 'tesis se apoya en declaración de empresa (C4)']
