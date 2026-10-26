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

---

## 4. RESOLUCIÓN CONVERGIDA (IA1 + IA2, 2026-10-26)

### ★ PRINCIPIO RECTOR (IA2 — el insight que ordena el resto)
**Todo límite DURO tiene inputs mecánicos (precios, pesos, ADV, market cap, fechas) O, si tiene un input de
LLM, tiene un CANAL DE DISPUTA que no es override.** El problema de v1 (VRNS) no era el cap de sizing; era
un límite duro con input potencialmente erróneo y sin forma de disputarlo. v2 lo reintroducía en el gate FAIL
y en el cap del 4% → ambos se arreglan abajo.

### Decisiones cerradas
1. **Override — disuelto para sizing, NO para el patrón:**
   - El sizing determinista desaparece; la validación de admisibilidad del IPS no.
   - **FAIL es el nuevo VRNS** → canal de disputa: el PM presenta una **objeción estructurada** (qué dato,
     por qué es artefacto, qué fuente lo contradice) → el **Verificador re-corre en contexto fresco** con la
     objeción; si sostiene el FAIL, queda FAIL y se registra. El PM **nunca overridea** pero no queda boxeado.
     Contador de disputas ganadas/perdidas (si gana muchas → falla el Verificador; si pierde casi todas → se
     usa como lobby).
   - **Inputs del IPS: mecánicos SOLO.** La clasificación sector/cuello para los caps de concentración viene
     de **fuente fija (GICS o tabla a mano)**, NUNCA de un bucket asignado por LLM.
   - **FAIL bloquea aperturas y aumentos, NUNCA reducciones** (una posición que pasa a FAIL no te puede dejar
     atrapado sin poder salir).
   - Violación **local simple** (7% vs tope 6%) → recorte mecánico + registro. Violación **agregada**
     (sector/liquidez/interacción) → el código NO elige qué recortar → el excedente va a **cash, sin
     redistribuir**; la cartera se marca **"PM+clip"** en el ledger para la atribución.
2. **REVIEW:** "grande" es un **número del IPS**; la regla se escribe sobre el **peso resultante** ("con
   REVIEW no se termina por encima de X%"), no sobre la intención. Justificación del gap en **formato fijo**
   (qué ítem, por qué no es material, qué lo volvería material). **Monitorear la distribución PASS/REVIEW/FAIL**
   (si REVIEW es el default, las justificaciones se vuelven boilerplate).
3. **Loops del IPS:** el PM recibe el IPS como **tool de dry-run** (`validate(propuesta)` → violaciones +
   holguras exactas) durante su razonamiento; el gate final sigue duro pero el loop casi no se usa. Máx 1
   re-propuesta; si hay que recortar → a cash, sin redistribuir.
4. **Auditor — sin veto, con dientes por MEDICIÓN:**
   - Concentración/rotación que se puede escribir como número → va al **IPS** (turnover budget + holding
     period mínimo). Lo que no es número, es juicio → no se le da veto a un 2º Opus con menos contexto.
   - Cada objeción = **predicción falsable** ("esta rotación destruye valor a 6m") puntuada ex-post +
     **cartera sombra contrafáctica "PM+veto-auditor"** → después de N desacuerdos se decide con datos si el
     auditor merece veto (no a priori hoy).
   - Intermedio: objeción de **severidad alta sobre un AUMENTO → demora de 1 ciclo** (no bloqueo); la demora
     compra información, no decide quién tiene razón.
5. **respuestas_flags — se reemplaza el cap del 4% (era el patrón del punto 1):** cada flag se responde de
   una de dos formas: **(a) refutado** con evidencia verificable → el Verificador chequea solo ese hecho
   (chequeo angosto); **(b) aceptado como riesgo** → se convierte en **falsador con fecha + umbral medible**.
   La (b) siempre está disponible → el PM nunca queda boxeado (el costo de no resolver es *accountability*, no
   sizing). Si no hace ninguna → el dossier baja a REVIEW (regla 2). Un mecanismo, cero números mágicos.
6. **Carteras sombra (5):** (a1) EW de las posiciones del PM → valor del **sizing**; (a2) EW de todas las
   PASS → valor de la **selección**; (b) "Opus+web solo" (mismo IPS/fechas/costos, **2-3 semillas**) → ¿vale
   el comité?; (c) ETFs temáticos **+ índice amplio (ACWI/SPY)** (temáticos = ¿el picking le gana al tema?;
   amplio = ¿los temas le ganan al mercado?); (d) contrafáctica del auditor. Medir drawdown/vol/turnover/
   exposición. **Expectativa: nada significativo antes de 12-18 meses** con cartera concentrada.
7. **Evento → PM:** (a) **las reducciones NUNCA pasan por el auditor** (en risk-off la velocidad importa);
   (b) umbral acumulado **por nombre en ventana móvil**; (c) **umbral más bajo para aumentos por noticia**
   (máx sesgo de sobrerreacción del LLM); lo que queda por debajo → auditoría **asíncrona post-hoc no
   bloqueante** que alimenta el track record del auditor.
8. **Hit-rate al PM:** **N mínimo 20-30** antes de inyectar nada; calibración **por bucket con conteos**
   ("alta: 7/12"), no un número único. Especificidad del falsador (umbral/fecha/fuente) **exigida por código
   o validada por el auditor** (anti-Goodhart). Presentar como **información, no instrucción**. **Fijar en el
   schema el signo** falsador-disparado (tesis falsada) vs tesis-cumplida.

### Implicancias para el código (Fase 4)
- El **validador del IPS** es puro-mecánico (sin inputs LLM) y expone `validate(propuesta) → violaciones`
  usable como dry-run tool del PM y como gate final. Clasificación sector/cuello desde tabla fija.
- El **Verificador** gana un modo "re-corrida con objeción del PM" (contexto fresco, chequeo angosto) + el
  contador de disputas.
- El **ledger de decisiones** marca "PM+clip", registra objeciones del auditor como predicciones falsables,
  y fija el signo disparado/cumplido del falsador.
- Las **5+ carteras sombra** se instrumentan desde el día 1, point-in-time.
