# 26 — Framework de EVALUACIÓN y RANKING v3 (consolidado, post 2 revisiones del crux)

> Cómo, a partir de hechos confiables, el sistema decide **qué incorporar a la cartera** — y por
> qué. Dos revisiones adversariales independientes convergieron en un diseño **más simple, más
> robusto y más específico al universo** que la versión anterior (16 dimensiones bandeadas y
> sumadas). Grounded en lo que el sistema viejo ya evaluaba. **Reemplaza la v1/v2.**

## 0. Los 3 reencuadres que lo cambian todo
1. **El output NO es un ranking cardinal — son TIERS.** Distinguir el nombre #7 del #8 es ruido con
   cualquier método. Se necesita un **conjunto elegible + una regla de sizing**, no un orden total.
2. **Se rankea por el DELTA de evidencia, no por el nivel.** En small caps pre-inflexión el retorno
   viene del **re-rating cuando la evidencia cruza de afirmación a hecho** (se nombra un cliente,
   aparece la 2ª orden, el contrato se vuelve revenue reconocido, el margen cruza a positivo).
   Rankear por nivel = comprar siempre **después** del re-rating. La señal es la **derivada de la
   madurez de evidencia** (el `diff` del fact store, doc 25). Nivel absoluto = filtro de elegibilidad.
3. **El bear case es DILUCIÓN por acción, no compresión de múltiplo.** Raise al descuento del sector
   contra shares proyectadas — aritmética del motor de CRR que ya existe. Es el mecanismo real por
   el que se pierde 70% en estos nombres.

## 1. Tres preguntas distintas — no mezclarlas
- *mejor empresa* (calidad) · *mejor acción al precio actual* (valuación/asimetría) · **mejor
  incorporación a la cartera HOY** (delta + timing + fit + liquidez). **El sistema responde la
  tercera.** Confundirlas es la raíz de medio problema del ranking.

## 2. Extracción vs. scoring; taxonomía por CLAIM (no dura/soft por dimensión)
La inestabilidad venía de que el LLM **puntuaba y agregaba**, no de que opinara. El LLM **extrae
hechos con cita y fuente para TODO**; un rulebook determinista mapea hecho→banda. Cada **claim** se
etiqueta:
- **Observado** (en fuente admisible) · **Derivado** (cálculo reproducible sobre observados) →
  **hacen banda dura.**
- **Inferido** (interpretación fundada, no verificable) · **Especulativo** (hipótesis futura) →
  **NO hacen banda; solo desempatan/penalizan/veto (§6).**
Las dimensiones se **descomponen** (management: dilución/guidance-cumplido/crecimiento-por-acción/
Form 4 = duro; "gran ejecutor" = inferido). Tres tipos de observable: **medido** (percentil del
universo) · **categórico** (checklist de binarios verificables — moat = ¿contrato con exhibit?
¿switching cost documentado? ¿sole-source cualificado?) · **sin observable** (no es dimensión: veto
o nota al pie, nunca número).

## 3. Los 4 PILARES de mérito + regla de NO-COMPENSACIÓN
Las ~16 dimensiones están **correlacionadas y sobre-especificadas** (se contaban 4×). Se agrupan en
4 pilares (diagnóstico rico, no 16 votos):
1. **Demanda + posición en el cuello** — demanda real, materialidad, madurez, calidad del revenue,
   validación externa, importancia/sustituibilidad del cuello.
2. **Economía + captura de valor** — gross margin, unit economics, pricing, recurrencia, capital
   intensity, conversión a FCF.
3. **Ejecución + creación de valor POR ACCIÓN** — track record, guidance cumplido, capital
   allocation, dilución, SBC, M&A, alignment (Form 4).
4. **Valuación + asimetría** — expectativas implícitas, downside (dilución), upside respaldado,
   supervivencia.
**Composición CONJUNTIVA (no suma):** una **debilidad crítica en cualquier pilar topea el tier**
(nada de rescatar runway fatal con TAM enorme). *En cuellos, el retorno lo domina no tener
desastres, no tener el mejor.* Fragility, CRR, red flags, cap-tóxica, liquidez y cobertura quedan
**fuera del mérito** → gates/caps.

## 4. Salida = TIERS + sizing
- **Tier A (core):** ningún pilar bajo · ≥2 altos · asimetría ≥ media.
- **Tier B (satélite):** fundamentos suficientes pero un pilar débil o evidencia incompleta.
- **Tier C (watch):** no elegible aún / falta evidencia / debilidad crítica.
- **Sizing = convicción(tier) × liquidez × cap** (los caps ya construidos: `min(arquetipo×fragility,
  CRR, madurez×materialidad)`).

## 5. Prioridad dentro de la elegibilidad = Δ de evidencia
Rankear los elegibles por **transiciones de madurez de los últimos 1-2 trimestres** (usa el `diff`
del fact store). Un nombre ya REALIZED estable se mantiene por nivel; el **delta manda las entradas
y la rotación.** + **base rate de clase de referencia** (de los comparables que llegaron a esta
madurez, ¿qué fracción llegó al bull?) como prior anti-sobreconfianza — no es opinión del LLM.

## 6. Valuación = expectativas implícitas (no price target)
Dado el EV actual, con margen terminal y múltiplo de la **distribución realizada de comparables**
(percentiles de datos), despejar el revenue que el precio exige: *"exige $X en 5 años = 7× = 48%
CAGR"* → **se testea contra filings** (¿entra en capacidad+capex? ¿backlog? ¿clientes × ASP?). Banda
= exige lo imposible/difícil/razonable/poco. **El precio enuncia la hipótesis, los filings la
testean.** Bear = dilución (§0.3). Peso de valuación: **normal + penalización fuerte por extremos**
(no ×1.5 — el peso pesado va al Δ de evidencia).

## 7. El juicio (inferido/especulativo), blindado
Nunca suma al mérito. Tres funciones únicas: **(a) desempatar dentro del mismo tier** · **(b)
penalizar downside / disparar revisión** (dependencia de fundador, solución técnicamente inferior,
cliente probando sustituto, contrato económicamente irrelevante) — *más poder para advertir downside
que para fabricar upside* · **(c) override EXPLÍCITO y visible del PM** ("promuevo B a A por estas 2
razones, con estos falsificadores, hasta esta fecha"). **Formato obligatorio de cada juicio:** claim
· evidencia a favor · en contra · fuente+fecha · falsificador observable · fecha de expiración ·
label (supportive/neutral/contradictory) · confianza (suficiente/insuficiente, NO 1-10). + **test de
estabilidad N=5**: si el juicio no es estable entre corridas, se descarta → UNKNOWN. Para juicio en
serio: **comparaciones pareadas** (Bradley-Terry/Elo), no escalas.

## 8. Fuentes = ADMISIBILIDAD claim-specific (no pesos universales)
Confiabilidad = fuente × **adecuación al claim** × corroboración × vigencia. Un Form 4 prueba
"compró", no "cree que está barata"; un contrato-exhibit prueba existencia, no el revenue/margen/
obligatoriedad. **Techo, no multiplicador:** una dimensión sostenida solo por aserción del management
llega **a lo sumo a neutra** (nunca diferenciador positivo; sí puede ser negativa). Modular **por
empresa** (un "auditado" con material weakness/restatement/auditor tier-3 vale menos). Precio de
mercado **condicionado a liquidez**. **Guidance = promesa falsable:** guidance-vs-actuals a 4T es
señal tier-1 de integridad (con lag). No promediar dos fuentes malas en una buena.

## 9. Sentiment social = eje de atención/timing, NUNCA mérito
Medir **cambio** de atención, concentración en pocas cuentas, aceleración, **divergencia** atención
vs. evidencia, reacción de precio/volumen. Usos: crowding (sube el hurdle / baja sizing) ·
divergencia = **red flag unidireccional** (+ detección de coordinación) · descubrimiento (puntero a
leer un filing, se vuelve evidencia solo si se confirma). **Nunca "+0.5 banda"** (contaminable,
duplica momentum). Ojo **sesgo de selección**: un industrial de $200M no tiene Reddit → solo hay
señal en lo ya hypeado.

## 10. UNKNOWN = ranquear sobre lo observado con shrinkage
No banda neutra (premia opacidad). **Shrinkage hacia la mediana proporcional a la cobertura** +
**cobertura mínima del bloque core como gate** + cap por madurez, **los tres juntos.** Y distinguir
**"no revelado" (missingness informativo → señal negativa si los peers sí revelan) ≠ "no extraído"
(bug del pipeline)** — hoy los dos son UNKNOWN y significan lo opuesto.

## 11. Dimensiones que faltaban / sobraban
**Sumar (casi todas a GATES/CAPS, no al mérito):** estructura de **capital tóxica** (convertibles
con reset, death-spiral, lockups, overhang — top predictor negativo) · **capacidad instalada +
capex** (la restricción física del cuello; reemplaza a TAM) · **posición en la cadena + poder de
negociación** (concentración de clientes Y proveedores — el moat Y la fragilidad a la vez) ·
**dependencia de política pública** (% de revenue atado a un subsidio nombrable) · **liquidez**
(ADV/spread/float/borrow → caps). **Sacar:** TAM narrativo · "ciclo/duración del edge" (redundante) ·
**catalizadores fuera del mérito** (no hacen mejor al negocio, hacen más rápido el camino → timing/
sizing).

## 12. EL LOOP DE MEDICIÓN (lo que faltaba — sin esto todo es opinión ordenada)
**Loggear el vector de bandas completo en el momento de decisión** (no reconstruido) y medir
**retorno forward 6/12/24m por decil de cada pilar/dimensión, por separado.** Con 3 años y ~50
nombres no hay significancia, pero sí lectura direccional de **qué discrimina** (apuesta: 4-5 sí, el
resto es ruido correlacionado). **Eso decide la arquitectura final, no la teoría.** Es lo primero.

---
**Las 3 que se lleva IA 1 si tiene que elegir:** (1) medí el poder discriminante antes de seguir
diseñando; (2) el bear es dilución por acción; (3) rankeá por delta de evidencia, no por nivel.
