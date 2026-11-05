# 78 — Cambio de método r7: valuación como motor + contratos como hecho duro

> **Prompt del operador (2026-11-05).** Pasado por una IA externa; adoptado por el operador como dirección de
> método. Este doc es la directiva; el esquema firme (y las mediciones que gatean los ítems riesgosos) se
> cierran antes de codear — ver la nota de reconciliación y el plan secuenciado al final.

## Nota de reconciliación con r6 (operador, 2026-11-05)

El §0 original dice "las bandas (especulativa ≤1,5% / satélite ≤5%) no se tocan". **Ese mismo día el operador
AMPLIÓ las bandas** (ips.yaml): especulativa **5%** · satélite **10%** · bucket especulativo **30%** · cluster
**40%**, y cambió el mandato del PM a **capital desplegado por default** (~90-100% salvo macro). **No hay
conflicto:** son palancas ortogonales que se componen —

1. **bandas más anchas** → más techo por nombre para el PM;
2. **contratos que gradúan** (este doc) → menos nombres atrapados en el carril especulativo chico;
3. **valuación como motor** (este doc) → el PM prefiere lo barato/contratado dentro de ese techo.

Por lo tanto, donde el §0 dice "no se toca", **léase contra los valores nuevos** (espec 5% / sat 10%). El
carril especulativo sigue existiendo y sin exigir valuación; sólo cambió su magnitud. Las tres palancas apuntan
al mismo objetivo: más capital desplegado, pero en SUSTANCIA (nombres con contrato/caja), no en apuestas
binarias más gordas.

---

# BORJA v2 — Cambio de método r7: valuación como motor + contratos como hecho duro

Decisión del operador. Partí del estado actual de la rama destete-v2-fase3, con r6 ya cerrado.

## 0. MARCO (no cambia)
- BORJA es un PM de IA: los agentes investigan, verifican y auditan; el PM-LLM decide nombres y tamaños. El
  determinismo INFORMA (datos, calculadoras, señales) y LIMITA (IPS, presupuesto). Nunca elige ni dimensiona.
- El carril de opciones ya existe: las bandas del operador (especulativa ≤1,5% / satélite ≤5%). No se toca.
  [Reconciliación 2026-11-05: léase contra las bandas ampliadas — espec 5% / sat 10%. Ver nota arriba.]
- CRITERIO CENTRAL DEL OPERADOR:
  - priorizar VALUACIÓN BAJA respecto de la generación de caja y el crecimiento;
  - un CONTRATO FIRME cuenta aunque la empresa todavía no genere caja.
- PROBLEMA ACTUAL:
  - La valuación solo FRENA: el PM achica si el precio ya descuenta la tesis. Nada prioriza lo barato.
  - La frontera entre carriles (D4) se define por revenue FY ≥ umbral. Un contrato firme no cuenta, así que
    una pre-revenue con un take-or-pay firmado cae en "especulativa".
  Las dos cosas se corrigen acá.

## 1. LENTE DE VALUACIÓN EN EL DATA PACK (determinista, con procedencia y known_at)
- XBRL nuevo:
  - RevenueRemainingPerformanceObligation (RPO/backlog);
  - ContractWithCustomerLiability (anticipos de clientes).
- Calculadoras DERIVED con linaje:
  - EV = market cap + deuda − (caja + inversiones de corto y largo plazo);
  - EV/revenue TTM, EV/bruto TTM y FCF yield (si FCF > 0);
  - crecimiento de revenue: últimos 4 trimestres vs los 4 anteriores;
  - EV/RPO y cobertura de backlog (RPO / revenue TTM);
  - valor contratado ajustado por margen: RPO × margen bruto (del XBRL; sin historial, se estima y se rotula
    como estimación).
- Percentil de cada métrica dentro de los pares de su cuello (nx_*).
- Emisores sin XBRL: n/a explícito, nunca estimado en silencio.
- Las métricas derivadas de insumos volátiles (precio, market cap) NO entran al hash de reutilización.
Tests con MP, OKLO y un nombre del universo con RPO.

## 2. CONTRATOS COMO HECHO DURO
- Parser del 8-K ítem 1.01: contraparte, monto, plazo, si es vinculante y condiciones precedentes. Fuente
  sec.gov, con el texto citado.
- Contratos de gobierno: monto OBLIGADO según USAspending.gov (fetch inyectable; corre en el server).
- DEFINICIÓN:
  - FIRME (cuenta como revenue para D4 y al 100% en el margen de seguridad):
    - take-or-pay, órdenes firmes, contratos vinculantes no cancelables o con penalidad de rescisión
      relevante;
    - RPO del XBRL;
    - contratos de gobierno SOLO por el monto obligado, nunca el techo del IDIQ.
    Contraparte con capacidad de pago (grado de inversión, hyperscaler, gobierno, utility). Siempre verificado
    con fuente primaria (8-K 1.01, 10-Q/10-K, USAspending).
  - CONDICIONAL (vinculante con condiciones precedentes de un tercero: licencia, financiación, FID del
    cliente): techo máximo = satélite; no suma al margen de seguridad como firme.
  - NO CUENTA: MOU, LOI, acuerdos marco sin volúmenes obligados, montos "de hasta X", techos de IDIQ, opciones
    no ejercidas, selecciones o adjudicaciones en negociación, partnerships sin condiciones de pago.
- RED FLAG: un solo cliente concentra más del 50% del backlog firme.
- Alinear con la escala de tracción de la ficha: 3 = firme, 2 = condicional. Ahora la tracción la VERIFICA el
  código con fuente primaria; no alcanza con que la declare el Analista.

## 3. EMBUDO
Agregar a la prioridad una señal de valor: percentil de EV / (valor contratado ajustado + revenue) dentro del
cuello. Lo barato con contrato firme sube en la fila. Mostrarla en el reporte del dry-run.

## 4. ANALISTA
Primera sección nueva de la ficha: "¿QUÉ COMPRO POR ESTE PRECIO?" (antes que todo lo demás):
- valor contratado firme y condicional, con claims ref al 8-K 1.01 / RPO / USAspending;
- calidad del contrato: cancelable o no, margen, cost-plus vs precio fijo, concentración, plazo de
  reconocimiento;
- caja actual o derivada de lo contratado;
- precio vs pares del cuello, usando la lente del pack;
- margen_de_seguridad = qué parte del EV cubren lo contratado firme (ajustado por margen) + la caja neta, y qué
  parte es opción.
Después sigue la ficha actual (captura de valor, riesgo remanente, camino crítico, qué exige el precio,
asimetría, test de atraso, clasificación). Los escenarios siguen igual.

## 5. VERIFICADOR
- Los claims de contrato son centrales cuando sostienen la tesis o el margen de seguridad.
- FIRME exige fuente primaria (8-K 1.01, 10-Q/10-K, USAspending). Un press release solo → condicional como
  máximo.
- Un monto "de hasta X" o un techo de IDIQ presentado como firme → REVIEW con motivo.

## 6. PM
Prompt: la valuación es MOTOR, no solo freno.
- A igual calidad de tesis, preferir el mayor valor contratado firme o caja por dólar de EV.
- El tamaño, dentro del techo de su carril, crece con el margen de seguridad.
- Cada acción declara su posición en un ranking de valor contra las alternativas vistas en la corrida y por qué
  eligió esa.
- Las especulativas siguen en su carril chico: no se les exige valuación.

## 7. D4: LA FRONTERA ENTRE CARRILES
- revenue_recurrente = revenue FY ≥ umbral_revenue_recurrente_usd, O revenue firme reconocible en ≤24 meses
  equivalente a ≥ ese umbral por año (contratos FIRMES verificados según el punto 2).
- Un contrato CONDICIONAL lleva como máximo a satélite.
- Por debajo del umbral, el contrato suma al margen de seguridad pero no cambia de carril.
- D4 sigue en sombra. NO pasar a sizing_modo: duro sin decisión explícita del operador.
Tests:
- pre-revenue con un take-or-pay firme verificado de US$200M a 24 meses con un hyperscaler → NO cae en
  "especulativa";
- el mismo contrato pero "sujeto a licencia" → techo satélite;
- un MOU → no cambia nada.

## 8. CIERRE
- Tests verdes, un commit por ítem, cada uno con su test de regresión.
- Dry-run del universo mostrando la señal de valor (top 15 por valor dentro de su cuello).
- Comandos listos para que el operador corra un smoke sobre 3 nombres (MP, OKLO y uno del universo con backlog
  firme). Export completo de los dossiers con la nueva sección y del ranking de valor del PM.
- Actualizar el doc 53 y dar un resumen honesto de qué se hizo, qué no y qué falta validar en vivo.

## REGLAS
- No inventar datos, fuentes ni citas. Una declaración de la empresa no es un hecho verificado.
- Nunca enviar órdenes reales.
- Lo que necesite API o red lo corre el operador en el server.

---

## Plan secuenciado + gates (ingeniero, 2026-11-05) — a cerrar con el operador antes de codear

El r7 es una **mini-fase**, no un patch. Orden por valor/riesgo, con mediciones que GATEAN lo riesgoso:

**Bloque 1 — lente de valuación determinista (alto valor, bajo riesgo; datos que ya tenemos).**
§1 (EV + múltiplos + crecimiento + percentil por cuello) · §3 (señal de valor en el embudo) · §6 (prompt del
PM: valuación como motor + ranking de valor). No depende del parser ni de RPO. Se puede hacer y testear ya.

**Bloque 2 — contratos como hecho duro (alto valor, ALTO riesgo de datos/NLP; GATEADO por medición).**
- **Gate A — cobertura:** medir RevenueRemainingPerformanceObligation + ContractWithCustomerLiability sobre el
  universo real (como el doc 60 midió el backbone). Si la cobertura es pobre en small caps/extranjeros, la
  lente RPO queda n/a justo donde hace falta → decidir alcance antes de construir sobre ella.
- **Gate B — precisión del parser 8-K 1.01:** gold set de contratos etiquetados a mano (firme/condicional/no
  cuenta) + precisión medida ANTES de que un FIRME mueva un tamaño. Un falso FIRME infla el margen de seguridad
  y sizea de más — el modo de falla que el doc 72 marcó (sobrevender la oportunidad). Sin harness, no shippea.
- §2 (parser + USAspending monto obligado) · §4 (sección "¿qué compro por este precio?") · §5 (reglas del
  Verificador) · §7 (frontera D4 con contratos; sigue en sombra).

**Conversión contrato→revenue-equivalente (§7):** default conservador (lineal sobre el plazo declarado),
rotulado estimado; si no, se presta a gaming de la frontera.

**Cuidado deep-value (§1/§6):** EV/revenue NUNCA se muestra solo — siempre con crecimiento + cobertura de
backlog al lado. Percentil DENTRO del cuello (relativo), no "barato absoluto". Es el seguro contra re-derivar
al agujero deep-value (memoria: drift growth→deep-value, g=0 sub-dimensiona la tesis).

**Triangulación:** el DISEÑO de r7 es sólido; los gates reales son EMPÍRICOS (cobertura, precisión), no debates
de método → la triangulación daría rendimiento marginal. Se puede hacer una vuelta corta enfocada sólo en §2/§7
(definición de firme/condicional + frontera) si el operador la quiere; el resto arranca.
