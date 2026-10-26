# 53 — BORJA v2: estado vivo

> **Fuente viva del estado.** Reemplaza al doc 32 (que describe el estado v1). Si algo acá contradice a un
> doc más viejo sobre *qué está hecho / qué sigue*, gana este. Directiva: doc 51 · arquitectura/plan: doc 52.
> Última actualización: **2026-10-26**.

## Dónde estamos
**FASE 1 (Consolidación) — en curso.** El cambio de dirección v2 está decidido (doc 51) y la arquitectura +
plan están cerrados (doc 52). Arrancó la ejecución por fases. Rama de trabajo: `destete-v2-fase1`.

## Decisiones del operador (cerradas)
- **Dirección:** PM de IA multiagente; el determinismo informa/limita, no decide (doc 51/52).
- **IPS (parcial):** peso máx/nombre **20%** · rango market cap **$150M–$60B** · resto = defaults del doc 52 §4
  hasta que el operador los edite (máx 12 posiciones, 30%/sector, 35%/cuello, ADV $3M, caja 0–100%, 2 ops/sem).
- **Presupuesto LLM:** **$40/mes** (régimen disciplinado: triage sobre todo el universo + ~2-4 análisis
  profundos/semana; posiciones se monitorean barato, al comité caro solo por evento). El ingeniero avisa si
  hace falta subir a ~$60-80/mes para que funcione bien.
- **Red flags de supervivencia:** alerta que el PM resuelve por escrito con OK del verificador (no bloqueo duro).
- **Ciberseguridad:** parte del universo amplio, sin prioridad de vertical.
- **Modelos (verificados en vivo 2026-10-26):** familia 5.5 — Opus 5.5 (Analista/PM/Auditor/Macro),
  Sonnet 5.5 (Bear/Verificador/Curator), Haiku 5.5 (Triage); Fable 5.1 opción máx. Configurable por agente.

## Hecho en Fase 1
- ✅ **Cortado el gasto LLM del v3:** `scheduler.py` — desactivados `paper_ciclo`, `paper_reextraccion` y
  `paper_pm` (el Opus+web semanal sobre todo el universo). Quedan solo snapshot/mtm ($0) sobre el libro congelado.
- ✅ **Paper v3 congelado:** `data/_archivo_v3/libro_v3_congelado_20261026.json` + `libro_pm_v3_congelado_…`.
- ✅ **Huérfanos archivados** → `backend/_archivo/`: `pipeline.py`, `sparring.py`, `discovery.py` (+ su test).
- ✅ **Suite en verde:** `pytest.ini` acota la colección a `tests/`; **465 passed**. App importa limpio.
- ✅ **Docs reescritos:** `CLAUDE.md`, `CONTEXT.md`, este `53`.

## Pendiente / acciones abiertas
- 🔴 **ACCIÓN DEL OPERADOR — reiniciar el host** para que el apagado de crons tome efecto (la consola está
  sandboxeada, no puede): `sudo systemctl restart borja` en el servidor, **o** `POST /admin/restart` desde el
  dashboard (hace `os._exit(0)`; systemd respawnea con el código nuevo). Hasta entonces `paper_pm` dispara el
  próximo domingo 19:30 ET (~$17 de gasto evitable).
- ⏳ Commit + PR de Fase 1 (requiere remoto git → GitHub del operador).

## Diferido con criterio (no se hace en Fase 1)
- **Move físico del núcleo de decisión v3** (flujo/selector/sizing_final/cartera_celdas/carril/escalera/
  challenger) → **Fase 4**. Razón: `flujo.EntradaEmpresa` lo usa el motor de evidencia CONSERVADO y
  `paper_trader` (que se reescribe en Fase 4) importa esos módulos. Sacarlos ahora rompe el arranque. En Fase 1
  quedan **neutralizados** (no corren).
- **Upgrade del SDK anthropic** (0.39.0 → versión con 5.5 + batch + caché) → **inicio de Fase 3**, justo antes
  de construir los agentes (hoy no llamamos a 5.5; upgradear ahora solo arriesga `services/llm.py` sin beneficio).

## Plan por fases (resumen — detalle en doc 52 §6)
- **Fase 0** — Plan. ✅ (docs 51/52).
- **Fase 1** — Consolidación (congelar v3, archivar, docs). ◐ en curso.
- **Fase 2** — Universo + mapa (importar Sistema Quant, poblar `nx_nodo`, Map Curator + cola de aprobación).
- **Fase 3** — Agentes de research (data pack con procedencia; Macro/Triage/Analista/Bear/Verificador; schemas;
  orquestador con presupuesto + reutilización por hash; smoke test real sobre 5 nombres). SDK upgrade acá.
- **Fase 4** — PM + Auditor + IPS en código + ledger; reescritura de `paper_trader`; el paper nuevo opera.
- **Fase 5** — Evaluación: carteras sombra + duelo de 25 nombres (pipeline vs "Opus+web solo") + Brier.
- **Fase 6** (opcional) — torneo de PMs.

## Repo Sistema-Quant (para Fase 2)
Público, clonado y verificado (2026-10-26): `https://github.com/borjadeli/Sistema-Quant`. Piezas a traer
confirmadas presentes (agents/map, funnel, schemas, provenance, data/universe ~246 empresas). En Fase 2 se
decide si se clona de forma persistente en el server para que el import sea reproducible.
