# 56 — Brief de P1 (para triangular/auditar antes de codear)

> **Qué es P1 y por qué.** El smoke real (2026-10-27, doc 53) probó que el pipeline v2 corre end-to-end, pero
> **los 3 nombres salieron REVIEW** con un único motivo: *"la tesis se apoya en declaración de empresa"*. Sin
> evidencia verificable (calculadoras + fact store), ningún claim central llega a **PASS** → el PM nunca
> compra (hoy eligió caja, con disciplina). **P1 es lo que destraba las compras.** Mismo método que docs
> 54/55: converger con 2+ IAs antes de codear. Contexto: doc 51 (directiva), 52 (plan), 53 (estado), 49
> (por qué Opus agéntico), 33 (método de análisis canónico).

## 0. Qué YA existe (no se re-discute; se CABLEA)
Conservado de v1, hoy **desconectado del data pack v2**:
- **Calculadoras** (`backend/nucleo/`): `valuacion_reverse` (`t_star`, `estado_valuacion_reverse`) ·
  `crecimiento` (`crecimiento_demostrado`, `fade` → g_D) · `dilucion` (`dilucion_forward`) ·
  `sizing_burden` (`size_burden`, `t_fade`) · `capital_raise_risk` (`calcular_crr_ticker`) ·
  `pre_revenue` (`evaluar`, `reverse_burden_gp`, `gap_financiamiento`). Owner-FCF.
- **Motor de evidencia citado** (`backend/nucleo/`): `fact_store` (guardar/`snapshot_vigente` por CIK/ticker,
  con `known_at`) · `extractor_citado` (`HechoCitado`, `verificar_cita` = la cita aparece en el texto fuente,
  `contrastar_xbrl` = el número coincide con XBRL ±tol, `verificar_entailment` = un LLM confirma que la cita
  respalda el claim) · `retrieval`/`gold_retrieval` (recall medido 88%, doc "motor-evidencia-medido-solido").
- **Data pack v2** (`backend/agentes/data_pack.py`): hoy una sola `Fuente` (mercado). El diseño ya es
  enchufable: `Fuente = (ticker, as_of) -> list[DataPoint]`, cada `DataPoint` con `kind` (ORIGINAL/DERIVED),
  `source`, `known_at`, `inputs`.
- **Verificador v2** (`backend/agentes/verificador.py`): hoy chequea **procedencia** (la URL es trazable). El
  smoke mostró su límite: un claim con cita de la empresa → REVIEW ("declaración de empresa"), nunca PASS.

## 1. El problema exacto a resolver (del smoke)
`VerificationReport.veredicto = review` cuando un claim central es `company_statement`. Para que el sistema
**pueda comprar**, un claim central tiene que poder alcanzar **PASS** con evidencia **verificada**, no
declarada. Eso requiere: (a) datos duros con procedencia en el data pack (calculadoras + fact store) y (b) un
verificador que mire **contenido**, no solo que la URL exista.

## 2. Diseño propuesto (a converger)

### 2.1 Contrato data pack ↔ calculadoras
Cada calculadora se expone como una **`Fuente`** del data pack que devuelve `DataPoint`s `kind=DERIVED` con
`inputs=[métricas que usó]` y `source` = la calculadora + sus hechos fuente. Ej.: `fuente_valuacion` corre
`t_star(...)` y emite `DataPoint(metric="t_star", value=..., kind=DERIVED, inputs=["revenue_ttm","g_D",...],
source=Source("reverse-DCF", ...), known_at=<known_at del hecho más viejo>)`. **El data pack sigue siendo
INPUT, nunca veredicto** (anti-anchoring, doc 49): el Analista ve `t_star`/`burden`/`runway`, no "comprá".

**Insumos de las calculadoras** = hechos del `fact_store` (revenue, FCF, cash, shares, deuda, SBC...). Si un
insumo falta → la calculadora devuelve `None`/no emite el DataPoint (binario/null, doc
"implementabilidad-como-gate"); nunca inventa.

### 2.2 fact_store como fuente de hechos extraídos
El ETL de hechos (EDGAR + `extractor_citado`) puebla el `fact_store` con `HechoCitado` (valor + cita + fuente
+ `known_at` + estado de verificación). El data pack lee `snapshot_vigente(ticker, as_of)` → alimenta 2.1.
**Gate de implementabilidad:** solo se cablea el hecho que es *sourceable + extraíble + verificable* hoy; el
resto queda null y se difiere (no se finge cobertura).

### 2.3 Verificador de CONTENIDO (el corazón de P1)
Un claim central deja de ser "declaración de empresa" y alcanza **PASS** cuando pasa un chequeo de contenido,
reusando `extractor_citado`:
- **`verificar_cita`**: el `cited_text` del claim aparece literalmente en la fuente citada (no inventado).
- **`contrastar_xbrl`**: si el claim lleva un número, coincide (±tol) con el valor XBRL del fact store.
- **`verificar_entailment`** (Sonnet): la cita efectivamente **respalda** el claim (no un non-sequitur).
- Regla de veredicto: claim central con cita verificada + número contrastado → cuenta como **hecho** (PASS
  posible). Claim central que es solo `company_statement` sin contraste → sigue **REVIEW**. Falta de
  procedencia en central → **FAIL** (sin cambios).
- `numeros_ok` y `dato_vigente` dejan de ser `True` fijo: salen del contraste XBRL y del `page_age`/`known_at`.

### 2.4 Contexto del mapa al Analista
`contexto_fn(ticker)` (hoy `""`) arma el contexto del cuello desde `nx_*`: nodo primario, estado del cuello,
dependencias (empresas vinculadas al mismo nodo). Le da al Analista el "por qué ahora" del mapa.

### 2.5 Candidatos desde el universo
Armar los candidatos desde `nx_empresa` (activas) con **`SenalesTriage` reales**: `dias_desde_dossier` (del
cache), `hechos_nuevos` (filings EDGAR nuevos desde el último `known_at`), `dias_a_evento` (próximo earnings),
`precio_vs_tesis_pct` (market_data), `prioridad_cuello` (del mapa). Cablear el runner al scheduler (semanal).

## 3. ⭐ DECISIONES ABIERTAS (a converger con la auditoría)
1. **Umbral de PASS.** ¿Cuántos claims centrales verificados-por-contenido hacen falta para PASS, y de qué
   tipo? ¿Basta 1 hecho central contrastado con XBRL, o se exige que TODA la tesis central tenga respaldo?
   **Default:** PASS si todos los `tesis_claims_soporte` pasan contenido; si alguno queda en company_statement
   → REVIEW; si alguno central sin procedencia → FAIL.
2. **Qué calculadoras entran en P1 (y cuáles se difieren).** Orden por implementabilidad: owner-FCF, dilución,
   runway/CRR parecen directas desde el fact store; reverse-DCF/`t_star` y burden necesitan g_D y márgenes
   (más insumos). **Default:** cablear primero las de pocos insumos; `t_star`/burden detrás.
3. **Pre-revenue (70% del universo).** El método canónico para pre-revenue (doc 31/33) es reverse
   underwriting + funded critical path + dilución, NO owner-FCF/DCF. ¿El data pack emite para pre-revenue
   `gap_financiamiento`/`reverse_burden_gp`/runway en vez de `t_star`? **Default:** sí, ruteo por `stage`.
4. **Costo del verificador de contenido.** `verificar_entailment` por claim central = llamadas Sonnet extra.
   ¿Por claim, o batch? ¿Cuánto sube el costo/nombre vs el smoke ($0.70)? **Default:** batch por dossier,
   solo claims centrales.
5. **Freshness del fact store.** ¿Cada cuánto se re-extrae un nombre? El hash del data pack (ya arreglado)
   invalida el dossier cuando cambia un hecho material; pero el fact store hay que re-poblarlo. **Default:**
   re-extracción por evento (filing nuevo) + TTL.
6. **XBRL: cobertura real.** `contrastar_xbrl` depende de que el valor exista en companyfacts; la memoria
   "extraccion-xbrl-triangulada" dice que companyfacts tiene techo (sin extension tags ni dimensionales).
   ¿Qué fracción de los números centrales se puede contrastar hoy? Si es baja, el PASS se vuelve raro.
   **Default:** medir cobertura antes de prometer; donde no hay XBRL, el claim queda REVIEW (no PASS).

## 4. Lo que NO se re-abre
El paradigma (doc 51), el método de análisis canónico (doc 33), el comité ya construido (54), la capa de
decisión + P0/r2 (55 + auditorías). P1 es **cablear evidencia verificada al data pack y endurecer el
verificador**, no rediseñar el análisis ni quién decide.

## 5. Para los otros puntos de auditoría (además de este brief)
- **Corrección numérica de las calculadoras:** leer `backend/nucleo/{valuacion_reverse,dilucion,
  sizing_burden,capital_raise_risk,pre_revenue,crecimiento}.py` — van a ser la fuente de verdad del data pack.
- **Calidad de los 3 dossiers reales del smoke:** ver `init_docs/56_smoke_dossiers.md` (export completo) —
  ¿el análisis agrega valor o alucina números? (tesis del doc 49).
