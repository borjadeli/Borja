# 19 — Revisión del análisis de empresas (para triangular)

> ⚠️ **SUPERADO (2026-07) — ver `00_MAPA_DOCUMENTOS.md`.** Los problemas que planteó (bull/bear inestable,
> asimetría inflada) **ya se resolvieron** (doc 32 §8 + doc 14 §D/E). Fue el insumo, no el estado actual.

> Cómo el sistema evalúa UNA empresa hoy: arquetipo → gate → quality → bull/bear →
> asimetría → fragility → mérito → hard cap. Grounded en el código. El objetivo es
> dejarlo **fundado y estable** — porque todo lo de abajo (sizing, PM, cartera)
> cuelga de estos números. Evidencia del problema al final.

## Contexto (para una IA externa)
Sistema quant de small/mid caps de "industrias del futuro" (cuellos de botella).
**Principio rector:** los datos y límites duros son deterministas; el LLM trae hechos
con fuente y NUNCA inventa un número de decisión. La decisión (arquetipo, gate,
score, sizing) es 100% determinista. Queremos verificar que ese principio se cumple
en cada pieza del análisis, y que los números resultantes sean sólidos y estables.

---

## La cadena de análisis, pieza por pieza

### 1. Arquetipo — `backend/nucleo/arquetipo.py`  ✅ FUNDADO
Clasifica en Madura / Growth / Tracción / Pre-revenue / Binary a partir del **revenue
elegible** (ASC 606, default-exclude: saca grants/NRE/milestones) + regla ex-top
(cliente >50% o top-2 >66% → resta ese revenue) + tabla determinista:
`Binary` (flag) · `<$10M`→Pre-revenue · `$10-50M`→Tracción · `≥$50M & crec≥25%`→Growth ·
`≥$50M, crec<25%, FCF+`→Madura · resto→Tracción.
**Evaluación:** determinista desde hechos citados. Sólido.

### 2. Gate de evidencia — `backend/nucleo/gate.py`  ✅ FUNDADO
Checklist pasa/no-pasa (todos los ítems deben pasar; sin score, sin compensación):
U1 (2-4 triggers con forma completa: hecho+umbral+fecha+fuente), U2 (fuente mínima
A/B/C), ítems por arquetipo (M1 / G1-G2 / T1-T2 / P1-P3 / B1-B3), financiación-hasta-
el-hito. Devuelve pasa / no_pasa / todavía_no (timing → watchlist).
**Evaluación:** determinista, hechos con fuente. Sólido. Es la mejor defensa del sistema.

### 3. Quality tier — `backend/nucleo/quality.py`  🟡 DETERMINISTA, PESOS NO VALIDADOS
Suma puntos y corta en tiers 1-4. Pesos actuales:
- margen bruto ≥50% → +2 · ≥30% → +1
- margen en expansión → +1
- crecimiento orgánico ≥25% → +2 · ≥10% → +1
- revenue recurrente → +1
- ≥3 hechos comerciales → +2 · ≥1 → +1
- ventaja estructural → +1
Cortes: ≥6→tier4 · ≥4→tier3 · ≥2→tier2 · resto→tier1.
**Evaluación:** determinista, pero los puntos/cortes son *"primera aproximación no
validada"* (lo dice el propio código). ¿Están bien ponderados? ¿Faltan/sobran señales?

### 4. Bull / bear — prompt `prompts/extractor_hechos_v2.txt` + `extractor.py`  🔴 LA PATA FLOJA
**Hoy el LLM emite bull y bear como PRECIO ABSOLUTO, directo.** El prompt le pide
"anclar con un múltiplo razonable (EV/S, EV/EBITDA, P/E)", pero **el número final lo
pone el LLM**. `extractor.py` los mapea tal cual a `EntradaEmpresa.bull/bear`.
**Evaluación:** viola el principio rector (el LLM inventa un número de decisión). Es la
fuente de los artefactos (ver evidencia: TENB asimetría 19.92). **El fix ya está
diseñado y construido** (`backend/nucleo/valuacion.py`): el LLM trae fundamento citado
+ pares; un motor determinista computa bull/base/bear (múltiplo = P25/P50/P75 de pares,
EV→equity, descuento por arquetipo, winsorize 5:1). **Falta cablearlo.**

### 5. Asimetría — `backend/nucleo/sizing.py`  ✅ FÓRMULA OK / basura entra, basura sale
`asimetria = (bull − precio) / (precio − bear)`; None si precio ≤ bear.
**Evaluación:** la fórmula es correcta, pero hereda la basura del bull/bear (#4).

### 6. Fragility — `backend/nucleo/fragility.py`  🟡🔴 TABLA OK, FLAGS SUBJETIVOS
Score 0-3, se evalúa de 3 hacia 0 (el más severo gana):
- Frag 3: `punto_unico_de_falla` (sin valor residual si falla)
- Frag 2: `bull_depende_evento_discreto` OR `concentración >50%` OR `financiación externa no firmada`
- Frag 1: `dependencia_con_respaldo` OR `concentración 30-50%` (default conservador si no se acredita robustez)
- Frag 0: `financiación completa cerrada` AND `redundancia comercial real`
**Evaluación:** la tabla es determinista, PERO varios flags de entrada (`punto_unico_de_falla`,
`bull_depende_evento_discreto`, `es_binary`) **los pone el LLM como juicio**, no como
hecho duro con fuente. Ej.: AAOI recibió Frag 3 ("único punto de falla") por criterio
del LLM. ¿Cómo fundamentar/objetivar estos flags?

### 7. Mérito — `backend/nucleo/sizing.py`  🔴 ORDINAL × RATIO SIN TECHO
`mérito = quality_tier × asimetría`. El tier es **ordinal (1-4)**; la asimetría es un
**ratio continuo sin techo**. Multiplicarlos explota: TENB dio **mérito 79.66** (tier ×
asimetría 19.92). Además, el mérito hoy se usa para **repartir capital proporcional**
(selector viejo), lo que hace el sizing hipersensible a la escala.
**Evaluación:** doble problema. Fix diseñado: (a) asimetría **acotada/categórica** +
winsorize; (b) mérito **cóncavo** (`merito_ranking` = tier × √asimetría, ya construido);
(c) separar **ranking** (mérito ordena) de **sizing** (lo decide el PM dentro de caps).

### 8. Hard cap — `sizing.py` + tabla `CAPS_ARQUETIPO_FRAGILITY`  ✅ FUNDADO
`hard_cap = min(cap_celda[arquetipo][fragility], cap_CRR, techo 40%)`. Tabla de caps
por arquetipo × fragilidad (ej. Growth×Frag3 = 11%). Sólido — el riesgo limita el tamaño.

---

## Evidencia del problema (smoke real, 2026-07-28)
- **TENB** entró al PM con **asimetría 19.92 → mérito 79.66** (bull/bear crudo del LLM).
  El PM, racionalmente, lo puso de ancla al 24% — sobre un número inflado.
- **AAOI**: Growth que pasa el gate, tier 3, crecimiento 132% — pero **Frag 3 por un flag
  del LLM** ("único punto de falla") → hard cap 11%. ¿Está bien fundado ese flag?
- **Consecuencia:** entre dos corridas la cartera cambió radicalmente. La causa NO es el
  PM (razonó coherente) sino los **inputs inestables/inflados** (mérito). Garbage in →
  garbage out. Si el análisis es sólido y estable, el PM arma carteras estables.

---

## Preguntas para triangular
1. **Bull/bear:** ¿el enfoque de sacarlo del LLM y computarlo con fundamento×múltiplo de
   pares (motor `valuacion.py`) es correcto? ¿Trampas?
2. **Mérito:** ¿`tier × asimetría` es estructuralmente sano si se acota la asimetría y se
   hace cóncavo, o hay que rediseñarlo del todo? ¿Cómo evitar que un solo input domine?
3. **Fragility:** los flags subjetivos del LLM (`punto_unico_de_falla`, `es_binary`,
   `bull_depende_evento_discreto`) — ¿cómo objetivarlos/fundamentarlos, o se acepta que
   sean juicio con justificación citada?
4. **Quality:** ¿los pesos (margen 2/1, crecimiento 2/1, wins 2/1, etc.) y los cortes de
   tier son razonables, o los recalibrarías? ¿Falta alguna señal de calidad importante?
5. **Estabilidad:** ¿qué haría que dos corridas sobre datos similares produzcan méritos y
   carteras similares? (más allá de histéresis en el PM).
6. **Visión global:** ¿la cadena arquetipo→gate→quality→asimetría→fragility→mérito tiene
   algún error estructural, o es sólida y solo hay que arreglar bull/bear + mérito?

Devolvé crítica concreta, priorizada, y dónde discrepes tu alternativa. Sin sobreingeniería:
buscamos algo **fundado, simple y estable**, no un modelo de investment bank.
