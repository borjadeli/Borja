# 30 — Extracción de datos financieros: plan de endurecimiento

> Producto de triangular la INGENIERÍA de extracción de XBRL con 2 IAs expertas que **convergieron
> por completo** (2026-08-04). Gatillado por medir 45 nombres reales (fallas: SYM extension-tag,
> TEM shares=0, CYBR IFRS, INFN deslistada). Ver memoria [[extraccion-xbrl-triangulada]].

## 0. La revelación (ambas IAs)

Nuestro enfoque `companyfacts + listas de tags` tiene un **techo ESTRUCTURAL**, no de calibración:
- `companyfacts` SOLO trae tags de **taxonomías estándar** → NO los **extension tags** del emisor
  (el capex de SYM no está en esa API, ninguna lista lo captura).
- `companyfacts` SOLO trae hechos **SIN dimensiones** → los **multi-clase** (shares clase A/B) son
  dimensionales y están filtrados (por eso TEM=0).
- CYBR = FPI IFRS (20-F); INFN = deslistada (sale de company_tickers.json).

El salto de robustez NO está en listas de tags más largas, sino en cambiar la unidad de trabajo de
**"concepto en companyfacts"** a **"filing con su XBRL completo"** (parseado con **Arelle**, el motor
open-source base del renderer de EDGAR), usando el **calculation linkbase** (el árbol de sumas que el
emisor DECLARÓ) como verdad estructural de los rollups.

## 1. LO MÁS URGENTE — los 3 heurísticos peligrosos (fail-loud)

Ambas IAs: estas 3 reglas "producen números plausibles pero contablemente equivocados" — la falla más
peligrosa. Prioridad #1, **antes de extraer mejor: que fallen fuerte.**
- **Fallback de shares** (`Outstanding`→`Issued`→weighted-avg): son conceptos DISTINTOS, no
  alternativas. Nunca sustituir uno por otro en silencio. Multi-clase → sumar contextos por
  `StatementClassOfStockAxis` a la misma fecha. Si no se puede → flag, no un número.
- **Corte 50% de deuda**: reemplazar por selección de UNA representación reconciliada (total directo →
  current+noncurrent → suma de instrumentos; la primera que RECONCILIE). Nunca padre + descendientes.
- **MAX de caja**: compara scopes distintos. Separar `cash_and_equivalents` / `short_term_investments`
  / `restricted_cash`; `available_cash` por política, solo si reconcilia.

## 2. Plan en dos fases

### 🟢 Fase 1 — wins baratos (el 80/20; nada malo pasa callado, SIN Arelle)
1. **Los 3 fail-loud** de §1 (shares/deuda/caja → flag+revisión en vez de número mentiroso).
2. **Security master keyed by CIK** (no ticker): status activo/deslistado/adquirido; override
   versionado; rama IFRS para FPIs. INFN/CYBR dejan de ser "errores XBRL" → `security_inactive` / `FPI`.
3. **Yahoo mcap como banda de sanidad**: `shares × precio` vs market cap; discrepancia >20% → flag.
   (Cazaba TEM al instante.)
4. **Identidades de reconciliación** (usar la ecuación declarada por el emisor, no hardcodear A=L+E):
   Assets = Liab+Equity(+mezzanine+NCI); OCF+ICF+FCF+FX ≈ ΔCash; EPS×weighted ≈ NetIncome
   (caza shares en miles); current+noncurrent debt = total. Tolerancias por `decimals` XBRL, no % fijo.
5. **Prohibir el `None` silencioso** → estados explícitos: `reported / derived / explicit_zero /
   verified_not_present / missing / conflicting`. Pre-revenue → `revenue=0 + verified_not_present`
   SOLO tras verificar el income statement completo (si hay opex pero no revenue = pre-revenue real;
   si no hay nada = parser falló → `missing`).
6. **Tiers de confianza A/B/C/D** en cada número (A=directo reconciliado, B=componentes reconciliados,
   C=inferencia no reconciliada, D=ambiguo). Solo A/B entran a valuación automática; C/D → revisión.

### 🟡 Fase 2 — build grande (extrae BIEN los casos duros)
Parser **filing-céntrico con Arelle**: instancia + presentation/calculation/definition linkbases.
- **Extension tags** (SYM): tomar los hijos de `NetCashProvidedByUsedInInvestingActivities` en el
  calculation linkbase, clasificar por label+arco → el custom capex aparece **sin conocer el tag**.
- **Dimensional** (TEM multi-clase, instrumentos de deuda): parsear contextos con dimensiones.
- **Fact store SIN pérdida**: guardar dimensiones/contexto/calc-parents/statement-role/decimals, no
  solo tag+date+value.
- **Deuda por el árbol de cálculo**: sumar hermanos del mismo corte → sin doble conteo por construcción.
- **De-acumulación robusta**: `TTM = último FY + YTD corriente − YTD comparable` (menos restas); dos
  series `as_reported_vintage` + `latest_restated`; manejar 52/53 semanas, 10-KT/QT (stub, no forzar
  4 trimestres), restatements (versionar), deSPACs (cortar la serie en el cambio de entidad).

## 3. Segunda fuente = segunda PIPELINE, no segunda autoridad
Filing inline XBRL = verdad · vista renderizada EDGAR = control humano · companyfacts = control de
estándar · FSDS = control batch · earnings release = control extra. **Discrepancia → FLAG, nunca
auto-corrige.** Preferentes ≠ deuda (claim senior separado, visible aparte).

## 4. Tabla de fallas → detector → política (§ IA 2)
| Falla | Detector | Política |
|---|---|---|
| Custom capex omitido | subtree de investing con línea no mapeada | bloquear FCF |
| Shares cero | emisor listado + DEI cero/ausente | error crítico |
| Multi-clase omitida | axis con múltiples miembros | parsear filing completo |
| Rollup + componentes duplicados | parent/descendant en calc graph | elegir UN corte |
| Principal vs carrying | label/measurement distinto | no sumar |
| Caja de scope distinto | no reconcilia componentes | separar métricas |
| Pre-revenue vs missing | income statement completo | estado explícito |
| FY transition | 10-KT/QT o ruptura de fechas | stub, no de-acumular |
| Restatement | mismo período, filing posterior | versionar |
| Ticker deslistado | lookup falla, CIK conocido | issuer inactive |

## 5. Recomendación de secuencia
Fase 1 **ya** (barata, hace el sistema fail-loud y auditable — nada malo pasa callado). Fase 2 (Arelle)
como **inversión deliberada** cuando la extracción a escala de universo lo justifique. Riesgo a evitar:
rabbit-hole de reconstruir un parser XBRL completo antes de tener la vista rankeada / dashboard que es
el objetivo. Los baratos + tiers de confianza dejan el dato en un estado honesto para avanzar al goal.
