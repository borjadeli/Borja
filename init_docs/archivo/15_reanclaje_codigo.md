# 15 — Re-anclaje: constitución vs. código del núcleo

> 📜 **HISTÓRICO (2026-07) — ver `00_MAPA_DOCUMENTOS.md`.** Diagnóstico de brecha doc↔código; los huecos
> que marcó (incl. "cero tests", hoy 276) ya están en doc 32 §7 / doc 14. No es referencia viva.

> Para dejar de decidir desde cero. Mapea cada artículo de la constitución (`13_`)
> contra lo que el **código del sistema nuevo YA implementa**, y separa lo que se
> conserva de lo genuinamente nuevo. Al final: lo que me hace **ruido** (huecos,
> errores, cosas colgadas). Verificado leyendo el código, 2026-07.

## Leyenda
✅ **EXISTE** (se conserva) · 🟡 **PARCIAL** (existe base, falta completar) ·
🔴 **NUEVO** (hay que construirlo)

## Mapa artículo → código

| Art. | Tema | Estado | Qué hay en el código |
|---|---|---|---|
| 1 | Objetivo / "funciona perfecto" | 🟡 | Filosofía "disciplina sobre actividad" en comentarios (`constantes.py`). Las 10 propiedades de fallo-seguro como **contrato** = 🔴. |
| 2 | Universo | 🟡 | `LIQUIDEZ_SCREENER`, market cap $50M–$2B (`descubrimiento.py`), arquetipos incl. Pre-revenue (`arquetipo.py`) ✅. **Jurisdicciones** 🔴. **Vínculo con nodo** 🟡 (brújula existe, nodo no persiste). |
| 3 | Evidencia | 🟡 | Fuentes A/B/C y hechos-con-fuente en `gate.py`/`extractor.py` ✅. **HECHO/INFERENCIA/HIPÓTESIS + UNKNOWN de 3 valores** 🔴 (hoy son booleans + default-exclude). |
| 4 | Frontera determinista ↔ PM | 🟡 | `gate/quality/fragility/sizing/salida/selector` ✅. **Caps por riesgo** (`CAPS_ARQUETIPO_FRAGILITY`) ✅. **PM (`pm.py`) existe pero BYPASSEADO** 🟡. **Validador reject-and-report** 🔴. `factor_macro` = visibilidad ✅; factor-cap = abierto. **Correlaciones/clusters** 🔴. |
| 5 | Estados y ciclo de vida | 🟡 | `EstadoFicha` enum (Universo/WL_*/Portfolio) ✅. `watchlist.py` lógica viva ✅. 5 vías de salida ✅. La máquina de **9 estados** completa (Esperando-evidencia, En-deep-research) 🟡. |
| 6 | Puertas de entrada | 🟡 | Intake manual (`ui.py`) ✅. **Filtro 0** = screener de 5 filtros (`descubrimiento.py`) ✅. Convergencia a **una cola nueva** 🔴. ticker→nodo 🟡. |
| 7 | Vigencia y cadencia | 🟡 | Pre-flight de staleness ✅. Frecuencia por estado (`mapa/discovery.py`) ✅ **pero huérfana**. Jobs diario/semanal (`jobs.py`) ✅. **PM semanal** como tal 🔴 (hoy `paper_ciclo` diario determinista). Actualización incremental 🟡. |
| 8 | Errores / fallo seguro | 🟡 | Degradación con try/except en `paper_trader` ✅. Política formal + **atomicidad del ledger** 🔴. |
| 9 | Shadow / testing | 🔴 | `shadow.py` (compara viejo vs nuevo) ✅. **CERO tests en todo el repo** → invariantes 🔴 (hueco grande). |
| 10 | Cierre de etapas | 🔴 | Proceso nuevo. |
| 11 | Ejecución paper + contabilidad | 🔴 | Hoy llena a **precio actual**, sizing = **fracción (no acciones)**, **sin costos**. Apertura+30′, slippage, comisiones, cap de ADV, doble P&L, acciones/caja reales = casi todo 🔴 (es la Etapa 2/ledger). |

## Lo que me hace RUIDO (huecos, errores, cosas colgadas)

1. **Dos libros paper en paralelo.** El evaluador viejo auto-aprueba "VALIDADAS" *y* el
   `paper_trader` nuevo opera su libro. Dos decisores sobre carteras distintas. → unificar (Etapa 0).
2. **El mapa no se persiste.** `Nodo` es un dataclass sin tabla; la brújula (34 territorios) y
   `mapa/discovery.py` **no tienen caller**. El vínculo ticker↔nodo no existe en la base.
3. **El fill del paper es optimista.** Llena a `_precio` (precio del análisis), sin
   apertura-siguiente ni costos, y el "sizing" es una **fracción, no acciones** → no hay
   contabilidad real de shares/caja. Es el corazón del Art. 11 + ledger, y hoy sesga el P&L.
4. **`cap_CRR = None` (`[CALIBRACIÓN PENDIENTE]`).** El riesgo de dilución/financiación **NO
   capea el tamaño hoy**, aunque el diseño dice que sí. Colgado.
5. **`MAX_POSICIONES = 12` pero el comentario dice "Real corre 10".** Config ambigua.
6. **Caminos muertos:** Challenger OFF, Piramidado OFF, `SLOT_BUCKET_MAX = 0` (bucket disuelto).
   Lógica presente pero apagada.
7. **El PM existe y está desconectado.** `pm.py` está construido pero el loop vivo no lo llama
   (el `paper_trader` es 100 % determinista). Es "enchufarlo", no crearlo de cero.
8. **Dos discoveries, ninguno cierra el loop.** El viejo (`discovery_hipotesis.py`) corre
   semanal pero **sus candidatos no se vuelven Fichas**; el nuevo (`mapa/discovery.py`) no corre.
9. **Concentración cross-sector sin capear.** `factor_macro` es solo visibilidad; el cap real es
   por sector → la concentración de "capex hyperscaler" (el riesgo más fuerte del mapa, según el
   propio código) **no tiene cap**. (Es el `A DECIDIR` de 4.5.)
10. **Cero tests.** Nada garantiza los invariantes del Art. 9.
11. **Universo = `Ficha.estado`** (el cordón con el sistema viejo).
12. **Docs canónicos ausentes** (01/04/11 no están; el código es la fuente de verdad de facto).

## Conclusión — el delta real (NO es "todo de cero")

- **Se CONSERVA (ya funciona):** gate · arquetipos · caps por riesgo · quality/fragility/sizing ·
  5 vías de salida · screener (Filtro 0) · watchlist viva · brújula · pre-flight · jobs ·
  shadow-runner.
- **Se ENCHUFA (existe, desconectado):** el PM (`pm.py`) al loop · discovery + mapa al Filtro 0.
- **Se CONSTRUYE nuevo:** ledger real (acciones/caja/costos/doble P&L) + ejecución realista
  (Art. 11) · validador reject-and-report · persistir nodos + link ticker↔nodo · evidencia de
  3 valores · jurisdicciones · tests/invariantes · desacople de `Ficha.estado`.
- **Se DECIDE aún:** factor-cap adicional (4.5) · ajuste menor de mérito (4.6).

El grueso del núcleo está y se conserva. El trabajo real es **contabilidad + conexión +
disciplina de pruebas**, no reescribir la lógica de inversión.
