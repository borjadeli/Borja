# 40 — Plan de build rebalanceado (post-paradigma)

> **Hoja de ruta canónica del build.** Reemplaza los planes ad-hoc anteriores (el reverse-DCF de doc 36 §10 se
> **pliega** acá). Organizado por el **sándwich** (doc 39): hechos deterministas → underwriting por juicio
> acotado → sizing/restricciones deterministas. Regla de orden: **MEDICIÓN PRIMERO, mecanismo después** (el
> meta-gate de la triangulación: no cerrar números sin evidencia). Todo en SHADOW; el paper vivo no se toca.
> Génesis: [[rebalanceo-determinismo-juicio]]. Cada bloque = una unidad de trabajo con tests.

## Principio de orden

Los dos bugs (g=0, r=15%) nacieron de construir motor sobre fe. Por eso el Bloque 0 es MEDICIÓN: el
instrumento que te dice si el frame separa ganadores de perdedores ANTES de invertir más energía. Si el
backtest no separa, se re-piensa; si separa, calibra los números en vez de argumentarlos.

---

## BLOQUE 0 — Medición (el meta-gate) · *arranca acá*

**Objetivo:** poder saber si el sistema está ciego. Sin esto, un determinista solo ve que sus posiciones se
comportaron razonablemente y nunca detecta los falsos negativos (los 10x que rechazó).

- **0.1 Ledger de rechazos / shadow portfolio** 🆕 — registrar cada rechazo con: precio al rechazo · **regla
  exacta que rechazó** · arquetipo/sector · retorno forward 1/3/5a (mark-to-market vía yfinance) · máx drawdown ·
  hito alcanzado · **tipo de error (dato/parámetro/reference-class/juicio)**. Métricas por VERSIÓN de política:
  falsos+ comprados · falsos− rechazados · alpha perdido por reason code · contribución de ganadores · ventas
  prematuras. (Reusa: el patrón de `paper_pnl`/mark-to-market ya existe.)
- **0.2 Backtest harness** 🆕/🔧 — correr el sistema sobre un universo histórico con datos point-in-time →
  ¿los COVERED superan a los OPTION_PRICED a 3/5a? (Reusa: `backend.backtesting` existe como base.) **Necesita
  XBRL point-in-time** (SEC Financial Statement Data Sets) → si es caro, v1 con la data que haya + honestidad
  sobre look-ahead.

**Desbloquea:** todo lo demás (calibración empírica en vez de a priori).

## BLOQUE 1 — Refactors deterministas (baratos, sin LLM, alto impacto)

**Objetivo:** sacar la MECANICIDAD sobre-extendida sin tocar aún el juicio. Todo son refactors de lo que existe.

- **1.1 Gates conjuntivos → SCORING no-compensatorio** 🔧 — `evaluacion.py`/`ranking.py`: los 3 pilares dejan de
  ser AND-gate; el determinismo veta SOLO sobre supervivencia (runway/burn, dilución tóxica, gobernanza, going
  concern, fraude). **UNKNOWN ≠ FAIL** (distinguir "todavía no observable" de "negativa").
- **1.2 Valuación deja de ser GATE → tamaño + falsador** 🔧 — sacar `valuacion_ok` como puerta dura; el
  reverse-underwriting produce el ESTADO (tamaño) y el falsador, no un pase/no-pase. Reusa `valuacion_reverse.py`.
- **1.3 Sacar el DOBLE-CONTEO** 🔧 — el riesgo idiosincrático vive en UN lugar (probabilidad/escenario/funding/
  dilución), NO apilado en `r` + g-cap + margen + dilución. Aplica el desdoblamiento **`r_mkt` (leer) / `h`
  (exigir)** de doc 37 y presupuesta el conservadurismo una vez. *(Acá se pliega el reverse-DCF de doc 36/37.)*
- **1.4 Sizing → BANDA, no punto** 🔧 — `cartera_celdas.py`: supervivencia→máx (duro) · asimetría→base · deja el
  hueco para que el juicio mueva dentro de la banda (Bloque 3).
- **1.5 Abstención → 4 estados** 🔧 — `REJECT / WATCH / PROBE / UNDERWRITTEN` (doc 39 §2.7). Reusa la abstención
  existente. (Piso vs sin-mínimo = la 1 decisión abierta; default: PROBE generoso + ledger vigilando.)
- **1.6 Ranking → DIVERSIDAD** 🔧 — reemplazar el lexicográfico total por maximizar nº de tesis independientes
  no correlacionadas sujeto a supervivencia+liquidez (desempate mecánico solo dentro de cohortes equivalentes).

**Desbloquea:** que el pre-revenue deje de ser excluido por construcción; que el growth no se sub-dimensione.

## BLOQUE 2 — La segunda gramática de valuación

**Objetivo:** el 70% pre-revenue tiene payoff BINARIO; el reverse-DCF continuo le hace la pregunta equivocada.

- **2.1 Valuación binaria / probabilidad-implícita** 🆕 — "¿qué probabilidad del evento único exige el precio?"
  vs la lectura (base rate sectorial de la transición + evidencia técnica). Árbol de milestones + dilution
  waterfall + kill condition. Reusa el burden de `pre_revenue.py` como base. g=0 queda como STRESS TEST.
- **2.2 Clasificador de gramática** 🔧 — Lynch: clasificar (continua vs binaria vs madura) ANTES de valuar,
  por el ruteo de owner-FCF DURABLE (doc 37 §7, tri-estado).

## BLOQUE 3 — El canal de juicio (el rebalanceo real)

**Objetivo:** recuperar falsos negativos sin reabrir el hype. El juicio entra POSITIVO pero acotado y medido.

- **3.1 Etiquetas + allocator** 🆕 — el PM-LLM emite SOLO `ADMIT_PROBE/PASS/PRIORITY_H·M·L/HOLD/THESIS_BROKEN/
  VETO`; un **allocator determinista** las mapea a banda. El LLM nunca emite un número.
- **3.2 Memo de juicio** 🆕 — estructurado, firmado, versionado; bull + bear INDEPENDIENTES antes de la síntesis;
  no ve el ranking previo (anti-anchoring). Auditabilidad = **reconstruibilidad** (qué se supo/infirió/prior/
  mecanismo/falsador/por qué esa banda/qué versión), NO reproducibilidad de la opinión.
- **3.3 Presupuesto + ledger de hit-rate** 🆕 — N promociones/ciclo; si el juicio no le gana al baseline sobre
  N decisiones, el presupuesto se achica solo. Prohibido: pisar veto de supervivencia, tocar un número de tabla,
  re-correr hasta que dé lindo, overrides por nombre. *(El carril especulativo ya construido se re-conceptualiza
  como el estado PROBE + este canal.)*

## BLOQUE 4 — Ensanchar la evidencia + escalera de add-on

**Objetivo:** el fact store es demasiado ANGOSTO (no demasiado determinista) y todo el sistema es de ENTRADA.

- **4.1 Extractores nuevos** 🆕 (todos citables/deterministas): management → **ledger de promesas** (guidance
  dicho vs cumplido, fechado) · cap table → 13D/G, uso de ATM, warrants, Form 4 open-market · **TAM → de la
  CONTRAPARTE** (capex hyperscalers, IRPs de utilities, presupuesto de defensa, órdenes NRC/DOE — adelanta 2-6Q).
  (Extiende el patrón de `FACT_KEYS`/`extraer_*` que ya existe.)
- **4.2 Underwriting ESCALONADO / escalera de add-on** 🆕 — probe chico → add-on DETERMINÍSTICO cuando llega la
  evidencia PRE-ESCRITA. Resuelve el dilema central (participar antes de la evidencia dura sin perder disciplina).
  Requiere el Bloque 0 (monitoreo/milestones) + Bloque 3 (PROBE).

---

## Qué NO se toca (el determinismo SÍ es el edge)

Fact store cita/hash/versión/changelog/re-run · LLM sin opiniones en extracción · vetos de supervivencia · cero
overrides por nombre · el CÓMPUTO del reverse-underwriting (solo no como puerta) · caps de tamaño/liquidez.

## Dependencias y estado

```
Bloque 0 (medición) ──► habilita calibrar todo lo demás
Bloque 1 (refactors deterministas) ──► independiente, alto impacto, arranca en paralelo a 0
Bloque 2 (2ª gramática) ──► depende de 1.2/1.3
Bloque 3 (canal de juicio) ──► depende de 1.4 (banda) + 1.5 (PROBE)
Bloque 4 (evidencia + add-on) ──► depende de 0 (monitoreo) + 3 (PROBE)
```

**Pendientes chicos parqueados (no bloquean):** #12 bug logger de costo · #13 recall del carril (se subsume en
Bloque 3/4) · #5 Pilar 3 guidance (Fase 2, FMP). **Superado:** el plan reverse-DCF-como-gate de doc 36 §10 (se
pliega en Bloque 1.2/1.3 + Bloque 2).
