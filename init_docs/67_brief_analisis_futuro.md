# 67 — Brief para triangular: cómo analiza BORJA una tesis (presente + futuro)

> Para converger con 2+ IAs antes de codear (método de docs 56/61). Contexto: el comité v2 corre end-to-end
> y es riguroso con los HECHOS presentes (XBRL, filings, frescura, contraste numérico) — ver doc 66 (dossier
> real de OKLO). El operador frenó la 1ª corrida sobre el universo con una duda de fondo: **¿analizamos BIEN
> la empresa, sobre todo su FUTURO, que es donde está nuestro edge?** No reabrir el paradigma (doc 51), el
> método canónico (doc 33 reverse underwriting · doc 31 pre-revenue · doc 29 carril especulativo) ni los
> hechos presentes ya resueltos. La pregunta es **cómo se refleja el análisis de tesis en los agentes v2**.

## 0. El encuadre del operador (no se discute; es el marco)
- **El futuro es UNA pata, no la única.** Lo que la empresa hace HOY, sus números, su historial y su
  tracción también valen. No sobre-indexar en el futuro ni en el presente.
- **El TIEMPO es decisivo.** Una gran tesis de futuro sin camino concreto hoy NO sirve: *"computación cuántica
  puede ser una excelente tesis de futuro, pero hoy no existe, no genera ingresos, es pura especulación → no
  sirve"*. Hay que distinguir **futuro INVERTIBLE** (camino concreto: hitos fechados, tracción incipiente,
  financiación/regulación en marcha) de **especulación lejana** (futuro sin camino ni ingresos).
- **El PM debe ser experto en tesis de futuro** (no solo sizer).
- **Macro/mercado al PM: suma, pero sin marearlo ni sesgarlo.** Dosis justa.

## 1. Lo que ya existe (del doc 66, dossier real de OKLO)
El Analista ya hace **reverse underwriting** básico: no pone un price target, pregunta *"¿qué tiene que pasar
para justificar el precio?"* y lo vuelve falsable (OKLO: "~19 unidades/1,4 GW operando a 2035, COLA a la NRC,
arranque Aurora-INL cerca de 2028"). Bull/bear independientes, falsador fechado, convicción. **Límite actual:**
(a) el burden/T* de futuro lo improvisa el LLM con supuestos a mano ($100/MWh, 10x EBITDA, 12%), no una
calculadora determinista; (b) el Verificador valida HECHOS presentes, NO la tesis de futuro; (c) el prompt
del Analista es fuerte en rigor de fuentes pero pobre en el MARCO de tesis power-law (cuello, captura,
opcionalidad, horizonte); (d) nada mide explícitamente la **invertibilidad temporal** de la tesis.

## 2. Roles sobre la TESIS (a aclarar — sin comités nuevos)
Hoy: **Analista** construye la tesis (bull/bear + reverse underwriting) · **Bear** la ataca · **Verificador**
verifica hechos (no juzga la tesis) · **PM** sizea por convicción · **Auditor** mira la cartera
(concentración/coherencia/rotación), NO la calidad de la tesis.

### ⭐ Decisiones abiertas
- **D1 · Balance presente/futuro.** ¿Cómo se asegura que el análisis pondere AMBAS patas (números/historial
  HOY + tesis de futuro) y no colapse en una? *Default:* el dossier exige las dos — salud presente
  (caja/runway/dilución/márgenes/tracción, ya verificada vs XBRL) Y la tesis de futuro (reverse underwriting
  + funded critical path). La convicción refleja las dos; una tesis de futuro brillante con salud presente
  frágil (quema sin runway) NO es alta convicción.
- **D2 · Invertibilidad TEMPORAL (el punto central del operador).** ¿Cómo distingue el sistema futuro
  invertible de especulación lejana? *Default propuesto:* un **gate de madurez de tesis** determinista +
  juicio, con ejes: (1) **funded critical path** — ¿la caja/financiación comprometida alcanza hasta el
  próximo hito que mueve la tesis? (doc 31); (2) **distancia al hito** — hitos concretos y fechados dentro de
  un horizonte razonable (¿3-5 años?) vs "algún día"; (3) **tracción/evidencia de demanda** — PPAs, contratos,
  pilotos, revenue incipiente vs cero señal comercial. Una tesis sin camino financiado ni hito cercano
  (cuántica pura) → **no elegible como posición core**; a lo sumo entra por el **carril especulativo** (doc 29:
  cap chico, presupuesto acotado), nunca como apuesta grande. ¿Cuáles son los umbrales y quién los aplica
  (determinista en el IPS / juicio del PM)?
- **D3 · ¿Quién cuestiona la CALIDAD de la tesis de futuro?** El Bear ataca con contra-evidencia; el PM
  decide. *Pregunta:* ¿el **Auditor** debería además cuestionar la **madurez/tiempo** de la tesis (no solo la
  cartera) — p.ej. objetar "esta tesis es especulación lejana sin camino"? ¿O eso recarga al Auditor y mejor
  va como un check determinista (D2) + el juicio del PM? *Default:* el gate de madurez (D2) es determinista e
  informa al PM; el Auditor suma una objeción de "madurez de tesis" como predicción falsable (no veto).
- **D4 · Calculadoras de futuro DETERMINISTAS.** Cablear `pre_revenue` (reverse underwriting, FCFE requerido,
  gap de financiamiento, runway al hito) y `valuacion_reverse` (T*/burden) al data pack, para que el "qué
  exige el precio" sea **determinista y citado**, no improvisado por el LLM. *Pregunta:* ¿esto es parte de
  este trabajo o se difiere? (depende de qué insumos del fact store estén listos).
- **D5 · El PM como experto en tesis + cuánta macro.** ¿Qué recibe el PM para ser "experto en futuro" sin
  marearse? *Default:* (a) el reverse underwriting + funded critical path del dossier; (b) el contexto del
  mapa (cuello, por qué importa, competencia) — ya cableado; (c) el memo macro como MARCO (qué cuellos se
  aprietan), NO para elegir nombres. **NO** sumar flujos de mercado/posicionamiento por ahora (riesgo de
  sesgo/ruido que el operador marcó). ¿De acuerdo, o falta/sobra algo?
- **D6 · Prompts (Analista + PM).** Enriquecer con el MARCO de tesis power-law: cuello de botella y por qué
  esta empresa lo captura, opcionalidad asimétrica (downside acotado por caja vs upside por el cuello),
  horizonte temporal del hito, falsadores ESTRUCTURALES (no solo de fuente). Sin romper el rigor de frescura/
  fuentes ya logrado. *Pregunta:* ¿qué debe decir el prompt del Analista sobre CÓMO pensar el futuro, y el
  del PM sobre cómo ponderar futuro vs precio actual vs tiempo?

## 3. Lo que NO se re-abre
El paradigma (LLM decide, determinismo informa/limita), el método canónico (33/31/29), el rigor de hechos
presentes (XBRL/frescura/contraste), el comité ya construido. Esto es **cómo el análisis pondera presente +
futuro y filtra la invertibilidad temporal**, reflejado en calculadoras + prompts — no un rediseño.
