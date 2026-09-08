# 41 — Triangulación: segunda gramática de valuación (payoff binario) + el "good loser" SBC-heavy

> Bloque 2 del plan (doc 40). Dos decisiones de método NUEVAS (no aplicación de algo cerrado) → se triangula.
> Surgieron del flujo vivo: el reverse-DCF continuo le hace la pregunta equivocada al ~70% pre-revenue (payoff
> binario), y los growers SBC-heavy rutean a pre-revenue por owner-FCF<0. El operador circula a 2 IAs; el
> asistente prepara. Ver [[rebalanceo-determinismo-juicio]] (doc 39 §3, §4.1, §4.3).

---

## PROMPT (copiar tal cual a cada IA, por separado)

Sos un quant/inversor worldclass en small & mid caps de tecnología emergente. Necesito cerrar DOS decisiones de
método de valuación entrelazadas. Sé adversarial y concreto (specs implementables); no me halagues.

### Contexto del sistema (no negociable)

Sistema de inversión determinista y auditable. El LLM SOLO extrae hechos citados de filings (EDGAR/XBRL);
tablas versionadas deciden. Ya tengo cerrado, para empresas COMERCIALES que generan caja, un **reverse-DCF de
falsación**: fijo el crecimiento en lo DEMOSTRADO (histórico citado, fadeado) y despejo **T\*** = cuántos años
de compounding EXIGE el precio, con terminal g=0, a través de una superficie de margen; lo leo a costo de
equity de mercado (`r_mkt`), y decido con un hurdle aparte. owner-FCF = CFO − capex − SBC (SBC restado UNA vez,
es dilución real). El universo objetivo es ~70% **pre-revenue** (nuclear/SMR, biotech, fotónica, defensa
pre-programa, hardware pre-producción).

### DECISIÓN 1 — Gramática BINARIA para pre-revenue (payoff no-continuo)

El reverse-DCF continuo le hace la pregunta equivocada a una empresa cuyo valor cambia DISCONTINUAMENTE con un
hito único (aprobación FDA, captura de un programa de defensa, licencia NRC, primer contrato comercial). No hay
CAGR histórico útil, los márgenes no son observables, y "exige 60% CAGR por 8 años" → rechazo automático de algo
que en realidad es una apuesta binaria con EV positivo.

**Hipótesis a pressure-testear:** computar la **probabilidad IMPLÍCITA que el precio demanda** para el evento, y
compararla contra una **base rate sectorial** de esa transición + evidencia técnica citada. Si el precio implica
P=12% y tu lectura es 30%, no es "caro" — es la posición. Mecánica candidata:

```
Precio_ops = P_implícita × V_éxito + (1 − P_implícita) × V_fracaso
  → P_implícita = (Precio_ops − V_fracaso) / (V_éxito − V_fracaso)
V_fracaso ≈ caja neta ajustada por dilución hasta el hito (piso de liquidación)
V_éxito   ≈ el reverse-DCF COMERCIAL aplicado a la empresa POST-hito (estado de-riesgado)
```

**Preguntas (respondé TODAS, con precisión de implementación):**
1. ¿Es correcto el frame? ¿O hay uno mejor para payoff binario disciplinado? Atacalo.
2. **`V_éxito` es el agujero de hype:** requiere asumir revenue/margen post-hito. ¿Cómo se ancla sin inventar
   (¿comparables de la empresa YA de-riesgada del mismo vertical? ¿capacidad física declarada × precio de
   contrato citado? ¿ceiling del programa con haircut?) y qué NO se permite?
3. **Base rates de transición:** ¿qué fuentes dan la base rate de "capturar el programa / pasar la fase / obtener
   la licencia" por vertical (FDA phase-transition tables, DoD program-of-record capture, NRC/DOE licensing
   timelines)? ¿Cuáles son sourceables y cuáles diferir?
4. **`V_fracaso`:** ¿caja neta menos burn-hasta-el-hito menos dilución? ¿Qué lo hace robusto vs manipulable?
5. **Múltiples hitos / árbol:** ¿un solo hito binario, o un árbol de probabilidades encadenadas? ¿Dónde parar
   para no sobre-parametrizar?
6. ¿Cómo mapea a mis estados de sizing (probe chico / core)? ¿La probabilidad-implícita-vs-leída define el TAMAÑO
   o solo el pase a "probe"?

### DECISIÓN 2 — El "good loser" (SBC-heavy comercial ruteado como pre-revenue)

Mi switch de ruteo es owner-FCF (= FCF − SBC) > 0 → comercial; si no → pre-revenue/burden. Problema: un SaaS que
crece 40% con SBC alto tiene owner-FCF < 0 y cae a la vía pre-revenue — pero es un negocio COMERCIAL escalando,
no una apuesta binaria. Pérdida contable ≠ destrucción económica (R&D expensado, CAC pre-ingreso, capacidad
pre-revenue, SBC por talento). Pero NO toda pérdida es "buena".

**Preguntas:**
7. ¿Cuál es el switch de ruteo CORRECTO (comercial vs pre-revenue vs binario), si el signo de owner-FCF es
   insuficiente? ¿Gross-margin positivo + operating leverage demostrado? ¿un tri-estado?
8. **La tensión del SBC:** para la VERDAD de valuación hay que restar el SBC (es dilución real); pero para el
   RUTEO, restarlo manda a la vía equivocada. ¿Cómo se resuelve sin trampa (¿SBC afecta la valuación pero no el
   ruteo? ¿un "owner-FCF ex-growth-investment" separado)?
9. ¿Cómo distinguir determinísticamente "pérdida de INVERSIÓN" (buena, escala) de "pérdida ESTRUCTURAL" (mala)?
   Retorno incremental por dólar, economics por cohorte, mejora de métricas FÍSICAS antes que financieras — ¿qué
   es sourceable de XBRL/filings y qué no?
10. ¿Se puede valuar un SBC-heavy grower con el reverse-DCF comercial si normalizo el margen a un estado maduro
    (en vez de usar el owner-FCF actual negativo)? ¿O eso reabre el hype?

### Formato
- Veredicto por decisión (frame correcto / modificado / equivocado) en 3 líneas c/u.
- La mecánica implementable de cada una (pseudo-fórmula + fuentes de datos XBRL vs texto).
- El modo de falla más peligroso de cada una + su guarda determinista.
- Qué NO haría (sobre-ingeniería / hype disfrazado).

No asumas que tengo razón. Si alguna decisión está mal planteada, decilo y dá la correcta.
