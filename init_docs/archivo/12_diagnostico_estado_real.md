# 12 — Diagnóstico del estado real + plan de rediseño

> 📜 **HISTÓRICO/DIAGNÓSTICO (2026-07) — ver `00_MAPA_DOCUMENTOS.md`.** El panorama módulo-por-módulo
> sigue siendo útil, pero las implementaciones avanzaron y hay un 3er stack (motor de evidencia) que
> no veía. Estado vigente: doc 32.

> **Propósito.** Documento vivo. Consolida la auditoría del código real de BORJA
> (no de los docs) contra el flujo objetivo que definió el operador, y traza el
> plan de reconstrucción por etapas.
>
> **Regla de trabajo (acordada 2026-07).** No se toca código ni se hacen cambios
> sin acuerdo total y con el esquema de cada etapa bien definido. El sistema tiene
> que quedar funcionando perfecto. Este doc se aprueba y se va editando antes de
> cualquier implementación.
>
> **Método.** Auditoría hecha leyendo el código y la DB reales (5 barridos
> paralelos: scheduler/jobs, endpoints, imports cruzados, datos/seeds, discovery/
> mapa). Cada afirmación tiene evidencia `archivo:línea`. Fecha: 2026-07-27.

---

## 0. Norte (lo que el operador quiere)

**Principio rector:** los **datos y los límites duros son deterministas**; el
**LLM (PM) ejerce criterio SOLO dentro de esos límites** — elige empresas, asigna
sizing dentro de los caps, decide cuánto cash, qué priorizar. El LLM nunca inventa
números, contratos ni fundamentos.

**Flujo objetivo (9 etapas):**

```
1. Mapa estructural
2. Discovery basado en hechos económicos
3. Candidatas (manuales + descubiertas)
4. Pre-screen barato (Filtro 0)
5. Deep research completo (ficha rica)
6. Universo vivo comparable
7. PM contextual que construye cartera
8. Sparring + aprobación
9. Monitoreo, actualización y rotación disciplinada
```

**Lo que hoy corre (colapsado):**

```
Universo heredado (lista estática de Fichas del viejo)
  → extracción parcial de hechos
  → reglas y scores del núcleo determinista
  → ordenamiento por mérito
  → llenar posiciones hasta la exposición objetivo
```

---

## 1. Hallazgo de fondo: dos sistemas en paralelo, y el objetivo es un tercero

No es "un sistema medio roto". Son **dos sistemas casi completos, ambos en paper,
ambos comiendo de la misma tabla `Ficha`**:

- **Sistema VIEJO** (`backend/agents/`, 12 jobs activos en el scheduler): embudo
  completo — screener → analista → juez → recomendación → **aprobación humana** →
  `Trade`. Produce **fichas ricas** (66/67 con tesis+score), tiene su propio libro
  (+13,6 %, 2 posiciones vivas: S, NABL), monitores, dispatcher, discovery semanal,
  2.788 decisiones auditadas. **Su pecado: el score 0-10 subjetivo** que el operador
  quiere eliminar.
- **Sistema NUEVO** (`backend/nucleo/` + `backend/seleccion/`, 3 jobs): núcleo
  determinista sobre hechos cacheados → su propio libro paper (`data/nucleo_paper/
  libro.json`, 12 posiciones, +4,86 %). **Su pecado: tiró el juicio del LLM** (PM
  bypasseado, ficha rica reemplazada por hechos tipados) **y nunca cableó el
  front-end** (discovery, filtro barato).

**El nuevo no reemplazó al viejo: lo consume** (usa `Ficha.estado` como universo,
`shadow.py:_tickers_vivos()`) y corre al lado. El flujo objetivo **no es ninguno de
los dos**: es un tercero que toma el **front-end rico del viejo** (discovery, ficha,
PM-LLM) montado sobre los **guardrails deterministas del nuevo** (gate, caps,
sizing, salidas).

> La migración quedó a mitad de camino: el núcleo nuevo construyó bien los
> guardrails deterministas pero descartó el juicio del LLM y no cableó el front-end;
> el viejo aún tiene el front-end y el flujo de aprobación, pero con el score
> subjetivo que se quería matar.

---

## 2. Diagnóstico módulo-por-módulo (9 etapas vs. código real)

Leyenda: ✅ existe y conectado · 🟡 existe pero incompleto/mal conectado ·
🔴 a reconstruir · 🏚️ heredado del viejo

| # | Etapa objetivo | Estado | Evidencia en el código |
|---|---|---|---|
| 1 | **Mapa estructural** | 🟡 duplicado + huérfano | Hay DOS mapas. **Nuevo** (`backend/mapa/`: `nodo.py`, `transiciones.py`, `brujula.py` con **34 territorios reales**, `discovery.py`) bien diseñado pero **sin persistencia** (no hay tabla `Nodo` en la DB) **y sin caller**. **Viejo** (`SectorMapa`, 16 mapas en DB, **0/7 activos aprobados**) es el que usa `agents/analista.py`. |
| 2 | **Discovery por hechos económicos** | 🔴 a reconstruir | `mapa/discovery.py` (frecuencia por estado — confirmado 14 d / promesa 10 d / caliente 2 d; nodo caliente por PO/orden/partnership) existe pero **ningún caller lo ejecuta**. El viejo `agents/discovery_hipotesis.py` corre domingos 20:00 (LLM ~$2-5) pero **sus candidatos NO se convierten en Fichas**. Nada abre nodos por contratos/backlog/lead-times de forma automática. |
| 3 | **Candidatas (manual + descubierta)** | 🟡 parcial / heredado | Puerta manual: `/descubrimiento/crear-candidatas-form` (`ui.py:848`) → crea `Ficha`. Puerta descubierta: el screener (`agents/descubrimiento.py`) crea Fichas pero es **manual on-demand**. Ambas escriben en la **tabla vieja `Ficha`**, no en una cola propia del núcleo. |
| 4 | **Pre-screen barato (Filtro 0)** | 🟡 existe pero no cableado | `LIQUIDEZ_SCREENER` (`nucleo/constantes.py:49`) + 5 filtros (market cap, revenue YoY, margen, deuda, volumen) viven en el screener viejo, **solo manual**. En el loop vivo NO hay Filtro 0: el gate exhaustivo corre directo. Confirmado: el filtro barato y el gate formal se fusionaron. |
| 5 | **Deep research → ficha rica** | 🏚️ heredado / 🔴 para el núcleo | La ficha rica (negocio, moat, management, escenarios) existe **solo en el viejo** (`agents/analista_writer.py`), construida alrededor del score 0-10 que se quiere matar. El núcleo nuevo produce **hechos tipados** (`data/nucleo_hechos/`, 37 tickers JSON), **no** una ficha comparable. |
| 6 | **Universo vivo comparable** | 🟡 lógica nueva huérfana / estados heredados | `seleccion/watchlist.py` tiene la lógica de watchlist viva (tope 20, expulsión por mérito, protección por timing, vínculo↔nodo). Pero el loop usa `_tickers_vivos()` = **`Ficha.estado`** (viejo), no esa abstracción. Los estados (Universo / WL_Seguimiento / WL_Activa / WL_Prioritaria / Portfolio) los maneja el viejo. |
| 7 | **PM contextual construye cartera** | 🔴 el gap más grande | `seleccion/pm.py` (PM-LLM) **existe** pero: (a) su poder es solo incluir/no + sesgo sectorial, **nunca asigna sizing** ("el sizing sale del núcleo, no del PM"); (b) **no se llama en el loop** — `paper_trader.py` es "100 % determinista, sin juicio blando del PM". Hoy hay **cero criterio de PM** en la construcción de cartera. Choca de frente con el norte. |
| 8 | **Sparring + aprobación** | 🟡 existe (viejo) / desconectado (nuevo) | `seleccion/sparring.py` (2º LLM adversarial), `seleccion/preflight.py` (chequeo de staleness) y el flujo de aprobación del viejo (2.989 recs aprobadas) existen. Pero el **paper nuevo corre sin sparring ni aprobación** (autónomo por diseño del operador). |
| 9 | **Monitoreo / rotación disciplinada** | 🟡 parcial | Monitoreo: los 4 monitores del viejo (precios/earnings/form4/noticias) → `Evento` → dispatcher. Cableado. Rotación: de las **5 vías de salida** (`nucleo/salida.py`), **solo precio (4, 5) + CRR/red-flags** están cableadas en paper; **governance hard y triggers (vía 1) NO**. No existe la cadencia explícita de 3 niveles (continuo / evento / integral-mensual). |

---

## 3. Estado operativo actual (verificado)

- **Dos libros paper conviviendo:**
  - Viejo: `PortfolioSnapshot` (51 snapshots), equity ~$113,6 K (+13,6 %), 2 posiciones
    (S, NABL), mucho cash (exposición ~12 %).
  - Nuevo: `libro.json`, 12 posiciones (100 % invertido), equity **$104.856 (+4,86 %)**
    al 23-jul (había cerrado +7,99 % el 22; MP se cayó −20,9 %). Cartera congelada
    desde el 3-jul (challenger y piramidado apagados).
- **18 jobs autónomos** hoy (scheduler dentro de `uvicorn`, `SCHEDULER_AUTOSTART=true`):
  3 del núcleo nuevo + 12 del viejo + 3 operativos. Costo LLM recurrente **~$22-34/mes**
  (reextracción del núcleo domingo ~$3,5 + discovery viejo ~$2-5).
- **Universo 100 % estático:** 50 tickers hardcodeados en `seed/tickers_iniciales.yaml`
  → 67 Fichas. 37 con hechos cacheados; 30 en estado "Universo" sin evaluar.

---

## 4. Auditoría de desacople del sistema viejo

Regla acordada: **el viejo no participa en ninguna decisión nueva, pero no se borra
todavía** (se conserva el código para no romper dependencias). El acople real es chico:

| Dependencia nuevo → viejo | Criticidad | Cómo cortarla |
|---|---|---|
| `shadow.py:_tickers_vivos()` ← `Ficha.estado` (el **universo entero**) | 🔴 crítica, sin degradación | Reemplazar por una fuente de universo propia del núcleo (la cola de candidatas nueva). **Es el cordón umbilical principal.** |
| `paper_trader.py` ← `calcular_crr_ticker` (agents), `Ficha.red_flags_count`, `Ficha.sector` | 🟡 degradables (try/except) | Encapsular en servicio propio; hoy si fallan degradan sin romper. |
| `paper_pnl.py` ← históricos SPY (`agents.equity_curve`) | ⚪ opcional | Mover a `services/market_data`. |
| `shadow.py` ← `agents.portfolio` (comparación viejo vs nuevo) | ⚪ cosmética | Retirar cuando ya no se compare. |

**Datos a preservar sí o sí:** `Ficha` (66 análisis), `DecisionJournal` (2.788),
`Trade` (14), `PortfolioSnapshot` (51 — la equity curve), `data/nucleo_hechos/`
(37 JSON). Todo append-only salvo `Ficha`.

**Dashboard:** casi todo es viejo. Solo `/` (parcial) y `/rediseno` leen el núcleo.
Apagar el viejo hoy rompe `/universo`, `/legacy`, `/sectores`, `/eventos`,
`/discovery`, fichas, recomendaciones. **Hay que reconstruir vistas nuevas antes de
desconectar.**

---

## 5. Plan de reconstrucción (por etapas, a acordar antes de tocar código)

Secuencia de menor riesgo, alineada al norte. Cada etapa se cierra con su esquema
detallado (archivos, contratos, cambios) **antes** de implementar. Nada se ejecuta
sin acuerdo.

### Etapa 1 — Descongelar la cantera (Discovery + Filtro 0)
Ataca directo el "universo heredado".
- Orquestador que ejecute `mapa/discovery.py` (`nodos_a_vigilar` → re-extrae hechos →
  `evaluar_transicion`/`evaluar_apertura`) y **abra nodos por hechos económicos**
  (contratos, PO, backlog, take-or-pay, lead-times, shortages).
- **Filtro 0** como etapa explícita y barata (liquidez, market cap, revenue/contrato
  mínimo, red flags evidentes) que decide *"¿vale el deep research?"* → descartar /
  esperar hecho / pasar a deep.
- Alimenta una **cola de candidatas propia del núcleo** (no la tabla `Ficha` vieja).

### Etapa 2 — PM-LLM con sizing dentro de caps (corazón del norte)
- `pm.py` decide **inclusión + sizing dentro de [piso, Hard Cap] + cash +
  priorización**, y se **cablea en el loop** en reemplazo del selector 100 %
  determinista.
- Los caps/gate del núcleo quedan como **límites duros** que el PM no puede violar.
- Contrato claro de qué es determinista (elegibilidad, caps, riesgo de financiación,
  liquidez, concentración, triggers) vs. qué decide el PM.

### Etapa 3 — Ficha rica para el núcleo
- Deep research que produzca una **ficha comparable** (negocio/posicionamiento,
  validación de tesis, finanzas, management, precio/escenarios, tesis operativa) —
  **sin score 0-10** — que alimente al PM. Reusar lo rescatable de `analista_writer.py`.

### Etapa 4 — Sparring + aprobación y rotación de 3 niveles
- Sparring (2º LLM adversarial) + aprobación sobre el mix del PM.
- Rotación deliberada: monitoreo continuo · revisión por evento · revisión integral
  (mensual). Cablear las vías de salida faltantes (governance hard, triggers).

### Etapa 5 — Desacople final + vistas nuevas + retiro del viejo
- Cortar el cordón `Ficha.estado`, encapsular las dependencias degradables.
- Reconstruir las vistas del dashboard sobre el núcleo nuevo.
- Recién entonces aislar/retirar el sistema viejo (preservando los datos históricos).

---

## 6. Preguntas abiertas (a resolver con el operador)

1. **Alcance del PM:** sizing dentro de caps confirmado. ¿También cash/timing/
   priorización explícitos? ¿Algún tope a su discrecionalidad?
2. **Libros paper:** ¿unificar en uno solo (el nuevo) o mantener los dos conviviendo
   durante la transición?
3. **Ficha rica:** ¿se reconstruye desde `analista_writer.py` o se diseña de cero sin
   arrastrar el score?
4. **Aprobación:** ¿el flujo nuevo vuelve a tener confirmación humana (como el viejo)
   o sigue autónomo en paper?
5. **Presupuesto LLM:** techo mensual aceptable para discovery + deep research + PM.

---

## 7. Referencias de código (evidencia)

- Núcleo: `backend/nucleo/{arquetipo,gate,quality,fragility,sizing,selector,salida,flujo,constantes,shadow,extractor}.py`
- Selección/PM: `backend/seleccion/{pm,watchlist,sparring,preflight,paper_trader,paper_pnl,jobs}.py`
- Mapa nuevo: `backend/mapa/{nodo,transiciones,brujula,discovery}.py`
- Viejo: `backend/agents/{descubrimiento,discovery_hipotesis,mapa_sectorial,analista_writer,juez,portfolio,dispatcher,...}.py`
- Scheduler: `backend/scheduler.py` · Endpoints: `backend/main.py`, `backend/ui.py`
- Datos: `data/borja.db` (17 tablas), `data/nucleo_paper/libro.json`, `data/nucleo_hechos/`
- Seeds: `backend/seed/{tickers_iniciales,sectores,macro_v1}.yaml`, `load_seed.py`
