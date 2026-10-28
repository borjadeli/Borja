# 60 — Medición de cobertura XBRL (gate de alcance de P1)

> El gate que ambas auditorías exigieron antes de cerrar D1/D6 (docs 57 §5, 58 §5). Determinista, sin LLM:
> ¿los números centrales reales se pueden contrastar en **companyfacts**, o P1 necesita el **parser del
> instance XBRL** (el componente caro)? Muestra: los 12 claims centrales del smoke (OKLO/RKLB/ACHR), que son
> 2/3 pre-revenue. Fuente: `data.sec.gov/api/xbrl/companyfacts` vía `backend/services/edgar.py`.

## Cobertura de conceptos us-gaap/dei (medido en vivo 2026-10-28)
Para los 3 CIK, companyfacts trae —y al **Q2-2026**, no solo FY25:
| concepto | OKLO | RKLB | ACHR |
|---|---|---|---|
| OperatingIncomeLoss | ✓ (−73.2M) | ✓ (−57.5M) | ✓ (−279.2M) |
| NetCashProvidedByUsedInOperatingActivities | ✓ | ✓ | ✓ |
| CashAndCashEquivalentsAtCarryingValue | ✓ (1.64B) | ✓ (2.13B) | ✓ (852.7M) |
| Revenue (RevenueFromContract… / Revenues) | ✓ | ✓ | ✓ |
| GrossProfit / CostOfRevenue | ✗ (sin ingresos) | ✓ | ✗ (pre-rev) |
| StockholdersEquity | ✓ | ✓ | ✓ |
| Goodwill / Intangibles | ✓ | ✓ | parcial |
| EntityCommonStockSharesOutstanding | ✓ (186.0M) | ✓ (598.4M) | ✓ (770.0M) |

## Clasificación de los 12 centrales en los 5 cubos
- **Contrastable en companyfacts (financiero estándar, ~8 átomos):** OKLO caja/pérdida op./burn · RKLB
  revenue/GM · ACHR equity/acciones/dilución/NTBV-derivable. **El backbone de supervivencia y dilución del
  pre-revenue ESTÁ.**
- **Non-GAAP con componentes en companyfacts:** ACHR "liquidity US$2.0B" (cash + ST investments).
- **Hecho posterior / KPI (no companyfacts → ruta B/8-K):** OKLO raise de enero (8-K), RKLB "17 contratos".
- **Dato de mercado (no XBRL por naturaleza):** market cap / EV (OKLO C8).
- **Cualitativo filed (→ ruta B, NO debe exigir XBRL):** OKLO OTA-DOE · RKLB backlog · ACHR Fase 3 FAA.
- **Pronóstico (→ falsador, no central):** ACHR C5 (timeline estimado).

## Veredicto
**La cobertura de companyfacts sobre los átomos numéricos financieros centrales está MUY por encima del
~60%.** Lo que companyfacts no cubre es, precisamente, lo que **debe** ir por **ruta B** (cualitativo) o es
dato de mercado — no son números que deberían estar en XBRL. **Conclusión: P1 NO necesita el parser del
instance XBRL en esta vuelta.** El lineage se construye sobre **companyfacts** (ya cableado en `edgar.py`) +
ruta B documental. El parser del instance queda diferido (solo haría falta para segmentos/dimensionales/
extension tags, que hoy no son el cuello).

## Hallazgo colateral (freshness, no cobertura)
companyfacts tenía los datos **al Q2-2026** pero el dossier del smoke usó **Q4-2025**. El problema de OKLO no
fue cobertura: fue que el **data pack no le pasó lo último** al Analista. Lo resuelve el cableado de la
`fuente_xbrl` (que tome el instant/period más nuevo), no un parser nuevo. Refuerza la regla `dato_vigente`
del doc 59 (D5): si hay una accession más nueva para la métrica → el dato viejo es REVIEW.

## Caveats de la medición
- n=3 (los del smoke). Ampliar a ~20 (incl. más pre-revenue y algún FPI 20-F) confirmaría; pero el patrón
  —financiero estándar en companyfacts, comercial/regulatorio fuera— es claro y consistente con la doc de la SEC.
- **IFRS/FPI** (20-F/40-F/6-K) siguen con cobertura ~0 en `_extract_concept` (solo us-gaap+dei): esos nombres
  quedan **explícitamente fuera** de la cobertura automática de P1 (o entran solo por ruta B) — no se finge.
- El contraste numérico real (signo/escala/período de `contrastar_xbrl`) se valida al cablear la `fuente_xbrl`
  con estos valores (próximo paso).
