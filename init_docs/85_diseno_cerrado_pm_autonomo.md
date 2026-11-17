# Doc 85 — Diseño CERRADO: el PM autónomo (ciclo operativo)

> **Canónico (v2, final).** Sucesor del doc 84 (brief). Convergido por **IA1 + IA2 + IA3** (2026-11-17) +
> decisiones del operador. Cierra el COMPORTAMIENTO del PM: cuándo mira, qué puede comprar, qué pasa si quiere
> algo sin analizar, cuándo vende, cada cuánto. **A IMPLEMENTAR en 3 fases.** No re-abre doc 80 (ficha viva) ni
> doc 83 (equity bridge). Relacionado: [[84]], doc 80, doc 83.

## 0. El principio que unifica todo
> **El determinismo decide qué está PERMITIDO y qué está ROTO; el LLM/PM decide qué hacer dentro de ese espacio.
> La autonomía NO viene de correr el LLM más seguido — viene de que las reglas sin-juicio se ejecuten SOLAS.**

Dos corolarios que afinan las IAs:
- **Lo que falta es un "sistema nervioso":** poller que detecta cambios → cola que encola trabajo → despertador
  que convoca al PM. Los distintos orígenes (evento de posición, revalidación, pedido del PM, pedido del
  operador, oportunidad) son **la misma cola** vista de distintos lados. El candado y el bucle de deep son la
  misma pieza: lo que el gate rechaza por falta de ficha **vuelve a la cola como pedido**.
- **Las salidas no se vuelven crujientes automatizando el precio, sino con el PRE-COMPROMISO:** la consecuencia de
  un falsador se escribe junto con la tesis, en frío, y no se negocia cuando la posición pierde.

Evolución: de un *sistema de investigación* (el comité analiza, el PM elige) a un *sistema de gestión de capital
que dirige su propia investigación*.

## 1. Arquitectura: 5 componentes de infra, CERO agentes nuevos
Se conservan comité, PM, Auditor y fichas. Se agregan 5 piezas (varias son tablas/funciones sobre lo existente):

| Componente | Responsabilidad |
|---|---|
| **Scheduler/Pipeline** | Encadenado diario idempotente + ciclos (semanal + por evento), con control de vida |
| **Event Monitor (poller)** | Poll EDGAR por CIK (y fuentes no-US) de filings de posiciones/banca/cola |
| **Research Queue** | Una sola cola de deep con origen + prioridad, drenada a DIARIO con presupuesto por carril |
| **Budget Manager** | Autoriza y contabiliza; reserva el costo máximo ANTES de cada deep |
| **Decision Gate** | El candado: impide incorporar riesgo no autorizado (ya existe parcialmente) |

## 2. El candado (Decision Gate) — fail-closed, en el gate, no en el prompt
Toda orden que **abra o aumente** una posición en acciones se rechaza salvo que **AL MOMENTO DEL GATE** se cumplan:
1. **Ficha VIGENTE** (ni EN_REVISION ni VENCIDA).
2. **Zona COMPRA**, recalculada con el precio del momento. *(También para AUMENTAR una posición propia — la banca
   filtra por COMPRA pero las posiciones no; sin esto el PM podría aumentar en MANTENER/SALIDA.)*
3. **Datos limpios:** precio del último cierre o más fresco; share count con fecha ≥ último filing periódico;
   ningún filing de dilución sin procesar (424B/S-1/S-3/8-K 3.02); ninguna corporate action pendiente; **pipeline
   del día corrido**.

- La orden sale con **precio límite = techo de la zona COMPRA** ("comprar hasta $X"). Cierra el hueco decisión↔ejecución.
- **El gate RELEE estado y precio; no confía en el packet** (si salió un filing entre la decisión y la orden, no
  aprueba con estado viejo).
- Distingue rechazo que **requiere investigación** (SIN_FICHA_VIGENTE, REFRESH_REQUIRED → crea la solicitud de
  deep) de uno que solo **impide operar** (FUERA_DE_ZONA, DATOS_SUCIOS, violación IPS → no dispara deep).
- **Asimétrico: las REDUCCIONES nunca se bloquean** (risk-off; solo chequeos operativos: identidad, tenencia, no
  abrir short, factibilidad). En rotación, cada pata se evalúa sola (si la venta pasa y la compra se rechaza, queda caja).
- **🔴 DEAD MAN'S SWITCH (el candado DEPENDE del poller vivo):** cada etapa del pipeline escribe su timestamp; si
  el pipeline **no corrió en 26h**, el gate pasa a **fail-closed para compras** + alerta al operador. Un candado
  sin poller vivo es decorativo (si el poller muere, toda ficha queda VIGENTE para siempre).

**Sin excepción para promediar a la baja con ficha vencida** (el caso más peligroso: la ficha vence por un 10-Q y
el precio cae por ese mismo 10-Q). La posición EN_REVISION va a P0 (SLA 48h); recién con la ficha fresca en COMPRA
se promedia. **ETFs de estacionamiento: exentos, con lista blanca explícita en el IPS.** Cambios involuntarios
(spin-off, split) no cuentan como aumentar; ejercer derechos de suscripción sí.

## 3. Cadencia: un pipeline diario encadenado + PM semanal + despertares por evento
| Cuándo | Qué | Costo |
|---|---|---|
| **Cada hora** (también fuera de horario — muchos 8-K salen post-cierre) | poller de filings de posiciones/banca/cola | $0 |
| **Diario, post-cierre** (encadenado idempotente) | 1) cerrar poller · 2) latido (zonas + transiciones) · 3) **drenar la cola** · 4) zonas de fichas nuevas · 5) condiciones de despertar · 6) **PM si corresponde** | $0 + deeps + PM ocasional |
| **Semanal** | revisión completa del PM aunque no haya alertas; encolar top-N de oportunidad | PM + deeps |
| **Mensual** | reporte al operador: costo y SLA por carril, acierto por origen, salidas por tier | $0 |

**El orden importa:** si el PM corre antes del drenaje, decide con fichas viejas. **Máximo 1 despertar del PM por
día** (debounce), además del semanal. El packet de despertar dice que **no hacer nada es una respuesta válida**
(anti sesgo de acción).

**Disparadores — 8-K por número de ítem, determinista, $0:**
- **Regla dura (§6 tier A/B):** 1.03 quiebra · 4.02 non-reliance · 4.01 renuncia de auditor con desacuerdos.
- **Revisión P0/P1:** 2.02 resultados · 2.06 impairment · 5.02 salida CEO/CFO · 2.04 aceleración de deuda · 3.01
  deslistado · 1.01/1.02 contratos materiales.
- **Dilución:** 3.02 / S-1 / S-3 / 424B → recalcular share count + zona EL MISMO DÍA.
- **Triage con modelo chico:** 8.01 / 7.01 → si toca la tesis, a P1.
- **10-Q/10-K de una posición → EN_REVISION → P0.** **Anti-doble-deep:** el 2.02 (earnings, semanas antes del
  10-Q) dispara el deep; cuando llega el 10-Q del mismo período, alcanza un **diff-check del Verificador** (going
  concern, factores de riesgo, hechos posteriores, share count).
- **Emisores extranjeros:** mapa de eventos por **tipo de emisor** (20-F/40-F/6-K, SEDAR+) + TTL de respaldo (§7),
  si no, nunca vencen.
- **Caída fuerte sin filing que la explique** (−20% en el día o −30% desde el último deep) → **deep P1 de
  revalidación, NO venta** (el mercado puede saber algo que los filings aún no dicen).
- **Histéresis** (anti-flapping): la alerta de transición entra en el umbral y sale a umbral + 3-5% (o dos cierres
  seguidos). No toca el cálculo de zonas del doc 80.

**Corrida semanal:** el PM re-evalúa la cartera como un todo. La pregunta no es *"¿sigue siendo buena?"* sino
**"si hoy tuviera este capital libre, ¿seguiría eligiendo esta posición frente a las demás oportunidades?"**
(costo de oportunidad, neto de fricción). Puede terminar sin operar.

## 4. El bucle REQUEST_DEEP (el PM dirige su investigación) — drenaje diario, sin 2ª pasada
El PM gana la acción **SOLICITAR_DEEP(ticker)**. **NO hay segunda pasada en el mismo ciclo** (reentrada compleja
para ahorrar un día, en una estrategia de PACIENCIA): como la cola se **drena a diario**, el pedido tarda un día
hábil y despierta al PM al día siguiente. Flujo:
1. El PM emite SOLICITAR_DEEP, o intenta COMPRAR y el gate lo rechaza por SIN_FICHA_VIGENTE (crea la misma
   solicitud, consume el mismo cupo).
2. **Dedup:** si ya hay ficha VIGENTE, no se gasta deep (se convierte en alerta de precio: "X vigente en MANTENER;
   COMPRA desde $Y"). Si ya hay solicitud activa, se suma el origen.
3. El **drenaje de esa noche** corre el deep dentro del cupo del carril.
4. Si la ficha nueva cae en COMPRA → despierta al PM al día siguiente. Si cae en otra zona → va al **radar** con su
   precio de compra + una línea de feedback al PM; el latido avisa si después cruza a COMPRA.

- **El PM solo pide nombres de SU packet** (oportunidades/mapa/banca/radar/posiciones). **NO pide tickers de
  afuera** (un LLM proponiendo tickers de memoria trae sesgo a nombres populares, datos viejos, tickers mal
  resueltos). Los externos los trae **el operador** (§5).
- **Pedido CIEGO:** el motivo del PM se guarda para auditoría, pero el Analista NO lo ve (si el comité sabe que el
  PM quiere el nombre, el deep se vuelve una justificación).
- **Cupo propio:** 2-3 pedidos del PM/semana; lo no usado pasa a oportunidad, **nunca al revés** (lo sistemático no
  se queda sin presupuesto por lo discrecional). **Cooldown 90 días:** un nombre analizado que no quedó en COMPRA
  no se re-pide, salvo filing nuevo o zona sombra en COMPRA.

**Una sola Research Queue con prioridad** (el origen NO determina la calidad): **P0** evento de posición ·
**P1** revalidación / pedido del PM / pedido del operador · **P2** oportunidad. SLA: P0 48h, P1 72h. Dedup por
ticker (se consolida y sube prioridad; no se investiga dos veces). Cierre ATÓMICO de la solicitud (re-correr el
pipeline no cobra dos veces el mismo deep).

## 5. Input del operador — mapa ≠ universo elegible; salta la SELECCIÓN del discovery, no sus FILTROS
El discovery hace dos cosas: **encontrar** candidatos y **filtrar** basura (fuentes primarias, invertibilidad). La
atención del operador reemplaza la PRIMERA función, no la segunda. Comando: **analizar TICKER [bolsa]**. Flujo:
1. **Resolver la entidad:** ticker → CIK/ISIN + bolsa. Si es ambiguo, confirmar con el operador antes de gastar
   (un deep sobre la entidad equivocada = hasta $5 y una ficha falsa).
2. **Admisión determinista $0:** bolsa permitida, filings primarios accesibles, liquidez + market cap dentro del
   IPS. Si falla un límite del IPS → igual se puede analizar, pero la ficha queda **"no invertible bajo IPS"** y el
   gate la bloquea (el PM no puede ampliar el IPS por iniciativa propia).
3. **Carril operador en la cola, P1** (3-5/semana).
4. **Deep normal, CIEGO al origen** (ni el Analista ni el PM saben que lo pidió el operador — anti sesgo de autoridad).
5. **Clasificación OBLIGATORIA** en el deep: sector, cuello, factores del IPS. Un nombre fuera del mapa no los trae,
   y sin ellos el gate no puede calcular los caps → **fail-closed**.
6. Después es una ficha más: universo extendido, `origen=operador`, latido diario, el mismo candado.

**Tag de origen** (DISCOVERY / PM / OPERADOR / EVENT): atribución (el paper compara nombres del operador vs
discovery con la misma vara) + feedback al discovery (un nombre del operador que pasa el deep y el discovery no
había encontrado = fallo de recall, se registra).

## 6. Salidas — regla para lo objetivo/binario/asimétrico; juicio para lo continuo/ruidoso
**Lo que las vuelve crujientes es el PRE-COMPROMISO + disparar por CAMBIO, no por nivel.** En small caps pre-revenue
going concern / material weakness / avisos de deslistado son endémicos: cada ficha guarda una **línea base** de
esas banderas al deep, y la regla dispara solo si aparece algo que NO estaba.

| Señal | Tipo | Acción |
|---|---|---|
| 4.02 non-reliance/restatement · quiebra (1.03) · renuncia de auditor con desacuerdos · suspensión SEC / fraude | **A — regla** | **Salida total.** Advisory: VENDER urgente (canal propio). Paper: ejecuta en la apertura siguiente con slippage realista |
| Going concern NUEVO (ausente en la línea base) | **B — regla** | recorte **50%** + deep P0 |
| Falsador DURO cumplido | **B — regla** | la consecuencia pre-comprometida (SALIDA o RECORTE_50) + deep P0 |
| Zona SALIDA en una posición | **C — juicio guiado** | deep P1 que revalida el bull; si la ficha fresca confirma SALIDA → recorte 1/3, y otro 1/3 si sigue así 20 ruedas después |
| Falsador BLANDO · material weakness nueva · salida CEO/CFO · otro cambio de auditor · 8-K de triage · aviso de precio mínimo | **C — juicio con escalada** | despierta al PM con **respuesta obligatoria**: recortar, o mantener con motivo escrito (queda para el Auditor) |
| Zona RECORTE | **D — información** | decide el PM; el cap de peso del IPS hace el resto |
| Caída fuerte sin evento | **revisión** | deep P1, sin venta |

**Por qué SALIDA no es venta automática:** el retorno esperado es negativo incluso en el bull (mantener contradice
el método), pero el riesgo real es que el bull esté viejo → revalidar primero, recortar después cubre los dos riesgos.

**Falsadores estructurados (la pieza clave):** `{métrica, fuente (tag XBRL | campo | tipo de evento), operador,
umbral, fecha_límite, tipo: DURO|BLANDO, consecuencia: SALIDA|RECORTE_50|REVISIÓN, línea_base}`.
- El **Bear** los escribe; el **Verificador RECHAZA la ficha** si un falsador DURO no es verificable por máquina.
- **Toda ficha lleva ≥1 falsador DURO con fecha límite** (corta la plata muerta: el catalizador que nunca llega).
- Numéricos → XBRL del filing nuevo, $0. Textuales (going concern) → modelo chico; dispara solo si devuelve la
  **cita literal** y esa cita aparece por coincidencia exacta en el filing.
- **Solo se AGREGAN:** borrar o aflojar un falsador exige motivo escrito + firma del Verificador (anti "mover el
  arco"; se registra la deriva del valor justo por nombre).
- **Shock sectorial:** los tiers B y C se agrupan en UN solo despertar del PM, con vista de cartera.
- **Advisory que nadie ejecuta:** canal propio para tier A + registro de recomendado vs ejecutado.

## 7. Revisión de posiciones — evento + TTL de respaldo + deep en FRÍO anual
No se toca la vigencia por evento del doc 80. Se agregan tres capas:
- **Por evento (principal):** deep incremental con cada resultado trimestral (§3).
- **TTL de respaldo:** período de reporte del emisor **+ 60 días** desde el último deep (~150d trimestrales —
  cubre el hueco Q3→10-K; ~240d semestrales). Si el poller funciona, casi nunca dispara. Vencido → a la cola; si
  no se cumple por presupuesto → **se bloquean nuevos aumentos** (sin cambiar la vigencia formal).
- **Deep en FRÍO anual (con el 10-K):** el Analista escribe **SIN ver la ficha anterior**; después se compara. Si
  el valor justo difiere **>25%** o cambian los falsadores → el Verificador reconcilia (estado de ficha que EXIGE
  reconciliación, no una línea de log) + el PM recibe la bandera. **Es el Verificador ciego del doc 83 aplicado en
  el TIEMPO** — el antídoto contra la tesis congelada por anclaje del refresh incremental.

Metadata operativa (`position_review`: `last_deep_at`, `tipo_deep` incremental|frío, `last_pm_review_at`,
`next_deep_due`, `review_status`). **Fichas de banca (fuera de cartera): sin TTL** — vencen con el próximo filing →
zona sombra; se re-analizan solo si la zona sombra entra en COMPRA o las piden el PM/operador. El gasto queda
proporcional a lo accionable.

## 8. Presupuesto — por FUNCIÓN, con budget manager
Un único Budget Manager (ejecutado + reservado + disponible); **reserva el costo máximo ANTES de cada deep.**
Política inicial: **~60% research regular · ~20% reserva de eventos críticos · ~20% PM+coordinación+triage.** P0 sin
tope pero presupuestado por temporada (los earnings se amontonan en ~3 semanas); P2 se frena solo. Un incidente
crítico usa la reserva + el regular no comprometido; si no alcanza → **se escala al operador (el límite no se rompe
en silencio).** No asumir $0.70/deep: si el real ronda $5, el mantenimiento se come casi todo.

## 9. El ciclo operativo (run_cycle) — con las salvaguardas
```
cerrar_poller() → latido_zonas_y_transiciones() → drenar_cola_dentro_de_presupuesto()
→ zonas_de_fichas_nuevas() → evaluar_condiciones_de_despertar()
if hay_motivo_de_despertar() or es_semanal():
    packet = build_pm_packet()          # incluye changes_since_last_decision + radar
    decision = pm.decide(packet)
    execute_validated_orders(decision)  # gate RELEE estado/precio; persistencia ANTES de operar
    enqueue_research_requests(decision)
persist_cycle_state()
```
**Obligatorio:** persistencia antes de operar · recuperación tras fallo · lock de ejecuciones simultáneas ·
anti-duplicados (cierre atómico de solicitudes y órdenes). *Un scheduler que duplica órdenes al reiniciar es peor
que uno manual.* **Packet `changes_since_last_decision`:** new_buy_candidates · zone_transitions · material_events ·
completed_research · rejected_orders · unresolved_alerts · overdue_reviews · **radar** (hasta 10 fichas VIGENTES
fuera de COMPRA, por distancia al precio de compra). *La ficha es la memoria de la empresa; el ledger de decisiones
es la memoria del PM; el packet conecta ambas.*

## 10. Orden de implementación (3 fases)
- **F1 — Autonomía mínima (P0):** pipeline diario encadenado + **poller EDGAR con control de vida (dead man's
  switch)** + **candado fail-closed en el gate** + **cola única con presupuesto por carril**. *(Sin poller vivo el
  candado es decorativo; por eso van juntos.)* → *BORJA empieza a correr sin intervención humana.*
- **F2 — Salidas y despertar:** **despertador del PM** (debounce 1/día) + **reglas de salida duras (tier A/B)** +
  **falsadores estructurados** con línea base en las fichas nuevas + SOLICITAR_DEEP + input del operador. → *las
  salidas se vuelven crujientes sin depender de que el PM esté corriendo.*
- **F3 — Calidad y costo:** histéresis en alertas · **deep en frío anual** · triage LLM de 8-K (8.01/7.01) ·
  métricas por carril y origen · revisiones 90/180d. → *se calibra con datos del paper trading.*

## 11. Tests de aceptación + métricas
1. Empresa sin ficha no se compra aunque el PM insista. · 2. Posición vencida no se aumenta. · 3. Reducción no se
bloquea por tesis vencida. · 4. Filing invalidante bloquea compras antes de ejecutar (gate relee). · 5. Ticker
externo del operador puede terminar en ficha elegible. · 6. El PM pide un deep y reconsidera al día siguiente. ·
7. Evento crítico convoca al PM fuera del semanal. · 8. Deep fallido NO deja ficha falsamente vigente. · 9.
Reinicio no duplica compras ni deeps. · 10. Pipeline sin correr 26h → fail-closed. · 11. Corrida sin oportunidades
termina sin operar.

**Métricas:** compras sin ficha vigente (=0) · tiempo evento→revisión · alertas críticas sin resolver · costo
research/mes y SLA por carril · deeps que cambian decisiones · % de falsadores DUROS verificables por máquina ·
turnover (despertadas vs semanales) · acierto por origen · retorno/drawdown/benchmark · timestamps de info +
ejecución con gap/slippage vs volumen.

## 12. Parámetros iniciales (a calibrar con el paper) + qué NO construir
Pedidos del PM 2-3/sem (lo no usado → oportunidad) · tickers del operador 3-5/sem · cooldown PM 90d · SLA P0 48h /
P1 72h · despertares ≤1/día · **control de vida del pipeline 26h → fail-closed** · histéresis 3-5% o dos cierres ·
revalidación por caída −20%/día o −30% desde el último deep · TTL = período de reporte + 60d · deep en frío anual ·
divergencia frío-vs-incremental >25% exige reconciliación · recorte por SALIDA confirmada 1/3 + 1/3 a 20 ruedas ·
recorte tier B 50%.

**NO construir (sobreingeniería):** 2ª pasada del PM en el mismo ciclo · stops por precio (la salida por valuación
ya es la zona SALIDA) · pedidos del PM fuera de su packet · score de urgencia para nombres sin ficha (sin ficha no
hay zona) · agente supervisor del PM (ya está el Auditor) · PM cada hora · comité diario de todas las posiciones ·
deep periódico de toda la banca · multiagente de priorización · orquestación distribuida · ampliar el IPS por
iniciativa del PM.
