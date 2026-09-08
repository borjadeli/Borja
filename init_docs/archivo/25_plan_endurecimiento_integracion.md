# 25 — Plan de endurecimiento e integración (consolida las 2 revisiones del conjunto)

> ⚠️ **PARCIALMENTE VIGENTE — ver `00_MAPA_DOCUMENTOS.md`.** Su parte de honestidad (reason codes /
> CONTESTED / frescura) vive en doc 32 §5 Bloque 3. **Su replay/canary/cutover (Fases D/E) doc 32 lo
> declara SOBREINGENIERÍA para un sistema advisory** → NO se construye. Tablas (evidence_cap, harness) → doc 14.

> Dos revisiones independientes del sistema ensamblado (doc 24) **convergieron**: el motor ya
> mata la alucinación; el riesgo que queda es **consistencia temporal, semántica y
> transaccional** — puede tomar una decisión determinista sobre un **estado incorrecto**. Este
> doc consolida los hallazgos y los ordena en un plan **faseado con gating**. Nada toca el
> paper vivo hasta cerrar la Fase A + el sellado.

## 0. Corrección conceptual (IA 2): maturity ≠ materiality ≠ continuity ≠ existence
`VALIDATED/COMMITTED/REALIZED` es **madurez** (fuerza de realización), NO magnitud. Se separan
cuatro dimensiones ortogonales de la demanda:
- **`demand_exists`** — tri-state (¿hay una relación/contrato con contraparte nombrada?).
- **`demand_continuity`** — tri-state cuando la tesis lo requiere (CONTINUING/NOT_CONTINUING/UNKNOWN).
  Un pedido único puede ser COMMITTED sin continuidad; un programa chico repetido, REALIZED y continuo.
- **`evidence_maturity_tier`** — ordinal (VALIDATED < COMMITTED < REALIZED).
- **`materiality`** — determinista cuando hay número (contract value / LTM revenue, backlog
  atribuible / backlog, capacidad comprometida / disponible…); **UNKNOWN → ceiling conservador,
  nunca estimación inventada.**
Esto reemplaza el "tier de magnitud" de doc 22 §8bis.

## 1. Composición del gate (dos capas + demanda desglosada)
**Capa 1 — estructura binaria (tri-state).** Un ítem es binario **solo si un FALSE es dispositivo
sin importar la magnitud** (going concern, cliff de financiación antes del hito, control accionario
que anula la tesis, U1 triggers, posición en el cuello). Composición:
`any FALSE → NO_PASA` · `any UNKNOWN → NO_EVALUABLE` · `else → PASA_ESTRUCTURAL`.
**Capa 2 — demanda** (existence ∧ continuity-si-aplica ∧ `maturity_tier ≥ tier_min[arquetipo]`).
`tier_min` **por arquetipo** (pre-revenue admite VALIDATED; Growth/Madura no sostienen demanda
presente solo con VALIDATED). **NO_EVALUABLE dominante** (un binario UNKNOWN manda a cuarentena
aunque el tier sea REALIZED). **Regla:** una proposición económica tiene **un solo dueño** — si
G2/T1/P1 eran proxies de demanda, se **reemplazan** por el tier; si miden continuidad/organicidad,
se conserva **UN** ítem, no tres. No es "checklist viejo completo + tier superpuesto".

## 2. tier → caps: `min`, no multiplicador
`final_cap = min( cap_arquetipo × fragility , evidence_cap[arquetipo][tier][materiality] )`.
El `min` preserva **cuál restricción ata** (accionable). **Tres condiciones anti-doble-penalización:**
1. El tier **no entra también en fragility** (fragility = balance/financiación/dependencia/dilución/
   downside operacional; NO evidencia-discrecional/madurez/calidad-de-demanda).
2. El tier **no entra en mérito** (mérito = preferencia relativa; caps = exposición máxima; secuencia
   separada).
3. **El tier esperado por arquetipo es NO vinculante:** `tier < min → no_pasa`; `tier esperado →
   cap neutral`; `tier superior → libera el cap pero NUNCA por encima de base_cap`. El tier solo
   **remueve** una restricción, nunca da bonus.
Niveles (sabor Kelly, calibrar contra realizaciones): VALIDATED ≈ ⅓, COMMITTED ≈ ⅔, REALIZED = pleno,
**condicionados a `materiality`** (REALIZED inmaterial ≠ cap pleno). Loggear la restricción **binding**
por posición; si el tier no ata nunca en 3 meses, los niveles están mal calibrados.

## 3. Los CONTRATOS entre piezas (lo que faltaba — el core de ambas revisiones)
- **Snapshot sellado + estado de corrida.** `analysis_run_id`, `status ∈ {RUNNING, COMPLETE,
  FAILED}`, `snapshot_id`, `sealed_at`. **El gate solo consume snapshots COMPLETE y sellados.** Si
  falla el hecho 7 de 12, la corrida **no publica** (mata el "Frankenstein snapshot" de corridas parciales).
- **Multi-timestamp** (accepted_at solo NO alcanza): `published_at` (cuándo el mercado pudo saber) ·
  `effective_at` (período económico del hecho) · `accepted_at` (cuándo lo ingerimos) · `valid_until` ·
  `superseded_at`. Invariante: **ninguna decisión en t usa una fuente publicada después de t.**
- **Reason codes** (los cuatro casos que hoy comparten UNKNOWN no pueden): `NOT_SEARCHED ·
  SOURCE_UNAVAILABLE · NOT_FOUND_IN_SCOPED_CORPUS · AMBIGUOUS · CONFLICTING · STALE · PARSER_FAILURE ·
  CORPUS_LIMIT · NOT_APPLICABLE`. **Un error de infra NUNCA escribe una fila de hecho.**
- **Frescura/decaimiento (silencio ≠ TRUE).** `half_life` por fact_key; un documento que debería
  refrescar un hecho y no pudo → el hecho viejo pasa a `STALE_PENDING_REFRESH` y **no abre el gate
  en silencio**. Los hechos de demanda decaen de tier si no se re-afirman en N filings.
- **`CONTESTED`** (contradicción intra-snapshot: dos DIRECT verbatim mutuamente excluyentes) →
  NO_EVALUABLE → cuarentena "¿cuál supersede?". **Nunca resolución implícita por orden de chunk.**
- **Contrato de evidencia por `fact_key`** (no solo pregunta+anchors): `entity_scope`,
  `document_types`, `lookback_required`, `period_semantics`, `source_priority`, `freshness_limit`,
  `negative_evidence_rule`, `cardinality`. Sin esto, retrieval no sabe qué corpus alcanza para evaluar.
- **`derived_from_fact_ids`.** Un DERIVED que depende de revenue+backlog debe **invalidarse/
  recalcularse** si un 10-K/A corrige un padre. Append-only + supersesión simple no alcanza.
- **`entity_id` interno estable** + mapa versionado ticker↔CIK↔issuer↔subsidiarias (ticker no es
  identidad: reuso post-quiebra/SPAC, múltiples CIK, ADR, subsidiarias nombradas en contratos).
- **Decision envelope inmutable (gate→PM):** `{PASS/NO_PASS/NO_EVALUABLE, evidence_tier, evidence_cap,
  materiality, snapshot_id, valid_until, invalidation_events}` + versiones (`fact_key_registry_version,
  gate_version, cap_table_version, archetype_version, fragility_version, code_commit`). El PM decide
  sobre ese paquete; **no re-consulta "el último snapshot"** durante la decisión. Y explícito:
  **evidencia más madura ⇒ más exposición, NO más alpha** (REALIZED puede estar totalmente descontado;
  el motor controla admisibilidad y riesgo de tesis, no estima retorno).
- **Entailment:** matriz `sección × support_type` — un risk factor ("we may not be able to…") es
  verbatim y fundado pero **no puede producir un DIRECT positivo**.
- **Límites de recurso:** `MAX_DOCUMENT_SIZE / MAX_CHUNKS / MAX_RETRIEVAL_TIME` → exceder →
  `NO_EVALUABLE: CORPUS_LIMIT`, nunca fragmentos parciales como si el corpus fuera completo.

## 4. Cuarentena como máquina de estados (no un loop)
Estados: `OPEN · SEARCHING · RESOLVED_TRUE · RESOLVED_FALSE · PERSISTENT_UNKNOWN · SOURCE_ERROR ·
WAITING_NEW_CORPUS · CONFLICT`. Identidad = `entity_id + fact_key + corpus_version + fact_key_version`.
**Se re-dispara solo si cambia** corpus_version / fact_key_version / entity_mapping / evento material
del emisor — **NO porque volvió a correr el scheduler** (mata el loop encubierto).
- **Camino DISTINTO** al que ya falló: sin pre-filtro de título, corpus ampliado (filings anteriores +
  incorporación por referencia), framings nuevos. "Si el segundo intento es el mismo intento, no es
  un segundo intento."
- **Presupuesto:** 1 búsqueda por `fact_key × corpus_version`, top-k chico (≤3), análisis de
  contradicción entre hits, misma verificación que el camino principal → luego PERSISTENT_UNKNOWN.
- **Estándar probatorio ≥ al del pipeline normal** (nunca inferior; más conservador): no resolver
  desde un único hit ambiguo; desacuerdo → CONFLICT; cualquier duda → PERSISTENT_UNKNOWN.
- **"Buscado y no encontrado" = registro `SearchAttempt` aparte** (NO un NxFact): `query_signature,
  corpus_hash, accessions_searched, hits_examined, result, reason_code`. **NOT_FOUND ≠ FALSE** — solo
  una disclosure negativa explícita produce FALSE.
- **Provenance `source=quarantine`** + techo de tier un nivel abajo salvo corroboración XBRL (nunca
  REALIZED desde un solo hit dirigido).

## 5. Harness ampliado (antes de vivo) + invariantes automáticas
125/125 sobre 4 nombres limpios es un **benchmark saturado**. Familias a agregar:
**A.** correctitud de decisión end-to-end (gate/tier/cap, no solo el hecho; errores asimétricos —
falso PASS, cuarentena falsamente resuelta, cap demasiado alto → tolerancia ~cero). **B.** recall de
retrieval (separar: doc en corpus / chunk recuperado / chunk bien interpretado). **C.** integridad
temporal (replay: 10-K→10-K/A, 8-K de terminación, ingesta con retraso, backfill, cambio de fiscal
year, stale vs. vigente). **D.** atomicidad/concurrencia (falla el 6º fact, reintento, dos workers,
gate durante persistencia). **E.** precisión de cuarentena (false-resolution rate es la métrica clave,
no el yield). **F.** metamórficos (mismo filing, distinto chunking/whitespace/orden → **decisión
idéntica**). **G.** corpus adversarial (NT, amendments, FPIs, múltiples CIK, contrato terminado,
"up to/subject to/non-binding"). **H.** operación (latencia p50/95/99, costo/ticker, FTS failure
rate, % snapshots sellados, freshness por fact_key).
**Invariantes automáticas (deben dar 0):** `unsupported_hard_fact == 0` · `gate_on_incomplete_snapshot
== 0` · `cap_increase_por_missing_evidence == 0` · `NOT_FOUND_convertido_a_FALSE == 0` ·
**`churn_sin_filing_nuevo == 0`** (cualquier valor positivo = el bug COHR volviendo).
**Gold set:** 25-50 casos **difíciles estratificados** (FPIs, enmiendas, terminados) > cientos de fáciles.

## 6. Plan FASEADO (con gating)
- **Fase A — Contratos de correctitud (PRE-SHADOW, BLOQUEANTE):** snapshot sellado + run status ·
  reason codes + INDISPONIBLE (infra nunca escribe hecho) · frescura/decaimiento · CONTESTED · gate
  de dos capas + demanda desglosada · cuarentena FSM · entailment (sección×support_type).
- **Fase B — Sello del track record (PRE-VIVO):** bitemporal (published/effective/accepted) + test
  de reproducción byte-a-byte · `derived_from_fact_ids` + invalidación en cascada · decision envelope
  versionado · tier→caps con las 3 condiciones + materiality.
- **Fase C — Cobertura (faseable):** contratos de evidencia ricos · entity map · casos rotos
  (10-K/A lineage, NT, 10-KT, FPIs, incorporación por referencia, CORPUS_LIMIT) · hechos multi-documento.
- **Fase D — Harness A-H + invariantes + gold estratificado** (cruza todas).
- **Fase E — Integración:** (0) **sellar** (pin de modelo/prompt/retriever + hash, stores separados) →
  (1) **replay offline** sobre cartera paper histórica + rechazados + COHR + adversariales (valida el
  MOTOR, no el edge; el look-ahead de training no toca la corrección de extracción) → (2) **shadow por
  COBERTURA** (viejo alimenta el paper, nuevo no opera; mínimo 4-6 semanas **Y** 50-100 decisiones
  materiales **Y** una temporada de filings — "lo que ocurra último") → (3) **adjudicar divergencias
  contra el filing** con barra asimétrica (≥95% nuevo-correcto y **cero** falso-PASS que abra lo que
  el viejo rechazaba) → (4) **canary** (fact_keys no-críticos o 20% del universo, kill-switch) →
  (5) **cutover** con el viejo de monitor un trimestre más.
  **No medir paridad simple** (el viejo es inestable, no es el oracle; paridad alta puede ser reproducir
  sus errores). El balde NO_EVALUABLE es bueno (la versión honesta de lo que el viejo adivinaba) pero
  si supera ~30-40% del universo el trabajo pendiente es **retrieval, no gate**.

## 7. Honestidad de alcance
Esto es **trabajo real de semanas, no de días** — es la diferencia entre un demo lindo y un sistema
seguro de conectar a plata. La triangulación del conjunto reveló el alcance verdadero **antes** de
tocar el paper. Ninguna de las piezas hay que tirarla; hay que **escribir los contratos entre ellas.**
