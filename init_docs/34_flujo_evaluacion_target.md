# 34 — Flujo de evaluación TARGET (la superficie única a construir)

> **Qué es.** El método (doc 33) dice el *qué/por qué*; este doc dice el *cómo* como UNA sola superficie
> coherente de evaluación→ranking→sizing→selección. Nace del pre-pass de coherencia (2026-08-13): el código
> encarna **tres superficies medio-migradas** que no matchean el método. Este es el target al que se refactoriza.
> **Fuente:** reconcilia doc 33 (método) + doc 27 (arquitectura/lexicográfico) + doc 28 (valuación/gate) +
> doc 29 (carril) + doc 31 (pre-revenue). No re-abre método; ORDENA la implementación. Estado: spec, a construir.

---

## 0. Las tres superficies actuales → qué pasa con cada una
- **S1 · `flujo`/`selector`/`sizing`: `merito = Quality × Asimetría` (score cardinal).** LIVE en el paper.
  → **JUBILAR el `merito`** (doc 33: "sin score cardinal"). `quality.py` SE CONSERVA como el motor del **pilar
  Economía** (tier de calidad → banda), no como factor de un score. `selector`: reemplazar la normalización por
  mérito por el **ranking lexicográfico + tier→cap** (abajo).
- **S2 · `pilares`/`evaluacion`: 4 pilares → tier conjuntivo (doc 26).** Desenchufado.
  → **CONSERVAR como la ficha de ELEGIBILIDAD, reducida a 3 pilares** (Demanda·Economía·Ejecución). Se **saca
  valuación como Pilar 4** → va al GATE (paso 4). `evaluacion.asignar_tier` pasa de "tier de 4 pilares" a
  "elegibilidad conjuntiva de 3 pilares".
- **S3 · `hoja`/`templates`/`pre_revenue`: cohort-free (doc 28).** Semi-vivo en `/hoja`.
  → **CONSERVAR como el motor de los NÚMEROS** (base/bull/bear/burden/falsador) que alimentan el GATE de
  valuación (paso 4) y se muestran en la FichaPM. `pilar_valuacion` (comparables/`multiplo_terminal`) se **RETIRA**
  (comparables diferidos, doc 28 §2).

---

## 1. El flujo target, end-to-end

```
0. Mapa sectorial → universo            (macro DEFINE el universo; nunca puntúa mérito)
1. Filtro 0 barato                      (elimina lo no-analizable; no rankea)
2. Motor de evidencia → fact store      (hechos CITADOS + verificados; COBERTURA como número)
3. ELEGIBILIDAD = 3 pilares CONJUNTIVOS (Demanda · Economía · Ejecución → banda c/u)
      └─ composición conjuntiva: una debilidad CRÍTICA en cualquier pilar descalifica (no compensa).
         NO incluye valuación. Output: elegible / no-elegible (+ por qué, citado).
4. VALUACIÓN = GATE separado (falsador)  (cohort-free: base/bull/bear + CAGR implícito, doc 28 §4)
      └─ si el precio YA paga el bull operable → PURA OPCIONALIDAD → fuera del libro duro
         (→ carril especulativo si pasa su gate, doc 29). Es kill/keep, NO una banda mezclada al tier.
5. TIER de riesgo de capital A/B/C       (¿financiada hasta su hito? runway + dilución; doc 31/33)
      └─ A/B/C → cap 8% / 5% / 2.5% (doc 28 §8). ESTE es el tier que mapea a cap (no el de los pilares).
6. RANKING lexicográfico (dentro de arquetipo, doc 27 §10)
      gate → tier → cobertura → asimetría operable (cap 5×) → catalizador → liquidez.
      Ordinal SOLO donde hay ancla; el resto descriptivo SIN puestos. SIN score cardinal (no `merito`).
7. SIZING = min(caps)                    (arquetipo×fragilidad · tier-capital · liquidez/ADV · sector)
      └─ piso por posición; el macro solo APRIETA, nunca afloja.
8. FichaPM                               (tier + números[bull/bear/burden/opcionalidad] + fragilidad_porque
      + hechos citados) → el PM propone dentro de [piso, cap], ADVISORY. El sizing sale del NÚCLEO, no del LLM.
9. Cartera                               (~6 duras + hasta 2 opcionales; carril con presupuesto propio 10→25%;
      caps por sector; margen p/ desplazar)
10. Rotación                             (5 vías + milestone-miss + evidence-decay)
```

**Distinción clave que resuelve la confusión de "tiers":** hay **DOS** cosas A/B/C-like, y son distintas:
- **Elegibilidad (paso 3):** los 3 pilares conjuntivos → elegible/no (Pass/Fail/Unknown). NO mapea a cap.
- **Tier de riesgo de capital (paso 5):** ¿financiada hasta el hito? (runway+dilución) → **A/B/C → cap**.
`doc 26`/`evaluacion.py` los fusionaba (un tier A/B/C de 4 pilares). El target los SEPARA.

---

## 2. Cómo los NÚMEROS (S3) alimentan el flujo
- **Al GATE de valuación (paso 4):** `bridge.falsador_cagr` (¿precio ya paga el bull operable?) + `templates`
  (base/bull/bear) + `pre_revenue` (burden para pre-revenue). Kill/keep + a la ficha.
- **Al pilar Economía (paso 3):** `quality.py` (márgenes, crecimiento, recurrencia, wins) → banda. (Los números
  de valuación NO entran a los pilares — valuación es gate.)
- **A la FichaPM (paso 8):** `precio_base_sin_contratos` ← `base_price`; `pct_opcionalidad_priceada` ←
  `option_premium_pct`; el veredicto del falsador; el burden. (Los campos de `FichaPM` ya mapean a esto.)

---

## 3. Forks abiertos (lo único que falta DECIDIR; el resto es build)
- **A1 · Tier de demanda: determinista-duro vs orientativo.** doc 33 (10-ago): "derivación determinista correcta
  de entrada, no depende del humano". Decisión 11-ago (posterior): tier **ORIENTATIVO** + cita, el PM juzga los
  bordes (porque el auto-tier es frágil, limitado por el retrieval). **Recomendación (reconcilia, no contradice):**
  el principio de doc 33 §"la evidencia viaja con la señal" YA dice ambos — la derivación *aspira* a ser correcta de
  entrada, y el hover/cita es "transparencia + red de seguridad, no el guardrail principal". → Adoptar **orientativo
  + cita** como el estado honesto DADO el límite actual del retrieval, con "determinista-correcto-de-entrada" como
  NORTE al que se sube mejorando el motor de evidencia (que estamos midiendo). Re-endurecer a auto-veto SOLO cuando
  el retrieval lo banque (medible). *(Si el operador quiere, es la única pregunta que valdría un chequeo externo puntual.)*
- **A2 · Forma (3 pilares + valuación=gate):** ya decidida por doc 33/27 → este doc la fija. Confirmar, no triangular.
- **A3 · Matar `merito`, ranking lexicográfico:** ya decidido por doc 27 §203/33 → este doc fija el orden (paso 6).

---

## 3bis. Resolución TRIANGULADA del cutover (A1 + ranking) — CERRADO (IA1+IA2 convergieron, 2026-08-14)

**A1 · Tier de demanda = 100% DETERMINISTA siempre.** Lo que se ablanda es el ESTADO de la evidencia (también
determinista), no la regla. Hechos **tri-estado** (presente/ausente/no-encontrado + cita + **score de calidad de
cita**). Arriba del umbral de confianza → el tier decide firme (pasa/vetea). Abajo → **ABSTENCIÓN determinista**
(`EVIDENCIA_INSUFICIENTE` → fuera del ciclo → cola de investigación con el hecho faltante nombrado). **El PM toca
solo INPUTS** (agrega/corrige cita → re-entra por la función pura, logueado), NUNCA el output (tier/elegibilidad).
Override si existe = **asimétrico: vetar/bajar, nunca promover** (el sesgo del universo apunta arriba). Umbral
calibrado desde la medición de retrieval (precisión por tipo de hecho vs muestra auditada). Razón dura (IA2):
en filtro conjuntivo + universo escaso, "el PM juzga los bordes" ≈ "el PM elige la cartera".

**Ranking = (iii) "Doc B endurecido":** prefijo GLOBAL (gate→tier→cobertura, misma escala p/ todos) → **corte por
ARQUETIPO** (clasificador determinista versionado — el objeto más gameable: "elegir bucket es elegir ranking") →
**llave económica LOCAL** (FCFE→asimetría; pre-revenue→**burden como TUPLA lexicográfica**: runway → funded-to-
milestone → dilución al hito → cobertura de backlog — NO score compuesto) → sufijo GLOBAL (liquidez, catalizador).
Cartera = **celdas (arquetipo × tier) con CUOTAS ex-ante** (caps, no cuotas obligatorias: si no hay buena, cash),
se llenan con el tope de cada ranking local; trade-off cross-arquetipo decidido UNA vez a nivel política. Techo
**3-4 arquetipos**. La lista única = **cola operativa** (intercalada por celdas), no ranking económico.

**Reglas transversales:** (1) misma patología en las 2 capas = coerción de "indefinido" a valor → tercer estado
explícito+contado (asimetría pre-revenue = **N/A, no −1.00**; UNKNOWN demanda = abstención, **no CRÍTICO**).
(2) **A1-duro es PRECONDICIÓN del ranking** (el tier es la llave global; si es orientativo, nada compara cross-
arquetipo). (3) **cada hecho puntúa en UN solo lugar; su 2º uso es gate, nunca contribución al orden** (el backlog
nuclear no paga dos veces: tier Y burden). (4) **replay** (decisión = f(hechos@t, versión de código, incl.
correcciones humanas de input)) + tablero (tasa de abstención / veto humano / distribución por celda).

## 3ter. Sizing por valuación — CERRADO (IA1+IA2 convergieron, 2026-08-18)

**Dos ejes ORTOGONALES (la clave):** la **EVIDENCIA** decide de qué LIBRO forma parte (inmutable); la
**VALUACIÓN/PRECIO** decide cuánto CAPITAL recibe (variable). Ninguna compensa a la otra. RKLB = `HARD_EVIDENCE /
OPTION_PRICED_CAPITAL` (libro duro por evidencia, piso por precio). NO se migra el libro por precio (contamina la
semántica: si cae 70%, la evidencia no se volvió más real).

**Quién dimensiona:** el NÚCLEO. El PM solo REDUCE/EXCLUYE (nunca aumenta) + corrige hechos/citas y re-ejecuta.
Nunca el número. El capital liberado no se redistribuye por encima de caps → puede quedar CASH.

**Cómo:** `size = min(cap_evidencia/tier, cap_valuación, cap_supervivencia, cap_liquidez, cap_sector)` — **min de
caps INDEPENDIENTES, no-compensatorio** (no es un score) · **salida en RETÍCULA DISCRETA** (ej. 2/4/8%, no 3.37%) ·
**reason code por posición** (qué cap ligó). El `cap_valuación` = 4 estados ordinales por **cobertura de GP_req**
(GP terminal que exige el precio) por evidencia contratada+citada:
- **COVERED** (economía actual + forward duro cubren GP_req, sin cambio de régimen) → cap completo.
- **STRETCH** (gap cerrable escalando lo YA demostrado) → escalón reducido.
- **OPTION_PRICED** (exige planta/producto nuevo, expansión de margen, financiación no asegurada, permiso, o varias
  transiciones no demostradas) → **piso**.
- **NON_UNDERWRITABLE** (sin puente falsable / inputs no calculables / falla supervivencia) → **0**.
Condiciones NECESARIAS, sin compensación (demanda dura no compensa falta de capacidad; capacidad no compensa margen
inexistente; etc.). Rango de burden que cruza estados → se usa el MÁS RESTRICTIVO; el ancho del rango = cap de
indeterminación aparte. Bandas anchas con HISTÉRESIS (no rotan por ruido de precio). Reason codes:
REQUIRED_GP_NOT_CONTRACT_COVERED · UNFUNDED_CAPACITY_REQUIRED · MARGIN_REGIME_CHANGE_REQUIRED ·
BURDEN_RANGE_CROSSES_BUCKET · SURVIVAL_GATE_FAILED.

**ARREGLO PREVIO (IA1, hacer PRIMERO):** el burden sobre GP y shares ACTUALES está sesgado a la baja en quemadores
(financiar el burn diluye antes de que llegue el GP) → computar el burden sobre **acciones plenamente diluidas +
las necesarias para financiar el burn hasta breakeven** (con la quema citada). Es el ρ que doc 31 difirió. Sin
esto, sobre-dimensiona sistemáticamente al ~70% pre-revenue del universo.

**Test de aceptación:** RKLB = MEJOR evidencia + MENOR tamaño (piso). Si el sistema no lo emite, el sizing no
transporta información — transporta la clasificación otra vez.

## 4. Secuencia de refactor (build hacia este target) → doc 14 Pila B
1. ✅ **Elegibilidad a 3 pilares HECHO (2026-08-14).** `evaluacion.PILARES` → 3 (Demanda·Economía·Ejecución);
   `evaluacion.asignar_tier` compone 3; `ranking.evaluar_ticker` ya NO arma ni pasa `pilar_valuacion`;
   `pilares.pilar_valuacion` marcado RETIRADO (comparables diferidos). 280 tests verdes, sin regresión. [G5]
2. 🟡 **Ranking lexicográfico — módulo SHADOW hecho (2026-08-14).** `ranking_lexicografico.py` (puro, 10 tests):
   `CandidatoLex` + `clave_lexicografica` (gate→tier→cobertura→asimetría cap5×→catalizador→liquidez) +
   `rankear_lexicografico`/`elegibles_ordenados`. **`selector`/`flujo` (merito vivo) NO tocados.** Falta:
   construir `CandidatoLex` desde datos reales + comparar shadow-vs-merito + cutover cuando esté verde. [B2]
3. 🟡 **Enchufar números cohort-free — contrato HECHO (2026-08-14, shadow).** `HojaEvidencia` expone
   `bear_operable` + `asimetria_operable`; `ranking_lexicografico.candidato_desde(ev, hoja)` mapea las 2
   superficies → `CandidatoLex` (elegibilidad de los 3 pilares + gate del falsador + tier de capital +
   asimetría). Duck-typed, 4 tests. `pilar_valuacion` ya retirado (paso 1). **`ops/shadow_ranking.py` corre
   las 2 superficies sobre datos reales** (cobertura del fact store + ADV) → ranking lexicográfico. Verificado:
   LEU pasa; TENB/BWXT/OKTA los mata el falsador. **Cazó G8** (el gate no cubre pre-revenue-piso → usar burden).
   Falta: fix G8 · fuentes cobertura/catalizador (G7) · comparación vs merito + cutover. NO toca el paper.
4. ✅ **Tier→cap 8/5/2.5% HECHO (2026-08-14, shadow).** `politica.CAP_TIER_CAPITAL` {A:.08,B:.05,C:.025} +
   `cap_tier_capital()` (versión v1.1→v1.2). `candidato_desde` computa `cap = min(arquetipo×fragilidad,
   tier-capital)` (liquidez/sector se suman en sizing). Shadow muestra el cap. 299 tests. El `sizing`/`selector`
   VIVO no se toca (cutover). [B4]
5. ✅ **FichaPM sin merito cardinal HECHO (2026-08-14, shadow).** `FichaPM` (pm.py) dejó de llevar `merito`
   float → lleva **tier_capital + rank + cap** (doc 33: sin score cardinal); `_fmt_ficha`/`proponer_mix`
   re-inyectan tier/cap (no merito). `pm.ficha_desde_candidato(candidato, hoja, rank)` compone la ficha desde
   el `CandidatoLex` + números + cita de demanda + flags. **Cadena completa en shadow:** evaluar_ticker→hoja→
   candidato_desde→rankear_lexicografico→ficha_desde_candidato→proponer_mix. 303 tests. Nadie la construía antes
   → sin blast radius. NO toca el paper. [G1/#7]
6. 🟡 **Limpieza + fixes + ranking restructurado (2026-08-14).** ✅ limpieza. ✅ **asimetría N/A** cuando no hay
   ancla (mata el −1.00). ✅ **UNKNOWN demanda → DÉBIL, no CRÍTICO** (no auto-veto por ausencia). ✅ **RANKING POR
   CELDA** (`ranking_lexicografico`): `clave_economica_local` (asimetría FCFE / **burden-tupla** runway→burden
   pre-revenue) + `rankear_por_celda` (arquetipo×tier, sin orden económico cross-celda) + `cola_operativa` (por
   tier, round-robin, NO ranking económico). Shadow por celda verde (308 tests). **FALTA:** cuotas ex-ante de
   cartera que llenan las celdas · estado de **ABSTENCIÓN** + umbral de cita · componentes de la burden-tupla
   (funded-to-milestone/dilución-al-hito/backlog-cov, evidence-blocked) · invariante I2 · carril · replay+tablero.

7. ✅ **Construcción de CARTERA por celdas HECHO (2026-08-14, shadow).** `cartera_celdas.construir_cartera`:
   llena las celdas por la cola operativa con `min(cap, cuota-arquetipo-ex-ante, disponible)`; **caps NO cuotas**
   (si no hay buena empresa → cash, no se fuerza); piso + max-posiciones + sellado de política (`CUOTA_ARQUETIPO`,
   v1.3). **CADENA COMPLETA en shadow:** evaluar→hoja→candidato→rankear_por_celda→construir_cartera. Verificado:
   3 elegibles → 24% invertido, 76% cash. 313 tests.
8. ✅ **ABSTENCIÓN (tercer estado) HECHO (2026-08-14, shadow).** `CandidatoLex.abstenido` + `cola_investigacion`
   + `tasa_abstencion`; `politica.UMBRAL_COBERTURA_ABSTENCION` (v1.4, UNCALIBRADO placeholder). Distingue
   *decidido-fuera* (gate/veto) de *no-puedo-decidir* (evidencia insuficiente → cola de investigación, NO veto).
   Verificado: BWXT/NABL abstenidos (cobertura 7%<10%), tasa 33%. 317 tests. **FALTA para cutover:** umbral
   POR TIPO DE HECHO calibrado (hoy cobertura agregada) · sector caps (falta `sector` en `CandidatoLex`) ·
   burden-tupla completa · I2/carril (evidence-blocked) · replay + tablero · el cutover.

**Regla:** cada tajada con tests; no se toca el paper vivo hasta que la superficie nueva esté verde en shadow.
