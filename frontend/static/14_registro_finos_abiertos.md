# 14 — Registro de finos abiertos (checklist vivo)

> Todo lo que falta cerrar para que el sistema funcione bien. Se va quemando a medida
> que decidimos. Complementa la constitución (`13_`). Cada ítem: `[ ]` abierto ·
> `[x]` cerrado (con la decisión). Marcados **[TRIANGULAR]** los que conviene pasar por
> una segunda IA antes de darlos por firmes.

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
