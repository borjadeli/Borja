# 57 — Auditoría externa del brief de P1 (doc 56) — IA 1

> Devolución de la **IA 1** (2026-10-27) sobre el brief de P1 (doc 56), leído contra el código v2 real en
> `origin/destete-v2-fase3@afff48e`. **Pendiente: converger con la IA 2.** No reescribir el brief ni codear
> hasta cerrar las decisiones con ambas. Captura fiel; mis notas de acción van al cerrar la convergencia.

## Conclusión
Aun con P1 implementado tal como está escrito, **ninguno de los 3 nombres del smoke llegaría a PASS**. El
cuello **no** es la cobertura de XBRL: es que la regla del brief **no tiene camino a PASS para claims
centrales cualitativos ni para pronósticos**, y esos son la tesis real de un pre-revenue.

En paralelo, **dos agujeros por los que el sistema SÍ compraría sobre evidencia mala:**
1. La clase epistémica (`verification`, `tipo`) y la centralidad (`tesis_claims_soporte`) las declara **el
   mismo Analista** al que se verifica.
2. Si el dossier **no tiene claims centrales**, el veredicto actual es **PASS** (`verificador.py:45-75`).

Conteo de los 12 centrales del smoke bajo la regla del brief → **0/3 llegarían a PASS aunque XBRL fuera
perfecto**: OKLO (C4 OTA DOE cualitativo, C8 EV con quema estimada sin contraste), RKLB (C2 "17 contratos"
KPI, C3 "backlog récord"), ACHR (C4 fase FAA, C5 estimación de fool.com, C2 NTBV de un 424B5 sin XBRL).

## 1. Las 6 decisiones abiertas
- **D1 · Umbral de PASS — ✗ incompleto.** Solo cubre `company_statement`/sin procedencia; un central
  `estimacion/inferencia/analyst_prior/hypothesis` cae a "PASS posible". No distingue "no contrastable" de
  "contradicho" (la contradicción debe ser **FAIL**, no REVIEW; hoy `contrastar_xbrl` la vuelve UNKNOWN,
  `extractor_citado.py:124`). Exigir "todos los centrales con número contrastado" deja sin salida a los
  cualitativos. **Propuesta: todos los centrales pasan, cada uno por la ruta de su tipo:**
  - Numérico ORIGINAL → contraste XBRL/fact store. OK→hecho · contradicho→FAIL · no contrastable→REVIEW.
  - Numérico DERIVED (EV, P/S, dilución del Analista) → coincide ±tol con un DataPoint DERIVED del pack; sin
    DataPoint→REVIEW; no coincide→FAIL.
  - Cualitativo → cita verificada en el texto completo + entailment + **fuente filed** (10-K/10-Q/S-1/8-K
    Item 1.01/8.01) o fuente primaria de tercero (regulador/contraparte) → PASS posible. PR/IR/transcript → REVIEW.
  - Pronóstico/estimación/hipótesis → **no puede estar en `tesis_claims_soporte`** (va a supuestos/falsador);
    si aparece → REVIEW.
  - Lista de centrales vacía o con ids inexistentes → **FAIL** (hoy da PASS).
- **D2 · Orden de calculadoras — ◐.** Dilución/runway/CRR primero, bien. Pero no hay archivo owner-FCF (es
  FCF−SBC en `edgar.py:638`) y en pre-revenue da negativo. (1) primero un DataPoint de **shares reconciliado
  XBRL↔Yahoo** (ACHR 757,9M filing vs 770M Yahoo → dilución falsa); (2) `t_star` **no** debe quedar atrás para
  nombres con revenue (RKLB: el Analista inventó un reverse-DCF a mano con 10%/25x/20% — la alucinación de
  valuación más cara; `valuacion_reverse.t_star` + serie con as_of ya existen); (3) mientras falte `t_star`,
  el verificador marca cualquier número de valuación del Analista como `hypothesis` no central.
- **D3 · Pre-revenue — ✓** con 2 condiciones: el `stage` que rutea lo deriva el **código** desde revenue/GP
  de XBRL (como `arquetipo.py`), nunca el LLM; cerca del umbral, el pack emite **las dos** familias. Además
  `gap_financiamiento`/runway toman la caja del **último instant** (la caja al 31/12 de OKLO subestima
  ~US$1.2B por el raise de enero).
- **D4 · Costo — ◐.** El costo no es el problema; **batchear sí** (mezcla pasajes entre claims; un JSON roto
  tira el lote). Llamadas **por claim**, solo cualitativos centrales (si un numérico ya pasó XBRL, el
  entailment no agrega), cache por `hash(claim,pasaje)`. **Ojo:** `verificar_entailment` usa por default
  **Haiku 4.5** (`extractor_citado.py:27`), no Sonnet como dice el brief — decidir explícito.
- **D5 · Freshness — ◐.** El 8-K de resultados es evento; re-extraer debe invalidar el cache de companyfacts
  (hoy 24h en disco); TTL por `fact_type` (SNAPSHOT corto/STRUCTURAL largo/EVENT solo se reemplaza); un
  10-K/A reemplaza al original; **`dato_vigente` no sale de `page_age`**: es False si el fact store ya tiene
  una accession más nueva para la métrica (OKLO usó 4T25 en oct-2026 con dos 10-Q posteriores → REVIEW).
- **D6 · Cobertura XBRL — ◐.** Medir los **átomos numéricos de los centrales de dossiers reales**, no el
  total de tags. "Sin XBRL→REVIEW" aplicado a cualitativos es la trampa que hace que nunca compre (ver D1).

## 2. Errores de diseño
**Compraría sobre evidencia mala:**
- **A. Etiquetas autodeclaradas.** El gate REVIEW usa `verification == company_statement`, puesta por el
  Analista. RKLB C1 es un EX-99.1 (press release) marcado `confirmed_by_filing`. **Fix: la clase la deriva el
  código desde la URL** (accession→form+exhibit vía submissions, + dominios de reguladores); lo que declare el
  LLM se ignora.
- **B. Centralidad manipulable.** `materiality` y `tesis_claims_soporte` se contradicen (RKLB C5/C6/C7
  `central` pero fuera de soporte; C3 soporte pero no central; el claim de memoria C5 se escapó). Con "todos
  los centrales pasan", el Analista aprende a declarar centrales solo los números fáciles. **Fix: rechazar el
  dossier si `materiality` y `tesis_claims_soporte` no coinciden; todo id citado por `bull.tesis`/`falsador`
  es central; el reporte expone cobertura por clase (PASS = hechos ciertos ≠ tesis probada).**
- **C. No hay texto fuente para `verificar_cita`.** El loop guarda solo URLs (`base.py:89`); `cited_text` lo
  escribe el LLM; `web_search_tool_result` viene encriptado. **Hoy no hay contra qué verificar.** Fail-closed:
  cita no verificable = no verificada → la evidencia central tiene que salir de **EDGAR (fetcheable) o el fact
  store**; para lo demás, sumar `web_fetch` al loop y **persistir el texto**.
- **D. `contrastar_xbrl` con bugs concretos:** **signo** ("pérdida US$139.3M" vs `OperatingIncomeLoss=-139.3M`
  → error 2.0 → rechaza todo pre-revenue); **escala** (M/B/miles, OKLO C9 en miles); **período** (no mapea
  Q/YTD/FY/instant); **tolerancia** fija 2% vs "~US$1.4B" (debería ser `max(2%, media unidad del último
  dígito)`); y el mapeo concepto↔texto no lo resuelve nadie → **contrato: los claims numéricos centrales
  llevan `ref` a un `fact_key`/id de DataPoint, y el contraste es por id, no por NLP**.
- **E. Entailment sobre cita truncada** (`cited_text` cortado a ~150 chars) → NOT_SUPPORTS falso. Correr el
  entailment sobre el chunk alrededor del span.

## 3. Contrato data pack ↔ calculadoras (§2.1)
- **`known_at = el hecho más viejo` es look-ahead.** Un derivado se conoce al conocerse su **último** insumo
  → `known_at = max(inputs.known_at)`; la antigüedad del más viejo va a `stalest_input_at`. Con el mínimo,
  `visible_en(t)` ve el futuro en replays/backtests.
- **"Insumos = hechos del fact_store" contradice el diseño** (`fact_keys.py:25`: el fact store guarda solo
  hechos **cualitativos**; los números salen de companyfacts). Hace falta una **`fuente_xbrl` de primera
  clase** que emita DataPoints ORIGINAL con `accn/filed/period`, y que las calculadoras consuman esos
  DataPoints, no `edgar.*` directo.
- **`Fuente(ticker, as_of)` es ficción** para varias calculadoras (`get_financials_quarterly`,
  `calcular_crr_ticker` no aceptan `as_of`; traen lo último).
- **`inputs = nombres de métricas` no da linaje** → ids de hecho (accession+concepto+período).
- **Defaults peligrosos** (`provenance.py:59-60`): `kind=ORIGINAL` + `verification=CONFIRMED_FILING` → los
  datos de Yahoo quedan "confirmados por filing". Obligatorios, sin default.
- **Omitir en silencio** un insumo faltante hace que el Analista invente (los 3 dossiers dicen "el pack no
  trae T*… cuenta propia"). Emitir un DataPoint explícito `value=None` con motivo; el verificador no da PASS a
  un central sobre una métrica que el pack declara nula. Ídem el `except` de `ensamblar` (`data_pack.py:72`).

## 4. Riesgos de implementación (cobertura XBRL)
- **IFRS = cero cobertura** (`_extract_concept` solo us-gaap+dei, `edgar.py:235`): 20-F/40-F sin contraste,
  6-K trimestrales sin XBRL — parte relevante en nuclear/minería/uranio.
- **Mezcla de monedas silenciosa** (`edgar.py:244` toma la primera unidad, p.ej. CAD, sin marcar).
- **Lag earnings↔10-Q (1-4 sem):** el EX-99.1 no tiene XBRL → los números frescos quedan sin contraste justo
  en la ventana del catalizador. Estado **"contraste pendiente"** que se resuelve al llegar el 10-Q.
- **Techo de companyfacts:** sin segmentos/dimensionales (revenue/GM por segmento de RKLB, shares por clase),
  sin extension tags (KPIs, backlog), sin non-GAAP ("liquidity", "adjusted burn"), sin hechos posteriores, sin
  NTBV de prospectos. Primer escalón: **parser del instance XBRL por filing** ("Fase 2 filing-céntrica"; OKLO
  C9 ya citaba un `Financial_Report.xlsx`).
- **Reexpresiones:** companyfacts guarda varios valores por período (accn+filed); contrastar contra el último
  en vez del **vigente al `known_at` del claim** da falso FAIL.

## 5. Medición propuesta ANTES de cerrar D1 y D6
- Muestra: los ~12 centrales del smoke + 20 dossiers del gold set.
- Separar cada claim en **átomos numéricos y cualitativos** y clasificar en 5 cubos: *contrastable en
  companyfacts / contrastable solo en el instance del filing / non-GAAP o KPI / cualitativo con fuente filed /
  pronóstico*.
- **Umbral:** si "contrastable en companyfacts" **< ~60%** de los átomos numéricos → P1 **debe** incluir el
  parser del instance; si no, el PASS va a ser raro.

## 6. Prioridad si hay que recortar
1. Clase epistémica derivada por código + cerrar el PASS con centrales vacíos/colgantes.
2. Ruteo de D1 por tipo de claim, con la contradicción como FAIL.
3. Fuentes con texto persistido y verificación fail-closed.
4. Contraste numérico por ref a DataPoint (resuelve signo, escala, período).
5. `known_at = max` y sacar los defaults de `provenance`.

**Sin 1, 2 y 3, P1 o no compra nunca o compra sobre etiquetas que puso el propio Analista.**
