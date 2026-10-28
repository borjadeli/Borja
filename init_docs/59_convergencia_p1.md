# 59 — P1: resolución convergida (IA 1 + IA 2)

> Síntesis de las dos auditorías del brief (doc 56): **IA 1** (doc 57, leyó el código v2) + **IA 2** (doc 58,
> auditó el diseño). **Convergen fuerte.** Este doc CIERRA las decisiones y es de lo que se codea. No reabre
> paradigma/método/comité/quién decide. El brief doc 56 queda **superado por este** en todo lo que contradiga.

## Veredicto común
P1 es la dirección correcta, pero **el brief, como estaba, o no compra nunca o compra sobre evidencia mala**.
La raíz (ambas IAs, distinto ángulo): el brief **equipara dato trazable = dato bien calculado = evidencia
económicamente suficiente**, y **no le da ruta a PASS a los claims cualitativos** (la tesis real de un
pre-revenue). Fix = separar esas tres cosas y endurecer el verificador, sin relajar el estándar.

## Decisiones CERRADAS (reemplazan los defaults del doc 56 §3)
- **D1 · Umbral de PASS.** El conjunto a verificar son los **HECHOS EMPÍRICOS críticos** necesarios para la
  tesis, no todas las afirmaciones interpretativas. Procedimiento: (a) **congelar** el inventario de centrales
  antes de verificar; (b) separar **hecho observable / inferencia / pronóstico**; (c) exigir que **todos los
  hechos críticos** pasen; (d) las **inferencias** son razonamiento sobre esos hechos (no se exige XBRL); (e)
  **pronóstico/estimación/hipótesis NO puede ser central** → va a `supuestos`/`falsador`. `critical_facts > 0`
  o **FAIL**; central contradicho no puede esconderse en un secundario; lista central vacía/colgante → **FAIL**
  (hoy da PASS). Un central **contradicho** por evidencia → **FAIL** (no REVIEW).
- **D2 · Orden de calculadoras** por **cobertura del universo + desbloqueo**, NO por cantidad de inputs:
  **P1-A** runway + dilución + `capital_raise_risk` + financiación del critical path · **P1-B** reverse burden
  de gross profit · **P1-C** owner-FCF (maduras; y NO es de pocos inputs: maintenance capex/SBC = juicio) ·
  **P1-D** `t_star`/g_D/burden. Pero **`t_star` NO se difiere para nombres CON revenue** (si no, el Analista
  inventa un reverse-DCF a mano — pasó con RKLB); mientras falte, el verificador marca todo número de
  valuación del Analista como `hypothesis` no central.
- **D3 · Pre-revenue.** Método OK (reverse underwriting + funded critical path + dilución). El contrato
  distingue **`cash_runway`** / **`funding_gap`** / **`funded_critical_path`**; **NO** cuenta como asegurado
  shelf/ATM/promesas/ronda futura (solo financiación disponible o jurídicamente comprometida). **Sobrevivir ≠
  demanda:** la evidencia comercial se verifica aparte. El `stage` que rutea lo deriva el **código** (XBRL
  revenue/GP), nunca el LLM; cerca del umbral se emiten las dos familias. Caja/runway toman el **último
  instant** (no el 31/12 si hubo raise posterior).
- **D4 · Verificador LLM.** Veredicto **por claim** (`claim_id, evidence_id, entailment, limitations,
  contradiction_found`), nunca un PASS global de batch. Orden: **deterministas primero** (`verificar_cita` +
  contraste numérico), **Sonnet solo** para centrales cualitativos que requieren semántica. Entailment sobre
  el **chunk alrededor del span** (no la cita truncada a 150 chars). Caché por `hash(claim, evidencia, versión
  del verificador, modelo)`. **Decidir modelo explícito** (`verificar_entailment` hoy usa Haiku por default,
  no Sonnet).
- **D5 · Freshness.** Evento (incluye 8-K de resultados) + **TTL por `fact_type`** (SNAPSHOT corto /
  STRUCTURAL largo / EVENT se reemplaza). Timestamps separados **`known_at` / `observed_at` / `extracted_at`
  / `valid_until`**. Un input nuevo (10-Q/8-K) **invalida y recomputa los derivados dependientes** aunque
  estén dentro del TTL. Re-extraer invalida el caché de companyfacts (hoy 24h). `dato_vigente=False` si hay
  una accession más nueva para la métrica. Un 10-K/A reemplaza al original.
- **D6 · XBRL.** Medir cobertura: **sí**. "Sin XBRL → REVIEW automático": **NO**. Tres rutas de validación
  (IA 2): **A Financiera** (XBRL + período + unidad + fórmula) · **B Documental** (filing/notas/exhibits/
  contrato/regulatorio; el verificador comprueba la **naturaleza económica**, no solo que el texto exista) ·
  **C No corroborada** (guidance/comercial/comunicado → **REVIEW si es central**). **La ruta B es
  imprescindible** para que un pre-revenue llegue a PASS legítimo.

## Las 4 correcciones CRÍTICAS de contrato/verificador (condición de aprobación — IA 2; confirmadas por IA 1)
1. **Temporalidad:** `derived.known_at = max(input.known_at)` (NO el más viejo) + `assert input.known_at <=
   as_of`. El más viejo va a `stalest_input_at`. El mínimo = look-ahead en backtests/snapshots. **(bloqueante)**
2. **Lineage:** `inputs` deja de ser nombres de métrica → **referencias de hecho inmutables** (accession +
   concepto + período) con valor/unidad/moneda + `known_at` + estado de validación. DataPoint derivado:
   `formula_id`, `input_refs`, `computed_as_of`, `validation=COMPUTED`, `source_lineage`. Estados internos
   distintos: **MISSING / STALE / CONFLICTED / NOT_APPLICABLE** (no la misma respuesta del verificador).
3. **Suficiencia probatoria ≠ extracción correcta:** el verificador valida **dos dimensiones** — (técnica:
   cita/número/período/fórmula/entailment) **y** (suficiencia: ¿el documento prueba el **hecho económico**
   que exige el claim?). **XBRL NO es fuente independiente del filing.** Política por tipo de claim ("hasta
   US$500M" ≠ compra comprometida; "generará US$500M en 2028" = proyección, no hecho). Leer
   **negaciones/contingencias** alrededor de la cita. **`root_source_id` + `issuer_id`** en la procedencia →
   3 URLs del mismo comunicado = 1 fuente, no 3.
4. **Clase epistémica derivada por CÓDIGO, no autodeclarada** (IA 1): `verification`/`tipo` salen de la URL
   (accession→form+exhibit; dominios de reguladores), no de lo que diga el Analista. Centralidad = lo que cite
   `bull.tesis`/`falsador`; rechazar el dossier si `materiality` y `tesis_claims_soporte` no coinciden.

## Bugs de código CONFIRMADOS por IA 1 (leyó el código) — reproducir y arreglar
- `contrastar_xbrl`: **signo** (pérdida −139.3M vs "139.3M de pérdida" → rechaza todo pre-revenue), **escala**
  (M/B/miles), **período** (Q/YTD/FY/instant), **tolerancia** fija 2% (→ `max(2%, media unidad del último
  dígito)`). Fix de contrato: el claim numérico central lleva **`ref` a `fact_key`/id de DataPoint** → contraste
  por id, no por NLP.
- `provenance.py:59-60`: defaults `kind=ORIGINAL` + `verification=CONFIRMED_FILING` → datos de Yahoo quedan
  "confirmados por filing". **Obligatorios, sin default.**
- `verificador.py`: central vacío/colgante → **PASS** (bug) → debe ser FAIL.
- `data_pack.py:72`: `except` silencioso → una calculadora rota desaparece sin rastro.
- **Sin texto fuente para `verificar_cita`:** el loop guarda solo URLs; `cited_text` lo escribe el LLM;
  web_search viene encriptado → **hoy no hay contra qué verificar.** Fail-closed: cita no verificable = no
  verificada → evidencia central de **EDGAR/fact store**; para el resto, `web_fetch` + **persistir texto**.
- `_extract_concept` solo us-gaap+dei → **IFRS = 0 cobertura** (20-F/40-F/6-K); **mezcla de monedas** silenciosa.

## Gate de medición ANTES del rollout (ambas IAs lo exigen)
Piloto **~20 empresas (≥12 pre-revenue)** + los 12 centrales del smoke. Medir por **claim y por arquetipo**:
% de centrales con evidencia suficiente · % por ruta A/B/C · % de REVIEW por límite del extractor vs debilidad
de tesis · **falsos PASS/REVIEW vs referencia humana**. Clasificar cada átomo en: companyfacts / solo instance
del filing / non-GAAP o KPI / cualitativo con fuente filed / pronóstico. **Si "companyfacts" < ~60% de los
átomos numéricos → P1 DEBE incluir el parser del instance XBRL** (IA 1). **Batería adversarial con CERO falsos
PASS críticos** (IA 2 §5) antes de conectar a producción.

## Orden de implementación (convergido)
1. **Temporalidad** (`known_at=max` + consistencia) — crítico, es además bug de código.
2. **Lineage** (ids de hecho + estados + DataPoint None explícito) — crítico.
3. **Suficiencia probatoria** + clase epistémica por código + centrales vacíos/contradichos (verificador) — crítico.
4. **Ruta documental B** (PASS sin XBRL obligatorio) + fail-closed de citas — crítico (destraba pre-revenue).
5. **Calculadoras P1-A** (runway/dilución/CRR/critical path) como `fuente_xbrl` de primera clase.
6. Caché + batch por claim + recomputación incremental.
7. **Medición por arquetipo + batería adversarial** antes de ampliar el rollout.

## Único punto a decidir con el operador (no lo cierran las IAs)
El **gate de medición (paso 7 / pre-rollout)** necesita una **referencia humana** (clasificación de los
claims centrales) para medir falsos PASS/REVIEW. ¿La hace el operador sobre el piloto de ~20, o se difiere y
se arranca con la batería adversarial sintética (casos construidos a mano, sin depender de etiquetado humano)?
