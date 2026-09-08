# 31 — Análisis de nombres pre-revenue / pre-profit (el corazón de la tesis)

> Producto de triangular con 2 IAs la pregunta "¿nuestro método es el mejor para nuestro universo,
> que es MAYORMENTE pre-revenue?" — **convergieron por completo** (2026-08-05). Resuelve el hueco:
> el operable FCFE (docs 28/30) floorea a toda la mayoría pre-revenue al mismo piso de balance, sin
> distinguirlas. Este doc define cómo darles tracción disciplinada. NO reemplaza el operable — lo
> EXTIENDE. Regla rectora: advisory, evidencia primaria, sin narrativa/TAM, "unknown ≠ zero".

## 0. El principio (ambas IAs)

Para un pre-revenue no se inventa un DCF. Se **rankea "prueba financiada por unidad de carga que
exige el precio"** — no cantidad de hitos ni tamaño de TAM. La pregunta cambia de *"¿cuánto vale el
flujo?"* a *"¿cuánto de lo que el precio exige ya está asegurado y financiado, y cuánta dilución
cuesta llegar al resto?"*. Dos motores nuevos, conectados al sistema actual: **Reverse Underwriting**
y **Funded Critical Path**.

## 1. Escalera de realización R0–R5 (por evidencia económica, no por signo de FCF)

Reemplaza el binario "genera-caja / floorea". TTM para evitar ruido. "Revenue" = **ingreso comercial
del producto central** (grants / NRE gubernamental / milestone payments se muestran pero NO suben la
etapa → requiere leer segmentos/notas, XBRL solo no alcanza).

| Etapa | Evidencia |
|---|---|
| **R0** | sin ingresos comerciales del producto central (OKLO, NNE, POET, LTBR) |
| **R1** | ingresos centrales, gross profit ≤ 0 |
| **R2** | gross profit > 0, operating income < 0 |
| **R3** | operating income > 0, CFO < 0 |
| **R4** | CFO > 0, FCF < 0 por capex (RKLB, MP, LEU caen donde indiquen sus economics reales) |
| **R5** | FCF > 0 → **método operable actual (doc 28)** |

## 2. Reverse Underwriting — cuánta economía exige el precio

- **Option premium** (base plenamente diluida): `OP = max(0, MarketCap_FD − V_operable)`.
- **FCFE requerido** que el precio obliga a explicar (comercialización a `t` años):
  `FCFE_req = OP × r × (1+r)^t / ρ` — `r` = retorno por arquetipo (ya lo usamos); `ρ` = retención
  mínima del accionista tras cubrir el gap de financiación (§5). No es un DCF de management: es la
  vara que el precio impone.
  > **Impl. nota (2026-08-10, triangulación IA1+IA2):** los dos `r` de la fórmula son objetos distintos.
  > El de adelante es el **cap yield terminal** (múltiplo de salida del estado YA de-riesgado a t años);
  > el de `(1+r)^t` es el **descuento del camino riesgoso** (r de la etapa de hoy). Usar el mismo castiga
  > dos veces el ser pre-revenue hoy. Implementado como `FCFE_req = OP × r_exit × (1+r_hurdle)^t` con
  > `r_exit = min(r_hurdle, R_TERMINAL=0.15)` (`politica.py` v1.1). ρ sigue en 1 (Fase 1, ver §5).
- **R1–R4 (con revenue):** `Burden_GP = (Opex_cash_TTM + FCFE_req) / GrossProfit_TTM` = cuántas veces
  debería multiplicarse el gross profit, a estructura constante. Límite optimista (sin crecimiento de
  opex ni impuestos): si aún así da 6-10×, el precio exige muchísimo. **Le da tracción objetiva a RKLB.**
- **R0 físico (con contratos):** invertir q×u×P como TEST, no como valuación:
  `q_entregable = min(q_permitido, q_financiado, q_feedstock)`; `q_asegurado = min(q_entregable,
  q_demanda_vinculante)`; `Revenue_asegurado = q_asegurado × P_contrato`; **margen FCFE requerido =
  FCFE_req / Revenue_asegurado**. Si >100% → **físicamente imposible** con la capacidad asegurada.
- **R0 sin economics:** `price anchor unavailable` (NA). **El NA es información** — el filing todavía
  no permite decir si está barata o cara. NO se completa con un score narrativo.

## 3. Funded Critical Path (el option ledger O0-O5 → grafo de dependencias)

Por arquetipo, 4-5 **carriles** obligatorios con niveles pre-definidos por subsector: **tecnología ·
regulación · sitio/feedstock · construcción/capacidad · demanda comercial.** Ejemplos de nivel:
"management planea presentar" NO avanza; solicitud aceptada = avance; permiso concedido = superior.
**Madurez = MÍNIMO entre carriles (cuello de botella), NO promedio.** Una planta con demanda
espectacular pero sin permiso/feedstock NO está "80% madura". Desempate: cuántos carriles por encima
del cuello — nunca compensar una dependencia crítica faltante.

**Hito decisivo** (no "densidad de hitos" — es fácil fabricar 20 PRs): debe cambiar el nivel de un
carril crítico, ser binario/observable, depender de un tercero (regulador/cliente/ensayo/lanzamiento),
tener ventana temporal y alterar la tesis. **Proximidad = desempate SOLO después de verificar
financiación** (un hito cercano sin plata para llegar es riesgo, no mérito).

## 4. Financiación hasta el hito (dos gaps)

`Gap_next` (hasta el próximo hito decisivo) y `Gap_self_funding` (hasta autosostenible). **Fuentes
admitidas:** caja irrestricta, inversiones líquidas, deuda comprometida y utilizable, grants
adjudicados (con condiciones), prepagos irrevocables de cliente. **NO cuentan:** ATM no utilizada,
shelf, subsidios solicitados, tax credits condicionados, MoUs, intención de project finance.
`FundingCoverage = comprometido / costo restante al hito`; costo no divulgado → **unknown, no 100%**.

## 5. Dilución como variable CENTRAL (no penalización cualitativa)

Modifica directamente el cash flow requerido. Piso optimista (colocación completa a spot, sin costos):
`dilución_min = G / (MarketCap_FD + G)`; `ρ = MarketCap_FD / (MarketCap_FD + G)`. Ese `ρ` entra al
reverse underwriting → **la empresa puede ganar y el accionista actual perder.** Toda métrica por
acción sobre **shares × (1+d)**. La ficha muestra: crecimiento real de shares 12/24m, ATM
remanente/mcap (overhang, no caja), warrants/RSU, convertibles (peor escenario para el común entre
repago y conversión), SBC/revenue. **Es donde más alfa hay porque casi nadie lo hace disciplinado.**
Distingue ASTS (burn $1.3B/año) de OKLO (caja gigante, burn bajo) — que hoy "floreaban igual".

## 6. Cross-sector: comparar sin narrativa

**Comparables honestamente en 5 ejes adimensionales:** etapa R0-R5 · madurez del cuello · financiación
al próximo hito · retención mínima del accionista · carga económica exigida por el precio. **NO
comparable sin supuestos:** el upside económico final (un E2 nuclear ≠ un E2 biotech en distribución
de payoff). Por eso: **ranking económico DENTRO de arquetipo · tier de riesgo de capital COMÚN ·
presupuesto + caps + diversificación de catalizadores ACROSS** (no 5 apuestas al mismo regulador NRC).
**Nada de un score ponderado 1-45** (los pesos son narrativa por la puerta de atrás).

Orden total (si el selector lo necesita): excluir/watchlist los no-financiados-hasta-el-hito → separar
`price_anchored` de `unanchored` → dentro de arquetipo por **menor reverse burden** → desempate por
madurez del cuello → luego menor dilución → luego cercanía del hito → mejores de cada arquetipo bajo
caps comunes. Un true pre-revenue sin economics gana el ranking de EVIDENCIA de su subsector pero
queda en el bucket `pure_option` — no compite como si tuviera la legibilidad económica de RKLB.

## 7. Integración (no toca el operable actual — agrega salidas)

`realization_stage · core_revenue_ttm · gross_profit_ttm · critical_path_bottleneck ·
next_decisive_milestone · funding_coverage_next · funding_gap_to_self_funding · minimum_dilution ·
shareholder_retention_floor · option_premium · reverse_burden_type · reverse_burden_value ·
price_anchor_status · peer_rank · capital_risk_tier`.

Flujo: **R5** → operable actual. **R1–R4** → operable conservador + economics realizados + Burden_GP.
**R0** → funded critical path + dilución + reverse physical burden (si hay contratos/economics). **Sin
economics verificables** → `price_unanchored` + cap especulativo duro.

## 8. Blindajes contra el autoengaño

Unknown ≠ zero (precio/costo no divulgado impide calcular, no autoriza estimar) · capacidad = mínimo
de restricciones, nunca la anunciada · backlog ≠ contrato irrevocable (IDIQ ceiling / pipeline /
design-win / MoU no cuentan) · **un mismo hecho no valida tres carriles** (un award no es
simultáneamente demanda + financiación + validación salvo que cada atributo esté documentado) ·
as-of estricta + templates congelados antes de ver resultados · hito perdido BAJA el nivel (no se
corre la fecha) · **ledger explícito de evidencia NEGATIVA** (retrasos, resubmissions, overruns,
cancelaciones, going-concern) · madurez ≠ precio (una empresa muy avanzada puede ser pésima acción) ·
si no se puede construir el reverse burden sin supuestos inventados → **"no valuable"**, no un score.
Tasa base histórica por arquetipo (¿qué fracción de SMRs anunciados llegó a operar?) congelada y
versionada — sin ella la escalera es narrativa ordenada.

## 9. Estado y pipeline

Diseño **cerrado y triangulado**. Implementable con: XBRL (RPO `RevenueRemainingPerformanceObligation`
—la demanda contratada más dura y comparable entre sectores—, shares diluidas, caja, capex, burn) +
**parsing dirigido de notas** (ATM/convertibles/purchase obligations, desagregación 606 core-vs-grants)
+ **scrapers por regulador** (ADAMS/FAA/FCC/DOE) que dan los hitos verificables gratis. Las dos últimas
piezas se solapan con la Fase 2 de [[extraccion-xbrl-triangulada]] (parsing filing-céntrico). Output
por nombre = "hoja de evidencia" de una página, defendible ante el cliente y ante nosotros en 2 años.
