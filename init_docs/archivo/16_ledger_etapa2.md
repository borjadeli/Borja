# 16 — Etapa 2: Fuente de verdad + ledger (diseño)

> 🏗️ **ANDAMIAJE (diseño VIGENTE, NO implementado) — ver `00_MAPA_DOCUMENTOS.md`.** Define las tablas
> `nx_*` del ledger fiel; el paper todavía usa `libro.json` de fracciones. Es la Etapa 2 pendiente. Estado: doc 32.

> La base sobre la que se apoya todo lo demás. Diseño en doc, **sin código**, hasta
> aprobar el esquema. Ancla en la constitución (`13_`): estados (Art. 5), evidencia
> (Art. 3), vigencia (Art. 7), ejecución/contabilidad (Art. 11), reproducibilidad
> (Art. 1.2). Reemplaza el libro paper actual (`libro.json`, fracciones) por
> contabilidad real de acciones y caja.

## Fundamentos (confirmados por el operador)
1. **Dónde vive:** tablas nuevas en el mismo `data/borja.db`, con **prefijo `nx_`**
   (núcleo nuevo), **sin tocar** las tablas viejas. Aislamiento por nombre.
2. **Acciones y caja REALES** (no fracciones). Invariante: `caja + Σ(shares × precio) = equity`.
3. **Append-only + estado derivado:** el log (decisiones, fills, versiones, snapshots) es
   **inmutable**; la posición/caja actual es una **proyección** de ese log. Todo reproducible,
   nada se pisa.

---

## Modelo de datos

### A. Identidad y mapa
- **`nx_nodo`** *(estado actual)* — cuello de botella persistido (hoy `Nodo` es solo un
  dataclass sin tabla). Campos: `id, nombre, cluster/sector, factor_macro, estado_confirmacion
  (promesa/confirmado/debilitandose), estado_archivo, fecha_ultima_vigilancia, nota`.
- **`nx_nodo_evento`** *(append-only)* — cada transición de estado del nodo con hecho/fuente/fecha.
- **`nx_empresa`** *(estado actual)* — `ticker (PK), nombre, jurisdiccion, exchange, sector,
  estado (9 estados Art. 5), fuente_ingreso (manual/discovery), fecha_ingreso, reentradas_usadas
  (Candado B)`.
- **`nx_empresa_evento`** *(append-only)* — cada cambio de estado (quién lo disparó: regla/PM/
  humano, motivo, evidencia, timestamp, versión de ficha). El `estado` de `nx_empresa` es la
  proyección de este log.
- **`nx_empresa_nodo`** — vínculo N↔N empresa–nodo (`es_primario`). **Nunca se borra** (preserva
  la 2ª/3ª ola, Art. 5.3).
- **`nx_vista_macro`** *(versionada)* — `version, factor, postura (viento_favor/neutral/
  viento_contra_documentado), fecha, motivo`. La lee/actualiza el LLM+operador (Art. 4.5).
- **`nx_ticker_factor`** *(artefacto versionado)* — `ticker, factor, version, fuente`.
  Multi-pertenencia con **conteo completo**. Alimenta el **factor-cap** (Art. 4.5) y los clusters
  (Art. 4.8). Consultado determinista en runtime.

### B. Análisis (ficha versionada + evidencia)
- **`nx_ficha_version`** *(append-only)* — una fila por corrida de análisis: `id, ticker, version,
  fecha, arquetipo, quality_tier, fragility_score, bull, base, bear, asimetria, cap_celda,
  cap_crr, hard_cap, es_binary, vencimiento (edad máx), estado_vigencia`. Cada actualización por
  hecho crea una versión nueva (Art. 7.4); el precio NO versiona.
- **`nx_hecho`** *(append-only)* — átomos de evidencia ligados a la versión: `id,
  ficha_version_id, campo, valor, tipo (HECHO/INFERENCIA/HIPOTESIS), verdad (TRUE/FALSE/UNKNOWN),
  fuente (A/B/C), documento, fecha_hecho`. **UNKNOWN nunca se coacciona a False** (Art. 3).
  *(Los campos de durabilidad del cuello, Art. 12.2, se agregan acá en la Etapa 4.)*

### C. Decisión (PM → validador → aprobación)
- **`nx_decision_pm`** *(append-only)* — `id, fecha, ciclo (semanal/evento/manual),
  input_state_hash, cash_objetivo (lo fija el operador), explicacion`. `input_state_hash` +
  las versiones de ficha usadas hacen la decisión **reproducible** (Art. 1.2).
- **`nx_decision_linea`** — por nombre: `decision_pm_id, ticker, incluir, peso_propuesto, motivo,
  ficha_version_id`. También **las excluidas** con su driver y por qué quedaron afuera (Art. 4.2).
- **`nx_validacion`** — `decision_pm_id, intento_n, resultado (pass/reject), errores[]`. Reject →
  **el PM re-propone** (nueva `nx_decision_pm`); el validador **no modifica en silencio** (Art. 4.4).
- **`nx_aprobacion`** — `decision_pm_id, resultado (aprobada/rechazada), cambios_pedidos, notas,
  fecha`. Paso humano obligatorio en construcción/calibración (Art. 9).

### D. Ejecución y contabilidad (Art. 11)
- **`nx_orden`** — de una decisión aprobada: `id, decision_pm_id, ticker, lado (buy/sell),
  shares_objetivo, adv_cap_aplicado, fecha_decision, fecha_dato`.
- **`nx_fill`** *(append-only)* — ejecución real: `id, orden_id, ticker, lado, precio_fill
  (apertura+30′), shares, slippage, comision, cash_delta, fecha_fill, input_state_hash`. Soporta
  **fills parciales / multi-día** (cap de ADV → varios fills). Sin fills en halts; gaps atraviesan
  stops.
- **`nx_corporate_action`** *(append-only)* — `id, ticker, tipo (split/dividendo/M&A/delisting),
  fecha, parametros`. Ajusta posición/caja de forma determinista (Art. 11.6).
- **`nx_snapshot`** *(append-only)* — diario: `fecha, equity, cash, pnl_ideal, pnl_modelado
  (doble P&L, Art. 11.5), benchmark (SPY), n_posiciones, exposicion`.

### E. Proyecciones (estado actual, derivado del log)
- **`nx_posicion`** — `ticker, shares, costo_promedio, precio_actual, valor_mkt, peso`.
  Reconstruible desde `nx_fill` + `nx_corporate_action`.
- **`nx_caja`** — `saldo, rf_acumulada, cash_objetivo`. = capital_inicial + Σ cash_deltas +
  dividendos + rf. En paper se acredita **tasa libre de riesgo** al cash (Art. 4.7).

---

## Relaciones (resumen)
`nx_nodo 1—N nx_empresa` (vía `nx_empresa_nodo`, N↔N) · `nx_empresa 1—N nx_ficha_version` ·
`nx_ficha_version 1—N nx_hecho` · `nx_decision_pm 1—N nx_decision_linea` · `1—N nx_validacion` ·
`1—1 nx_aprobacion` · `nx_aprobacion → N nx_orden` · `nx_orden 1—N nx_fill` ·
`nx_fill + nx_corporate_action → nx_posicion / nx_caja` (proyección).

**Inmutable (log):** nodo_evento, empresa_evento, ficha_version, hecho, decision_pm,
decision_linea, validacion, aprobacion, orden, fill, corporate_action, snapshot, vistas macro.
**Derivado (proyección):** empresa.estado, posicion, caja, estado actual del nodo.

---

## Invariantes de reconciliación (tests, Art. 9)
1. `caja + Σ(shares × precio) = equity`, siempre.
2. `Σ pesos + cash% = 100 %`.
3. Ninguna `nx_posicion` sin `nx_fill` que la respalde.
4. Ningún `nx_fill` que viole el cap de participación sobre ADV (Art. 11.3).
5. Ninguna `nx_orden` sin `nx_aprobacion`.
6. Toda `nx_decision_pm` reproducible desde su `input_state_hash` + versiones de ficha.
7. Ningún `nx_hecho` con `verdad=UNKNOWN` coaccionado a False aguas abajo.

---

## Qué reemplaza / migra
- `data/nucleo_paper/libro.json` (fracciones) → tablas `nx_*` (acciones reales). El libro viejo
  queda como **histórico read-only**.
- `Nodo` (dataclass sin persistencia) → `nx_nodo` + `nx_nodo_evento`.
- Tablas viejas (`Ficha`, `Trade`, `PortfolioSnapshot`, `DecisionJournal`) → **intactas, solo
  lectura**; no las toca el sistema nuevo (corta el cordón `Ficha.estado`).

---

## Decisiones de la Etapa 2 `CERRADO` (operador)
- **Migración:** el nuevo ledger **arranca LIMPIO** (el libro viejo en fracciones no es
  reconstruible a acciones/fills reales; heredarlo ensuciaría la contabilidad desde el día 1).
  El libro paper viejo queda como **histórico read-only**.
- **Capital inicial:** **$100.000**.
- Números calibrables (rf del cash, slippage, comisiones, cap de ADV) → registro `14_`; se fijan
  al construir.
