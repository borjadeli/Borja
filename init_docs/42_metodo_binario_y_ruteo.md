# 42 — Método CERRADO: gramática binaria (pre-revenue) + ruteo de dos ejes (good-loser)

> **CERRADO** (2026-08-25). Síntesis de la triangulación de doc 41 (IA1 + IA2 convergieron casi total —
> señal muy fuerte). Bloque 2 del plan (doc 40). Génesis: [[rebalanceo-determinismo-juicio]] §4.
> **Disciplina de build (decisión del operador):** se implementa el corte barato-que-arregla-bugs-vivos;
> las tablas de base-rate y el V_éxito Tier-A/B/C se DIFIEREN (dependen de datos externos). No construir
> árboles ni segundo-frame para un sistema en shadow.

## 0. Los dos veredictos

**D1 (gramática binaria) — frame correcto, implementación reescrita.** NO es "probabilidad implícita del
mercado": es **`P_req@r`** (probabilidad requerida bajo `r`, contaminada por la prima de riesgo). Descontar
bien, por acción después de dilución. **`V_éxito` NO sale de reverse-DCF** (de comparables/contratado, percentil
BAJO condicional al éxito, capado por EV del par ya de-riesgado). **`V_fracaso` solo de XBRL** (default 0). Sin
base-rate table auditable → **quinto estado: sin posición salvo a precio de piso** (correcto, no defecto).

**D2 (good-loser) — switch equivocado, faltan ESTADOS no umbrales.** El signo de owner-FCF mide intensidad de
inversión, no la CLASE de empresa. El defecto real: el SaaS-que-escala y el negocio-que-muere caen al MISMO
bucket. **Reemplazar el test de NIVEL por un test de DERIVADA** (`Δ8Q(GP)/Δ8Q(OpEx) > 1.0` = apalancamiento
operativo demostrado). **SBC = reclamo sobre el equity: rutear PRE-SBC, valuar POST-SBC, muro entre ambos.**

## 1. D1 — Mecánica binaria (para PRE_REVENUE_BINARIO)

```
# Precio de las ops, con dilución hasta el hito (por acción, no market cap básico):
S_T        = S_hoy + cash_need / (P_mkt × (1 − haircut_emisión))     # haircut 0.20–0.30
cash_need  = burn_mensual × T_hito × 1.30                            # burn = −(CFO+capex) 4Q/12; T con slip
Precio_ops = P_mkt × S_T
# Descontar (el bug de mi propuesta era NO descontar):
P_req@r    = (Precio_ops·(1+r)^{-0}·… )  →  (Precio_ops − PV_fail) / (PV_éxito − PV_fail)   # PV a T_hito
```
**Regla de decisión (no de estimación):** `GATE = P_base_comprometida / P_req@r ≥ 2.0` (absorbe la cuña de
prima de riesgo + el error de V_éxito; ambos inputs ±50%). IA1 pedía además `p_U−p_BE ≥ 5pp` → tomar **ambos**
(el más conservador). `P_base` se **HASHEA ANTES** de leer el market cap (anti-anchoring — el módulo de valuación
NO puede ver el precio, o el sistema está roto por diseño).

**`P_base` desde base-rate:** `Beta(s+½, f+½)`, percentil **Q20 conservador**; celda `n<20` → sube al padre. El
LLM NO puede mover la probabilidad leyendo evidencia (solo elegir subclase pre-registrada o LR calibrado
out-of-sample). **`V_éxito`:** ≤5 números citados; Tier-A (techo contractual×haircut · capacidad física
FINANCIADA×precio contratado×utilización · deal comparable del vertical) permitido; Tier-C (TAM×penetración,
sell-side, guidance>12m, deck como número, márgenes no auditados) = **rechazo automático**. Topes: `V_éxito ≤
EV(par de-riesgado)` y **percentil bajo condicional al éxito, NUNCA E[V|éxito]** (el error más caro y fácil).
**`V_fracaso` solo XBRL:** `cash + ST_inv − deuda − burn×T_P90 − wind_down`; ≥0; por acción sobre `S_T`. Texto
solo puede RESTAR (asimétrico). Nunca NOLs/goodwill/IP/PP&E-sin-haircut/ATM. **`V_fracaso=0` es legítimo y
frecuente** (converts).

**Sizing binario (la brecha define el PASE, no el tamaño):** gate a probe = `P_base/P_req@r ≥ 2.0 ∧ V_fracaso/
Precio_ops ≥ 0.35 ∧ n≥20 ∧ ≥2 citas Tier-A ∧ runway cubierto`. Tamaño dentro de probe por variables que NO son P
(tiempo a resolución, ratio de piso, **correlación de cartera por factor de resolución** —6 SMR = 1 binaria
grande—, cap 0.5-1.5%/nombre, cap del bucket 15-20%). **Core PROHIBIDO pre-hito** (se gana por transición de
estado; post-hito se re-rutea al motor comercial). Kelly solo como TECHO con `P=P_base` a fracción 1/5.

**Árbol: máx 2 nodos** (técnico + financiamiento). Usar la compuesta PUBLICADA (Fase2→aprobación), NUNCA el
producto de factores (correlacionados). Parar en el 1er nodo con precio de comparable observable.

## 2. D2 — Ruteo de dos ejes (4 estados deterministas, todo XBRL)

```
COMERCIAL_MADURO:     revenue_TTM>0 ∧ GP>0 ∧ owner_FCF>0 en ≥2/4Q            → reverse-DCF as-is (margen demostrado)
COMERCIAL_ESCALANDO:  revenue_TTM ≥ $50-100M (o ≥3a) ∧ GM ≥ 55% ∧ pendiente_8Q(GM) ≥ −100bps/a
  (el "good loser")   ∧ (GP − S&M) > 0 ∧ Δ8Q(GP)/Δ8Q(OpEx) > 1.0 ∧ conc_top<30% ∧ runway≥24m ∧ SBC/Rev ≤ 0.25
                      → reverse-DCF con superficie de margen normalizado (§3)
PRE_REVENUE_BINARIO:  sin revenue recurrente (grants/NRE no cuentan) ∧ hito nombrado ∧ base_rate n≥20  → §1
BURDEN / SIN_POSICIÓN: GM≤0 · revenue↓ con owner_FCF<0 · runway<12m · o nada calificó                  → excluido
```
**El insight central:** test de DERIVADA, no de nivel — `Δ8Q(GP)/Δ8Q(OpEx) > 1.0` separa "pierde plata
escalando" de "pierde plata muriendo". XBRL, no manipulable por management, contesta la pregunta económica.

**SBC — muro de dominios (restricción de TIPOS en el código, no convención):**
```
fcf_pre_sbc = CFO − capex           → SOLO ruteo + tests de apalancamiento. PROHIBIDO en cualquier output de valuación.
owner_FCF   = CFO − capex − SBC     → SOLO valuación. El margen terminal de todo DCF normalizado es POST-SBC.
```
Segunda guarda: `SBC/Revenue > 0.25` sostenido → motor comercial ficticio → BURDEN.

## 3. D2 — Reverse-DCF con margen normalizado (para COMERCIAL_ESCALANDO)

**NO normalizar el margen a un punto (ahí reabrís el hype): RESOLVER el lugar geométrico.** Dos incógnitas
(T*, m_terminal), una ecuación → reportar el `locus = {(T*,m): precio se justifica}` y una sola pregunta binaria:
```
hull = envolvente convexa de márgenes operativos GAAP POST-SBC auditados de ≥3 pares maduros (rev≥$1B) del vertical
if locus ∩ hull == ∅:  RECHAZO determinista
```
Es el MISMO movimiento epistémico del reverse-DCF de falsación, en 2 dimensiones (extensión natural, no método
nuevo). Restricciones: `m ≤ GM_actual − opex_mínimo` (R&D no va a 0; piso P25 de pares); `SBC/rev terminal ≥
mediana de pares` (el SBC decae MÁS lento que lo que asume cualquier modelo); el opex no puede caer en dólares
absolutos; fade por vertical, no por nombre. Dilución terminal por observación: `S_T = S_hoy×(1+dilución_neta_
observada)^T` (mejor que restar SBC en dólares).

## 4. Good-loss vs structural (3 estados, gates duros XBRL)

`DEMONSTRATED_SCALING_LOSS`: rev↑ ∧ GP>0 ∧ incremental_GP>0 ∧ ΔOM≥0 ∧ Δowner-margin≥0 ∧ mejora ≥300bp ∧
Δ(SBC/rev)≤200bp ∧ dilución≤cap. `STRUCTURAL_EVIDENCE`: GM≤0 dos LTM · incremental_GP≤0 dos comparaciones ·
ambos márgenes empeoran tras rev acumulado ≥50% · crecimiento solo por SBC/dilución sobre cap. `UNPROVEN_LOSS`:
resto (sin crédito, sin auto-rechazo). **RPO** (`RevenueRemainingPerformanceObligation`) = mejor input
estructurado de un SaaS (contratado, no proyectado). **NRR** (solo texto, no tagueado): `NRR≥110% ∧ GM≥70% ∧
RPO↑≥rev↑ → inversión`; `NRR<100% ∧ owner_FCF<0 → estructural sin excepción`; ausente se penaliza. **Prohibido:
LTV/CAC calculado por vos** (extraído+citado o nada — la métrica más manipulada del sector).

## 5. Guardas (los modos de falla, de las dos IAs)

**D1 — laundering de hype con apariencia de rigor** (V_éxito infalsificable + P anclada al número despejado →
"todo barato" con trazabilidad impecable). Guardas: (1) **pipeline de dos etapas con COMMIT** — P_base+V_éxito
hasheados antes de ver el precio; (2) **libro de calibración** (Brier score acumulado — "sin esto tenés
opiniones con LaTeX"); (3) **backtest sobre el CEMENTERIO** (30 fracasos resueltos, point-in-time; si E[P_leída]
> frecuencia realizada, recalibrar el gate, no la lectura); (4) descuento obligatorio con T slip-ajustado.

**D2 — "COMERCIAL_ESCALANDO" se vuelve bucket de amnistía** (todo lo que te gusta y pierde plata cae ahí con
margen normalizado). Guardas: (1) **democión automática por RELOJ** — ESCALANDO que no mejora margen owner-FCF
≥X bps/año en 2 años → BURDEN, sin apelación narrativa (el reloj es el guardián); (2) **cap de cartera** sobre el
bucket; (3) criterios pre-registrados versionados (aflojar un umbral sale en el diff del re-run); (4) el muro
pre/post-SBC como restricción de tipos.

## 6. Qué NO hacer (prohibiciones convergentes)

Real options / Black-Scholes (σ inobservable = perilla de hype). Monte Carlo como gate (display, nunca). Base
rates ajustadas por nombre. Encadenar >2 nodos o multiplicar factores con compuesta publicada. TAM×penetración
en CUALQUIER disfraz (incl. "capacidad del sector × share razonable"). Forzar la maquinaria binaria sin tabla
(→ quinto estado floor-only). LTV/CAC self-computed. V_fracaso con texto que sume. Sizing proporcional a la
lectura de P. **E[V|éxito] en vez del percentil bajo** (el error más caro y fácil de cometer sin notarlo).

## 7. Triage de build (disciplina del operador, 2026-08-25)

| Pieza | Estado | Por qué |
|---|---|---|
| **D2: ruteo 4 estados + derivada ΔGP/ΔOpEx + muro SBC** | 🟢 **AHORA** | barato, XBRL, arregla bug VIVO (S/RBRK) |
| **D2: good-loss 3 estados (XBRL) + democión por reloj** | 🟢 **AHORA** (gates duros) / 🟡 reloj con loop de cartera | XBRL |
| D1: `V_fracaso` (solo XBRL, default 0) + `P_req@r` + gate + **quinto estado floor-only** | 🟡 **skeleton ahora** | cheap; excluye pre-revenue correctamente sin tabla |
| D1: base-rate tables (biotech 1º, defensa escalera, SMR slip) | 🔴 **DIFERIR** (datos externos) | BIO/WSL versionada; defensa=observables; SMR=slip |
| D1: `V_éxito` Tier-A/B/C (contratos, comparables) | 🔴 **DIFERIR** (extracción de texto) | trabajo real |
| D1: árbol 2 nodos · 2º frame (arbitraje de transición) · Monte Carlo | 🔴 **NO ahora** (sobre-ingeniería en shadow) | superficie sin capital vivo |
| Guardas: libro de calibración (Brier) + cementerio backtest | 🟡 **cuando haya P leídas** | reusa `registro_decisiones`/`backtest_valuacion` |

**Conclusión:** D2 se implementa entero (arregla el good-loser). D1 = skeleton + floor-only; el resto diferido
con su dependencia de datos explícita. Nada de árboles/2º-frame hasta que el skeleton pruebe valor.
