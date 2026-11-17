# Doc 85 — Diseño CERRADO: el PM autónomo (ciclo operativo)

> **Canónico.** Sucesor del doc 84 (brief). Convergido por **IA1 + IA2** (2026-11-17, convergencia casi total) +
> decisiones del operador. Cierra el COMPORTAMIENTO del PM: cuándo mira, qué puede comprar, qué pasa si quiere
> algo sin analizar, cuándo vende, cada cuánto. **A IMPLEMENTAR en 3 etapas.** No re-abre doc 80 (ficha viva) ni
> doc 83 (equity bridge). Relacionado: [[84]], doc 80, doc 83.

## 0. El principio que unifica todo
> **El determinismo decide qué está PERMITIDO y qué está ROTO; el LLM/PM decide qué hacer dentro de ese espacio.
> La autonomía del PM NO viene de correr el LLM más seguido — viene de que las reglas que no admiten juicio se
> ejecuten SOLAS, para reservar el juicio donde sí importa.**

La evolución clave: de un *sistema de investigación* (el comité analiza, el PM elige) a un *sistema de gestión de
capital que dirige su propia investigación* (el PM administra la cartera, detecta qué conocimiento le falta y
asigna recursos para adquirirlo). La ficha viva (doc 80) resolvió *conservar* el conocimiento; el **scheduler**
resuelve *cuándo usarlo*; **REQUEST_DEEP** resuelve *cómo ampliarlo* según la necesidad de la cartera.

Determinismo (reglas que se ejecutan solas): **candado · event watcher · scheduler · freeze de aumentos en
señales duras.** Juicio (el espacio de decisión): **el deep, el comité, qué comprar/cuánto, las salidas
graduables.**

## 1. Arquitectura: 5 componentes de infra, CERO agentes nuevos
Se conservan comité, PM, Auditor y fichas. Se agregan 5 piezas (varias son tablas/funciones sobre lo existente):

| Componente | Responsabilidad |
|---|---|
| **Scheduler** | Ejecuta el latido diario y los ciclos autónomos (semanal + por evento) |
| **Event Monitor** | Detecta filings/precio/eventos que requieren atención |
| **Research Queue** | Centraliza y prioriza los pedidos de deep (una sola cola) |
| **Budget Manager** | Autoriza y contabiliza el costo; reserva antes de cada deep |
| **Decision Gate** | Impide incorporar riesgo no autorizado (el candado) — ya existe parcialmente |

## 2. El candado (Decision Gate) — determinista, no en el prompt
**Ninguna posición individual se abre ni se aumenta sin ficha VIGENTE, verificada y con datos críticos usables.**
Regla dura en el gate (devuelve NO_TRADE + motivo en el log), no una sugerencia que el PM overridea con texto.

| Estado de la ficha | Abrir | Aumentar | Reducir | Cerrar |
|---|---|---|---|---|
| VIGENTE + zona COMPRA | ✅ | ✅ | ✅ | ✅ |
| VIGENTE + otra zona | ❌ | ❌ | ✅ | ✅ |
| EN_REVISION | ❌ | ❌ | ✅ | ✅ |
| SIN ficha | ❌ | ❌ | ✅ | ✅ |
| Datos críticos inválidos (`datos_conflicted`) | ❌ | ❌ | ✅ | ✅ |

- La zona COMPRA **habilita** una decisión, no la ordena. Toda compra sigue sujeta al IPS.
- **Sin excepción para promediar a la baja.** Una caída del 30% puede ser oportunidad o una tesis muerta —
  justamente ahí hay que exigir ficha vigente. Si el PM lo quiere igual, dispara REQUEST_DEEP (§4), no la compra.
- **Re-chequeo point-in-time en la EJECUCIÓN:** se valida la info disponible AL AUTORIZAR, no la del packet. Si
  aparece un filing entre la decisión del PM y la orden, **la autorización de compra se invalida** hasta resolver.
- El gate distingue rechazo que **requiere investigación** (DEEP_REQUIRED / REFRESH_REQUIRED → a la cola) de uno
  que solo **impide operar** (NO_MARGIN_OF_SAFETY / violación IPS → no dispara deep).
- **Asimétrico: las REDUCCIONES nunca se bloquean** (risk-off). Solo chequeos operativos básicos (identidad,
  tenencia disponible, no abrir short accidental, factibilidad). El estacionamiento en ETFs es carril aparte (no
  es una vía para eludir el candado).

## 3. Cadencia: vigilar / investigar / decidir (tres relojes distintos)
| Actividad | Frecuencia | Quién | Costo |
|---|---|---|---|
| **Latido** (precios, zonas, pesos, IPS, alertas) | diario | código | $0 |
| **Vigilancia de eventos** (filings/resultados/precio) | cada ~60 min en sesión + barrido | Event Monitor | $0 |
| **PM-LLM** (decidir) | semanal + por evento accionable | PM | medio |
| **Comité** (deep/refresh de fichas) | semanal + por evento material / pedido prioritario | comité | alto |

**Disparadores (determinista → LLM):**
- nuevo precio → recalcular zona (sin LLM); entra a COMPRA → actualizar banca (+ PM si es accionable).
- RECORTE → alerta + PM; **SALIDA → alerta prioritaria + revisión obligatoria** (no auto-trim).
- nuevo 10-Q/10-K → invalida vigencia (→ EN_REVISION, comité por prioridad).
- **8-K potencialmente material → clasificar + BLOQUEAR compras preventivamente** mientras se evalúa (triage/comité).
- falsador confirmado → **freeze de aumentos** + PM urgente.
- caída abrupta → buscar causa (triage); pedido del operador → a la cola.
- **El 8-K es el hueco que hace sentir muerto al PM: esperar al comité semanal para procesarlo es tarde.** Por
  eso la corrida **extraordinaria** por evento crítico (acotada: ¿la nueva info exige una decisión de cartera?).
- No todo 8-K amerita deep ni todo salto de precio significa que la tesis cambió: el 1er paso es resolver si hay
  info nueva que afecte supuestos económicos / riesgo / supervivencia / valuación. Emisores extranjeros: sus
  reportes equivalentes.

**Corrida semanal:** el PM re-evalúa la cartera como un todo aunque no haya alertas. Elige los deeps con **mayor
capacidad de mejorar/proteger el portfolio por presupuesto restante** (no una cantidad fija). Puede terminar sin
operar. **La pregunta semanal no es "¿sigue siendo buena?" sino "si hoy tuviera este capital libre, ¿seguiría
eligiendo esta posición frente a las demás oportunidades?"** (costo de oportunidad, neto de fricción/impuestos).

## 4. El bucle REQUEST_DEEP (el PM dirige su investigación)
El PM gana una acción: **REQUEST_DEEP** (no es intención de compra vinculante; es "vale la pena investigar esto").
Flujo: 1ª pasada del PM → REQUEST_DEEP (con hipótesis + qué decisión cambiaría) → asignación (elegibilidad +
prioridad + presupuesto) → comité (investiga INDEPENDIENTE) → ficha → 2ª pasada del PM (compra / observa /
descarta). **Máx 2 pasadas por ciclo; la 2ª no genera otro deep inmediato (anti-recursión).** Las reducciones de
la 1ª pasada NO esperan al deep.

**Una sola Research Queue con prioridad** (el origen NO determina la calidad), con reserva para incidentes de
cartera que **protege la capacidad de discovery** (mientras no haya incidentes, se conserva presupuesto para
descubrir nombres nuevos):

| Prioridad | Investigación |
|---|---|
| **P0** | riesgo crítico en una posición |
| **P1** | actualización material de una posición existente |
| **P2** | oportunidad accionable del PM (REQUEST_DEEP) |
| **P3** | oportunidad fuerte de discovery |
| **P4** | investigación exploratoria |

Config inicial: 2 pedidos del PM/ciclo · 1 deep inmediato por iniciativa del PM · 1 investigación pendiente por
ticker (dedup: si dos piden el mismo, se consolida y sube prioridad) · vigencia de un pedido exploratorio 14 días
· tickers fuera del mapa permitidos. Los eventos críticos de posiciones no consumen el cupo exploratorio.

**Deep inmediato (misma vuelta) solo si:** hay presupuesto + la empresa es elegible + la investigación tiene
consecuencia plausible sobre una decisión actual (sustituir una posición deteriorada, desplegar caja estacionada,
resolver incertidumbre de una posición). Un nombre nunca analizado **no puede estar "en zona COMPRA"** — a lo
sumo hay indicios preliminares de valuación atractiva. El comité investiga con INDEPENDENCIA del deseo del PM
(anti confirmation-bias).

## 5. Input del operador — mapa ≠ universo elegible
- **El mapa identifica DÓNDE buscar; el universo elegible define EN QUÉ se puede invertir.** El mapa es discovery,
  no una frontera rígida. Una buena empresa de fuera del mapa no se pierde.
- El operador incorpora cualquier ticker, pero **no puede declararlo apto para comprar sin que pase los gates.**
  Flujo: ticker → validación de identidad/elegibilidad (instrumento/mercado/liquidez/mandato) → validación de
  fuente primaria → cola → comité → ficha. **Salta el DISCOVERY, no el comité ni la validación primaria ni el IPS.**
- Tres comandos: **WATCH X** (observación + scoring) · **RESEARCH X** (deep en el próximo cupo) · **REVIEW X**
  (reconsiderar una tesis existente). El operador prioriza presupuesto, NO convierte eso en compra automática.
- **Fuera del mapa** = se incorpora sin problema. **Incompatible con el IPS** = se puede investigar pero no comprar
  sin un cambio EXPLÍCITO del mandato. **El PM no puede ampliar el IPS por iniciativa propia.**
- Campo `origin` en la ficha/request (DISCOVERY / DESEO_PM / OPERADOR / EVENT) → se audita el desempeño por origen.

## 6. Salidas: automatizar la OBLIGACIÓN de decidir, no la decisión
No se introducen stops automáticos de precio por defecto (cortarían al ganador por ruido). Se automatiza **el
deber de actuar**, no la orden.

| Evento | Regla automática (determinista) | Decisión del PM |
|---|---|---|
| Zona RECORTE | alerta + revisión | mantener o recortar |
| **Zona SALIDA** | **revisión obligatoria prioritaria** (NO auto-trim) | justificar mantener / reducir / salir |
| Falsador CONFIRMED | **freeze de aumentos** + revisión urgente | recortar / salir / mantener justificado |
| Going concern | freeze de aumentos + revisión crítica | evaluar supervivencia (no siempre = liquidar) |
| Material weakness | clasificar gravedad + freeze si afecta datos críticos | evaluar impacto |
| Límite IPS excedido | bloquear ops que agraven el exceso | plan de reducción |
| Stop duro definido en el IPS | aplicar regla preautorizada | **no puede revocarla** |

- **Zona SALIDA invierte la carga de la prueba:** el PM ya no justifica por qué comprar, sino **por qué seguir
  manteniendo**. Si mantiene, exige 3 campos: razón explícita · condición que lo haría vender · fecha/evento de
  reconsideración. Si cree que cambió la valuación, no la modifica solo: pide un deep.
- **Anti-racionalización:** falsador CONFIRMED → freeze + PM urgente → *reducir/salir* (ejecuta sin deep nuevo) o
  *mantener* (justificación + **Auditor** + revisión obligatoria). Si el PM no responde / falla / sin presupuesto →
  la alerta queda ABIERTA, el freeze se mantiene y **se escala al operador.** El sistema NO transforma una falla
  del modelo en una decisión implícita de mantener.
- **Falsadores estructurados** (id, condición, deadline, evidencia, severidad, estado, `action_on_breach`). Tipos:
  hito / económico / estructural / supervivencia. **Evidencia ambigua → SUSPECTED, no CONFIRMED** (un error de
  extracción no puede volverse una orden de liquidación).

## 7. Revisión de posiciones — un reloj de MANTENIMIENTO (no otro de valuación)
No se toca la vigencia por evento del doc 80. Se agrega metadata operativa para que **ninguna posición quede
olvidada** (detecta "deuda de investigación"):

| Revisión | Frecuencia | Quién | Costo |
|---|---|---|---|
| precio / zona | diaria | código | $0 |
| riesgos / falsadores | continua por evento | código + triage | bajo |
| conveniencia de mantener | semanal | PM | medio |
| revisión ligera de tesis | cada 90 días | PM | bajo |
| deep-refresh | evento material **o 180 días** sin update | comité | alto |

`position_review`: `last_deep_at`, `last_pm_review_at`, `last_thesis_review_at`, `next_deep_due`, `review_status`.
A los **180 días sin deep → entra OBLIGATORIAMENTE a la cola**; si no se cumple por presupuesto → **se bloquean
nuevos aumentos** (sin cambiar el estado formal de vigencia). Las **posiciones tienen prioridad de mantenimiento**
sobre la banca; una ficha vencida de un nombre lejos de sus zonas puede quedar meses sin refrescar (no perjudica).
El **deep-refresh por TTL puede ser más LIVIANO** que el inicial ("deep de mantenimiento": verifica que los
falsadores siguen observables + no hay riesgos nuevos + la tesis no fue superada por los hechos).

## 8. Presupuesto — por FUNCIÓN, no por agente
Un **único Budget Manager** (costo ejecutado + reservado + disponible). **Reserva el costo máximo ANTES de cada
deep.** Política inicial sobre el tope mensual: **~60% research regular · ~20% reserva de eventos críticos · ~20%
PM+coordinación+triage.** Un incidente crítico puede usar la reserva + el regular no comprometido; si no alcanza →
**se escala al operador (el límite no se rompe en silencio).** No asumir $0.70/deep: si el real ronda $5, el
mantenimiento puede comerse casi todo. La cola ordena por riesgo de cartera / potencial de cambiar una asignación
/ urgencia / calidad preliminar — sin un cálculo sofisticado de valor esperado.

## 9. El ciclo operativo (run_cycle) — con las salvaguardas
```
update_market_data() → detect_and_register_events() → update_fichas_and_zones() → invalidate_outdated_fichas()
if needs_portfolio_decision(trigger):
    execute_priority_research_within_budget()
    packet = build_pm_packet()          # incluye changes_since_last_decision
    decision = pm.decide(packet)
    execute_validated_orders(decision)  # gate point-in-time + persistencia ANTES de operar
    enqueue_research_requests(decision)
    if actionable_deep_available_within_budget():   # 2ª pasada, UNA sola
        execute_one_requested_deep(); refresh_market_and_event_state()
        packet = build_pm_packet(); decision = pm.decide(packet)
        execute_validated_orders(decision); enqueue_research_requests(decision)
persist_cycle_state()
```
**Obligatorio:** persistencia antes de operar · recuperación tras fallo · lock de ejecuciones simultáneas ·
anti-duplicados. *Un scheduler que duplica órdenes al reiniciar es peor que uno manual.*

**Packet incremental — `changes_since_last_decision`:** new_buy_candidates · zone_transitions · material_events ·
completed_research · rejected_orders · unresolved_alerts · overdue_position_reviews. *La ficha es la memoria de la
empresa; el ledger de decisiones es la memoria del PM; el packet conecta ambas.*

## 10. Orden de implementación (3 etapas)
- **Etapa 1 — Autonomía mínima (P0, primero):** Scheduler (diario + semanal) · latido de todas las fichas · **gate
  duro de compras** · **Event Monitor de filings (8-K/10-Q)** · alertas persistentes + corrida extraordinaria del
  PM · Budget Manager básico. → *BORJA empieza a funcionar sin intervención humana.*
- **Etapa 2 — Autonomía de investigación:** REQUEST_DEEP · Research Queue centralizada con prioridad · 2ª pasada
  del PM · tickers del operador (WATCH/RESEARCH/REVIEW) · reservas de presupuesto. → *el PM decide qué conocimiento
  necesita adquirir.*
- **Etapa 3 — Gestión madura del riesgo:** falsadores estructurados (OK/SUSPECTED/CONFIRMED) · protocolos de salida
  + escalamiento · revisiones periódicas (90/180d) · clasificación fina de eventos · métricas del sistema. →
  *BORJA identifica y corrige sus propios errores.*

## 11. Tests de aceptación (criterios, a implementar)
1. Una empresa sin ficha no puede comprarse aunque el PM insista.
2. Una posición vencida no puede aumentarse.
3. Una reducción no se bloquea por tesis vencida.
4. Un filing invalidante bloquea compras antes de ejecutar (point-in-time).
5. Un ticker externo puede terminar en una ficha elegible.
6. El PM puede pedir un deep y reconsiderar su decisión.
7. Un evento crítico convoca al PM fuera del ciclo semanal.
8. Un deep fallido NO deja una ficha falsamente vigente.
9. Un reinicio no duplica compras ni investigaciones.
10. El sistema respeta el presupuesto máximo (escala, no rompe en silencio).
11. Una corrida sin oportunidades puede terminar sin operaciones.

**Métricas de salud:** compras sin ficha vigente (= 0) · tiempo evento→revisión · alertas críticas sin resolver ·
costo de research/mes · deeps que cambian decisiones · oportunidades válidas no atendidas · turnover (hiperactividad)
· retorno/drawdown/benchmark · timestamps de disponibilidad de info + ejecución con costos/slippage razonables.

## 12. Qué NO se construye (sobreingeniería)
Agente supervisor del PM (ya está el Auditor) · PM corriendo cada hora · comité diario de todas las posiciones ·
deep periódico de TODA la banca · multiagente de priorización de deeps (una cola ordenada alcanza) · stops de
precio dinámicos (contradicen la filosofía) · orquestación distribuida · auto-trim por % arbitrario · ampliar el
IPS por iniciativa del PM.
