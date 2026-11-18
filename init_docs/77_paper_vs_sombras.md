# 77 — El paper del PM vs las carteras sombra (primer corte)

> **Estado:** primer corte (2026-11-18). **No es un veredicto** — doc 59 §6: no esperar nada estadísticamente
> significativo antes de 12-18 meses. Esto es un chequeo de salud del método, no una medida de edge.

## Qué se mide
Desde el día 1 (Capa E, doc 51/52) el sistema registra, en cada ciclo, varias carteras contrafácticas
point-in-time y encadena su curva de equity (base 1.0). La vara responde: **¿el comité + el PM AGREGAN** sobre
alternativas más baratas/tontas? Baselines deterministas (solo precios, sin LLM salvo `opus_solo`):

- **`pm`** — las posiciones reales del paper (el valor del sizing del PM).
- **`opus_solo`** — "Opus+web solo" sin comité (la vara que dice si el COMITÉ agrega sobre un LLM crudo).
- **`ew_pass`** — equal-weight de los nombres PASS del ciclo (el valor de la SELECCIÓN, sin sizing).
- **`spy`** — índice amplio (¿el picking le gana al mercado?).
- **`etf_smh/ura/ita/copx`** — ETFs temáticos (¿le gana al tema?).

## Resultado al 2026-11-18 (≈3 semanas, 14 ciclos; inicio 2026-10-28)

| Cartera | Índice | Retorno | Lectura |
|---|---|---|---|
| **pm** | **0.9922** | **−0.78%** | el PM protegió capital |
| opus_solo | 0.9736 | −2.64% | el comité agregó sobre el LLM crudo |
| ew_pass | 0.9477 | −5.23% | el sizing del PM > equal-weight |
| spy | 0.9470 | −5.30% | le ganó al mercado |
| etf_ura | 0.8271 | −17.29% | — |
| etf_smh | 0.8133 | −18.67% | — |
| etf_copx | 0.8011 | −19.89% | — |
| etf_ita | 0.9935 | −0.65% | ⚠️ **no confiable** (ver nota de datos) |

**Decisiones del período (38):** caja 11 · mantener 17 · comprar 6 · vender 2 · recortar 1 · aumentar 1.

## Lectura (con todas las cautelas)
En una ventana de 3 semanas en que el universo temático cayó **−17% a −20%** y el mercado amplio **−5.3%**, el
PM terminó en **−0.78%**: le ganó a TODOS los benchmarks limpios. El patrón de decisiones lo explica —mayoría
`caja`/`mantener`, pocas compras— que es exactamente la **doctrina PACIENCIA** (doc 80): no estar invertido por
estar; desplegar solo con margen de seguridad; estacionar el residual. En un mercado a la baja, esa disciplina
protege. Dos señales direccionalmente buenas:
1. **pm > ew_pass** → el *sizing* del PM agrega sobre comprar lo mismo equal-weight.
2. **pm > opus_solo** → el *comité* (Analista/Bear/Verificador/Auditor) agrega sobre un Opus+web crudo.

**Lo que esto NO dice:** nada sobre el edge en un mercado alcista (donde la PACIENCIA puede quedar atrás), ni
nada estadísticamente sólido (n diminuto; una sola configuración de mercado). El valor del power-law se mide en
ciclos, no en semanas. Esto solo confirma que el método **no está roto** y se comporta como su doctrina dice.

## ⚠️ Nota de datos — `etf_ita` no es confiable en este corte
El índice `etf_ita` arrastró un **print corrupto**: ITA cotizó $213.70 (04/11) y el proveedor devolvió $71.73
(13/11) —un split fantasma / dato sucio de yfinance, no un retorno real (ITA defensa no cayó 66%)—. Como el
índice es multiplicativo, ese único dato lo hundía a 0.333 (falso −66%). Se agregó un **guard** (`carteras_sombra.py`,
`_MAX_MOVE_PASO=0.50`): un retorno de 1 ticker en un paso con |r|>50% se descarta (carry-forward), y como la curva
se recomputa desde el raw, **sanó la curva histórica** (0.333→0.9935) sin reescribir el ledger. Pero el guard
CONGELA el índice en el nivel previo al print malo: no es un ajuste de splits de verdad, así que `etf_ita` queda
**aproximado, no benchmark**. Pendiente real: precios split-adjusted en la fuente. Los otros ETFs no tienen el
problema.

## Qué falta para que esto valga
- **Tiempo:** doc 59 §6 — horizonte 12-18 meses antes de leer edge.
- **Más baselines:** la contrafáctica "PM+veto-auditor" (hook ya previsto en `carteras_sombra.py`).
- **Precios split-adjusted** para que los ETF temáticos sean benchmark confiable.
- **Régimen alcista:** este corte es íntegramente un mercado a la baja; la PACIENCIA se tiene que medir también
  cuando el costo de oportunidad de la caja es alto.
