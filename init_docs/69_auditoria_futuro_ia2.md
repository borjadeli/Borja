# 69 — Auditoría del brief 67 (análisis presente+futuro) — IA 2

> Devolución de **IA 2**. Converge con IA 1 (doc 68); refina D2 con el concepto rector **time-to-investable-
> inflection**. ⚠️ El pegado del operador se cortó al final de D6 (Analista). Convergencia → doc 70.

## Veredicto
El enfoque es correcto; modificaría D2 y D3. El problema no es que BORJA analice poco el futuro, sino que no
distingue sistemáticamente **tres cosas**: (1) un futuro prometedor (la industria puede crecer); (2) una
empresa capaz de capturarlo (tecnología, clientes, ventaja, ejecución); (3) una inversión atractiva HOY
(camino verificable para capturar ese valor, en un plazo relevante, a un precio que deja upside). **El edge
power-law está donde las tres coinciden, antes de que el mercado lo reconozca.** No hace falta un score
rígido ni que una calculadora elija: el Analista construye mejor el caso, el Bear ataca la viabilidad, el PM
distingue oportunidad anticipada de promesa lejana.

| Decisión | Veredicto | Modificación |
|---|---|---|
| D1 presente/futuro | Correcto | ambas patas, sin penalizar automáticamente márgenes negativos de empresas en expansión |
| D2 invertibilidad temporal | **Modificar** | medir tiempo a una INFLEXIÓN DE VALOR, no a comercialización; separar cálculo objetivo del juicio del PM |
| D3 quién cuestiona | **Modificar** | el BEAR es el adversario principal de la madurez; no duplicar en el Auditor |
| D4 calculadoras | Correcto | deterministas, supuestos explícitos, escenarios, dilución por acción |
| D5 PM + macro | Correcto c/matiz | macro como contexto CAUSAL; financiación y condiciones cuando afecten la tesis |
| D6 prompts | Correcto, incompleto | captura económica, secuencia causal, tiempo, precio, falsadores estructurales |

## D2 — el cambio más importante: TIME-TO-INVESTABLE-INFLECTION (no time-to-revenue)
Una empresa puede tardar 5 años en FCF positivo pero tener en 12 meses un hito externo que valida una porción
sustancial de su valor futuro → **invertible hoy**. La distinción: el hito debe demostrar **progreso
económico real**, no ser una excusa para que suba la acción. **Un catalizador de cotización ≠ inflexión de
valor**: debe haber relación CAUSAL entre el hito y mejores probabilidades de ingresos/márgenes/financiación/
flujos.

### A. Dos relojes
- **RELOJ FUNDAMENTAL (3-5 años):** ¿cuándo demuestra el negocio su potencial económico (escala, márgenes, FCF)?
- **RELOJ DE INVERSIÓN (6-24 meses):** ¿cuándo puede aparecer evidencia nueva, suficientemente importante,
  para modificar RACIONALMENTE su valoración?
- **Regla central:** NO hace falta rentabilidad en 24m; SÍ una razón fundamental y verificable para que la
  inversión genere valor en ese horizonte. (Evita los dos errores: comprar narrativa lejana / rechazar
  disruptivas sin ganancias aún.)

### B. Los 4 tests de invertibilidad
| Test | Pregunta | Quién |
|---|---|---|
| 1. Inflexión temporal | ¿qué hecho verificable cambia el valor fundamental en 6-24m? | Analista + juicio PM |
| 2. Camino financiado | ¿llega al hito sin financiación hipotética ni dilución destructiva? | Calculadora + PM |
| 3. Validación externa | ¿qué evidencia independiente respalda que el hito es alcanzable y económicamente relevante? | Analista + Bear |
| 4. **Captura por acción** | aunque la tecnología triunfe, ¿ganan los accionistas ACTUALES al precio de hoy? | Calculadora + PM |
El test 4 es indispensable: se puede acertar tecnológicamente y destruir valor por dilución/márgenes/
competencia/valuación inicial desmesurada.

### C. Umbrales (criterios analíticos por defecto, NO límites duros del IPS)
- **Primera inflexión de valor:** core preferentemente **≤24 meses**; especulativa >24-36m sin prueba
  intermedia. **No** fijar 3-5 años como umbral core general (demasiado permisivo para una estrategia de
  6-24m). Sí admitir comercialización a 5 años **si hay hitos intermedios relevantes, financiados y próximos**.
- **Financiación:** cubre el próximo hito material + colchón (ref. 6 meses), también bajo estrés.
- **Tracción:** evidencia comercial/técnica/regulatoria externa apropiada a la etapa (no TAM/promesas/pruebas
  internas).
- **Economía futura:** camino defendible a captura de valor POR ACCIÓN.
- **No exigir ingresos presentes** como condición universal: una pre-revenue con financiación + prueba externa
  en 12m + economía defendible puede ser invertible; otra con ingresos insignificantes pero sin camino es
  especulación.

### D. Ejemplo cuántica (3 casos)
- **A — gran futuro, no defendible hoy:** sin ingresos relevantes, sin demanda validada, comercialización a
  muchos años, hitos vagos, capital insuficiente → **watchlist, no core**. La calidad del sector no compensa
  la falta de camino financiado.
- **B — futuro lejano, prueba próxima:** sin comercialización masiva pero con tecnología validada
  externamente, contratos/pilotos pagos, caja para completar pruebas, hito importante en 12m → **potencialmente
  invertible** (el PM decide core vs especulativa según evidencia, economía por acción y precio).
- **C — negocio presente sólido + crecimiento:** rentable, ya vende componentes críticos, gana share en un
  cuello, con nuevas expansiones → **puede ser core sin un hito binario único** (la evolución trimestral de
  ventas/márgenes/órdenes valida la tesis). **Importante para respetar el encuadre: no todo depende de un gran
  catalizador futuro.**

### E. Implementación del gate — FICHA estructurada, NO score 0-100
Un score agregado da falsa precisión y compensaciones absurdas (TAM enorme tapando falta de financiación).
Ficha: `next_value_inflection · months_to_inflection · fundamental_impact_if_successful ·
independent_evidence · milestone_funding_coverage · stress_funding_gap · subsequent_capital_need ·
dilution_exposure · price_implied_requirements · critical_unverified_assumption · analyst_classification
(core/speculative/watchlist) · pm_decision_and_rationale`. Caja/financiación/fechas/dilución =
**determinista cuando los inputs lo permiten**; relevancia/credibilidad del hito y si el precio compensa =
**juicio experto**. **Autoridad:** el IPS mantiene sus límites duros (supervivencia, carril especulativo); el
gate **informa y exige justificar, NO crea veto autónomo ni sizing paralelo al PM.**

## D1 — mantener (sin ponderación mecánica 50/50)
Presente = qué POSEE el accionista hoy (activos, caja neta, ventas, márgenes, ejecución, clientes,
supervivencia). Futuro = qué puede cambiar estructuralmente y cuánto valor adicional captura esa acción. Un
margen negativo NO es mala salud si refleja inversión financiada con buenos economics incrementales; una
empresa con runway insuficiente y sin acceso creíble a financiación NO debe tener alta convicción aunque su
tecnología sea extraordinaria.

## D3 — NO convertir al Auditor en otro Analista (el BEAR ataca la madurez)
Cambia el default: el **Bear** incorpora explícitamente la crítica de madurez temporal:
- ¿el próximo hito prueba la tesis o es un avance cosmético?
- ¿qué supuesto puede retrasar 2 años el camino económico?
- ¿cuánto capital adicional se necesita y qué pasa con las acciones actuales?
- ¿qué parte del éxito ya está en el precio?
El PM resuelve estas objeciones antes de decidir. El **Auditor** conserva cartera pero puede señalar que N
posiciones dependen de financiación externa en el mismo período de tasas altas (concentración que el análisis
individual pasa por alto). **No sumar otro agente ni segunda revisión de tesis.**

## D4 — aprobar con 3 condiciones
1. **Inputs trazables:** distinguir XBRL/filings · compromisos contractuales · consenso · supuestos del
   Analista. 2. **Escenarios:** el funded critical path en BASE y ESTRÉS (capex, cash burn, servicio de deuda,
   financiación realmente disponible). 3. **Valor por acción:** reverse underwriting y T* con dilución futura,
   no solo EV. **Si no hay info suficiente → UNKNOWN, no fabricar una estimación precisa.**

## D5 — macro liviana pero CAUSAL
No introducir por defecto flujos/posicionamiento/señales tácticas. SÍ las variables que condicionan la
ejecución de la tesis: costo de financiación, capex de clientes, contratos, ciclo de inventarios, energía,
regulación, disponibilidad de componentes. **Memo de máximo 3 elementos: régimen relevante · mecanismo de
transmisión · riesgo concreto para la tesis.** Nada genérico. (El precio/burden/liquidez siguen esenciales
para dimensionar; excluir posicionamiento ≠ ignorar valuación.)

## D6 — instrucciones a los roles existentes (no otra metodología)
**Analista:** construí la tesis como **secuencia causal** entre hechos presentes → ventaja competitiva →
captura económica futura → valor por acción. **No confundas crecimiento del sector con crecimiento capturable
por esta empresa.** Identificá la primera inflexión fundamental verificable dentro del horizonte, qué
evidencia la anticipa, qué capital necesita y qué eventos POSTERIORES siguen siendo necesarios para
monetizarla. Separá hechos/inferencias/supuestos. Evaluá si el precio exige un éxito superior al respaldado
por la evidencia y las **tasas base**. Falsadores estructurales fechados (deterioro competitivo, cambio
tecnológico, problemas de adopción, necesidad de dilución).

**PM:** evaluá CONJUNTAMENTE negocio presente, oportunidad futura, precio actual y tiempo. Priorizá
asimetrías donde la empresa capture valor económico relevante **antes de que esté plenamente reconocido en la
cotización**. No descartes disruptivas por falta de ganancias, pero no confundas narrativa de largo plazo con
inversión ejecutable hoy: exigí explicación concreta del **camino financiado, la evidencia externa, el plazo
a la próxima inflexión y el valor que llega al accionista actual**. La convicción surge de la solidez
CONJUNTA, no del TAM ni de una historia atractiva. Resolvé las objeciones del Bear antes de dimensionar bajo
el IPS.

**Corrección al brief:** el downside NO está necesariamente acotado por la caja — en una empresa que quema
efectivo, la caja puede desaparecer antes de generar retornos y la financiación futura puede diluir fuerte.
Analizar valor residual y consumo de capital, no suponer un piso por tener efectivo. (Coincide con IA 1 D6.)

## Recomendación de implementación (IA 2) — sin sumar complejidad institucional
1. **D2:** ficha de invertibilidad temporal (primera inflexión de valor vs monetización final).
2. **D4:** deterministas las necesidades de financiación + burden por acción, bajo escenarios.
3. **D3:** el Bear obligado a atacar el camino temporal y económico; el Auditor casi sin cambios.
4. **D6:** incorporar los bloques al Analista y PM. D1/D5 solo ajustes menores.

**Output que el PM debe poder decir de cada tesis:** *"esta empresa hoy tiene un negocio verificable de tal
calidad; puede capturar una oportunidad estructural por estas razones; necesita estos dos hitos, el primero
en 12 meses; tiene fondos para hacerlo; el mercado exige este nivel de éxito; y los motivos por los que
podría fracasar son estos."* Si eso no se puede explicar con evidencia y supuestos explícitos, la tesis no
está lista para alta convicción.

**Conclusión:** BORJA no necesita ser conservador con el futuro; necesita ser EXIGENTE con el camino que
conecta ese futuro con una rentabilidad atractiva para el accionista actual. Esa distinción preserva el edge
power-law sin convertir el sistema en comprador de narrativas.
