# 37 — Triangulación: ¿qué tasa de descuento usa un reverse-DCF? (mercado vs hurdle)

> Follow-up de doc 35/36. La decisión: la tasa `r` del reverse-DCF sobre T*. Surgió en la 1ª corrida en vivo.
> El operador circula a 2 IAs; el asistente prepara. Ver [[drift-valuacion-growth-reverse-underwriting]].

---

## PROMPT (copiar tal cual a cada IA, por separado)

Sos un analista quant worldclass. Ya cerramos un método de valuación; te pido resolver UN parámetro que
resultó ser la palanca dominante. Sé adversarial y concreto; no me halagues.

### Contexto (breve)

Valúo small/mid caps de industrias del futuro con un **reverse-DCF de falsación, no de proyección**: fijo el
crecimiento en lo DEMOSTRADO (histórico citado, fadeado y castigado) y **despejo `T*` = cuántos años de
compounding a ese ritmo EXIGE el precio de hoy**, con terminal g=0 (`owner-FCF/r`), a través de una superficie
de margen terminal P25/P50/P75 (tomo el peor estado). `T*` chico = barato (COVERED, tamaño pleno); `T*` grande
o sin raíz = caro (OPTION_PRICED/NON_UNDERWRITABLE, piso o fuera). La disciplina anti-hype vive en: (a) el
crecimiento entra DEMOSTRADO y capado, (b) un gate de **base rate** (¿qué fracción histórica sostuvo ese CAGR
esos años?), (c) la superficie de margen, (d) un chequeo: si >70% del universo cae en NON_UNDERWRITABLE, asumo
que MIS parámetros están mal, no el mercado.

### El hallazgo

`V(T) = Σ owner-FCF_t/(1+r)^t + terminal`. La incógnita es T, pero **todo el resultado es dominado por `r`**.
Mi tabla de `r` es el **costo de equity que uso como HURDLE en el resto del sistema**: está inflado a
propósito por iliquidez/size/stage (Growth = 15%, Pre-revenue = 25%). En la 1ª corrida en vivo, a `r=15%`,
**el 100% de los nombres comerciales salió NON_UNDERWRITABLE** (el chequeo de distribución se disparó).
Ejemplo, un SaaS rentable y limpio (owner-FCF +8% margen, creció ~9%/año demostrado, cotiza a 6× el piso g=0):

| r | T* (superficie de margen) | estado |
|---|---|---|
| 15% (mi hurdle) | sin raíz | NON_UNDERWRITABLE |
| 12% | ~12 años | OPTION_PRICED |
| 10% | ~2-12 años | OPTION_PRICED |
| 8% | ~1-2 años | STRETCH |

### La pregunta central (resolvéla y atacá ambos lados)

Un reverse-DCF que existe para **LEER el crecimiento que el mercado ya está priceando** (para juzgarlo contra
lo demostrado): ¿con qué `r` se descuenta?

- **(a) Costo de equity de MERCADO** (~9-11% para un growth mid-cap líquido): el reverse-DCF revela la
  expectativa implícita del marginal buyer; la disciplina la ponés DESPUÉS, en el gate de base-rate y el cap
  de crecimiento demostrado. Argumento: descontar a MI hurdle confunde "qué pide el precio" con "qué retorno
  quiero yo", y hace que casi todo parezca imposible.
- **(b) Mi HURDLE inflado (15%+)**: el reverse-DCF ya incorpora mi exigencia de retorno; un `T*` grande
  significa "no me da mi retorno sin crecimiento heroico", que ES la señal disciplinada. Argumento: bajar `r`
  es exactamente por donde vuelve el hype.

### Sub-preguntas obligatorias

1. **¿(a), (b), o un híbrido?** Si híbrido, ¿cuál es la construcción exacta y por qué no es arbitraria?
2. **¿Bajar `r` re-importa el hype, o la disciplina está bien relocalizada** en el gate de base-rate + cap de
   crecimiento + superficie de margen + chequeo de distribución? Sé específico sobre dónde vive la falsación.
3. **Si (a): ¿qué `r` exacto** por perfil (líquido vs ilíquido, size, sin caja vs cash-rich)? ¿Se separa del
   hurdle que uso para REQUERIR retorno en otras partes del sistema, o son el mismo número usado distinto?
4. **¿Dónde va mi exigencia de retorno (el 15%)** si NO va en `r`? (ej. ¿en el umbral de T*? ¿en el sizing?
   ¿en exigir COVERED/STRETCH y no comprar OPTION_PRICED?)
5. **Coherencia:** la MISMA tabla `r` la uso para valuar operable (perpetuidad g=0) y para el reverse
   underwriting pre-revenue. Si cambio `r` solo para el reverse-DCF comercial, ¿rompo la coherencia entre vías?
6. **Ruteo de vías:** ¿es correcto que owner-FCF ≤ 0 mande el nombre a la vía burden (pre-revenue) en vez de a
   la comercial, y que el signo de owner-FCF sea el switch? ¿O hay un criterio mejor?

### Formato

- Veredicto (a/b/híbrido) en 3 líneas, con el `r` concreto que usarías.
- Dónde vive la falsación si `r` baja (la respuesta a "¿no es esto hype otra vez?").
- Dónde va mi exigencia de retorno del 15% si sale de `r`.
- El error más peligroso de tu propia recomendación.

No asumas que tengo razón en ningún lado. Si el reverse-DCF sobre T* es el frame equivocado para decidir esto,
decilo.

---

## SÍNTESIS CERRADA (2026-08-20) — IA1 + IA2 convergieron

**La pregunta (a)/(b) era un falso binario. La respuesta: hacen falta DOS tasas, como dos LENTES.** Ninguna
mezcla; cada una hace UN trabajo y es falsable contra datos externos (el test de no-arbitrariedad: si un
parámetro "se infla a propósito", es una perilla, no un dato).

**1. Dos namespaces de tasa, en TODAS las vías (leer vs exigir):**
- **`r_mkt` = `Rf_10Y + β_sectorial_BU × ERP`** — para LEER qué pricea el mercado (piso operable, reverse-DCF,
  burden priceado). Beta **sectorial bottom-up** (no individual ruidosa de small cap), relevered si hay deuda
  material. **SIN prima de size/iliquidez/stage adentro** (esas primas "explican como riesgo lo que querés
  detectar como mispricing"). Hoy ≈ software 10% · internet-sw 11.7% · semis 11% · defensa 8.6% (Rf 4.65% +
  ERP ~4.18%, betas Damodaran). **8% está MAL** para un growth β>1 (ahí "hacés que dé" vía la tasa).
- **`h` = 15%/25% (hurdle)** — para DECIDIR si te da TU retorno (comprar, sizing, VAN del burden pre-revenue).

**2. Dos solves, dos gates (misma serie de cash-flow):**
- `T_mkt = root(V(T; r_mkt) = P)`. Sin raíz o `> T_BR` → **PRICE_NON_UNDERWRITABLE** (el mercado no lo justifica).
- Decisión: **comprás solo si `P ≤ V(T_BR; h)`** (forma limpia de IA2; equivale a "TIR implícita ≥ h" de IA1
  pero SIN el problema de raíces múltiples de la TIR con owner-FCF negativo temprano). Si no → **HURDLE_FAIL**
  (justificable, pero no te da tu retorno — NO es lo mismo que NON_UNDERWRITABLE).
- `T_BR` (base rate) = el horizonte al que ≥ cutoff de los comparables sostuvo ese CAGR. Gate DURO, binario,
  ANTES del ranking (no ponderado, no ajuste).

**3. El fix del mal-condicionamiento (las dos, central):** `T*` es hiperbólico en `(r−g)` — con g≈r, 100-200
bps lo mueven una década; a r≤g el modelo NO debe correr (artefacto). **No se cierra con un solo `T*`.** Se
cierra con una **superficie margen × (beta/tasa)**, y solo se da **COVERED si la clasificación es ROBUSTA en
toda la superficie**. Si cambia dentro de un rango razonable → estado **`RATE_SENSITIVE`** (nunca elegir la
tasa que da el resultado deseado).

**4. Dónde vive la falsación si `r` baja (no en el denominador):** el hype entra por el NUMERADOR (crecimiento/
margen/duración heroicos). Disciplina = gate de base-rate + cap de crecimiento DEMOSTRADO + margen P25. Bajar
`r` de un hurdle inflado a `r_mkt` da **capacidad discriminante** (a 15% todo es "sin raíz" = idéntico = cero
información), no laxitud.

**5. Dónde va tu 15%:** como **gate de precio/IRR ANTES del sizing** (`P ≤ V(T_BR; h)`), no solo en sizing. Un
nombre puede tener `T_mkt` soportado (no está hype-priced) pero `T_15` no (no te da tu retorno) → no full size.
Exigir solo COVERED a `r_mkt` NO alcanza: si se cumple lo priceado, ganás ~retorno de mercado, no 15%.

**6. Chequeo de distribución de DOS lentes:** mucho "sin raíz a `r_mkt`" → bug de inputs/caja/código. Mucho
"HURDLE_FAIL a `h`" → **puede ser correcto** (tu universo no ofrece 15% hoy) → **NO relajes el hurdle** para
"arreglar" esa distribución.

**7. Ruteo por owner-FCF DURABLE (tri-estado):** `COMERCIAL = OFCF_TTM>0 ∧ ΣOFCF_3FY>0 ∧ (#FY+ ≥ 2/3)`. Con
revenue/GP pero sin pasar → `PRE_FCF_BURDEN`. Sin GP relevante → `PRE_REVENUE/BINARY`. Los del medio → ambas
vías, peor resultado. El signo puntual de owner-FCF es necesario pero NO suficiente (discontinuo/ruidoso/
manipulable). Cash-rich → valuar caja aparte (restarla del precio, sacar su interés del owner-FCF). Apalancada
→ relever β o FCFF/WACC (consistencia flujo-tasa: equity-FCF↔CoE, firm-FCF↔WACC).

**8. Dos meta-reglas de yapa:**
- **Presupuestar el conservadurismo UNA vez** (IA1): hoy se apila g-cap ×0.75 · terminal-g0 ×0.7 · P25 ×0.8 ·
  r-inflado ×0.17 ≈ 7% del fair value → nada pasa por construcción, y el r-inflado solo es ~80% del haircut.
- **BACKTEST antes de cerrar tasas/umbrales** (IA1, IA2 lo apoya vía RATE_SENSITIVE): correr el sistema sobre
  el universo 2016 con datos 2016 → ¿los COVERED superan a los OPTION_PRICED a 5 años? Si no separan, el frame
  no tiene poder predictivo (es teología). Si separan, el backtest CALIBRA en vez de argumentar. Necesita bulk
  XBRL point-in-time (P1). **Esto es el gate meta: la evidencia empírica manda sobre el razonamiento a priori.**

**Implicancia:** doc 36 se actualiza (dos tasas, gates `T_mkt`+`P≤V(T_BR;h)`, estado `RATE_SENSITIVE`, ruteo
durable) y el código construido (un `r`, un `T*`) se ajusta. Ver tarea de build (reverse-DCF).
