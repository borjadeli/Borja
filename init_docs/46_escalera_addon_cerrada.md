# 46 — Escalera de add-on CERRADA (underwriting escalonado)

> **CERRADO** (2026-08-28). Síntesis de doc 45 (IA1 + IA2 convergieron CASI TOTAL — la convergencia más fuerte de
> todas las triangulaciones). Bloque 4.2. La última decisión de método abierta. Génesis:
> [[rebalanceo-determinismo-juicio]] §3. **Reframe central: NO es un módulo nuevo — es UNA variable (`stage`) +
> una tabla de triggers hasheados; todo lo demás REUSA el `min()` de sizing existente.**

## 0. El reframe (las dos IAs, idéntico)

**La "escalera de add-on" como módulo separado es la abstracción EQUIVOCADA.** No hay decisión de "¿agrego?" (esa
2ª superficie discrecional es donde entra el hype). Hay una **reconciliación** entre el peso actual y un target
autorizado por evidencia:
```
LIVE_CAP(t) = min(cap_surv/tier, cap_val(P_t), cap_liq, cap_arq)     # el techo de siempre
w_target(t) = STAGE_FRACTION[stage] × LIVE_CAP(t)                    # la escalera escala el techo
```
`stage ∈ {0,1,2,3}` sube **SOLO por hechos citados** (triggers pre-registrados). **Lo único genuinamente nuevo a
construir es `stage` + su tabla de triggers hasheados.** Esto da 3 cosas GRATIS (IA1): (1) la **martingala queda
prohibida sin regla extra** — si el precio cae y nada cambió, `cap_val` sube pero `STAGE_FRACTION[stage]` sigue
siendo el binding; no podés promediar a la baja porque el stage no subió; (2) el **arco no se mueve** (mismo
techo, misma tabla versionada); (3) **no duplicás valuación** — el hito entra como HECHO (RPO/burn nuevos),
NUNCA como premio por cumplir el trigger. El trigger es un GATE, jamás un input al reverse-DCF (evita doble-conteo).

## 1. Veredicto: (a) híbrido con JERARQUÍA estricta

**Evidencia DISPARA · valuación VETEA · precio NUNCA dispara.** Un add (stage→stage+1) es admisible SOLO si TODAS:
- **A1 trigger cumplido:** hecho citado, fuente whitelisted (10-Q/10-K/8-K/XBRL tag/docket regulatorio), umbral
  numérico, dirección, antes del deadline. (Pyramiding/momentum = FUERA: no hay edge, ensucia la auditoría.)
- **A2 estado_val(P_ejecución) ∈ ADMISIBLE:** {COVERED, STRETCH} siempre. OPTION_PRICED solo para binaria en el
  paso 0→1 (es su estado natural). NON_UNDERWRITABLE NUNCA habilita add.
- **A3 margen de FALSACIÓN no deteriorado (IA1, el corazón):** no preguntes "¿sigue underwritable?" (nivel),
  preguntá "¿está MENOS underwritable que antes?" (derivada). `M_comercial = T*_max − T*(P); ADD si M_t ≥ M_{t−1}
  − 0.5a`. `M_binaria = ln(p_base/p_req); ADD si M_t ≥ 0.90·M_{t−1}`. Sin esto: el **sapo hervido** (cada trimestre
  agregás a algo un poco más caro, seguís "en STRETCH", a los 6Q estás all-in en el borde).
- **A4 target > peso actual** (con histéresis ~0.15×techo).
- **A5 ventana de ejecución:** ≤5 sesiones post-filing, qty ≤ 15% ADV, re-underwrite al precio de EJECUCIÓN.
- **A6 presupuesto del nombre:** máx 2-3 add-ons de por vida.

**El hito NO compra un tramo — solo PERMITE evaluarlo.** Re-underwrite conjunto (caps + target al P_ejecución); si
la suba ya llevó el peso al target → `SATISFIED_BY_DRIFT`, sin orden. Peso cae tras comprar → NO auto-repone (el
target no es orden de rebalanceo permanente). No ejecutado en la ventana → expira (no se persigue el precio).

## 2. STAGE_FRACTION (discreto y fijo — NUNCA proporcional al Δriesgo)

Lo proporcional-a-cuánto-bajó-el-riesgo es un canal de juicio numérico encubierto que rompe la arquitectura de
etiquetas discretas. **El riesgo determina BINARIAMENTE qué stage alcanzó; la tabla fija el tamaño.**
```
COMERCIAL (probe + 3 add-ons, cada stage resuelve un riesgo DISTINTO):
  Stage 0 Probe        25%   ·  Stage 1 Demanda verificable (RPO/bookings)  50%
  Stage 2 Conversión económica (revenue/margen/unit-econ)  75%  ·  Stage 3 Repetibilidad/caja (2ª obs. indep.)  100%
BINARIA/PRE-REVENUE (NO admite escalera suave alrededor del evento terminal):
  Stage 0 Probe 20%  ·  Stage 1 hito técnico/regulatorio 50% (si runway+dilución+valuación sobreviven)
  Post-evento → RE-CLASIFICACIÓN de arquetipo obligatoria (nuevo árbol de riesgos) + re-underwrite; NO auto-100%.
```
**Regla dura: un paquete informativo avanza MÁXIMO un stage** (aunque el 10-Q traiga 5 sorpresas). No usar 3
trimestres de RPO como 3 riesgos. Máx 4 stages; nada de fracciones por-empresa.

## 3. Trigger válido vs tramposo

Campos obligatorios (append-only, hasheado antes del evento): `trigger_id, registered_at, from/to_stage,
risk_claim_resolved, eligible_source, metric_definition (tag XBRL/línea auditada), period, operator, threshold,
deadline, disqualifiers, missing_disclosure_treatment (→ UNRESOLVED), execution_window, valuation_model_version,
cap_table_version, previous_hash, trigger_hash`. **Tests (IA1):** (1) ¿la empresa puede cumplirlo SIN que baje el
riesgo? Si sí, tramposo (partnership PR pasa; RPO>$X en XBRL no). (2) `p_ex_ante ∈ [0.20, 0.80]` (>80% = tiempo
pasando = permiso automático; <20% = nunca ejecuta). (3) anti-backfit: umbral a <15% del último reportado → subilo
o descartá. **DESCARTAR:** LOI/MOU, guidance, TAM, pipeline, non-GAAP que el emisor define, menús de KPI (alcanza
uno verde), dos triggers con el mismo dato. **Fail-closed:** vence sin cumplirse O ventana pasó sin evaluar →
`stage = max(0, stage−1)` + freeze de adds 2Q. **Modificar un trigger lo CANCELA para ese evento** (la penalidad
es la guarda real, no el hash); el reemplazo recién usa el próximo período independiente.

## 4. El probe NO es 25% mecánico — depende de la DENSIDAD de triggers (IA1)

`probe = f0 × techo`: `f0=0.30` si ≥2 triggers evaluables en 4Q · `f0=0.50` si el próximo está a >12m · **`f0=1.00`
si NO existe trigger que pase los tests** (si no podés escribir un trigger falsable, NO tenés escalera: entrás al
techo de una o no entrás — *"un probe con triggers vagos es solo una posición chica con una historia encima"*).
**Regla de entrada:** iniciar SOLO si el gate pasa Y hay ≥1 trigger futuro registrado. **Piso de materialidad:**
probe <1% de cartera → no tomar (cada nombre consume capacidad de MONITOREO; triggers no monitoreados → fail-closed).
**Nº de nombres capado por capacidad de monitoreo de ventanas de filing, NO por apetito de diversificación.**

## 5. TRIM — la regla que salva del pecado #1: la valuación CONGELA, NO VENDE

```
CAP_ANCHOR   = LIVE_CAP del último evento add-admisible (se congela si OPTION_PRICED/NON_UNDERWRITABLE)
DRIFT_LIMIT  = min(2.0 × CAP_ANCHOR, ABSOLUTE_SINGLE_NAME_CAP=10% NAV)
TRIM_TARGET  = 0.75 × DRIFT_LIMIT
if thesis_falsificada or survival_gate_falla:  exit/demote (kill rules, NO es trim)
elif weight > DRIFT_LIMIT:                      trim a TRIM_TARGET (máx 1/3 de unidades/evento, cooldown 90d)
else:                                          hold; NO rebalancear
```
**PROHIBIDO:** trim por % de ganancia (+200% no es razón, es un hecho sobre el pasado) · trim por estado de
valuación (eso solo CONGELA adds, nunca vende) · trim dentro de 90d post-milestone (salvo kill) · rebalanceo por
calendario · "vender hasta recuperar el costo" (gestión de ansiedad disfrazada). **NON_UNDERWRITABLE por PRECIO →
congelar, no vender; por DETERIORO DE EVIDENCIA → kill.** Ejemplo: ceiling previo 4%, probe 1% hace +200% → 3%;
DRIFT_LIMIT 8% → no se toca; si llega a 8.1% → recorta a 6%. **El ganador puede redefinir la cartera, no destruirla.**

## 6. El modo de falla más peligroso (ambas): el sistema CORTA al ganador

No es comprar caro. Es que el sistema, ejecutado CORRECTAMENTE, **corta al outlier**: el reverse-DCF marca
NON_UNDERWRITABLE justo cuando la power-law se expresa, Y el trim por peso muerde al que compone. **Sesgo
estructural anti-outlier que mata en silencio a lo largo de años, con cada decisión pareciendo prudente.**
Guardas: (1) asimetría precio-vs-hecho (valuación congela, nunca vende); (2) prohibición de trim por ganancia;
(3) ventana de 90d post-milestone; (4) **LEDGER CONTRAFÁCTUAL** (valor de mercado de cada unidad recortada a
1/3/5a) — *"sin este ledger el modo de falla es invisible por construcción, porque cada trim se ve como
disciplina"*. Segundo modo: el **zoo de probes** (25 nombres al 0.8%, monitoreo colapsa, triggers vencen) →
fail-closed + piso de materialidad + nº capado por monitoreo.

**Segunda falla insidiosa (ambas): un solo trimestre positivo contado 4 veces** (satisface el trigger + promueve
el tier + relaja la valuación + sube el liquidity cap) — parece que 4 controles independientes autorizaron el add,
pero todo vino del mismo evento. Guardas: un evento = máx un stage · un hecho ≠ dos triggers · liquidez con ADV
mediano rezagado EXCLUYENDO la ventana del evento · tablas congeladas antes del evento.

**La puerta de hype que nadie mira (IA1): el extractor se vuelve LAXO con el nombre que ya ganó** (+180% → lee el
filing con generosidad). → **Extracción CIEGA al P&L: el prompt de extracción NO lleva ticker (cuando es evitable),
y NUNCA precio, peso ni retorno acumulado.** El allocator ve el resultado; el extractor no ve la posición.

## 7. Roles y prohibiciones del PM-LLM
El PM-LLM puede **VETO o DEFER**, NUNCA declarar PASS de un trigger, crear un trigger retroactivo, ni agrandar un
tramo. El evaluador de triggers es **determinista** (hechos del filing → PASS/FAIL/UNRESOLVED/EXPIRED).

## 8. Qué NO hacer (convergente)
Tramos continuos proporcionales al Δriesgo · add-ons por breakout/momentum · promediar a la baja · stop-loss por
PRECIO en pre-revenue (vol 80-120% → máquina de realizar ruido; stops por HECHO) · >4 stages · triggers con >2 AND
+ el gate de valuación · Bayes con números del LLM · trim por 2x/3x/recuperar-costo · llevar una binaria de 20% a
100% por un único comunicado.

## 9. Triage de build (poco código, mucho reuso)

| Pieza | Estado | Nota |
|---|---|---|
| `stage` + `STAGE_FRACTION` escalando el techo en `construir_cartera` (`w_target = f(stage)×cap`) | 🟢 chico | reusa el min() |
| Tabla de triggers hasheada (append-only) + evaluador determinista + fail-closed | 🆕 el núcleo nuevo | doc 46 §3 |
| Regla de TRIM (CAP_ANCHOR/DRIFT_LIMIT, valuación-congela) | 🔧 extiende salida/sizing | doc 46 §5 |
| Ledger CONTRAFÁCTUAL de unidades recortadas (1/3/5a) | ♻️ reusa `registro_decisiones` | §6 |
| Margen de falsación A3 (derivada de T*/p_req) | 🔧 sobre `valuacion_reverse` | §1 A3 |
| Extracción ciega al P&L | ♻️ ya casi (el extractor no recibe P&L) — auditar | §6 |
| Densidad de triggers → `f0` del probe | 🆕 chico | §4 |

**Requiere datos que aún no extraemos:** los triggers necesitan que el sistema extraiga los HECHOS de milestone
(RPO citado, financiamiento, hito regulatorio) — es Bloque 4. La MECÁNICA (stage/trim/ledger) es buildable ya y
la mayoría reusa lo existente.
