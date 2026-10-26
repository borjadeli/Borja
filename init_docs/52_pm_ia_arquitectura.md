# 52 — BORJA v2: arquitectura del PM de IA multiagente (entregable FASE 0)

> **Estado: FASE 0 — PLAN, SIN CÓDIGO.** Entregable pedido por el doc 51 §6. Define arquitectura detallada,
> schemas de salida de cada agente, flujo semanal y por evento, IPS propuesto, presupuesto semanal, mapa de
> módulos (conservar/retirar/traer) con rutas, y riesgos. Cierra con las preguntas del §7 (doc 51) que el
> operador debe responder **antes** de arrancar Fase 1. Fecha: 2026-10-26.
>
> Directiva fundacional: doc 51. Este doc es su plan de ejecución.

---

## 0. Verificación de los hallazgos de la auditoría (§5 del doc 51) — TODOS reproducen

| # | Hallazgo | Veredicto | Evidencia verificada en el código |
|---|---|---|---|
| 1 | Dos núcleos; el paper decide por Quality×Asimetría | **CONFIRMADO** | `paper_trader.py:126,142` llama `flujo.evaluar_empresa`; `prompts/extractor_hechos_v2.txt:72` dice literal *"NO SEAS TÍMIDO"*; el PM solo alimenta `pm_t` (banda) |
| 2 | BUG: base PM = `CAP_FLOOR_BURN`=4% < `PISO_POSICION`=5% → se descarta en silencio | **CONFIRMADO, reproducible** | `flujo_pm.py:26` `base=round(min(CAP_FLOOR_BURN,techo))`, `CAP_FLOOR_BURN=0.04` (`politica.py:198`); `sizing.py:75` devuelve `entra:False` si `<0.05` (`constantes.py:24`); `paper_trader.py:311-313` `s=sizing_final(...)` → `if not s["entra"]: continue` (drop mudo, sin registro) |
| 3 | Mapa vacío → contexto del PM degrada a `{}` | **CONFIRMADO** | filas: `nx_nodo=0`, `nx_empresa_nodo=0`, `nx_empresa=0`; `flujo_pm.py:42-54` degrada a `{}` by design |
| 4 | Docs viejos (CLAUDE/CONTEXT/doc32) | **CONFIRMADO** | doc 32 fechado 2026-09-07 (previo al doc 49 y al destete del 2026-09-16) |
| 5 | Doc 49 (n=3, ciberseguridad) = hipótesis | **De acuerdo** | n=3, un solo vertical; Fase 5 lo amplía con el duelo de 25 nombres |
| 6 | Track record del paper = núcleo v3 | **CONFIRMADO** | `libro.json` lo maneja el camino `evaluar_empresa`; hay que congelarlo antes del libro v2 |

> El bug #2 ya causa **silenciosamente** que toda decisión del PM a 4% (su base) nunca se ejecute en el
> paper: hoy el PM "decide" pero el sizing lo tira. Desaparece al retirar `sizing_final` del camino (Fase 1),
> pero exige el test de regresión del §5.2 ("ninguna decisión del PM se descarta sin registro").

---

## 1. Principio rector de v2

> **El determinismo informa y limita; la IA decide.** Datos, cálculos, detección de eventos, presupuesto y
> los límites del IPS son deterministas. Qué comprar/vender, cuánto y cuándo lo deciden agentes LLM, con el
> PM como decisor final y un auditor independiente que lo cuestiona. **El determinismo NO elige nombres ni
> tamaños.**

Esto invierte la premisa de los docs 33/39/49 en *quién decide* (de "determinista decide + LLM trae hechos" a
"LLM decide + determinista informa/limita"), pero **conserva todo su trabajo intelectual** (owner-FCF,
dilución, reverse-DCF/T*, burden, arquetipos, falsadores, anti-anchoring) como **herramientas que reciben los
agentes**.

---

## 2. Arquitectura en 5 capas (detalle)

### Capa A — Datos y calculadoras (determinista, informa)
Reusa el motor de evidencia actual. Produce un **data pack** por empresa: cada número con `fuente`,
`known_at` y `tipo ∈ {original, derivado, estimación, interpretación}` (contrato = `provenance.DataPoint`,
trasplantado del Sistema Quant). Calculadoras conservadas: owner-FCF, dilución 24m/3y, runway, CRR, g_D,
reverse-DCF/T*, reverse-burden; arquetipo/ruteo degradados a **etiqueta descriptiva**. El data pack es
**input**, nunca veredicto ni ranking → anti-anchoring: los agentes ven cálculos, no "la opinión del sistema".

### Capa B — IPS (en código, único lugar donde el código manda)
`config/ips.yaml` versionado + hash. Valida toda propuesta del PM; si viola, **rechaza y devuelve con motivo**
(nunca corrige en silencio). Cubre: máx. posiciones, peso máx./nombre, máx./sector, máx./cuello, rango de
market cap, ADV mínimo, tamaño máx. como % ADV, caja mín./máx., máx. operaciones/semana, presupuesto LLM,
prohibición de órdenes reales. Ver §4 para los valores propuestos.

### Capa C — Agentes (razonan y deciden)
8 agentes (detalle y schemas en §3). Contrato común: prompt versionado en `prompts/`, salida pydantic
validada, costo/tokens registrados, fuentes citadas. Reglas comunes adaptadas de `_common.md` del Sistema
Quant. Orden del comité: Macro → Triage → (Analista ⇄ Bear) → Verificador → PM ⇄ Auditor.

### Capa D — Monitoreo por eventos (determinismo detecta, PM decide)
Disparadores deterministas: filings (8-K, 10-Q/K, Form 4), precio sobre umbral, red flags extraídas,
falsadores que vencen, alertas de las 5 vías de `salida.py`. Cada disparo abre una **revisión** del nombre
(Analista + Verificador + PM). **Las 5 vías pasan de venta automática a ALERTA.** Lo único que opera solo es
el IPS (p.ej. recortar lo que superó peso_máx + banda).

### Capa E — Ledger y evaluación
Ledger append-only: cada decisión con memo, falsador, hash del dossier, versiones de prompts/modelos, hash
del IPS, precio, timestamp. Métricas: hit-rate de falsadores, Brier (calibración de convicción), P&L vs
benchmarks. **Carteras sombra desde día 1:** (a) equal-weight del universo elegible; (b) "Opus+web solo"
(un agente, sin pipeline); (c) ETFs temáticos (SMH/URA/ITA/COPX). Sin esto no sabemos si el pipeline agrega.

---

## 3. Schemas de salida por agente (borrador, se cierran en Fase 3)

> Pydantic. Campos comunes a todos: `agent`, `prompt_version`, `model`, `cost_usd`, `tokens`, `created_at`,
> `sources: list[Source]` (cada `Source` = `{url|fact_key, quote, known_at}`).

**1. MacroMemo** — `ciclo_capex_ia`, `energia`, `commodities`, `tasas` (cada uno: estado + dirección +
evidencia); `cuellos_prioridad: list[{cuello, prioridad_0_3, delta_vs_anterior, razon}]`; `resumen`.

**2. MapCuratorOutput** — `nodos_actualizados: list[NodoDelta]`; `propuestas_empresa: list[{ticker, cuello,
tesis_corta, market_cap, por_que_ahora, fuentes}]` → van a cola de aprobación (no entran solas).

**3. TriageDecision** (por nombre) — `ticker`, `prioridad_0_3`, `incertidumbre_0_1` (valor de la
información), `motivo`, `research_profundo: bool`. Posiciones en cartera y nombres con evento → `True`
siempre. El código solo corta por presupuesto.

**4. Dossier** (Analista) — `ticker`; `negocio_y_posicion_cuello`; `demanda: list[{afirmacion, citas}]`;
`valuacion: {que_exige_el_precio, T_estrella, burden, supuestos_explicitos}`; `bull: Escenario`;
`bear: Escenario` (independientes); `catalizadores: list[{evento, fecha_esperada}]`;
`red_flags: list[{tipo, severidad, cita}]`; `falsador: {afirmacion, fecha_limite, que_lo_mataria}`;
`conviccion_0_1`. **Sin price targets libres**: todo escenario explicita supuestos y los contrasta con las
calculadoras.

**5. BearAttack** — `objeciones: list[{afirmacion_atacada, contraevidencia, citas, severidad}]`;
`replica_analista: str` (una sola vuelta).

**6. VerificationReport** — `checks: list[{afirmacion, fuente_ok: bool, fecha_ok: bool,
es_declaracion_corporativa: bool, consistente_con_numeros: bool, motivo}]`; `veredicto ∈ {pass, fail}`.
Un `fail` **no puede** justificar compra ni aumento.

**7. PMDecision** (por nombre y a nivel cartera) — `acciones: list[{ticker, accion ∈
{comprar, vender, recortar, aumentar, mantener, caja}, peso_objetivo, por_que_ese_tamaño, tesis,
falsador: {afirmacion, fecha}, que_me_haria_vender, dossier_hash}]`; `operar_ahora: bool`;
`razon_timing`. Puede quedarse 100% en caja.

**8. AuditReport** — `objeciones: list[{tipo ∈ {concentracion, coherencia_memo_peso, rotacion,
verificacion_fallida, violacion_ips}, detalle, severidad}]`; `devuelve_al_pm: bool` (máx. 1 vez);
`replica_pm: str`; `decision_final` + objeciones registradas juntas.

---

## 4. IPS propuesto (defaults — a confirmar por el operador, §7)

> Derivados de la cartera actual (máx 12 posiciones, caps por sector) y del universo small/mid cap. Son
> **defaults razonados**; el operador fija los definitivos.

| Parámetro | Default propuesto | Alternativa / nota |
|---|---|---|
| Máx. posiciones | 12 | (hoy el sistema usa 12; AI Finance Labs ~15-20) |
| Peso máx. por nombre | **20%** (operador, 2026-10-26) | el PM sizea libre bajo el tope; sin piso inviolable |
| Máx. por sector | 30% | evita "10 nombres = 1 apuesta al capex IA" |
| Máx. por cuello de botella | 35% | requiere el mapa poblado (Fase 2) |
| Rango de market cap | **$150M – $60B** (operador, 2026-10-26) | techo subido a $60B; incluye mid/large de industrias del futuro |
| ADV mínimo (liquidez) | $3M/día | tamaño máx. posición ≤ 10% del ADV |
| Caja mínima / máxima | 0% / 100% | el PM puede ir full-cash (disciplina sobre actividad) |
| Máx. operaciones/semana | 2 | igual que AI Finance Labs |
| Presupuesto LLM/mes | **PENDIENTE §7** | condiciona cuántos nombres van al Analista caro |
| Órdenes reales | PROHIBIDAS | paper únicamente, sin broker con escritura |

**Red flags de supervivencia** (going concern / material weakness / restatement): **DECIDIDO (operador,
2026-10-26) = alerta que el PM resuelve por escrito con OK del verificador** (no bloqueo duro). Abre revisión;
el PM debe justificar por escrito y el verificador debe dar pass para comprometer o aumentar capital.

---

## 5. Flujos

### Flujo SEMANAL (revisión programada)
1. **Macro** (Opus+web) → memo + prioridades de cuello.
2. **Map Curator + Discovery** (Sonnet+web, quincenal) → propuestas a la cola de aprobación.
3. **Triage** (Haiku/Sonnet) sobre todo el universo → selecciona los N que van a research profundo
   (posiciones + eventos entran siempre; el resto por prioridad×incertidumbre hasta agotar presupuesto).
4. Por cada seleccionado: **Analista** (Opus+web) → Dossier; **Bear** (Sonnet/Opus+web) ataca; Analista
   replica una vez; **Verificador** emite pass/fail.
5. **PM** (Opus) ve dossiers vigentes (solo pass), cartera, memo, IPS, su hit-rate → propone.
6. **Auditor** (Opus, contexto separado) revisa; puede devolver 1 vez; PM replica; decisión final.
7. **IPS** valida; si viola, rechaza y devuelve con motivo.
8. Decisión → ledger → paper → dashboard.

### Flujo por EVENTO (asíncrono)
Disparador determinista (filing/precio/red-flag/falsador-vence/vía de salida) → abre revisión del nombre →
Analista (refresco dirigido) + Verificador + PM (decisión acotada a ese nombre) → Auditor solo si cambia
peso material → IPS → ledger → paper. Tope de operaciones semanal sigue vigente.

---

## 6. Presupuesto estimado por semana (precios 5.5 reales)

> Ancla de costo medida en BORJA (doc 49): Analista Opus+web ≈ **$1.40/nombre**, Haiku ≈ **$0.02/nombre**.
> Con Opus 5.5 ($4/$20, más barato que el 4.8 con que se midió) + las dos palancas de abajo, el costo del
> Analista baja respecto a ese ancla. **El Triage + el presupuesto del IPS son la válvula central.**

**Conteo por capa (DECIDIDO con el operador, 2026-10-26):**
- **Triage:** corre sobre **todo el universo elegible** (~50 hoy; hasta ~200 tras importar el Sistema Quant).
  Modelo Haiku 5.5, ~$0.02/nombre.
- **Análisis profundo (Analista+Bear+Verificador):** **~8 nombres/semana** con todas las capas llenas
  (posiciones en cartera + nombres con evento entran siempre; el resto por prioridad×incertidumbre hasta
  agotar presupuesto). El código solo hace cumplir el tope.

| Agente | Modelo | Frecuencia | Nombres | $/sem aprox |
|---|---|---|---|---|
| Triage | Haiku 5.5 | semanal | universo (~50–200) | ~$1–4 |
| Analista | Opus 5.5 + web | semanal | ~8 | ~$10 |
| Bear | Sonnet 5.5 + web | semanal | ~8 | ~$5 |
| Verificador | Sonnet 5.5 | semanal | ~8 | ~$2 |
| Macro | Opus 5.5 + web | semanal | 1 | ~$1.5 |
| Map Curator+Discovery | Sonnet 5.5 + web | quincenal | — | ~$1 |
| PM + Auditor | Opus 5.5 | semanal | 1 cartera c/u | ~$3 |

- Capas llenas (~8 profundos): **≈ $25–40/semana** antes de palancas. Coincide con la estimación externa.
- **Dos palancas que lo bajan fuerte (ambas confirmadas en la doc oficial):**
  1. **Batch API: −50%** en todo lo no urgente (triage, re-extracción, análisis no disparado por evento).
  2. **Prompt caching:** la parte común de cada pedido (reglas del IPS, mapa, memo macro, rúbrica) se cachea;
     las lecturas cuestan **5% del precio de input en Opus 5.5 y Sonnet 5.5** (2.5% en Fable 5.1). Los dos
     descuentos **se suman**.
  3. **Reutilización por hash:** la mayoría de las empresas no cambian semana a semana → no se re-analizan.
- Con batch + caché + reutilización, un régimen de ~8 profundos cae cómodamente a **~$15–25/semana**.
→ El operador fija un **techo mensual**; el código deriva el N máximo y lo hace cumplir (freno duro del IPS).

### Re-análisis de un nombre (DECIDIDO) — Capa D
Un nombre se vuelve a analizar cuando: (a) es **posición en cartera** (entra siempre al ciclo semanal);
(b) **dispara un evento** (filing 8-K/10-Q/K/Form 4, precio sobre umbral, red flag extraída, **falsador que
vence**, o una de las 5 vías de `salida.py`); (c) el Triage lo promueve por prioridad×incertidumbre. Si nada
cambió y hay dossier vigente verificado, **se reutiliza** (no se re-gasta LLM).

---

## 7. Mapa de módulos (conservar / retirar / traer) con rutas

### CONSERVAR (se reusan tal cual o como librería)
- `backend/services/edgar.py`, `market_data.py`, `precio_base.py`
- `backend/nucleo/fact_store.py`, `extractor_citado.py`, `retrieval.py`, `gold_retrieval.py`, `fact_keys.py`
- Calculadoras: `valuacion_reverse.py`, `crecimiento.py`, `pre_revenue.py`, `dilucion.py`,
  `capital_raise_risk.py`, y `sizing_burden.py` **como lectura** (no como cap duro)
- De `juicio_llm.py`: bull/bear independientes, falsador, fuentes, anti-anchoring (se reencarnan en el
  Analista)
- `ledger_juicio.py`, `registro_decisiones.py`, `seleccion/paper_pnl.py`, `scheduler.py`, `panic.py`,
  `ui.py`+templates, `auth.py`, `consola.py`

### RETIRAR DEL CAMINO DE DECISIÓN → `backend/_archivo/` (no borrar hasta cerrar Fase 2)
- `nucleo/flujo.py` (`evaluar_empresa`, `armar_cartera` — Quality×Asimetría con bull/bear de precio del LLM)
- `nucleo/selector.py`; `sizing.py:sizing_final` (el del `PISO_POSICION` — **causa del bug #2**);
  `cartera_celdas.py`, `carril.py`, `escalera.py`; `seleccion/challenger.py`
- La banda `[piso, techo]` como techo inviolable (el PM sizea libre bajo el IPS)
- Huérfanos sin caller: `mapa/discovery.py` (→ reemplaza el del Sistema Quant), `seleccion/sparring.py`
  (→ bear + auditor), `backend/pipeline.py`
- ⚠️ `paper_trader.py` NO se archiva: se **reescribe** para operar desde `PMDecision` (sin `sizing_final`,
  sin normalización por mérito). Es el cambio central de Fase 4.
- ⚠️ `prompts/extractor_hechos_v2.txt` "NO SEAS TÍMIDO": el extractor deja de producir bull/bear de precio;
  el Analista los produce con supuestos explícitos. Revisar/retirar esa instrucción.
- ⛔ **APAGAR YA (acción de Fase 1, cuesta plata hoy):** el cron **`paper_pm`** (`scheduler.py`, dom 19:30 ET)
  corre `job_paper_pm` → `pm_run.correr(..., usar_web=True)` sobre **todo el universo vivo cada semana** con
  Opus+web (`jobs.py:24-43`). Es el gasto recurrente del sistema v3 y el bug #1/#2 combinados. **Desactivar
  `paper_pm` y el re-juicio por evento del v3 en Fase 1**, antes de construir el comité nuevo, para no pagar
  dos pipelines en paralelo. El `paper_reextraccion` (re-extrae hechos, dom 19:00) se conserva pero pasa a
  modo batch.

### TRAER DEL SISTEMA QUANT (adaptar + traer sus tests) — ⚠️ BLOQUEADO: repo no accesible (ver §9)
- Data: `data/map/industry_map.yaml`, `data/bottlenecks/`, `data/research/bottlenecks_evidence.json`,
  `data/universe/companies.yaml` (filtrar por rango de market cap del IPS; `search_summary` = no verificado)
- `agents/map_agents.py` + prompts map_curator/discovery + cola de propuestas
- Embudo/presupuesto: `funnel/pipeline.py` (promoción por valor de información, reutilización por hash,
  reserva para comité), `funnel/costs.py`, `agents/base.py`, `agents/llm.py` (pause_turn, errores, costo
  parcial)
- `agents/schemas.py` (modelo de salidas estructuradas), prompts bear/auditor/_common,
  `provenance.py` (DataPoint), patrón `ScriptedLLM` (tests sin API)

### NO TRAER
- `scoring/engine.py` (score compensatorio), `valuation/core.py` como motor de decisión (múltiplos de salida
  libres sin límite), el sesgo del L0 hacia large caps

---

## 8. Riesgos

1. **Costo descontrolado.** Opus+web agéntico es caro por diseño (doc 49). Mitigación: Triage + presupuesto
   del IPS como válvula dura; reutilización por hash; Bear/Verificador en modelos más chicos.
2. **Alucinación / cita falsa del Analista.** Mitigación: Verificador obligatorio (fail → no compra),
   contrato de procedencia, "declaración corporativa ≠ hecho". Es la salvaguarda más crítica.
3. **PM sobre-confiado o incoherente.** Mitigación: Auditor en contexto separado, falsadores fechados +
   Brier, ledger de hit-rate que el propio PM ve.
4. **Concentración oculta** (N nombres = 1 apuesta macro). Mitigación: caps por sector/cuello en el IPS +
   chequeo explícito del Auditor.
5. **Mapa vacío** (nx_nodo=0 hoy). Sin el Sistema Quant el contexto de cuello degrada a `{}`. → Fase 2
   bloqueada hasta acceso al repo.
6. **Pérdida del track record v3.** Se congela y archiva; el libro v2 arranca limpio en Fase 4 (los números
   no son comparables).
7. **Evaluación circular.** Si el mismo pipeline juzga su propio éxito, nos engañamos. Mitigación: carteras
   sombra (b) "Opus+web solo" y (c) ETFs desde día 1; el duelo de 25 nombres (Fase 5).
8. **Regresión silenciosa del bug #2.** Al reescribir el sizing, cualquier decisión del PM descartada debe
   quedar registrada (test de regresión obligatorio).
9. **Sin órdenes reales.** Riesgo operativo: que alguien conecte un broker con escritura. El IPS lo prohíbe
   explícitamente; no se integra ningún cliente de broker con permisos de escritura.

---

## 9. ✅ RESUELTO — repo Sistema-Quant accesible (clonado 2026-10-26)

`https://github.com/borjadeli/Sistema-Quant` es **público**; clonado en el scratchpad de la sesión
(solo lectura, fuera del árbol de BORJA). **Todas las piezas del §4 "traer" verificadas presentes:**
`docs/research/ai_finance_labs.md`, `src/qa/agents/{schemas,map_agents,base,llm}.py` + `prompts/_common.md`,
`src/qa/funnel/{pipeline,costs}.py`, `src/qa/provenance.py`, `data/map/industry_map.yaml`,
`data/universe/companies.yaml` (~246 empresas), `data/bottlenecks/`, `data/research/bottlenecks_evidence.json`.

Estructura relevante del repo (`src/qa/`): `agents/`, `funnel/`, `scoring/engine.py` (**NO traer**),
`valuation/core.py` (**NO traer como decisor**), `providers/{yahoo,sec_edgar,manual}.py`, `portfolio/`,
`universe/`, `map/`, `fundamentals/`, `feed/events.py`, `db/`, `options/`, `provenance.py`.

→ Fase 2 y las piezas "traer" de Fase 3 **desbloqueadas**. En Fase 1/2 se definirá si se clona de forma
persistente en el server (p.ej. `/opt/Sistema-Quant`) para que el import sea reproducible fuera de esta sesión.

---

## 10. Decisiones del operador (§7 del doc 51)

### ✅ RESUELTAS (2026-10-26)
- **Red flags de supervivencia:** alerta que el PM resuelve por escrito con OK del verificador (no bloqueo
  duro). Ver §4.
- **Sistema-Quant:** repo público, clonado y verificado. Bloqueante levantado. Ver §9.
- **Ciberseguridad:** **no es un vertical central**; entra como parte del universo amplio junto a IA core,
  defensa, espacio, biotech, energía/nuclear, commodities/minerales, robótica. Las posiciones cyber actuales
  (NABL/S/TENB/VRNS/RBRK) no se expulsan por sector, pero no gozan de prioridad de vertical.
- **Modelos:** la familia **Claude 5.5 EXISTE** (verificado contra `/v1/models` en vivo + página oficial de
  pricing, 2026-10-26). Mi catálogo interno estaba cacheado al 2026-06-24 y no la tenía; el operador tenía
  razón. IDs y precios vigentes (base $/1M tok):

  | Modelo | ID | in/out | Default effort | Rol en el comité |
  |---|---|---|---|---|
  | Claude Opus 5.5 | `claude-opus-5-5` | **$4 / $20** | medium | **Analista, PM, Auditor, Macro** |
  | Claude Sonnet 5.5 | `claude-sonnet-5-5` | **$2 / $10** | high | **Bear, Verificador, Curator** |
  | Claude Haiku 5.5 | `claude-haiku-5-5` | **$0.10 / $0.50** | medium | **Triage** |
  | Claude Fable 5.1 | `claude-fable-5-1` | $10 / $50 | high | opción máx. capacidad para el Analista |

  Decisión: **modelo por agente configurable en `config/agentes.yaml`**, default a la familia 5.5 arriba.
  Nota oficial: la doc recomienda "empezar con Opus 5.5 para la mayoría de los workloads" → coincide con el
  rol de Analista/PM. ⚠️ **El SDK anthropic instalado es 0.39.0 — demasiado viejo para 5.5** (sin `.models`,
  sin adaptive thinking, sin helpers de batch/caché). **Upgrade del SDK = tarea de Fase 1/3.**

### ⏸️ PENDIENTES antes de Fase 1 (no arranco sin esto)
1. **IPS — confirmar o editar los defaults de §4:** máx. posiciones (12), peso máx./nombre (15%),
   máx./sector (30%), máx./cuello (35%), rango market cap ($150M–$20B), ADV mínimo ($3M; ≤10% ADV),
   caja (0–100%), máx. operaciones/semana (2).
2. **Presupuesto mensual de LLM** (define el N del Triage: ~$64/mes con N=4, ~$105/mes con N=8).
3. **Aprobación explícita para arrancar Fase 1** (consolidación: congelar paper v3, archivar camino v3,
   reescribir CLAUDE/CONTEXT/estado).

**Ambigüedades de diseño resueltas con default (§8, sigo salvo que bloquees):** schemas de §3 como borrador;
IPS de §4 como base; cadencia semanal fija + eventos con tope 2 ops/semana; carteras sombra (a)(b)(c) desde
día 1; el extractor deja de emitir bull/bear de precio (los produce el Analista con supuestos explícitos).
