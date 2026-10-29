# 66 — Export COMPLETO de dossiers (smoke #3, 2026-10-29)

> Export SIN recortar (auditoría r4 #4): todos los claims con url/fecha/clase/contraste + checks +
> motivos/notas del Verificador + la decisión del PM. **Nota honesta:** el cache del smoke #2 se
> sobrescribió al re-correr el #3; su versión recortada quedó en el doc 56. Acá va el #3 completo.


## OKLO — Verificador: **REVIEW**  ·  convicción analista 0.3

**Negocio/cuello:** Oklo desarrolla Aurora, un reactor rápido refrigerado por sodio de tipo pileta (hasta 75 MWe; Aurora-INL arranca derrateado a ~45 MWe). Usa combustible metálico HALEU y el modelo es "build-own-operate": vende energía vía PPA a data centers (prepago de Meta para un campus de 1,2 GW en Ohio; un marco no vinculante con Switch por 12 GW). Además tiene una línea de isótopos y combustible (Groves, laboratorio radioquímico en Idaho, carta de intención con Centrus). En el cuello de botella "SMRs y reactores avanzados" (estado: promesa) compite con NuScale (SMR), Rolls-Royce SMR y NANO Nuclear (NNE). Lo que la diferencia: (a) eligió una vía regulatoria doble. La primera unidad va bajo autorización del DOE (Reactor Pilot Program), mientras que la licencia comercial de la NRC (COLA) sigue en pre-aplicación después del rechazo de 2022. (b) Tiene una tesorería de unos US$3.000M, de las más grandes del grupo, financiada con dilución. Hoy no genera ingresos relevantes: US$1,2M en el Q2-26. Es una opción tecnológico-regulatoria con mucha caja.

**Valuación que exige el precio:** El market cap es de US$5.000M (US$26,88 × 186,0M de acciones). La liquidez al Q2 era de ~US$3.006M (C2), así que el EV ronda los US$2.000M y el P/B es ~1,5x (patrimonio de US$3.274M). El pack no trae owner-FCF ni T*/burden: con FCF fuertemente negativo, la calculadora no es aplicable, así que hago un burden propio con supuestos explícitos. Una unidad de 75 MWe al 90% de factor de carga genera ~590 GWh/año; a US$100/MWh y 50% de margen EBITDA da ~US$30M de EBITDA por unidad. Si el EV de US$2.000M se paga por un EV de 10x EBITDA en 2035, descontado al 12% durante 9 años (factor ~0,36), hacen falta ~US$5.600M de EV futuro: ~US$560M de EBITDA, unas 19 unidades (~1,4 GW) operando hacia 2035. Eso SIN contar la dilución adicional para financiar ~US$400–500M/año de capex. Si se la incluye (el nuevo ATM de US$1.000M equivale a ~37M acciones, +20%, al precio actual), la exigencia sube a unos 2 GW. El precio, entonces, no exige la flota de 12 GW de Switch, pero sí que Aurora-INL arranque cerca de 2028, que la NRC otorgue licencia comercial y que haya varios GW de pedidos firmes antes de 2032. La caja cubre ~60% de la capitalización, pero se consume a ~US$0,5–0,65B por año (C21).

**Bull:** El mercado castigó a Oklo junto con todo el sector (−61% en el año, SMR y NNE también cayeron) mientras la empresa ejecutaba. Groves llegó a criticidad en menos de un año, Aurora-INL tiene la PDSA aprobada por el DOE y hay prepago de Meta. Con ~US$3.000M de caja, el EV de ~US$2.000M es una opción barata sobre el primer reactor rápido privado en operar en EE.UU. y sobre un pipeline de demanda de data centers.

**Bear:** Oklo es un vehículo de emisión de acciones. Levantó US$1.900M en 2026 y ya abrió otro ATM de US$1.000M. Su primer reactor comercial no tiene licencia de la NRC (ni siquiera una solicitud presentada desde el rechazo de 2022). Consume ~US$0,5–0,65B por año y su combustible HALEU no está asegurado. El reactor de prueba Groves no valida la economía de un sodio-rápido de 75 MWe. Los costos de primera unidad del rubro suelen multiplicarse, como señala TD Cowen. Cada hito se financia diluyendo, y el valor por acción se erosiona aunque la tecnología funcione.

**Falsador:** Si al 2027-12-31 Oklo no presentó formalmente (y la NRC no aceptó a revisión) la COLA de Aurora, o anunció que el arranque de Aurora-INL se corre más allá de 2028, la tesis de que el EV de ~US$2.000M es una opción barata con camino comercial queda refutada. (límite 2027-12-31)


**Claims (21)** — ★=central:

- ★ `C1` [hecho/central] Al 30/06/2026 el efectivo y equivalentes era de US$1.644,7M.
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-08-07 · clase_url=primaria_regulatoria ref=cash=1644.704M/instant
      check: proc=True num=True vigente=True — XBRL: coincide (1.645e+09 ≈ 1.645e+09)
- ★ `C2` [inferencia/central] Si se suman los valores negociables corrientes (US$820,5M) y no corrientes (US$541,1M) al efectivo, la liquidez total al 30/06/2026 da unos US$3.006M. Contra un market cap de US$5.000M, eso implica un EV aproximado de US$2.000M.
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-08-07 · clase_url=primaria_regulatoria
      check: proc=True num=True vigente=False — procedencia trazable (primaria_regulatoria)
- ★ `C3` [hecho/central] Hay 186,0M de acciones en circulación (XBRL, 10-Q del Q2-26), contra 156,2M un año antes: dilución de ~19% en 12 meses.
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-08-07 · clase_url=primaria_regulatoria ref=shares_outstanding=186.01765M/instant
      check: proc=True num=True vigente=True — XBRL: coincide (1.86e+08 ≈ 1.86e+08)
- ★ `C4` [hecho/central] La pérdida operativa del FY2025 fue de US$139,3M (XBRL, 10-K del FY2025).
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-03-17 · clase_url=primaria_regulatoria ref=operating_income_loss=-139.294M/FY
      check: proc=True num=True vigente=True — XBRL: coincide (-1.393e+08 ≈ -1.393e+08)
-   `C5` [hecho/soporte] El efectivo usado en operaciones del FY2025 fue de US$82,2M. No incluye capex.
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-03-17 · clase_url=primaria_regulatoria ref=cash_used_ops=-82.174M/FY
      check: proc=True num=True vigente=True — XBRL: coincide (-8.217e+07 ≈ -8.217e+07)
-   `C6` [declaracion_empresa/soporte] Guía de uso de caja para 2026: US$120–150M en operaciones y US$400–500M en capex. La gerencia dice que la liquidez alcanza para al menos un año.
      url: https://quartr.com/companies/oklo-inc_15051
      source_date=2026-08-07 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C7` [hecho/secundaria] Ingresos del Q2-26: US$1,21M. Pérdida neta del trimestre: US$48,5M.
      url: https://cryptobriefing.com/oklo-q2-2026-earnings-revenue-net-loss/
      source_date=2026-08-07 · clase_url=media_o_busqueda ref=revenue=1.21M/Q
      check: proc=True num=True vigente=True — XBRL: sin DataPoint de referencia en el pack
-   `C8` [hecho/soporte] Pérdida operativa acumulada del H1-26: US$124,2M, compensada en parte por US$44,5M de intereses y dividendos. El gasto operativo se aceleró contra el FY2025.
      url: https://www.investing.com/news/company-news/oklo-q2-2026-slides-first-criticality-achieved-3b-liquidity-93CH-4846923
      source_date=2026-08-07 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
- ★ `C9` [hecho/central] La NRC rechazó (sin perjuicio) la COLA original de Aurora en enero de 2022. En la página de pre-aplicación de la NRC figuran la evaluación de preparación para la Fase 1 de la COLA y topical reports en revisión, pero no hay una solicitud nueva presentada formalmente.
      url: https://www.nrc.gov/reactors/new-reactors/advanced/who-were-working-with/pre-application-activities/okla-aurora-powerhouse
      source_date=2026-05-18 · clase_url=primaria_regulatoria
      check: proc=True num=True vigente=False — procedencia trazable (primaria_regulatoria)
-   `C10` [hecho/soporte] Al 16/10/2026 un tracker independiente no encuentra ninguna solicitud nueva de Oklo presentada ante la NRC.
      url: https://www.nuclearnewsnetwork.com/industry-trackers/nrc-licensing-reviews/oklo-aurora-col
      source_date=2026-10-16 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C11` [hecho/soporte] El DOE aprobó la Preliminary Documented Safety Analysis de Aurora-INL en junio de 2026. La primera unidad avanza bajo autorización del DOE.
      url: https://world-nuclear.org/information-library/country-profiles/countries-t-z/usa-nuclear-power
      source_date=2026-10-23 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C12` [declaracion_empresa/soporte] El reactor de prueba Groves alcanzó la primera criticidad el 5/8/2026, menos de un año después de la colocación de la piedra fundamental. El arranque de Aurora-INL está previsto para 2028.
      url: https://www.insidedeeptech.com/oklo-aurora-powerhouse-fast-reactor-full-guide/
      source_date=2026-10-17 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C13` [declaracion_empresa/soporte] Meta firmó un prepago de energía para un campus Aurora de 1,2 GW en Ohio. Switch tiene un marco NO vinculante por 12 GW hasta 2044.
      url: https://www.insidedeeptech.com/oklo-aurora-powerhouse-fast-reactor-full-guide/
      source_date=2026-10-17 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C14` [hecho/central] En 2026 Oklo levantó US$1.900M vía ATM y en septiembre de 2026 abrió un ATM nuevo por hasta US$1.000M.
      url: https://finance.yahoo.com/markets/stocks/articles/oklo-shares-fall-3-5-133240602.html
      source_date=2026-09-11 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C15` [hecho/soporte] Existe un prospecto 424B5 de Oklo en EDGAR en 2026 (registro shelf/ATM).
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000110465926060387/tm2614458-1_424b5.htm
      source_date=2026-09-11 · clase_url=primaria_regulatoria
      check: proc=True num=True vigente=True — procedencia trazable (primaria_regulatoria)
-   `C16` [hecho/soporte] La acción cae ~61–63% en lo que va de 2026. Rango de 52 semanas: US$25,39–152,06 (al 26/10/2026).
      url: https://www.investing.com/equities/altc-acquisition
      source_date=2026-10-26 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C17` [hecho/soporte] La caída es sectorial: al 7/10/2026 NuScale bajaba 43% y NANO Nuclear 31% en el año. El drenaje propio de Oklo viene de la emisión de acciones.
      url: https://finance.yahoo.com/markets/stocks/articles/oklo-nearly-halved-2026-240-164511758.html
      source_date=2026-10-07 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C18` [hecho/soporte] TD Cowen inició cobertura con Hold el 26/10/2026 por incertidumbre de costos. Truist mantuvo Hold y recortó su referencia de 51 a 31.
      url: https://www.investing.com/equities/altc-acquisition
      source_date=2026-10-26 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C19` [hecho/soporte] La carta de intención con Centrus podría abastecer combustible para hasta cinco Aurora, con entregas desde 2029. El HALEU sigue sin asegurar en firme.
      url: https://tradingview.com/news/zacks:b96a3cdfe094b:0-bwxt-or-oklo-which-nuclear-stock-should-you-choose-and-why
      source_date=2026-10-28 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C20` [hecho/secundaria] Hay ventas de insiders de bajo monto (~US$41–66k cada una) asociadas a vesting de RSU en octubre de 2026.
      url: https://www.investing.com/equities/altc-acquisition
      source_date=2026-10-25 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C21` [inferencia/central] Runway real con capex: la liquidez de ~US$3.006M dividida por un consumo guiado de US$520–650M/año da ~4,6–5,8 años. El cash_runway de 240 meses del data pack sobreestima porque ignora el capex.
      url: https://www.sec.gov/Archives/edgar/data/0001849056/000162828026054571/oklo-20260630.htm
      source_date=2026-08-07 · clase_url=primaria_regulatoria
      check: proc=True num=True vigente=True — procedencia trazable (primaria_regulatoria)

**Verificador motivos:** ['central C2: fuente del 2026-08-07 anterior al último filing (2026-10-29) — dato viejo', 'central C9: fuente del 2026-05-18 anterior al último filing (2026-10-29) — dato viejo']
**Verificador notas:** (ninguna)
**Red flags:** dilucion[alta]; regulatorio_sin_licencia_comercial[alta]; metrica_pack_enganosa[media]; demanda_no_vinculante[media]; brecha_informativa[media]; costo_first_of_a_kind[media]

**PMDecision (último ciclo):** mantener → peso 3.0% (conv 0.30, ejec=False)
      tesis PM: Con un EV de ~US$2.000M, es una opción barata sobre el primer reactor rápido privado de EE.UU. (Aurora-INL bajo DOE) y sobre la demanda de data centers. La caja cubre buena parte del precio.
      falsador PM: Oklo presenta formalmente la COLA de Aurora y la NRC la acepta a revisión, y además mantiene el arranque de Aurora-INL en 2028 o antes. (límite 2027-12-31)


## RKLB — Verificador: **REVIEW**  ·  convicción analista 0.35

**Negocio/cuello:** Rocket Lab (RKLB) está integrada verticalmente en el sector espacial. Tiene dos negocios: (1) Launch, con Electron (cohete chico, ya opera de forma recurrente: 98ª misión en oct-2026) y Neutron (cohete mediano reutilizable, todavía sin volar); y (2) Space Systems (buses satelitales, componentes, paneles solares, star trackers y constelaciones para defensa, por ejemplo SDA). El cuello de botella que dice atacar es el lanzamiento de carga mediana en EE.UU., donde hoy SpaceX es prácticamente monopolio. Beck llama a Neutron el 'monopoly breaker'. El 14-oct-2026 Neutron se volvió a postergar, ahora a 2027, por vacíos en el domo compuesto de la primera etapa. Así que la posición en el cuello de botella sigue siendo una promesa: lo que hoy factura es Space Systems más Electron. En jun-2026 anunció la compra de Iridium (~US$8B de EV, la mitad en cash y la mitad en acciones, cierre esperado a mediados de 2027). Eso la convertiría en operador de constelación con ingresos recurrentes y espectro, al costo de más dilución, deuda y riesgo de integración. Frescura: la evidencia operativa central es el 8-K del Q2-2026 (10-ago-2026, 80 días, menos de 120). Los números de P&L/FCF del pack son del FY2025 (known_at 26-feb-2026, más de 245 días, viejos). Falta el Q3-2026, que se espera para principios o mediados de noviembre.

**Valuación que exige el precio:** Market cap de US$37,7B, o ~US$37,8B si se cuentan las 641M acciones básicas con preferidas. La caja es de US$2,13B, así que el EV queda en ~US$35,6B. El revenue anualizado según la guía del Q3 (~US$257M × 4) es ~US$1,03B, lo que da un EV/Sales de ~35x run-rate y ~59x el FY2025 (US$602M). La empresa sigue con EBITDA ajustado negativo y flujo operativo negativo (FY25: -US$165M), sin owner-FCF positivo. El dato de runway del pack (154 meses) es engañoso: Iridium demanda ~US$27 por acción de IRDM en cash, que consumiría buena parte de esa caja o requeriría deuda (inferencia). Burden: para que el EV de hoy sea 20x un FCF estable, hace falta ~US$1,8B de FCF. Con 15% de margen FCF eso son ~US$12B de revenue, ~12x el run-rate. Lograrlo en 10 años exige ~28% de CAGR sostenido, sin descontar el tiempo ni la dilución del 12% anual (con descuento y dilución, T* pasa holgadamente los 10 años). El precio exige que Neutron vuele en 2027 y gane una parte relevante del lanzamiento mediano, que Space Systems siga creciendo más de 40%, y que Iridium aporte flujo sin destruir valor por acción.

**Bull:** RKLB es el único competidor occidental creíble de SpaceX con integración vertical real. Space Systems más Electron ya generan un crecimiento de 60% interanual y un backlog de US$2,36B (más de US$1B en contratos nuevos en el Q3). Iridium agrega ingresos recurrentes de servicios, espectro y una constelación propia que Rocket Lab puede reponer con sus propios satélites y cohetes. Si Neutron vuela en 2027, la empresa pasa a ser el segundo proveedor de lanzamiento mediano para la constelación de defensa de EE.UU. La caída de ~61% desde el máximo ya descuenta buena parte de la demora y del riesgo del deal.

**Bear:** El mercado pone precio de ganador a una empresa cuyo producto diferencial (Neutron) acumula demoras desde 2024 y nunca voló. El margen bruto se deteriora: la guía GAAP bajó de 34-36% a 29-31% en dos trimestres. La compra de Iridium por US$8B es un giro defensivo: compra flujo fuera del core porque el core no genera caja, y lo paga con caja, deuda y acciones emitidas cerca del piso del collar (dilución máxima). Las acciones crecen ~12% por año antes del deal. El revenue crece pero el valor por acción no acompaña, y con un EV/Sales de 35x cualquier tropiezo (otra demora, un fallo de Electron, un bloqueo regulatorio de Iridium) tiene mucho recorrido a la baja.

**Falsador:** Al 2027-12-31 Neutron completa su primer lanzamiento orbital exitoso. (límite 2027-12-31)


**Claims (13)** — ★=central:

- ★ `C1` [hecho/central] Revenue récord del Q2-2026 de US$234M, +62% interanual.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement ref=revenue=234.0M/Q
      check: proc=True num=True vigente=False — XBRL: período distinto: claim=Q vs ref=FY
- ★ `C2` [hecho/central] Backlog récord de US$2,36B al cierre del Q2-2026, +137% interanual.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
- ★ `C3` [declaracion_empresa/central] Guía del Q3-2026: revenue de US$250-265M, margen bruto GAAP de 29-31% (cae desde 34-36% en la guía del Q1) y EBITDA ajustado negativo de US$17-23M.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
-   `C4` [declaracion_empresa/soporte] La guía del Q3-2026 proyecta 641M acciones básicas promedio ponderadas, incluidas ~41M preferidas Serie A convertibles. Es más que las 598M ordinarias del pack.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=True — procedencia trazable (company_statement)
- ★ `C5` [hecho/central] Revenue FY2025 de US$601,8M, con resultado operativo de -US$228,8M y flujo operativo de -US$165,5M (todavía quema caja operativa).
      url: https://www.sec.gov/Archives/edgar/data/1819994/000181999426000012/rklb-02262026ex991.htm
      source_date=2026-02-26 · clase_url=company_statement ref=revenue=601.799M/FY
      check: proc=True num=True vigente=True — XBRL: coincide (6.018e+08 ≈ 6.018e+08)
-   `C6` [hecho/soporte] Pérdida operativa FY2025 de US$228,8M.
      url: https://www.sec.gov/Archives/edgar/data/1819994/000181999426000012/rklb-02262026ex991.htm
      source_date=2026-02-26 · clase_url=company_statement ref=operating_income_loss=-228.838M/FY
      check: proc=True num=True vigente=True — XBRL: coincide (-2.288e+08 ≈ -2.288e+08)
- ★ `C7` [hecho/central] Caja de US$2,13B al 30-jun-2026.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement ref=cash=2129.485M/instant
      check: proc=True num=True vigente=True — XBRL: coincide (2.129e+09 ≈ 2.129e+09)
-   `C8` [hecho/central] Acuerdo definitivo para comprar Iridium a US$54 por acción (US$27 en cash más acciones de RKLB con collar de US$67,50-112,50), ~US$8B de EV, cierre esperado a mediados de 2027 sujeto a aprobación de los accionistas de IRDM y de reguladores.
      url: https://www.govconwire.com/articles/rocket-lab-iridium-8b-cash-stock-acquisition
      source_date=2026-06-29 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C9` [hecho/soporte] El 8-K del Q2 confirma el cierre de Mynaric y Motiv y el anuncio de la compra de Iridium.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=True — procedencia trazable (company_statement)
-   `C10` [hecho/central] El 14-oct-2026 se postergó de nuevo el primer lanzamiento de Neutron, ahora a 2027, por problemas en componentes de fibra de carbono. Según la prensa, se comunicó por 8-K.
      url: https://spacenews.com/rocket-lab-delays-first-neutron-launch-again/
      source_date=2026-10-14 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C11` [hecho/soporte] Rango de 52 semanas de US$37,57 a 151,00. El precio actual (~US$59) está ~61% debajo del máximo.
      url: https://www.benzinga.com/quote/RKLB
      source_date=2026-10-27 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
- ★ `C12` [hecho/soporte] Las acciones ordinarias pasaron de 534,2M a 598,4M en 12 meses: dilución de ~12%.
      url: https://www.sec.gov/Archives/edgar/data/0001819994/000181999426000061/rklb-08102026ex991.htm
      source_date=2026-08-10 · clase_url=company_statement ref=shares_outstanding=598.350482M/instant
      check: proc=True num=True vigente=True — XBRL: coincide (5.984e+08 ≈ 5.984e+08)
-   `C13` [inferencia/soporte] Con el precio actual (~US$59) debajo del piso del collar (US$67,50), Iridium probablemente recibe la cantidad máxima de acciones por título (~0,4 RKLB). La dilución del deal queda al máximo y el valor implícito de la oferta cae por debajo de US$54.
      url: https://finance.yahoo.com/markets/stocks/articles/rocket-lab-acquire-iridium-8bn-092445487.html
      source_date=2026-06-29 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)

**Verificador motivos:** ['central C1: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C1: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo', 'central C2: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C2: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo', 'central C3: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C3: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo']
**Verificador notas:** (ninguna)
**Red flags:** brecha_informativa[media]; ejecucion_producto[alta]; dilucion[alta]; deterioro_margen[media]; M&A_transformacional[media]; datos_viejos[baja]

**PMDecision (último ciclo):** mantener → peso 0.0% (conv 0.30, ejec=False)
      tesis PM: Es un buen negocio a un precio que no deja margen.
      falsador PM: Neutron completa su primer lanzamiento orbital con éxito en 2026 y el precio corrige a un múltiplo que deje margen. (límite 2026-12-31)


## ACHR — Verificador: **REVIEW**  ·  convicción analista 0.25

**Negocio/cuello:** Archer Aviation (ACHR) está desarrollando el eVTOL Midnight para taxis aéreos urbanos. Todavía no tiene ingresos recurrentes de aviones certificados. El poco revenue que reporta sale de operar el aeropuerto de Hawthorne (LA). Además desarrolla una variante híbrida de uso dual (defensa) y una pila de IA. El cuello de botella del negocio es regulatorio: la certificación de tipo de la FAA, en sus fases TIA/for-credit, y después la manufactura a escala. Archer no controla un insumo escaso que otros necesiten. Su posición depende de llegar primero a la certificación y a la operación comercial (eIPP en EE.UU. y lanzamiento en Emiratos), en una carrera contra Joby y otros. La evidencia central es el 8-K del 2T26 (10-ago-2026, 80 días, menos de 120). Todavía no salió el 3T26 (se espera el 9-nov-2026), así que la información sobre el estado operativo actual tiene un hueco.

**Valuación que exige el precio:** Market cap: US$3.39B (pack). Liquidez del 2T26: US$1.56B (C1), sin deuda relevante verificada, así que el EV ronda US$1.8B. El pack no trae T*/burden ni owner-FCF; el owner-FCF es claramente negativo. Burn: unos US$194M por trimestre en el 2T26 (caja operativa más capex), que anualizado da cerca de US$775M y sube trimestre a trimestre. Con eso la liquidez total alcanza para unos 8 trimestres, hasta mediados o el 3T de 2028. Es coherente con el runway de 23.6 meses del pack, aunque el pack calcula con caja sin inversiones de corto plazo y con el burn del FY25. Ejercicio ilustrativo (inferencia, no es target): para justificar US$3.4B a un costo de capital del 15% durante 6 años, el equity tendría que valer cerca de US$7.9B en 2032. Si la dilución acumulada es de +50% (consistente con un 18% anual y el burn actual), el equity total tendría que valer unos US$11.8B. A 15x EBIT eso son unos US$0.8B de EBIT, o sea cerca de US$5B de revenue con un 15% de margen en 2032. Eso exige certificación entre 2027 y 2028, producción de cientos de aviones por año y una red comercial en varias ciudades. El precio de hoy descuenta una probabilidad de éxito más baja que en enero, pero igual exige una ejecución que todavía no existe.

**Bull:** Archer es de los dos jugadores de eVTOL en EE.UU. más avanzados en certificación (cerró la Fase 3, C5). Tiene US$1.56B de liquidez (C1), que financian unos 2 años hasta llegar a TIA, operar en el eIPP y en Emiratos (C6, C7). La caída de alrededor del 50% en 2026 (C9) dejó el EV cerca de US$1.8B. Si en los próximos 12 meses empiezan los vuelos for-credit de TIA, arrancan las operaciones del eIPP y llegan adjudicaciones de defensa para el híbrido, la percepción de riesgo baja mucho y el capital se puede levantar con menos dilución.

**Bear:** Archer es una opción de certificación que vive de emitir acciones. Revenue del FY25 de US$0.3M, pérdida operativa de US$729M (C10) y burn en aumento (C2, C4), con un Adjusted EBITDA que empeoró un 49% interanual. Las metas de la empresa se fueron corriendo: TIA 'tan pronto como este año' (C7). Una fuente secundaria (C8) dice que a fines de 2026 la TIA todavía no empezó. La dilución del 18% anual (C11) va a seguir y probablemente se acelere cuando el runway baje de 18 meses en 2027, justo con la acción en mínimos. El revenue que muestra viene de un FBO de aeropuerto comprado (C3), no del producto. La caída del 50% refleja que el calendario se está desmoronando, no una oportunidad.

**Falsador:** Archer empieza los vuelos for-credit de TIA con la FAA para Midnight y mantiene la liquidez por encima de US$1B sin una ampliación que diluya más del 15%. (límite 2027-06-30)


**Claims (12)** — ★=central:

- ★ `C1` [hecho/central] Al cierre del 2T26 Archer tenía US$1,560.6M entre caja, equivalentes e inversiones de corto plazo, más US$7.3M de caja restringida. El pack de datos marca cash=852.7M porque cuenta solo caja y equivalentes, sin las inversiones de corto plazo.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000056/archerq226earningspressr.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
- ★ `C2` [hecho/central] En el 2T26 la caja operativa consumida fue de US$156.4M, el capex de US$37.1M y la compra del FBO de Hawthorne de US$25.0M. La liquidez bajó US$215.3M en el trimestre.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000056/archerq226earningspressr.htm
      source_date=2026-08-10 · clase_url=company_statement ref=cash_used_ops=-156.4M/Q
      check: proc=True num=True vigente=False — XBRL: período distinto: claim=Q vs ref=FY
-   `C3` [hecho/soporte] El revenue del 2T26 fue de US$5.0M (US$1.6M en el 1T26) y salió de las operaciones en el aeropuerto de Hawthorne, no de vuelos de eVTOL.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000056/archerq226earningspressr.htm
      source_date=2026-08-10 · clase_url=company_statement ref=revenue=5.0M/Q
      check: proc=True num=True vigente=True — XBRL: período distinto: claim=Q vs ref=FY
- ★ `C4` [hecho/central] En el 2T26 la pérdida neta fue de US$263.2M y el Adjusted EBITDA de -US$177.1M. Los opex totales subieron a US$284.2M, contra US$176.1M en el 2T25.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000056/archerq226earningspressr.htm
      source_date=2026-08-10 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
- ★ `C5` [declaracion_empresa/central] La empresa dice que fue la primera en cerrar la Fase 3 de las 4 fases de la certificación de tipo de la FAA para eVTOL. Es una declaración de la empresa, no la certificación.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000035/archerq126earningspressr.htm
      source_date=2026-05-01 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
- ★ `C6` [declaracion_empresa/central] La empresa prevé empezar a operar en EE.UU. en 2026 dentro del eIPP de la Casa Blanca y como preparación para los Juegos Olímpicos LA28. También espera adjudicaciones por fases del programa híbrido de uso dual hacia fines de 2026.
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000035/archerq126earningspressr.htm
      source_date=2026-05-01 · clase_url=company_statement
      check: proc=True num=True vigente=False — procedencia trazable (company_statement)
- ★ `C7` [declaracion_empresa/central] La empresa planeaba hacer actividades TIA con la FAA en 2026 'tan pronto como este año' y operar Midnight en Emiratos dentro del programa de lanzamiento comercial.
      url: https://www.sec.gov/Archives/edgar/data/1824502/000182450226000017/archerlettertoshareholde.htm
      source_date=2026-03-02 · clase_url=primaria_regulatoria
      check: proc=True num=True vigente=False — procedencia trazable (primaria_regulatoria)
-   `C8` [estimacion/soporte] Según una fuente secundaria (Wikipedia), a fines de 2026 Midnight todavía no había empezado los ensayos TIA de la FAA. No está verificado; hay que confirmarlo con el 10-Q del 3T26.
      url: https://en.wikipedia.org/wiki/Archer_Aviation
      source_date=2026-10-29 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
-   `C9` [hecho/soporte] La acción empezó 2026 cerca de US$8 y hoy cotiza por debajo de US$4-4.4, una caída de alrededor del 50% en el año. Las medias móviles de 50 y 200 días están en torno a US$5.5.
      url: https://www.fool.com/investing/2026/10/25/archer-stock-is-down-50-is-now-finally-time/
      source_date=2026-10-25 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)
- ★ `C10` [hecho/central] Pérdida operativa del FY2025: -US$729.3M. Caja operativa consumida en el FY2025: -US$432.9M. Revenue del FY2025: US$0.3M (datos XBRL del pack).
      url: https://www.sec.gov/Archives/edgar/data/1824502/000182450226000017/archerlettertoshareholde.htm
      source_date=2026-03-02 · clase_url=primaria_regulatoria ref=operating_income_loss=-729.3M/FY
      check: proc=True num=True vigente=True — XBRL: coincide (-7.293e+08 ≈ -7.293e+08)
- ★ `C11` [hecho/central] Las acciones en circulación pasaron de 651.3M a 770.0M en 12 meses, una dilución del 18.2% (pack XBRL).
      url: https://www.sec.gov/Archives/edgar/data/0001824502/000182450226000056/archerq226earningspressr.htm
      source_date=2026-08-10 · clase_url=company_statement ref=shares_outstanding=770.0238M/instant
      check: proc=True num=True vigente=True — XBRL: coincide (7.7e+08 ≈ 7.7e+08)
-   `C12` [hecho/secundaria] Los resultados del 3T26 se publican el 9-nov-2026 después del cierre. El consenso espera una pérdida de US$0.36 por acción.
      url: https://www.earningswhispers.com/stocks/ACHR
      source_date=2026-10-29 · clase_url=media_o_busqueda
      check: proc=True num=True vigente=True — procedencia trazable (media_o_busqueda)

**Verificador motivos:** ['central C1: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C1: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo', 'central C2: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C2: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo', 'central C4: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C4: fuente del 2026-08-10 anterior al último filing (2026-10-29) — dato viejo', 'central C5: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C5: fuente del 2026-05-01 anterior al último filing (2026-10-29) — dato viejo', 'central C6: fuente NO primaria (company_statement) — no es un hecho verificado', 'central C6: fuente del 2026-05-01 anterior al último filing (2026-10-29) — dato viejo', 'central C7: fuente del 2026-03-02 anterior al último filing (2026-10-29) — dato viejo']
**Verificador notas:** (ninguna)
**Red flags:** dilucion[alta]; burn_creciente[alta]; calendario_regulatorio_corrido[alta]; brecha_informativa[media]; calidad_revenue[baja]

**PMDecision (último ciclo):** mantener → peso 0.0% (conv 0.30, ejec=False)
      tesis PM: Es una opción sobre el certificado de tipo de la FAA, pero sin caja verificada ni camino a producción en serie sin capital nuevo.
      falsador PM: Archer obtiene el certificado de tipo de la FAA con caja propia y sin dilución destructiva. (límite 2027-06-30)
