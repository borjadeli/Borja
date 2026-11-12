# 80 — Convergencia (r8→r9): ficha viva + priorización por oportunidad — DISEÑO CERRADO

> Triangulación del doc 79 por **3 IAs** independientes de alta calidad. **Convergieron fortísimo** — mismo
> esqueleto; cada una aportó rigor en una capa distinta e IA 3 resolvió las dos divergencias que quedaban. Este
> doc fija lo **FIRME** (diseño, no debate), las **divergencias resueltas** (con el porqué), los **números que
> aprueba el operador**, los **cortes por sobreingeniería**, el **orden de implementación** y el **impacto sobre
> lo ya construido (r7/r7a)**. Fecha: 2026-11-12. NO codear fuera de lo que acá queda cerrado.

## 0. El veredicto en una frase (las 3 coinciden)
**BORJA deja de ser una fábrica de dossiers y pasa a ser un inversor con memoria permanente, observación barata,
investigación selectiva y decisiones de capital disciplinadas.** Tres ritmos:
- **Observar** — código, diario, $0: precio, filings, insider, news, Δ XBRL → mantiene vivas las oportunidades.
- **Entender** — agentes, semanal, selectivo: investigar solo donde hay incertidumbre que puede cambiar una decisión.
- **Decidir** — PM semanal + excepciones: comparar oportunidades, cartera, riesgo agregado y costo de oportunidad.

Los **dos núcleos** que habilitan todo lo demás: **(F) la FICHA VIVA** (no olvidar nunca una tesis útil + sus
condiciones económicas de entrada/salida) y **(D) la PRIORIZACIÓN POR OPORTUNIDAD** (dirigir el gasto de
research adonde más puede cambiar la cartera). Las dos son **P0**.

## 1. FIRME — el diseño cerrado (donde convergen las 3)

### El principio rector: DOS RELOJES
La tesis es **lenta** (la escribe el comité citando un hecho nuevo); el precio es **rápido** (lo procesa el
código, gratis, a diario). Hoy están atados — por eso una caída moderada no dispara nada y una tesis sin
novedades se vuelve a pagar cada 35 días. **El rediseño los separa.**

### F — Ficha viva (la primitiva central; reemplaza al dossier como objeto principal)
- **1 ficha viva por nombre + historial append-only.** El **dossier** sigue siendo evidencia inmutable
  cacheada; la ficha es la **vista viva** que lo envuelve. Cada decisión del ledger cita `ficha_version`. El
  hash del cache sigue **sin precio**.
- **Reloj lento (solo lo cambia el comité, citando un hecho con `known_at` nuevo):** tesis (resumen + 2-4
  pilares citados), escenarios bear/base/bull (métrica terminal, múltiplo, prob, ancla de tasa base, dilución),
  falsadores fechados, clase D4, rol en el cuello, `visto_hasta` (p.ej. "10-Q 2026Q2"), estado
  (VIGENTE/EN_REVISION/VENCIDA/ROTA), tope duro.
- **Reloj rápido (100% determinista, recalculado a diario y en cada filing):** el **puente de valuación**
  (acciones diluidas, deuda neta, ventas TTM, RPO → valor/acción por escenario), precio, retorno esperado,
  pérdida bear, "qué exige el precio", trayectoria (ventas reales vs senda del base), y las **zonas/gatillos**.
- **Los gatillos se DERIVAN de los escenarios — ningún agente escribe un precio** (anti price-target libre):
  ```
  V_i  = (métrica_i × múltiplo_i − deuda_neta) / (acciones × (1+dilución)^T)
  E[V] = Σ prob_i · V_i
  r(P) = (E[V]/P)^(1/T) − 1
  COMPRA  ⇔ r(P) ≥ hurdle[clase]  Y  V_bear/P − 1 ≥ −piso[clase]
  RECORTE ⇔ r(P) < hurdle_min
  SALIDA  ⇔ P > V_bull / (1+hurdle_min)^T      # ni el bull paga el mínimo
  ```
  El **precio equivalente se mueve solo**: sube al acercarse el horizonte, baja con dilución, se recalcula con
  cada filing. Guardar un `buy_below` estático NO alcanza (una caída puede ser por dilución/pérdida de cliente/
  supervivencia) → ver las tres guardas de abajo.
- **Vigencia por EVENTO, no TTL.** Comprar exige que la última revisión LLM sea **posterior al último 10-Q/10-K**.
  El TTL de 35d desaparece de la ficha (queda solo en el cache del dossier, anti-look-ahead). Tope duro ~2
  trimestres en banca. Una tesis vencida **no se borra**: baja a RADAR con el gatillo 15% más abajo.
- **Tres guardas antidisparo-falso (compuestas de las 3 IAs):**
  1. **Regla de NO-DERIVA (IA3):** el Analista re-suscribe la tesis **sin ver la zona ni el gatillo** — si los
     viera, movería escenarios para justificar la compra o para no vender un ganador caro. El Verificador lo exige.
  2. **Re-chequeo de economía-por-acción (IA2):** al cruzar la zona, el código revalida acciones/deuda/caja +
     que no haya filing material pendiente, antes de habilitar ENTRY (no comprar un cuchillo que cae *porque se
     diluyó*).
  3. **"Por qué cayó" (IA3):** cayó con el sector (z bajo) → vía barata; cayó **sola** → **Bear-delta obligatorio**
     antes del PM ("¿qué sabe el vendedor?").
- **El gatillo ABRE revisión, no ejecuta** (los escenarios tienen error ancho): 3 cierres dentro de la zona + 7%
  de histéresis para salir.
- **Backfill:** las fichas se construyen desde los dossiers ya cacheados ($0).

### D — Priorización por oportunidad (segundo núcleo)
- **Resolución elegante (IA3, subsume el debate 1-score vs 2-colas):** un nombre **con ficha vigente NO necesita
  score** — tiene la **distancia exacta a su zona**. El **score es SOLO para los que no tienen ficha vigente.**
- **Score determinista para ficha-less** (media geométrica, un cero mata el candidato):
  ```
  V = pctl(g_entregado − g_exigido)      # BRECHA DE EXPECTATIVAS, no baratura (Tier B)
  M = pctl(aceleración ventas, RPO/ventas, Δ margen)
  C = estado_cuello × prioridad_macro × rol_en_cuello
  A = compuerta de supervivencia ∈ {0, 0.5, 0.7, 1}      # runway, dilución, deuda, going concern
  score = (V·M·C)^(1/3) × A + bonus(cluster insiders; precio↓ con fundamentals↑)
  ```
  Percentiles **dentro del cluster** (un cuello tiene pocos nombres). V mide brecha de expectativas: lo barato
  que se achica y lo excelente ya en precio dan brecha negativa los dos. Sin ventas no hay brecha → compiten
  solo por exploración.
- **Carriles con cupo:**
  | Carril | Qué entra | Cupo |
  |---|---|---|
  | Tenencias | refresh post-earnings; comité completo por ruptura | obligatorio, se paga primero |
  | Banca | gatillos + post-earnings en zona | por demanda, barato |
  | **Oportunidad** | top del score sin ficha vigente; fichas vencidas con gatillo | **protegido: ~4 deeps/sem (2 en earnings season)** |
  | Exploración | 1 nombre random del 2º cuartil de un cuello prioritario (anti-sesgo) | 1 c/2 sem |
  | Pre-earnings de no-posiciones | **ELIMINADO** | — |
- **Blackout pre-earnings (decisión del operador):** no se **re-analiza** (refresh/deep de una **ya analizada**)
  a ≤14 días de su earnings — guarda su puesto y se revisa con el filing fresco. Una **nunca analizada** SÍ es
  elegible (su primer deep no es re-trabajo; el earnings pasa a ser su refresh). El evento, para una no-tenencia,
  **mueve el score; no tiene carril.**
- **Determinista vs LLM:** el ranking es 100% determinista (no usa ningún insumo escrito por el Analista).
  Triage (Haiku) elige dentro del top-K (K=3×cupo) con código de motivo. Sombra "top-N determinista" mide si
  Triage aporta.

### A — Universo (membresía por calidad)
- **5 niveles (IA2/IA3):** **CARTERA** (≤20) · **BANCA** (~15: suscriptas, tesis vigente, esperando precio) ·
  **RADAR** (~30) · **COLA** (resto hasta 160) · **ARCHIVO** (afuera, con lápida).
- **El número que ATA no es 160 — son ~30-35 FICHAS VIGENTES** (lo que el presupuesto mantiene fresco). 160 es
  el tope de monitoreo (gratis).
- **Reemplazo por CALIDAD, no rotación:** al llenarse, sale el de menor valor de retención en COLA (score bajo,
  sin ficha, cuello débil); **nunca una posición ni una ficha vigente ni un gatillo a <20%.** Salir = ARCHIVO
  con lápida. Umbral anti-churn: ventaja clara y persistente, no fluctuación de precio.
- **Liquidez como elegibilidad de deep:** días para armar el tamaño mínimo de banda a `pct_adv_max`.

### B + G — Mapa vivo + contexto del PM (divergencia RESUELTA, punto medio de IA3)
- **NO un agente nuevo.** El Map Curator se amplía a **Curador de cuello**: valida cuellos nuevos (≥2 fuentes
  primarias independientes) **y** mantiene un **brief versionado SOLO de los ~10 cuellos ACTIVOS** (con
  tenencias/banca/prioridad macro). Cadencia **trimestral** (cuando reportan los líderes) + cambios de estado
  por evento. Estándar de dossier (fuente primaria, `known_at`, append-only, Verificador).
- **El brief es una DEPENDENCIA del dossier:** el Analista lo recibe en vez de reinvestigar la industria por
  nombre → **abarata el deep y hace comparables los escenarios**. Un cambio de estado del cuello abre chequeo de
  delta en las fichas del cuello.
- **El cuello es TEMPORAL (insight de IA3):** se disuelve cuando la capacidad alcanza la demanda — y eso aparece
  en el **tablero XBRL (capex↑, inventarios↑, margen↓) ANTES que en la narrativa.** Estados nuevos:
  promesa/vigilancia/confirmado/**resolviéndose/resuelto** + falsadores de cuello.
- **El mapa manda por tres vías:** elegibilidad (A), la pata C del score (D) y los caps por cuello (H).
- **El PM recibe un PAQUETE determinista por sesión (IA2)** con **corte de datos CONGELADO** (no mezclar precio
  del lunes con el del miércoles): tablero de zonas, fichas de 1 página, briefs de cuellos relevantes, macro +
  delta, exposición vs caps, tabla de reemplazo, track record, historial con **por qué eligió XYZ vs ABC**.

### C — Latido (monitoreo barato)
- **Un job diario post-cierre para los 160**, 100% determinista, $0. Por nivel cambian el umbral y la acción, no
  la cadencia. Señales: precio (z sectorial, drawdown, zona de la ficha); EDGAR por tipo (8-K 1.01/2.02/3.02/
  4.01/4.02/5.02, S-3/424B5 dilución, NT atraso, 13D); Form 4 con cluster; RSS red-flag; **Δ XBRL en cada filing**
  (acciones, RPO, ventas, margen, runway, inventarios).
- **5 estados de alerta (IA2)** independientes del scoring: PRICE_CROSS, MATERIAL_CHANGE, RISK_ALERT (bloquea
  compras hasta revalidar; las reducciones siguen), DATA_STALE, EVENT_REVIEW. **Deduplicación:** no re-alertar
  lo mismo a diario; se rearma por cambio económico/decisión del PM/cruce nuevo.
- **El pre-earnings de cartera deja de ser un deep:** es un **marcador** que el código arma gratis (qué tiene
  que mostrar el trimestre para seguir en senda); el post-earnings se puntúa contra ese marcador.

### E — Deep research (el comité no cambia; cambia cuándo se invoca y qué persiste)
- **Tres productos de costo creciente:** **chequeo de delta** (Haiku sin web ~$0.02-0.10: ¿el filing toca un
  pilar/falsador/insumo?) → **refresh parcial** (Analista sobre el delta + Verificador ~$0.25: post-earnings en
  cartera, gatillo en banca) → **comité completo** ($0.68).
- **Se gasta un deep COMPLETO solo si:** comprable bajo IPS al tamaño mínimo · no tiene ficha vigente · encabeza
  el score (o es tenencia con tesis rota/vencida) · hay lugar en el cuello o es candidato de reemplazo.
- **Comité completo se repite ante:** pilar invalidado · trayectoria fuera de tolerancia 2 trimestres · evento
  transformacional · el **10-K de cada tenencia como re-suscripción base cero** ("si no la tuviera, ¿la
  compraría hoy?").
- **Destinos del deep:** PASS en zona → PM; PASS cara → BANCA; REVIEW → RADAR (ficha baja confianza); FAIL →
  lápida. **Bear solo en refresh si cambian escenarios o la caída es idiosincrática** (no en cada refresh).

### H — Sizing
- **Gate duro: no se compra sin ficha VIGENTE.** Zona de compra = requisito **blando** (la excepción se permite
  pero queda marcada, la cuestiona el Auditor, se mide aparte).
- **Entrada escalonada = OPCIÓN del PM (decisión del operador):** el PM puede entrar de una o en tramos (ej.
  mitad en zona, resto al confirmar un hecho) como juzgue — **no es obligatorio**. **Agregar por precio exige
  información nueva** desde la última compra.
- **Tamaño — SIN bandas de clasificación salvo el extremo especulativo (decisión del operador):** el PM sizea
  **libre** bajo el IPS (**20%/nombre** + caps sector/cuello); **core y satélite NO tienen banda** (el PM pondera
  el riesgo como PM). **Único techo duro por clase: especulativa ≤10%, watchlist 0%** — seguro barato contra que
  una lotería pre-revenue sea una posición grande (power-law: muchas apuestas chicas, no pocas grandes). El PM
  sizea, el IPS limita (si viola, rechaza y devuelve; el código **no** elige size alternativo). **Nada de Kelly/
  optimizador/fórmula.**
- **Estacionamiento (ajuste, ver §5):** el residual va al **ETF del cuello de la mejor candidata de banca** (no
  perder beta hacia donde estás por invertir), **pero SOLO si ese cuello no está sobrevaluado** (gate
  determinista: percentil de valuación del cuello vs su historia; si está caro → **caja** / índice amplio).
  Evaluar la exposición **ETF+acciones en conjunto** contra los caps por cuello (un ETF de semis no diversifica
  si ya dependés del capex de IA).

### I — Salidas (5 vías, todas leídas de la ficha)
Tesis rota · valuación (zona SALIDA) · reemplazo · **cuello resuelto** · riesgo/IPS. La zona **RECORTE dispara
re-suscripción, no venta**: el código descompone la suba en fundamentals (ventas/RPO por acción) vs múltiplo —
si corrieron los fundamentals, el comité puede subir escenarios con hechos; si corrió solo el múltiplo, se
recorta a media banda. **Recortar por valuación es la decisión más cara de una cartera power-law → el único
recorte OBLIGATORIO es peso > banda.** Reemplazo: tabla semanal (peor tenencia vs mejor banca en zona), rota
solo si la brecha de retorno esperado supera el umbral y la ficha entrante está vigente. **Sin stops/trailing**
(contradicen el diseño: una caída con tesis intacta es compra).

### J — Discovery + memoria de lo que salió (lápida)
- **Archivo = estado, no borrado.** `lápida`: ticker, fecha, ficha_version_final, **motivo** (TESIS_ROTA /
  VALUACION / REEMPLAZO / FUERA_DE_IPS / CUELLO_RESUELTO / CALIDAD / ROTACION_UNIVERSO), **huella** (último
  filing, ventas TTM, margen, acciones, RPO), **reingreso** (PRECIO | FUNDAMENTAL | SCORE | NUNCA + condición).
- **Reingreso según el motivo:** valuación/reemplazo con tesis intacta → gatillo congelado y vigilado; si
  dispara, vuelve a RADAR con prioridad. Tesis rota/calidad → el validador **rechaza** mientras la huella no
  cambie. Rotación de universo → vuelve si el score entra al cuartil superior.
- **Identidad por SECURITY (CIK + instrumento), no ticker** (maneja cambios de símbolo/fusiones/clases).
- Discovery recibe las lápidas del cuello que barre; al admitir un nombre se le calcula el score (compite por
  valuación, no solo narrativa). **Hit-rate como embudo** (propuesto→admitido→cuartil→deep→PASS→banca→cartera);
  el gasto de barrido se reasigna por conversión.

### K — Aprendizaje (sin auto-tuning; cinco preguntas)
Con ~200 deeps y ~30 ops/año **no hay muestra para ML**, pero sí para medir: (1) ¿aporta el Triage? (sombra
top-N determinista) · (2) ¿aporta el PM sobre las reglas? (sombra "ficha mecánica": todo lo de banca-en-zona a
media banda) · (3) ¿predice el score? · (4) ¿funcionan las zonas? (retorno a 3/6/12m de cada gatillo vs ETF del
cuello) · (5) **¿cuánto cuesta la disciplina?** (registro de OMISIONES: banca nunca comprada que subió >100% —
en power-law el error grande es de omisión). Realimentación = **informe trimestral determinista** con el que el
operador cambia parámetros, versionado. **Nada de auto-ajuste ni "reflexiones" LLM como memoria.**

### L — Datos y presupuesto
- **SQLite WAL + esquemas versionados + JSON** (son ~200-300 filas estructuradas; **NO** Postgres/Redis/vector
  DB/RAG/event bus). Solo `live_opportunity_state` se actualiza siempre. Contrato de dato con **`known_at` Y
  `ingested_at`** (en paper no asumir que conociste un dato antes de capturarlo, aunque el filing ya fuera
  público). Ningún LLM sobrescribe un hecho verificado.
- **Cobertura:** XBRL da gratis por filing acciones/RPO/ventas/margen/caja/deuda/inventarios/capex/SBC/contract
  liability; **extranjeros (20-F/40-F) solo anual → marcar PARCIAL y bajar el techo de clase.** Guidance no está
  en XBRL (lo lee Haiku del comunicado, solo cartera/banca). **No asumir extracción uniforme de RPO** (confirma
  el 38% de Gate A — techo estructural de companyfacts).

## 2. Divergencias RESUELTAS (las 3 posturas → la resolución y el porqué)
| Tema | IA 1 | IA 2 | IA 3 | **Resolución** |
|---|---|---|---|---|
| Gatillo de entrada | buy_below del escenario | función económica + re-chequeo solvencia | math completa `r(P)` + anti-deriva + "por qué cayó" | **IA3 (math) + IA2 (solvencia) + IA3 (anti-deriva, por-qué-cayó)** — se componen |
| Priorización | 1 score + cooldown | 2 colas (conocida/nueva) | **ficha→distancia a zona; score SOLO para ficha-less** | **IA3** — subsume a las otras dos |
| Tiering | 2 niveles | 5 niveles | **5 niveles con BANCA** | **IA3** (nombra el caso del operador: "suscripta esperando precio") |
| Mapa/sector | plegado en Macro | agente dedicado | **Curador de cuello: ~10 activos, trimestral, brief = dependencia** | **IA3** (punto medio; + cuello temporal) |
| Score | 40/25/20/15 suma | 40/20/20/10/10 suma | **media geométrica V·M·C × A, V=brecha expectativas** | **IA3** (robusto; un cero mata; no compra barato-que-muere) |
| Estacionamiento | por convicción | exposición conjunta | ETF del cuello de la mejor banca | **IA3 + IA2 + operador** (ETF de la banca **solo si el cuello no está caro**; exposición total vs caps) |
| Bandas D4 | sombra→duro | duro tras validar | duro espec/watchlist ya | **operador: SIN banda core/satélite (PM libre a 20%); duro solo especulativa 10% / watchlist 0** |
| Rotación | ~5pp | ~5pp | **~10pp** | **~10pp de arranque** (power-law castiga el churn), confirmar en sombra |

## 3. DECISIONES del OPERADOR — APROBADAS (2026-11-12)
**Cualitativas (cerradas):**
- **Doctrina: PACIENCIA.** El objetivo NO es "~90-100% invertido por default" (se ABLANDA el mandato r7a):
  desplegar en nombres con **margen de seguridad**; el residual se **estaciona** (con el gate de sobrevaluación
  del cuello); la caja alta sigue exigiendo tesis macro. Si se quiere MÁS paciencia, se suben los hurdles.
- **Sin bandas D4 para core/satélite** (PM libre hasta IPS 20%); **techo duro solo en especulativa 10% /
  watchlist 0** (gestión de riesgo, va a duro YA). El PM, actuando como PM, pondera el riesgo; el 10% es el
  seguro contra una lotería grande.
- **Blackout pre-earnings** solo para **re-analizar una ya analizada**; una **nunca analizada** SÍ puede ir a su
  primer deep pre-earnings.
- **Entrada escalonada = opción del PM**, no obligatoria.

**Números (priors; las sombras confirman o corrigen):**
- **Hurdles / pisos por clase:** core 15% / −35% · satélite 20% / −50% · especulativa 30% / sin piso (bull ≥5×);
  **hurdle_min 8%**. (Horizonte ~24-36m.)
- **Fichas vigentes objetivo:** ~30-35 (el verdadero cuello del presupuesto).
- **Cupo oportunidad:** ~4 deeps/sem (2 en earnings season). **Blackout:** 14 días (solo re-análisis).
- **Reemplazo:** ventaja persistente (score al cuartil superior) — anti-churn.
- **Rotación:** abrir revisión si la brecha de retorno esperado ≥ ~10pp anualizados.
- **Zona:** 3 cierres dentro + 7% de histéresis.
- **Presupuesto:** ~$26-34 planeado, techo $40. No subir todavía; subir a $55-60 **solo si** tras un trimestre
  la banca se llena de tesis vigentes que convierten (ahí el cuello es el research: cada $10 ≈ 15 deeps).

## 4. CORTES por sobreingeniería (las 3 coinciden)
Agentes nuevos (se amplían los existentes) · memoria vectorial/RAG/embeddings (son ~200-300 filas
estructuradas) · re-deep ante grandes movimientos (usar gatillos) · ML / pesos aprendidos / auto-tuning del IPS ·
forecasts automáticos de TAM · sentimiento de noticias como señal de compra · optimizador/Kelly que sustituye al
PM · intradía / tick / short interest / opciones · stops y trailing stops · DCF o Monte-Carlo por nombre · más de
3 escenarios · gemelo digital de la cadena de suministro · Postgres/Redis/event-bus en un solo entorno.

## 5. Impacto sobre lo YA construido (r7/r7a) — qué se conserva, ajusta o reencuadra
- **Lente de valuación (r7 Bloque 1):** se CONSERVA y pasa a ser el **insumo del reloj rápido** (el puente
  EV/escenarios de la ficha). El `ratio_valor`/percentil por cuello alimenta la pata **V** del score — pero V
  debe ser **brecha de expectativas** (g entregado − g exigido), no baratura: hay que ajustar `fuente_valuacion`/
  `valor_del_universo` para restar el crecimiento que descuenta el EV.
- **Estacionamiento (r7a #1):** se AJUSTA. Hoy parkea por los clusters donde el PM tiene convicción → cambiar a
  **el ETF del cuello de la mejor candidata de banca, SOLO si ese cuello NO está sobrevaluado** (gate
  determinista; si está caro → caja/índice amplio) + **chequear exposición ETF+acciones conjunta** vs caps.
- **D4:** decisión del operador — **se QUITAN las bandas de core/satélite** de `ips.yaml` (PM libre hasta IPS
  20%); queda **solo el techo duro especulativa 10% / watchlist 0** (a duro ya). El `sizing_modo` deja de tener
  bandas core/sat que gatear; el cap especulativo sí es duro.
- **Mandato del PM (r7a deployment):** se ABLANDA de "~90-100% invertido" a **PACIENCIA** (desplegar con margen;
  residual estacionado). Hay que ajustar el prompt del PM y CONTEXT.md otra vez.
- **Embudo (`seleccionar_para_deep`/`triage.prioridad`):** se REESTRUCTURA — carriles nuevos (tenencias/banca/
  oportunidad/exploración), blackout pre-earnings, score solo para ficha-less, distancia-a-zona para fichas.
  El +1 de valor actual queda subsumido por el nuevo score.
- **Gold set de contratos (r7 Bloque 2):** SIGUE vigente — el contrato firme es un insumo del puente (RPO +
  8-K 1.01 + USAspending). El parser medido entra cuando etiquetes el gold set.
- **Señales que ya tenemos (insider Form 4, news RSS, Δ XBRL):** pasan a ser el **latido** (C).
- **Ledger fiel + carteras sombra + Brier:** se CONSERVAN; se agregan las sombras nuevas (top-N determinista,
  ficha mecánica) y el **registro de omisiones** (K).

## 6. Orden de implementación (las 3 convergen; con criterios de aceptación)
- **P0 — Memoria viva + gatillos económicos (prioridad absoluta).** Schema de ficha (reloj lento/rápido) +
  backfill desde dossiers cacheados + puente + zonas + job diario + vigencia por evento (fuera el TTL).
  **Aceptación:** una empresa analizada y descartada por precio reaparece como oportunidad **sin repetir el deep**.
- **P1 — Motor de oportunidad + Triage nuevo.** Score para ficha-less (brecha de expectativas, media geométrica,
  compuerta de supervivencia) + distancia-a-zona para fichas + carriles con cupo + blackout pre-earnings +
  productos de research (delta/refresh/completo). **Aceptación:** un 8-K rutinario no consume deep; una
  oportunidad económica válida sí recibe atención.
- **P2 — Paquete del PM + revisión de posiciones.** Packet determinista con corte congelado + fichas de 1
  página + zonas de recorte/rotación/falsadores. **Aceptación:** el PM revisa toda la cartera sin web ni deeps
  completos de todas las tenencias.
- **P3 — Archivo inteligente + mapa vivo + Discovery.** Lápidas + reingreso + supresión + briefs de los ~10
  cuellos activos (con estados temporales + tablero XBRL) + discovery con valuación. **Aceptación:** una buena
  archivada vuelve por abaratamiento; una descartada estructuralmente no reaparece sin nueva evidencia.
- **P4 — Evaluación + endurecimiento D4.** Oportunidad perdida + sombras nuevas + calibración + D4 a duro
  (validado en sombra). **Aceptación:** BORJA explica qué generó valor, qué lo destruyó y qué cambiar, sin usar
  información futura.

## 7. Casos de aceptación (del rediseño completo)
| Caso | Comportamiento correcto |
|---|---|
| Empresa cara cae 25% sin deterioro | recalcula oportunidad y alerta; NO fuerza deep |
| Cae 25% **tras emisión dilutiva** | bloquea elegibilidad hasta revalidar economía-por-acción |
| 8-K rutinario de no-tenencia | registra y procesa; NO fuerza deep |
| Earnings cambia una tenencia | revisión excepcional fuera de ciclo |
| Archivada cruza su entrada | recupera ficha → cola de oportunidad |
| Descartada sigue igual de mala | discovery la reconoce y evita re-investigar |
| PM propone peso > IPS | gate rechaza, nueva decisión del PM |
| Se agota el presupuesto LLM | siguen monitores y alertas; no se simulan análisis |
| Se reproduce una decisión pasada | se recuperan exactamente datos y versiones de aquel momento |

---

**Estado:** diseño CERRADO, triangulado (3 IAs) y **APROBADO por el operador (2026-11-12)** — decisiones del §3
cerradas (paciencia · sin bandas core/sat, espec 10% dura · blackout solo re-análisis · tramos opcionales ·
estacionamiento con gate de sobrevaluación). **Próximo: arrancar por P0 (ficha viva).** NO se codea fuera de lo
acordado acá. Los números son priors que las sombras confirman o corrigen.
