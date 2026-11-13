# 81 — Export de 4 empresas para validación independiente (r9a)

> Export de la ficha viva + el dossier del comité de 4 nombres (VST, MP, IESC, OKLO), para pasarle a 1-2 IAs
> independientes y contrastar si llegan a la misma conclusión que BORJA. Fecha: 2026-11-13. Precios y datos
> point-in-time de ese día. (Mismo propósito que los docs 66/71 de exports previos.)

## Prompt para la IA independiente (pegar ESTO + el export de abajo)

```
Sos un analista quant worldclass de equity (small/mid caps de "industrias del futuro": nuclear/energía,
semis, defensa, tierras raras, datacenters). Abajo te paso el análisis de 4 empresas hecho por un sistema de
IA (BORJA) y SU CONCLUSIÓN. Quiero una SEGUNDA OPINIÓN INDEPENDIENTE: analizá cada una por tu cuenta y decime
si llegás a la misma conclusión; si no, por qué.

CÓMO BORJA saca su conclusión (para que critiques los INPUTS, no el mecanismo):
- El analista define 3 escenarios (bear/base/bull): una métrica terminal (EBITDA o EBIT) × un múltiplo de
  salida, a un horizonte en años, con una probabilidad.
- El código calcula el valor por acción de cada escenario (equity = métrica×múltiplo − deuda neta, dividido
  por las acciones diluidas), el valor esperado E[V] ponderado por probabilidad, y el RETORNO ANUAL esperado
  comprando al precio de hoy.
- Define un "precio de compra" = el precio al que ese retorno esperado llega al hurdle exigido (core 12%,
  satélite 15%, especulativa 20% anual) con un gate de downside. Si el precio de hoy está por debajo → COMPRA;
  si está muy por encima del valor → RECORTE/SALIDA; en el medio → MANTENER.

PARA CADA UNA DE LAS 4, respondé:
1. VEREDICTO: ¿coincidís con la zona de BORJA (COMPRA/MANTENER/RECORTE)? ¿ACUERDO o DESACUERDO?
2. LOS ESCENARIOS (lo más importante): ¿son razonables la métrica terminal, el múltiplo de salida, el
   horizonte y las probabilidades? ¿El bull es demasiado optimista o el bear demasiado benigno? Dame TUS
   números si diferís.
3. EL BEAR: ¿está bien planteado el riesgo? ¿Falta algún riesgo material (ciclicidad, dilución, dependencia
   política/regulatoria, competencia, un solo cliente)?
4. LOS DATOS: ¿ves algún dato dudoso? (OJO especial con IESC, que BORJA marcó "datos en conflicto" por un
   posible split: acciones feed 42,4M vs XBRL 19,9M. ¿Cuál es el número correcto?)
5. QUÉ SE PERDIÓ BORJA: cualquier cosa material que el análisis no haya considerado.

Al final: un ranking tuyo de las 4 por atractivo a estos precios, y en qué te diferenciás más de BORJA.
No inventes datos: si no estás seguro de una cifra, marcala como estimada y decí por qué.
```

---

## EXPORT (la conclusión de BORJA + el dossier, por empresa)

### VST — core · cuello: Utilities e IPPs (PPAs con datacenters)
**Precio hoy:** $131.36  ·  **acciones:** 339,394,683  ·  deuda neta: 13,395,000,000

**Conclusión BORJA:** zona **MANTENER** · precio de compra $118.6325 · recorte $137.2085 · salida $233.0411
- E[V]/acción por escenario: {'bull': 317.0498, 'base': 172.6751, 'bear': 84.2824} → E[V] = $186.6706 (vs precio $131.36)
- Retorno esperado anual: 9% · pérdida bear: -36%
- Qué exige el precio: rendir 12% a 4a pide ≤ $118.63; hoy $131.36 (retorno esperado 9%)

**Escenarios (métrica terminal × múltiplo @ años · prob):**
- bull: 11,000,000,000 × 11.0x @ 4a · prob 0.25
- base: 8,000,000,000 × 9.0x @ 4a · prob 0.5
- bear: 6,000,000,000 × 7.0x @ 4a · prob 0.25

**Dossier** — convicción 0.5 · verif pass
- **Negocio/cuello:** Vistra es el mayor IPP integrado de EE.UU. (~41 GW + ~5,5 GW de gas de Cogentrix, cerrado el 30-oct-2026): nuclear (Comanche Peak en ERCOT; Beaver Valley/Perry/Davis-Besse en PJM), gas, carbón en retiro y una pata retail grande en Texas que actúa como cobertura natural. Cuello: generación firme y despachable disponible ANTES de 2030 para datacenters. Por qué captura ESTA empresa: (a) tiene megawatts YA construidos y con licencia en los dos mercados donde la carga de IA crece más rápido (ERCOT, PJM); (b) las turbinas de gas nuevas tienen backlog hasta ~2029-30 y el nuclear nuevo es de la década del 2030, así que el reemplazo por otra vía es lento; (c) con PPAs firmados (Meta en sus nucleares de PJM, ene-2026) el margen queda contratado a 20 años en vez de expuesto al precio spot. Límites a la captura: el hyperscaler tiene poder de negociación y alternativas (behind-the-meter de gas, autogeneración, otros IPPs: CEG, TLN, NRG); los reguladores (FERC con la co-location, Texas SB6, el tope de capacidad en PJM) pueden limitar la renta; y cuando la oferta nueva de gas llegue (~2029-31) el cuello se libera de manera estructural. Ojo: el crecimiento del sector NO es todo capturable. Vistra captura la parte que contrata a largo plazo; el resto es beta del precio mayorista.
- **Qué exige el precio (analista):** Market cap $47,3B; EV ~$68-72B (con deuda de LP de $19,6B, caja de $0,4B, preferidas y la deuda asumida de Cogentrix, esta última estimada). Contra la guía 2026 (punto medio de EBITDA $7,2B y FCFbG $4,3B), el precio exige ~9,5-10x EV/EBITDA y da ~9% de FCF yield sobre el equity. Eso NO descuenta un crecimiento heroico: alcanza con sostener ~$7B de EBITDA en el ciclo y seguir recomprando (dilución 12m de -0,94%). No hay runway relevante porque la empresa genera caja (runway=None en el pack). Lo que el precio NO paga del todo es una prima tipo CEG por contratos nucleares a 20 años. El riesgo real es el inverso: que el EBITDA 2026 esté inflado por precios mayoristas/capacidad cíclicos y revierta. Limitación: no pude verificar la evolución del precio en 6 meses ni el motivo de la baja desde los máximos (ver red flag).
- **Bull:** Vistra convierte su nuclear (Comanche Peak + PJM) y su gas ya construido en contratos de 15-20 años con hyperscalers. Así pasa de un IPP cíclico a un 'utility contratado' con flujo atado a IA. El EBITDA sube a ~$11B al 2030 (Cogentrix + PPAs + capacidad en PJM) y el múltiplo se re-rata hacia 11x, como los comparables con contratos de largo plazo.
- **Bear:** El EBITDA récord de 2025-26 es un pico cíclico (spot de ERCOT, subasta de capacidad de PJM con techo político, clima), no una renta estructural. Los hyperscalers se autoabastecen (gas behind-the-meter, turbinas propias), la política (FERC con la co-location, Texas SB6, el techo de PJM) limita la captura, y la ola de gas nuevo hacia 2029-30 libera el cuello. Con $19,6B de deuda + Cogentrix, la palanca amplifica la caída: EBITDA ~$6B y múltiplo de IPP commodity de ~7x.
- **Falsador:** La tesis de que Vistra captura valor contratado de la demanda de datacenters (y no solo beta cíclica del precio mayorista) se cae si al 2027-12-31 no firmó ningún PPA/contrato adicional de ≥1 GW y ≥10 años con contraparte investment grade, más allá de los PPAs con Meta en PJM. (límite 2027-12-31)
- **Red flags:** [('brecha_informativa', 'media'), ('apalancamiento', 'media'), ('calidad_de_ganancias', 'baja'), ('dependencia_regulatoria', 'media')]

---

### MP — satelite · cuello: Tierras raras (NdPr, Dy, Tb) e imanes
**Precio hoy:** $38.3  ·  **acciones:** 178,267,976  ·  deuda neta: -401,658,000

**Conclusión BORJA:** zona **RECORTE** · precio de compra $21.1436 · recorte $27.1817 · salida $48.7346
- E[V]/acción por escenario: {'bull': 66.3029, 'base': 35.7055, 'bear': 10.2076} → E[V] = $36.9804 (vs precio $38.3)
- Retorno esperado anual: -1% · pérdida bear: -73%
- Qué exige el precio: rendir 15% a 4a pide ≤ $21.14; hoy $38.30 (retorno esperado -1%)

**Escenarios (métrica terminal × múltiplo @ años · prob):**
- bull: 900,000,000 × 14.0x @ 4a · prob 0.25
- base: 550,000,000 × 12.0x @ 4a · prob 0.5
- bear: 200,000,000 × 8.0x @ 4a · prob 0.25

**Dossier** — convicción 0.4 · verif pass
- **Negocio/cuello:** MP Materials (Mountain Pass, CA) es el único productor integrado mina→óxido NdPr→metal→imán a escala en EE.UU. Segmentos: Materials (concentrado/NdPr separado; desde jul-2025 no vende concentrado a terceros, o sea a China) y Magnetics (Independence, Fort Worth; GM/Apple). Captura de valor: el cuello no es el mineral (hay otros depósitos) sino la separación + metalización + imán fuera de China, más un contrato con el gobierno. El acuerdo con DoD/DoW de jul-2025 (preferidas convertibles + warrants, piso de precio NdPr ~$110/kg vía PPA y compra comprometida del 10X a 10 años; datos de memoria del analista, no re-verificados en esta sesión) hace que MP capture el valor del cuello vía un contrato y no vía precio de mercado: el PPA ya paga ($17,6M en el 2T26). Riesgos de captura: (i) Lynas (Australia/Texas/Malasia) separa pesadas desde antes y es el comparable directo; (ii) USAR/UUUU y Noveon/Vulcan atacan la etapa del imán; (iii) si China normaliza las exportaciones, la prima "no-China" se achica, pero el piso de precio pone un límite a la baja de la pata Materials mientras rija el contrato. El crecimiento del sector NO es crecimiento capturable: lo capturable es el volumen NdPr de Mountain Pass a precio piso más el EBITDA contratado del 10X.
- **Qué exige el precio (analista):** Market cap $6,83B; liquidez $1,45B menos deuda LP $0,93B ≈ caja neta de $0,52B → EV ≈ $6,3B. Run-rate del 2T26: (revenue $108,5M + PPA $17,6M) ×4 ≈ $0,5B; Adj. EBITDA de segmentos ≈ $40M/trimestre → ~$160M anual → EV/EBITDA ≈ 40x. A 10-12x de salida en 2030, el precio exige ~$550-650M de EBITDA (≈3,5-4x el actual), es decir: Mountain Pass a ~6-10 kt NdPr bajo el piso de $110/kg más el 10X operando con EBITDA contratado. Es básicamente el caso base ejecutado; el precio ya no paga una prima por la escasez geopolítica.
- **Bull:** El piso de DoD convierte a MP en un utility de NdPr: con Mountain Pass a ~10 kt/año a ≥$110/kg, más Independence + 10X (10 kt de imanes con offtake gubernamental) y pesadas separadas (Dy/Tb/Gd), en 2030 el EBITDA llega a ~$900M con riesgo de precio acotado. La caída de 60% descuenta un sentimiento sectorial, no un deterioro del negocio: el revenue sube 89% y el PPA ya paga.
- **Bear:** MP es un procesador de commodities sostenido por un contrato político. El ramp de NdPr se estanca (840 t en el 2T26, debajo de las 917 t del 1T26), los imanes no escalan a costo competitivo frente a China, el 10X se atrasa o se encarece y China, con su lista de control de exportaciones, corta insumos y mercados. Si el piso se renegocia o el gobierno cambia de prioridades, el EBITDA queda en ~$150-200M y la deuda de $0,9-1,5B pesa sobre el equity.
- **Falsador:** MP escala NdPr lo suficiente como para ser un proveedor no-chino de escala comparable a Lynas, que es la condición para que el precio actual (~40x EBITDA) se justifique. (límite 2027-09-30)
- **Red flags:** [('brecha_informativa', 'media'), ('dependencia_politica', 'alta'), ('ejecucion_produccion', 'media'), ('verificacion_incompleta', 'media')]

---

### IESC — satelite · cuello: Construcción y EPC de datacenters
**Precio hoy:** $169.68  ·  **acciones:** 42,404,806  ·  deuda neta: -75,770,000  ⚠ DATOS EN CONFLICTO (acciones feed≠XBRL)

**Conclusión BORJA:** zona **RECORTE** · precio de compra $123.9566 · recorte $159.3552 · salida $299.5283
- E[V]/acción por escenario: {'bull': 407.5049, 'base': 209.8303, 'bear': 68.3369} → E[V] = $216.8009 (vs precio $169.68)
- Retorno esperado anual: 6% · pérdida bear: -60%
- Qué exige el precio: rendir 15% a 4a pide ≤ $123.96; hoy $169.68 (retorno esperado 6%)

**Escenarios (métrica terminal × múltiplo @ años · prob):**
- bull: 1,350,000,000 × 13.0x @ 4a · prob 0.25
- base: 900,000,000 × 10.0x @ 4a · prob 0.45
- bear: 360,000,000 × 8.0x @ 4a · prob 0.3

**Dossier** — convicción 0.4 · verif pass
- **Negocio/cuello:** IES Holdings (IESC) es un contratista eléctrico y de infraestructura de EE.UU. con 4 segmentos: Communications (cableado estructurado y sistemas de baja tensión para data centers; en el Q3 FY26 creció ~51%), Infrastructure Solutions (envolventes y equipos de potencia de ingeniería a medida, sobre todo para data centers; creció ~73%), Commercial & Industrial (cada vez más orientado a data centers) y Residential (en caída por los housing starts). En el cuello de construcción de data centers NO es EPC/GC: es subcontratista especializado más fabricante de equipos de potencia. Captura valor por la escasez de mano de obra calificada y de capacidad de fabricación, y por saber ejecutar. Límites a esa captura: el poder de compra de los hyperscalers y colos, que licitan por proyecto; la competencia de FIX, EME, STRL y contratistas privados que suman capacidad; la normalización de la mano de obra; y que la demanda incremental depende casi por completo del ciclo de capex de IA. El margen operativo del Q3 FY26 (14,4%) es de pico de ciclo, no un nivel estructural probado. Hay crecimiento sectorial y captura parcial, pero es un negocio de servicios cíclico, no un peaje. DELTA: no hay filing nuevo desde el 10-Q del 2026-07-31 (105 días, cerca del umbral de 120). Lo nuevo es una caída fuerte del precio: el rango de 52 semanas es $142,66–$408,26. Cerró en $203 el 3/11, tocó ~$143 hacia el 5/11 y rebotó a $174 el 13/11. No encontré la causa. El Q4 FY26 y el 10-K salen el 20/11/2026, y el consenso espera revenue de $1,15B, por debajo de los $1,24B del Q3.
- **Qué exige el precio (analista):** A $174,17, el market cap es de $6,9B (39,85M acciones post-split según SEC) a $7,4B (42,4M según Yahoo). Con ~$388M de caja más inversiones y sin deuda, el EV queda en ~$6,55–7,0B. Al run-rate del Q3 FY26 (revenue ~$5,0B y EBIT ~$715M, margen del 14,4%), el precio paga ~9–10x EV/EBIT: más barato que en el dossier previo (~11x). Con márgenes de pico, el precio no exige crecimiento: exige que el EBIT no colapse. Si el margen vuelve al ~9% histórico sobre un revenue de ~$5B (EBIT ~$450M), el múltiplo pasa a ~15x, exigente para un contratista. Si además el revenue cae a ~$4B, el EBIT ronda ~$360M y el múltiplo ~19x. El mercado ya descuenta parte de la reversión: el consenso del Q4 espera revenue secuencial más bajo ($1,15B vs $1,24B) y la acción cayó ~57% desde el máximo. Lo que exige el precio es que el ciclo de capex de data centers no revierta fuerte antes de 2028 y que el margen se sostenga ≥11%.
- **Bull:** IES gana participación en el cuello de mano de obra eléctrica/comunicaciones y de equipos de potencia para data centers de IA. La caída del precio de noviembre es contagio sectorial (el trade de IA está dividido), no un deterioro propio. Communications e Infrastructure Solutions siguen creciendo con márgenes de segmento altos. Las RPO de $2,8B dan visibilidad hasta FY27. El balance sin deuda y con ~$388M de liquidez financia capacidad, M&A y recompras sin diluir. A ~9-10x EBIT, el precio paga poco si el ciclo dura hasta 2029-30.
- **Bear:** IES es un subcontratista cíclico que cotiza sobre márgenes de pico de un único ciclo, y la caída de ~57% desde el máximo anticipa la digestión del capex de IA. El consenso ya proyecta revenue secuencial más bajo en el Q4. No tiene foso: hyperscalers y GCs licitan, y FIX, EME, STRL y contratistas privados agregan capacidad. Al normalizarse la mano de obra, los márgenes vuelven al 8-10%. Las RPO se convierten sin reposición, Residential sigue cayendo y el múltiplo se comprime a 7-8x EBITDA de contratista. El accionista controlante decide la asignación de capital.
- **Falsador:** La demanda de data centers capturable por IES sigue creciendo y el margen operativo de ≥12% es sostenible hasta mediados de 2027 (no fue un pico de ciclo) (límite 2027-08-15)
- **Red flags:** [('brecha_informativa', 'alta'), ('desaceleracion_esperada', 'media'), ('datos_inconsistentes', 'media'), ('gobierno_corporativo', 'media'), ('frescura', 'baja')]

---

### OKLO — especulativa · cuello: SMRs y reactores avanzados
**Precio hoy:** $23.32  ·  **acciones:** 195,289,593  ·  deuda neta: -3,130,085,000

**Conclusión BORJA:** zona **RECORTE** · precio de compra $6.2098 · recorte $11.6848 · salida $36.2561
- E[V]/acción por escenario: {'bull': 57.5339, 'base': 18.0321, 'bear': 11.7777} → E[V] = $18.5424 (vs precio $23.32)
- Retorno esperado anual: -4% · pérdida bear: -50%
- Qué exige el precio: rendir 20% a 6a pide ≤ $6.21; hoy $23.32 (retorno esperado -4%)

**Escenarios (métrica terminal × múltiplo @ años · prob):**
- bull: 700,000,000 × 18.0x @ 6a · prob 0.1
- base: 120,000,000 × 15.0x @ 6a · prob 0.35
- bear: 30,000,000 × 3.0x @ 6a · prob 0.55

**Dossier** — convicción 0.25 · verif pass
- **Negocio/cuello:** Oklo desarrolla el reactor rápido Aurora (sodio, ~75 MWe) con un modelo de construir, ser dueño y operar: vende electricidad/calor por PPA, no reactores, y suma servicios de combustible/reciclaje e isótopos. Está en el cuello de SMR/reactores avanzados (estado: promesa) junto a NuScale, NNE y Rolls-Royce SMR, y a privadas como TerraPower, Kairos y X-energy. Captura de valor: si el modelo dueño-operador funciona, se queda con el margen de generación. Hay tres riesgos para esa captura: (1) los hyperscalers tienen poder de negociación y alternativas (uprates de nuclear existente, gas, SMR de agua liviana); (2) el HALEU es un cuello aguas arriba que pueden capturar otros (Centrus, DOE); (3) como dueño-operador, Oklo carga con el capex y el sobrecosto FOAK. La demanda eléctrica de la IA es crecimiento del sector, no algo capturado por Oklo. Qué cambió (delta): según el XBRL del 10-Q del 3T26 (2026-11-06), el revenue del trimestre fue $1,86M (antes $1,2M), igual de irrelevante; la pérdida operativa del trimestre fue -$71,0M, en línea con el ~-$72M/trimestre previo; la liquidez es ≈$3,13B (caja $1,55B + inversiones de corto plazo $0,95B + de largo plazo $0,63B), estable; hay 195,3M de acciones (+25% en 12 meses). El market cap pasó de $4,38B a $4,77B (+9%) y el EV de ~$1,37B a $1,64B. LIMITACIÓN: la búsqueda web no estuvo disponible en esta actualización. No pude leer la narrativa del 10-Q ni noticias de los últimos 90 días (estado regulatorio DOE/NRC, PPAs, capex guidance). El delta se apoya solo en el XBRL del data pack. En los números no hay nada que rompa ni que valide la tesis.
- **Qué exige el precio (analista):** El market cap es de $4,77B y la liquidez de ≈$3,13B, así que el EV que paga el mercado por la opción Aurora es ≈$1,64B (+20% frente al dossier previo, sin un hito fundamental verificado que lo explique). La caja no es un piso: la pérdida operativa ronda los $285M/año, a lo que se suma un capex creciente en plantas propias. Con ~40% de dilución hasta 2032, justificar el precio exige ≈$8B de valor terminal: unos $450M de EBITDA a 18x, es decir varias Aurora operando con PPA y un revenue que pase de ~$7M/año a >$1B, un CAGR >100% durante 5 años. Además requiere FOAK nuclear a tiempo (tasa base de ~5%). El valor esperado con mis probabilidades (~$2,9B antes de dilución) queda por debajo del market cap, y el precio implica una P(bull) muy por encima del 10% que asigno.
- **Bull:** Con ≈$3,1B de liquidez, sin aumento del burn en el 3T26 y sin deuda, Oklo es el reactor avanzado cotizado mejor financiado. La vía DOE le permitiría llevar el Aurora-INL a operar hacia 2027-28 sin más equity, y después convertir el pipeline de hyperscalers en PPAs vinculantes con 20+ años de margen de generación. El reciclaje de combustible mitiga el cuello del HALEU.
- **Bear:** El reactor rápido de sodio con modelo dueño-operador es la variante más intensiva en capital y en riesgo del cuello SMR. Oklo no tiene revenue de la tesis ($1,86M/trimestre) ni depósitos de clientes (pasivo contractual de $2 mil). Su caja es dilución pura: +25% de acciones en 12 meses. Los hyperscalers consiguen energía firme antes y más barata con nuclear existente, gas o BWRX-300/NuScale. Si el costo nivelado supera $120/MWh o el FOAK se atrasa, la liquidez se va en capex y el residual vale poco más que la caja que quede.
- **Falsador:** Oklo lleva el Aurora-INL a generar electricidad y convierte la demanda de data centers en al menos un contrato pago vinculante, con su caja actual y sin otra ronda de equity de más del 15%. (límite 2028-06-30)
- **Red flags:** [('brecha_informativa', 'media'), ('dilucion', 'alta'), ('sin_traccion_contractual', 'alta')]

---

