# 50 — BORJA: resumen del sistema + detalle del código (para evaluación externa)

> **Propósito.** Documento autocontenido para que **otra IA (o revisor externo) evalúe el sistema sin
> acceso al repo.** Describe (a) qué es BORJA y su tesis, (b) el estado honesto en 3 niveles —
> *decidido / documentado / implementado en código* —, (c) el mapa completo del código módulo por módulo,
> (d) almacenamiento, automatización y dashboard, y (e) las decisiones abiertas donde más queremos criterio
> externo. **Fecha de corte: 2026-10-26.** La fuente de verdad son el código y los `init_docs/`; este doc orienta.
>
> **Aviso de honestidad (importante para el evaluador):** hay un *gap* real entre lo que está *decidido/escrito*
> y lo que está *corriendo en el código*. Lo marcamos explícitamente en cada punto con las etiquetas
> **[DECIDIDO]**, **[DOCUMENTADO]**, **[IMPLEMENTADO]**, **[PARCIAL]**, **[FALTA]**. No queremos que el evaluador
> confunda el diseño con la realidad del código.

---

## 1. Qué es BORJA

Sistema **quant** para analizar y operar **small & mid caps de "industrias del futuro"** (AI infra, energía/
nuclear, defensa, healthcare tech, robótica, fotónica, semis). Es a propósito el sector de **mayor riesgo**:
es donde un sistema disciplinado puede generar más diferencial (tesis **power-law**: pocos ganadores grandes
pagan muchos perdedores chicos).

- **Filosofía operativa:** *disciplina sobre actividad.* Se prefieren slots vacíos a forzar entradas; no se
  relajan umbrales sin evidencia documentada.
- **Modo de uso real:** el sistema es **ADVISORY** (asesor), no un fondo autónomo. El operador humano replica
  las propuestas a mano en su bróker. Hay un **paper trading** autónomo que valida el método con capital
  simulado ($100K base), pero no mueve dinero real.
- **Stack:** Python 3 · FastAPI (API + UI server-side Jinja2/Tailwind) · SQLite (SQLAlchemy) · APScheduler
  (cron) · Anthropic Claude SDK (el LLM) · yfinance + SEC EDGAR + RSS (datos). ~18.500 LOC de backend,
  ~4.400 LOC de tests (49 archivos de test).

### El edge (hipótesis central)
El edge **no** es la opinión del LLM. El edge es: **una IA procesa evidencia primaria fresca** (filings SEC,
datos de mercado, el "mapa de cuellos de botella" sectorial) de forma disciplinada y rastreable. El LLM
**trae hechos fechados y citados**; la decisión de capital la toma maquinaria **determinista**. (Ver §3 para
el matiz medido: dónde el determinismo suma y dónde el LLM es irreemplazable.)

---

## 2. Historia reciente y forma de trabajo

- **Migración completada (destete).** BORJA tuvo un **"sistema viejo"** (score 0-10 + pipeline de agentes
  tipo mesa de inversión) que **se borró del disco el 2026-09-16** (commits `destete B1..B4`). El **núcleo
  determinista nuevo** es ahora autosuficiente. ⚠️ Esto significa que `CLAUDE.md` y `CONTEXT.md` del repo
  **quedaron parcialmente viejos** (describen la convivencia viejo/nuevo que ya no existe).
- **Método de trabajo:** nada de código sin esquema cerrado; las decisiones de método se **triangulan** (se
  le pide a 2+ IAs que converjan) y recién después se codea. Por eso hay muchos `init_docs/` de triangulación.
- **Mapa de documentos:** `init_docs/00_MAPA_DOCUMENTOS.md` dice qué está vigente. Canónicos vivos:
  **32** (estado+plan), **33** (método), **14** (pendientes), **39** (paradigma determinismo↔juicio),
  **46** (escalera add-on), **47** (sizing burden), **49** (ablation del PM). ⚠️ **El doc 32 es del 2026-09-07
  y no incorporó la conclusión del doc 49 (2026-09-21)** — ver §3.

---

## 3. ⭐ El hallazgo clave (y el gap que queremos que evalúes): determinismo vs. LLM

Esta es **la decisión de método más importante y la que más nos interesa que un tercero cuestione.**

### 3.1 El experimento (doc 49 — `ops/ablation_pm.py`) **[DOCUMENTADO, medido]**
Surgió la duda: *¿el núcleo determinista aporta algo al análisis, o el LLM solo lo hace mejor/más barato?*
Se midió (no se especuló) sobre 3 nombres (RBRK/VRNS/NABL):

| Config | RBRK | VRNS | NABL | $/nombre |
|---|---|---|---|---|
| **Opus + web** (el PM investiga agénticamente) | PRIORITY_MED | PRIORITY_MED | **VETO** | ~$1.40 |
| Opus **sin web** (solo nuestros fundamentals) | PASS | PASS | PASS | ~$0.15 |
| Haiku + web | PRIORITY_MED | PASS | PASS | ~$0.08 |
| **gather→judge** (Haiku junta hechos citados → Opus juzga sin web) | PASS | PASS | PASS | ~$0.25 |

**Conclusión (nítida):** el valor **no** es "tener hechos web"; es que **Opus investigue AGÉNTICAMENTE**
(formula la búsqueda, lee, sigue el hilo, razona *mientras* busca). **Todos los atajos colapsan a PASS** y se
pierden los juicios finos (VRNS: su `g_D=2.9%` era un artefacto contable; NABL: material weakness declarada).
El razonamiento-durante-la-búsqueda **es** el producto; no se decodifica en un pipeline barato. El costo
(~$1.40/nombre) es intrínseco al mecanismo.

### 3.2 La decisión arquitectónica **[DECIDIDO, no implementado]**
> **¿El determinismo suma? SÍ como *límites + triage*; NO como *análisis* (ahí duplica al LLM).**

El determinista deja de ser "un segundo analista" y se queda con dos funciones donde el LLM no sirve:
1. **Límites (gratis, sin LLM):** `cap = min(arquetipo, tier, valuación)`, veto de supervivencia, banda
   `[piso, techo]`, caps de sector/cluster. Es el **ancla anti-hype**.
2. **Triage:** decidir qué **pocos** nombres (~3-4/semana) merecen el Opus+web caro; el resto los cierra el
   determinista solo (veto→0, carril→base-rate, COVERED-en-piso-sin-upside→despliega el piso) **sin llamar al
   PM**. Esto bajaría el costo de ~$17/sem a ~$5/sem sin perder edge.

Esto encastra con el **paradigma del doc 39 ("sándwich"):** determinismo para *hechos/límites/disciplina* +
juicio LLM acotado para *el futuro*.

### 3.3 ⚠️ El GAP entre lo decidido y lo que corre hoy
- **[FALTA] El triage NO está implementado.** El job `job_paper_pm` (`backend/seleccion/jobs.py:24`) corre
  Opus+web sobre **todo el universo vivo** (`tickers_vivos()`), no sobre ~3-4 nombres. O sea: hoy el código
  gasta el costo que el doc 49 dijo evitar. No existe ningún gate que decida "este lo cierra el determinista,
  este va al analista caro".
- **[FALTA] El doc 32 (estado vivo) quedó viejo:** es anterior al doc 49, su etapa 5 todavía dice "PARCIAL,
  desenchufado" y no menciona la conclusión triage/analista.
- **[ABIERTO] Sub-decisión del override:** VRNS mostró que el *input del cap* puede estar mal (`g_D` artefacto
  → el PM quedó "boxeado" con techo=piso=4% aunque quería promover). **¿El hallazgo del PM debe poder
  *corregir* el cap (override acotado, gated por un falsador explícito, estilo doc 39) o solo mover el size
  dentro del cap dado?** No está resuelto ni codeado. **Es la pregunta que más nos interesa que evalúes.**

### 3.4 Lo que SÍ está implementado del canal PM-LLM **[IMPLEMENTADO / PARCIAL]**
El canal de juicio (Bloque 3) **sí está cableado** al paper (más de lo que sugería documentación vieja):
`job_paper_pm` corre semanal (cron dom 19:30 ET) + por evento fuerte, produce `libro_pm.json`, y
`job_paper_ciclo` lee esos targets para sizear dentro de la banda `[piso, techo]`. Hay vista `/pm`. Lo que
falta es **la lógica de triage** (correrlo solo sobre pocos) y **resolver el override**.

---

## 4. Arquitectura y flujo de decisión

### 4.1 El núcleo determinista (`backend/nucleo/`, 57 archivos, el corazón)
Flujo por empresa: **arquetipo → gate de evidencia → mérito/pilares → sizing → 5 vías de salida → re-gate.**

- **Arquetipo** (`arquetipo.py`): clasifica en Madura / Growth / Tracción / Pre-revenue / Binary. El ~70% del
  universo es pre-revenue.
- **Gate de evidencia** (`gate.py`, `gate_evidencia.py`): vara de evidencia por arquetipo (U1/U2 + ítems por
  dimensión). Si no pasa → "todavía no" / `NO_EVALUABLE` (`cuarentena.py`).
- **Método de análisis (doc 33, canónico):** datos deterministas + LLM citado; **owner-FCF** separa "valuar"
  de "reverse underwriting"; **dilución** es un eje aparte; comparación en **2 niveles** (dentro del arquetipo
  + cartera across) **sin un score único**.
- **Valuación:** dos gramáticas ruteadas por `ruteo.py`:
  - Empresas con flujo → **reverse-DCF unificado** (`valuacion_reverse.py`, `crecimiento.py`): se resuelve el
    `T*` (cuántos años de crecimiento hay que creer para justificar el precio) — *falsación, no proyección*.
  - **Pre-revenue** (~70%) → **reverse underwriting** (`pre_revenue.py`): funded critical path + dilución
    central, no DCF (doc 31).
  - `compilador.py` + `admisibilidad.py`: *scenario compiler determinista* — el LLM clasifica, el compiler
    pone los valores (doc 27). `templates.py`, `bridge.py`, `realizacion.py` completan la capa.
- **Sizing (2 ejes, doc 34 §3ter — triangulado):** **EVIDENCIA → libro** (si entra o no, inmutable) ·
  **VALUACIÓN → tamaño** (variable). `sizing.py` + `fragility.py` + `sizing_burden.py`. Clave:
  `sizing_burden` da un **CAP (techo en [4%,8%])**, no el size; el PM elige dentro (sándwich). `escalera.py`:
  escalera de add-on (doc 46) — la evidencia dispara, la valuación vetea, el precio nunca; congela, no vende.
- **Ranking / cartera:** `ranking_lexicografico.py` (reemplazó `merito = Quality × Asimetría`),
  `cartera_celdas.py` (ranking por celdas arquetipo×tier, doc 34 §3bis), `selector.py` / `cartera.py`:
  top-N, piso 70%/techo 100% invertido, **máx 12 posiciones**, caps por sector/driver, con **abstención**
  (el PM aporta inputs; su override nunca *promueve* por sí solo).
- **Carril especulativo** (`carril.py`, doc 29): la opcionalidad influye en la *selección* (desempate), nunca
  multiplica el size. Reemplazó el viejo "sleeve 2% por nombre".
- **5 vías de salida** (`salida.py`): triggers/stop de progreso · CRR-crítico · ≥3 red flags · asimetría
  muerta · monitor mecánico. Precedencia gov → CRR → vía1 → vía4 → vía5.
- **Canal de juicio (Bloque 3):** `juicio.py` + `juicio_llm.py` + `flujo_pm.py` + `ledger_juicio.py`
  (hit-rate) + `registro_decisiones.py` (ledger de rechazos / anti-ceguera). Es la "última milla" del
  sándwich: el PM emite una etiqueta discreta + falsador + evidencia web; el allocator sizea dentro de la banda.

### 4.2 El motor de evidencia (medido, Bloque 0 cerrado) **[IMPLEMENTADO]**
`extractor_citado.py` (extrae + cita) + `retrieval.py` (recupera evidencia primaria) + `fact_store.py` /
`fact_keys.py` (hechos fundados persistidos) + `gold_retrieval.py` (gold set + medición). Medido: recall
62→88%, **P(correcto | HIT) = 100%**, temp=0 fue el win. Conclusión: **la extracción no es el cuello**; el
límite es el retrieval/cita. El tier de demanda es orientativo + cita → el humano/PM juzga (no sobre-gatea).

### 4.3 El mapa sectorial (`backend/mapa/`, Bloque B)
Worldview configurable: nodos de **cuellos de botella** sectoriales (`nodo.py`), tabla determinista de
apertura/transición/archivo (`transiciones.py`), brújula sectorial (`brujula.py`), discovery con frecuencia
de vigilancia por estado (`discovery.py`).

### 4.4 Paper trading autónomo (`backend/seleccion/`)
`paper_trader.py` (464 LOC) opera `data/nucleo_paper/libro.json` de forma determinista (sin LLM en la
decisión de capital): **salida primero, luego entrada por mérito**, consumiendo los targets del PM si existen.
`paper_pnl.py` marca a mercado (equity, P&L, curva vs SPY normalizada). El dashboard lee esto por request.

---

## 5. Mapa completo del código (módulo por módulo, con LOC)

> Docstring de módulo = propósito declarado en el propio archivo. Fuente de verdad = el código.

### `backend/` (raíz / infra)
| Archivo | LOC | Propósito |
|---|---|---|
| `main.py` | 881 | FastAPI app — entrypoint (API JSON + health + admin). |
| `ui.py` | 579 | Rutas de UI server-side (Jinja2). |
| `consola.py` | 474 | Consola Claude Code embebida (`/consola`). |
| `models.py` | 650 | SQLAlchemy — 16 tablas del sistema. |
| `panic.py` | 219 | Kill switch global (pausa todo). |
| `scheduler.py` | 152 | APScheduler — jobs del paper + backup. |
| `pipeline.py` | 134 | Cableado end-to-end Etapas 3→6 sobre el ledger fiel. |
| `auth.py` | 156 | Auth admin single-user (cookie firmada). |
| `config.py` / `database.py` / `utils.py` | 63/59/75 | Config (.env), SQLite session, utilidades. |

### `backend/nucleo/` — núcleo determinista (57 archivos; selección por relevancia)
| Archivo | LOC | Propósito |
|---|---|---|
| `flujo.py` | 149 | Flujo punta a punta (`evaluar_empresa`, `armar_cartera`). |
| `arquetipo.py` | 151 | Clasificación de arquetipo (Madura/Growth/Tracción/Pre-rev/Binary). |
| `gate.py` / `gate_evidencia.py` | 262/94 | Vara de evidencia por arquetipo + 🔒 evidencia→decisión. |
| `evaluacion.py` | 128 | Elegibilidad por 3 pilares conjuntivos → tier (doc 33/34). |
| `pilares.py` / `ranking.py` | 199/162 | Evaluadores de pilares (hechos→banda) + wiring del ranking. |
| `ranking_lexicografico.py` | 291 | Ranking lexicográfico (reemplazó Quality×Asimetría). |
| `cartera_celdas.py` / `cartera.py` / `selector.py` | 88/72/54 | Sizing por celdas + selector de cartera. |
| `sizing.py` / `fragility.py` / `sizing_burden.py` | 114/112/150 | Mérito/Hard Cap · Fragility · cap continuo del bucket growth. |
| `escalera.py` / `carril.py` | 85/160 | Escalera de add-on (doc 46) · carril especulativo (doc 29). |
| `salida.py` / `estado.py` | 197/193 | 5 vías de salida + re-gate · estado stateful por posición. |
| `valuacion_reverse.py` / `crecimiento.py` | 156/142 | Reverse-DCF unificado (solver T*) · g_D demostrado y fadeado. |
| `pre_revenue.py` / `dilucion.py` | 198/94 | Reverse underwriting pre-revenue · pilar de dilución (doc 31). |
| `compilador.py` / `admisibilidad.py` / `templates.py` / `bridge.py` | 187/65/98/73 | Scenario compiler determinista + contrato fact-store→valuación. |
| `ruteo.py` / `binaria.py` / `realizacion.py` | 118/52/121 | Ruteo de gramática de valuación · gramática binaria · router realización. |
| `quality.py` / `valuacion.py` | 108/137 | Tier de calidad de negocio · valuación bull/base/bear. |
| **Canal de juicio (Bloque 3):** | | |
| `flujo_pm.py` | 142 | Orquestación del canal de juicio (doc 39 §2.6). |
| `juicio.py` / `juicio_llm.py` | 98/148 | Canal de juicio acotado · interfaz PM-LLM (la "última milla"). |
| `ledger_juicio.py` / `registro_decisiones.py` | 89/154 | Hit-rate del juicio · ledger de rechazos (anti-ceguera). |
| **Motor de evidencia:** | | |
| `extractor.py` / `extractor_citado.py` | 264/212 | LLM traedor de hechos · extractor citado + verificador. |
| `retrieval.py` / `fact_store.py` / `fact_keys.py` | 214/140/232 | Recuperación de evidencia · fact store · registry de fact_key. |
| `gold_retrieval.py` | 385 | Gold set + medición del retrieval (Bloque 0). |
| `hoja_evidencia.py` | 299 | Hoja de evidencia por empresa + ranking del universo. |
| `generador.py` / `cuarentena.py` / `resolve_event.py` | 102/75/109 | Capa generadora (marco/hipótesis) · cuarentena · eventos atómicos. |
| `politica.py` / `constantes.py` | 345/76 | Archivo de política versionado (todas las constantes de juicio). |
| `capital_raise_risk.py` | 136 | CRR determinista (riesgo de ampliación de capital). |
| `auditoria.py` / `validacion_datos.py` / `fidelidad.py` | 61/83/42 | Crítico de completitud · cross-validator · guard de unidades. |
| `backtest_valuacion.py` | 173 | Backtest point-in-time de la valuación (meta-gate empírico). |
| `analisis.py` | 209 | Orquestador vertical (un nombre punta a punta). |
| `medicion.py` / `demo.py` | 31/81 | Log de decisiones · ejemplos para el dashboard. |

### `backend/seleccion/` — Bloque C (selección + paper, 18 archivos)
| Archivo | LOC | Propósito |
|---|---|---|
| `paper_trader.py` | 464 | Trader automático en paper (sin confirmación humana). |
| `paper_pnl.py` | 156 | P&L / mark-to-market / equity / curva vs SPY. |
| `jobs.py` | 86 | Jobs del scheduler del paper (incluye `job_paper_pm`). |
| `pm_run.py` | 125 | Productor del LibroPM (canal de juicio, oficialización). |
| `pm.py` / `pm_loop.py` | 132/154 | PM: arma el mix · orquestador propone→valida→re-propone. |
| `validador.py` / `sparring.py` | 130/78 | Validador determinista del PM · 2º LLM adversarial. |
| `challenger.py` | 137 | Recambio de cartera por mérito con histéresis. |
| `monitor.py` / `presupuesto.py` | 88/96 | Monitor de precio (vía 4/5) · freno de presupuesto. |
| `watchlist.py` / `universo.py` | 94/24 | Watchlist viva (MAX_WATCHLIST) · universo vivo del paper. |
| `deploy.py` / `preflight.py` / `puntos_humanos.py` | 164/153/98 | Deploy al ledger · pre-flight · 2 puntos humanos. |
| `constantes.py` | 10 | Constantes calibrables de la capa. |

### `backend/ledger/` — ledger determinista (Etapa 2)
`core.py` (228, append-log + proyección a posición/caja) · `models.py` (248, tablas `nx_*`) ·
`entidades.py` (163, identidad + máquina de estados) · `ficha.py` (73, ficha versionada).

### `backend/ingreso/` — Etapa 3 (entrada + filtro de universo)
`universo.py` (64, admisibilidad Art. 2) · `filtro0.py` (121, ¿vale el deep research caro?) ·
`adapter.py` (100, ticker real → hechos) · `flujo.py` (85, orquestación sobre el ledger).

### `backend/mapa/` — Bloque B (mapa de cuellos de botella)
`brujula.py` (132) · `nodo.py` (114) · `transiciones.py` (104) · `discovery.py` (85).

### `backend/services/` — integraciones externas
| Archivo | LOC | Propósito |
|---|---|---|
| `edgar.py` | 1066 | Cliente SEC EDGAR — financials + insiders + filings (fuente oficial). |
| `llm.py` | 480 | Wrapper Anthropic Claude (agentes cualitativos). |
| `calculators.py` | 424 | Funciones deterministas — núcleo cuantitativo. |
| `news.py` / `market_data.py` / `precio_base.py` | 230/204/207 | RSS news · precios/volumen/liquidez · precio base sin contratos. |
| `mailer.py` | 216 | SMTP — alertas + digest + reporte semanal. |

### `backend/eval/` + `backend/seed/` + `backend/ops/`
`eval/harness.py` (125, vara objetiva del extractor) · `seed/load_seed.py` (112, seed: 7 sectores + macro +
20 tickers) · `ops/backup.py` (95, backup SQLite).

### `ops/` (scripts CLI, `.venv/bin/python -m ops.<x>`)
`ablation_pm.py` (el experimento del doc 49) · `correr_pm.py` · `paper_auto.py` · `paper_snapshot.py` ·
`medir_retrieval.py` / `medir_extraccion.py` · `gold_freeze.py` · `ficha_profunda.py` · `generar_sizing.py` ·
`generar_hoja.py` · `cutover_diff.py` · `shadow_ranking.py` · `ledger_decisiones.py` · varios `generar_doc_*`
y `restore_*` (recuperación de contaminación de tests) · `extraer_demanda.py`.

### `tests/` — 49 archivos, ~4.371 LOC
Cobertura por módulo del núcleo (gate, evaluación, pilares, ranking lexicográfico, cartera/celdas, sizing
burden, escalera, carril, valuación reverse, pre-revenue, dilución, compilador, bridge, ruteo, binaria) +
motor de evidencia (fact_store, gold_retrieval, hoja_evidencia, demanda_citada) + canal de juicio (juicio,
juicio_llm, flujo_pm, ledger_juicio, registro_decisiones) + paper (paper_jobs, paper_pm_sizing) + ledger +
ingreso + EDGAR (extractors, quarterize). ⚠️ Nota histórica: hubo un bug donde tests del juicio pegaban a la
API real; se corrigió (commit `c0df56d`).

---

## 6. Almacenamiento

- **SQLite** (`data/borja.db`) vía SQLAlchemy. Dos familias de tablas:
  - **Sistema** (`backend/models.py`, 16): `fichas`, `eventos`, `recomendaciones`, `sectores`, `macro`,
    `sectores_mapas`, `discovery`, `dispatch_log`, `tasks`, `llm_calls`, `peer_groups`,
    `fichas_contractuales`, `decision_journal`, `revalidaciones`, `trades`, `portfolio_snapshots`.
  - **Ledger fiel** (`backend/ledger/models.py`, prefijo `nx_`): `nx_cash_movimiento`, `nx_fill`,
    `nx_corporate_action`, `nx_snapshot`, `nx_empresa`, `nx_empresa_evento`, `nx_nodo`, `nx_nodo_evento`,
    `nx_empresa_nodo`, `nx_ficha_version`, `nx_hecho`, `nx_fact`.
- **JSON stores** (`data/`): `nucleo_paper/libro.json` (libro paper), `libro_pm.json` (targets del PM),
  `nucleo_hechos/` (hechos LLM cacheados), `ablation_pm.json` (output del doc 49), `backtests/` (corridas).

---

## 7. Automatización (scheduler, APScheduler, todo en zona ET salvo backup)

| Job | Cron | Qué hace | Costo LLM |
|---|---|---|---|
| Backup SQLite | 4:00 UTC diario | Backup de `borja.db` | $0 |
| `paper_ciclo` | L-V 16:40 | Opera el paper (salida + entrada) | $0 salvo evento fuerte |
| `paper_snapshot` | L-V 16:45 | Mark-to-market + punto de equity | $0 |
| `paper_mtm_intraday` | L-V 9-16h, :00/:30 | MtM en vivo | $0 |
| `paper_reextraccion` | dom 19:00 | Re-extrae hechos (LLM) | **$** |
| `paper_pm` | dom 19:30 | Canal de juicio PM-LLM → `libro_pm.json` | **$$ (ver §3.3: hoy sobre TODO el universo, no triageado)** |

**Deploy:** el dashboard corre como systemd `borja.service` (uvicorn :4151) detrás de Cloudflare Tunnel
(borja.i-314.com). La consola Claude embebida está sandboxeada (no ve/reinicia el proceso del host).

---

## 8. Dashboard (rutas)

- **UI** (`ui.py`): `/` (home = núcleo nuevo: equity/P&L/curva/posiciones), `/hoja`, `/sizing`, `/pm`
  (canal de juicio: etiqueta + tamaño + falsador), `/universo`, `/fichas/{ticker}/view`, `/sectores`,
  `/eventos`, `/costos`, `/rediseno` (vista de sombra), `/login`, `/logout`.
- **API** (`main.py`): `/api`, `/health`, `/api/universo`, `/api/sectores`, `/macro`, `/api/trades`,
  `/api/eventos`, `/api/costos`, `/api/peer-groups/{t}`, `/api/precio-base/{t}`,
  `/api/fichas-contractuales/{t}`, `/scheduler/{status,start,stop}`, `/panic/{pausar,reanudar}`,
  `/backup/run`, `/admin/restart`, etc.
- **Consola** (`consola.py`): `/consola` + `/api/consola/status`.

---

## 9. Decisiones ABIERTAS — dónde más queremos criterio externo

1. **⭐ Override del cap por el PM (la grande).** VRNS: el *input* determinista del cap era un artefacto
   contable (`g_D=2.9%` por fin del on-prem; el recurrente real era ~20-25%) y el PM quedó boxeado
   (techo=piso=4%). ¿El PM debe poder **corregir el cap** (override acotado, gated por un falsador que él
   mismo declare y que luego se mida en el ledger de hit-rate) o debe **solo mover el size dentro del cap**?
   Tensión: power-law (no cortar al ganador) vs. disciplina (no dejar que el LLM entusiasta rompa el ancla).
2. **Triage: cómo elegir los ~3-4 nombres/semana** que merecen Opus+web. ¿Qué señales deterministas definen
   "nombre de borde" sin reintroducir el score único que descartamos?
3. **Deriva de valuación hacia deep-value (doc 35/36).** El reverse-DCF con `g=0` tiende a sub-dimensionar
   tesis de crecimiento temprano; unificamos todo bajo reverse underwriting (falsación), pero el bucket
   "comercial-temprana/growth" sigue siendo el agujero. ¿El método captura bien a un ganador tipo power-law,
   o estructuralmente lo sub-pondera?
4. **Doble validación (doc 44):** en un ejercicio ciego, una IA objetiva nos empató o nos ganó levemente en
   calidad/concentración/ciclicidad. ¿El sistema realmente le gana a "una buena IA analizando a mano", o su
   valor es solo disciplina/reproducibilidad/costo?
5. **Edge data-gated (SYM):** el veto por red-flag solo funciona si la extracción corrió. Fijamos "ausencia
   de dato ≠ ausencia de veto" (sin veto-fact extraído → no se compromete capital → WATCH). ¿Es la política
   correcta, o es demasiado conservadora y mata oportunidades?

---

## 10. Cómo correr / dependencias

- Python 3 + `requirements.txt` (FastAPI 0.115, SQLAlchemy 2.0, anthropic 0.39, yfinance 0.2.48, APScheduler
  3.10, etc.). yfinance usa `curl_cffi impersonate=chrome` por el fingerprinting de Yahoo.
- Entrypoint: `uvicorn backend.main:app`. Scheduler embebido (APScheduler). LLM vía `ANTHROPIC_MODEL`.
- Scripts: `.venv/bin/python -m ops.<x>`. Tests: `pytest`.
- `.env` (no versionado) tiene las claves (Anthropic; opcionales FMP/Polygon/Benzinga diferidas).

---

## 11. Resumen ejecutivo para el evaluador (TL;DR)

BORJA es un sistema quant **advisory** para small/mid caps de industrias del futuro, construido sobre un
**núcleo de decisión determinista** (gate de evidencia → valuación por falsación → sizing con caps
no-compensatorios → 5 vías de salida) alimentado por un **motor de evidencia medido** (LLM que trae hechos
citados de filings SEC, no opiniones). Corre en **paper trading autónomo** con dashboard web. El código está
maduro y testeado (~18.5k LOC backend + 4.4k LOC tests). **El frente abierto más importante** es el
rebalanceo determinismo↔juicio: medimos (doc 49) que el LLM investigando **agénticamente** es irreemplazable
para los juicios finos y que el determinismo debe quedar como **límites + triage**, pero **el triage todavía
no está implementado** (hoy se corre el analista caro sobre todo el universo) y **queda abierto si el PM
puede corregir un cap cuyo input determinista es un artefacto**. Ese es el punto donde más valoramos una
segunda opinión externa.
