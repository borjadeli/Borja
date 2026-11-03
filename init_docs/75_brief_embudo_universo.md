# 75 — Brief para triangular: el EMBUDO de priorización + el UNIVERSO (¿tope de $60B?)

> El smoke Tier B cerró bien (método OK, 2 bugs arreglados). El **dry-run del universo** (`--cupo 6`) promovió
> **30 nombres a deep (~$20)**, de los cuales **21 "forzados por evento"**. Investigando salieron 3 cuestiones
> de diseño del embudo/universo. Estamos en **congelamiento de método** (r5) → se triangula antes de tocar.
> Para mandar a 2 IAs independientes.

## 0. De dónde sale el universo de hoy (HECHO, no opinión)

- `nx_empresa` (135 activas) se pobló desde `backend/seed/sistema_quant/universe/companies.yaml` (v0.1,
  2026-10-21), importado del repo público **borjadeli/Sistema-Quant** (commit 95f0f6e) el 2026-10-26. ~245
  empresas en el YAML.
- Es una lista **curada a mano por el operador**, clasificada por **FUNCIÓN INDUSTRIAL** (nodos de cuello del
  mapa AI/energía/commodities), NO por sector bursátil ni por screening de market cap/liquidez.
- Incluye desde **gigantes** (NVDA ~$3T, GOOG, AVGO, AMD) hasta **small caps** — a propósito: el mapa modela
  los cuellos y los gigantes son jugadores de cuello. `seed: true` marca el grupo inicial de validación.
- Market cap / precio / liquidez NO están en el seed: se traen por API (ingest) con fuente y fecha.

## 1. El embudo promueve casi todo por "evento" (sin filtro de calidad)

`seleccionar_para_deep` (doc 64) manda a deep: **posición** · **evento fuerte** · **precio fuerte** ·
**earnings top-N** · **cupo** (los mejores nuevos por prioridad de cuello). Hallazgos del dry-run:

- **`es_evento_fuerte` incluye el 8-K ítem 2.02 (earnings/resultados).** La ventana de monitoreo es de 30 días.
  Estamos en **temporada de earnings** → casi todas reportaron → casi todas disparan "evento fuerte" (21/30).
- Eso **contradice la regla de earnings del propio operador** (doc 64): *"earnings deep solo en los que están
  en cartera y los mejores candidatos; el resto post-earnings"*. Un earnings CONSUMADO de un no-posición
  entra por "evento fuerte", salteándose esa regla.
- **El carril "forzado" NO tiene ranking de calidad NI tope.** Cualquier evento entra. El ranking por
  prioridad de cuello + el `cupo` solo aplican al carril "nunca analizados sin trigger".

## 2. No filtra por market cap/liquidez del IPS ANTES del deep

- En los 21 forzados está **GOOG** (~$2T). Se analizaría (~$0,68 de Analista) y recién el **gate del IPS** lo
  rechaza por tamaño ($150M–$60B). Plata tirada en nombres que no se pueden comprar.
- El filtro de admisibilidad del IPS (market cap, liquidez) vive en el gate final, no en el embudo.

## 3. (ESTRATÉGICO) ¿Tiene sentido el tope de $60B?

La tesis fundacional (doc 51/CLAUDE.md): **small/mid caps de industrias del futuro, power-law** — el
diferencial está donde un sistema disciplinado agrega más (nombres poco cubiertos, asimétricos). Eso sugiere
SÍ un tope de tamaño. **Pero** el universo curado incluye gigantes a propósito, y el IPS los rechaza. Tensión.

**Preguntas a triangular (decisión del operador + juicio de las IAs):**
- a. ¿El tope de $60B es el correcto para la tesis power-law, o deja fuera asimetrías reales (p.ej. un nombre
  de $70-100B que todavía puede multiplicar)? ¿Debería ser un cap distinto, o un rango por arquetipo?
- b. ¿Qué hacemos con los gigantes (NVDA/GOOG/AVGO) que están en el mapa?
  - (i) salen del universo ANALIZABLE y quedan solo como **contexto del mapa** (quién depende de quién);
  - (ii) se analizan pero no se compran (hoy = waste);
  - (iii) se vuelven comprables con un **sleeve aparte** (exposición a los enablers), separado del power-law.
- c. ¿El universo **curado a mano** (~245 nombres, oct-2026) es la base correcta, o necesita un
  **screening/refresh sistemático** (reglas de inclusión, actualización periódica, de-listing de los que
  dejaron de ser cuello)?

## 4. Lo que proponemos (a validar antes de codear)

- **Embudo (fix de disciplina, con tests):** (1) sacar el 8-K 2.02 (earnings rutinario) de "evento fuerte" →
  que vaya por el carril de earnings (respeta la regla del operador); mantener como evento fuerte lo que SÍ es
  cambio material (red flags 4.02/4.01/3.01, dilución S-1/S-3/424B5, M&A 2.01, management 5.02, activismo
  SC 13D). (2) Aplicar el filtro de market cap/liquidez del IPS **en el embudo**, antes del deep. (3) Opcional:
  rankear + capear el carril forzado por prioridad de cuello.
  - Impacto estimado: los 30 deeps bajan a ~10-15 → corrida real ~$7-10, más limpia.
- **Universo / $60B:** es estrategia, no código → se decide con la triangulación.

## 5. Principio rector (no se toca)

El determinismo **informa y limita**; el PM-LLM decide nombres y tamaños. El mapa/universo es el INPUT, el
embudo PRIORIZA (barato, determinista), el IPS CAPEA. Nada acá le saca la decisión al PM; se discute qué entra
al análisis y qué se puede comprar.
