# 38 — Triangulación del PARADIGMA: ¿es el determinismo el enfoque correcto para small/mid caps del futuro?

> Meta-revisión. No un parámetro: el paradigma entero. La preocupación del operador: que el determinismo esté
> peleándose con la tesis (small/mid caps de industrias del futuro, donde el edge suele ser cualitativo/forward).
> El operador circula a 2 IAs; el asistente prepara. Ver [[modelo-de-uso-real]], [[drift-valuacion-growth-reverse-underwriting]].

---

## PROMPT (copiar tal cual a cada IA, por separado)

Sos un inversor/quant worldclass con experiencia REAL en small & mid caps de tecnología emergente. Te pido
una crítica de PARADIGMA, no de parámetros. Sé brutal; no me halagues. Prefiero descubrir ahora que el enfoque
está mal a descubrirlo con capital adentro.

### Qué construí

Un sistema de inversión para **small & mid caps de "industrias del futuro"** (AI infra, nuclear/energía,
defensa, healthtech, robótica, fotónica; ~70% pre-revenue). Sector elegido a propósito por ser el más
riesgoso: donde un sistema disciplinado puede generar más diferencial. Filosofía central: **DETERMINISTA y
auditable.** En concreto:

- El **LLM solo extrae hechos citados** de filings (EDGAR) + datos XBRL. **Nunca emite una opinión ni un número
  de decisión.** Tablas versionadas producen todas las decisiones.
- **Pipeline:** universo → extracción de evidencia (fact store con cita) → evaluación por empresa (3 pilares
  conjuntivos como gate: demanda-por-cuello / economía / ejecución-por-evidencia; + valuación como gate
  separado) → **sizing de 2 ejes** (la EVIDENCIA decide de qué LIBRO forma parte —inmutable—; la VALUACIÓN
  decide el TAMAÑO —variable—) → **dos libros** (duro = evidencia contratada; carril especulativo = opcionalidad,
  capado a 2 plazas / 8%) → ranking lexicográfico (sin score cardinal) → cartera.
- **Valuación = reverse underwriting de falsación, no proyección:** computo qué crecimiento/burden EXIGE el
  precio y lo juzgo contra lo DEMOSTRADO (histórico citado) + base rates. Nada de proyecciones de crecimiento.
- **Disciplina sobre actividad:** se prefieren slots vacíos (cash) a forzar entradas. Abstención determinista
  cuando la evidencia es insuficiente.
- Todo versionado, con hash, changelog, y re-run completo ante cualquier cambio de parámetro. Cero overrides
  por nombre.

### La preocupación (el core de tu tarea)

**¿El determinismo total está peleándose con la naturaleza de esta clase de activo?** Dos veces ya descubrí
que mi operacionalización determinista SUB-DIMENSIONABA estructuralmente todo mi universo (una vez asumiendo
crecimiento cero; otra usando una tasa de descuento inflada) — el sistema "disciplinado" tendía a rechazar o
minimizar exactamente las empresas que son mi tesis. Me preocupa que:

- el edge en small caps del futuro sea **cualitativo y forward** (calidad del management, inflexión tecnológica,
  timing de catalizador, credibilidad del TAM, calidad del cap table) — cosas que NO se reducen bien a hechos
  XBRL + tablas;
- un sistema que solo actúa con evidencia dura y contratada esté **estructuralmente ciego al 10x** (que casi
  siempre se ve "caro/especulativo" con evidencia contratada), y que la disciplina "abstención→cash" signifique
  **sentarme afuera justo cuando la tesis se juega**;
- haya confundido **anti-hype** (correcto) con **anti-juicio** (posiblemente fatal para esta clase de activo).

### Tus preguntas (respondé TODAS, adversarial)

1. **¿Es el determinismo el paradigma correcto para ESTA clase de activo?** ¿O es un método de deep-value/
   quality apuntado a un problema de venture/growth? Atacá la premisa.

2. **¿Dónde debería estar el BORDE determinismo↔juicio?** ¿Qué partes del proceso GANAN con determinismo
   (cuáles son las que enumero arriba) y cuáles se DEGRADAN por forzarlas a ser deterministas? Sé específico
   por etapa.

3. **¿Qué MISS estructuralmente un sistema puramente determinista en small/mid caps del futuro?** Dame los
   modos de falla concretos (falsos negativos: los 10x que rechaza y por qué), no generalidades.

4. **El PM-LLM con juicio DENTRO de caps** (el diseño original: guardrails deterministas + juicio acotado a
   reducir/vetar/priorizar, nunca a inflar) — ¿es la síntesis correcta, o es contaminación del juicio que
   arruina la auditabilidad? ¿Dónde exactamente puede intervenir el juicio sin re-abrir la puerta al hype?

5. **La disciplina "abstención→cash":** ¿es sabiduría (no operar lo que no entendés) o es el bug fatal (en un
   sector donde la incertidumbre es la norma, abstenerse = no invertir nunca)? ¿Cómo se calibra?

6. **¿Cómo lo saben los MEJORES inversores reales de este espacio?** (no los quants — los que efectivamente
   agarraron los multibaggers de tech emergente). ¿Su proceso es replicable de forma disciplinada-pero-no-
   determinista? ¿Qué de eso es sistematizable y qué es irreductiblemente juicio?

7. **Si tuvieras que rediseñar el balance determinismo/juicio de este sistema desde cero para MAXIMIZAR el
   retorno ajustado por riesgo en small/mid caps del futuro** — ¿qué se queda determinista, qué pasa a juicio
   acotado, y qué se tira?

### Formato

- Veredicto en 5 líneas: ¿el paradigma está bien, mal, o mal-balanceado? ¿Dónde exactamente?
- El mapa determinismo↔juicio ideal, por etapa del pipeline.
- Los 3 falsos-negativos estructurales más peligrosos (los 10x que este sistema rechazaría) + cómo evitarlos
  sin reabrir el hype.
- Qué NO tocarías (dónde el determinismo SÍ es el edge).

No asumas que el sistema está bien. Si el balance está mal, decime dónde y cuál es el correcto.
