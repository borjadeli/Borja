# BORJA — Contexto del sistema (orientación para asistentes)

> Mapa del sistema, estado actual y por dónde entrar — para quien explora BORJA
> (incluida la consola Claude Code embebida). El **código y los `init_docs/` son la
> fuente de verdad** para umbrales y detalles exactos; este doc orienta, no reemplaza.

> ### ★ EMPEZÁ ACÁ (índice de la documentación)
> `init_docs/` tiene ~22 documentos; muchos son andamiaje o quedaron superados. **Antes de leer o citar
> cualquiera, mirá `init_docs/00_MAPA_DOCUMENTOS.md`** — dice qué está vigente y qué es historia.
> **Canónico:** estado → **doc 32** `estado_y_plan` (fuente viva) · método → **doc 33** · pendientes →
> **doc 14** · opcionalidad → **doc 29** (reemplazó el "sleeve 2%") · valuación → **27/28/31** · motor de
> evidencia → **22/30**. Si un doc viejo contradice a 32/33/14, ganan 32/33/14.
> ⚠️ La **§2 de acá abajo está fechada 2026-07-23 y quedó vieja** (subestima lo construido); para el estado
> real leé doc 32.

## 1. Qué es BORJA
Sistema quant para analizar/operar **small & mid caps de "industrias del futuro"**
(AI infra, energía/nuclear, defensa, healthcare tech, robótica, fotónica…). Es el sector
de mayor riesgo, elegido a propósito: es donde un sistema disciplinado puede generar más
diferencial. Filosofía operativa: **disciplina sobre actividad** — se prefieren slots
vacíos a forzar entradas; no se relajan umbrales sin evidencia documentada.

## 2. Estado actual (al 2026-07-23)
- **Migración en curso:** el **sistema viejo** (score 0-10 + pipeline de agentes) convive
  con un **núcleo determinista nuevo** que ya opera. El núcleo nuevo corre **en PAPER**
  (capital simulado, libro propio, sin confirmación humana).
- **Dashboard:** home `/` = núcleo nuevo (equity / P&L / curva vs SPY / posiciones);
  el sistema viejo está en `/legacy`; `/rediseno` = vista de sombra; `/consola` = esta terminal.
- **Cartera paper (núcleo nuevo):** 12 posiciones — NABL, S, TENB, VRNS, RBRK, MP, LEU,
  VCYT, CLS, UEC, TER, COHR. Equity ≈ **$107.993 sobre base $100K (+7,99%)**,
  **alpha vs SPY +6,06%** (cierre 22-jul-2026). Libro estable desde el 3-jul (hold disciplinado).
- **Autónomo:** un scheduler diario opera el paper, marca P&L y arma la curva, sin intervención.

## 3. Mapa del código
- `backend/agents/` — **sistema viejo**: pipeline tipo mesa de inversión
  (Descubrimiento → Analista → Juez → Mapa sectorial → Recomendación) + anti-fraude,
  red flags, capital-raise risk (CRR), revalidación, transición de fase macro, reporte
  semanal y script nocturno; orquestado por un dispatcher de eventos.
- `backend/nucleo/` — **núcleo determinista nuevo** (el corazón). Ver §4.
- `backend/mapa/` — Bloque B: mapa sectorial de cuellos de botella (nodos, transiciones,
  brújula sectorial, discovery).
- `backend/seleccion/` — Bloque C: PM, watchlist viva, sparring (2º LLM adversarial),
  monitor, presupuesto, **paper_trader** + **paper_pnl** (P&L/MtM) + **jobs** (scheduler del paper).
- `backend/main.py` (FastAPI: API JSON + health), `backend/ui.py` (vistas server-side),
  `backend/consola.py` (esta consola).
- `frontend/templates/` — Jinja2 + Tailwind (estilo Banking/Finance). `prompts/` — prompts LLM.
- `data/` — `borja.db` (SQLite), `nucleo_paper/libro.json` (libro paper), `nucleo_hechos/`
  (hechos LLM cacheados). `ops/` — scripts + systemd. `init_docs/` — spec canónica.

## 4. El núcleo determinista (`backend/nucleo/`)
El LLM deja de decidir y pasa a **traer hechos fechados**; la decisión es 100% determinista.
Flujo: **arquetipo → gate de evidencia → mérito (Quality × Asimetría) → sizing → 5 vías de
salida → re-gate.**
- **Arquetipo** (`arquetipo.py`): Madura / Growth / Tracción / Pre-revenue / Binary.
- **Gate** (`gate.py`): vara de evidencia (U1/U2 + ítems por dimensión); "todavía no" si no pasa.
- **Quality** (`quality.py`): tier ordinal 1-4 derivado de hechos (NO un score 0-10 nuevo).
- **Sizing** (`sizing.py` + `fragility.py`): Hard Cap = min() de caps + clamp por asimetría;
  Fragility Score → caps adicionales + "cubo residual-cero".
- **Selector** (`selector.py`): rankea por mérito normalizado (top-N), despliega hacia
  **piso 70% / techo 100%**, con piso por posición, **máx 12 posiciones** y caps por sector/driver.
- **Salidas** (`salida.py`): 5 vías (triggers/stop de progreso · CRR-crítico · ≥3 red flags ·
  asimetría muerta · monitor mecánico) con precedencia gov → CRR → vía1 → vía4 → vía5.
- Orquesta `flujo.py` (`evaluar_empresa`, `armar_cartera`); estado en `estado.py`; hechos en
  `extractor.py` (EDGAR+market + capa LLM). Umbrales exactos: código + `init_docs/11_nucleo_consolidado_v3`.

## 5. Paper trading + dashboard
- `paper_trader.py` opera `data/nucleo_paper/libro.json` de forma determinista (sin LLM en la
  decisión de capital): salida primero, luego entrada por mérito.
- `paper_pnl.py` marca a mercado (equity, P&L, curva vs SPY normalizada). La home lee esto por request.
- Scheduler (`backend/seleccion/jobs.py` + `backend/scheduler.py`): `paper_ciclo`
  (L-V 16:40 ET, compra/vende, $0 LLM), `paper_snapshot` (16:45), `paper_mtm_intraday`
  (cada 30' en mercado), `paper_reextraccion` (dom 19:00, re-extrae hechos — único costo LLM recurrente).

## 6. Datos, APIs y cómo correr cosas
- **Datos:** yfinance (con `curl_cffi` impersonate=chrome por el fingerprinting de Yahoo),
  EDGAR/SEC, feeds RSS. Claves opcionales FMP/Polygon/Benzinga (diferidas).
- **LLM:** SDK Anthropic (`backend/services/llm.py`); modelo en `ANTHROPIC_MODEL`.
- **Scripts** (`.venv/bin/python -m ops.<x>`): `batch_analista` (re-evalúa tickers, ~$0.40 c/u),
  `paper_auto` (corre un ciclo paper), `paper_snapshot` (marca P&L), `generar_reporte_pdf`.
  Backtest: `python -m backend.backtesting`.
- **Vistas:** `/` (núcleo), `/universo`, `/sectores`, `/eventos`, `/discovery`, `/rediseno`,
  `/costos`, `/backtest`, `/evaluate`, `/legacy`, `/consola`.

## 7. Documentos canónicos (`init_docs/`)
`01_sistema_inversion`, `02_mvp`, `03_especificacion_tecnica_agentes` (sistema viejo);
`04_sistema_inversion_v4_2` (reglas v4.2); `11_nucleo_consolidado_v3`,
`11_bloque_c_consolidado`, `11_traspaso_mapa_cuellos_botella` (rediseño / núcleo nuevo).
El orden importa para entender el algoritmo. Ver también `CLAUDE.md` (misión + lineamientos).
