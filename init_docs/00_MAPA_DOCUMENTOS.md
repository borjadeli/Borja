# 00 — MAPA DE DOCUMENTOS (leer PRIMERO)

> **Puerta de entrada a `init_docs/`.** Actualizado 2026-10-28 (cambio de dirección **v2**).
>
> ## ★ CANÓNICO v2 (leé ESTO primero)
> BORJA dejó de ser "núcleo determinista que decide" y es un **sistema de PM de IA multiagente** (advisory).
> | Doc | Qué es |
> |-----|--------|
> | **53** `estado_v2` | **ESTADO VIVO** — en qué fase estamos, qué se hizo, qué falta. **Entrada principal.** |
> | **51** `prompt_pm_ia` | DIRECTIVA fundacional de v2 (qué se construye y por qué). |
> | **52** `pm_ia_arquitectura` | ARQUITECTURA + plan por fases + presupuesto + mapa de módulos. |
> | **49** `ablation_pm` | la medición que justifica usar Opus agéntico (por qué el LLM, no el atajo barato). |
> | 54/55 | triangulaciones del comité (54) y de la capa de decisión PM/Auditor/IPS (55). |
> | 56–60 | P1: brief + 2 auditorías externas + convergencia + medición de cobertura XBRL. |
>
> **Regla de oro (v2):** de ESTADO manda **[53]**; de DIRECTIVA **[51]**; de ARQUITECTURA **[52]**. Si un doc
> viejo (abajo) contradice a estos sobre *qué está hecho / qué sigue / quién decide*, **ganan 51/52/53**.
>
> ⚠️ Los docs v1 de abajo (32 estado, 14 pendientes, 34 flujo, 27/28 arquitectura) describen el paradigma
> **"el determinismo decide"**, que v2 **invierte**. Pero el **trabajo intelectual del MÉTODO** (33, owner-FCF,
> reverse underwriting, dilución, T*/burden, falsadores, 31 pre-revenue, 22 motor de evidencia) se
> **CONSERVA como herramienta** que reciben los agentes. Leelos como *método*, no como *quién decide*.

---

## Mapa v1 (historia + herramientas de método conservadas)

> La "regla de oro" de abajo es **v1 y está superada** por 51/52/53 (se deja por trazabilidad).
> **Regla de oro (v1, SUPERADA):** ante cualquier duda de ESTADO manda **[32]**; de MÉTODO manda **[33]**; de
> PENDIENTES manda **[14]**. Si un doc viejo contradice a estos tres, ganan estos tres.

---

## ✅ CANÓNICO-VIGENTE — la lista corta a leer

| Doc | Qué es | Nota |
|-----|--------|------|
| **32** `estado_y_plan` | **FUENTE DE VERDAD VIVA**: estado real + plan por bloques. **Entrada principal.** | Se actualiza cada tajada. |
| **33** `metodo_analisis` | Método de análisis canónico y cerrado (owner-FCF, reverse underwriting, dilución eje aparte, demanda por gates, comparación 2 niveles sin score único). | No re-abrir sin evidencia. |
| **34** `flujo_evaluacion_target` | El *cómo* como UNA superficie: flujo evaluación→ranking→sizing→PM reconciliado (3 pilares + valuación=gate + lexicográfico + tier→cap). Target del refactor. | Resuelve las 3 superficies medio-migradas (doc 14 §G6). |
| **14** `registro_finos_abiertos` | **Registro ÚNICO de pendientes** (§A-E). El worklist. | Todo pendiente vive acá. |
| **29** `carril_especulativo` | Cómo entra la opcionalidad a la cartera (gate + caps + presupuesto 10→25%). | **Reemplazó el viejo "sleeve 2%".** |
| **27** `arquitectura_final_triangulada` | Arquitectura end-to-end (flujo 12 etapas, decisiones grandes). | ⚠️ el "sleeve 2%" de §7 quedó superado por [29]. |
| **28** `compiler_valuacion_buildable` | Valuación: compiler, tabla de retención/haircuts, invariantes, falsador CAGR, option ledger. | ⚠️ §4 "sleeve 2%" superado por [29] (banner puesto). |
| **31** `analisis_pre_revenue` | Reverse underwriting / burden para pre-revenue (owner-FCF, FCFE_req). | Implementado en `pre_revenue.py`. |
| **22** `spec_consolidado_motor_evidencia` | Spec del motor de evidencia citado (taxonomía de soporte, pipeline, fact model, vigencia). | ⚠️ §7bis (generadora) y §8bis (tier de magnitud) evolucionaron en la implementación. |
| **30** `extraccion_datos_hardening` | Plan técnico de extracción XBRL (Fase 1 wins baratos · Fase 2 Arelle). | Fase 1 PARCIAL (ver [14] §E); Fase 2 diferida. |

**Si venís a entender el sistema hoy:** leé **32** (estado) → **33** (método) → **14** (pendientes).
Para valuación: **27/28/31**. Para el motor de evidencia: **22/30**. Para opcionalidad: **29**.

---

## 🟡 SUPERADO — NO leer para el estado/método vigente (quedó viejo)

| Doc | Era | Superado por | Por qué |
|-----|-----|--------------|---------|
| **18** `mapa_estado` | Foto de estado (2026-07) | **[32]** | Cifras viejas ("78 tests", "PM no existe"=falso, "ledger fiel"=no implementado). |
| **19** `revision_analisis` | Auditoría del análisis (2026-07) | **[32] §8 + [14] §E** | Los problemas que planteó (bull/bear inestable, asimetría inflada) **ya se resolvieron**. Fue el insumo que generó [14] §D/E. |
| **26** `framework_evaluacion_ranking` | Framework de ranking v3 | **[33]** | Absorbido/refinado en 33 (3-4 pilares, valuación=gate no pilar, ranking lexicográfico). |
| **21** `extractor_motor_evidencia` | Rediseño del extractor | **[22]** | Subsumido y refinado en el spec consolidado. |
| **23** `estandar_demanda_confirmada` | Crux AAOI/Amazon (didáctico) | **[33] gates de demanda** | Resolvió un caso; formalizado en los gates G1-G4 de 33. Lectura didáctica, no operativa. |

---

## 🏗️ ANDAMIAJE DEL REDISEÑO — diseño que se está implementando (no leer para estado)

| Doc | Qué es | Estado de implementación |
|-----|--------|--------------------------|
| **13** `constitucion_sistema` | Constitución (10 artículos): límites determinista/PM, estados, evidencia. Guía de diseño. | Se implementa por detrás. ⚠️ "cero tests" (art. 9) es viejo (hoy 276). |
| **16** `ledger_etapa2` | Diseño del ledger fiel (tablas `nx_*`, append-only, doble P&L). | **Diseño vigente, NO implementado** (el paper sigue en `libro.json` de fracciones). Etapa 2. |
| **17** `etapa4_ficha_rica` | Diseño de la ficha rica (deep research, bull/bear disciplinado, durabilidad). | Parcial: compiler/valuación hecho; falta enchufe + dashboard. |
| **20** `mapa_motor_evidencia` | Tesis del EDGE (IA detecta cuellos pre-consenso). | **Hipótesis a demostrar** (el propio 22 §10 lo admite), no premisa probada. |
| **24** `sistema_ensamblado` | Pre-revisión del conjunto de piezas del motor. | Superado por **[25]** (que respondió sus preguntas). |

---

## 📜 HISTÓRICO / DIAGNÓSTICO — foto de un momento (contexto, no referencia viva)

| Doc | Qué es | Vigencia |
|-----|--------|----------|
| **12** `diagnostico_estado_real` | Diagnóstico código-real vs objetivo + plan 5 etapas (2026-07). | Panorama aún **útil**; [32] lo retomó y agregó el "3er stack desenchufado". |
| **15** `reanclaje_codigo` | Análisis de brecha doc↔código (2026-07). | Los huecos que marcó ya están en [32] §7 / [14]. |
| **25** `plan_endurecimiento_integracion` | Plan faseado A-E de endurecimiento del motor. | **PARCIAL**: su Bloque de honestidad (reason codes/CONTESTED/frescura) vive en [32] §5 Bloque 3; **su replay/canary/cutover (Fases D/E) [32] lo declara SOBREINGENIERÍA para un sistema advisory.** Sus tablas (evidence_cap, harness A-H) son pendientes reales → [14]. |

---

## Notas de mantenimiento
- **Los docs 🟡 SUPERADO / 🏗️ ANDAMIAJE / 📜 HISTÓRICO están en `init_docs/archivo/`** (movidos 2026-08-13).
  El nivel de arriba muestra SOLO los 9 canónicos + este mapa. Los números de las tablas de arriba son los
  mismos; el archivo vive en `archivo/NN_*.md`.
- Este mapa se actualiza cuando un doc cambia de estado (se supera, se implementa, se archiva).
- Los `.docx` originales (01/02/03 sistema/mvp/agentes) y los 04/11 citados en CLAUDE.md **no están en el repo**; el código + estos docs son la fuente de verdad de facto.
