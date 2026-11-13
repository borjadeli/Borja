# 53 — BORJA v2: estado vivo

> **Fuente viva del estado.** Reemplaza al doc 32 (que describe el estado v1). Si algo acá contradice a un
> doc más viejo sobre *qué está hecho / qué sigue*, gana este. Directiva: doc 51 · arquitectura/plan: doc 52.
> Última actualización: **2026-11-05** (r6 + r7 Bloque 1/§3 + r7a #1/#2/#4).

## Actualización 2026-11-05 (r7a) — revisión externa r7a: deployment coherente + archivo + menores

Punch list externo (rama hasta 675038b). Prioridad en orden. **831 tests verdes.**
- **#1 Estacionamiento en ETFs temáticos (HECHO a nivel módulo + config + IPS + prompts):** el residual que NO
  encuentra nombres con margen de seguridad se aparca en ETFs temáticos (`SMH/URA/ITA/COPX` + `SPY` default),
  ponderados por los clusters del mapa — NUNCA en nombres caros para llegar al 90%. `backend/agentes/
  estacionamiento.py` (`aplicar_estacionamiento`: residual = 1−nombres−caja_macro; desarme-primero implícito).
  `max_posiciones` 12→20; los ETFs de parking NO cuentan como posición (IPS los excluye) ni como op. Prompt PM:
  el residual lo maneja el determinismo, NUNCA subir un escalón de clasificación por deployment. Auditor: objeción
  ALTA (`coherencia`) si un escalón se justifica por deployment y no por evidencia. **PUESTA EN VIVO HECHA
  (2026-11-05):** `RunnerSemanal._estacionar` aplica el overlay al target final (solo si `operar_ahora`; si el
  PM no opera = caja macro, se respeta), ponderado por el sector de los nombres con convicción (fallback: el
  mapa del universo); `_rotacion` excluye los ETFs de parking; el ops `correr_semana_v2` trae los precios de
  los ETFs + el meta de conversión para el fill. 833 tests verdes.
- **#2 Orden de archivo (HECHO):** `elegir_a_archivar` ahora archiva (a) analizado+descartado/FAIL → (b) analizado
  >180d sin señal de valor → (c) nunca analizado, y protege la ALTA NUEVA hasta su primer análisis. Caller en
  `ops.cola_propuestas` enriquecido (descartado/tiene_valor/alta_nueva).
- **#3 interim (HECHO):** prompt PM — un contrato sin RPO en el pack es NO VERIFICADO (no suma al margen de
  seguridad) hasta el Bloque 2. **Bloque 2 sigue PENDIENTE (gateado por Gate B: gold set de contratos).**
- **#4 menores:** doc 53 línea vieja de bandas corregida (HECHO); **auditabilidad del fill (HECHO):** NxFill
  ganó `moneda`/`precio_nativo`/`fx_usado` (+ migración idempotente SQLite) y `paper_pm`/`registrar_fill` los
  pueblan vía `precios_meta_de` (falta threading en el runner real). **Doc 77 PENDIENTE** (necesita corridas en
  vivo: smoke Tier B, primera corrida del universo, decisiones del PM, discovery, cartera vs sombras).

## Actualización 2026-11-02 — calidad del análisis: Tier A + Tier B (docs 72/73/74)

**3 IAs externas triangularon la CALIDAD de los dossiers** (OKLO/RGTI/MP, doc 72). Hallazgo central (3/3): el
sistema **analiza bien el RIESGO y mal la OPORTUNIDAD** — el futuro salía narrativo, no económico; faltaba el
puente `hechos → tesis → precio → retorno del accionista`. Y compramos el nombre con MÁS errores de dato (MP).
Se abrió un plan en 3 tiers; Tier A y el core de Tier B están **HECHOS y testeados (~737 verdes)**.

- **Tier A — bugs deterministas (reproducidos con datos reales + regresión):** liquidez (resolver de valores
  negociables: caja+ST+ladder — MP $429M→$1.452,6M, exacto vs filings) + runway capex-aware; `browse-edgar` ya
  no es fuente primaria; señal `dilucion_overhang` (convertibles/warrants que XBRL no cuantifica).
- **Tier B — el puente económico (doc 74, convergido con 2 IAs):**
  - **D1 (corazón)** puente INVERSO: `metrica_requerida_por_precio` (reverse burden) + `probabilidad_implicita_bull`
    (expectations investing) + render al PM. Clava RGTI (exige $1,22B@8x o $400M@24,5x, "caro"). Solo display.
  - **D2** `vara_externa` en el falsador → Verificador REVIEW si es autorreferencial/infalsable.
  - **D3** `tasas_base.py` (tabla curada con fuente) + calibración: P(bull)>2x la tasa base → REVIEW.
  - **D4** `clasificacion.py` sizing por clasificación en **MODO SOMBRA** (techo por hechos duros + bandas +
    caps bucket/cluster; `sizing_modo: sombra` reporta, no gatea). [Bandas ampliadas el 2026-11-05 — ver
    la sección de esa fecha; los valores viejos quedaron obsoletos.]
  - **D5** Auditor **con web** + checklist "buscar para refutar" + materialidad (máx 3); Sonnet ≠ Analista Opus.
  - **Persistencia Brier** + **ciclo de resolución** (`resolucion.py` + `ops.resolucion`): cierra el loop para
    medir si el análisis calibra.
**Endurecimiento r5 (2026-11-03) — CONGELAMIENTO DE MÉTODO, cerrar punch-list antes de nada nuevo:**
- **HECHO (API-free):** (1) D3 tasas base — `verificada`+`cita`, sacadas las filas "a computar", Flyvbjerg
  corregido, y **no gatea hasta estar verificada contra la fuente** (hoy todas informan). (2) D4 techo por
  **hechos DUROS del pack** (revenue FY ≥ umbral del IPS · fcf/runway capex-aware), ya NO desde `traccion_0_4`.
  (3) **Set dorado** `ops.golden_snapshot` + `tests/test_golden.py` (network-gated): captura MP/OKLO/RGTI
  (incluye `long_term_debt`); el pack los reproduce dentro de tolerancia (la red que habría atrapado el bug de
  MP). (6) doc 53 limpio. 744 tests verdes.
- **PENDIENTE del operador (server + crédito):** (4) **smoke Tier B** (MP/OKLO/RGTI vs doc 71: costo/agente,
  tasa de dossiers malformados, export, sombra D4, objeciones del Auditor con web; el PM re-decide MP/OKLO con
  datos corregidos y se registra que la compra original fue con datos malos). (5) **primera corrida real**
  (`--universo --dry-run` → OK → `--bootstrap`) + cablear el **scheduler** semanal con digest por mail.
- **Pendiente menor (no bloquea):** verificar las filas de tasas base contra la fuente; ruteo D5
  Analista-responde (API); activar el **cap duro de D4** tras correr la sombra en vivo.

## Actualización 2026-11-05 — ronda r6 (embudo/universo/discovery + gigantes + consistencia)

Revisión externa r6, foco en el frente **extranjero + discovery-sin-humano** y las decisiones del operador
de docs 75/76. Todo commiteado en `destete-v2-fase3`. **800 tests verdes.**
- **#1 FX en el paper (P0):** `market_data.precio_a_usd` (maneja GBp/GBX) y `precios_de` convierte en el
  BORDE → paper + sombras valúan en USD (antes 042700.KS sizeaba a 0 acciones; 6315.T, 1 'acción' a $4200).
  Sin FX, el nombre queda fuera.
- **#2 Tenencias SIEMPRE con precio:** una tenencia sin precio valía 0 (equity subestimado, sizing mal);
  `_asegurar_precios_tenencias` usa feed→USD o el último precio del ledger (marcado viejo).
- **#3 Validadores duros de discovery (auto-entrada sin humano):** fuente PRIMARIA obligatoria (clase_por_url
  ∈ regulador/filing/IR; X/Reddit/blogs NO cuentan) + market cap requerido en la auto-entrada; **nodos nuevos
  del curador exigen ≥2 fuentes primarias** (un cuello es estructural → vara más alta que una empresa).
- **#2 bis — tope de universo (160) + reemplazo DIRECTO:** con el universo lleno, una alta de discovery
  **archiva al peor no-posición** y entra la nueva (`elegir_a_archivar`, pura). Una posición del paper NUNCA
  se archiva. Decisión del operador: nada espera afuera.
- **#6 — carril de gigantes COMPRABLE (decisión del operador "los grandes, si están baratos, van"):** un
  nombre > `market_cap_max` ya no es rechazo automático; si `gigantes_comprables`, es ADMISIBLE pero sizea
  bajo `peso_max_gigante` (10%) en vez de 20%. El piso de $150M (micro) sigue firme. El embudo ya ruteaba los
  gigantes CAÍDOS (z≤-1.5) a deep.
- **#4 — consistencia en CADA pack ("verificar siempre", el operador tenía razón):** `fuente_consistencia`
  (derivada, sin API, para TODOS los nombres) marca banderas CONFLICTED que ve el Analista/Verificador:
  (1) acciones feed vs XBRL >25%, (2) market cap sospechosamente chico (escala/moneda), (3) último XBRL >400d.
  Complementa (no reemplaza) al set dorado.
- **Diferido r6:** reporte doc 77 (#4 pendiente de redacción), período de observación N semanas antes de
  habilitar nombre nuevo, scheduler + digest por mail (#7), auditabilidad del fill (moneda/precio nativo+FX).

> **Observación del operador (2026-11-05), abierta — NO es bug, es mandato:** el paper (depósito inicial
> $100k, 2026-10-27) está **~1,5% invertido** (sólo MP ~$1.450; OKLO entró 3% y salió). El operador quiere
> estar **casi totalmente invertido salvo justificación macro para liquidez**, lo cual choca con dos cosas
> baked-in hoy: (a) el mandato "disciplina sobre actividad / preferir slots vacíos" del prompt del PM +
> CLAUDE/CONTEXT, que lo lleva a CAJA por default; y (b) las bandas de sizing por clasificación (D4: espec
> ≤1,5% · satélite ≤5%) — como casi todo el universo clasifica "especulativa", el techo agregado es chico por
> construcción. **Requiere decisión de método del operador** (relajar bandas / cambiar el mandato del PM vs.
> mantener la disciplina power-law). Ver dudas respondidas 2026-11-05.

## Actualización 2026-11-13 (r8→r9) — rediseño CERRADO (doc 80) + P0 ficha viva HECHO

**El rediseño grande del sistema operativo de investigación/portfolio** (embudo/memoria/universo/deep) se
trianguló con **3 IAs** (docs 79 brief → **80 convergencia + diseño cerrado**) y lo **aprobó el operador**
(2026-11-12). Núcleos: **ficha viva** (tesis lenta del comité / precio rápido del código; gatillos derivados de
escenarios; vigencia por EVENTO, no TTL) + **priorización por oportunidad** (score solo para ficha-less).
Decisiones del operador: PACIENCIA (se ablandó el "~90-100%"), **sin bandas D4 core/satélite** (espec 10% dura),
blackout solo re-análisis, tramos opcionales, estacionamiento con gate de sobrevaluación. Implementación P0→P4.
- **P0 (ficha viva) CERRADO (2026-11-13):** `backend/agentes/ficha.py` (puro: puente equity-bridge + zonas
  COMPRA/MANTENER/RECORTE/SALIDA con hurdle+piso por clase, aprobados en `ips.yaml`) + `ficha_store.py` (store
  JSON + backfill desde el cache de dossiers + **job diario** `recalcular_todas` que emite alertas de cambio de
  zona + vigencia por evento) + `ops.backfill_fichas`. **Validado en vivo:** MP compra $17,83 / OKLO compra
  $3,84 (ambas RECORTE hoy). Caso de aceptación cumplido en test (cara→cae→COMPRA sin re-deep). 841 tests.
- **Próximo: P1** (motor de oportunidad + Triage nuevo: score para ficha-less, distancia-a-zona para fichas,
  carriles con cupo, blackout, productos de research delta/refresh/completo). Después P2 (packet del PM) · P3
  (archivo+mapa vivo+discovery) · P4 (evaluación+D4 duro). **No codear fuera del doc 80.**

## Actualización 2026-11-05 (tarde) — vistas + caps/PM + r7 Bloque 1 (valuación como motor)

Sesión con el operador. Tres frentes:
- **Vistas corregidas:** (1) `/descubrimiento` mostraba las propuestas SIN tesis/por-qué-ahora/market-cap/
  fuentes (el embudo tiraba esos campos) → ahora las rinde completas. (2) `/pm` ("Decisiones del comité")
  truncaba todos los textos con slices fijos Y mostraba sólo el dossier, no la DECISIÓN del PM → sin truncado +
  badge con acción/peso/ciclo real del ledger de decisiones.
- **Caps + mandato del PM (deployment):** el paper estaba ~1,5% invertido. Causa: no eran los caps (D4 está en
  SOMBRA, no gatea) sino el PROMPT del PM ("disciplina sobre actividad / caja por default"). Cambios: prompt del
  PM → **capital desplegado por default (~90-100% salvo macro)**; bandas D4 ampliadas (espec 1,5→5% · sat 5→10%
  · bucket 10→30% · cluster 20→40%); CONTEXT.md actualizado. D4 sigue en sombra.
- **r7 — valuación como motor + contratos como hecho duro (doc 78, directiva del operador).** Adoptado; sin
  conflicto con los caps nuevos (palancas ortogonales — ver doc 78). **Bloque 1 HECHO (determinista, 808 tests
  verdes):** tags XBRL `rpo` (RevenueRemainingPerformanceObligation) + `contract_liability` + `revenue_fy_prev`;
  **`fuente_valuacion`** (DERIVED, fuera del hash): EV, EV/revenue, EV/gross, FCF yield, crecimiento YoY, EV/RPO,
  cobertura de backlog, valor contratado ajustado por margen — con COMPUTED/MISSING/NOT_APPLICABLE; prompt del PM
  §6 (valuación prioriza, no solo frena; preferir valor contratado firme/caja por $ de EV; nunca EV/revenue
  solo). **Gate A CORRIDO** (`ops.medir_cobertura_valuacion`, 45 nombres): lente general con buena cobertura
  (EV 89% · EV/revenue 84% · FCF yield 64% · crecimiento 84%) pero **RPO solo 38%** (contract_liability 47%) →
  la lente de valor sirve casi en todo el universo; el "contrato duro vía RPO" en ~4/10 → refuerza la necesidad
  del parser 8-K/USAspending (§2), que es el ítem riesgoso (Gate B).
  **Embudo §3 HECHO (determinista, 817 verdes):** señal de valor en `embudo.py` (`ratio_valor` = EV/(contratado
  +revenue); `percentiles_valor_por_cuello`; `top_por_valor` para el dry-run) + `SenalesTriage.valor_percentil_
  cuello` + boost en `triage.prioridad` (barato en su cuello → +1, sube en la fila) + plumbing en
  `candidatos_del_universo`. **Última milla CABLEADA:** `universo.valor_del_universo` (assembla la lente por
  nombre, best-effort) + `cuello_primario`; el ops `correr_semana_v2 --universo` computa el overlay (flag
  `--sin-valor` para saltearlo) y el dry-run imprime el **top-15 por valor** (§8). Verificado en vivo (OKLO
  pre-revenue → sin señal; CRDO<ALAB en conectividad). 819 tests verdes.
  **Bloque 2 EN MARCHA (gateado por Gate B):** **gold set de contratos ARMADO** — `ops.gold_contratos` baja los
  8-K ítem 1.01 de EDGAR y deja el excerpt + campos vacíos a etiquetar (firme/condicional/no_cuenta) en
  `tests/gold_contratos/gold_contratos.json`; **corrido: 35 filings 1.01 en 8 nombres** (BWXT/LEU/RKLB/OKLO/
  KTOS/MP/LUNR/UUUU), todos SIN etiquetar. `tests/test_gold_contratos.py` valida el scaffold + las labels.
  **PENDIENTE del operador: ETIQUETAR los 35.** Después: parser 8-K 1.01 + USAspending medido contra el set +
  sección "¿qué compro por este precio?" del Analista + reglas del Verificador + frontera D4 con contratos.
  Hallazgo del dry-run cerrado: 4º check `revenue_sospechoso` (revenue > 5× market cap → CONFLICTED; captura GLXY).

## Dónde estamos
**FASE 4 + P1 + EMBUDO completos y validados en vivo; el PM ya compró (OKLO 3%).** El comité corre
end-to-end (fuente_xbrl point-in-time + calculadoras → Analista/Bear/Verificador con contraste XBRL, clase
epistémica por URL y protocolo de frescura → PM bajo IPS → Auditor → paper). **Embudo** de priorización
construido (doc 64): materialidad por ítem de 8-K, precio residual normalizado, earnings diferido, bootstrap
acelerado, presupuesto mensual con arrastre, `candidatos_del_universo` cableado (`--universo`). **4 rondas de
auditoría externa** trianguladas y cerradas (P0/r2 docs 57-59, embudo+verificador docs 61-64, frescura r3 doc
65). Rama `destete-v2-fase3` (en GitHub). El cambio de dirección v2 está cerrado (doc 51), arquitectura/plan
doc 52. **El estado y los pendientes vigentes están en la sección de arriba (Tier A + Tier B + r5).**

**Hecho hasta ahora (todo commiteado):**
- Fase 1: gasto v3 cortado (crons off), paper congelado, huérfanos archivados, docs reescritos.
- Fase 2: ETL + **ingest ejecutado** → `nx_*` poblado (142 nodos, 135 empresas, 184 vínculos). Resolvió el
  hallazgo #3 (mapa vacío). Fuente del SQ versionada en `backend/seed/sistema_quant/`.
- Fase 3: SDK anthropic 0.39→2.3 (Opus 5.5 operativo) · contratos de datos (`provenance.py` + `schemas.py`,
  los 8 agentes, al diseño convergido) · data pack assembler (`data_pack.py`) · **triangulación CERRADA +
  validada por spike** (doc 54 §4) · **agent base** (`base.py`: transporte + costo 5.5 + `ScriptedLLM`) ·
  **Triage** (`triage.py`, pointwise, validado en vivo Haiku 5.5) · **Analista** (`analista.py`: Opus 5.5 +
  web + tool `emitir_dossier` strict — **validado en vivo sobre OKLO**: Dossier real, 9 claims, bull/bear
  independientes, falsador fechado, $0.69/corrida).
  **Bear** (`bear.py`, Sonnet 5.5 + web, ataca) · **Verificador** (`verificador.py`, determinista por
  procedencia, 3 estados PASS/REVIEW/FAIL, núcleo sin API) · **Macro** (`macro.py`, Opus 5.5 + web →
  MacroMemo). **Los 5 agentes de research están completos** (Triage, Macro, Analista, Bear, Verificador).
  **ORQUESTADOR** (`orquestador.py`) + **ledger de presupuesto USD** (`presupuesto.py`): flujo semanal
  Macro→Triage(ranking, forzados)→ por nombre bajo el ledger (sobre semanal + reserva de eventos + reserva
  de peor-caso + escalera 70/90/100%): reutiliza por hash (TTL 35d) o corre Analista→Bear→Verificador; un
  dossier FAIL no se cachea. Todo testeado con stubs (508 tests verdes).
- **Fase 3: COMPONENTES COMPLETOS.** Falta solo la **validación**: el SMOKE REAL sobre 5 nombres (doc 52) —
  una corrida semanal en vivo (≈$4-6, ~20-30 min de llamadas agénticas) → reportar costo real/nombre + 2
  dossiers. Diferido a Fase 4: réplica del Analista al Bear (turno en su hilo) + Analista en Batch (−50%).
- **Fase 4 — TRIANGULADA (doc 55, principio rector: límite duro = inputs mecánicos O canal de disputa) +
  en curso:**
  - ✅ **IPS en código** (`config/ips.yaml` + `backend/agentes/ips.py`): validador determinista, inputs
    mecánicos-solo, tipos local_simple (recorte a cash) / agregada (NO_ACTION), cap de supervivencia DENTRO
    del IPS, dry-run + gate final. Testeado.
  - ✅ **Ledger de decisiones** (`backend/agentes/ledger_decisiones.py`): append-only e inmutable (log de
    eventos → el estado es proyección, mismo patrón que el ledger fiel). Marca "PM+clip", objeciones del
    auditor como predicciones falsables, signo del falsador en el schema (disparado=tesis falsada /
    no_disparado), Brier + hit-rate por bucket con conteos + `pendientes(hoy)`. JSONL gitignored. 8 tests.
  - ✅ **PM** (`backend/agentes/pm.py`, Opus 5.5): ve dossiers PASS/REVIEW + cartera + memo + hit-rate +
    flags; emite `PMDecision`. Sizea él (el determinismo no impone tamaño); usa el IPS como **dry-run tool**
    (`validar_ips`) vía nuevo `base.conversacion_tools` (tools cliente). `PMAccion` ganó `conviccion_0_1`
    (insumo del Brier). Sin web (decide sobre evidencia ya verificada). 6 tests.
  - ✅ **Auditor** (`backend/agentes/auditor.py`, Opus 5.5): revisa la `PMDecision` con contexto separado y
    emite objeciones como **predicciones falsables** (concentración/coherencia/rotación/verif-fallida/IPS);
    SIN veto. Salida estructurada, sin web. 4 tests.
  - ✅ **Orquestador de decisión** (`backend/agentes/orquestador_decision.py`): **PM → gate duro del IPS →
    Auditor → ledger**. local_simple → recorte mecánico a cash (clip); agregada → NO_ACTION; objeción alta
    sobre aumento → demora 1 ciclo. Desacoplado del PM (recibe la `PMDecision`). 6 tests. Difiere la "1
    re-propuesta" explícita (el dry-run ya fue la 2a chance).
  - ✅ **Paper nuevo** (`backend/agentes/paper_pm.py`): ejecuta `ResultadoDecision` contra el **ledger fiel**
    (`backend.ledger.core`): traduce `pesos_finales` → acciones enteras, ventas antes que compras, honra
    `demoradas` y `no_action`; puro sobre `Session`. Reemplaza al `paper_trader` v3 (congelado hasta su
    archivado físico). 7 tests.
  - ✅ **Canal de disputa del FAIL** (`backend/agentes/disputa_fail.py`): el FAIL es el nuevo VRNS (doc 55
    §4.1). El PM objeta (claim + por qué es artefacto + fuente que lo contradice) → el Verificador re-corre
    en contexto fresco; quien decide es un **re-chequeo independiente** (`refetch_fn`), NO el PM (nunca
    overridea). `LedgerDisputas` cuenta ganadas/perdidas. 4 tests.
  - ✅ **Runner semanal** (`backend/agentes/runner_semanal.py`): cablea **research→PM→decisión→paper**
    end-to-end. Inyectable (recibe agentes + datos reales: precios, contexto, `session` del ledger fiel);
    toma los dossiers PASS/REVIEW, proyecta la cartera del ledger fiel, inyecta el hit-rate solo si N≥20.
    `DecisionOrq` ahora expone el hash del data pack. 2 tests.
  - ✅ **Adaptadores de datos reales + harness del smoke** (`backend/agentes/datos_reales.py` +
    `ops/correr_semana_v2.py`): precios/market-cap/ADV de market_data, sector/cuello del ledger `nx_*`,
    paper nuevo en DB SQLite separada (`data/paper_v2.db`). El ops cablea agentes reales (Opus/Sonnet/Haiku
    5.5) + runner → corre el ciclo end-to-end con datos reales. 4 tests (adaptadores); el ops es import-safe.
    **El SMOKE REAL queda listo para disparar** (`python -m ops.correr_semana_v2 OKLO MP RKLB`, ⚠️ gasta ~$4-6).
  - ✅ **P0 de la auditoría externa (2026-10-27) CERRADO** — cada bug reproducido antes de corregir + test
    de regresión: **1 gate del IPS** (reducciones siempre se ejecutan; admisibilidad no vende a la fuerza;
    operar_ahora respetado; max_ops por semana calendario; turnover/cap_flag cableados; holding_period
    sacado); **2 reutilización** (hash_pack estable ignorando volátiles; cache persistente); **3 triage**
    (cupo de cobertura + bootstrap para nombres nuevos); **4 presupuesto** (mensual persistente desde
    llm_calls; todos los agentes loguean su costo → /costos).
    **+ 2ª vuelta de la auditoría (r2) CERRADA:** gate por SESIONES (no órdenes), turnover = rotación (no
    despliegue desde caja), agregado de grupo bloquea solo el sector/cuello violado, re-propuesta UNA vez con
    holguras, evento fuerte saltea el caché, presupuesto con ritmo semanal + bootstrap + fail-closed, dry-run
    con ops del ledger, alertas persistidas al PM, sin Auditor si no opera. 588 tests verdes.
  - ✅ **SMOKE REAL corrido (2026-10-27)** — `ops.correr_semana_v2 OKLO RKLB ACHR`, exit 0, **$2.09**
    (Analista $1.65/18 web · Bear $0.34 · PM $0.09 · Verificador/Auditor $0). Pipeline end-to-end OK con LLMs
    reales. Dossiers reales y ricos (OKLO 9 claims/4 red flags, RKLB 7 claims, bull/bear independientes,
    falsadores fechados). **Los 3 → REVIEW** (motivo: "la tesis se apoya en declaración de empresa"). El PM
    eligió **CAJA** (operar_ahora=False, disciplina) → Auditor no corrió (✓ item 6), 0 fills.
    **Hallazgo clave:** sin fact_store/calculadoras (P1) la evidencia es company-stated → nada llega a PASS →
    **el sistema NO puede comprar hasta P1**. El smoke confirma que P1 es la prioridad real.
  - ✅ **P1 CABLEADO Y VALIDADO EN VIVO (2026-10-28)** — auditado 2× (docs 57/58), convergido (doc 59),
    medido (doc 60: companyfacts cubre el backbone → sin parser de instance). Pasos:
    1 `fuente_xbrl` (backbone financiero point-in-time, arregla el freshness) · 2 calculadoras DERIVED
    (runway/dilución, `known_at=max`, estados MISSING/COMPUTED) · 3 contraste numérico por ref
    (signo/escala/período/tolerancia) · 4a clase epistémica por URL (mata la auto-declaración) · 4b
    contraste numérico cableado al verificador (un central numérico que matchea el XBRL del pack = hecho
    verificado aunque el Analista cite un agregador; contradice = FAIL). **SMOKE #2 (OKLO/RKLB/ACHR, $1.82):
    OKLO y ACHR → PASS, RKLB → REVIEW (tesis cualitativa), y el PM COMPRÓ OKLO 3% ($26.56) — primera compra
    de v2.**
  - **Próximo:** paso 4c opcional (persistir texto de EDGAR + entailment, para PASS cualitativo riguroso —
    autónomo, difierible en advisory) · P2 (reescribir CLAUDE.md, limpieza) · Fase 5 (carteras sombra).

## Decisiones del operador (cerradas)
- **Dirección:** PM de IA multiagente; el determinismo informa/limita, no decide (doc 51/52).
- **IPS (parcial):** peso máx/nombre **20%** · rango market cap **$150M–$60B** · resto = defaults del doc 52 §4
  hasta que el operador los edite (máx 12 posiciones, 30%/sector, 35%/cuello, ADV $3M, caja 0–100%, 2 ops/sem).
- **Presupuesto LLM:** **$40/mes** (régimen disciplinado: triage sobre todo el universo + ~2-4 análisis
  profundos/semana; posiciones se monitorean barato, al comité caro solo por evento). El ingeniero avisa si
  hace falta subir a ~$60-80/mes para que funcione bien.
- **Red flags de supervivencia:** alerta que el PM resuelve por escrito con OK del verificador (no bloqueo duro).
- **Ciberseguridad:** parte del universo amplio, sin prioridad de vertical.
- **Modelos (verificados en vivo 2026-10-26):** familia 5.5 — Opus 5.5 (Analista/PM/Auditor/Macro),
  Sonnet 5.5 (Bear/Verificador/Curator), Haiku 5.5 (Triage); Fable 5.1 opción máx. Configurable por agente.

## Hecho en Fase 1
- ✅ **Cortado el gasto LLM del v3:** `scheduler.py` — desactivados `paper_ciclo`, `paper_reextraccion` y
  `paper_pm` (el Opus+web semanal sobre todo el universo). Quedan solo snapshot/mtm ($0) sobre el libro congelado.
- ✅ **Paper v3 congelado:** `data/_archivo_v3/libro_v3_congelado_20261026.json` + `libro_pm_v3_congelado_…`.
- ✅ **Huérfanos archivados** → `backend/_archivo/`: `pipeline.py`, `sparring.py`, `discovery.py` (+ su test).
- ✅ **Suite en verde:** `pytest.ini` acota la colección a `tests/`; **465 passed**. App importa limpio.
- ✅ **Docs reescritos:** `CLAUDE.md`, `CONTEXT.md`, este `53`.

## Pendiente / acciones abiertas
- 🔴 **ACCIÓN DEL OPERADOR — reiniciar el host** para que el apagado de crons tome efecto (la consola está
  sandboxeada, no puede): `sudo systemctl restart borja` en el servidor, **o** `POST /admin/restart` desde el
  dashboard (hace `os._exit(0)`; systemd respawnea con el código nuevo). Hasta entonces `paper_pm` dispara el
  próximo domingo 19:30 ET (~$17 de gasto evitable).
- ⏳ Commit + PR de Fase 1 (requiere remoto git → GitHub del operador).

## Diferido con criterio (no se hace en Fase 1)
- **Move físico del núcleo de decisión v3** (flujo/selector/sizing_final/cartera_celdas/carril/escalera/
  challenger) → **Fase 4**. Razón: `flujo.EntradaEmpresa` lo usa el motor de evidencia CONSERVADO y
  `paper_trader` (que se reescribe en Fase 4) importa esos módulos. Sacarlos ahora rompe el arranque. En Fase 1
  quedan **neutralizados** (no corren).
- **Upgrade del SDK anthropic** (0.39.0 → versión con 5.5 + batch + caché) → **inicio de Fase 3**, justo antes
  de construir los agentes (hoy no llamamos a 5.5; upgradear ahora solo arriesga `services/llm.py` sin beneficio).

## Plan por fases (resumen — detalle en doc 52 §6)
- **Fase 0** — Plan. ✅ (docs 51/52).
- **Fase 1** — Consolidación (congelar v3, archivar, docs). ◐ en curso.
- **Fase 2** — Universo + mapa (importar Sistema Quant, poblar `nx_nodo`, Map Curator + cola de aprobación).
- **Fase 3** — Agentes de research (data pack con procedencia; Macro/Triage/Analista/Bear/Verificador; schemas;
  orquestador con presupuesto + reutilización por hash; smoke test real sobre 5 nombres). SDK upgrade acá.
- **Fase 4** — PM + Auditor + IPS en código + ledger; reescritura de `paper_trader`; el paper nuevo opera.
- **Fase 5** — Evaluación: carteras sombra + duelo de 25 nombres (pipeline vs "Opus+web solo") + Brier.
- **Fase 6** (opcional) — torneo de PMs.

## Repo Sistema-Quant (para Fase 2)
Público, clonado y verificado (2026-10-26): `https://github.com/borjadeli/Sistema-Quant`. Piezas a traer
confirmadas presentes (agents/map, funnel, schemas, provenance, data/universe ~246 empresas). En Fase 2 se
decide si se clona de forma persistente en el server para que el import sea reproducible.
