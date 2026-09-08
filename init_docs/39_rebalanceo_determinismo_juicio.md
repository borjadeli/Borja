# 39 — Rebalanceo determinismo ↔ juicio (síntesis de la triangulación de paradigma)

> **CERRADO** (2026-08-21). Síntesis de doc 38 (IA1 + IA2, meta-review del paradigma). Las dos convergieron
> INDEPENDIENTEMENTE en el mismo diagnóstico y casi el mismo remedio — señal fuerte. Valida la preocupación del
> operador ("el determinismo se pelea con la tesis"). NO es "tirar el sistema": es rebalancear el motor,
> conservando la carcasa. Ver [[modelo-de-uso-real]], [[drift-valuacion-growth-reverse-underwriting]].

## 0. El veredicto (convergente)

El paradigma **no está mal — está mal-balanceado**: usa el determinismo como **motor de CONOCIMIENTO** (decidir
qué va a FUNCIONAR) cuando debería ser un **sistema de CONTROL** (hechos, límites, disciplina). El juicio NO se
eliminó: se **congeló y escondió dentro de tablas/umbrales/tasas** — lo cual es MÁS peligroso, porque una tabla
mal especificada sub-dimensiona TODO el universo a la vez. **Los dos bugs (g=0, r=15%) no fueron accidentes
independientes: fueron la firma estructural de esa sobre-extensión.** "Cualquier operador monótono decreciente
en incertidumbre, sobre evidencia demostrada, sub-dimensiona exactamente los nombres de máxima convexidad."

**La distinción raíz (IA1):** **AUDITABILIDAD** (reproducible, versionado, falsable) = gratis, es el edge,
INTACTA · vs **MECANICIDAD** (la decisión = función total de hechos tabulables) = lo que rompe la tesis.

**La línea central (IA2):** **determinismo para los hechos, los límites y la disciplina; juicio para
interpretar el futuro.** Estructura = **SÁNDWICH**: hechos/procedencia deterministas → underwriting causal por
juicio estructurado → restricciones/sizing/ejecución deterministas.

## 1. Por qué (la matemática del power-law)

~2% de las acciones explican >90% de la creación de riqueza; ~60% no superan T-bills. La asimetría cambia el
objetivo: un falso positivo a 0.5% cuesta ~0.5% (acotado); un 10x NO comprado cuesta un múltiplo NO acotado.
El sistema actual maximiza **PRECISIÓN** ("que casi todo lo que compro esté bien respaldado") cuando el power-
law exige también **RECALL** ("asegurarme exposición a una fracción razonable de los outliers"). Gates
conjuntivos en dominio power-law = optimizar precisión donde el falso negativo es el costo dominante.

## 2. Los 8 cambios (ambas IAs los respaldan)

1. **Gates conjuntivos (3 pilares AND valuación) → SCORING no-compensatorio.** El determinismo conserva
   autoridad TOTAL para decir "no sobrevive" (vetos de supervivencia/gobernanza/dilución/fraude) y CERO
   autoridad para decir "no va a funcionar". **UNKNOWN ≠ negativo** (la conjunción convierte UNKNOWN en cero y
   excluye sistemáticamente al pre-revenue).
2. **Valuación: DEJAR de usarla como GATE.** Es **el tamaño + el falsador**, no un pase/no-pase. Y **DOS
   gramáticas** (Lynch: clasificar antes de valuar): **continua** (los que ya escalan) + **binaria/milestone
   de probabilidad implícita** para el 70% pre-revenue: *"¿qué probabilidad del evento único exige el precio?"*
   Si implica 12% y tu lectura es 30%, no es "caro" — es la posición. El terminal g=0 queda como **stress test**,
   no como juez único.
3. **Base rates = PRIORS, no techos.** Actualización bayesiana con evidencia company-specific. "Demostrado como
   cap" = proyectar implícitamente que el pasado es el límite. No hay valuación de emerging-growth sin ALGUNA
   creencia forward; el reverse-DCF la revela, no la elimina.
4. **El fact store es demasiado ANGOSTO, no demasiado determinista → construir los extractores faltantes**
   (todos citables/deterministas): management → **ledger de promesas** (guidance dicho vs cumplido, fechado) ·
   cap table → 13D/G, uso de ATM, warrants, Form 4 open-market · **TAM → de la CONTRAPARTE** (capex de
   hyperscalers, IRPs de utilities, presupuesto de defensa, órdenes NRC/DOE — adelanta 2-6Q al backlog del target).
5. **Sizing = una BANDA, no un punto.** supervivencia→máximo (determinista, duro) · asimetría→base (determinista,
   del underwriting) · **juicio→mueve DENTRO de la banda, en AMBAS direcciones**, con presupuesto. (Un PM que
   "solo reduce" nunca puede corregir un falso-negativo que la tabla puso en cero.)
6. **Canal de juicio: presupuestado + puntuado + con LEDGER.** N promociones/ciclo (vetos ilimitados); cada
   intervención con **falsador escrito + fecha**; ledger con hit-rate; si el juicio no le gana al baseline
   determinista sobre N decisiones, el presupuesto se achica solo. PROHIBIDO igual: pisar un veto de
   supervivencia, tocar un número que alimenta una tabla, re-correr hasta que dé lindo, excepciones por nombre.
   **MECÁNICA LIMPIA (IA2):** el determinista produce **hard exclusions + bandas + ceilings, NO una cartera
   obligatoria completa**; el PM-LLM emite SOLO **etiquetas discretas** — `ADMIT_PROBE · PASS · PRIORITY_H/M/L ·
   HOLD · THESIS_BROKEN · VETO` — y un **allocator determinista** las traduce a una banda de tamaño (el LLM
   NUNCA emite un número). `ADMIT_PROBE` exige TODO: mecanismo causal + ≥1 evidencia validada (no contractual) +
   milestone falsable próximo + runway a ese hito + downside modelado (con dilución) + payoff grande vs precio +
   sin red lines. **Memo de juicio: estructurado, firmado, versionado; bull y bear INDEPENDIENTES antes de la
   síntesis; el modelo NO ve el ranking previo en la 1ª evaluación (anti-anchoring).**
   **AUDITABILIDAD REDEFINIDA (clave):** NO significa que dos corridas den la misma opinión. Significa que después
   podés RECONSTRUIR: qué se sabía, qué se infirió, qué prior, el mecanismo causal, la evidencia contraria, el
   milestone esperado, qué habría falsado la tesis, por qué esa banda, qué versión decidió. **El juicio ES
   auditable.** (Ésta es la reconciliación con la filosofía: auditabilidad ≠ reproducibilidad de la opinión.)
7. **"Abstención→cash" → CUATRO estados, no binario** (IA2): **REJECT** (evidencia negativa/fraude/funding
   imposible/burden inalcanzable aun en escenario favorable) · **WATCH** (hipótesis interesante, sin evidencia
   independiente ni milestone invertible) · **PROBE** (alta incertidumbre PERO mecanismo causal + payoff
   asimétrico + milestone próximo + supervivencia) · **UNDERWRITTEN** (3 pilares con evidencia para tamaño core).
   La abstención es **correlacionada por régimen** (abstenés en todo el sector a la vez, justo cuando el payoff
   se concentra) → hoy es market-timing encubierto. El cupo especulativo: **8% total pero 6-10 probes** a
   0.5-1.0% inicial, máx 1.5-2% antes de más evidencia, promoción SOLO tras hitos predefinidos (más breadth,
   menos tamaño inicial). ⚠️ **ÚNICA divergencia IA1↔IA2:** IA1 quiere un **PISO** ("al menos X% desplegado, si
   no llena baja la vara y loguea") por el argumento de abstención-correlacionada; IA2 quiere **SIN mínimo** (el
   carril es presupuesto MÁXIMO, no target a llenar). A decidir — probablemente PROBE-por-defecto-generoso sin
   piso duro + el ledger de rechazos vigilando que no estemos abstiniéndonos en masa. Es la 1 cosa abierta.
8. **Ranking lexicográfico → DIVERSIDAD de tesis independientes.** El orden total tira la info de cola y crea
   comparabilidad falsa (biotech vs nuclear vs cloud). Construcción de cartera = maximizar nº de apuestas vivas
   no correlacionadas sujeto a supervivencia+liquidez, no rank-and-fill.

## 3. Las DOS piezas estructurales que FALTAN

- **Underwriting ESCALONADO / escalera de add-on (IA1):** todo el sistema es de ENTRADA. En esta clase el
  retorno se gana **sosteniendo y agregando sobre confirmación PRE-REGISTRADA.** Comprás la opcionalidad chica
  (probe) y agregás **determinísticamente** cuando llega la evidencia escrita de antemano. **Resuelve el dilema
  central:** participar ANTES de la evidencia dura SIN abandonar la disciplina, porque la escalera está escrita
  antes. (Modelo VC: posición inicial chica, add-on sobre milestone.)
- **Ledger de RECHAZOS / anti-portfolio (ambas):** shadow portfolio permanente de rechazadas con: precio al
  rechazo · **regla EXACTA que rechazó** · arquetipo/sector · retorno posterior (1/3/5a) · máx drawdown · hito
  alcanzado · **tipo de error (dato / parámetro / reference-class / juicio)**. Medir POR VERSIÓN: falsos
  positivos comprados · falsos negativos rechazados · **alpha perdido por reason code** · capital perdido en
  probes · contribución de ganadores · ventas prematuras. Sin esto, un sistema determinista **no sabe que está
  ciego** — solo ve que sus posiciones se comportaron razonablemente. Habría cazado los dos bugs automáticamente.
  **El objetivo NO es minimizar errores** — es *"comprar suficientes outliers para capturar la cola derecha,
  limitando DETERMINÍSTICAMENTE cuánto puede costar estar equivocado."*

**Regla anti-doble-conteo (IA1+IA2, central):** el riesgo operativo/idiosincrático vive en UN lugar
(probabilidades/escenarios/funding/dilución), NO se re-incorpora entero vía una tasa punitiva. Si castigás a la
vez crecimiento + margen + probabilidad + dilución + `r`, no sos conservador — **contás el mismo riesgo varias
veces** (es la causa mecánica de los dos bugs). Presupuestar el conservadurismo UNA vez y repartirlo.

## 4. Los 3 falsos-negativos estructurales (a arreglar)

1. **Deep-tech que crea valor ANTES de la demanda contratada** (biotech pre-approval, fotónica en qualification,
   nuclear pre-licencia, hardware pre-producción). Falla demanda+economía+valuación a la vez aunque la PoS haya
   pasado de 10%→35%. Fix sin hype: árbol de milestones + base rate sectorial de cada transición + evidencia
   técnica independiente + runway al próximo punto de verdad + dilution waterfall + kill condition ANTES de
   comprar + probe chico nunca core. "No necesitás afirmar que va a funcionar — reconocer que una transición de
   probabilidad tiene EV positivo."
2. **Plataforma al inicio de una curva S** (TAM endógeno, sin base histórica). Fix: adopción/uso REAL (no
   partnerships), ROI verificable del cliente, evidencia cruzada en filings del cliente, retención/expansión,
   ventaja técnica medible, upside bottom-up, TAM separado de la afirmación del management.
3. **El "good loser" que quema justo antes de escalar** (R&D expensado, capacidad pre-revenue, CAC pre-ingreso,
   yields bajos, SBC por talento). Pérdida contable ≠ destrucción económica. Fix: FCF−SBC como verdad de caja
   + vista SEPARADA inversión-vs-gasto improductivo + retorno incremental por dólar + economics por cohorte +
   exigir mejora de métricas FÍSICAS antes de asumir mejora financiera. (No capitalizar R&D automáticamente.)

## 5. Qué NO se toca (el determinismo SÍ es el edge)

Fact store con cita/hash/versión/changelog/re-run (ventaja real, casi nadie la tiene) · LLM sin opiniones en
extracción · **vetos de supervivencia** (runway/burn, dilución, warrants, gobernanza, going concern) · cero
overrides por nombre · **el CÓMPUTO del reverse underwriting** (perfecto como cálculo — solo no como puerta) ·
caps de tamaño/liquidez. Y: si "libro inmutable" = el juicio no lo pisa, bien; si = la clasificación no se
actualiza con evidencia nueva, es un congelamiento (arreglar: re-clasificar con evidencia, no con juicio).

## 6. El meta-gate (IA1): evidencia sobre razonamiento

Antes de cerrar tasas/umbrales: **BACKTEST** (¿los COVERED superan a los OPTION_PRICED a 5 años, histórico?) +
**construir el ledger de rechazos**. Si no separan, el frame no tiene poder predictivo. Necesita bulk XBRL
point-in-time (P1). "Todo lo a priori es necesario pero no es evidencia."

## 7. Implicancia para el build

Reordena bastante — y para MEJOR (da un principio organizador: el sándwich). Afecta: evaluación (gates→scoring),
valuación (gate→tamaño+falsador, 2 gramáticas), sizing (banda + canal de juicio), cartera (diversidad, piso no
techo, escalera de add-on), + 2 artefactos nuevos (ledger de rechazos, extractores contraparte/management/cap-table).
El reverse-DCF (tarea #15) deja de ser "reemplazar el falsador con un gate" → pasa a ser "tamaño+falsador, no
puerta". **Re-planificar el build alrededor del sándwich antes de seguir codeando mecanismo.**
