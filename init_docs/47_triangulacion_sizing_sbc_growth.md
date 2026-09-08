# 47 — Triangulación: sizing del bucket growth de alto SBC (owner-FCF<0)

> Estado: ABIERTA (2026-09-02). Disparador: post-extracción, los 9 UNDERWRITTEN salieron todos
> `OPTION_PRICED` (tamaño chico) porque los 9 rutean a **BURDEN**. Diagnóstico preciso abajo.
> Triangulación en curso: subagente Claude ciego + 2 IAs externas (circula el operador).
> Relacionado: [[drift-valuacion-growth-reverse-underwriting]] (doc 36), ruteo doc 42.

## Diagnóstico (números reales que ve el router)

| Ticker | GM | apal Δ8Q(GP)/Δ8Q(OpEx) | owner-FCF post-SBC | SBC/rev | burden | → ruteo |
|---|---|---|---|---|---|---|
| NET | 73% | 0.70 | −$159M | 20% | 16.6× | BURDEN (owner-FCF<0, apal<1) |
| S | 73% | **1.13** | −$266M | **29%** | **2.65×** | BURDEN (SBC>25% pisa el apal>1) |
| VRNS | 77% | 0.60 | −$11M | 19% | 3.0× | BURDEN (owner-FCF<0, apal<1) |
| PL | 56% | 0.94 | −$12M | 18% | 11.4× | BURDEN (apal 0.94 casi) |
| RKLB | 37% | 0.99 | −$453M | 11% | 41× | BURDEN |
| SDGR/KTOS/AAOI/LEU | 23-57% | <1 o neg | negativo | bajo | — | BURDEN (correcto) |

## Veredicto interno (a validar)

- **CORRECTO, no tocar:** el gate `owner-FCF POST-SBC < 0` es la disciplina central. NET gasta
  $508M/año en SBC > todo su FCF: en economía-del-dueño no genera cash. El muro-SBC es un feature.
- **CIEGO (3 bordes que aplastan distinciones):**
  1. `apal > 1.0` es un acantilado (PL 0.94 = SDGR −0.26 = LEU −1.17, todos BURDEN).
  2. SBC>25% pisa el apalancamiento DEMOSTRADO (S apal 1.13 → BURDEN igual).
  3. BURDEN aplasta la MAGNITUD del burden a OPTION_PRICED: S (2.65×) = RKLB (41×).

## Las 4 preguntas de triangulación
1. ¿`owner-FCF post-SBC < 0` es la vara correcta para achicar, o el sistema tiene razón y me tienta el growth?
2. ¿`apal > 1` debe override el veto SBC>25%? ¿Con qué guarda anti-diluidor-serial?
3. Dentro de "caro/BURDEN", ¿el tamaño debe escalar con (burden, GM, apal, SBC)? Fórmula concreta.
4. ¿Modo de falla de darle más tamaño a estos (queman cash del dueño) que no esté viendo?

## Convergencia (a completar cuando vuelvan las 3 voces)

### Voz #1 — Claude ciego (2026-09-02) ✓
Reencuadre central: el gate NO es un sizer, es un **clasificador de régimen (techo)**. El error fue
implementarlo como **masa puntual** (todos a 2%) en vez de **techo con distribución debajo**.
*"you weren't being seduced by growth; you were being lossy."*
- **Q1:** owner-FCF post-SBC<0 se QUEDA (SBC = comp diferida real, los buybacks lo prueban). Define el
  **techo** del bucket (`W_max ≈ 4%`/nombre), NO el nivel.
- **Q2:** NO override de SBC>25% por apal. SBC → **impuesto continuo** `d = clip(1−max(0,SBC−0.15)/0.20, 0.4, 1)`.
  IDEA NUEVA: exigir **`apal_net = Δ8Q(GP)/(Δ8Q(cashOpEx)+Δ8Q(SBC))` ≥ 1** (dilución adentro) —
  desenmascara al diluidor que disfraza SBC como leverage. Resuelve S sin override.
- **Q3:** `peso = W_max × B(burden,log2) × Q(GM) × L(apal_net,rampa) × d(SBC)`, multiplicativo
  no-compensatorio. Worked: S≈2.0%, VRNS≈1.2%, NET≈0.84%, PL≈0.89%, RKLB≈0.25%.
- **Q4 (modo de falla que no veíamos):** **riesgo de ventana de financiamiento CORRELACIONADO** — todos
  los owner-FCF<0 comparten el factor "acceso a capital barato"; en un repricing caen juntos. Beta del
  bucket ≈1. → **CAP AGREGADO del bucket `Σ ≤ ~18%`** (pro-rata scaledown), la disciplina real que falta.

### Voz #2 — IA externa 1 (2026-09-02) ✓
Converge con #1: owner-FCF<0 = techo, no masa puntual; fórmula continua burden-dominante; no override
desnudo; cap de cluster. *"No estás equivocado en castigar owner-FCF negativo. Estás equivocado en
castigarlo de manera binaria."* Aportes NUEVOS (no dijo #1):
- **Matar el piso de 2% de verdad:** size calculado <0.5% → **0%**, no redondear a 2%.
- **Doble conteo:** si el reverse-DCF ya proyecta shares futuras, NO restar además SBC completo del FCF.
  Elegir UN método. → CHEQUEAR si nuestro reverse-DCF proyecta shares. (si sí, el gate owner-FCF y el T*
  ya castigan dilución dos veces).
- **Usar T\* en vez de burden bruto:** `f_burden = 0.75·exp(−0.23·max(T*−3,0))`. Ya tenemos T*.
- **Dilución con shares OUTSTANDING reales**, no diluted weighted-average. Ratio clave **SBC/GP** (S ≈ 40%:
  paga 40¢ de acciones por $1 de gross profit).
- Separar `FCF_cash = CFO−capex` (supervivencia/financiamiento) de `FCF_owner = CFO−capex−SBC` (economía
  del accionista): dos caps distintos (runway_cap por FCF_cash + dilution_cap por dilución efectiva).
- Mecanismo anti-diluidor propuesto: categoría discreta **ESCALANDO_DILUTIVO** (solo SBC 25-40% + guardas
  de TENDENCIA: apal 8Q≥1 y 4Q≥0.9, owner-FCF margin +3pp/8Q, SBC/rev −2pp/8Q, dilución≤6%, runway≥36m),
  cap 60% del techo si pasa / 15% si no. SBC>40% o dilución>12% → excluida.
- Worked (techo 6%): S 3.6%/0.9%, VRNS 3.1%, PL 1.1%, NET 0.9%, RKLB 0.4%→watch.

### Voz #3 — IA externa 2 (2026-09-02) ✓ — la más profunda
Diagnóstico de raíz: **mezclás dos variables con controles distintos.** Dilución = impuesto al RETORNO
(→ valuación). Quema de caja = riesgo de SUPERVIVENCIA (→ tamaño). Aplicás el control de supervivencia
(tamaño mínimo) a un problema de retorno. Identidad CFO−capex = owner-FCF + SBC: **4 de 5 GENERAN caja**
(solo RKLB quema). Cobrás SBC como si fuera caja — es costo de propiedad, no de solvencia.
- **SBC/rev es la métrica equivocada** (grants en $: si la acción sube 3×, mismo $ emite ⅓ de acciones →
  ratio sube mecánicamente por apreciación, al revés de lo que importa). Usar **dilución neta observada**
  (CAGR share count fully-diluted neto de recompras). [converge con #2]
- **Dos gates:** A) solvencia binaria `burn=CFO−capex` SIN restar SBC (solo muerde RKLB); B) dilución
  continua a la VALUACIÓN `B_adj = burden×(1+d)^H`, `d=max(d_3y, d_stress)` (SBC es short-vol del share
  count: si cae 50% emite 2×).
- **Sizear por T, NO por burden crudo:** `T_flat = ln(B_adj)/ln(1+g)`; luego **fade** g→8% entre t5-t10.
  BOMBSHELL con nuestros números: RKLB (41×) exige MENOS años que NET (16.6×); PL (11.4×) es el PEOR (22y).
  *"escalar con la magnitud del burden te habría hecho lo contrario de lo correcto en 3 de 5."*
- **Override real = ΔGP/acción(8Q) ≥ 12% anual**, NO apal (apal = confirmación 2ª). Anti-diluidor: 3
  condiciones (ΔGP/acción≥12% + d no creciente + overhang RSU/options<8%).
- **apal es frágil — LAG:** el S&M de hoy da GP en 2-4Q; medir GP vs OpEx contemporáneos sesga apal ABAJO
  en quien acelera inversión. `apal = Δ8Q(GP lag 3Q)/Δ8Q(OpEx)`. Puede rescatar NET/VRNS. + t-stat>2 sobre
  12Q, ΔOpEx>15%base, ΔGP>0.
- **Convexidad (el punto más profundo):** el 10× vive en los RKLB, no en S (burden 2.65× no tiene espacio
  de múltiplo p/ 10×). Mover capital de opción→moderado mata la cola que justifica el mandato. **RKLB →
  sleeve de opciones (3-5% book, 8-15 nombres @0.3-0.5%, mortalidad 60%+, sizeado por BASE-RATE de hito,
  NO por burden).** = nuestro carril doc 29.
- Worked (CAP 8%): S 4.0%, VRNS 1.5%, NET 0%(watch), PL 0%, RKLB ≤0.5%(→sleeve). "no es más tamaño al
  bucket, es DISPERSIÓN."
- Caveats de la #3: verificar g_GP REALES (usó supuestos; T hipersensible a g, sobre todo RKLB) y SBC-$.

## ESQUEMA CERRADO (síntesis de las 3 voces, 2026-09-02)
```
Gate A (supervivencia):  burn = CFO−capex (SIN SBC). runway corto → opción/0.  [solo RKLB]
Gate B (dilución→valuac): B_adj = burden × (1+d)^H,  H=7,  d = max(d_3y, d_stress).  d = share-count CAGR.
Sizing por T (NO burden): T_fade (fade g→8% t5-t10);  f_val = clip((T_max−T_fade)/(T_max−T_min)), T∈[3,12].
Override acretividad:     ΔGP/acción(8Q) ≥ 12%.  apal = confirmación 2ª (con LAG 3Q + t-stat>2 + ΔOpEx>15%).
SIZE = min(CAP × f_val × q_GM × q_apal × q_ps,  tope_caja,  gate_A)
Cluster cap:             Σ bucket ≤ 2×CAP  (N_eff: ρ≈0.7 ⇒ 5 nombres ≈ 1.3 apuestas).
Convexidad:              RKLB-type → carril doc 29, sizeado por base-rate de hito, NO por burden.
Matar piso 2%:           SIZE < 0.5% → 0%.
```
Divergencia menor (resuelta): anti-diluidor continuo (#1 apal_net / #3 ΔGP-acción) > categoría discreta
(#2). Se adopta **ΔGP/acción** (#3) como gate + apal-con-lag como confirmación.

## IMPLEMENTACIÓN — Fase 1 (2026-09-03, política v2.1, 450 tests verde)
Módulo nuevo `backend/nucleo/sizing_burden.py` (puro, testeado `tests/test_sizing_burden.py`):
- **#1 apal LAG 3Q** (`ruteo.apalancamiento_operativo(lag_q)` + guarda ambos deltas>0): RESCATÓ NET
  (0.70→1.20 → COMERCIAL_ESCALANDO), desenmascaró S (1.13→0.85), neutralizó PL (artefacto).
- **#2 sizing por T_fade** (`t_fade(burden, g)` con fade g→8% t5-t10): la variable correcta. Reemplaza el
  cliff OPTION_PRICED. `SIZE = CAP × f_val(T) × q_GM × q_apal × q_ps(acretividad) × d_sbc`.
- **#3 cap de cluster** `aplicar_cap_cluster` (Σ ≤ 2×CAP).  **#4 piso muerto** (<0.5%→0).
- **#5 RKLB-type → carril** (Gate A: quema caja pre-SBC → pura opción, base-rate).
- Resultado sobre los 5 (ANTES todos ~2%): **S 1.7%** (libro duro, top) · NET/VRNS/PL **0/WATCH** (caros,
  esperar) · RKLB **carril**. Coincide con la #3; S sale más conservador que su 3.6% porque usamos apal-LAG.
- Constantes calibrables en politica: CAP_BURN_BUCKET=8%, CLUSTER_CAP_MULT=2, SIZE_FLOOR_KILL=0.5%,
  ACRETIVIDAD_MIN=12%, SBC_TAX_KNEE/SLOPE.
- **WIRING (hecho, v2.2):** `hoja()` computa `size_burden` → `candidato_desde` lo usa como cap de valuación.
- **v2.2:** quitado el triple-conteo de SBC (sin `d_sbc`: la dilución ya se cobra vía burden+acretividad) → S 0.7→1.6%.
  Gate de carril por burden (>15× = pura opción): KTOS/LEU vuelven al libro duro, no al sleeve.
- **v2.3 (corrección ARQUITECTÓNICA, decisión del operador):** `sizing_burden` produce un **CAP en [4%,8%]**, NO el
  tamaño. El PM SELECCIONA y sizea DENTRO del cap (doc 39 sándwich: determinismo=límites, juicio=futuro/elige). Un
  nombre elegible nunca baja de 4% (CAP_FLOOR) — eso le prohibiría al PM tesis de aceleración de crecimiento que el
  g-demostrado no ve. Mérito = f_val×q_GM×q_apal×q_ps ∈[0,1] interpola FLOOR→MAX. Libro final: S cap 4.8% (barato,
  mayor techo), resto 4.0% (piso), RKLB/AAOI carril. **Fase 1 COMPLETA, 450 tests, política v2.3.**

## CHEQUEOS repo-grounded ANTES de codear (medición, no juicio)
1. ¿El reverse-DCF (t_star/burden) ya proyecta shares? Si sí, owner-FCF post-SBC + B_adj = triple conteo.
2. Correr apal con LAG 3Q sobre NET/VRNS/S/PL (¿rescata?).
3. g_GP demostrado REAL (8-12Q) de cada nombre → recalcular T_fade con datos nuestros, no supuestos.

### Puntos a chequear si convergen las 3
1. techo-con-distribución (vs masa puntual) — ¿unánime?
2. `apal_net` (dilución adentro) como anti-gaming — ¿lo proponen independientemente?
3. cap AGREGADO del bucket por riesgo de financiamiento correlacionado — ¿lo ven?
4. forma de la fórmula de tamaño (bandas vs continua; qué factores).

- Esquema cerrado: _pendiente_ → recién ahí se codea.
