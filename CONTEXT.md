# BORJA — Contexto del sistema (orientación para asistentes)

> Mapa del sistema, estado actual y por dónde entrar — para quien explora BORJA
> (incluida la consola Claude Code embebida). El **código y los `init_docs/` son la
> fuente de verdad**; este doc orienta, no reemplaza.

> ### ★ EMPEZÁ ACÁ (índice de la documentación)
> BORJA está en un **cambio de dirección (v2, 2026-10-26)**: deja de ser "núcleo determinista que decide"
> y pasa a ser un **sistema de PM de IA multiagente**. Canónico vigente:
> - **doc 51** `prompt_pm_ia` — la directiva fundacional de v2 (qué se construye y por qué).
> - **doc 52** `pm_ia_arquitectura` — arquitectura detallada + plan por fases + presupuesto + mapa de módulos.
> - **doc 53** `estado_v2` — **estado vivo** (en qué fase estamos, qué se hizo, qué falta). **Leé esto primero.**
> - **doc 49** `ablation_pm` — la medición que justifica usar LLM agéntico para el análisis.
> - `init_docs/00_MAPA_DOCUMENTOS.md` — qué docs viejos siguen vigentes y cuáles son historia.
>
> ⚠️ Los docs **32/33/39** describen el paradigma **v1** ("el determinismo decide"). En v2 ese paradigma se
> **invierte** en lo que respecta a *quién decide* (ahora decide el LLM). El *trabajo intelectual* de esos
> docs (owner-FCF, dilución, reverse-DCF/T*, burden, arquetipos, falsadores) se **conserva como herramienta**
> que reciben los agentes. Si un doc v1 contradice a 51/52/53 sobre quién decide, ganan 51/52/53.

## 1. Qué es BORJA
Sistema quant para analizar/operar **small & mid caps de "industrias del futuro"** (AI infra, energía/
nuclear, defensa, commodities/minerales, espacio, robótica, healthcare/biotech, fotónica, semis). Sector de
mayor riesgo, elegido a propósito: donde un sistema disciplinado genera más diferencial (tesis **power-law**).
**Modo de uso: ADVISORY** (asesora; el humano ejecuta). Hay **paper trading** autónomo que valida el método
con capital simulado. Filosofía: **disciplina sobre actividad** — se prefieren slots vacíos a forzar entradas.

## 2. El cambio de dirección v2 (quién decide)
> **El determinismo informa y limita; la IA decide.** Datos, cálculos, detección de eventos, presupuesto y
> los límites de política (IPS) son deterministas. Qué comprar/vender, cuánto y cuándo lo deciden **agentes
> LLM**, con un PM-LLM como decisor final y un auditor independiente que lo cuestiona.
> **El determinismo NO elige nombres ni tamaños.**

Base empírica: el **doc 49** midió que el valor es **Opus investigando agénticamente** (formula la búsqueda,
lee, sigue el hilo, razona mientras busca); los atajos baratos colapsan. El determinismo se queda con lo que
el LLM no hace mejor: **datos + límites + triage**.

## 3. Arquitectura objetivo (5 capas) — detalle en doc 52
- **A — Datos y calculadoras** (determinista, informa): EDGAR + market + fact store citado; calculadoras
  (owner-FCF, dilución, runway, CRR, g_D, reverse-DCF/T*, burden). Todo con fuente + `known_at` + tipo. Son
  **inputs** del data pack, nunca veredicto. (`backend/services/`, `backend/nucleo/` calculadoras + motor de evidencia.)
- **B — IPS** (`config/ips.yaml`, a construir): el único lugar donde el código manda, con reglas del operador
  (máx posiciones, peso máx/nombre **20%**, caps sector/cuello, rango market cap **$150M–$60B**, liquidez,
  caja, máx ops/semana, presupuesto LLM **$40/mes**). Si el PM viola el IPS, el código rechaza y devuelve.
- **C — Agentes** (razonan y deciden): Macro · Map Curator+Discovery · Triage · **Analista** (Opus+web
  agéntico) · Bear/Red-team · Verificador · **PM** · Auditor. Prompts versionados, salida pydantic, costo
  registrado, fuentes citadas.
- **D — Monitoreo por eventos** (el determinismo detecta, el PM decide): filings / precio / red flags /
  falsadores que vencen / 5 vías de `salida.py` → abren una **revisión** del nombre. Las 5 vías son **alertas**,
  no ventas automáticas.
- **E — Ledger y evaluación**: ledger append-only + hit-rate de falsadores + Brier + P&L; **carteras sombra**
  desde el día 1 (equal-weight, "Opus+web solo", ETFs temáticos).

## 4. Estado actual — ver doc 53 (vivo)
**DESTETE v2 Fase 1 en curso (2026-10-26).** Hecho: cortado el gasto LLM del sistema v3 (jobs `paper_ciclo`/
`paper_reextraccion`/`paper_pm` desactivados en `scheduler.py`); paper v3 **congelado** (libros en
`data/_archivo_v3/`); huérfanos (`pipeline.py`, `sparring.py`, `discovery.py`) movidos a `backend/_archivo/`;
suite en verde (465 tests). Pendiente de Fase 1: reescritura de docs (este archivo), commit + PR. Diferido con
criterio: move físico del núcleo de decisión v3 → **Fase 4**; upgrade del SDK anthropic → **inicio de Fase 3**.

## 5. Mapa del código
- `backend/nucleo/` — **motor de evidencia + calculadoras CONSERVADOS** (fact_store, extractor_citado,
  retrieval, gold_retrieval, valuacion_reverse, crecimiento, pre_revenue, dilucion, capital_raise_risk,
  sizing_burden, juicio_llm) **+ el camino de decisión v3 NEUTRALIZADO** (flujo, selector, sizing_final,
  cartera_celdas, carril, escalera, ranking*; ya no corre, se archiva físicamente en Fase 4).
- `backend/mapa/` — Bloque B: mapa de cuellos (nodos, transiciones, brújula). `discovery.py` → archivado
  (lo reemplaza el del Sistema Quant en Fase 2).
- `backend/seleccion/` — paper_trader (se **reescribe** en Fase 4), paper_pnl, jobs, pm_run, challenger,
  monitor, presupuesto, watchlist, universo.
- `backend/services/` — edgar.py, market_data, precio_base, news, **llm.py** (wrapper Anthropic; SDK a
  upgradear en Fase 3), calculators, mailer.
- `backend/ledger/`, `backend/ingreso/`, `backend/eval/` — ledger fiel (`nx_*`), etapa de entrada, harness.
- `backend/main.py` (FastAPI), `backend/ui.py` (Jinja2), `backend/consola.py` (esta consola),
  `backend/scheduler.py`, `backend/panic.py` (kill switch).
- `backend/_archivo/` — código v3 retirado (no se importa; no borrar hasta cerrar Fase 2).
- `frontend/templates/` (Jinja2 + Tailwind, estilo Banking/Finance), `prompts/`, `data/` (SQLite + JSON,
  gitignored), `ops/` (scripts `.venv/bin/python -m ops.<x>`), `tests/` (pytest, 465), `init_docs/` (spec).

## 6. Datos, LLM y cómo correr
- **Datos:** yfinance (`curl_cffi impersonate=chrome`), EDGAR/SEC, RSS. FMP/Polygon/Benzinga diferidas.
- **LLM:** SDK Anthropic (`backend/services/llm.py`). Modelos vigentes verificados vía `/v1/models` (2026-10-26):
  familia **5.5** — `claude-opus-5-5` ($4/$20, Analista/PM/Auditor/Macro), `claude-sonnet-5-5` ($2/$10,
  Bear/Verificador/Curator), `claude-haiku-5-5` ($0.10/$0.50, Triage); `claude-fable-5-1` ($10/$50, máx
  capacidad). Palancas de costo: Batch API −50% + prompt caching (lecturas al 5% en Opus/Sonnet 5.5).
  ⚠️ El SDK instalado (0.39.0) es viejo para 5.5 → upgrade en Fase 3.
- **Correr:** `uvicorn backend.main:app`. Tests: `.venv/bin/python -m pytest` (colección acotada a `tests/`).
- **Deploy:** systemd `borja.service` (uvicorn :4151) → Cloudflare Tunnel → borja.i-314.com. **Esta consola
  está sandboxeada**: no ve ni reinicia el proceso del host. Cambios en rutas/jobs Python requieren reiniciar
  el host (`sudo systemctl restart borja` en el servidor, o `POST /admin/restart` desde el dashboard, que hace
  `os._exit(0)` y systemd respawnea con el código nuevo). Templates Jinja se leen en vivo.
