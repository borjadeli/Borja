# 24 — El motor de evidencia ENSAMBLADO (para triangular el CONJUNTO)

> Construimos las piezas bottom-up y cada una se triangeló sola. Este doc presenta el
> **sistema ARMADO** para una revisión del **conjunto**, antes de integrarlo al pipeline
> vivo. La pregunta no es sobre una pieza: **¿el todo encaja? ¿qué falla estructuralmente?
> ¿qué rompe en producción? ¿qué costura entre piezas quedó mal?**

## Contexto (para una IA externa)
Sistema quant de small/mid caps de "industrias del futuro" (cuellos de botella). Principio
rector: **datos y límites duros deterministas; el LLM trae hechos citados y NUNCA inventa un
número de decisión; un PM-LLM decide DENTRO de caps deterministas.** El detonante: el extractor
viejo pedía al LLM "traer hechos" pero NO le pasaba el filing — extraía de memoria → sobre inputs
idénticos, la empresa COHR entraba 2 de 4 corridas y se rechazaba 2 (un booleano gate-crítico
muestreado distinto cada vez). Reconstruimos el análisis como **motor de evidencia**: leer texto
primario real, extraer citando, verificar, y decidir determinísticamente.

## El sistema COMO ESTÁ CONSTRUIDO (módulos + flujo, todo andando)
```
generador → retrieval/FTS → extractor_citado (D+E) → fact_store → gate_evidencia → cuarentena → re-gate
```
- **`generador.py`** — capa generadora: memoria del LLM como MARCO (K framings distintos → UNIÓN
  de leads); cada lead se verifica contra FTS. La memoria propone qué buscar, nunca afirma un hecho.
- **`retrieval.py`** — `resolver_corpus` (último filing + exhibits Ex-10/Ex-99), `buscar_fts`
  (EDGAR full-text: consultar, no crawlear), `clasificar_por_titulo` (pre-filtro gratis por título;
  la lección AAOI: contar palabras falla, el título no).
- **`extractor_citado.py`** — **D**: el LLM lee UN chunk y emite `value + support_type + quote
  VERBATIM`. **E**: verificador determinista (substring normalizado + offsets, números vs XBRL);
  sin cita fundada → degrada a UNKNOWN (fail-safe). Soporte DIRECT/DERIVED/INFERRED/UNKNOWN.
- **`fact_store.py`** + tabla `NxFact` — append-only inmutable, `guardar` (dedup + supersesión),
  `snapshot_vigente` (point-in-time por `accepted_at`), `diff` (delta de evidencia). Provenance
  (model/prompt/retriever/hash) por hecho.
- **`fact_keys.py`** — registry (qué extraer, pregunta, anchors, fact_type, XBRL).
- **`analisis.py`** — orquestador `analizar_ticker`: resolver → por cada fact_key extraer+verificar
  → persistir → snapshot. No decide (deja los hechos listos).
- **`gate_evidencia.py`** — gate sobre el snapshot: `no_pasa` (hecho FALSE) vs `NO_EVALUABLE`
  (hecho gate-crítico UNKNOWN → cuarentena con la pregunta) vs `pasa`. Demanda = existencia-abre +
  tier de magnitud (VALIDATED/COMMITTED/REALIZED). Solo DIRECT/DERIVED alimentan hard items.
- **`cuarentena.py`** — ante NO_EVALUABLE dispara UNA búsqueda dirigida (FTS con los términos →
  mejor hit → extraer+verificar → persistir → re-gate). No es loop; si no encuentra, espera el
  próximo filing o el vencimiento.
- **`eval/`** — gold set (4 empresas, hechos etiquetados del filing real) + harness
  (estabilidad/corrección/grounding). 125/125 en la suite.

## Decisiones AS-BUILT clave (lo que quedó fijado al construir)
1. **Solo DIRECT/DERIVED alimentan hard gates.** INFERRED prioriza, no decide. Orden: XBRL →
   disclosure obligatoria → texto citado → UNKNOWN (derivar-antes-de-extraer).
2. **UNKNOWN ≠ FALSE.** Falta de evidencia → NO_EVALUABLE/cuarentena, nunca rechazo.
3. **Existencia abre; magnitud fija el cap.** Una redacción (Reg S-K 601) es evidencia fuerte con
   un campo tapado, no ausencia. AAOI/Amazon = VALIDATED (discrecional), no COMMITTED (verificado
   contra el 8-K: "discretionary purchases... up to $4 billion").
4. **Fail-safe:** cita no fundada, número que contradice XBRL, o parse dudoso → UNKNOWN, nunca un
   valor inventado. (Se validó cazando un bug propio: una fecha ilegible dio UNKNOWN, no un dato falso.)
5. **Point-in-time por `accepted_at`** (arregla look-ahead de datos, no el de training del LLM →
   el juicio de alpha es forward paper sellado, no backtest).
6. **Memoria: propone (leads, unión), no afirma (hechos, intersección/unanimidad).**

## Lo que FALTA (no construido aún)
- **Componer con `gate.py`** — el checklist estructural viejo (U1 triggers, G1 orgánico,
  financiación) todavía no se fusionó con el gate nuevo. **Es el fork abierto** (pregunta 3).
- **Tier → caps** — el tier de magnitud aún no mapea a tamaño de posición (pregunta 4).
- **K=3 unanimidad** en booleanos gate-críticos (a nivel extracción).
- **Job del scheduler** (poll diario de filings + dispara cuarentena) e **integración al pipeline
  vivo** (reemplazar el extractor viejo que hoy corre el paper).

## Preguntas para la revisión del CONJUNTO
1. **¿El todo encaja, o hay una costura mal resuelta entre piezas?** (p.ej. generador↔retrieval,
   extractor↔fact_store, fact_store↔gate). ¿Algún supuesto de una pieza que otra viola?
2. **¿Qué rompe en producción que los demos no muestran?** Filings raros (NT, 10-K/A, cambio de
   fiscal year), empresas sin exhibits, FTS caído/rate-limited, un fact_key que ninguna sección
   ancla, un ticker con múltiples CIK, un filing de 300MB.
3. **El fork `gate.py`:** ¿el checklist estructural viejo (binario) CONVIVE con el tier de
   magnitud, o el estándar de demanda REEMPLAZA los ítems de continuidad (G2/T1/P1)? ¿Cuál es la
   composición correcta, y qué ítems son binarios vs. tier?
4. **tier → caps:** ya hay caps deterministas por arquetipo × fragility. ¿Cómo mapear
   VALIDATED/COMMITTED/REALIZED a un cap SIN doble-penalizar ni netear con la fragility? ¿El tier
   es un cap adicional (min) o un multiplicador?
5. **Cuarentena auto-resuelta:** ¿tiene un failure mode? Un término de búsqueda que matchea otra
   cosa (falso positivo), una cita que existe pero no sostiene el estado, un "loop encubierto" si
   cada filing nuevo la re-dispara. ¿Cómo acotar y cómo registrar "buscado y no encontrado"?
6. **¿Qué NO estamos midiendo** que debería estar en el harness antes de ir a vivo? (más allá de
   estabilidad/corrección/grounding sobre 4 nombres).
7. **Orden de integración menos riesgoso:** ¿shadow mode (correr el motor nuevo en paralelo sin
   operar) por N semanas antes de reemplazar? ¿Qué métrica de paridad/divergencia mirarías?

Devolvé crítica del **conjunto**, priorizada, y donde discrepes tu alternativa. No re-revises
piezas sueltas (ya se triangularon); enfocá en cómo encajan y qué falla en producción.
