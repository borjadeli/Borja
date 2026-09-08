# 36 — Método de valuación unificado: reverse underwriting sobre T* (growth · madura · continuo con pre-revenue)

> **CERRADO** (2026-08-19). Síntesis de la triangulación de doc 35 (IA1 "invertir por tiempo/T*" + IA2
> "superficie de margen"). Convergieron; esto combina ambas. **Reemplaza** el falsador binario crudo de
> `bridge.py`/`hoja_evidencia.py` (el "ya-priceada" que mandaba todo growth a OPTION_PRICED 2%). Complementa
> doc 31 (reverse underwriting pre-revenue) — es el MISMO frame para el bucket que genera caja. Génesis y
> diagnóstico: [[drift-valuacion-growth-reverse-underwriting]]. Umbrales = **priors versionados** (doc 28 §0).

## 0. El principio (cerrado)

**Falsación, no proyección.** No proyecto un valor "justo"; computo **qué exige el precio** y lo juzgo contra
lo **demostrado** (histórico citado) + **base rates**. Tres invariantes que las dos IAs cazaron:

1. **g=0 es un PISO, no una valuación.** El bug original fue usar `owner-FCF/r` (g=0) como *denominador* de un
   ratio de carestía ("55× el piso"). Es el caso LÍMITE del modelo general, no la vara.
2. **Backlog/RPO = revenue, NO equity.** Nunca se suma dólar-a-dólar al valor. Entra como `PV(RPO × margen
   incremental normalizado, descontado a r)`, o como piso de revenue para años con calendario contractual.
3. **SBC se resta UNA vez** dentro de owner-FCF (corrige el numerador que CFO infló). NO es castigo de dilución
   — ese eje (share count prospectivo) sigue **separado**. Sin doble conteo. Ídem ejecución (Pilar 3).

## 1. La ecuación y las incógnitas (cerrado)

Misma ecuación de descuento que ya existe (`templates.escenario_operable`), con la incógnita movida.

```
P_ops = MarketCap − ExcessCash          # ExcessCash = caja EXCEDENTE, no la del runway
                                        # RUTA EV si apalancada (ver §6 gate de estructura de capital)
OwnerFCFE_0 / m_0  =  Σ_3FY(CFO − Capex − SBC) / Σ_3FY(Revenue)     # margen owner-FCF acumulado 3FY (robusto, no TTM)

# Trayectoria: crecimiento FIJADO en lo demostrado-fadeado (§3); margen converge m_0 → m_j; terminal g=0.
V(T ; m_j) = Σ_{t=1..T} [ R_t · m_t ] / (1+r)^t  +  [ R_T · m_j / r ] / (1+r)^T
   con  R_t = R_0·(1+g^D_t)     (g^D_t = crecimiento demostrado fadeado, §4)
        m_t = m_0 + (m_j − m_0)·min(t,H_m)/H_m     (H_m = 7, converge a m_j y se mantiene)
        terminal = perpetuidad g=0 a r  (M_T = 1/r — TU convención conservadora, NO un parámetro libre)
```

**Incógnita = T\* (IA1): fijar el crecimiento en lo demostrado, despejar el TIEMPO** que el precio exige.
`T*` = el T que resuelve `V(T; m_j) = P_ops`. V es monótona creciente en T (con margen ≥ 0) → **bisección,
raíz única, auditable**. (Si el margen de los primeros años es negativo, V no es monótona → grillar T,
detectar cambios de signo, tomar la MENOR raíz económicamente válida — IA2.)

**A través de la SUPERFICIE DE MARGEN (IA2): resolver para `m_j ∈ {m_P25, m_P50, m_P75}`** (percentiles de
margen owner-FCF de comparables MADUROS por modelo de negocio, fijados ANTES de ver el ticker). Da
`T*_P25 ≥ T*_P50 ≥ T*_P75` (a menor margen, más años exige el precio). El margen terminal es el **segundo
grado de libertad por donde entra el hype** → no se elige, se barre, y el **estado = el PEOR**.

**Salidas obligatorias (falsables, legibles):**
- `T*_j` por margen.
- `Rev_req = R_0·(1+g^D)^T*` y `RevenueMultiple_req = R_T/R_0` — "el precio exige facturar US$X / ser N× más
  grande". Más adversarial que un CAGR aislado (ambas IAs).
- `TV_share` = PV(terminal) / P_ops.
- `p_BR` = base-rate de sostener `g^D` durante `T*` años (§5).

## 2. Colapso al núcleo actual (verificación, cerrado)

Con `g^D=0`, `m_t=m_0`, terminal `1/r`: `V = OwnerFCF/r`. **No abandonamos lo conservador — lo volvemos el
caso límite del modelo general.** Una madura da `T*≈0` (el precio ya lo paga la caja sin crecimiento).

## 3. Crecimiento DEMOSTRADO — núcleo mínimo (cerrado; todo XBRL salvo lo marcado)

```
g_rev = min( CAGR_3FY(Revenue) , YoY_TTM(Revenue) , P25(8×YoY_Q Revenue) )      # per-share
g_GP  = min( CAGR_3FY(GrossProfit) , YoY_TTM(GP) , P25(8×YoY_Q GP) )            # per-share
g_D   = min( g_rev , g_GP )     # revenue pass-through con GP estancado NO es growth
```
**Per-share** (Revenue/diluted_shares): crecer emitiendo no es crecer para el accionista. Métricas del núcleo,
todas XBRL con cita (accession+tag+período): revenue/GP CAGR 3FY, secuencia 8 YoY (P25), margen bruto nivel+Δ,
margen operativo, owner-FCF margin 3FY, SBC/CFO, intensidad de M&A (`PaymentsToAcquireBusinesses`+Δgoodwill),
RPO+deferred revenue, diluted shares. **Texto citado (gates de calidad):** revenue no recurrente/concentración,
calendario de backlog.

**Reglas de cobertura de datos (data_state):** <3 FY limpios → nunca COVERED. <8 trimestres → máx STRETCH.
M&A material sin bridge orgánico reconstruible → máx OPTION_PRICED. GP negativo/no identificable → fuera del
método comercial (va a la vía pre-revenue o al carril).

**DIFERIR (no usar como gate):** Rule of 40 (suma dos cosas ya modeladas), NRR/retención, ARR/bookings, magic
number, cohortes, TAM de decks. Motivo (ambas IAs): su **definición flota entre emisores** → no comparables
cross-name aunque el LLM las cite bien. Un hecho con definición flotante no es utilizable.

## 4. Fade y estrés de lo demostrado (cerrado; half-lives = prior)

`g_D` NO entra crudo (la persistencia del crecimiento es ~indistinguible del azar — Chan-Karceski-Lakonishok,
citado por las dos). Fade determinista, **unidireccional (solo recorta)**:
```
g^D_t = g_∞ + (g_D − g_∞)·λ^(t−1)          g_∞ = 0.03 nominal
  base:   λ_B = 2^(−1/3)   (half-life 3 años)
  estrés: g_D − max(5pp, 0.25·(g_D−g_∞)),  λ_S = 2^(−1/2)  (half-life 2 años)
```
Castigos previos a `g_D` (deterministas, unidireccionales): `min` con YoY reciente (deceleración) · pendiente
de los 8 YoY · ΔGM_3y < −300bps → ×0.75 (crecimiento comprado) · M&A_cash ≥ 20%·ΔRev → ×0.50 (inorgánico) ·
Revenue_TTM < US$50M → cap 0.30 (artefacto de base chica) · **cap duro `CAP_arq` ≈ 0.35–0.40** (nadie recibe
crédito por >~40% demostrado — la base rate de sostenerlo >3-4 años es ~0). Dilución y ejecución NO se tocan acá.

## 5. Base rates — el falsador de CAGR (estructura cerrada; tabla = P1)

`p_BR(g, T | banda de revenue inicial, banda de GM)` = fracción histórica de firm-years de EDGAR/XBRL que
sostuvo ≥ ese CAGR durante T años. **Quiebra = fracaso; adquisición = censurada; M&A material = separado.**
- **v1 (ahora):** anclas provisionales + cutoffs de `T*` en años (abajo). Sin cutoff universal de CAGR: "30%"
  significa cosas distintas partiendo de $10M vs $1B → por eso el gate es sobre `p_BR`, no sobre el CAGR.
- **P1 (destino):** construir la tabla propia del **bulk XBRL de la SEC** (Financial Statement Data Sets, ~20
  años, gratis). Es lo que la filosofía exige: el falsador tiene que ser NUESTRO. ~un fin de semana.

Geometría del burden (para intuición): 30% → 3.7×/6.3×/13.8× (5/7/10y); 40% → 5.4×/10.5×/28.9×; 50% →
7.6×/17.1×/57.7×. Anclas de persistencia (bootstrap, revenue inicial >$50M): 20%→~15-20%/~3-5% (5y/10y);
30%→~7-10%/~1-2%; 40%→~3-5%/<1%; 50%→~2%/~0.2%.

## 6. Mapa a los 4 estados (cerrado en estructura; umbrales = prior v1)

**`estado = worse(growth_state, margin_state, data_state)`** — el peor manda (no-compensatorio, coherente con
el `min()` de caps del sizing). Reusa `estado_valuacion_por_burden`, cambiando el input (T*/p_BR por burden).

| Estado | Regla v1 (prior) |
|---|---|
| **COVERED** | bajo margen **P25**: `T* ≤ 3y` (≡ `p_BR ≥ 10%`) · `TV_share ≤ 80%` · 3FY limpios · **owner-FCF trailing > 0** (sin excepción) |
| **STRETCH** | bajo margen **P50**: `3 < T* ≤ 7` (`p_BR ≥ 5%`); o cubierto en base pero no en estrés |
| **OPTION_PRICED** | raíz falsable pero `7 < T* ≤ 12` (`1% ≤ p_BR < 5%`) · o <3FY · o solo funciona con margen **P75** |
| **NON_UNDERWRITABLE** | sin raíz antes de `s_max` (P99 histórico) · `T* > 12` (`p_BR < 1%`) · margen requerido > P75 maduro · crecimiento orgánico no reconstruible · `TV_share > 80%` sin evidencia intermedia |

`v2` (destino): umbrales en `p_BR` (auto-ajustan al nivel de `g`), no en años absolutos.

## 7. Guardas y modos de falla (cerrado)

| Falla | Cómo vuelve el hype | Guarda determinista |
|---|---|---|
| **Margin laundering** | elegir margen terminal 25% justifica cualquier precio | P25/P50/P75 maduros fijados ANTES de ver el ticker; COVERED solo bajo P25; requerido >P75 → NON_UNDERWRITABLE |
| **Crecimiento falso** | M&A/pass-through/cliente único infla el CAGR | `g_D = min(rev, GP)` per-share; flag M&A; sin bridge orgánico → máx OPTION_PRICED |
| **FCF artificial** | working capital/capex diferido/SBC inventan caja | owner-FCF acumulado 3FY; SBC restado UNA vez; si SBC/CFO > 40% → forzar estado ≤ STRETCH |
| **Deriva de parámetros** | bajar `r` o subir `CAP_arq` re-ratea el universo sin que nadie lo note | tabla versionada + changelog fechado + **re-run completo con diff report**; CERO overrides por nombre |

**Guardas de combinación:** `TV_share > 80%` → no puede ser COVERED · prohibido combinar margen-P75 +
múltiplo-P75 + horizonte largo (triple upside mecánico). **Techo físico (P1, necesita TAM/líder):** `Rev_req`
vs TAM citado y revenue del líder del sector; > 30% del TAM o > el líder → castigo automático.

**Chequeo de distribución (obligatorio, cada re-run):** si **>70% del universo** cae en OPTION_PRICED/
NON_UNDERWRITABLE, **el problema son los parámetros, no el mercado** — volvimos a estar anti-crecimiento.
Dispara recalibración por percentil del universo. (Es el bug original, en forma de alarma automática.)

## 8. Continuidad pre-revenue ↔ growth ↔ madura (cerrado)

No hay continuo económico perfecto; hay **continuo de lenguaje de decisión**: pre-revenue = reverse
underwriting de hitos/capital/dilución (doc 31) · comercial = reverse DCF sobre revenue/margen (este doc) ·
madura = el mismo, colapsado a `owner-FCF/r`. El borde **owner-FCF ≈ 0 NO es un problema**: owner-FCF
determina `m_0`, no el denominador (nunca dividimos por owner-FCF en la vía comercial). Zona de solape
(`|owner-FCF| < 5% de revenue`): correr ambas vías, tomar el **peor estado**. **Gate de estructura de
capital (IA2):** ruta equity (MC/owner-FCFE/r) solo si deuda estable/refinanciable; si es materialmente
apalancada → ruta EV (owner-UFCF/WACC).

## 9. Triage de IMPLEMENTABILIDAD (qué reusa / extiende / es nuevo)

| Pieza | Estado | Dónde |
|---|---|---|
| `r`/arquetipo, terminal, horizonte, versionado+hash+changelog | ♻️ **reusa** | `politica.py` |
| Owner-FCF = CFO−capex−SBC, SBC_TTM, fcf_ttm | ♻️ **reusa** | `edgar.py` |
| Máquina de descuento / perpetuidad (la ecuación) | ♻️ **reusa** | `templates.escenario_operable` |
| 4 estados + patrón de banding | 🔧 **extiende** (input: T*/p_BR en vez de burden) | `estado_valuacion_por_burden` |
| Ejes dilución + ejecución separados | ♻️ **reusa** (esta sesión) | `dilucion.py`, `pilares.py` |
| 2-ejes, min-caps, ranking, cartera, carril, cutover harness | ♻️ **reusa** (downstream del estado) | varios |
| Reverse underwriting (hermano del T*) | 🔧 **extiende** (mismo frame) | `pre_revenue.py` |
| Series trimestrales revenue/GP + CAGR 3FY per-share | 🔧 **extiende** (patrón de series ya existe) | `edgar.py` |
| **Solver de T\*** (bisección + fade + trayectoria de margen) | 🆕 **nuevo** (~1 módulo) | `valuacion_reverse.py` (nuevo) |
| **Superficie de margen** P25/P50/P75 por modelo de negocio | 🆕 **nuevo** (del XBRL; provisional v1) | `politica.py` + tabla |
| **Tabla de base rates** de persistencia | 🆕 **nuevo** (bulk XBRL — **P1**; anclas v1) | nuevo |
| Techo físico (Rev_req vs TAM/líder) | ⏸️ **diferido** (necesita TAM, dato de texto) | — |
| **Reemplaza** el falsador binario "ya-priceada" | ♻️→🔧 | `bridge.py`/`hoja_evidencia.py` |

**Resumen:** ~50% reusa, ~30% extiende, ~20% nuevo. No es de cero — se reemplazan ~200 líneas del falsador
binario por el reverse-DCF, reusando motor, datos, estados, sizing y gobernanza.

## 10. Orden de construcción (propuesto)

1. ✅ **HECHO (2026-08-19).** `edgar.serie_crecimiento` (series trimestrales alineadas rev/GP/diluted) +
   `nucleo/crecimiento.py` (`crecimiento_demostrado` = min(g_rev, g_GP) per-share con castigos §3/§4 +
   `fade`). Política v1.8. 9 tests. Validado en vivo: RBRK g_D=40% (capado), TENB 9.3% (decel), LEU 0% (lumpy).
2. ✅ **HECHO.** `politica`: superficie de margen {P25/P50/P75} por modelo + anclas de base rate + umbrales v1
   (T* 3/7/12, TV_share 0.80) + G_TERMINAL/H_MARGEN. Política v1.8.
3. ✅ **HECHO.** `valuacion_reverse.py`: solver `t_star` (bisección/interp, colapsa a owner-FCF/r) +
   `estado_valuacion_reverse` (superficie de margen plegada en la escalera, worse-of con data_state) +
   Rev_req. 20 tests. **1ª corrida en vivo: el chequeo de distribución §7 DISPARÓ** (100% NON_UNDERWRITABLE a
   r=15%) → 2 calibraciones: (i) **ruteo de vías** (owner-FCF ≤ 0 → vía burden, no comercial; RBRK/S/LEU); (ii)
   **la tasa `r`** — a 15% (hurdle inflado) todo es ununderwritable; TENB: r=8%→STRETCH, 10%→OPTION, 15%→NON.
   **En TRIANGULACIÓN (doc 37):** ¿el reverse-DCF descuenta a costo de equity de MERCADO (~9-11%, lee el pricing)
   o al hurdle (15%)? El método se auto-diagnosticó — el §7 hizo su trabajo a la 1ª.
4. `estado_valuacion`: `worse(growth, margin, data)` desde T*/p_BR. (extiende)
5. Reemplazar el falsador binario; re-correr `cutover_diff` → ver la cartera nueva con growth bien dimensionada.
6. Guardas §7 + chequeo de distribución. Tests en cada paso. Todo en SHADOW.
