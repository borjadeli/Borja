# 54 — Triangulación: el comité de agentes de research (v2 Fase 3)

> **Para converger con 2+ IAs antes de codear** (método del proyecto: esquema cerrado primero). Este doc
> propone el diseño del comité de agentes LLM y lista las **decisiones abiertas** donde quiero criterio
> externo. Contexto: doc 51 (directiva), doc 52 (arquitectura/plan), doc 49 (ablation: el valor es Opus
> investigando agénticamente), doc 53 (estado vivo). Fecha: 2026-10-26.

## 0. Qué ya está construido (no se re-discute)
- **Modelos (verificados en vivo):** Opus 5.5 ($4/$20), Sonnet 5.5 ($2/$10), Haiku 5.5 ($0.10/$0.50);
  Batch −50%; prompt caching: lecturas al **5%** del input en Opus/Sonnet 5.5. SDK anthropic 2.3.0.
- **Contratos de datos** (`backend/agentes/`): `provenance.DataPoint` (fuente, `known_at` point-in-time,
  kind=original/derived/estimate/interpretation) + `DataPack`; `schemas.py` con los 8 outputs pydantic
  (Macro, Triage, Dossier con bull/bear independientes + falsador fechado, Bear, Verificador pass/fail, PM,
  Auditor) + `AgentMeta` (modelo, costo, tokens, web_searches).
- **Data pack assembler** (`data_pack.py`): capa de mercado con procedencia; arquitectura de fuentes
  enchufables para las calculadoras (owner-FCF, dilución, g_D, T*, burden).
- **Universo + mapa** poblados en `nx_*` (135 empresas small/mid filtradas por IPS, 142 cuellos).
- **IPS parcial:** peso máx 20%/nombre · market cap $150M–$60B · **presupuesto $40/mes** · red flags de
  supervivencia = alerta (el PM resuelve con OK del verificador, no bloqueo duro).

## 1. Diseño propuesto (a converger)

### 1.1 Agent base (`backend/agentes/base.py`, adapta `agents/base.py`+`llm.py` del Sistema-Quant)
Un `Agente` encapsula: prompt versionado (`prompts/<agente>_vN.md`) → llamada LLM (vía `services/llm.py`,
que ya trae costo/tokens/caché/reintentos) → **parse a pydantic** → `AgentMeta` con costo. Maneja
`pause_turn` (tool loop server-side), errores y **costo parcial** (si falla a mitad, se registra lo gastado).

### 1.2 Los agentes
| Agente | Modelo | Web | Input | Output | Cadencia |
|---|---|---|---|---|---|
| **Triage** | Haiku 5.5 | no | universo elegible + señales baratas (market cap, eventos, data pack mínimo) | `TriageDecision[]` | semanal, 1 llamada batcheada sobre todo el universo |
| **Macro** | Opus 5.5 | sí | estado de ciclo IA/energía/commodities/tasas + mapa de cuellos | `MacroMemo` | semanal |
| **Analista** | Opus 5.5 | sí (agéntico) | data pack + calculadoras + contexto de cuello + memo macro | `Dossier` | ~N nombres/semana (triageados) |
| **Bear** | Sonnet 5.5 | sí | el Dossier | `BearAttack` (el analista replica 1 vez) | por nombre analizado |
| **Verificador** | Sonnet 5.5 | — | Dossier + fact store | `VerificationReport` (pass/fail) | por nombre analizado |

### 1.3 Orquestador (`backend/agentes/orquestador.py`)
Flujo semanal: Macro → Triage (todo el universo) → selecciona top-N por prioridad×incertidumbre **hasta
agotar presupuesto** (posiciones en cartera + nombres con evento entran siempre) → por cada seleccionado:
Analista → Bear → (réplica) → Verificador. **Reutilización por hash:** si el data pack + hechos no
cambiaron desde el último Dossier verificado y no hubo evento, se reutiliza (no se re-gasta LLM).
**Presupuesto $40/mes = freno duro:** el orquestador deriva N y corta.

### 1.4 Harness de tests (`ScriptedLLM`, adapta el del Sistema-Quant)
Un fake de `services/llm.py` que devuelve respuestas guionadas → tests de cada agente y del orquestador
**sin pegarle a la API**. El `AgentMeta`/costo se testea con números fijos.

## 2. ⭐ DECISIONES ABIERTAS (acá quiero convergencia)

1. **Parse: ¿structured outputs nativo o free-text + parse?** 5.5 soporta `output_config.format` /
   strict tools (JSON schema-válido garantizado). Para Triage/Bear/Verificador parece ideal. **Para el
   Analista es dudoso:** es agéntico con `web_search` (tool loop); forzar JSON schema puede chocar con el
   loop de búsqueda o recortar el razonamiento (que es EL producto, doc 49). ¿Analista = razona+busca libre
   y emite el Dossier estructurado al final en la misma llamada, o un 2º pase barato que estructura el texto?

2. **Mecánica del Analista (la pieza cara y valiosa).** (a) ¿Una sola llamada agéntica Opus 5.5 + `web_search_20260209`
   (dynamic filtering) con `max_uses` acotado y luego el Dossier? ¿`effort` = `medium` (default 5.5) o `high`?
   (b) **Caché:** la parte común (IPS + mapa del cuello + memo macro + rúbrica) se cachea al 5% — ¿conviene
   un prefijo fijo compartido entre todos los análisis de la semana? (c) ¿Tope de tokens/costo por nombre
   como `task_budget`?

3. **Triage: ¿1 llamada batcheada o por nombre?** Propongo 1 llamada Haiku que rankea todo el universo
   (barato) con prioridad×incertidumbre. ¿Alcanza la señal con un data pack mínimo + eventos, o hace falta
   algo más por nombre? ¿Cómo se fuerzan las posiciones + nombres con evento sin gastar?

4. **Bear ↔ Analista (1 vuelta).** ¿El Bear ve solo el Dossier (contexto independiente, anti-sesgo) o
   también el data pack? ¿El Verificador corre antes o después de la réplica del analista?

5. **Verificador: ¿determinista-primero o full-LLM?** Propongo: chequeo determinista de cada `Evidence`
   (¿la URL resuelve? ¿la cita aparece en el fact store / vía `web_fetch`? ¿`company_statement` marcado
   como NO-verificado?) + LLM solo para consistencia narrativa↔números. ¿Es suficiente? ¿`fail` si hay
   ≥1 afirmación factual sin fuente que sostiene la tesis central?

6. **Reutilización por hash + presupuesto.** ¿Con qué se hashea la validez de un Dossier (data pack +
   set de hechos con `known_at` + ausencia de evento)? ¿El freno de $40/mes se aplica como N máx de
   análisis profundos/semana derivado de un costo/nombre medido, o como acumulador duro que corta a mitad
   de la semana? ¿Batch API para Triage/re-extracción (no urgente) y el Analista agéntico queda fuera de
   batch (es interactivo)?

7. **Red flags de supervivencia (alerta, no bloqueo).** ¿Cómo se implementa el "el PM resuelve por escrito
   con OK del verificador"? ¿El Verificador emite un flag de supervivencia que el PM DEBE responder en su
   `PMAccion` antes de comprometer capital?

8. **Agent base: ¿extender `services/llm.py` o `agentes/base.py` nuevo?** `llm.py` ya tiene
   `call_llm_json` + `call_llm_json_with_web_search` + costo + `_persistir_llm_call`. ¿Reusar eso como
   capa de transporte y poner la lógica de agente (prompt+schema+parse) encima, o un base propio?

## 3. Lo que NO se re-abre
El paradigma (determinismo informa/limita, LLM decide — doc 51), los modelos, el IPS parcial, los contratos
pydantic ya definidos, y que el Analista es Opus+web agéntico (doc 49). La triangulación es sobre la
**mecánica de implementación**, no sobre quién decide.
