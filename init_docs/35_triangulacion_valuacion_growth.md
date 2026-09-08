# 35 — Triangulación: método de valuación para GROWTH (comercial temprana) en industrias del futuro

> Prompt para circular a 2 IAs independientes (agresiva + adversarial). Objetivo: cerrar el método para
> valuar el bucket "comercial temprana / alto crecimiento" — el agujero del sistema. Ver
> [[drift-valuacion-growth-reverse-underwriting]]. El operador circula; el asistente prepara.

---

## PROMPT (copiar tal cual a cada IA, por separado)

Sos un analista quant worldclass de Wall Street, especialista en **small & mid caps de "industrias del
futuro"** (AI infra, energía/nuclear, defensa, healthtech, robótica, fotónica). Te contrato para
pressure-testear y cerrar UN método de valuación. Sé riguroso, adversarial y concreto; no me halagues.

### Contexto del sistema (no negociable)

Estoy construyendo un sistema de inversión **determinista y auditable** con esta filosofía:
- **Evidencia sobre narrativa.** El LLM SOLO extrae *hechos citados* de filings (EDGAR 10-K/10-Q/8-K) y
  datos XBRL. **Nunca emite un número de decisión ni una opinión.** Una **tabla versionada** determinista
  produce la decisión. Esto existe para excluir el momentum narrativo / el hype.
- **Implementabilidad como gate:** solo adopto lo que puedo computar HOY desde EDGAR/XBRL + hechos citados
  del filing. Si un input no es sourceable/extraíble/computable de forma robusta, se difiere o se hace binario.
- **Sizing por asimetría, no por calidad:** el tamaño de una posición sale de un `min()` de caps
  independientes (evidencia, valuación, liquidez, fragilidad), no de un score. La valuación decide el TAMAÑO.

### El problema exacto

Mi núcleo de valuación "operable" para empresas que generan caja es una **perpetuidad con crecimiento
CERO**: `equity ≈ owner_FCF_TTM / r` (con `r` = costo de equity del arquetipo), más el revenue **ya
contratado** (backlog/RPO). Es decir: **el valor operable NO acredita NINGÚN crecimiento no contratado.**

Esto es correcto y disciplinado para una empresa madura. Pero **rompe estructuralmente para una growth
probada**: una empresa que crece 40%/año a `FCF/r` con g=0 sale cotizando "55× su valor operable" — no
porque esté cara, sino porque el modelo le acredita crecimiento cero. Como TODO mi universo objetivo
(small/mid de industrias del futuro) cotiza por crecimiento, **todas parecen priced-for-perfection y el
sistema las dimensiona al mínimo** → nunca participo de mi propia tesis. Confundí *anti-hype* con
*anti-crecimiento*.

Para el **pre-revenue** (~70% del universo) ya uso **reverse underwriting**: no proyecto; computo el
**crecimiento/burden que el precio EXIGE** y lo juzgo contra la evidencia (funded critical path, dilución).
Es un frame de **falsación**, no de proyección. Funciona.

### La hipótesis a pressure-testear

**Unificar TODO — incluida la growth comercial — bajo reverse underwriting.** Para una growth que ya
genera caja/revenue: computar el **crecimiento implícito que el precio demanda** (el CAGR de revenue/FCF
que haría que el precio de hoy sea "justo" a un múltiplo terminal de-riesgado), y **graduarlo contra el
crecimiento DEMOSTRADO** (histórico, citado), no contra cero. Mapear a 4 estados que ya uso, que gobiernan
el tamaño:
- **COVERED** (el precio pide ≤ lo demostrado → tamaño pleno)
- **STRETCH** (pide más, pero cerrable escalando lo demostrado → tamaño medio)
- **OPTION_PRICED** (pide un régimen nuevo no demostrado → piso)
- **NON_UNDERWRITABLE** (sin puente falsable → fuera del libro duro, va a un carril de opcionalidad capado)

### Tus preguntas (respondé TODAS, con precisión de implementación)

1. **¿Es correcto el frame?** ¿"Reverse underwriting unificado" (juzgar el crecimiento IMPLÍCITO que el
   precio demanda contra el DEMOSTRADO) es el mejor método disciplinado para valuar growth comercial
   temprana en industrias del futuro? Si no, ¿cuál es mejor y por qué? Atacá la hipótesis.

2. **Cómputo del crecimiento implícito.** Dame la mecánica concreta y determinista para computar "el CAGR
   que el precio demanda" a partir de: market cap, owner-FCF TTM (o revenue + margen), `r`, un múltiplo
   terminal de-riesgado, y un horizonte. Sé explícito con la fórmula y los supuestos (¿2 etapas? ¿qué fade?
   ¿terminal sobre qué margen normalizado?).

3. **Juzgar contra lo DEMOSTRADO (evidencia, no proyección).** ¿Qué métricas *históricas y citables*
   capturan la durabilidad del crecimiento, y son extraíbles de EDGAR/XBRL o del texto del filing?
   Priorizá por implementabilidad: revenue CAGR 3y (XBRL, fácil), expansión de margen bruto/operativo
   (XBRL), Rule of 40, NRR/retención (a veces en el MD&A/deck, difícil), cohortes/magic number (raro).
   ¿Cuáles son el núcleo mínimo robusto y cuáles diferir?

4. **Fade, estrés y castigos.** ¿Cómo fadear el crecimiento demostrado hacia la madurez sin re-importar
   hype? ¿Cómo estresar (deceleración, competencia)? El sistema ya castiga **dilución** (SBC + emisión) y
   **ejecución** (guidance-vs-actuals, insider, restatements) en ejes SEPARADOS — no los dupliques; asumí
   que el crecimiento se juzga *limpio* y la dilución/ejecución pesan aparte.

5. **Mapa a los 4 estados.** Dame los umbrales concretos (en términos de: crecimiento-implícito-demandado
   vs demostrado) que separan COVERED / STRETCH / OPTION_PRICED / NON_UNDERWRITABLE. Anclalos en base rates
   si podés (¿qué fracción de empresas sostiene 30%/40%/50% de CAGR por 5-10 años? — el "falsador de CAGR").

6. **Modos de falla y guardas.** ¿Dónde re-entra el hype con este método y qué guarda determinista lo
   frena? ¿Qué lo rompe (márgenes negativos, SBC que infla el FCF, crecimiento inorgánico por M&A,
   revenue no recurrente)?

7. **Consistencia pre-revenue ↔ growth ↔ madura.** ¿El método unificado es realmente un continuo, o hay
   discontinuidades feas en los bordes (una growth que apenas genera caja vs una que apenas no)? ¿Cómo se
   maneja el borde owner-FCF ≈ 0?

### Formato de respuesta

- Veredicto directo sobre el frame (¿sí/no/modificado?) en 3 líneas.
- La mecánica de cómputo, como pseudo-fórmula determinista implementable.
- El set mínimo de métricas demostradas (con su fuente: XBRL vs texto) y qué diferir.
- Los umbrales de los 4 estados, anclados en base rates.
- Los 3 modos de falla más peligrosos + su guarda.
- Qué NO haría (qué es sobre-ingeniería o hype disfrazado).

No asumas que tengo razón. Si el frame está mal, decímelo y dame el correcto.
