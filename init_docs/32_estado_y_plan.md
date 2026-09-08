# 32 — Estado del sistema + Plan de trabajo (documento VIVO)

> **Fuente de verdad única.** Reemplaza el tener que acordarse de todo o reconstruir de memoria.
> Se actualiza cada vez que cerramos una tajada. **Primer archivo a leer al empezar una sesión.**
> Grounded contra el código real (última re-verificación **2026-09-07**), no contra memoria. Cuando el
> código y un doc viejo se contradicen, manda el código (ver §7).
>
> ### ⚑ FRENTE ACTIVO (al 2026-09-07) — leer esto primero
> Secuencia real reciente: (1) **3-sep** — `sizing_burden` Fase 1 cerrado (doc 47, política v2.3: el módulo
> da un **CAP [4%,8%]**, no el tamaño); (2) **4-sep** — arrancó el **Bloque 3 del rebalanceo (doc 39/40): el
> canal de juicio PM-LLM** (`backend/nucleo/flujo_pm.py` + `juicio_llm.py`). **Ahí quedamos.** El canal está
> **construido + unit-testeado pero SIN CALLER VIVO** (mismo patrón "construido-y-desenchufado"): nadie lo
> invoca desde paper/scheduler/ui/ops. Falta cablearlo + resolver la decisión abierta §2.7 (piso de despliegue
> / ledger de rechazos). Ver §4 y §8 (entradas de septiembre) y la memoria `canal-juicio-pm-llm-bloque3`.
> ⚠️ Ojo: la numeración de "Bloques 0-4" de la §5 de acá es la del plan VIEJO (retrieval/universo/PM-en-caps),
> NO la del rebalanceo (doc 40). Cuando choquen, manda doc 40.

---

## 0. TL;DR — la verdad de fondo

Estamos construyendo **UN sistema nuevo** (el viejo `backend/agents/` está congelado, solo insumo).
Pero hoy conviven **tres "stacks nuevos" que NO son el mismo, y dos de ellos están desconectados**:

1. **Núcleo determinista LIVE** — el único que opera el paper (`paper_trader.py` + `libro.json` en
   *fracciones*). **Sin PM, sin ledger de acciones, y usa el extractor VIEJO (memoria del LLM).**
   Es lo que mueve el capital simulado y reporta el equity de la home.
2. **Stack fiel + PM** (`ledger/`, `ingreso/`, `pipeline.py`, `pm_loop.py`, `deploy.py`) — construido y
   testeado, **sin caller vivo**; las tablas `nx_*` **ni existen en `borja.db`**.
3. **Motor de evidencia + compiler de valuación** (`analisis.py`, `fact_store.py`, `extractor_citado.py`,
   `compilador.py`, `politica.py`, `ranking.py`, `pilares.py`, `pre_revenue.py`) — construido y testeado,
   **sin caller vivo ni integración**; al compiler le faltan los VALORES (haircuts, templates).

**El gap real no es diseñar más — es CABLEAR + completar valores + integrar.** El "corazón inteligente y
honesto" del rediseño está escrito pero enchufado a nada; lo que corre es la versión que queremos jubilar.

**Marco de uso:** sistema **ADVISORY** (el operador ejecuta a mano en Interactive; es el humano en el loop).
→ el valor está en **calidad de la propuesta rankeada + dashboard + rotación**, NO en autonomía. Buena
parte del endurecimiento autónomo (doc 25 Fases D/E: replay/canary/cutover) es sobreingeniería para este goal.

---

## 1. Arquitectura objetivo en una página (lo que NO se re-litiga)

Flujo canónico end-to-end (doc 27 §2; nombres exactos de módulo/etapa):

```
0.  Mapa sectorial → universo            (macro DEFINE el universo, NUNCA puntúa mérito)
1.  Screen $0                            (elimina lo no-analizable; no rankea calidad)
2.  Priority score                      (cola de investigación 0/1/2; no es score de inversión)
3.  Motor de evidencia → fact store     (hechos citados+verificados; COBERTURA como número)
4.  Elegibilidad: 3-4 pilares CONJUNTIVOS   (Demanda·Economía·Ejecución[·Valuación] = Pass/Fail/Unknown)
5.  Valuación = GATE separado de falsificación  (CAGR implícito; o participación FÍSICA si rev≈0)
6.  Scenario compiler → caso operable   (bull/base/bear; cada término con REGLA autorizada o vale 0)
7.  Option ledger O0–O5                  (opcionalidad fechada/falsable; se MUESTRA, no se valúa)
8.  Tier → CAP                          (A/B/C → 8% / 5% / 2.5%)
9.  Ranking LEXICOGRÁFICO               (gate→tier→cobertura→asimetría operable cap 5x→catalizador→liquidez)
10. Sizing = min(caps)                  (arquetipo·evidencia·fragilidad·liquidez·sector)
11. Cartera                             (~8 pos = 6 duras + 2 opcionales; caps por sector; margen 20% p/ desplazar)
    └─ carril especulativo: piso 10% → techo 25% (ganado por hit-rate 8Q); máx 2 plazas; cap 8%/pos
12. Rotación: 5 vías + milestone-miss + evidence-decay
```

**Decisiones grandes CERRADAS (trianguladas):**
- **LLM clasifica hechos citados / el compiler determinista decide los valores.** El LLM nunca emite un valor.
- **Valuación = gate separado** (CAGR implícito como *falsador*, no generador), no un pilar.
- **Ranking lexicográfico**, no score fusionado. Asimetría operable capada a 5×.
- **Tier → cap** A/B/C = 8/5/2.5%. Salida = TIERS, no ranking cardinal.
- **Opcionalidad = 0 en el bull, SIN probabilidades** → option ledger O0–O5 (de O2 arriba exige doc de tercero).
- **Carril especulativo con presupuesto propio** 10%→25%; nunca desplaza al carril duro; log = interruptor de apagado.
- **Rankear por Δ de evidencia, no por nivel.** El bear case = **dilución por acción** (I3), no compresión de múltiplo.
- **Bridge cohort-free**: márgenes de historia propia (mín/mediana 8Q), terminal UFCF/r g=0, `r` por arquetipo (§ política).
- **Juicio = política versionada, no instancia**: cambiar una constante bumpea versión y obliga a recorrer TODA la cartera.
- **Composición conjuntiva de pilares** (no-compensación: una debilidad crítica topea el tier).
- **Auditabilidad total**: cada número → qué hecho lo originó / qué regla / por qué / qué lo invalida; replay desde `fact_store_version_id`.

Docs canónicos: **27** (arquitectura), **28** (compiler/valuación/haircuts/ledger), **29** (carril especulativo),
**26** (framework de ranking v3), **31** (pre-revenue), **22/23** (motor de evidencia + demanda), **30** (extracción).

---

## 2. Dónde estamos — las 9 etapas (estado REAL, verificado en código)

| # | Etapa | Estado | Módulo(s) | Qué falta |
|---|-------|--------|-----------|-----------|
| 1 | Mapa estructural | **PARCIAL** | `mapa/nodo,brujula,transiciones`; `ledger::NxNodo` | Brújula se muestra; nodos NO se persisten (tablas `nx_*` ausentes), sin caller vivo. |
| 2 | Discovery por hechos | **STUB** | `mapa/discovery.py` (huérfano); discovery viejo agendado | El nuevo no tiene caller; el viejo no crea Fichas del núcleo. Barrido LLM por firmas = pendiente. |
| 3 | Candidatas (manual+desc.) | **PARCIAL** | live: intake viejo (`Ficha`); fiel: `ingreso/flujo.py` | La puerta única nueva no está viva; intake real crea `Ficha` vieja. |
| 4 | Filtro 0 barato | **CONSTRUIDO, desenchufado** | `ingreso/filtro0.py`, `admisibilidad.py`; live: screener viejo | El Filtro 0 nuevo solo lo llama `pipeline.py` (no corre). Actúa el screener viejo. |
| 5 | Deep research / ficha rica | **PARCIAL, desenchufado** | `analisis.py`, `compilador.py`, `pilares.py`, `pre_revenue.py`, `templates.py`, `realizacion.py`, `dilucion.py` | Superficie enorme construida+testeada, **sin caller vivo**. `/analizar` dispara el Analista VIEJO. Compiler sin haircuts. |
| 6 | Universo vivo comparable | **PARCIAL** | `hoja_evidencia.py` (+ `/hoja`), `watchlist.py`, `estado.py` | La hoja rankea FCFE; los NON_FCFE/pre-revenue quedan descriptivos (falta pre-revenue Fase 2). |
| 7 | **PM dentro de caps** | **CONSTRUIDO pero BYPASSEADO** | `pm.py`, `pm_loop.py`, `validador.py`, `deploy.py`; caller: `pipeline.py` (sin scheduler) | El paper vivo es 100% determinista; el PM-LLM **no toca el loop**. Falta cablear + tablas + migrar libro. |
| 8 | Sparring + aprobación | **STUB** | `sparring.py`, `puntos_humanos.py` | No hay 2º LLM adversarial en el flujo ni loop de aprobación (paper opera sin confirmación, por diseño). |
| 9 | Monitoreo / rotación | **CONSTRUIDO-CABLEADO** ✅ | `jobs.py`, `scheduler.py`, `paper_trader.py`, `salida.py`, `paper_pnl.py` | Lo más vivo. Challenger APAGADO (`CHALLENGER_ACTIVO=False`); rotación de 3 cadencias (Art. 7) no está (todo diario). |

**El punto crítico (etapa 7):** `paper_trader.correr_ciclo` NO importa ni llama a `pm.py`/`pm_loop.py` — su
docstring dice *"decisión 100% DETERMINISTA, sin juicio del PM"*. El PM-LLM solo lo invoca `pipeline.py`, que
**no tiene ningún caller** (ni scheduler, ni main, ni ops). Todo el andamiaje "PM propone → validador → deploy"
existe y está testeado, pero **desconectado**. El delta real = **cablear + crear tablas + migrar el paper de
libro-fracciones a ledger-acciones**.

---

## 2bis. Mapa FUNCIONAL (lente del operador — qué HACE el sistema)

Las 9 etapas de §2 son la lente de implementación. Esta es la lente funcional (el proceso de inversión
como lo piensa el operador); es el MISMO sistema, otro corte. Reconciliado con el código 2026-08-13.

| Componente funcional | Etapa/módulo | Estado |
|---|---|---|
| **Filtro inicial de empresas** | Screen $0 / Filtro 0 | 🔨 nuevo construido, desenchufado; corre el screener viejo |
| **Análisis — revenue Y pre-revenue** | split owner-FCF (doc 33) | ✅ vivo: revenue→`templates` · pre-revenue→`pre_revenue` (reverse underwriting) |
| **Valuación base/bull/bear** | `templates`+`compilador`+`bridge` | ✅ hecho (spread real, RPO→bull, falsador) |
| **Pilar 1 Demanda + cuello** | `pilares.pilar_demanda` | ✅ lógica lista (tier de demanda citado + nodo) |
| **Pilar 2 Economía** | `pilares.pilar_economia`/`quality` | ✅ lógica lista (márgenes, crecimiento, recurrencia, wins) |
| **Pilar 3 Ejecución/MANAGEMENT** | `pilares.pilar_ejecucion` | ✅ lógica lista · ❗ faltan inputs (insider Form 4, guidance-vs-actuals) + cablear |
| **Pilar 4 Valuación/asimetría** | `pilares.pilar_valuacion` | 🟡 doc-26 (usa comparables); el path vivo usa el bridge cohort-free → RECONCILIAR |
| **Arquetipos · Dilución · Fragilidad** | clasificador · `dilucion` · caps | ✅/🟡 mayormente vivo (dilución = eje separado) |
| **Capacidad física (q·u·P)** | template D pre-revenue | ⏳ diferido Fase 2 |
| **Sizing / caps** | tier→caps + fragility | 🟡 construido, no del todo cableado (Bloque 2) |
| **PM que elige** | `pm.py` dentro de caps | 🔨 construido, BYPASSEADO (paper es determinista) |
| **Mapa de industrias** | `mapa/` (etapa 0) | 🟡 brújula se muestra; nodos no persisten; discovery sin caller |
| **Agente info externa** | discovery / motor evidencia | 🟡 EDGAR/mercado/RSS sí; research externo amplio diferido |

**Dos decisiones de método a tener presentes (no son gaps, son diseño):** (a) **comparables** = fuera en el
MVP (cohort-free, doc 28 §2; pueden volver post-8Q); (b) **probabilidades del bull/bear** = NO se ponen
(doc 28/29: la "prob" de un LLM es proxy de hype); la *fuerza* del caso la da cobertura/tier de evidencia +
burden + option ledger. **Nudo abierto:** hay DOS superficies de evaluación (los 4 pilares `pilares.py`/doc 26
vs el path vivo `templates`+`pre_revenue`) → reconciliar cuál es la ficha canónica (doc 14 §G).

## 3. Motor de evidencia — construido vs. diseño (el gap que más importa)

**Construido y testeado:** `extractor_citado.py` (extrae hecho de un chunk REAL del 10-Q/10-K + quote verbatim),
verificación determinista fuera del LLM (substring+offsets, contraste XBRL 2%, entailment adversarial),
`fact_store.py` (ledger `NxFact` append-only, snapshot point-in-time, `diff()` de evidencia), `retrieval.py`
(incl. EDGAR full-text search — "consultar, no crawlear"), `gate_evidencia.py` (tiers de demanda desde hechos
binarios citados), `admisibilidad.py`/`compilador.py` (MECÁNICA de ruteo hecho→operable/ledger + trazabilidad).

**Diseño / no cerrado:** los VALORES de haircut (`admisibilidad._OVERRIDES = {}` vacío) · templates revenue→precio
por arquetipo · catálogo de `fact_key` (hoy **14** specs) · cortes tier→cap · **K=3 unanimidad** en booleanos
gate-críticos (hoy 1 llamada + 1 reintento) · gold set (hoy **4 nombres**, el doc pedía 25-50 difíciles).

**El bug de fondo que sigue vivo:** el motor citado **no alimenta al paper**. El `paper_trader` usa el
**extractor viejo** (`extractor.py`), al que **no se le pasa el 10-K** — lo cualitativo (bull/bear incluido)
sale de la **memoria del LLM**. Es la "Versión A" que el doc 20 prohíbe: causa la inestabilidad (COHR flipeó
candidata↔rechazo entre corridas idénticas; TENB mérito ±22%) y es lo contrario del edge.

**Riesgos de fondo (no olvidar):** verificado≠verdadero · citado≠material · **lo que nunca se extrajo domina**
(14 fact_keys → recall bajo) · heurísticos XBRL "plausibles pero contablemente falsos" (doc 30: que fallen
fuerte antes que extraer mejor) · **arreglar el extractor NO construye edge** — construye el terreno para
buscarlo sin engañarse; el alpha se prueba en **forward paper sellado**, no en backtest (look-ahead del LLM).

---

## 4. Lo hecho recientemente (contexto de continuidad)

- **2026-09-04 — Canal de juicio PM-LLM cableado end-to-end (Bloque 3 del rebalanceo, doc 39/40).**
  `juicio_llm.py` (el PM-LLM emite SOLO una etiqueta discreta —PRIORITY_*/ADMIT_PROBE/PASS/HOLD/THESIS_BROKEN/
  VETO—, bull+bear independientes + falsador escrito+fecha, **web search server-side real**, `fuentes`
  snapshoteadas para auditoría) + `flujo_pm.py` (`orquestar_pm`: candidato→`Banda[piso,base,techo]`→PM→
  allocator `juicio.aplicar_juicio`→`LibroPM`, contexto MAPA best-effort). Decisión del operador: `base=piso`
  (el determinismo despliega el piso; el PM gana el tramo hasta el techo con convicción presupuestada+falsable);
  contexto = SISTEMA+MAPA+WEB; el hype lo contiene el techo+presupuesto+ledger, NO la censura. **Estado:
  construido + testeado, SIN caller vivo** — falta el pegamento de producción (job, persistencia, `ledger_juicio.
  registrar`, vista). Detalle en memoria `canal-juicio-pm-llm-bloque3` y §8.
- **2026-09-02/03 — Sizing del bucket growth/BURDEN cerrado y construido (doc 47, Fase 1, política v2.3).**
  Triangulación 3 voces → esquema: Gate A supervivencia (`burn=CFO−capex` sin SBC) · Gate B dilución→valuación
  (`B_adj`) · **sizing por T_fade, NO por burden crudo** · override por acretividad (ΔGP/acción≥12%, apal con
  LAG 3Q) · cluster cap Σ≤2×CAP · piso-muerto <0.5%→0. Módulo `sizing_burden.py`. **El módulo produce un CAP
  en [4%,8%], no el tamaño** (sándwich doc 39). Vista `/sizing` + `ops/generar_sizing.py`. ~450 tests.
- **2026-08-10 (paquete Fase-1-hardening + eje dilución §5):** tabla `r` única (`politica` v1.1, borrado
  `ranking._TASA`), fix doble-castigo `r_exit`, eje dilución §5 (Δ acciones 12/24m + SBC/rev, suma-de-clases
  neutraliza Up-C). Triangulado 4 IAs. Ver doc 14 §D. Vive en la etapa 5-6 (motor de análisis/valuación).
- Antes: `realizacion.py` (R0-R5 + route sobre owner-FCF = FCF−SBC), `hoja_evidencia.py` (1ª vista rankeada),
  `dilucion.py` v2 (burn_yield forward), `politica.py`+`bridge.py`, `admisibilidad.py`+`compilador.py` (esqueleto),
  dashboard `/hoja`. Motor de evidencia citado (docs 21/22) hecho módulos.

---

## 5. Plan de trabajo secuenciado (PROPUESTA — a acordar)

Ordenado por valor para el uso **advisory** (propuesta rankeada honesta + dashboard), no por completitud autónoma.
Cada bloque cierra con tajadas chicas + tests + (donde toque decisión) triangulación.

### Bloque 0 — CALIDAD DEL RETRIEVAL (motor de evidencia) ★★ próximo hito, foundational
La sesión 2026-08-11/12 (pilar de demanda) reveló que **el cuello real de la capa citada es el retrieval/
cita**, no los gates: el extractor cita la línea equivocada (AAOI → línea del warrant en vez de Digicomm
42.8%) → falso negativo. Esto afecta a TODOS los pilares (no solo demanda), y es la RAÍZ de la tesis de
BORJA ("la IA procesa evidencia primaria fresca"). **Hacerlo MEDIBLE para no caer en tuneo a ciegas:**
- **0a · Gold set.** Para ~10 nombres, definir a mano cuál es el pasaje/respuesta CORRECTA de cada fact_key
  (ej. AAOI cliente_nombrado → la línea de Digicomm). Es el criterio de "listo" (antídoto al rabbit hole).
- **0b · Medir el hit-rate** del retrieval actual (`retrieval.py` anchors + `_window`) contra el gold.
- **0c · Mejorar** anchors / ventana / multi-pasaje / FTS dirigido hasta subir el hit-rate; re-medir; parar
  cuando amesetа. NO tuneo sin medición.
- Prerequisito de que Bloque 1a (cablear citado→hoja) y los pilares económicos sean confiables.
- **Ya aplicado (base):** `temperature=0` en `extractor_citado.py` (estabilidad — el extractor corría a 0.3).

### Bloque 1 — Universo comparable HONESTO (lo que el operador lee) ★ foco cercano
- **1a · Cablear el motor de evidencia citado → la hoja.** Que los hechos de un nombre vengan del
  extractor citado+verificado (chunk real del filing), no del extractor de memoria. Reemplaza el bug "Versión A".
- **1b · Completar los VALORES del compiler** (triangular): tabla de haircuts/retención + templates
  revenue→precio por arquetipo (A/B/C/D). Sin esto el compiler excluye todo. *(Decisión de modelo → triangular.)*
- **1c · Pre-revenue Fase 2** (para rankear de verdad los NON_FCFE): funded critical path + fracción asegurada
  + ρ real desde funded gap. Depende del parsing de notas + (opcional) scrapers de regulador.
- **1d · Dashboard:** surface el burden + eje dilución §5 + tiers + evidencia citada, estilo Banking/Finance.

### Bloque 2 — El PM dentro de caps (advisory) ★ el corazón del rediseño
- **2a · tier → caps** (`evidence_cap[arquetipo][tier][materiality]` con `min()`) — hoy falta; prerequisito del sizing objetivo.
- **2b · Ranking lexicográfico** — reemplazar Quality×Asimetría por gate→tier→cobertura→asimetría(cap 5×)→catalizador→liquidez.
- **2c · Enchufar el PM-LLM como PROPONENTE dentro de caps** (advisory): que su propuesta se **muestre** en el
  dashboard (no que opere sola). Validador rechaza-e-informa; el humano decide.

### Bloque 3 — Honestidad del snapshot (selectivo del doc 25 — solo lo que mejora la propuesta)
- Reason codes (en vez de un `UNKNOWN` único: NOT_FOUND/STALE/CONFLICTING/…) · CONTESTED (contradicción intra-snapshot)
  · frescura/decay. **NO** el harness de replay/canary/cutover completo (sobreingeniería para advisory).

### Bloque 4 — Alimentar la tubería sola (más adelante)
- Filtro 0 nuevo vivo · Discovery por firmas de hechos cableado · persistencia del mapa + link ticker↔nodo · carril especulativo (shadow).

### Housekeeping inmediato (barato, alto retorno de claridad)
- **Corregir `CONTEXT.md`** (hoy sobreestima cuánto del rediseño está vivo) y marcar docs 15/18 como
  desactualizados ("cero tests" es falso; el PM "existe pero desconectado"). Apuntar a este doc 32 como índice vivo.

---

## 6. Decisiones abiertas / a triangular antes de codear
- **1b · Haircuts + templates revenue→precio por arquetipo** — valores de modelo → triangular (repo-grounded lo hago yo; juicio de modelo se circula).
- **Alcance del doc 25** para uso advisory — cuánto endurecimiento hacer (rec: solo Bloque 3, diferir Fases D/E).
- **★ Pendientes: TODOS viven en `14_registro_finos_abiertos.md` (registro ÚNICO).** §D (hardening/dilución),
  **§E (bloque valuación/compiler + diferidos de retrieval — el worklist activo)**. Regla: MVP-básico se
  anota en doc 14 ANTES de codear (atajo nunca silencioso); se trabaja tras correr el MVP.

---

## 7. Contradicciones doc↔código a corregir (registradas 2026-08-10)
1. Docs 15/18 dicen **"CERO tests"** → hoy hay **~454 tests / 46 archivos** (al 2026-09-07; el "244" previo
   quedó viejo). De esos, 4 están en rojo por el test roto del canal PM-LLM (ver §8, 2026-09-07), no por regresión.
2. Doc 18 dice el PM **"no existe"** → **existe en código** (testeado); lo que falta es la **conexión al loop**.
3. Doc 18 lista "Ledger fiel" como en uso → está construido/testeado pero **las tablas `nx_*` no existen en `borja.db`** y el paper no lo usa (sigue en `libro.json` de fracciones).
4. `CONTEXT.md` presenta el núcleo determinista vivo como "el corazón" sin aclarar que el motor de evidencia
   triangulado y el stack PM+ledger fiel están **construidos-y-desenchufados** → el lector sobreestima lo vivo.

---

## 8. Bitácora de actualizaciones
- **2026-09-07 — Revisión integral (4 agentes) + re-sync de estado.** Se detectó que este doc y la memoria
  habían quedado ~5 días atrás (se cortaban el 31-ago). Ground-truth por mtime: el frente real es el **canal
  de juicio PM-LLM (Bloque 3)** del 4-sep, NO el sizing. Hallazgos de la revisión: (1) canal PM-LLM construido
  pero **DESENCHUFADO** (sin caller vivo); (2) **tests `test_juicio_llm.py` rotos** — mockean `call_llm_json`
  pero el código usa `call_llm_json_with_web_search` (usar_web=True) → **pegan a la API real, flaky, ~$2/suite**;
  (3) bug cosmético `juicio_llm.py:117` `web_searches` siempre 0 (attr inexistente; está en
  `metadata["web_searches_usadas"]`); (4) `temperature=0` NO se aplica en Opus (`llm.py:370`); (5) núcleo:
  **dos clasificadores de arquetipo divergentes** — el canónico `arquetipo.py` (ex-top por concentración) solo
  lo usa el sistema viejo; el pipeline nuevo usa `ranking._clasificar_arquetipo` (simple, SIN concentración) y
  ese es el que fija el hard_cap → nombre concentrado puede recibir cap equivocado. **Decisión de método ABIERTA
  (doc 39 §2.7): piso de despliegue sí/no** — el código adoptó "sin piso" (postura IA2) delegando la vigilancia
  al ledger de rechazos, **que aún no existe** → a triangular antes de cablear. Memoria nueva:
  `canal-juicio-pm-llm-bloque3`. Suite: 454 pass / 4 fail (los 4 = el test roto de arriba).
- **2026-08-31 (cont.⁴) — FIX #26: pura-opción pre-revenue → carril/probe.** `hoja` expone `revenue_ttm`;
  `candidato_desde` fuerza NON_UNDERWRITABLE cuando no-comercial + revenue < base-chica ($50M) = ancla inmaterial.
  SMR ($11M rev, $8B val) pasó UNDERWRITTEN→PROBE (coincide con 'evitar/pura-opción' del analista); comerciales
  intactos. 438 tests. Cierra el único miss del fresh-10.
- **2026-08-31 (cont.³) — Comparativa FRESH-10 (AMBA/CRDO/KTOS/AVAV/RKLB/SMR/OKLO/IONQ/TEM/ASTS) → edge GENERALIZA
  + 1 hueco nuevo.** Set fresco (nunca visto) para testear generalización sin overfitting. **🟢🟢 El edge sistemático
  de red-flags GENERALIZÓ: AVAV → REJECT por material weakness (igual que NABL) — 2 de 2 sobre nombres distintos,
  el analista lo marcó 'eliminatorio'. Reproducible, no suerte.** Convergemos 8/10 (KTOS→UNDERWRITTEN=su único
  'comprar core'; OKLO→REJECT; AMBA/CRDO/RKLB→chico; concentración CRDO 0.49 cazada). **🔴 Hueco NUEVO (#26): SMR
  (pre-revenue, Q2 rev $75k!) sale UNDERWRITTEN** — el path BURDEN→anchor toma su revenue de ingeniería como
  'ancla'; el #25 capó el tamaño (2%) pero no la ETIQUETA (debería ser carril/PROBE). + no penalizamos la dilución
  SERIAL (SMR 318→410M acciones/6m, ASTS +85%). Scorecard fresh-10 MEJOR que el primero (parejos/mejor — el edge
  de red-flags pesa cuando hay un AVAV). El set fresco validó generalización (edge + #25 + concentración) Y encontró
  1 gap concreto. Total hallazgos comparativas: #25 fixeado · #24 resuelto-por-diseño · #26 nuevo · gobernanza→B4. Testeé el PM-LLM sobre KLIC
  (piso de ciclo): emitió PASS DISCIPLINADO — vio el piso ("+122% YoY es rebote de ciclo, no durabilidad") y puso
  falsador "2 trimestres de recuperación sostenida". Reframe: nuestro PROBE en KLIC NO es un miss — es el sistema
  siendo MÁS disciplinado que el analista (que timea el piso con "comprar core-chico"). Por nuestra tesis
  (demostrado no proyectado; add sobre confirmación) la respuesta correcta es: probe ahora + AGREGAR cuando la
  recuperación se demuestre — y el falsador del juicio ("2 trimestres") ES un trigger de la escalera de add-on.
  El sándwich maneja la ciclicidad en ambas direcciones: KLIC (piso) conservador+probe+add-on-on-confirmación;
  CLS (pico) concentración→OPTION_PRICED 2% + juicio flaggea. **Meter un g_D normalizado-hacia-arriba habría sido
  acreditar mean-reversion NO demostrada = el hype que evitamos.** El fix determinista habría sido un ERROR. Los 3
  hallazgos de la comparativa n=10: #25 (coherencia) FIXEADO · #24 (ciclicidad) resuelto-por-diseño · gobernanza→B4. `hoja` expone `estado_ruteo`;
  `candidato_desde` capa a OPTION_PRICED cuando ruteo=BURDEN sin reverse-DCF (antes caía al path anchor→UNDERWRITTEN
  pleno). Validado en vivo: S/LEU/VRNS 2% (era pleno) — disciplina los SBC-heavy/diluyentes donde el analista
  objetivo nos ganaba (S 29% SBC, LEU +31% dilución → ahora chicos, alineado con "esperar/evitar"). CLS/KLIC sin
  cambio. 438 tests. Queda #24 (ciclicidad bidireccional, KLIC) + gobernanza (B4).
- **2026-08-31 — Comparativa n=10 vs IA objetiva ciega → 3 HALLAZGOS ESTRUCTURALES (n=2 los escondía).** Corrida
  sobre CLS/RBRK/TENB/S/KLIC/MP/LEU/VRNS/UEC/NABL. Veredicto honesto: COMPARABLE, analista LIGERAMENTE adelante.
  Empate en NABL (ambos REJECT/evitar por material weakness = nuestro edge sistemático) y en disciplina sobre los
  caros (RBRK/MP/UEC/CLS converge). **Hallazgos:** (1) **🔴 CICLICIDAD CORTA PARA LOS DOS LADOS** — el único
  "comprar" del analista fue KLIC (semis saliendo del piso de ciclo, P/E 13.7x, net cash) y nosotros lo tenemos
  NON_UNDERWRITABLE/PROBE porque g_D=demostrado=0% (piso) no ve la recuperación. INVERSO de CLS (sobre-acreditamos
  el pico 23%, sub-acreditamos el piso 0%). Punto ciego estructural del reverse-DCF en giros de ciclo → #24. (2)
  **🔴 bug BURDEN-pero-UNDERWRITTEN SISTEMÁTICO** (S/LEU/VRNS rutean BURDEN pero salen UNDERWRITTEN vía anchor path)
  → nos sub-disciplina en SBC-heavy/diluyentes (S 29% SBC, LEU +31% dilución) donde el analista dice esperar/evitar
  → #25. (3) **🟡 falta señal de GOBERNANZA** (dual-class/control fundador — analista lo flaggea en RBRK) → Bloque 4.
  n=10 fue mucho más informativo que n=2 (razón: subir el n reveló que el bug de coherencia es sistemático y que la
  ciclicidad es bidireccional). Los 3 huecos son concretos y arreglables (no es "el enfoque está mal").
- **2026-08-28 — Escalera de add-on: método CERRADO (doc 46, triangulado) + MECÁNICA determinista construida.**
  Triangulación #23 (IA1+IA2 convergieron casi total): la escalera NO es módulo — es `stage` que escala el techo
  del min(). `escalera.py` (funciones puras): `w_target = STAGE_FRACTION[stage]×live_cap` · `probe_f0` (por densidad
  de triggers) · `puede_add` (gate A1-A6: evidencia dispara / valuación vetea / margen de falsación derivada
  anti-sapo-hervido / target>peso / presupuesto) · **`regla_trim`** (LA guarda del modo de falla #1: la valuación
  CONGELA no vende; trim SOLO por peso DRIFT_LIMIT o falsación, NUNCA por caro ni por ganancia; el ganador redefine
  la cartera no la destruye). Politica: STAGE_FRACTION, DRIFT/TRIM, tolerancias. 12 tests, 438 total. FALTA (Bloque
  4, requiere datos): tabla de triggers hasheada + evaluador determinista + extracción de hechos de milestone (RPO/
  financiamiento/hito) + wire a posiciones stateful + ledger contrafáctico + extracción ciega al P&L. La MECÁNICA
  está lista; los TRIGGERS necesitan extracción. **TODO el método del proyecto está ahora cerrado y triangulado**
  (docs 36/37/39/42/46) — de acá es ejecución + datos, sin forks de método abiertos. `binaria.py` (doc 42 §1):
  `v_fracaso` = piso de liquidación SOLO XBRL (cash+ST−debt−burn×P90−wind_down, floored 0, texto solo resta) +
  `estado_binario` = quinto estado (sin base-rate table → underwritable solo si `Precio_ops ≤ V_fracaso×k`, si no
  NON_UNDERWRITABLE → carril/probe). Politica: WIND_DOWN_QTRS/BURN_P90/K_FLOOR. 7 tests, 426 total. Validado: UEC
  precio 33× el piso → NON_UNDERWRITABLE, LEU 6× → NON_UNDERWRITABLE (correcto: sin denominador del evento, no hay
  margen). DIFERIDO (doc 42 §7): P_req@r + V_éxito Tier-A/B/C (necesita tablas externas + extracción de contratos)
  + wire a ruteo (hoy nada rutea a BINARIO: requiere extraer 'hito nombrado'; Bloque 4). El piso `v_fracaso` es
  útil per se (downside de cualquier pre-revenue).
- **2026-08-27 (cont.⁴) — Juicio CABLEADO a la cartera (sándwich end-to-end) + escalera de add-on identificada
  para triangular.** `construir_cartera` acepta `juicio={ticker:etiqueta}`: capa DESACOPLADA de la banda plena —
  solo VETO/THESIS_BROKEN→0 (saca lo malo) + ADMIT_PROBE→rescata falso-negativo (piso). PRIORITY/PASS no mueven
  el size acá. NUNCA supera el cap de supervivencia. 419 tests. **Hallazgo de diseño (respondiendo el recordatorio
  de triangular):** la BANDA plena (base<techo, juicio mueve en ambas direcciones) está ENTANGLED con la ESCALERA
  DE ADD-ON ("empezás chico y ganás tamaño con evidencia" = add-on) → esa mecánica (qué dispara cada tramo,
  cuánto, re-gate) NO está cerrada en doc 39 → **es la ÚNICA decisión de método abierta que queda, a TRIANGULAR
  en Bloque 4.2.** Todo lo demás pendiente es ejecución (D1 binario, extractores B4). El sándwich (determinismo +
  juicio acotado + governance) está armado end-to-end. `juicio_llm.py`: el
  PM-LLM lee evidencia CRUDA (ciego a nuestro veredicto, anti-anchoring), escribe bull+bear independientes +
  falsador, emite SOLO una etiqueta (validada contra el set; inválida/error→PASS conservador; temp=0). `a_
  intervencion` → el allocator ya construido (`juicio.aplicar_juicio`) la traduce a tamaño DENTRO de la banda.
  El LLM NUNCA emite un número (invariante testeado). Validado en vivo (RBRK/CLS): AMBOS PASS con razonamiento
  SUSTANCIAL — el juicio VIO la calidad de RBRK (recurrente/80%GM/secular) pero NO la promovió a ciegas (pesó
  SBC/canal/sin-FCF) = DISCIPLINADO, consistente con la IA objetiva ("esperar, chica"). Complementariedad linda:
  el determinista EXCLUYE canal del castigo de concentración (correcto, canal≠cliente), y el juicio FLAGGEA la
  dependencia de canal como riesgo cualitativo (también correcto). El sándwich funciona. Si el juicio agrega
  valor lo mide el ledger de hit-rate (ya construido). 414 tests. **Bloque 3 core+interfaz COMPLETO** (falta:
  cablearlo al armado de cartera + acumular hit-rate con el tiempo). Iteré el
  fact_key (era el ENTAILMENT el que rechazaba "three customers... (32%,17%,14%)" como si fuera top-N). Fix:
  pregunta + entailment aceptan listas de %s INDIVIDUALES (extraé el mayor) y excluyen canal + agregado-puro.
  Resultado: **CLS→0.34** (cliente único real → g_D 16% → OPTION_PRICED, conservador ✓), **RBRK→null** (canal
  excluido → g_D 40% sin castigo ✓), MP→0.40. Los 2 lados del hallazgo, corregidos con dato. **PERO el ranking
  sigue CLS≥RBRK** (CLS rentable-hoy=MADURO/libro-duro; RBRK no-rentable=ESCALANDO/carril). El residuo "RBRK es
  mejor NEGOCIO pese a no rentable" es IRREDUCIBLEMENTE JUICIO (calidad de revenue: recurrente/diversificado/
  secular) → es exactamente lo que el Bloque 3 (canal de juicio) mete dentro de guardrails. NO es bug ni
  miscalibración: es la mitad del sándwich que falta. 409 tests. Refiné
  `customer_concentration_pct` a CLIENTE FINAL único (excluye canal/distribución + top-N agregado; entailment).
  Re-extraído: RBRK→null (canal excluido, ya NO castigado — fix del hallazgo ✓), MP→0.40 (cliente único, castigo ✓).
  PERO trade-off honesto: CLS/AAOI→null (concentración real que el filing da en TABLA "Customer 32%,17%,14%" y el
  extractor no aisló el 32% individual) → perdieron señal. Cambié falsos-positivos (RBRK) por falsos-negativos
  (CLS). El concepto es correcto; **necesita mejor RECALL** para sacar el cliente-único de una tabla (retrieval-
  quality, no método). Net: el fix de RBRK (que mueve el ranking a lo correcto) es real; la conservadurización de
  CLS espera mejor extracción. 409 tests. → #22 sigue abierto (recall del cliente-único-en-tabla). Extraje
  `customer_concentration_pct` en 13 nombres (~$0.03). El castigo dispara, PERO medir reveló que el número NO está
  normalizado: conflaciona *un solo cliente* (MP 40%, TENB 30%), *top-10 agregado* (CLS 83%, AAOI 99%) y *partners
  de CANAL/distribución* (RBRK 58% = 2 revendedores, NO clientes finales). Es el "la definición flota entre emisores"
  que las 2 IAs advirtieron. Consecuencia: **el castigo OVER-penaliza a RBRK** (concentración de canal ≠ de cliente;
  RBRK vende a miles de clientes = diversificado como dijo la IA objetiva). CLAVE: **normalizar la concentración
  (extraer el ÚNICO cliente final más grande, distinguir canal) moverá a RBRK a mejor ranking = hacia la vista
  correcta RBRK>CLS.** → Bloque 4 (calidad de extracción): fact_key `concentracion` debe medir SINGLE-largest-end-
  customer, separado de top-N y de canal. El castigo mecánico está bien; el dato necesita refinamiento. 409 tests.
- **2026-08-26 (cont.) — FIX del hallazgo: castigo de CONCENTRACIÓN en g_D.** Directo de la validación: `crecimiento_
  _demostrado` ahora descuenta g_D ×0.70 si la concentración top-cliente > 30% (crecimiento concentrado = frágil,
  no durable; politica v2.0). Wireado a `hoja` (lee `customer_concentration_pct` del fact store). Validado en vivo:
  CLS concentración 83% (top-10, citado DIRECT) → g_D 23%→16% → estado STRETCH→**OPTION_PRICED** = hacia donde los
  2 chequeos externos lo tenían. **El sistema ahora coincide con el juicio disciplinado que la IA objetiva hizo a
  mano.** 409 tests. Nota: el mecanismo estaba listo pero data-gated (concentración no extraída) → confirma el punto
  del Bloque 4 (la dimensión cualitativa necesita extracción). Ciclicidad (más difícil, necesita señal de sector)
  queda diferida. Falta aún: ranking relativo RBRK>CLS (necesita juicio de calidad, Bloque 3/4).
- **2026-08-26 (cont.) — DOBLE VALIDACIÓN corrida (CLS+RBRK) → hallazgo mayor + honesto.** Chequeo A (IA aplica
  NUESTRO método): ruteo 100% fiel (externo computó Δ8Q=1.98=nuestro 1.97); valuación diverge 1 banda (nuestro
  solver más conservador que cálculo a mano — no bug, calibración). Chequeo B (IA objetiva CIEGA): **NO le ganamos
  claramente.** (1) Invertimos el RANKING: objetiva rankea RBRK>CLS (mejor calidad de revenue: recurrente/80%GM/
  diversificado/secular); nuestro sistema CLS>RBRK porque premia owner-FCF+ de HOY → prefiere el EMS cíclico-
  concentrado-rentable sobre el SaaS calidad-superior-no-rentable. (2) La objetiva cazó CONCENTRACIÓN (63% en 3
  clientes CLS), CICLICIDAD (g_D 23% de CLS = pico capex AI, no durable — lo acreditamos plano), CAP-TABLE (RBRK
  diluye vs CLS recompra) — las 3 cosas que doc 39 dijo que los fundamentals NO ven. **Empatamos en DISCIPLINA**
  (ambas caras → posición chica; no sobre-dimensionamos). **Conclusión: NO refuta el proyecto, lo VALIDA** — el
  analista nos ganó EXACTAMENTE en lo que Bloque 3 (juicio) + Bloque 4 (extractores calidad/concentración/contraparte)
  cubren y aún no construimos. Acciones: (a) valuación CLS demasiado indulgente (castigo ciclicidad/concentración
  en g_D); (b) prioridad Bloque 4 + Bloque 3. Instrumental: docs 43/44 + ops/dump_datos + ficha_profunda. 407 tests. `ops/ficha_profunda`
  actualizada al vocabulario nuevo (ruteo → reverse-DCF/burden → pilares SCORING → decisión UNDERWRITTEN/PROBE/
  WATCH/REJECT). Validada en 3 nombres: CLS→UNDERWRITTEN/STRETCH, RBRK→PROBE (good-loser, grower caro), LEU→
  UNDERWRITTEN/STRETCH (backlog). Doc 43 = protocolo para el "chequeo fuerte" del operador (prompt neutral CIEGO
  al método + rúbrica de comparación). **FINO cazado:** LEU rutea a BURDEN pero sale UNDERWRITTEN — el estado
  ruteo BURDEN hoy NO excluye, solo manda al path burden (que la valúa por su backlog contratado→STRETCH). Outcome
  correcto (LEU es Tracción con RPO), label engañoso; reconciliar "BURDEN=excluido" (doc 42) vs "BURDEN=path
  burden decide". Anotado, no bloquea.
- **2026-08-26 (cont.) — BACKTEST rebalanceado (ruteo-aware) → HALLAZGO CENTRAL que valida el rebalanceo.**
  Upgradé `backtest_valuacion` a ruteo-aware (serie con operating_income as-of → opex → `rutear` + `estado_por_
  ruteo` point-in-time). Corrida as_of 2022-06 fwd 3a: separación +1.10 (baseline directo era +6.64). PERO el
  resultado está DOMINADO por 2 ganadores de shock EXÓGENO — VRT +1434% (boom AI capex) y LEU +640% (revival
  nuclear) — que NO estaban en sus fundamentals de 2022 (VRT point-in-time era hardware en apuros → BURDEN
  honesto). **LECCIÓN (valida doc 39):** en esta clase de activo el 10x viene de cambios de RÉGIMEN que los
  fundamentals no ven → un frame de valuación puramente fundamental NO separa bien; se necesita RECALL + JUICIO
  + opcionalidad/probe (exactamente el rebalanceo). El backtest no falló — reveló empíricamente por qué el
  determinismo total se peleaba con la tesis. Honesto: n=10 dominado por outliers, nada concluyente; ruteo
  point-in-time correcto (sin look-ahead); conclusiones reales necesitan bulk XBRL (P1). 407 tests. `ruteo.rutear` (4 estados por derivada
  Δ8Q(GP)/Δ8Q(OpEx)) enchufado a `hoja`; `valuacion_reverse.estado_por_ruteo` reemplaza el switch crudo
  owner-FCF>0. ESCALANDO usa m0 ACTUAL (negativo, no se borra) + `cap_estado=OPTION_PRICED` (doc 42 §3: sin
  apalancamiento demostrado autoriza probe NO core — el hallazgo: el solver con m0<0 daba tv_share>1 y T* chico
  = hype, capado). Validado en vivo: **RBRK→ESCALANDO** (ya NO cae a burden; valuación NON_UNDERWRITABLE→carril/
  probe, correcto para grower caro no-rentable), CLS→MADURO→STRETCH, S/VRNS/LEU/MP→BURDEN. 407 tests. ⚠️ CAVEAT
  honesto: casi todo sale NON_UNDERWRITABLE/BURDEN salvo CLS → dispara el chequeo de distribución (doc 36 §7):
  ¿caros de verdad o umbrales duros? Lo adjudica el BACKTEST, no argumento. FALTA: valuación §3 fina de ESCALANDO
  (locus∩hull + superficie τ) · D1 skeleton binario · re-correr backtest con el frame rebalanceado.
- **2026-08-25 — Bloque 2 triangulación preparada (doc 41) + Bloque 3 CORE determinista.** Bloque 2 (gramática
  binaria pre-revenue + "good loser" SBC-heavy) → doc 41 listo para circular (decisión de método, se triangula
  antes de codear). **Bloque 3 (canal de juicio) CORE HECHO:** `juicio.py` — el determinismo produce banda+techo
  (NO cartera obligatoria); el PM-LLM emitirá SOLO etiquetas (ADMIT_PROBE/PASS/PRIORITY_H·M·L/HOLD/THESIS_BROKEN/
  VETO); `asignar_size` (allocator determinista) las traduce a tamaño DENTRO de [piso,techo], NUNCA supera el
  techo (cap de supervivencia); `aplicar_juicio` respeta el PRESUPUESTO de promociones (N/ciclo, vetos ilimitados,
  promoción sin falsador escrito → no se ejecuta). Entrega también **1.4 (la banda)**. `ledger_juicio.py` — hit-rate
  del juicio vs baseline; si sobre ≥8 resueltas no le gana, el presupuesto se achica solo (empíricamente responsable,
  no amordazado). Política v2.0. 400 tests. FALTA de B3: el memo estructurado (bull+bear independientes) + la
  llamada LLM real (interfaz, último) + cablear la banda al cartera_celdas. Abierto (doc 39 §2.7): piso vs sin-mínimo
  → default sin-piso + ledger vigilando.
- **2026-08-24 — REBALANCEO Bloque 0 completo + Bloque 1.1 (gates→scoring).** Tras triangular el PARADIGMA
  (docs 38/39, determinismo↔juicio) y armar el plan (doc 40): **Bloque 0 (medición) CERRADO** — ledger de
  rechazos (`registro_decisiones.py`, sembrado t0) + backtest point-in-time de valuación (`backtest_valuacion.py`
  + `edgar.serie_crecimiento(as_of=)`, sin look-ahead; 1ª corrida: separación +6.64 pero NO concluyente, muestra
  chica + outliers + hipótesis "deep-value disfrazado"; es el BASELINE pre-rebalanceo). **Bloque 1.1 HECHO:**
  gates conjuntivos → **scoring no-compensatorio**: la ÚNICA exclusión dura es el **veto de supervivencia**
  (`Pilar.es_veto_supervivencia`, seteado por ejecución en restatement/integridad); un CRÍTICO de "no funciona"
  (unit economics) pisa el score a C pero NO excluye (candidato PROBE); **UNKNOWN ≠ FAIL**. `Evaluacion.elegible`
  = sobrevivió (no tier∈AB). Wireado a `candidato_desde`. Validado en vivo: NABL vetado (supervivencia, correcto),
  12/13 elegibles (antes el pre-revenue se excluía por construcción). **Bloque 1.2/1.3 HECHO:** el reverse-DCF
  growth-aware (T*/g_D/superficie de margen) ENCHUFADO al flujo vivo — antes estaba en un módulo standalone y
  `candidato_desde` usaba el binario g=0. Ahora `hoja` computa `estado_reverse` (comercial, owner-FCF+, con
  `r_mkt` de doc 37 = lente de LECTURA, SEPARADA del hurdle) → `candidato_desde` lo usa como estado de valuación.
  Ruteo owner-FCF+ → comercial (reverse-DCF); owner-FCF≤0 → path burden/pre-revenue. Política v1.9. Validado en
  vivo: CLS g_D=23% → **STRETCH** (antes binario/2%; el g=0 arreglado en vivo), TENB 9%/KLIC 0% → NON_UNDERWRITABLE
  (caros vs su crecimiento, read legítimo), S/RBRK (SBC alto → owner-FCF<0) → path pre-revenue. 385 tests.
  ⚠️ OBSERVACIÓN p/ Bloque 2: los growers SBC-heavy (S, RBRK) rutean a pre-revenue por owner-FCF<0 — el "good
  loser" de doc 39 §4.3 (pérdida contable ≠ destrucción económica). **Bloque 1.5 HECHO:** `estado_decision` →
  4 estados de doc 39 §2.7 (UNDERWRITTEN/PROBE/WATCH/REJECT), mapean 1:1 al eje EVIDENCIA; es el vocabulario que
  consume el canal de juicio (Bloque 3). **1.6 YA SATISFECHO:** el path vivo de cartera usa `rankear_por_celda`
  (celdas arquetipo×tier) + cuotas = construcción por DIVERSIDAD (doc 34 §3bis); el orden total lexicográfico
  dañino que critica doc 39 es legacy, NO está en el path vivo → no se reescribe. **1.4 (sizing→banda) DIFERIDO a
  Bloque 3:** una banda sin el canal de juicio que se mueva dentro no tiene consumidor (evita estructura muerta).
  387 tests. **Bloque 1 CERRADO** (1.1✅ 1.2✅ 1.3✅ 1.5✅ 1.6✅ · 1.4→B3). Diferido: sector→modelo (hoy "default")
  · ruteo durable 3FY (doc 37 §7) · el "good loser" SBC-heavy → Bloque 2 (segunda gramática, TRIANGULAR).
- **2026-08-18 (cutover, paso 4) — Rúbrica del carril (#11) COMPLETA end-to-end.** La superficie nueva ya tiene
  sus DOS libros construidos. Carril: 7 fact_keys `opcion_*` (`FACT_KEYS_CARRIL`, lista SEPARADA para no inflar la
  cobertura del duro) con entailment adversarial (TAM/deck/ceiling no cuentan) → `analisis.extraer_carril` (guard
  propio, resolver_8k) → `carril.construir_hechos_carril` (snapshot→HechosCarril) → gate §2 → **rúbrica §3**
  (`politica.grado_opcionalidad`, pesos versionados) → sizing §4/§5. Política v1.7, 353 tests, wireado a cutover_diff.
  **Validado end-to-end (MP/UEC):** extracción corre, gate evalúa, ambos RECHAZADOS (`evidencia_externa=False` —
  su premium es demanda-commodity especulativa, sin hito fechado/funded/material en el filing; defendible). Carril
  admite 0/8 hoy, pero por razón MEDIDA. **FALTA (refinamiento, no infra):** (a) medir recall de los 7 fact_keys nuevos
  (gold set — ¿MP False es genuino o miss? la opcionalidad suele vivir en 8-K/PR); (b) triangular pesos §3
  (`PESO_RUBRICA_OPCION` uncalibrado); (c) extraer carril-facts a los 8 (solo MP/UEC hechos). #13.
- **2026-08-18 (cutover, paso 3) — Extracción del libro vivo (#9) + foto EVIDENCIA-COMPLETA + validación del edge.**
  Extraídos NABL/KLIC/ALGM (abstención 31%→0%). Reclasificación limpia del libro vivo (12): **4 libro duro** (CLS 8%,
  KLIC 8% —antes abstenido, ahora COVERED—, LEU 4%, AAOI 2%) · **8 → carril** (…+ALGM) · **1 descarte: NABL** · 0
  investigación. **HALLAZGO MAYOR (validación del edge):** NABL era la posición #1 del libro merito (16.5%) y tiene
  **material weakness en controles internos DECLARADA** (cita DIRECT del 10-Q: "disclosure controls… not effective…
  material weakness") → el nuevo la veta (Pilar 3 Ejecución CRÍTICO), el merito NO la cazó. **Los 8 ruteos a carril
  verificados correctos por diseño** (falsador "el precio ya paga el bull operable" sobre XBRL, no artefacto de poca
  data). O sea: el gate de valuación + el de integridad están BIEN calibrados. Bug colateral: logger de costo pierde
  escrituras en extracción batch (#12). Bloqueos del switch restantes: construir la rúbrica del carril (#11 cont).
- **2026-08-18 (cutover, paso 2) — Carril especulativo `backend/nucleo/carril.py` (núcleo determinista).** Resuelve
  la duda del operador "¿las pura-opción no tienen sizing?": SÍ lo tienen, en el CARRIL, no en el libro duro (el `0`
  del duro = "no acá", no "en ningún lado"). Construido fiel a doc 29: **gate §2** (`gate_carril`, 5 obligatorias,
  None→no pasa conservador) + **sizing §4** (cap 8%/pos, máx 2 plazas, máx 1/catalizador) + **budget §5** (piso 10%→
  techo 25%). Política v1.6. Enchufado a `cutover_diff` (7 candidatos → 0 admitidos HOY: el gate §2 necesita hechos
  FECHADOS —evidencia externa/hito/materialidad/falsabilidad— que no se extraen aún; honesto, doc 29 §9 shadow).
  **FALTA (#11 cont.):** extracción de los hechos del gate §2 + la **rúbrica §3** (PM-LLM, orden ordinal citado) —
  hoy `orden_placeholder=True`. Decisión relacionada: **opción-gratis sobre libro duro** (doc 14 §E1-bis) usa la MISMA
  rúbrica como desempate. 350 tests.
- **2026-08-18 (cutover, paso 1) — Harness de IMPACTO `ops/cutover_diff.py` + hallazgo decisivo (RE-RUTEO, no liquidación).**
  Corre la superficie nueva (celdas+sizing 2-ejes) vs el libro paper VIVO (merito) y diffea por DESTINO. **Hallazgo
  clave:** la nueva **NO liquida a cash — RE-RUTEA**. De 12 posiciones vivas → **3 libro duro** (CLS 8% COVERED, LEU
  4% STRETCH, AAOI 2% nuevo) · **7 → carril especulativo** (TENB/VCYT/TER/VRNS/UEC/RBRK/MP — TODAS elegibles/3-pilares
  OK, pero el precio ya paga el bull operable ⇒ su upside es OPCIONALIDAD, doc 29) · **3 → investigación** (NABL/KLIC/
  ALGM, cobertura 0-7%, gap de extracción, NO venta) · 0 descarte. Los 7 rechazos son **correctos por diseño** (el
  merito no distinguía asimetría-sobre-evidencia de precio-que-descuenta-crecimiento; el nuevo sí y rutea). **El gap
  real que destapó:** el **carril especulativo está referenciado en todo el código pero NO construido** (falta rúbrica
  §3 + sizing §4/§5). **Bloqueos del switch:** (1) extraer investigación (#9), (2) **construir el carril** (#11 nuevo),
  (3) revisar los del duro + los 7 ruteos (#10). NO se toca el paper. `clasificacion_2ejes` ahora distingue
  HARD_EVIDENCE/CARRIL/INVESTIGACION/DESCARTE. 338 tests + harness.
- **2026-08-18 (cont.) — Pendientes cerrados: E1 (#6) + Pilar 3 management (#5, mitad sourceable).** ✅ **E1:**
  `analisis.extraer_e1` (guard propio) cableado a `ops/extraer_demanda` → persiste `backlog_no_cancelable`;
  validado S/VRNS→firm_po 0.85, resto conservador. ✅ **Pilar 3:** `edgar.get_insider_activity` parsea Form 4 XML
  real (P/S, cache 24h, `net_usd`) + `sbc_pct_revenue` de XBRL con scoring; wireado a `ranking.evaluar_ticker`.
  Validado: CLS −$234M/SBC 1%, S −$22M/SBC 29%. Guidance-vs-actuals sigue Fase 2 (FMP). 337 tests.
- **2026-08-18 — SIZING triangulado (IA1+IA2 → doc 34 §3ter) + paso 1 hecho.** 2 ejes ORTOGONALES:
  EVIDENCIA→libro (inmutable) · VALUACIÓN→tamaño (variable). `size=min(caps independientes)` no-compensatorio +
  retícula discreta + reason codes; `cap_valuación` = 4 estados (COVERED/STRETCH/OPTION_PRICED/NON_UNDERWRITABLE)
  por cobertura de GP_req. Núcleo dimensiona, PM solo reduce/excluye. **Paso 1 HECHO:** burden con **ρ real**
  (`gap_financiamiento` + `burden_con_rho` en pre_revenue): G=burn×max(0,t−runway), burden×(mcap+G)/mcap —
  un-difiere el ρ de doc 31 §5 (subestimaba a los quemadores). **Paso 2 HECHO:** 4 estados de valuación
  (`CAP_VALUACION` en politica v1.5 + `estado_valuacion_por_burden` + fold al `min()` de caps con **reason code**
  `cap_reason`; retícula discreta COVERED 100%/STRETCH 4%/OPTION_PRICED 2%/NON_UNDERWRITABLE 0%; `MIN_VIABLE` 1.5%
  reemplaza el piso 5% del merito). Shadow real: CLS→COVERED 8% (tier) · LEU→STRETCH 4% (val) · AAOI→OPTION_PRICED
  2% (val) — mismo libro, tamaño por valuación. **Paso 3 HECHO:** `clasificacion_2ejes` (eje EVIDENCIA→libro:
  HARD_EVIDENCE/INVESTIGACION/CARRIL · eje VALUACIÓN→tamaño), RKLB=HARD_EVIDENCE/OPTION_PRICED. 329 tests. El
  NÚCLEO del sizing (3 pasos) CERRADO. FALTA del sizing: solo PM reduce/excluye (parte del cutover, no de este bloque).
  **Roadmap a "superficie nueva operando el paper": ~3-4 sesiones**
  (sizing + gaps cutover + replay/tablero/switch + E1). Edge real = forward paper sellado, meses.
- **2026-08-14 (cont.) — VALIDACIÓN del análisis sobre empresas reales + `ops/ficha_profunda.py`.** Herramienta
  que corre el proceso COMPLETO legible (Filtro 0 → evidencia citada → 3 pilares → valuación → decisión). Probada
  en LEU/RKLB/S/TER/OKTA: análisis defendible y SOBRIO (RKLB, la favorita del mercado, entra pero con burden 53×GP
  encima; el sistema no compra hype). **Cazó un bug real:** el gate de valuación ruteaba por `route` e ignoraba el
  falsador en CASH_POSITIVE (S entraba al libro duro pese a "ya priceado"). Fix: **rutear por si el falsador PUDO
  evaluar** (evaluable→manda cualquier route; no_evaluable→anchor). S ahora sale correctamente. 317 tests.
  Validación externa: prompt disciplinado en scratch; pasada interna (subagentes disciplinado+naive) para contrastar.
- **2026-08-14 (cont.) — Triangulación del cutover CERRADA + refactor casi completo en shadow.** IA1+IA2
  convergieron (doc 34 §3bis): tier de demanda 100% determinista + ABSTENCIÓN (PM solo inputs, override nunca
  promueve); ranking por CELDAS (arquetipo×tier) con llave económica LOCAL (asimetría FCFE / burden-tupla
  pre-revenue), sin orden económico cross-arquetipo; "no aplica" nunca coaccionado a valor (asimetría N/A,
  UNKNOWN abstención). **Aterrizado en shadow:** fixes (asimetría N/A, UNKNOWN no-veto) + `ranking_lexicografico`
  por celda + `cartera_celdas.construir_cartera` (cuotas ex-ante, caps-no-cuotas, `CUOTA_ARQUETIPO` v1.3).
  **CADENA COMPLETA end-to-end en shadow** (evaluar→hoja→candidato→rankear_por_celda→construir_cartera): 3
  elegibles→24% invertido/76% cash. 313 tests, paper intacto. Falta para cutover: abstención+umbral · sector caps ·
  burden-tupla completa · I2/carril (evidence-blocked) · replay+tablero. Canónico: doc 34.
- **2026-08-14 (cont.) — Refactor a la superficie única: pasos 4-5 (shadow). 5 de 6 pasos.** Paso 4: tier→cap
  8/5/2.5% (`politica.CAP_TIER_CAPITAL`, v1.2) en el `min()` de caps del `CandidatoLex`. Paso 5: **`FichaPM` sin
  merito cardinal** → tier+rank+cap (doc 33), `ficha_desde_candidato` compone desde el candidato. **Cadena completa
  en shadow:** evaluar→hoja→candidato→rankear→ficha→PM. 303 tests, paper intacto. Falta paso 6 (I2/carril/limpieza)
  + **cutover** (con el chequeo A1 + orden económico within-archetype). Ver doc 34 §4 + doc 14 §G8.
- **2026-08-13/14 — Coherencia del método + spec target + refactor arrancado.** Pre-pass de coherencia (3
  subagentes) reveló que las "contradicciones" son mayormente LAG DE IMPLEMENTACIÓN (3 superficies de evaluación
  medio-migradas), no incoherencia del método → se SALTEÓ la triangulación externa amplia (re-confirmaría doc 33).
  Escrito **`34_flujo_evaluacion_target.md`** (la superficie única: 3 pilares + valuación=gate + lexicográfico +
  tier→cap + FichaPM→PM; secuencia de refactor en 6 pasos). **Refactor paso 1 HECHO:** `evaluacion` a 3 pilares
  (valuación fuera del pilar → gate), 280 tests verdes. A1 (demanda determinista vs orientativo) recomendado
  (orientativo+cita, norte determinista). Detalle: doc 14 §G6 + doc 34.
- **2026-08-13 (cont.) — E1 (tipo de contrato del RPO) parcial + I3 descartado + limpieza de docs.**
  · **I3 DESCARTADO:** al aterrizarlo se vio que "dilución en el bridge" (doc 28 §2) **choca con doc 33 §4**
    (dilución = eje separado, ya en `dilucion.py`) → no se construye (doble-conteo). Registrado doc 14 §E3-bis.
  · **E1 parcial (apaga el `evidencia_insuficiente` honestamente):** fact_key citado `backlog_no_cancelable`
    + `compilador.tipo_contrato_rpo` (firme→firm_po 0.85 / cancelable→0.60 / sin extraer→asumido) + wireo en
    `hoja._bull_contratado`. Extracción probada: OKTA/S/VRNS non-cancelable→firm, TENB/BWXT sin describir→conservador.
    280 tests. Falta el pipeline ops que persista el hecho al fact store (doc 14 §E1).
  · **Limpieza documental:** `00_MAPA_DOCUMENTOS.md` (índice único) + 13 docs viejos archivados en `init_docs/archivo/`
    con banners; CONTEXT.md apunta al mapa; corregido el "sleeve 2%" (→ carril especulativo doc 29) en código+docs.

- **2026-08-13 (noche) — Bloque VALUACIÓN arrancado: vertical RPO→compiler (pasos 1-2 de 4, HECHOS+TESTS).**
  Diagnóstico grounded: el compiler/falsador/política ya estaban construidos+testeados pero DESENCHUFADOS, y
  **el spread bull/bear estaba INERTE en producción** (`hoja` llama a templates sin `revenue_contratado` → bull=base=bear).
  · **Paso 1 — RPO sourceable (implementabilidad confirmada):** `RevenueRemainingPerformanceObligation` está
    limpio en companyfacts (OKTA/TENB/LEU/BWXT/S coinciden con la prosa). Agregado `edgar._extract_rpo` +
    `FinancialsQuarterly.rpo/rpo_as_of` + `extractor.extraer_deterministas["rpo"]`. Verificado: BWXT $8.4B, LEU $800M.
  · **Paso 2 — compiler rutea por TIPO DE CONTRATO:** `compilar_escenario` vía nueva que usa
    `politica.retencion_contrato` (tabla ya poblada) → término con `haircut_source` + condicional/ceiling→ledger O3.
    **Honestidad del atajo (pedido del operador):** RPO entra con tipo ASUMIDO `cancelable_backlog(asumido)` →
    `es_piso=True` → dispara `evidencia_insuficiente` (>40% del bull sobre piso → no sleeve completo). Cuando se
    extraiga el tipo real (E1), el flag se apaga → el sistema PREMIA extraer. 15 tests (9 compilador + 6 edgar) verdes.
  · **Pasos 3-4 — HECHOS (vertical completa):** `hoja_evidencia._bull_contratado` arma el escenario vía compiler
    (RPO→retención) y alimenta `templates.escenario_operable(revenue_contratado=...)` → **el spread bull/base
    ahora es REAL** (antes inerte). Falsador CAGR cableado en la hoja. Campos nuevos en `HojaEvidencia`:
    revenue_contratado, bull_operable, haircut_source, evidencia_insuficiente, falsador_ya_priceado/veredicto.
    **Verificado end-to-end en nombres reales:** BWXT base $32.5→bull $69.6 (falsador: precio $169 YA paga el bull
    → pura opcionalidad, fuera del libro duro / carril especulativo doc 29 — NO "sleeve 2%", eso se sacó);
    OKTA $34.5→$52.5 (ya priceado); TENB $9.1→$12.9 (ya priceado); LEU owner-FCF<0→piso. Todos con
    `evidencia_insuficiente=True` (tipo asumido → penaliza sleeve). **276 tests verdes, cero regresión.**
  · **Falta solo para el DASHBOARD (diferido a propósito, "primero que esté bien"):** surface los campos nuevos en
    el template `/hoja`. La DATA ya está; `ops/generar_hoja` la regenera. Pendientes de mejora: doc 14 §E.

- **2026-08-12/13 — Bloque 0: harness de medición del retrieval, TRIANGULADO (IA1+IA2, convergieron).**
  Construida y re-diseñada la maquinaria para hacer MEDIBLE el retrieval (antídoto al tuneo a ciegas).
  El diseño v1 (contención binaria) tenía una falla que ambas IAs cazaron: **recall libre se maximiza
  devolviendo TODO el documento** → se rediseñó. Estado cerrado:
  - **`backend/nucleo/gold_retrieval.py`** — `GoldCase` (case_id = ticker:fact_key:**período**;
    location PRIMARY/EXHIBIT/EIGHTK/OTHER_DOC ⊥ answerability STATED_SINGLE/STATED_MULTI/TABLE_ONLY/
    **DERIVABLE**/AMBIGUOUS/**NOT_DISCLOSED**; `evidence` = **OR-de-AND** de spans verbatim; distractors;
    split dev/holdout). Métrica `medir_caso`: **recall a presupuesto** (win_chars) + **region_precision**
    + **causa del miss A/B/C/D** (A=ningún anchor cerca · B=ventana ±w no cubre el span · C=lo tiró el
    cap de max_regs · D=perdido en extracción HTML→texto) + distractor-en-ventana.
  - **Fixture = HTML CRUDO congelado** (`data/gold/corpus/<T>_<acc>.html`); el harness EXTRAE en runtime
    (el extractor también está bajo test → una mejora suya puede arreglar/romper retrieval y se ve).
    Determinista y offline; la red se usa solo al freezar. `analisis.construir_regiones` (nuevo, fuente
    única de la lógica de regiones; `_window` lo usa) expone capadas/sin_cap/pos para diagnosticar C y A.
  - **`ops/gold_freeze.py`** (crudo+sha) · **`ops/medir_retrieval.py`** (reporte con causa + IC95). 
    **`tests/test_gold_retrieval.py` — 15 tests, verde**; `test_demanda_citada` sigue verde (refactor OK).
  - **Vertical slice AAOI (2 casos):** `demanda_realizada` → **MISS_A_NO_ANCHOR** (confirma: `revenue from`
    singular no pega en "revenueS from" — fix = vocabulario, NO cap ni tabla). `customer_concentration_pct`
    → HIT pero **region_precision 0.25** (75% de la ventana es ruido; la métrica vieja lo cantaba como win limpio).
  - **Decisiones tomadas:** set de fact_keys v1 = **HÍBRIDO** (concentración compuesta + demanda_realizada
    [caso AAOI] + no_customer_over_10pct [negativo, mide FP] + respaldo_backlog [diversidad tabular]).
    Held-out por EMISOR. Es un **regression seed** de nombres difíciles (IC95 ancho, no estimador de prod)
    + ~10 random para cazar que un fix rompa los fáciles. Diferido: corpus 200-random para derivar anchors,
    job semanal de drift, inyección de header+período en `_window` (1er fix de 0c, se mide antes/después),
    doble-etiquetado formal, corrida LLM P(correcto|HIT). Prompt de triangulación + respuestas en scratchpad.
  - **Gold set v1 etiquetado (11 casos / 8 nombres, contra filing real congelado):** AAOI·SMR·ASTS·TER·LEU
    (dev) + OKTA·TENB·RKLB (holdout). Cubre las 3 answerabilities: STATED (targets limpios), DERIVABLE
    (LEU: divulga $78.9M/$39.1M pero NO el % → hay que calcular), AMBIGUOUS (TER cualitativo · ASTS MNOs
    genérico) + trampa de período (SMR Fluor 92% es 2025 comparativo + related-party; 2026 ~0) + distractor
    de métrica (RKLB "MDA 11%" = AR, no revenue).
  - **BASELINE (2026-08-13): recall 5/8 = 62% (IC95 ±34pp).** Y **valida el desafío de IA2** ("no es solo
    anchors, n=1"): los 3 misses tienen 2 causas DISTINTAS →
    · **2× MISS_A (vocabulario):** AAOI `revenue from` no pega en "revenueS from"; SMR "% of the Company's
      revenue" evade todos los anchors (ninguno matchea → WIN=0).
    · **1× MISS_C (ranker sin score):** OKTA backlog — el anchor SÍ matchea cerca del RPO pero la región la
      **tiró el cap de max_regs=4**. Arreglo = ranking de regiones, NO vocabulario. (IA2 lo predijo.)
    · **Precisión baja en los HITs** (AAOI/LEU 0.25, TENB 0.50/0.33): 50-75% de la ventana es ruido →
      confirma que la métrica vieja (contención binaria) los cantaba como wins limpios. RKLB precisión 1.0
      PERO con distractor en ventana (la línea AR de MDA) → riesgo de que el LLM cite la métrica equivocada.
    · Los 3 no-evaluables (LEU DERIVABLE, ASTS/TER AMBIGUOUS) quedan FUERA del denominador (bien: no son
      fallas de retrieval, son definición de tarea).
  - **0c FIX 1+2 HECHOS y MEDIDOS (2026-08-13): recall 62% → 75% → 88% (7/8). 272 tests verdes, sin regresión.**
    · **Fix 1 (vocabulario, clase lingüística no issuer-string):** `revenue from`→`revenues? from` (plural,
      caso AAOI/Digicomm); `accounted for [\$\d~]` (monto antes del %, caso SMR/Fluor); `% of <0-3 tokens>
      revenues?` (posesivo "the Company's revenue" + plural). → SMR MISS_A→HIT (prec 1.0); AAOI demanda MISS_A→C.
    · **Fix 2 (ranker de regiones):** `construir_regiones` capa por **densidad de anchors** (top-N), no por
      posición — antes tiraba la región buena solo por venir más tarde en el doc. → OKTA backlog MISS_C→HIT.
      Cambio en el CORE (lo usa el pipeline vivo); mejora producción también. Holdout confirmó generalización.
    · **Residual (1 miss): AAOI demanda MISS_C** — su región es genuinamente poco densa (solo `revenues? from`,
      sin otros anchors convergiendo) → el ranker por densidad no la promueve. Empujar más = riesgo de
      sobreajuste. Candidatos honestos: subir max_regs (trade precisión/budget, medir) · señal específica de
      demanda-realizada · resolución 8-K (`resolver_8k` ya existe). DIFERIDO, decisión abierta.
    · **Precisión de región baja en varios HITs (0.25–0.50):** el fix 3 (header de sección + período + límites
      de párrafo en `_window`) la ataca y ataca el modo de falla de período — NO hecho aún (cambio más invasivo).
    · RKLB HIT con distractor en ventana (AR "MDA 11%") → pendiente corrida LLM P(correcto|HIT).
  - **0c — P(correcto|HIT) MEDIDO (2026-08-13, `ops/medir_extraccion.py`, Haiku ~$0.005 total):**
    corrida del LLM sobre las 7 ventanas HIT. **VALOR correcto = 7/7 = 100%. CERO citas en distractor**
    (RKLB tenía la línea AR "MDA 11%" en la ventana y el LLM igual sacó 0.42, no 0.11). Cita-en-gold 43%
    porque el gold etiqueta UN span y el filing tiene varios pasajes válidos (los "otra" son citas
    correctas a otro pasaje, no errores) — límite del gold, no del sistema.
    → **DECISIÓN basada en evidencia: la extracción NO es el cuello; el modo de falla de período NO se
    materializó.** El fix 3 profundo (extracción estructura-consciente por período) **NO está justificado
    hoy** — casi construimos una solución invasiva para un problema que el dato dice que (en este seed) no
    existe. El retrieval (62→88%) fue el palier correcto y suficiente para este seed. **Medir-antes-de-
    construir evitó sobreingeniería.**
  - **Caveat honesto:** n=7, seed adversarial, IC ancho. El 100% alienta pero no prueba a escala.
  - **0c — GENERALIZACIÓN CONFIRMADA (2026-08-13):** gold ampliado a **24 casos / 18 nombres** (8 difíciles +
    10 random: NABL·S·VRNS·RBRK·MP·VCYT·CLS·UEC·COHR·BWXT, split="random", NO se tunearon anchors con ellos).
    · **Recall 13/15 = 87%** (IC ±17pp) — se mantiene el ~88% de los difíciles → **no hay sobreajuste**.
    · **P(correcto|HIT) = 13/13 = 100%**, **0 citas en distractor** (MP tenía "Customer D 2025" y RKLB "MDA 11%"
      en ventana; el LLM citó igual el pasaje correcto). El modo de falla de período **no se materializa**.
    · El set random cazó 2 cosas reales: (a) brecha de vocabulario (**S**: "accounted for more than X%" +
      denominador **ARR** no cubierto → MISS_A; REGISTRADO, no tuneado); (b) **error de mi label** (MP: el
      fact_key pide agregado top-N, el extractor sumó 87% bien, mi label decía 40% → corregido). El medidor
      caza errores propios.
    · **CONCLUSIÓN con evidencia (no fe): el motor de evidencia — retrieval + extracción — es SÓLIDO en este
      seed.** El fix 3 profundo (extracción estructura-consciente) queda DIFERIDO justificado por dato.
  - **PRÓXIMO BLOQUE (grande): compiler de valuación / haircuts** — el core construido-pero-vacío del método
    (doc 33 §Diferido; docs 27/28). Haircuts + templates revenue→precio = juicio de modelo → TRIANGULAR.
    Diferidos menores: brecha explícito-negativo/ARR en anchors (medir en dev), residual AAOI demanda,
    gold con múltiples spans válidos por hecho, ~10 random como regresión permanente en CI.

- **2026-08-12 — Pilar de demanda: el auto-tier fino topó su límite (calidad del motor de evidencia).**
  Tras varias iteraciones + triangulación (4 IAs) + verificación en todo el universo, la conclusión honesta:
  el auto-tier VALIDATED/COMMITTED/REALIZED es FRÁGIL para este universo (cliente nombrado vs categoría,
  related-party en texto no en XBRL, comparativos viejos). Cada gate arreglaba un caso y rompía otro.
  **Lo que quedó (decisión del operador: "simple + honesto"):**
  - ✅ **`temperature=0`** en el extractor (`extractor_citado.py`) — el WIN firme: mata la inestabilidad
    (AAOI ya no flapea). Reveló que la cobertura "27" previa estaba INFLADA por ruido de temp=0.3.
  - ✅ Tier **ORIENTATIVO** (no auto-veto): se muestra tier + CITA cruda + flags; el **PM/humano juzga**
    los bordes (SMR-comparativo-viejo, AAOI-cita-mala, related-party). Se revirtió el endurecimiento de
    preguntas y el hecho binario que sobre-disparaba.
  - ✅ `edgar.get_related_party_pct` (rp% determinista de XBRL) como **FLAG** informativo, no veto.
  - **REQUISITO PM (pedido del operador):** cuando se cablee el PM-LLM, recibe **tier + cita + flags**
    (no la etiqueta pelada) para juzgar los bordes igual que el humano en el hover. Principio "la evidencia
    viaja con la señal" (doc 33 §5).
  - **Límite real identificado:** la cobertura/precisión del tier la limita el **retrieval/cita del motor de
    evidencia** (ej. AAOI: se citó la línea del warrant, no la de Digicomm 42.8%). Mejorarlo = trabajo del
    motor de evidencia (bloque propio), NO más gates. **Diferido:** G3 (vigencia, arregla SMR), calidad de
    retrieval (AAOI). 257 tests.


- **2026-08-11 — Pilar de demanda por GATES (triangulado 4 IAs: 2 Claude + IA1 + IA2, convergieron).**
  Reencuadre: el tier no es "hay cliente nombrado → tier", es "etapa de comercialización CALIFICADA para
  la tesis"; la evidencia inelegible se EXCLUYE (no se degrada) y se recalcula. Implementado (MVP): G1
  contraparte-específica (endurecí entailment de `cliente_nombrado`/`demanda_realizada` → rechaza "MNOs"/
  "significant customers") + G2 parte-relacionada (fact nuevo `demanda_es_parte_relacionada` → excluye la
  evidencia relacionada) en `ranking._demanda_de_snapshot`, con nota visible del por qué en la hoja.
  **Verificado en 6 nombres reales:** SMR REALIZED→0 (Fluor=matriz), ASTS REALIZED→0, TER→0 (genérico
  falla G1), BWXT/AAOI/LEU preservados. 257 tests. G3 (staleness) y G4 (thesis-scope core/no-core) +
  two-output model + firm_commitment-separado + denominador-segmento de BWXT = diferidos (doc 33 §5).
  Re-extracción completa de los 37 en curso (fondo) para que el dashboard refleje el gate.


- **2026-08-10** — creación del doc. Estado grounded con 3 lecturas cruzadas (arquitectura / build / motor de evidencia).
  Paquete Fase-1-hardening + eje dilución §5 cerrado (doc 14 §D).
- **2026-08-10 (tarde)** — **Método de análisis fijado y confirmado** → doc canónico [33](33_metodo_analisis.md)
  (no re-abrir). Roadmap de implementación del método (para completar la hoja advisory fiel al método):
  - **#1 Demand tier citado — HECHO** (end-to-end): `analisis.extraer_demanda` (cache-guard + tx corta),
    tablas `nx_*` creadas, columna display-only en la hoja + template `/hoja` (tier + quote en hover).
    Verificado: OKTA=comprometida (RPO no cancelable), TENB=realizada, AAOI/RKLB=validada. Backfill de los
    37 corriendo en fondo (`ops/extraer_demanda.py`). Fix colateral: retrieval 90→400d (RKLB). Refinamiento
    pendiente: calidad de quotes (a veces ruido de tags XBRL).
  - **#2 Unificar clasificador de arquetipo** (dos divergentes → uno) — en curso.
  - **#3 Endurecer datos — 1ª tajada HECHA** (staleness de shares por ANTIGÜEDAD): `_extract_shares`
    devuelve `(valor, fecha)`, `FinancialsQuarterly.shares_as_of`, flag `flags_plausibilidad` severidad
    MEDIA si el dato de shares es >200d más viejo que el último Q (caza LEU 2022 SIN confundir con dilución
    — mide fecha, no cantidad). Validado en 10 nombres reales: 0 falsos positivos. **Aprendizaje:** el
    intento previo (banda mcap_feed vs precio×shares_XBRL) fue FALSO POSITIVO (revertido) — confundía
    dilución/stale/feed-vs-xbrl. Proceso nuevo: **scopear ANTES de construir.** Pendiente del doc 30:
    reconciliación de deuda/caja + tiers de confianza por dato + security master (más grande).
  - **#2 Unificar arquetipo** — resultó entangled con extracción citada (ASC 606 elegible + concentración
    + binary) → diferido hasta que la capa citada sea más rica (no era el "cleanup" que parecía).
  - **Robustez extracción — HECHO:** retry self-healing en `ops/extraer_demanda.py` (3 intentos + backoff)
    ante transitorios (lock de DB por scheduler, JSON intermitente del LLM). **37/37 tickers extraídos.**
  - **Verificación de calidad de datos (2026-08-11):** chequeadas las citas reales. Extracción FIEL (quotes
    verbatim verificadas). Triage de "s/d": mayoría legítimos (SaaS de mercado amplio / pre-revenue sin
    cliente nombrado); COHR/TER verificados = **NO eran misses** (COHR sin cliente nombrado en el 10-Q; TER
    concentración genérica sin nombrar → vara estricta correcta). **Único caveat real: SMR/ASTS tier
    sobreestimado** (Fluor=matriz parte-relacionada; ASTS=venta equipos no-core) → hecho de parte-relacionada
    PENDIENTE (scopeado, medio). Principio registrado en doc 33 (evidencia viaja con la señal + derivación
    correcta de entrada). Artifact visual publicado.
  - **#4+ diferido por diseño:** scenario compiler con haircuts · funded critical path / q×u×P físico.
