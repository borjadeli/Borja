# 51 — Prompt del cambio de dirección: BORJA v2, de núcleo determinista a PM de IA multiagente

> Guardado literal (según instrucción del operador, 2026-10-26) del prompt que define el cambio de dirección.
> Es la directiva fundacional de BORJA v2. Su plan de ejecución vive en el doc 52 (arquitectura, Fase 0).

---

# BORJA v2 — de núcleo determinista a PM de IA multiagente

Rol: sos el ingeniero principal de BORJA y trabajás sobre este repo. Tenés acceso de SOLO LECTURA al repo
"Sistema Quant" (borjadeli/Sistema-Quant, clonado en <RUTA_SISTEMA_QUANT>), del que vas a trasplantar piezas.
No lo modifiques. Guardá este prompt como `init_docs/51_prompt_pm_ia.md` antes de empezar.

## 1. Cambio de dirección (decisión del operador, 2026-10-26)
BORJA deja de ser "núcleo determinista que decide + LLM que trae hechos". Pasa a ser un SISTEMA DE PM DE IA
al estilo AI Finance Labs: agentes especializados investigan, verifican y auditan, y un PM-LLM toma las
decisiones de cartera (qué comprar, qué vender, cuánto y cuándo). El determinismo queda para lo que sirve:
datos, cálculos, detección de eventos, control de presupuesto y los límites de política que fija el humano.
EL DETERMINISMO NO ELIGE NOMBRES NI TAMAÑOS.

Esto reemplaza la premisa de los docs 33/39/49 en lo que respecta a QUIÉN DECIDE. El trabajo intelectual de
esos docs (owner-FCF, dilución, reverse DCF/T*, burden, arquetipos, falsadores, anti-anchoring) se conserva
como herramientas y criterio que reciben los agentes, no como máquina de decisión.

## 2. Referencia: metodología pública de AI Finance Labs
- Etapas con agentes distintos: macro → research por empresa → construcción de cartera → verificación.
- Un sistema amplio preselecciona candidatas y el modelo arma la cartera.
- Variante Claude: un agente por acción verifica el research, un agente arma la cartera y otro la audita.
  Hay varios ciclos de revisión. Decide cuándo operar, con un tope de 2 veces por semana.
- Los humanos fijan la estrategia y los parámetros de riesgo.
Detalle en `docs/research/ai_finance_labs.md` del Sistema Quant (separa lo verificado, lo reconstruido y lo
desconocido).

## 3. Arquitectura objetivo

### Capa A — Datos y calculadoras (determinista, informa, no decide)
- Fuentes: EDGAR, market data y el fact store citado (motor de evidencia actual).
- Calculadoras: owner-FCF, dilución 24m/3y, runway, CRR, g_D, reverse DCF/T*, reverse burden, y
  arquetipo/ruteo como ETIQUETA DESCRIPTIVA.
- Todo número sale con fuente, `known_at` y tipo (original/derivado/estimación/interpretación).
- Las salidas son INPUTS del data pack, nunca un veredicto ni un ranking.
- Anti-anchoring: los agentes ven cálculos, no "lo que el sistema opina".

### Capa B — IPS (Investment Policy Statement) en código
Es el único lugar donde el código manda, y solo con reglas que fija el operador, en `config/ips.yaml`
versionado. Cubre:
- máximo de posiciones, peso máximo por nombre, máximo por sector y por cuello de botella;
- liquidez mínima (ADV) y tamaño máximo como % del ADV;
- caja mínima y máxima, y rango de market cap del universo;
- máximo de operaciones por semana y presupuesto de LLM;
- prohibición de órdenes reales.
Si el PM propone algo que viola el IPS, el código lo RECHAZA y se lo devuelve al PM con el motivo. Nunca lo
corrige en silencio.

### Capa C — Agentes (razonan y deciden)
Cada agente tiene:
- prompt versionado en `prompts/`;
- salida estructurada validada con pydantic;
- costo y tokens registrados;
- fuentes citadas.
Las reglas comunes se adaptan de `src/qa/agents/prompts/_common.md` del Sistema Quant.

1. MACRO/TESIS (semanal, Opus + web). Analiza el estado del ciclo de capex de IA, energía, commodities y
   tasas, y qué cuellos se aprietan o se aflojan. Sale: memo macro + cambios de prioridad por cuello.
2. MAP CURATOR + DISCOVERY (quincenal, Sonnet + web). Mantiene el mapa de cuellos y propone empresas nuevas
   dentro del rango del IPS. Las propuestas van a una cola y el operador aprueba. Se trasplanta del
   Sistema Quant.
3. TRIAGE (semanal, Haiku/Sonnet). Sobre todo el universo, decide quién merece research profundo esta
   semana: prioridad + incertidumbre (valor de la información). Las posiciones en cartera y los nombres con
   evento entran siempre. El código solo hace cumplir el presupuesto.
4. ANALISTA (Opus + web, agéntico, por nombre). Es la pieza que el doc 49 mostró como valiosa. Recibe data
   pack + calculadoras + contexto del mapa + memo macro, y produce un dossier con:
   - negocio y posición en el cuello;
   - demanda con citas;
   - lectura de valuación (qué exige el precio, usando T*/burden);
   - bull y bear INDEPENDIENTES;
   - catalizadores fechados y red flags;
   - FALSADOR CON FECHA y convicción.
   Nada de price targets libres: si usa escenarios, explicita los supuestos y los contrasta con las
   calculadoras.
5. BEAR / RED TEAM (Sonnet u Opus + web). Ataca el dossier con evidencia. El analista responde una vez.
6. VERIFICADOR DE RESEARCH (por nombre). Chequea:
   - cada hecho citado contra la fuente y el fact store;
   - fechas y precios vigentes;
   - declaraciones corporativas tratadas como hechos;
   - consistencia entre narrativa y números.
   Veredicto pass/fail con motivos. Un dossier `fail` no puede justificar una compra ni un aumento.
7. PM (Opus). Ve los dossiers vigentes, la cartera, el memo macro, el IPS y su propio historial de hit-rate
   de falsadores. Decide compras, ventas, recortes, pesos y cuándo operar (revisión semanal o evento, dentro
   del tope del IPS). Por cada decisión deja: tesis, tamaño y por qué ese tamaño, falsador con fecha, qué lo
   haría vender. Puede quedarse en caja.
8. AUDITOR DE CARTERA (Opus, contexto separado). Revisa la propuesta del PM:
   - concentración real (¿10 nombres son 1 apuesta al capex de IA?);
   - coherencia entre memo y peso;
   - rotación excesiva;
   - nombres con verificación fallida;
   - violaciones del IPS.
   Puede devolverla UNA vez con objeciones. El PM responde, y la decisión final queda registrada junto con
   las objeciones.

### Capa D — Monitoreo por eventos (el determinismo detecta, el PM decide)
- Disparadores: filings nuevos (8-K, 10-Q/K, Form 4), movimiento de precio sobre umbral, red flags
  extraídas, falsadores que vencen y alertas de las 5 vías de `salida.py`.
- Cada disparador abre una REVISIÓN de ese nombre (analista + verificador + PM).
- Las 5 vías de salida pasan a ser ALERTAS, no ventas automáticas.
- Solo el IPS opera automáticamente (p.ej. recortar una posición que superó el peso máximo más una banda).

### Capa E — Ledger y evaluación
- Ledger append-only: cada decisión con memo, falsador, hash del dossier, versiones de prompts y modelos,
  hash del IPS/config, precio y timestamp.
- Métricas: hit-rate de falsadores, calibración de convicción (Brier) y P&L vs benchmarks.
- CARTERAS SOMBRA DESDE EL DÍA 1:
  (a) equal-weight del universo elegible;
  (b) "Opus + web solo": un único agente, sin pipeline, mismo universo y cadencia;
  (c) ETFs temáticos (SMH, URA, ITA, COPX; ajustar).
  Sin esto no hay forma de saber si el pipeline agrega algo.

## 4. Conservar / retirar / traer

CONSERVAR:
- services/edgar.py, market_data, precio_base;
- fact_store, extractor_citado, retrieval, gold_retrieval;
- calculadoras: valuacion_reverse, crecimiento, pre_revenue, dilucion, capital_raise_risk, y sizing_burden
  como LECTURA;
- de juicio_llm: bull/bear independientes, falsador, fuentes y anti-anchoring;
- ledger_juicio, registro_decisiones, paper_pnl, scheduler, panic, dashboard, auth.

RETIRAR DEL CAMINO DE DECISIÓN (mover a `backend/_archivo/`, no borrar hasta cerrar la Fase 2):
- flujo.evaluar_empresa / armar_cartera (mérito Quality×Asimetría con bull/bear del LLM);
- selector, sizing_final con PISO_POSICION, cartera_celdas, carril, escalera, challenger;
- la banda [piso, techo] como techo inviolable.
Huérfanos sin caller:
- discovery.py → se reemplaza por el del Sistema Quant;
- sparring.py → lo reemplazan bear + auditor;
- backend/pipeline.py.

TRAER DEL SISTEMA QUANT (adaptar, no copiar a ciegas; traer también sus tests):
- data/map/industry_map.yaml, data/bottlenecks/, data/research/bottlenecks_evidence.json y
  data/universe/companies.yaml, filtrados por el rango de market cap del IPS. Lo marcado `search_summary`
  queda como no verificado.
- agents/map_agents.py, los prompts map_curator/discovery y la cola de propuestas.
- La lógica de embudo y presupuesto: funnel/pipeline.py (promoción por valor de información, reutilización
  por hash, reserva para el comité), funnel/costs.py, agents/base.py y agents/llm.py (pause_turn, errores,
  costo parcial).
- agents/schemas.py como modelo de las salidas estructuradas.
- Los prompts bear, auditor y _common.
- provenance.py (DataPoint con known_at y tipo) como contrato del data pack.
- El patrón ScriptedLLM para tests sin API.

NO TRAER:
- scoring/engine.py (score compensatorio);
- valuation/core.py como motor de decisión (múltiplos de salida elegidos por el LLM sin límites);
- el sesgo del L0 hacia large caps.

## 5. Hallazgos de la auditoría externa (2026-10-26). Verificalos en el código antes de actuar.
1. DOS NÚCLEOS. El paper (`paper_trader.correr_ciclo` ← `flujo.evaluar_empresa`) rankea por
   Quality×Asimetría, con bull/bear de precio absoluto que genera el extractor (el prompt v2 pide "no seas
   tímido"). El método nuevo solo alimenta la banda del PM en `pm_run`. → Se resuelve retirando el camino v3.
2. BUG. La base del PM es CAP_FLOOR_BURN = 4%, pero `sizing_final` descarta todo lo menor a
   PISO_POSICION = 5%, así que todo PASS/HOLD a 4% se pierde en silencio. Reproducción: 4 candidatas, el PM
   da 3×4% + 1×7% y el paper compra solo la de 7%. → Desaparece al retirar sizing_final. Agregar un test de
   regresión: ninguna decisión del PM se descarta sin quedar registrada.
3. MAPA VACÍO en la práctica: nx_nodo sin poblar y el contexto de mapa del PM degrada a {}. → Fase 2.
4. DOCS VIEJOS: CLAUDE.md, CONTEXT.md, doc 32. → Fase 1.
5. DOC 49 (n=3, ciberseguridad) es una hipótesis, no una prueba. → La Fase 5 lo amplía.
6. El TRACK RECORD del paper actual mide el núcleo v3. → Congelarlo y archivarlo; el libro nuevo arranca en
   la Fase 4.
Si alguno no se reproduce, decilo explícitamente.

## 6. Plan por fases
Cada fase va en un PR propio, con tests verdes y un resumen al operador. No se avanza a la siguiente sin
aprobación.

FASE 0 — Plan, sin código.
- Leer el repo, los docs canónicos y el Sistema Quant.
- Entregar `init_docs/52_pm_ia_arquitectura.md` con: arquitectura detallada, schema de salida de cada
  agente, flujo semanal y flujo por evento, IPS propuesto, presupuesto estimado por semana, mapa de módulos
  (conservar/retirar/traer) con rutas, y riesgos.
- Listar las preguntas del §7. PARAR y esperar respuesta.

FASE 1 — Consolidación.
- Congelar el paper actual (archivar libro.json y libro_pm.json con fecha).
- Mover a `backend/_archivo/` el camino v3 y los huérfanos.
- Reescribir CLAUDE.md, CONTEXT.md y un doc de estado nuevo a partir del código.
- Tests verdes.

FASE 2 — Universo y mapa.
- Importar mapa, cuellos y universo del Sistema Quant (poblar nx_nodo / nx_empresa_nodo).
- Fusionar con los 50 tickers de BORJA y aplicar el rango de market cap del IPS.
- Map Curator + Discovery con cola de aprobación en el dashboard.

FASE 3 — Agentes de research.
- Data pack con procedencia.
- Agentes Macro, Triage, Analista, Bear y Verificador, con schemas y prompts versionados.
- Orquestador con presupuesto y reutilización por hash.
- Tests con ScriptedLLM.
- SMOKE TEST REAL contra la API sobre 5 nombres, al menos 2 pre-revenue (p.ej. OKLO y NNE), con tope de
  gasto. Reportar el costo real por nombre y 2 dossiers completos.

FASE 4 — PM + Auditor + IPS + ledger.
- Loop propone → audita → revisa (máximo 1 vuelta).
- El IPS en código rechaza y devuelve.
- El paper nuevo opera desde las decisiones del PM.
- El monitor de eventos abre revisiones.
- Dashboard: por cada decisión, el dossier, la verificación, las objeciones del auditor y el falsador.

FASE 5 — Evaluación.
- Activar las carteras sombra.
- DUELO sobre los 25 nombres comunes a ambos universos: AAOI, AEIS, ALAB, ATI, BWXT, CLS, COHR, CRDO, CW,
  KLIC, LEU, LITE, MP, MTSI, NNE, NVMI, NVTS, NXE, OKLO, POET, SMR, TER, UEC, USAR, VRT.
  Pipeline completo vs "Opus + web solo", con los mismos datos y la misma fecha. Comparar decisiones,
  falsadores y tasa de hechos verificados.
- Panel de hit-rate y Brier.

FASE 6 (opcional, con 2-3 meses de datos) — Torneo de PMs al estilo AI Finance Labs: mismo pipeline de
research, 2-3 PMs distintos (modelos o estilos) operando carteras paper en paralelo.

## 7. Decisiones del operador (pedirlas en la Fase 0)
- IPS: máximo de posiciones, peso máximo por nombre, máximo por sector y por cuello, rango de market cap,
  liquidez mínima, caja mínima y máxima, máximo de operaciones por semana.
- Red flags de supervivencia (going concern, material weakness, restatement): ¿bloqueo duro del IPS, o
  alerta que el PM debe resolver por escrito con el OK del verificador?
- Presupuesto mensual de LLM.
- Verticales: IA core, energía/nuclear, commodities/minerales, defensa, espacio, robótica, biotech (hoy
  ausente). ¿Ciberseguridad se queda?
- Cadencia: revisión semanal fija + eventos, y tope de operaciones.
- Modelos por agente. Default: Opus 5.5 para analista, PM, auditor y macro; Sonnet 5.5 para bear y curator;
  Haiku 5.5 para triage.

## 8. Reglas de trabajo
- No inventar datos, fuentes ni citas. Las declaraciones de la empresa no son hechos verificados. Las
  probabilidades subjetivas van etiquetadas como tales.
- Nunca enviar órdenes reales ni conectar un broker con permisos de escritura.
- Cada fase cierra con tests verdes y un resumen honesto: qué se hizo, qué no y qué se rompió.
- No reabrir triangulaciones de método salvo que un hallazgo de código lo exija: esta etapa es de
  construcción.
- Ante una ambigüedad de diseño: proponer una opción por defecto y una alternativa en el resumen, y seguir
  con la de defecto si no bloquea.
