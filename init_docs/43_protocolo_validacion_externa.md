# 43 — Protocolo de validación externa (chequeo fuerte + comparación)

> Para validar que el sistema rebalanceado produce análisis SENSATO, contrastándolo contra un análisis
> independiente y CIEGO a nuestro método (si la IA externa ve nuestro framework, la convergencia no significa
> nada — lección de los subagentes contaminados). Pedido del operador: "chequear fuerte que funcione bien y
> comparar con otros análisis". SHADOW.

## Cómo se corre

1. **Nuestra ficha:** `.venv/bin/python -m ops.ficha_profunda CLS RBRK LEU TENB S VRNS KLIC MP UEC NABL`
   → produce el análisis rebalanceado legible (ruteo → valuación reverse-DCF/burden → 3 pilares scoring →
   decisión UNDERWRITTEN/PROBE/WATCH/REJECT), con evidencia citada.
2. **Análisis externo CIEGO:** copiar el prompt de abajo a 1-2 IAs, POR NOMBRE, SIN mostrarles nuestro método.
3. **Comparar** (§Rúbrica): ¿converge la conclusión de fondo? Donde diverge, ¿por qué? La divergencia es
   información (o un bug nuestro, o un blind-spot del externo).

## PROMPT NEUTRAL (copiar por ticker, sin revelar nuestro framework)

> Sos un analista de inversiones institucional, escéptico y riguroso. Analizá **[TICKER]** en profundidad como
> oportunidad de inversión a 3-5 años. Quiero tu juicio honesto, no un resumen de la empresa.
>
> Estructurá así:
> 1. **Qué hace y de dónde viene el revenue** (¿contratado/recurrente o especulativo? ¿concentración?).
> 2. **¿El precio actual está justificado por los fundamentals?** ¿Qué crecimiento/márgenes futuros exige el
>    precio de hoy, y es plausible contra lo que la empresa YA demostró? Sé cuantitativo.
> 3. **Forward-looking:** ¿hacia dónde va? ¿Qué tendría que pasar para que sea un multibagger, y qué
>    probabilidad real le das? ¿Qué la mata?
> 4. **Calidad de management y cap table** (dilución, SBC, insider activity, gobernanza).
> 5. **Veredicto:** ¿comprar / esperar / evitar? ¿A qué tamaño de posición (core / especulativa chica / nada)?
>    ¿Qué evidencia concreta te haría cambiar de opinión?
>
> Basate en hechos verificables (filings, datos duros). No uses price targets de sell-side ni TAM de la empresa
> como si fueran hechos. Si no tenés datos suficientes para una parte, decilo en vez de inventar.

## Rúbrica de comparación (por nombre)

| Dimensión | Nuestro sistema | IA externa | ¿Converge? |
|---|---|---|---|
| ¿Comprar/esperar/evitar? | decisión (UNDERWRITTEN/PROBE/WATCH/REJECT) | veredicto | |
| ¿Caro o barato vs lo demostrado? | estado valuación (COVERED..NON_UNDERWRITABLE) | punto 2 | |
| Tamaño (core / probe / nada) | cap de sizing + estado | punto 5 | |
| Red flag de supervivencia | veto supervivencia / flags | punto 4 | |
| Naturaleza (comercial/pre-rev/binaria) | ruteo | punto 1/3 | |

**Qué buscamos:** (a) convergencia en el veredicto de fondo = el sistema es sensato; (b) donde el sistema es MÁS
disciplinado que el externo (ej. cazó un red flag que el externo pasó — caso NABL material weakness) = el edge;
(c) donde el externo ve algo forward que el sistema NO (ej. un catalizador cualitativo) = el hueco que el juicio
acotado (Bloque 3) debe cubrir; (d) donde el sistema es DEMASIADO duro sin razón = miscalibración a corregir.

## Antecedentes (validaciones previas)

- **NABL:** el sistema lo vetó por material weakness declarada que el merito viejo no cazó → el edge de disciplina.
- **S (SentinelOne):** el disciplinado y el sistema coincidieron en la sobriedad vs el hype; RPO $0.8B conservador.
- **Backtest 2022 (doc 32):** los 10x (VRT/LEU) fueron shocks EXÓGENOS no visibles en fundamentals → un frame
  fundamental no separa bien; se necesita juicio+recall. La validación externa NO debería esperar que el sistema
  "predijo" VRT — debería esperar que el sistema es SENSATO y DISCIPLINADO con la evidencia disponible.
