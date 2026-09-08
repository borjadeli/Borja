# 21 — El extractor como MOTOR DE EVIDENCIA (diseño para triangular)

> Cómo el sistema extrae hoy los hechos de UNA empresa, por qué es inestable (evidencia
> MEDIDA), y el rediseño: **recuperar texto primario FRESCO → extraer citando → verificar
> la cita (determinista) → fact store versionado.** Es el motor del doc 20 aplicado a la
> empresa: arreglar la estabilidad ES construir el edge. Sin código hasta triangular.

## Contexto (para una IA externa)
Sistema quant de small/mid caps de "industrias del futuro" (cuellos de botella).
**Principio rector:** los datos y límites duros son deterministas; el LLM trae **hechos con
fuente** y NUNCA inventa un número de decisión. La decisión (arquetipo → gate → quality →
asimetría → fragility → mérito → sizing) es 100% determinista. El extractor es la puerta de
entrada de los hechos: si es inestable o inventa, todo lo de abajo se corrompe.

## La evidencia del problema (medido, 2026-07-29)
Corrimos la extracción **K=4 veces sobre el MISMO ticker, mismo día, mismos números**:
- **COHR**: 2 corridas → `candidata`, 2 → `rechazo`. **Todo el flip dependía de UN booleano**
  (`gate.growth.desglose_organico_disponible`): en 2 corridas el LLM dijo "orgánico 100%,
  fuente A" (pasa G1), en 2 dijo "no hay desglose" (falla G1 por default-exclude).
- Los **triggers de invalidación** salieron con **texto distinto en cada corrida** (3 en una,
  4 en otra): no se están *extrayendo*, se **inventan de nuevo** cada vez. Como tienen la forma
  correcta (hecho+umbral+fecha+fuente), el gate los valida — no puede distinguir citado de confabulado.
- TENB: `fragility` flipeó 1→0 entre corridas (cambia el hard cap); mérito osciló ±22%.

**Causa raíz (leída en `backend/nucleo/extractor.py`):** al LLM **NO se le pasa el 10-K/10-Q.**
Solo recibe 8 números de EDGAR (revenue, crecimiento, fcf, caja, burn, deuda, margen, precio).
**Todo lo cualitativo** (triggers, desglose orgánico, es_binary, hechos comerciales, ventaja
estructural, bull/bear) el LLM lo saca de su **MEMORIA** de la empresa, no de un documento. El
prompt le pide citar fuente "A" (filing) de algo que **nunca leyó**. Cuando la memoria es
ambigua (COHR = merger II-VI/Coherent → ¿el crecimiento es orgánico?), el modelo **muestrea su
propia incertidumbre** → moneda al aire sobre un HECHO.

## Por qué esto rompe DOS cosas a la vez
1. **Estabilidad:** un booleano muestreado de memoria ambigua cae sobre un ítem binario del
   gate → la decisión flipea. No es ruido en un número, es un veredicto distinto sobre inputs idénticos.
2. **Edge:** es exactamente la **"Versión A"** (opinión/memoria/consenso, con look-ahead de
   training) que el doc 20 **prohíbe**. El extractor actual es lo contrario del edge buscado.
→ **Un solo fix resuelve las dos.**

## Rediseño — 4 capas
### 1. Recuperación de evidencia primaria FRESCA
- Resolver **siempre el filing MÁS RECIENTE** (`get_recent_filings` ordenado por fecha). Nunca
  un doc viejo ni hardcodeado.
- Bajar el texto (`_fetch_text` del `primary_doc`) y **seccionarlo** (MD&A, notas de revenue,
  risk factors; contratos/PO de los 8-K recientes).
- **Alineación temporal:** el texto y los números XBRL deben ser del **MISMO período** — no
  mezclar números de un 10-Q nuevo con texto de un 10-K viejo (contradicción invisible).
### 2. Extracción CITANDO el texto
- Cada hecho / trigger / flag sale con: **valor + pasaje citado (texto exacto) + filing
  (accession) + fecha del filing.**
- **Sin pasaje que lo respalde → el hecho es UNKNOWN** (default conservador), no inventado.
### 3. Verificación de cita (determinista, anti-alucinación)
- Un chequeo **fuera del LLM** confirma que el pasaje citado **existe** en el texto bajado
  (substring normalizado y/o embedding con umbral). Si no existe → se descarta el hecho.
- **Esto es lo que mata la confabulación de triggers:** un trigger sin pasaje real no pasa el
  gate aunque tenga la forma perfecta.
### 4. Fact store versionado + incremental
- Persistir los hechos **fundados**, keyed por **(ticker, accession)**. Tablas `nx_hecho` /
  `nx_ficha_version` ya existen en el ledger.
- Versionar; el update incremental recalcula los resultados dependientes (Art. aprobado).

## FRESHNESS — disciplina de actualización (constraint del operador: "no puede tomar un 10-K viejo")
- **Regla dura:** NUNCA extraer de un filing más viejo que el último disponible.
- Cada hecho lleva la **fecha de su filing**; el sistema siempre conoce la antigüedad del dato.
- **Invalidación por ACCESSION, no por tiempo fijo:** aparece un 10-Q/10-K nuevo → el store de
  ese ticker se marca vencido y se re-extrae. Nunca se sirve un hecho de una accession vieja
  habiendo una nueva. (El job semanal dispara el chequeo de accession, no re-extrae a ciegas.)
- **Política de staleness:** si el último 10-Q/10-K supera N meses (¿4-5?), el set se marca
  **STALE** → los ítems sensibles al tiempo se tratan conservadores y se prioriza re-extracción
  o se degrada a watchlist. Los catalizadores 8-K tienen su propia ventana de recencia
  (ya en `mapa/discovery.py`: caliente 2d / promesa 10d / confirmado 14d).

## Las 3 decisiones de peso (a triangular)
1. **Cuánto texto / cuáles secciones.** Full filing (100+ págs → caro y ruidoso) vs. secciones
   dirigidas (MD&A + notas de revenue + risk factors) vs. retrieval por chunk según el hecho.
   Tradeoff costo / ruido / cobertura.
2. **Verificación de cita.** Substring normalizado (barato, exacto, frágil a paráfrasis) vs.
   embedding (robusto a paráfrasis, más caro, umbral a calibrar) vs. cascada (substring y si
   falla, embedding).
3. **Costo.** De ~$0.13 a ~$0.50–2 por extracción con texto. ¿Aceptable para la re-extracción
   semanal de ~12–30 nombres? ¿Se hace **full solo en deep research** (caras, pocas) y algo
   liviano en el screen?

## Qué existe / qué construir
- **EXISTE:** `edgar._fetch_text` (baja el HTML del filing, trunca a 5MB — construido para
  "los documentos de filing (10-K)") · `get_recent_filings` (lista con `primary_doc` + fecha) ·
  la capa determinista XBRL · el caché de edgar · `nx_hecho`/`nx_ficha_version` (fact store).
- **CONSTRUIR:** resolver+bajar el `primary_doc` del último 10-Q/10-K · seccionador de texto ·
  prompt de extracción-con-cita · **verificador de cita determinista** · invalidación por
  accession · política de staleness.

## Preguntas para triangular
1. ¿La arquitectura (**recuperar fresco → citar → verificar → cachear**) es la correcta, o
   falta/sobra una capa?
2. **FRESHNESS:** ¿invalidación por accession + umbral de staleness de N meses alcanza? ¿Qué N?
   ¿Cómo manejar empresas que reportan tarde, cambian de fiscal year, o cuyo último filing
   relevante es un 8-K entre dos 10-Q?
3. **Verificación de cita:** ¿substring, embedding, o cascada? ¿Cómo evitar penalizar al LLM
   cuando parafrasea correctamente un pasaje real (falso negativo del substring)?
4. **Cuánto texto:** ¿full en deep research y liviano en screen, o siempre secciones dirigidas?
   ¿El seccionado por headings de 10-K es confiable *entre empresas* (formatos distintos)?
5. **El límite honesto:** aún con el texto delante, hay hechos que el filing **no da
   explícitamente** (p. ej. el desglose orgánico exacto de COHR puede no estar). ¿La respuesta
   correcta es **UNKNOWN** (y el gate default-excluye, bajando el recall a cambio de no
   inventar), o hay una vía intermedia legítima?
6. **Versionado:** un fact store por accession guarda todo el histórico. ¿Está bien, o hay que
   podar? ¿Cómo se audita qué cambió entre dos accessions?

Devolvé crítica concreta y priorizada, y donde discrepes tu alternativa. Sin sobreingeniería:
buscamos algo **fundado, fresco, estable y auditable**, implementable con el edgar.py que ya existe.
