# 22 — Motor de evidencia: SPEC CONSOLIDADO (fusiona 20 + 21 + triangulación)

> Post-triangulación (2 IA adversariales independientes, convergentes). **Esto es lo
> acordable**: reemplaza y unifica los docs 20 y 21. El código sale de acá, con tu OK
> explícito para la lógica de decisión nueva (marcada 🔒). Grounded en el código actual.

## 0. Qué cambió al triangular (resumen ejecutivo)
- **El edge es cobertura × linkage × consistencia, NO velocidad.** Descubrir cuellos
  genuinamente pre-consenso es una **hipótesis a demostrar**, no la premisa que se vende.
  Afirmación honesta: *"la máquina revisa sistemáticamente más eslabones, detecta cambios
  y no olvida contradicciones"* — eso ya vale, y no escala en AUM (por eso sobrevive).
- **Arreglar el extractor NO construye edge: construye la infraestructura para BUSCAR edge
  sin engañarse** (integridad/estabilidad/auditabilidad). Son tres pruebas distintas:
  **Grounding / Novedad / Alpha.** Hoy resolvemos la 1ª; la 3ª (alpha) es una **hipótesis a
  demostrar**, no una promesa. Lo más probable: la ventaja inicial es velocidad + amplitud +
  disciplina sobre información pública; una fracción menor puede volverse descubrimiento
  pre-consenso real. Se diseña y mide bajo *esa* expectativa, no bajo "IA omnisciente".
- **Extractor actual = memoria del LLM** (la "Versión A" prohibida). Es a la vez el bug de
  estabilidad (COHR) y lo contrario del edge.
- **Universo:** perseguimos el **cuello real, incluido no-US**, gated por **calidad de
  evidencia** (decisión del operador; el bróker opera afuera).

## 1. Principio rector (extendido)
Datos y límites duros deterministas; el LLM trae **hechos citados** y **nunca** un número de
decisión. **Extensión (triangulación):** el LLM tampoco elige (a) los **thresholds** de los
falsificadores, (b) la **estructura** del grafo de cadena. Solo aporta **estado + evidencia +
hipótesis etiquetadas como tales**.

## 2. Taxonomía de soporte — el corazón de la integridad
Cada hecho lleva un `support_type`:
- **DIRECT** — el filing lo declara explícitamente.
- **DERIVED** — se obtiene por **fórmula determinista** sobre números citados.
- **INFERRED** — interpretación económica del LLM (cross-empresa, cadena).
- **UNKNOWN** — sin soporte suficiente.
**Solo DIRECT y DERIVED alimentan hard gates.** INFERRED prioriza investigación, nunca
satisface un booleano del gate. **Orden de resolución (derivar-antes-de-extraer):**
`XBRL → disclosure obligatoria → texto con cita → UNKNOWN`.
> COHR era **DERIVED** (ASC 805 obliga revenue pro-forma en la nota de business combination),
> no una moneda al aire. El extractor debía *computarlo*, no recordarlo.

## 3. Estados de hecho y de gate — "no evaluable" ≠ "falso"
- **Hecho:** `TRUE · FALSE · UNKNOWN_NOT_DISCLOSED · UNKNOWN_RETRIEVAL_FAILURE ·
  CONFLICTING_EVIDENCE · NOT_APPLICABLE`.
- **Gate:** `pasa · no_pasa · todavia_no · NO_EVALUABLE` (🔒 estado nuevo). Un hecho
  obligatorio **no divulgado** → **NO_EVALUABLE / cuarentana** con la *pregunta que lo
  resolvería* nombrada, **no rechazo** ("empresa mala") ni FALSE ("hecho falso").
  `RETRIEVAL_FAILURE` nunca se lee como "el filing no lo dice".

## 4. Modelo de hecho (fact store)
Identidad = **`fact_key` canónico** (p.ej. `organic_growth_available`,
`customer_concentration_pct`, `take_or_pay_present`, `capacity_expansion_date`), **NO** la
accession. Campos por hecho:
`value · support_type · quote_exacta + quote_start/quote_end · chunk_id · source_accession ·
cik · accepted_at · period_end · fact_type · valid_from · valid_until · superseded_by ·
last_confirmed_at` + **provenance**: `model_id · prompt_version · retriever_version ·
schema_version · document_hash`.
Guardar **todo el historial lógico, inmutable** (dedup textual por hash; el storage es ruido).

## 5. Vigencia y frescura (corrige la regla global del doc 21)
La accession es **linaje, no vigencia económica**. Clasificar cada hecho:
| `fact_type` | ejemplos | vigencia |
|---|---|---|
| **SNAPSHOT** | revenue, margen, caja, backlog al cierre | lo reemplaza el próximo período comparable |
| **EVENT** | contrato, adquisición, capacidad anunciada | vigente hasta ejecución/cancelación/supersesión |
| **STRUCTURAL** | qualification cycles, tecnología, sitios | persiste; requiere reconfirmación periódica |

- **Dos relojes:** fundamentals (último periódico) vs. nodo/catalizador (8-K, precios). Un
  8-K actualiza **solo los dominios afectados** (contrato/adquisición/guidance/capacidad/
  deuda/regulatorio), nunca "renueva todo el extractor".
- **STALE dinámico** (no N fijo): vencido si pasó la **fecha esperada del próximo filing**
  (derivada del **calendario fiscal del propio emisor** + cadencia histórica) + gracia corta.
  `NT 10-Q/NT 10-K` → `LATE_FILER`. `8-K Item 4.02` (restatement) → **invalidación dura** del
  fact store del ticker. `Item 5.03` (cambio fiscal) → recalcular cadencia. `10-K/A` → keyear
  por **datetime de filing**, no por período (o se filtran cifras restateadas hacia atrás).
- **Ficha actual** = último 10-Q/10-K + 8-K posteriores relevantes + estructurales vigentes.

## 6. Point-in-time (`as_of_ts`)
El resolver responde *"¿cuál era el último filing **públicamente disponible** en `as_of_ts`?"*
usando **`accepted_at`**, no la fecha nominal. Arregla el look-ahead de **datos**. **NO**
arregla el look-ahead de **training del LLM** → por eso el juicio de alpha es **forward paper
sellado**, no backtest.

## 7. Pipeline del extractor (9 pasos)
1. **Resolver corpus point-in-time** (`as_of_ts`).
2. **Descargar + hashear** documentos — `primary_doc` **+ exhibits** (Ex-10 contratos
   materiales = take-or-pay/prepagos; Ex-21 subsidiarias). Truncado/incompleto → `RETRIEVAL_FAILURE`.
3. **Seccionar + chunkear** (IDs estables; headings Reg S-K como ayuda, no frontera dura;
   varios patrones + fallback a chunking; loggear fallas de parseo como métrica de calidad).
4. **Extraer claims estructurados** con `quote` **literal** (`claim_normalizado` separado de
   `quote_exacta`; el LLM normaliza el valor pero **copia** el pasaje).
5. **Verificar soporte** — determinista: chunk correcto · offsets · quote literal normalizada ·
   **números citados ⇒ contra XBRL** (difieren → rechazo) · regla semántica de campo. Falla →
   **1 reintento con el chunk** → si vuelve a fallar, UNKNOWN.
6. **Clasificar** DIRECT/DERIVED/INFERRED/UNKNOWN (§2).
7. **Compilar snapshot vigente** (capa aparte: el store guarda historia; esto decide qué está
   vigente hoy según §5).
8. **Publicar atómicamente** — construir+validar el nuevo snapshot y **recién ahí** mover el
   puntero de versión. Si falla, se conserva el anterior como **STALE** y **no** se sirve a
   hard gates.
9. **Cachear/versionar** todo (con provenance §4).

**Un solo extractor, distinta profundidad:** screen = XBRL + retrieval dirigido sobre filing +
8-K recientes, pocos chunks; deep = más queries/chunks + exhibits + históricos. **Nunca full
filing crudo** (dilución de atención; risk factors envenenan). **Precision > recall en hard
gates.** Verificación = **substring normalizado + offsets**; embeddings **solo para retrieval**,
nunca para validar. Recall se protege en el **retrieval** (varias queries/sinónimos por
`fact_key`, corpus completo, fallback), no relajando el verificador.
**🔒 K=3 con unanimidad en booleanos gate-críticos** (desacuerdo → UNKNOWN). En `opus-4-8` no
hay `temp=0`, así que la robustez viene del K-voto, no del sampling.

## 7bis. Capa generadora — la memoria como MARCO, no como hecho (idea del operador)
La memoria del LLM tiene varianza. Es un **bug para hechos y un feature para leads** — misma
técnica (llamar K veces), **agregación opuesta**:
- **Hechos de decisión → INTERSECCIÓN.** K llamadas con **unanimidad**; desacuerdo → UNKNOWN.
  Precisión (es el K=3 del gate).
- **Leads / marco → UNIÓN.** K llamadas con **framings distintos** (ángulos: ¿cuál es el cuello?
  ¿quiénes son los clientes? ¿qué lo mata? ¿qué hay upstream? ¿qué miraría un bajista?) y te
  quedás con **todos** los leads. Recall.

La memoria **genera qué ir a buscar** (nunca afirma un hecho); cada lead se **verifica contra la
fuente** (FTS + cita, §7). Un lead falso no cuesta nada (la búsqueda no encuentra); un fino que
*una* corrida olvidó, *otra* lo trae → **menos finos perdidos, sin riesgo de inventar** (un lead
no es un hecho, es un "andá a chequear esto"). Resuelve el miedo "la memoria se olvida algo y por
eso no lo buscamos".
- En `opus-4-8` (sin `temperature`) la diversidad sale de los **framings**, no de re-samplear.
- Costo acotado: **loop-until-dry** — pedís ángulos hasta 2 rondas sin leads nuevos. Una vez por
  nombre, al entrar a deep research.
- Ubicación: corre **antes** del extractor; su salida son las queries/preguntas que alimentan el
  retrieval dirigido (§7).

## 8. El mapa de cuellos
- **`grafo_produccion` vs `grafo_candidatos`.** El LLM **actualiza estado**, **extrae
  evidencia de relación**, y **propone** nodos/aristas → entran a *candidatos*. Se **promueven**
  a producción con relación comercial/técnica/contractual **fundada**. Topología base =
  **brújula** (fechada, con provenance, look-ahead del operador **reconocido y medido**) **∪**
  aristas de **customer-concentration** (clientes >10% = disclosure obligatoria, citable). **El
  LLM llena estado, jamás estructura.**
- **Regla de apertura de nodo: NÚMERO + unidad + fecha** (lead-time en semanas, take-or-pay en
  $, % capacidad vendida, backlog en meses, % de suba de precio). El lenguaje cualitativo de
  escasez **nunca abre** un nodo; solo **sostiene** uno abierto.
- **Fuentes por señal COSTOSA** (no por tier de documento; preferí la **contraparte** sobre el
  beneficiario): **A** contrato/take-or-pay/precio realizado/capacidad vendida → puede
  confirmar · **B** disclosure cuantificado de management → requiere corroboración · **C**
  narrativo/risk factor → solo discovery · **D** prensa/research → solo lleva a la fuente
  original. Triangulación fuerte = **dos lados de la cadena** (proveedor "capacidad agotada" +
  cliente "lead-times extendidos por el mismo insumo").
- **Falsificadores fundados:** el LLM nombra la **variable** falsificadora; el **threshold**
  sale de **fórmula determinista sobre hechos citados** (ej.: capacidad incremental / déficit
  ≥ 1, ambos citados). Sin threshold fundado → **hipótesis cualitativa**, no trigger operativo.
- **Delta de evidencia (la señal real):** no *"¿hay shortage?"* (estático, probablemente
  priceado) sino *"¿qué **cambió** vs. la versión anterior?"* (lead-time 12→20 sem, primera
  aparición de take-or-pay, backlog creciendo más rápido que capacidad). **El diff entre
  accessions ES la señal**, no solo auditoría. `first_seen` por hecho. Tipos de diff:
  `ADDED · REMOVED · VALUE_CHANGED · SUPPORT_CHANGED · CONFIRMED_AGAIN · EXPIRED · CONFLICT`.
- **Atención/consenso = SEGUNDO eje** (no se penaliza la evidencia): `fuerza_de_evidencia ×
  densidad_de_consenso`. **Test del ETF** = *input* de densidad (existe ETF del nodo → alta
  densidad), **no** bloqueo. Nodos muy atendidos: exigir **mayor delta**, monetización más
  clara, **menor tamaño máximo**, no abrir por narrativa sola, y **cola de discovery separada a
  proveedores de 2º/3º orden**. Además: la fecha de la evidencia que abre debería **preceder**
  al pico de atención.

## 8bis. Estándar de "demanda/continuidad confirmada" (post-triangulación, doc 23)
Caso testigo: AAOI/Amazon (Transaction Agreement con volumen **redactado** + warrant + FAB4). Dos
IA convergieron salvo el crux, resuelto acá. **Toca el gate → 🔒 requiere OK.**

> **⚠️ CORREGIDO por la revisión del conjunto (doc 25):** VALIDATED/COMMITTED/REALIZED es
> **madurez**, NO magnitud. Se separan `demand_exists` · `demand_continuity` ·
> `evidence_maturity_tier` · `materiality` (determinista, UNKNOWN→ceiling). Ver `init_docs/25` §0-2.

**La EXISTENCIA abre; la MAGNITUD gobierna el sizing (no el pasa/no-pasa).**
- Una redacción bajo Reg S-K 601(b)(10)(iv) **no es ausencia de evidencia** — es evidencia de
  altísima calidad con un campo tapado (el emisor le representó a la SEC que es material).
  Aplicarle la regla anti-alucinación ("número público o no abre") es **error de categoría** y
  genera **selección adversa**: un press release *"pipeline $500M"* (barato, no vinculante)
  pasaría y un acuerdo vinculante con Amazon no. En nuestro universo, **la señal cara ES el edge**.
- Por eso: la **existencia** (contraparte nombrada + exhibit material bajo certificación 302/906)
  **abre** el nodo. La **magnitud** entra como **tier ordinal** que fija el cap:
  - **VALIDATED** (relación real, magnitud UNKNOWN) → abre con el **cap más duro**.
  - **COMMITTED** (obligación ejecutable / mínimo / take-or-pay / backlog no cancelable, con plazo) → cap mayor.
  - **REALIZED** (compras/revenue observados y **repetidos**) → cap mayor.
- **Falsificador FECHADO** resuelve promesa→realización sin juicio: p.ej. *"Amazon debe aparecer
  como cliente >10% (ASC 280) en N trimestres; si no → salida determinista"*. No se baja la vara:
  se **corre en el tiempo** con vencimiento.
- **El número redactado suele ser DERIVABLE:** los thresholds de vesting sobreviven la redacción
  (deben ser objetivamente determinables + el equity se registra). AAOI: el warrant vestea con
  compras acumuladas hasta $4bn → **las compras reales de Amazon se despejan del vesting disclosed
  cada trimestre** (UNKNOWN → cuantificable). También: concentración >10% (ASC 280), RPO (ASC 606),
  contra-revenue del warrant (ASC 718/606) publican el volumen realizado con lag.

**Demanda y dilución: un hecho, dos campos — NO netear.**
- `demand_existence` y `dilution_overhang` **separados**; netearlos en un score destruye info.
- La dilución es **contingente y correlacionada** (los warrants vestean solo si la demanda se
  materializa) → el **bull case se modela YA DILUIDO** (tramos veteados). Modelar el bull sin
  dilución = escenario **imposible**. No es un haircut genérico de CRR.
- **Signo del warrant (invertido — lo tenía al revés):** el **proveedor le paga al cliente**
  (AAOI→Amazon) como rebate por volumen → señal de **asimetría de poder de negociación** →
  predictor de **compresión de margen**. El warrant cuantifica **incentivo + dilución, no
  demanda**. Registrar: `purchase_ceiling_for_full_vesting`, `customer_incentive_fv`,
  `volume_linked_incentive_fv`, `max_warrant_dilution_fd`, `binding_purchase_minimum=UNKNOWN`.
  Nunca un "demand score" del warrant.
- **Trap de contra-revenue (crítico):** el warrant se reconoce como **reducción de revenue** a
  medida que Amazon compra → **revenue y gross margin CAEN por éxito**. El sistema **no debe leer
  esa caída como deterioro** (cortaría la posición justo cuando funciona). La caída atribuible a
  contra-revenue se separa de la erosión competitiva.
- **Prohibido en valuación:** el techo ($4bn) NO entra en bull/base/backlog — solo como *"purchase
  level required for full vesting"*.

**Capacidad ≠ demanda; y el cuello es de la INDUSTRIA, no de la empresa.**
- FAB4 (capex $94.1M) es `company_capacity_execution` (alcista para AAOI), **separado** de
  `bottleneck_persistence` (propiedad de la industria). Un proveedor expandiendo dentro de un
  cuello que aún no puede servir es alcista para el proveedor, **neutro para el nodo**.
- Falsificador del nodo = **adiciones AGREGADAS del set de competidores nombrados** (el FTS lo
  hace bien), no de uno. **Lag** anuncio→online 18-36m: guardar `capacity_online_estimate` y
  **decaer la durabilidad desde esa fecha, no desde el anuncio**. La **granularidad del nodo**
  define si es contestable (definir nodos angostos).

**PM: se limita el TIPO de enunciado, no el entusiasmo.**
- **Puede:** rankear, elegir, asignar dentro del cap, ponderación cualitativa, convicción ordinal.
- **No puede:** rellenar un campo redactado con estimación (redactado = UNKNOWN **también** en su
  razonamiento), convertir ausencia de evidencia en evidencia, relajar sus triggers post-entrada
  (write-once), re-abrir un gate cerrado.
- **Enforcement barato:** todo numeral del output del PM debe resolver a un `evidence_id` o se
  rechaza el output (se policían **números**, no adjetivos). Cada creencia se escribe como
  **falsificador fechado** (*"espero Amazon >10% en el 10-Q de Q_; si no, salgo"*).

## 9. Universo (decisión del operador + el puente)
Cuello **real** incluido **no-US**, gated por **calidad de evidencia**. **Puente:** el cuello
no-US que no filea en SEC se **ve por las disclosures de sus clientes US** (costly-signal +
customer-concentration). **La tesis del NODO puede salir de un filer US; la POSICIÓN puede ser
el nombre no-US** (bróker opera afuera).
- **Arquitectura de embudo:** screen **ANCHO y barato determinista** (cientos de nombres,
  XBRL + disclosures estructuradas, sin LLM) → deep research **ANGOSTO** (20-40 con LLM
  profundo). No angosto-y-profundo desde el vamos.
- **🔓 ABIERTO (para resolver):** estándar de evidencia para la **FICHA del nombre no-US** —
  EDGAR no aplica → EDINET (JP) / filings EU, **diferido**. **MVP:** posiciones donde la ficha
  es analizable (US-listed / ADR); los nombres no-US se **trackean** (tesis del nodo) pero la
  **ejecución se difiere** hasta tener retrieval no-US. El modelo de hecho (§4) es
  jurisdicción-agnóstico; solo falta la capa de retrieval no-SEC.

## 10. Cómo se mide el edge (no se prueba arreglando el extractor)
**Grounding → Novedad → Alpha**, en ese orden. Batería (toda barata):
- **A. Validez fundamental:** post-detección, ¿subieron revenue/margen/backlog/precio
  realizado? ¿se materializó el contrato? ¿se retrasó la capacidad? (detectó una realidad).
- **B. Lead-time de descubrimiento:** fechas de {primera evidencia · señal del sistema ·
  confirmación posterior · reacción de mercado/estimaciones}. **Mediana ≤ 0 = somos seguidores.**
- **C. Alpha incremental** vs. baseline sectorial **controlando momentum, tamaño, sector,
  liquidez, quality**. La pregunta no es correlación con momentum, sino capacidad predictiva
  *después* de momentum.
- **D. ABLATION (el test honesto):** motor de cadena completo vs. (a) keyword-search simple
  ("shortage"/"capacity constrained"/"lead times") vs. (b) momentum/earnings-revisions. **Si
  el motor complejo no supera al lexical, la "inteligencia de cadena" no aporta edge.**
- **No hay backtest honesto** (look-ahead de training) → **forward paper con log sellado**.
- **Afirmación falsable, escrita HOY:** *"nuestro edge es cobertura y linkage, no velocidad"*
  — la mata un **lead-time mediano ≤ 0 a los 12 meses**. Mismo estándar de falsificación que le
  exigimos a cada nodo.

## 11. Cartera (caps)
**Máx 2 nombres activos por nodo** (tope de conteo) **+ cap de % de cartera por nodo** (el que
hace el trabajo) **+ anti-doble-conteo** (una empresa en 3 nodos correlacionados **no** son 3
tesis). Meta: cap por **contribución de riesgo** a nivel nodo.

## 11bis. Arquitectura mínima del MVP (8 componentes — no es un sistema enorme)
La prueba de que es **implementable, no una nube**: el MVP concreto son 8 piezas acotadas.
| | Componente | Qué hace |
|---|---|---|
| **A** | Manifest de documentos por CIK | accession · form · accepted_at · period_end · exhibits · hash |
| **B** | Chunking determinista | `chunk_id` estable + texto completo (nunca truncado en silencio) |
| **C** | Registry de `fact_key` | fuentes permitidas · queries · tipo de valor · regla de aceptación |
| **D** | Extractor | value + quote exacta + accession + período + support_type |
| **E** | Verificador | offsets/substrings + números vs XBRL + regla de campo |
| **F** | Fact store inmutable | hechos históricos + versiones del extractor |
| **G** | Snapshot compiler | vigencia fact-level + 8-K posteriores + supersesiones |
| **H** | Motor determinista | usa SOLO DIRECT y DERIVED |

**Cuatro tests que cierran el sistema:** **Stability** (mismas evidencias → mismos facts) ·
**Grounding** (cero hechos positivos de hard gate sin soporte) · **Recall** (contra el gold
set etiquetado) · **Edge** (señales point-in-time vs. baselines y fundamentals/retornos futuros).
Nota: la mitad de estas piezas ya existen a medias en el código (edgar, ledger `nx_hecho`/
`nx_ficha_version`, gate determinista). El retrieval de texto **está probado y anda hoy**.

## 12. Plan de ejecución
**P0 — días, independiente del modelo:**
- **Gold set** de 30-50 hechos etiquetados a mano sobre 5-10 filings + **harness
  precisión/recall** (sin esto, no sabemos si algo mejora).
- **Auditoría de sensibilidad del gate** (por candidata, qué input único voltea la decisión).
- **🔒 K=3 unanimidad** en booleanos gate-críticos (desacuerdo → UNKNOWN).
- **🔒 Estados ricos / NO_EVALUABLE** (§3) — tercer/cuarto estado del gate.
- **Regla derivar-antes-de-extraer** (§2).

**P1 — semanas:** retrieval point-in-time (`primary_doc` + exhibits) · seccionado/chunk ·
extracción con quote literal · verificación substring+offset + support-type · snapshot compiler
· publicación atómica · invalidación por fact-type/cadencia · provenance de modelo ·
**capa generadora** (§7bis: leads por unión, framings diversos, loop-until-dry).

**P1-gate 🔒 (requiere OK) — estándar de demanda (§8bis):** existencia-abre + tier de magnitud
(VALIDATED/COMMITTED/REALIZED) + falsificador fechado + `demand_existence`/`dilution_overhang`
separados + bull modelado ya diluido + trap de contra-revenue + PM con `evidence_id`.

**P2:** eje de atención (2 ejes + test del ETF) · lead-time de descubrimiento · grafo de cadena
desde customer-concentration · motor de delta de evidencia (first-seen) · falsificador de
capacidad **agregado con lag** (§8bis: `capacity_online_estimate`).

## 13. Finos abiertos
- Estándar de evidencia para la **ficha no-US** (§9).
- Catálogo canónico de `fact_key` y umbrales de `support_type` (se calibra con el gold set).
- Diseño exacto del **snapshot compiler** y de la publicación atómica sobre el ledger actual.
- `N` de trimestres del **falsificador de realización** y cortes de los **tiers de magnitud** → caps (§8bis).
- **Framings y K** de la capa generadora (§7bis) — se tunean midiendo recall de leads.

---
**🔒 = requiere tu OK antes de codear** (toca lógica de decisión). Todo lo demás (gold set,
retrieval, verificación) es integridad/infra y puede arrancar. El gold set del P0 no tiene
lógica de decisión: es etiquetado + medición.
