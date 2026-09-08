# 14 — Registro de finos abiertos (checklist vivo)

> **★ ESTE ES EL REGISTRO ÚNICO DE PENDIENTES DEL SISTEMA.** Todo lo que quedó en versión
> básica / diferido / por decidir vive ACÁ (no disperso en TODOs sueltos). Regla: **cuando
> elegimos el camino MVP en vez del bueno, se anota acá ANTES de codear** — así el atajo nunca
> es silencioso. Se trabaja una vez que el MVP corre.
>
> Cómo leer: los `[ ]` **abiertos = worklist**; los `[x]` cerrados quedan como contexto/decisión.
> Complementa la constitución (`13_`) y el estado vivo (`32_`). **[TRIANGULAR]** = pasar por 2ª IA
> antes de darlo por firme. La sección **E** es el bloque activo hoy (valuación + retrieval).

---

## A. Decisiones abiertas de constitución (forks reales — decidir antes de implementar)

- [x] **A1 · Macro: dónde entra.** CERRADO (4.5): exposición estructural por factor = **cap
  duro determinista** desde tabla ticker→factor **versionada** (no LLM runtime), conteo
  completo en multi-pertenencia; **el macro solo aprieta, nunca afloja**; régimen/nodos
  calientes = contexto del PM.
- [x] **A2 · Fórmula de mérito.** CERRADO (4.6): **separar selección de sizing**. Ranking =
  matriz Quality Tier × Asimetría Tier (categorías, sin multiplicar); asimetría categórica por
  escenarios con precio objetivo de múltiplos citados, winsorizada 5:1; **sizing desacoplado**
  vía escalera discreta que decide el PM dentro de [piso, hard cap]. *(Diferido: prob.
  determinista + Kelly.)*
- [x] **A3 · Política de cash.** CERRADO (4.7): **0–100 %**, sin piso ni tope; instrumentación
  (reporte de gate fallado si cash alto por N ciclos, cash drag) no bloqueo; **rf acreditada al
  cash en paper**.
- [x] **A4 · Correlaciones ocultas.** CERRADO (4.8): **estructural primero** (caps por factor +
  **grafo de dependencias de hechos citados** → cluster = 1 posición para el cap; incluye
  "ventana de capital"); stress test de cluster y no-redundancia; **estadística = tripwire**,
  no driver.
- [ ] **A5 · Re-entrada tras tesis invalidada.** ¿Un nombre que salió por tesis rota vuelve
  alguna vez? ¿Bajo qué condición dura? (el código tenía "Candado B" = 1 sola re-entrada).
- [ ] **A6 · Candidata sin nodo claro.** Si una entrada manual no mapea a un nodo del mapa:
  ¿nodo provisional, rechazo, o cola "esperando vínculo"?
- [x] **A7 · Naturaleza del Filtro 0.** CERRADO (6.5): **determinista puro, sin LLM en el
  pipeline**; ticker→nodo como artefacto versionado; datos point-in-time; se loguea cada
  rechazo. El juicio "real vs marketing" va al deep research/gate, no acá.
- [x] **A8 · Mecánica de ejecución paper.** CERRADO (Art. 11): **fill en apertura siguiente**;
  slippage + comisiones modeladas (tabla por venue); **cap de participación sobre ADV que
  alimenta el sizing**; sin fills en halts, gaps atraviesan stops; **doble P&L** (ideal vs
  modelada) + hash de estado por fill.
- [ ] **A9 · Corporate actions.** Splits, dividendos, M&A, delisting de un nombre en cartera
  — cómo los maneja el ledger sin romper el P&L ni la reconciliación. *(No cubierto por la
  triangulación — decidir en Etapa 2.)*
- [ ] **A10 · Representación de la vista macro.** Cómo se configura (operador), se versiona
  y se alimenta a elegibilidad/PM. Hoy existe una tabla `Macro` vieja (fase/postura); el
  nuevo modelo está sin definir. *(Se apoya en la tabla ticker→factor de 4.5.)*

## B. Números calibrables (regla cerrada, número a afinar con tracking)

- [x] **B1 · Cadencia.** CERRADO (7.5): **PM semanal** (quincenal es demasiado lento para
  small/mid; semanal da muestra para calibrar al PM). Evento material de precio: **±15 % en un
  día O ±20 % en 3 ruedas**. Histéresis desacopla corrida de decisión. Números finos calibrables.
- [ ] **B2 · Universo.** Piso market cap **$50M**; liquidez **$1M/día**.
- [ ] **B3 · Guardrails de cartera.** Tabla de caps arquetipo × fragilidad; piso posición
  **5 %**; cubo residual-cero **8 %**; máx posiciones **12**; máx watchlist **20**; máx por
  sector **3**. *(Todos "primera aproximación no validada" según el código.)*
- [ ] **B4 · Vigencia.** Edad máxima de ficha **por arquetipo**; ventana de validez de caché
  **por tipo de dato** (EDGAR / precio / noticias).
- [ ] **B5 · Operativos.** N máx de re-intentos del validador (Art. 4.4); timeout de
  "Esperando-evidencia" antes de archivar.
- [ ] **B6 · Nuevos (de la triangulación).** Escalera discreta de pesos {1, 2, 3.5, 5, 7} % ·
  winsorize asimetría 5:1 · umbral de cash-alto ~40 % × N ciclos · slippage v1 ~25 bps + medio
  spread · **cap de participación ADV ~10-15 %/día** · umbral de stress de cluster (−40 %) ·
  banda de histéresis de rotación.
- [ ] **B7 · Comisiones IBKR** `verificar`: confirmar el **schedule vigente** de IBKR (Fixed
  vs Tiered, mínimos y topes %, fees pass-through, estructura por venue en Europa) — no tomar
  los números de memoria de la IA como definitivos.
- [ ] **B8 · Jurisdicción — normalizar upstream** (revisión Etapa 3): definir si el campo es
  país de listing vs. incorporación, usar ISO consistente (GB vs UK, "EU" no es país), y decidir
  qué mercados tech sumar (IL, AU, SG, nórdicos) mirando la fuente. Hoy solo se produce "US".
- [ ] **B9 · Definición exacta de ADV** (revisión Etapa 3): fijar **mediana del dollar volume
  de las últimas 20 sesiones completas** (evita falsos positivos por spike de IPO). Hoy
  market_data usa media de 30d.
- [ ] **B10 · Prioridad por tamaño en la cola** (revisión Etapa 3): sin techo de market cap
  (ok), pero para no gastar deep research en mega-caps, una `prioridad_tamano` (objetivo/grande/
  mega) en el selector de cola, no un cap duro.
- [ ] **B11 · Deuda faltante — calibración** (desviación consciente): el revisor sugirió que
  deuda `None` en un nombre con revenue → esperar. NO lo apliqué para no matar recall (EDGAR
  devuelve None seguido, ej. TENB). Solo se actúa sobre deuda CONOCIDA alta. Revisable si aparecen
  falsos negativos.

## C. Definiciones finas a redactar (contratos exactos, en su etapa)

- [ ] **C1 · Jerarquía de fuentes A/B/C.** Definición concreta de qué califica en cada nivel.
- [ ] **C2 · Campos críticos.** La lista exacta de campos que usan TRUE/FALSE/UNKNOWN.
- [ ] **C3 · Contrato del PM.** Qué ve exactamente el PM (FichaPM) y el schema exacto de su
  salida (para el validador). *(Etapa 6.)*
- [ ] **C4 · Filtro 0.** Dimensiones, umbrales y los 3 resultados (descartar / esperar /
  investigar). *(Etapa 3.)*
- [ ] **C5 · Ficha rica.** Estructura de la ficha comparable (secciones, campos, evidencia).
  *(Etapa 4.)*
- [ ] **C6 · Esquema del ledger.** Entidades y relaciones de la fuente de verdad. *(Etapa 2 —
  la próxima.)*
- [ ] **C7 · Métricas y benchmark.** Forward-test: benchmark (¿SPY?), alpha, turnover,
  drawdown, atribución, seguimiento de decisiones aceptadas/rechazadas. *(Etapa 9.)*
- [ ] **C8 · Flujo de aprobación humana.** UX/cola en el dashboard, qué se muestra al
  aprobar, qué pasa si no se aprueba a tiempo. *(Etapa 6/7.)*

---

## Recap de lo YA cerrado (contexto para triangular)
Norte: datos y límites deterministas, el PM decide dentro. · Universo: US/Canadá/Europa/Asia
tech (Japón/Corea/Taiwán), **China afuera**, no ADRs, IBKR, piso $50M **sin techo**, liquidez
$1M/día, vínculo con nodo obligatorio, pre-revenue solo con contrato firme (no design-in
simple). · Fuente de info: EDGAR (US) hoy, otros mercados vía su regulador cuando exista
extractor. · Evidencia: HECHO/INFERENCIA/HIPÓTESIS + TRUE/FALSE/UNKNOWN, dos capas. ·
Validador: rechaza e informa, **el PM re-propone** (no modifica en silencio). · Estados: 9
estados con vínculo↔nodo indeleble; salida que no invalida tesis → vuelve a Watchlist. ·
Cadencia: diario (precios/riesgos + salidas urgentes) · PM semanal (**correr ≠ operar**) ·
extraordinario por evento material · mensual con más contexto. · Fallo seguro: ante la duda,
no actuar; caché vigente sí, vencido no. · Shadow obligatorio para módulos decisorios.

---

## D. Paquete Fase-1-hardening + eje dilución §5 (2026-08-10) — triangulado con 4 IAs

Triangulación: 2 subagentes Claude (repo-grounded) + IA1/IA2 externas (juicio de modelo). Convergencia.

### D.1 CERRADO (implementado + tests + shadow)
- **C1 · Tabla `r` única.** Se borró el duplicado divergente `ranking._TASA` (0.10/0.14/0.16/0.22);
  `politica.R_ARQUETIPO` (0.12/0.15/0.20/0.25/0.25) es la ÚNICA fuente. VERSION `v1.0→v1.1`.
  Las 4 IAs: es la MISMA magnitud (costo de equity) leída en dos direcciones → una sola tabla.
  `_TASA` estaba en `ranking.evaluar_ticker` (sin callers) → **no movió el libro paper** (el libro usa
  `templates`/`bridge`, que ya leían `politica`).
- **Fix doble-castigo (`r_exit`).** `FCFE_req = OP × r_exit × (1+r_hurdle)^t` con
  `r_exit = min(r_hurdle, R_TERMINAL=0.15)`. IA1+IA2 convergieron independientemente + confirmó el
  revisor de matemática Claude. Los dos `r` de la fórmula vieja eran cosas distintas (múltiplo de
  salida terminal vs descuento del camino). Efecto shadow: burdens de pre-rev/tracción −30% (SMR
  857→697, RXRX 545→478, LEU 13.8→11.3); Growth sin cambio (r_hurdle=r_exit=0.15). No mueve el
  ranking ordinal (los FCFE_OPERABLE tienen burden=None). doc 31 §2 actualizado.
- **C2 · Hueco silencioso cerrado.** Flag `arquetipo_default_r=Growth` cuando el arquetipo cae al default.
- **C4 · Código muerto podado.** Se borró `pre_revenue.rank_por_arquetipo` (sin callers; la hoja usa
  `_peer_rank_por_arquetipo`) + su test.
- **Eje dilución §5 (2 de 5 señales construibles hoy).** `edgar.get_shares_growth` (Δ acciones 12/24m) +
  `sbc_over_revenue`, cableados a `Dilucion`/`HojaEvidencia`. **Regla defensiva Up-C: sumar clases por
  fecha neutraliza el artefacto B→A** + flag `up_c_suspect`. Da señal a los R0 que antes solo tenían
  mult+burn_yield (LTBR +44%/12m, AAOI +107%/24m, RXRX sbc/rev=1.65). NO entra al ranking (eje separado).

### D.2 DIFERIDO (finos nuevos de esta triangulación, con contrato para después)
- [ ] **D-a · Binary como flag booleano ortogonal a la etapa** (aporte IA2): hoy Binary es una 5ª fila
  de arquetipo; conceptualmente es una FORMA de payoff (todo-o-nada) que aplica a cualquier etapa (una
  biotech fase-3 es pre-revenue Y binary; una minera con revenue esperando permiso es tracción Y binary).
  Rediseño: 4 arquetipos de etapa (fijan r) + `binary: bool` (fija PoS + cap, NO r). Toca el clasificador.
- [ ] **D-b · PoS `p` explícito en el numerador** para binarias: `FCFE_req_éxito = … / p`. Requiere una
  fuente para `p` (override del analista o hecho). Saca el riesgo de evento de la tasa continua (correcto).
- [ ] **D-c · C3 cosmético** (no bloqueante): `option_premium_pct = 1−1/mult` puede divergir de `OP/mcap`
  cuando `mcap` viene del feed (distinto share count). Es display; blindable computando ambos con el mismo
  `mcap_efectivo`. No cambia decisiones.
- [ ] **D-d · Eje dilución §5 — 3 señales diferidas a Fase 2-notas** (sin tag XBRL, NUNCA aproximar):
  ATM overhang/mcap · warrants/RSU · convertibles-peor-caso-para-el-común (el principal ya está en
  `total_debt`, falta ratio/precio de conversión). Siguen bajo `forward_dilution_unknown`.
- [ ] **D-e · Fase 2 pre-revenue (pre-existente):** ρ real desde G (funded gap) · R0 físico q×u×P ·
  funded critical path (grafo de carriles, scrapers ADAMS/FAA/FCC/DOE). Se solapa con extracción
  filing-céntrica ([[extraccion-xbrl-triangulada]]).

---

## E. Bloque VALUACIÓN / compiler — versión básica activa + pendientes (2026-08-13)

> El bloque que estamos construyendo. Cada MVP-básico se registra ACÁ con: qué queda básico ·
> cómo se ve "bien hecho" · cómo el sistema lo hace VISIBLE (para que no se olvide). Se trabaja
> después de que la vertical MVP corra. Spec canónica: docs 27/28/33.

### E.1 · Versión básica ACTIVA (elegida a propósito; visible + penalizada, no silenciosa)
- [x] **E1 · Tipo de contrato del RPO — HECHO (2026-08-18).** ✅ Fact_key citado
  `backlog_no_cancelable` (anchors + entailment) + mapeo `compilador.tipo_contrato_rpo` (firme→firm_po 0.85 /
  cancelable→0.60 / sin extraer→0.60 ASUMIDO) + wireo en `hoja._bull_contratado` (lee el hecho del fact store
  cuando hay session; apaga `evidencia_insuficiente` si el tipo es EXTRAÍDO). ✅ **(a) Pipeline ops HECHO:**
  `analisis.extraer_e1` (guard propio por accession, targeted 1 fact_key → no re-gasta los 3 de demanda) cableado
  a `ops/extraer_demanda.py`. **Validado end-to-end 2026-08-18:** S/VRNS→`True` DIRECT ("non-cancelable contract
  revenue")→firm_po 0.85 (sleeve sube, flag off); LEU/MP/CLS/BWXT→UNKNOWN→cancelable ASUMIDO (correcto: el filing
  no afirma no-cancelabilidad; LEU incluso tiene risk-factor de contratos cancelables). 332 tests.
  **FALTA (retrieval-quality, no wiring):** (b) tipos más finos (take-or-pay 0.90, IDIQ→ledger) — hoy solo
  firme/cancelable; (c) recall del key: la no-cancelabilidad suele vivir en el 10-K/exhibits, no en el 10-Q
  primario (LEU: ni 10-Q ni 10-K la afirman con los anchors actuales) → subir recall = ampliar scope/anchors
  con cuidado de falsos positivos. Pertenece al workstream de extracción, no a E1.
- [ ] **E1-bis · OPCIÓN GRATIS sobre nombre del libro duro — DECISIÓN 2026-08-18 (pregunta del operador).**
  Un nombre cuyo cashflow YA merece su valuación (COVERED, entra al libro duro) pero que ADEMÁS tiene opcionalidad
  especulativa (design-win sin firmar, TAM, expansión no contratada): hoy esa opcionalidad se registra en el
  `option_ledger` (se muestra) pero es **INERTE** — `ranking_lexicografico` no la mira, ni para size ni para orden.
  Es información dejada sobre la mesa (pagás el cashflow, la opción va gratis). **Decisión (estructura cerrada, calza
  con doc 29 §7/§8):** la opción gratis entra como **DESEMPATE en el ranking intra-celda, NUNCA como multiplicador
  del size** (size sigue `min(caps)`, invariante anti-hype). Se mide con la **misma rúbrica citada del carril (§3)** —
  una sola maquinaria, dos usos. **Distinguir:** upside CONTRATADO ya cuenta (entra al operable/asimetría); esto es
  solo para el ESPECULATIVO no contratado. **Magnitud del desempate = prior versionado** (calibrable, candidato a
  triangular). Se construye JUNTO con el carril (#11): la rúbrica alimenta ambos. Sin esto, un COVERED con moonshot
  gratis rankea igual que uno sin él.
- [ ] **E2 · Fuente de magnitudes contratadas = solo RPO (XBRL).** BÁSICO: el único insumo del escenario
  operable es el RPO agregado. **BIEN HECHO:** sumar awards/PO/take-or-pay/mínimos desde hechos citados +
  exhibits (Ex-10), con su tipo. Doble-conteo LTA+PO evitado por fuente canónica única (doc 28 §7 nº7).
- [ ] **E3 · Invariante I2 (bear despojado de no-recurrentes) NO aplicado en templates.** BÁSICO:
  `templates.escenario_operable` no despoja el bear de grants/NRE/venta-de-equipo/contratos únicos (un bear con
  grant del DOE es un bull disfrazado). **BIEN HECHO:** identificar no-recurrentes como hecho citado/XBRL y
  restarlos del bear. Depende de extracción (como E1). No conflictúa con doc 33.
- [x] **E3-bis · I3 (dilución obligatoria EN el bridge) — DESCARTADO (superado por doc 33 §4).** doc 28 §2 metía la
  dilución dentro de la valuación (acciones diluidas a T); **doc 33 (canónico, posterior) decidió dilución = EJE
  SEPARADO, no se mezcla en la valuación** — ya implementado en `dilucion.py` (burn_yield/runway) + `capital_risk_tier`.
  Aplicar I3 sería doble-contar. `DESCUENTO_DILUCION`/`PPE_REALIZABLE` quedan sin uso (o para el piso de balance).
  Pendiente REAL relacionado: la regla de combinación de doc 33 ("penaliza solo si falla en AMBOS ejes: cara Y
  diluyendo") — es lógica de ranking/sizing, no del bridge; ver Bloque 2.
- [ ] **E4 · Falsador CAGR sobre bridge de perpetuidad mínimo** (no template completo por arquetipo). OK por
  diseño (es diagnóstico, no price target — doc 28 §4). Los templates A/B/C/D completos (márgenes 8Q min/mediana,
  terminal gating, template físico D q·u·P) siguen diferidos (doc 28 §3, §8).

### E.2 · Hygiene / deuda técnica detectada
- [ ] **E5 · `valuacion.py` tiene tabla `r` propia y divergente** (`TASA_DESCUENTO` 0.10/0.14/0.16/0.22) —
  el mismo "juicio duplicado" que v1.1 mató en `ranking._TASA`. El módulo (motor de pares) está DESENCHUFADO.
  **BIEN HECHO:** alinear a `politica.R_ARQUETIPO` o borrar el módulo si no se va a usar. Bajo riesgo (sin callers).

### E.3 · Diferidos de RETRIEVAL (sesión 2026-08-13, motor de evidencia)
- [ ] **E6 · Brecha de vocabulario de anchors: negativo explícito + denominador ARR.** Descubierta por el set
  random (S: "no customer accounted for **more than** X% of **ARR**" → MISS_A). Ampliar anchors, medir en dev
  (no en el random). Barato.
- [ ] **E7 · Residual AAOI `demanda_realizada` (MISS_C poco denso).** Su región tiene 1 solo anchor → el ranker
  por densidad no la promueve. Candidatos: subir `max_regs` (medir trade precisión/budget) · señal específica de
  demanda-realizada · resolución 8-K (`resolver_8k` ya existe). No forzar (riesgo de sobreajuste).
- [ ] **E8 · Gold con múltiples spans válidos por hecho.** Hoy el gold etiqueta 1 span; el filing tiene varios
  (baja la métrica "cita-en-gold" sin ser error). Enriquecer los OR-groups del gold. Cosmético de la métrica.
- [ ] **E9 · ~10 tickers random como regresión permanente en CI** + corrida LLM `P(correcto|HIT)` periódica.
- [x] **E10 · Extracción estructura-consciente por período (fix 3 profundo).** DIFERIDO **justificado por dato**:
  P(correcto|HIT)=100% y 0 citas en distractor → el modo de falla de período no se materializó en el seed. NO se
  construye hasta que la evidencia lo pida (evita sobreingeniería). Ver doc 32 bitácora 2026-08-13.

---

## F. Pendientes heredados de docs de rediseño (recogidos en el censo 2026-08-13)

> Ítems reales que estaban dispersos en docs viejos (marcados en `00_MAPA_DOCUMENTOS.md`); traídos acá para
> que no se pierdan. Muchos son parte de bloques ya nombrados en doc 32 §5 (se referencia el bloque).

- [ ] **F1 · Hardening de extracción XBRL — Fase 1 (doc 30).** Wins baratos parcialmente hechos: `_extract_shares`
  con flag de staleness ✅ (doc 14 §D). ABIERTOS: **fail-loud** de shares/deuda · **security master keyed por CIK**
  (detecta deslistadas) · **sanity check de mcap** (feed vs precio×shares) · **tiers de confianza A/B/C/D por dato**
  (para que el compiler sepa qué admitir) · reconciliación de deuda por árbol. Fase 2 (Arelle, dimensionales) diferida.
- [ ] **F2 · Ledger fiel `nx_*` + unificación de libros paper (doc 16, Etapa 2 / doc 32 §5 Bloque 4).** Tablas
  append-only en la DB (hoy el paper usa `libro.json` de fracciones); doble P&L (ideal vs modelada); baseline/capital
  inicial versionado. El stack fiel (`ledger/`, `pm.py`) está construido y testeado pero SIN caller ni tablas.
- [ ] **F3 · Tablas de caps + harness (doc 25 / doc 32 §5 Bloque 2).** `evidence_cap[arquetipo][tier][materiality]`
  y `tier_min[arquetipo]` (valores sin calibrar); familias de test A-H del harness; `reason_codes` enum (Bloque 3).
- [ ] **F4 · Cortar el cordón umbilical del universo (doc 12).** `_tickers_vivos()` ← `Ficha.estado` del sistema
  viejo; discovery/Filtro-0 nuevos vivos; reconstrucción de vistas del dashboard (doc 32 §5 Bloque 4).
- [ ] **F5 · Loop de medición / backtesting (doc 26 / doc 14 §C7).** Loggear el vector de bandas y medir retorno
  forward por decil; es el forward-test que valida (o no) el edge. Se solapa con C7.

---

## G. Ficha de evaluación de empresas — reconciliación (censo funcional 2026-08-13)

> Surgió de reconciliar el modelo funcional del operador (filtro → análisis fundamental → PM) con el código.
> El análisis fundamental (los 4 pilares) es lo más completo del sistema, PERO hay dos superficies paralelas.

- [ ] **G1 · Componer las DOS superficies de evaluación (nudo real, DIAGNOSTICADO 2026-08-13).** Hay dos mitades
  construidas que NO se integran ni se cablean al PM:
  - **Stack A — 4 pilares → tier → FichaPM → PM.** `pilares.py` (Demanda·Economía·Ejecución·Valuación) →
    `evaluacion.evaluar` (tier CONJUNTIVO A/B/C) → `ranking.evaluar_ticker` → `pm.FichaPM`/`proponer_mix`.
    **Construido + testeado, pero `evaluar_ticker` y `proponer_mix` NO tienen caller vivo.** Es la ficha
    cualitativa (tier) que doc 33 pide, desconectada.
  - **Stack B — path vivo del `/hoja`.** `hoja_evidencia`+`templates`+`pre_revenue`: números de valuación
    (bull/bear/burden/múltiplo). Es lo que se genera y muestra. Solo reusa el helper de demanda de `ranking`.
  - **NO es "borrar una".** Son las dos mitades de la comparación de 2 niveles (doc 33): B = los NÚMEROS, A = el
    TIER conjuntivo. **El trabajo:** que los números de B ALIMENTEN el pilar de valuación de A → los 4 pilares
    producen el tier → tier + números → `FichaPM` → PM. Esto es también el Bloque 2 (doc 32 §5). **Próximo paso.**
- [~] **G2 · Pilar 3 (Ejecución/Management) — sourcing de inputs — CASI HECHO (2026-08-18).** La lógica existe
  (`pilar_ejecucion`). ✅ **insider neto de Form 4 HECHO:** `edgar.get_insider_activity` parsea el XML crudo real
  (código P/S = compra/venta a MERCADO; excluye grants/ejercicios/tax/regalos), cachea por (ticker,ventana) 24h,
  expone `net_usd`; wireado a `ranking.evaluar_ticker` (ventana 12m). ✅ **SBC/revenue HECHO:** `sbc_ttm`/`revenue_ttm`
  de XBRL → `sbc_pct_revenue` con scoring en el pilar (>20% penaliza, <5% suma). Validado end-to-end: CLS insiders
  −$234M/SBC 1%, S −$22M/SBC 29% (dilución silenciosa alta bien flaggeada). Dilución 3y + crec-por-acción ya estaban.
  337 tests. **FALTA solo (Fase 2, bloqueado por FMP):** ratio **guidance-vs-actuals** (necesita transcripts).
  Fino menor: la confianza del pilar aún exige dilución+crec-por-acción; podría contar insider+SBC como señales duras.
- [ ] **G3 · Pilar 4 (Valuación) — reconciliar con el bridge cohort-free.** `pilar_valuacion` (doc 26) usa
  `multiplo_terminal` de **comparables** P50; el path vivo (doc 28/`templates`) es **cohort-free** a propósito.
  Alinear: o el pilar adopta el bridge cohort-free, o se decide reintroducir comparables (post-8Q). Ligado a G1.
- [ ] **G4 · Decisiones de método a NO perder de vista** (no son gaps, son diseño cerrado; revisables con evidencia):
  **comparables** fuera del MVP (cohort-free, doc 28 §2) · **probabilidades** del bull/bear NO se ponen (doc 28/29).
  Si el operador quiere reintroducir alguna, es conversación de método, no olvido.
- [ ] **G9 · SIZING por burden + quién dimensiona (hallazgo de la VALIDACIÓN 2026-08-14, a TRIANGULAR).** La
  validación (system vs disciplinado vs naive sobre RKLB/LEU) mostró: el análisis es holístico y el sistema es
  SOBRIO (converge con el disciplinado; evita el hype), y el **RPO $0.8B se confirmó** (el disciplinado usó la
  misma cifra ASC-606). PERO 2 cosas: (a) el sistema les da **cap completo (8%)** pese a burden 53/11 → el burden
  (= la valuación HOLÍSTICA: economía actual + forward que exige el precio + precio) **debe achicar el SIZING**,
  no mandarlas a otro bucket (tienen evidencia dura → son "caras-anchored", no pura opción). (b) **¿quién
  dimensiona?** tensión: PM-LLM propone dentro de [piso,cap] (doc 14 A2) vs núcleo determinista + PM mínimo
  (triangulación IA2: "sizing sale del núcleo, discreción del PM solo sobre inputs, no outputs"). Si el burden
  achica el cap, se le saca al PM la palanca de sizing. **Prompt de triangulación:** scratch `triangulacion_
  sizing_burden.md`. NO tocar el sizing hasta cerrar esto.
  - ✅ **RESUELTO (IA1+IA2 convergieron, 2026-08-18) → doc 34 §3ter.** Núcleo dimensiona (PM solo reduce/excluye).
    **Dos ejes ortogonales: EVIDENCIA→libro (inmutable) · VALUACIÓN→tamaño (variable).** `size = min(caps
    independientes)` no-compensatorio + retícula discreta + reason codes. `cap_valuación` = 4 estados por cobertura
    de GP_req (COVERED/STRETCH/OPTION_PRICED/NON_UNDERWRITABLE). **Arreglo previo (hacer 1º): burden con dilución de
    financiamiento del burn** (ρ real, no ρ=1). RKLB = HARD_EVIDENCE + OPTION_PRICED → piso. Test: mejor-evidencia →
    menor-tamaño.
- [ ] **G8 · Ruteo del gate/orden de valuación por owner-FCF (hallazgo del shadow 2026-08-14).** Para owner-FCF<0
  el modelo operable gatea `bull=bear=piso` → la **asimetría es −1.00 y no significa nada**, y el **falsador es
  `no_evaluable`** (margen<5%). Consecuencia en el shadow: LEU (Tracción con $800M RPO, revenue real — NO pura
  opción) entra al libro duro con asimetría −1.00, sin que el gate ni el orden la traten bien. **Fix (2 niveles
  de doc 33):** rutear por arquetipo/route — **FCFE_OPERABLE** → gate=falsador, orden=asimetría; **NON_FCFE/
  owner-FCF<0** → gate=`price_anchor_status` (PURE_OPTION fuera del libro duro→carril) + `reverse_burden`, orden
  DENTRO del arquetipo por **menor burden**. El paso "asimetría cap5×" del lexicográfico debe ser "asimetría O
  burden según arquetipo". Es la comparación de 2 niveles de doc 33 aterrizada en el `CandidatoLex`.
  - ✅ **GATE ruteado HECHO (2026-08-14):** `candidato_desde` — FCFE_OPERABLE→falsador · NON_FCFE→`price_anchor`
    (PURE_OPTION fuera). Verificado en shadow: LEU/RKLB (NON_FCFE ANCHORED, revenue real) pasan por anchor;
    TENB/BWXT/OKTA (FCFE) los mata el falsador. `CandidatoLex` lleva route/burden/price_anchor. 297 tests.
  - ✅ **RESUELTO por triangulación (IA1+IA2 convergieron, 2026-08-14) → doc 34 §3bis.** Ranking = prefijo global
    (gate→tier→cobertura) → corte por arquetipo → llave económica LOCAL (asimetría FCFE / burden-TUPLA pre-revenue)
    → sufijo global; cartera por CELDAS (arquetipo×tier) con cuotas ex-ante. **Asimetría pre-revenue = N/A, no −1.00.**
    Y **A1** (tier de demanda) = 100% determinista + ABSTENCIÓN bajo umbral de cita + PM solo sobre inputs, override
    asimétrico (nunca promueve). **UNKNOWN demanda = abstención, NO CRÍTICO** (bug a arreglar). A1-duro es precondición.
  - ⏭️ **CASH_POSITIVE = 3er route** (no 2): hoy cae al gate de anchor (S falla con burden bajo). Afinar el ruteo.
- [ ] **G7 · Fuentes que faltan para el `CandidatoLex` del ranking lexicográfico** (doc 34 §2, gaps del paso 3):
  **cobertura** (fracción del registry con hecho fundado — la calcula el caller desde el fact store snapshot;
  falta el wrapper que la pase) · **catalizador** (¿hay catalizador fechado y cercano? — hoy `False`, no hay
  señal citada todavía; la última prioridad del orden lexicográfico no discrimina hasta sourcearla) ·
  **liquidez_adv** (ADV desde `market_data`; cablear en el wrapper). Ninguna bloquea el orden; degradan a neutro.
- [ ] **G5 · CONTRADICCIÓN ESTRUCTURAL: valuación = ¿pilar o gate? (a resolver en la triangulación del método).**
  doc 33 (canónico) dice **valuación = GATE SEPARADO** (falsador), y pilares conjuntivos = **3** (Demanda·Economía·
  Ejecución). Pero `pilares.py`/`evaluacion.py` (doc 26) tienen valuación como **Pilar 4** (4 pilares). Antes de
  componer la ficha (G1) hay que cerrar la FORMA: 3 pilares + valuación-gate (doc 33) vs 4 pilares (doc 26). Bloquea G1.
- [~] **G6 · Pre-pass de coherencia HECHO (3 subagentes, 2026-08-13) → META-HALLAZGO que da vuelta la pregunta.**
  La mayoría de las "contradicciones" NO son incoherencias del MÉTODO — son **LAG DE IMPLEMENTACIÓN**: el código
  encarna **TRES superficies de evaluación medio-migradas** y ninguna matchea el target canónico:
  (1) `flujo`/`selector`/`sizing` **merito=Quality×Asimetría** (score cardinal, LIVE en el paper — lo que doc 33
  quiere jubilar); (2) `pilares`/`evaluacion` 4-pilares→tier (doc 26, desenchufado); (3) `hoja`/`templates`
  cohort-free (doc 28, semi-vivo). **Dentro del set canónico (33/27/28) el método es casi coherente** (una arruga:
  I3 dilución, ya resuelta a favor de 33). → **Una triangulación externa amplia mayormente RE-CONFIRMARÍA doc 33
  (bajo valor).** Inventario completo en scratch `coherencia_metodo_prepass.md`. Dos pilas:
  - **PILA A — forks de método genuinos (decidir):** A1 tier de demanda determinista (doc 33) vs orientativo
    (decisión 2026-08-11 post-33) · A2 confirmar forma target (3 pilares + valuación=GATE, no Pilar 4; bull/bear
    cohort-free alimenta el gate) · A3 matar `merito`, ranking lexicográfico (orden exacto). A2/A3 ya casi decididos
    por doc 33/27 → confirmar. Solo A1 es conflicto vivo.
  - **PILA B — lag de implementación (construir hacia el target, NO triangular):** refactor a UNA superficie
    (3 pilares alimentados por cohort-free → FichaPM → PM; jubilar merito) · ranking lexicográfico · valuación-gate ·
    tier→cap 8/5/2.5% · invariantes I1/I2 · dilución realizada a la economía · carril · limpieza (`DESCUENTO_DILUCION`,
    comentarios "2%", doc 32 §rotación).
  - **RECOMENDACIÓN:** saltear la triangulación amplia; escribir el SPEC del flujo target (reconciliado a 33/27) +
    plan de refactor; decidir A1 (quizá con chequeo externo puntual). El refactor es el nudo, no más método.
  - **HECHO 2026-08-13/14 → `34_flujo_evaluacion_target.md`** (spec de la superficie única + secuencia de refactor
    en 6 pasos + qué pasa con cada superficie actual). A2/A3 fijados ahí; A1 recomendado (orientativo+cita, norte
    determinista). **El refactor (Pila B) sale de ahí §4.** #7 (componer ficha) = paso 5 de esa secuencia.
