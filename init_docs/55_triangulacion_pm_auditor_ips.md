# 55 — Triangulación: PM + Auditor + IPS + ledger + paper nuevo (v2 Fase 4)

> **Para converger con 2+ IAs antes de codear** la capa de DECISIÓN. Igual método que doc 54. Contexto:
> doc 51 (directiva), doc 52 (plan), doc 54 (comité, ya construido), doc 53 (estado vivo). Fecha: 2026-10-26.

## 0. Qué ya está (no se re-discute)
El comité de research está construido y testeado (doc 53): Triage, Macro, Analista (validado en vivo),
Bear, Verificador (3 estados PASS/REVIEW/FAIL por procedencia) + orquestador + ledger de presupuesto USD.
El Verificador produce `VerificationReport` (veredicto + `flags_supervivencia`). Schemas `PMDecision`
(`PMAccion` con `peso_objetivo` 0-1 + `respuestas_flags`) y `AuditReport` ya definidos (`schemas.py`).
IPS parcial decidido: peso máx **20%/nombre**, market cap **$150M-$60B**, presupuesto **$40/mes**, red flags
de supervivencia = **alerta** (el PM resuelve por escrito con OK del verificador, no bloqueo duro).

## 1. Diseño propuesto (a converger)

### 1.1 IPS en código (`config/ips.yaml` + validador)
Único lugar donde el código manda, con reglas del operador. Valida toda `PMDecision`; si viola → **rechaza
y devuelve con motivo** (nunca corrige en silencio). Cubre: máx posiciones, peso máx/nombre, máx/sector,
máx/cuello, rango market cap, ADV mín + % ADV máx, caja mín/máx, máx ops/semana, presupuesto, prohibición
de órdenes reales. Hash del IPS en cada decisión del ledger.

### 1.2 PM (`backend/agentes/pm.py`, Opus 5.5)
Ve: dossiers vigentes **PASS/REVIEW** + cartera actual + memo macro + IPS + su **hit-rate de falsadores**.
Decide compras/ventas/recortes/aumentos/mantener/caja con `peso_objetivo`, tesis, falsador fechado, qué lo
haría vender, y `respuestas_flags` a cada flag de supervivencia. Puede quedarse 100% en caja. **El PM sizea;
el determinismo NO impone tamaño** (doc 51) — las calculadoras (burden/T*) son LECTURA que el PM recibe.

### 1.3 Auditor (`backend/agentes/auditor.py`, Opus 5.5, contexto separado)
Revisa la `PMDecision`: concentración real (¿N nombres = 1 apuesta macro?), coherencia memo↔peso, rotación,
nombres con verificación fallida, violaciones del IPS. Puede **devolver UNA vez** con objeciones; el PM
replica; la decisión final + las objeciones quedan registradas juntas.

### 1.4 Ledger de decisiones (`backend/agentes/ledger_decisiones.py`)
Append-only: cada decisión con memo, falsador, hash del dossier, versiones de prompts/modelos, hash del IPS,
precio, timestamp. Métricas: hit-rate de falsadores, Brier (calibración de convicción), P&L vs benchmarks.

### 1.5 Paper nuevo
`paper_trader` se **reescribe** para operar desde `PMDecision` (sin `sizing_final`/mérito v3). Libro nuevo
limpio. El monitor de eventos abre revisiones (Analista+Verificador+PM del nombre).

### 1.6 Carteras sombra (desde el día 1, doc 51 Capa E)
(a) equal-weight del universo elegible · (b) "Opus+web solo" (un agente, sin pipeline) · (c) ETFs temáticos
(SMH/URA/ITA/COPX). Sin esto no se sabe si el pipeline agrega.

## 2. ⭐ DECISIONES ABIERTAS (a converger)

1. **¿Se dissolvió el problema del override del cap (doc 49 / VRNS)?** En v1, un cap determinista con input
   artefacto (g_D) boxeaba al PM. En v2 **el PM sizea bajo el IPS y el determinismo no impone tamaño** →
   parece que el problema desaparece. ¿Correcto, o queda un residuo (p.ej. el veto de supervivencia sí debe
   seguir siendo duro)? **Mi default:** disuelto; el único límite duro es el IPS + la prohibición de operar
   con dossier FAIL.

2. **Dossier REVIEW: ¿puede el PM actuar sobre él?** PASS = respaldo suficiente; FAIL = no justifica
   compra/aumento. **Mi default:** sobre REVIEW el PM PUEDE actuar pero debe justificar el gap por escrito
   (como con los flags); REVIEW no habilita *aumentar* una posición grande.

3. **IPS reject-and-return: ¿cuántos loops?** Si la `PMDecision` viola el IPS, el código la devuelve con el
   motivo. **Mi default:** máx 1 re-propuesta del PM; si vuelve a violar, se recorta determinísticamente al
   límite y se registra (no se descarta la decisión entera).

4. **PM ↔ Auditor: ¿qué puede forzar el Auditor?** **Mi default:** el Auditor NO veta (devuelve 1 vez con
   objeciones, el PM replica, queda registrado) — SALVO violación de IPS o dossier FAIL, que son duros
   (código). ¿O el Auditor debería poder vetar rotación excesiva / concentración por sí mismo?

5. **respuestas_flags:** el código chequea que el PM responda TODOS los flags de supervivencia (retry si
   falta). **Mi default:** además, severidad "supervivencia" no-resuelta satisfactoriamente → cap de sizing
   automático (ej. ≤4%) hasta que el verificador confirme. ¿Gobernanza o mecánica?

6. **Carteras sombra — construcción exacta.** ¿Equal-weight de qué conjunto: el universo elegible del IPS,
   o solo los dossiers PASS de la semana? ¿"Opus+web solo" corre sobre los mismos nombres triageados?
   **Mi default:** (a) equal-weight de las posiciones que el PM tiene + candidatas PASS; (b) mismo universo
   que el PM ve.

7. **Evento → revisión del PM: ¿salta el Auditor?** Una decisión disparada por evento (un solo nombre)
   ¿pasa por el Auditor igual, o solo si cambia peso material? **Mi default:** Auditor solo si el cambio de
   peso supera un umbral; si no, va directo al ledger + IPS.

8. **Hit-rate de falsadores → PM:** ¿cómo se le presenta al PM su propio track record para que calibre?
   **Mi default:** un resumen (falsadores vencidos: cuántos se cumplieron, Brier de convicción) inyectado
   en el prompt del PM.

## 3. Lo que NO se re-abre
El paradigma (doc 51), los schemas ya definidos, el comité ya construido (doc 54), el IPS parcial decidido.
La triangulación es sobre la **mecánica de decisión** (PM/Auditor/IPS/ledger/paper), no sobre quién decide.
