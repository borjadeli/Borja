# 74 — Convergencia Tier B (2 IAs) + plan de implementación

> Triangulación del doc 73 (Tier B: el puente económico al precio) por 2 IAs independientes de alta calidad.
> **Convergieron fuerte**; una tercera daría rendimiento marginal → cerrado. Este doc fija lo FIRME (diseño,
> no debate), las decisiones del operador, los cortes por sobreingeniería, y el orden de implementación.
> Secuela del doc 72 (hallazgo: "el sistema analiza el riesgo bien y la oportunidad mal").

## 0. El corazón (las 2 IAs: "si hago una sola cosa, esta")

**D1 en su versión INVERSA** (reverse burden = probabilidad implícita). Para cada nombre, una línea:
> *"A este precio, para ganar 15%/año necesitás X de [métrica] en [año] a [múltiplo] con [dilución]; equivale
> a una probabilidad de bull ≥ Y%."*

El PM no le cree al "25%" del analista; juzga si *"este precio exige ≥35% de bull"* es razonable. Es
**expectations investing** (Mauboussin/Rappaport): leer qué descuenta el precio en vez de proyectar la propia
historia. Reduce la dependencia de las probabilidades del LLM (el punto más débil). **Reemplaza al retorno
esperado ponderado como pieza central.** Es el reverse underwriting canónico de BORJA (doc 31/33), ahora atado
al precio y al retorno del accionista.

## 1. FIRME — diseño convergido

**D1 — puente económico (aritmética pura, solo DISPLAY, nunca gate ni score):**
- **Inverso/probabilidad implícita** como salida principal (§0).
- **No ponderar IRRs** (Jensen): ponderar en **MOIC por acción**, recién después anualizar. Mostrar: esperado,
  **base (≈mediana)**, **P(pérdida >50%)** y probabilidad implícita. La brecha esperado↔mediana dice "es una
  opción, no una inversión" → alimenta D4.
- **Equity bridge EV→equity:** múltiplo da EV; para llegar a precio/acción hay que restar deuda y sumar/restar
  caja neta del año terminal (depende del burn hasta ahí). No comparar EV terminal vs EV hoy a secas.
- **Dilución = PISO determinista:** `gap = burn acumulado − caja`, emitido al precio de hoy, + SBC. El analista
  puede poner MÁS, nunca menos. Permitir dilución negativa (recompras) → el mismo helper sirve para core.
- **Bear = "la tesis FALLA", no "se demora"** → valor ≈ caja remanente, anclado en lo que vale el negocio de
  HOY sin futuro. **Acá entra la pata del presente** al puente económico (no compite con el futuro).
- **Múltiplo de salida:** anclado a comparables con el crecimiento/margen del AÑO TERMINAL (no de hoy);
  declarar el margen terminal que lo justifica; marcar (sin bloquear) si cae fuera del p10–p90 del sector;
  **mostrarlo siempre** junto al resultado ("a 8x") porque puede decidir todo sin verse.
- **Tasa = HURDLE fija 15%**, no "ajustada por riesgo". El fracaso ya está en el bear+su probabilidad; subir la
  tasa por riesgo científico es **doble conteo**. ±3pp de sensibilidad como mucho.

**D2 — falsadores con vara externa (`vara_externa`):**
- Campos: `tipo` (hito-de-tercero | económico | competitivo), `metrica`, `umbral`, `comparador`,
  `fuente_medicion`, `fecha_limite`, `accion_si_dispara`. Exigir al menos uno económico o competitivo, con un
  `no_aplica`+razón que el Verificador revisa (sin esa salida, el LLM fabrica un comparable = cumplimiento
  teatral, peor que vacío).
- **El Bear endurece o propone el falsador** (no solo el Analista, que es pro-tesis — raíz del problema).
- **Silencio = disparado:** fecha límite sin evidencia cuenta como falla. Preferir hitos de terceros
  (regulador, cliente con contrato vinculante+precio) a hitos propios.
- **Consecuencia pre-comprometida:** dispara → baja un escalón de clasificación (D4) y el **bear de D1 pasa a
  ser el base**. Sin consecuencia, el falsador es decoración.

**D3 — tasas base (tabla curada que el sistema POSEE, no citas libres):**
- 15–25 filas curadas (persistencia de crecimiento por tamaño/sector — Mauboussin/Callahan; sobrecostos/demoras
  de megaproyectos — Flyvbjerg, nuclear en la peor cola; dilución histórica de small caps pre-revenue;
  cumplimiento de guidance de primera planta comercial — varias computables del propio universo). El analista
  elige la fila; si ninguna aplica, "sin muestra". Evita el **lavado de citas** (citar el libro para lo que no
  dice, peor que "juicio sin muestra" porque parece fundado).
- **Conectada a D1:** la probabilidad de bull declara su ancla (una fila o "sin muestra") y el ajuste; si queda
  **>2x por encima de la tasa base → Verificador REVIEW**. D3 pasa de nota al pie a control de calibración de
  D1. (Se CORTA el check genérico de "afirmaciones tipo-tasa-base" en todo el texto: ruidoso, nadie lo lee.)

**D4 — sizing por clasificación (determinismo como LÍMITE):**
- **Techo determinista de clasificación por hechos duros** (para que el Analista, pro-tesis, no infle la
  etiqueta): sin revenue recurrente → máx `especulativa`; FCF neg + runway <24m → máx `satelite`; **D1 UNKNOWN
  → máx `especulativa`** (sin puente económico, solo tamaño de opción). El Analista clasifica igual o MÁS BAJO,
  nunca más alto; el Auditor la cuestiona.
- **Banda de peso por clasificación = cap duro en el IPS** (precedente: ya existe `cap_flag_supervivencia`).
  El gate **rebota y exige reformular, NO clipea en silencio**. El PM sizea DENTRO. **NO hay fórmula
  determinista de sizing** (sería trasladar la decisión al código).
- **Caps agregados** (la banda por nombre no controla el riesgo que importa — 10 especulativas a 1,5% = 15% de
  apuestas binarias correlacionadas): **cap del bucket especulativo** + **cap por cluster temático**
  (cuánticas entre sí, SMRs entre sí, tierras raras atadas a China–EE.UU.).
- **Drift:** una especulativa que hace 4x NO sube de banda por precio; solo sube por **reclasificación al
  superar falsadores** (el tamaño sigue al de-risking, no al momentum). Por suba: revisión a 2x la banda, no
  venta automática (cortar la opción ganadora temprano destruye la asimetría — coherente con [[escalera-addon-cerrada]]).
- **Downside real −80%** (no −40/−50: en pre-revenue con burn, cuando falla la caja ya se quemó).
- **No hay piso de 5%/nombre en el IPS v2** (verificado en `config/ips.yaml`) → las bandas chicas no chocan.

**D5 — Auditor con web (mandato estrecho):**
- Flujo: PM (provisional) → Auditor (búsqueda **para refutar**, no para entender) → hallazgo material +
  evidencia + consecuencia → **el Verificador lo valida** y la objeción va **primero al Analista a responder** →
  PM reconsidera **una vez**. Una objeción no verificada NO es veto (validación o incertidumbre para el humano).
- **Umbral de materialidad:** cuenta solo si, de ser cierta, cambia un número de D1, un falsador o una
  clasificación. **Máx 3 por nombre.**
- **Dirigido por checklist** (lo que el comité pierde sistemáticamente): eventos vinculantes a ≤90 días;
  cláusulas de filings (clawbacks, warrants, ATM, covenants); cambios de guidance/capex; acuerdos comerciales
  nuevos + competidor relevante.
- **Parte es DETERMINISTA, no del LLM:** el vencimiento a 8 días y el capex revisado deberían venir de un
  **calendario de eventos + diff de filings**, no pedírselo a un LLM. (Feed > LLM para datos.)
- Correr el Auditor en **modelo distinto** al Analista (errores descorrelacionados). **Darle el mismo checklist
  al Bear** (ya tiene web y no cazó el clawback). Medir hit-rate y decidir en 2–3 ciclos si se queda.

**Transversal — persistencia ex-post (barato y crítico):** guardar escenarios, probabilidades y falsadores al
momento de cada decisión → puntuar ex-post (Brier sobre falsadores y sobre la probabilidad de bull). Sin esto
no se sabe si Tier B mejoró el análisis de oportunidad o solo lo vistió de números.

## 2. Principio rector — las puertas traseras a vigilar

- **D1 solo DISPLAY, nunca gate ni score.** Si algo lo usa para rankear/gatear, el determinismo empieza a
  decidir y el futuro (por la cola bull) pesa de más. El PM sigue contrastando con negocio HOY, historial,
  balance, financiamiento y precio. **Nada de score agregado donde 2034 domine los hechos de 2026.**
- **D4:** la clasificación NO debe ser manipulable → techo determinista + desafío del Auditor.
- **D1 no es un DCF encubierto** (los inputs son juicio), pero el múltiplo de salida puede decidir todo sin
  verse → mostrarlo siempre.

## 3. Cortes por sobreingeniería (las 2 IAs)

Nada de: DCF anual completo por empresa · tasas de descuento por arquetipo · modelos probabilísticos que simulen
calibración inexistente · competidor comparable obligatorio en todo falsador · fórmula automática de sizing ·
iteraciones extra PM↔Auditor · búsqueda abierta del Auditor · uso de D1 como score · check genérico de D3.
Para negocios binarios: éxito/fracaso sin inventar un EBITDA intermedio. **Criterio único para sumar
complejidad: ¿esta variable podría cambiar razonablemente la decisión de inversión?**

## 4. Decisión del operador (única abierta): números de las bandas

Contexto real del IPS: **12 plazas**, sin piso por nombre, downside especulativa −80%. Regla de calibración
(IA2): *la pérdida en bear de una especulativa ≤ ~1% del NAV*. Propuestas:

| | watchlist | especulativa | satélite | core | bucket espec. | cluster temático |
|---|---|---|---|---|---|---|
| IA1 | 0% | ≤2% | ≤6% | IPS máx | — | — |
| IA2 | 0% | ≤1,5% | ≤4% | 6–8% | 8–10% | 15–20% |
| **Recomendado** (12 plazas) | 0% | **≤1,5%** | **≤5%** | IPS máx (20%) | **≤10%** | **≤20%** |

Recomiendo ≤1,5% especulativa (bear −80% → −1,2% del NAV, cerca de la regla; 2% daría −1,6%) y ≤5% satélite
(regla de IA2 para ≤15 plazas). **A confirmar por el operador** (es apetito de riesgo).

## 5. Orden de implementación (síntesis de ambos órdenes)

1. **Persistencia ex-post** (Brier) — cimiento de todo, barato.
2. **D4 en modo SOMBRA** (bandas + caps agregados + techo determinista de clasificación): config sobre un gate
   que ya existe; arregla el fallo observado (OKLO 2,8% ≈ MP 3%) sin activar el cap duro hasta confiar en la
   clasificación.
3. **D1 + D2** como un solo cambio de schema de la ficha (el corazón: inverso/probabilidad implícita, MOIC por
   acción, EV→equity, piso de dilución, bear=falsador, vara_externa). Probar con RGTI/OKLO/MP.
4. **D3** tabla curada + regla de ancla de la probabilidad de bull.
5. **D5** piloto en 3–5 nombres, 2 ciclos, en paralelo con el calendario de eventos + diff de filings
   deterministas; darle el checklist al Bear. Medir hit-rate.
6. Activar el **cap duro de D4** cuando la clasificación sea confiable.

(Base ya construida: `futuro.retorno_por_escenario` — commit 42a5061 — hace la aritmética directa; falta
girarla al inverso y agregar el equity bridge + piso de dilución.)
