# 44 — Doble validación: fidelidad de proceso (A) + superioridad vs análisis objetivo (B)

> Dos chequeos que pidió el operador. **A:** otras IAs aplican NUESTRO método a los datos → ¿ejecutamos bien el
> proceso? **B:** otras IAs analizan con SU método → ¿el nuestro le gana a una IA objetiva? (Si no, el proyecto
> no tiene sentido.) Complementa doc 43 (prompt neutral de B). SHADOW.

## Cómo se corre

1. **Nuestra salida:** `.venv/bin/python -m ops.ficha_profunda <TICKERS>` (análisis rebalanceado legible) +
   `.venv/bin/python -m ops.dump_datos <TICKERS>` (los HECHOS crudos que el método consume, para el chequeo A).
2. **Chequeo A:** dar a 1-2 IAs el **método portable** (§Método abajo) + el dump de datos del ticker → que lo
   EJECUTEN → comparar contra nuestra salida. Divergencia = bug nuestro O ambigüedad del método O error del externo.
3. **Chequeo B:** dar a 1-2 IAs el prompt NEUTRAL (doc 43) — SIN el método — → que analicen a su criterio →
   comparar conclusiones. La vara: **nuestro veredicto debe ser ≥ tan bueno y MÁS disciplinado.**

---

## MÉTODO PORTABLE (para el Chequeo A — dárselo a la IA externa junto al dump de datos)

> Aplicá EXACTAMENTE estas reglas al dump de datos de la empresa. No agregues tu opinión; ejecutá el proceso.
> Devolvé: (1) ruteo, (2) estado de valuación, (3) elegibilidad por pilares, (4) decisión, (5) tamaño.

### 1. Ruteo — ¿qué gramática de valuación? (todo con los datos del dump)
- `owner_FCF = CFO − capex − SBC`. `fcf_pre_sbc = CFO − capex` (solo para el ruteo).
- Si `SBC/revenue > 0.25` sostenido → **BURDEN** (motor comercial ficticio). Fin.
- Si NO hay revenue recurrente (grants/NRE no cuentan) + hay hito nombrado + base-rate del hito con n≥20 →
  **PRE_REVENUE_BINARIO**. Sin hito/base-rate → **BURDEN** (floor-only).
- Si `revenue>0 ∧ GP>0 ∧ owner_FCF>0` (en ≥2 de últimos 4Q) → **COMERCIAL_MADURO**.
- Si `revenue≥$50M ∧ gross_margin≥55% ∧ Δ8Q(GP)/Δ8Q(OpEx)>1.0 ∧ runway≥24m` → **COMERCIAL_ESCALANDO** (el
  "good-loser": pierde caja pero ESCALA — apalancamiento operativo demostrado). `OpEx = GP − OperatingIncome`.
- Si no calificó (pierde caja SIN apalancamiento) → **BURDEN**.

### 2. Valuación — reverse underwriting de FALSACIÓN (no proyección)
**Comercial (MADURO/ESCALANDO):** fijá el crecimiento en lo DEMOSTRADO (`g_D` = CAGR 3FY per-share, capado ~40%,
fadeado hacia 3%), y despejá **`T*` = cuántos años de compounding a ese ritmo EXIGE el precio de hoy**, con
terminal g=0 (perpetuidad `owner-FCF/r`), descontado a `r_mkt≈10%` (costo de equity de mercado, NO tu hurdle),
barriendo una superficie de margen terminal maduro {P25,P50,P75}. Mapa: `T*≤3→COVERED · ≤7→STRETCH · ≤12→
OPTION_PRICED · else/sin raíz→NON_UNDERWRITABLE`. ESCALANDO se capa a **OPTION_PRICED** (sin apalancamiento
demostrado no autoriza core). **NUNCA** uses TAM×penetración, guidance de management, ni price targets.

**Pre-revenue/burden (BURDEN con backlog):** `reverse_burden = (opex_cash + FCFE_req)/GP`; bandas `≤3→COVERED ·
≤12→STRETCH · >12→OPTION_PRICED`; sin puente falsable (pura opción) → NON_UNDERWRITABLE.

### 3. Pilares — elegibilidad (SCORING, no gate conjuntivo)
3 pilares: **demanda-por-cuello** (¿demanda real contratada/recurrente, materialidad, posición en el cuello?),
**economía** (márgenes, unit economics, recurrencia), **ejecución** (dilución 3y, insider Form-4, SBC/rev,
restatements). Cada uno CRÍTICO/DÉBIL/SUFICIENTE/FUERTE. **La ÚNICA exclusión dura es el VETO DE SUPERVIVENCIA**
(restatement/material-weakness, going-concern, dilución tóxica) → REJECT. Un CRÍTICO de "no funciona" (economía
floja) BAJA el score pero NO excluye. **UNKNOWN ≠ negativo.**

### 4. Decisión (4 estados)
- **REJECT** = veto de supervivencia / no elegible.
- **WATCH** = evidencia insuficiente (cobertura < umbral) → cola de investigación (NO es "no").
- **UNDERWRITTEN** = sobrevivió + evidencia suficiente + valuación underwritable (COVERED/STRETCH/OPTION_PRICED)
  → tamaño CORE.
- **PROBE** = elegible pero valuación NON_UNDERWRITABLE (pura opcionalidad) → probe CHICO.

### 5. Sizing = min de caps independientes (no-compensatorio)
`size = min(cap_tier_capital, cap_valuación, cuota_arquetipo)`. cap_tier: A=8%/B=5%/C=2.5%. cap_valuación:
COVERED=8%/STRETCH=4%/OPTION_PRICED=2%/NON_UNDERWRITABLE=0. El juicio puede mover DENTRO de [base, cap], NUNCA
sobre el cap. Pre-hito: solo probe, nunca core.

---

## Rúbrica de comparación

**Chequeo A (fidelidad):** por ticker, ¿la IA externa llegó al MISMO ruteo / estado de valuación / decisión que
nuestro `ficha_profunda`? Cada divergencia se clasifica: **(i) bug nuestro** (el externo aplicó bien y nosotros
mal) · **(ii) ambigüedad del método** (la regla no era determinista) · **(iii) error del externo** (aplicó mal).
Meta: ≥80% de convergencia; toda divergencia tipo (i)/(ii) es un fix.

**Chequeo B (superioridad):** por ticker, comparar nuestro veredicto vs el objetivo del externo. Ganamos si:
**(a)** cazamos un red-flag de supervivencia que el externo pasó (caso NABL) · **(b)** fuimos más disciplinados
con la valuación (no compramos hype que el externo racionalizó) · **(c)** distinguimos bien comercial/pre-rev/
binaria donde el externo mezcló. Perdemos (= a corregir) si: el externo vio un catalizador forward REAL que
descartamos por falta de dato (→ es el hueco que el juicio del Bloque 3 debe cubrir), o si fuimos duros sin razón.

**Vara honesta:** NO se le pide al sistema predecir shocks exógenos (VRT/LEU 2022, doc 32). Se le pide ser
**más SENSATO y DISCIPLINADO con la evidencia disponible** que una IA objetiva. Ese es el edge o no lo es.
