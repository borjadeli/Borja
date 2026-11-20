# 90 — Diseño cerrado: DISCOVERY como motor de alpha (2026-11-20)

> Continuación del doc 88/89 (mapa vivo). En la iteración del mapa concluimos solo el FILTRO; del discovery
> tocamos una mitad (dueño de la evidencia). Este doc cierra la otra mitad —el discovery como **motor de
> alpha que busca empresas**— triangulado con las MISMAS 3 IAs del mapa. **Las 3 convergieron en el marco;
> donde divergieron, la síntesis gana la disciplina más barata.** Principio rector idéntico al mapa:
> **construir lo mínimo, medir si cambia una decisión del PM, recién después automatizar del todo.**

## 1. El principio converjido (las 3 devoluciones)
**Discovery y mapa son la MISMA máquina.** El mapa dice *dónde mirar* (cuello-first = filtro de relevancia
económica), el discovery *propone* candidatos dentro, y el **deep es la única instancia que gasta caro** y
valida si el candidato captura crecimiento real y aún cotiza barato. El discovery **no compite por el
presupuesto: es el embudo barato que PROTEGE el gasto caro.** Su éxito se mide por **conversión a deep útil,
no por volumen de propuestas.**

El riesgo central (las 3): construir un discovery que encuentra *empresas interesantes* en vez de *desajustes
entre evidencia económica y precio*. La pieza faltante **NO es otro agente ni un scoring nuevo** — es una
**política de búsqueda + un registro + una regla de promoción a deep.**

## 2. Las DOS autonomías (separar lo que estaba confundido)
- **Eje 1 — ¿corre solo?** → **SÍ, autónomo POR DISPARADOR.** Lo que las 3 rechazan NO es que corra solo, es
  el **barrido ciego de los 142 cuellos con timer semanal** (el tablero solo cambia con resultados → misma
  respuesta 12 de 13 semanas = ruido). La autonomía CORRECTA es por evento: dispara cuando algo cambió —un
  filing con restricción de suministro, una cualificación nueva, una expansión de capacidad, un cambio de
  estado en el mapa— + una pasada post-resultados + lanzable a mano por el operador. Es MÁS autónomo que un
  cron tonto, no menos.
- **Eje 2 — ¿gasta deeps / admite a la cartera solo?** → en BORJA ese freno **ya es determinista y autónomo**
  (ledger de presupuesto fail-closed · IPS · validadores de discovery + curador, "el humano no decide" · PM
  autónomo doc 85). O sea: el pipeline **ya es autónomo de punta a punta sin humano.** La ÚNICA razón para
  una mano suave temporal: **nunca medimos si el discovery propone señal o ruido** (lo aparcamos como ruido).
  → **Ventana de medición:** corre autónomo, pero se MIRA la conversión durante ~20-30 deeps; si da señal
  (umbral §6), se suelta a full-auto-drain. Misma disciplina que el gate del mapa.

**Decisión firme (las 3, unánime):** discovery **propone a una cola**, NUNCA admite ni dispara deeps por su
cuenta sin pasar los gates deterministas. La cantidad la pone la **capacidad de deeps**, no las ganas de
cobertura (proponer ~2-3× los deeps pagables; lo que sobra espera en la cola, no fuerza gasto).

## 3. Cuello-first: acierto como disciplina, con DOS válvulas (sin barrido amplio)
Cuello-first se **mantiene** (sin cuello, Sonnet+web devuelve lo más mencionado sobre "IA" o "energía" =
consenso). Deja plata en la mesa en dos casos que se nombran en vez de ignorar, y se abren dos válvulas
laterales **sin** convertirlo en búsqueda amplia:
1. **Cuellos ADYACENTES (aporte de IA3):** una empresa que no ocupa un cuello existente pero cuya tecnología
   **ALIVIA** un cuello confirmado (el láser InP que destraba la fotónica de silicio; el bonding híbrido para
   HBM; el interposer para packaging avanzado). Es *cuello-first por FUNCIÓN, no por etiqueta.*
2. **Huérfanos — solo por decisión del operador** (IA1+IA3, 2 de 3): si el operador introduce un huérfano a
   mano (`ops.solicitar`), el discovery lo trata como candidato y el deep decide. El discovery **NO sale a
   cazar huérfanos solo** (es una tesis del operador, no del agente). *[El screen de huérfanos determinista
   $0 de IA2 queda DIFERIDO: opcional, solo si el embudo se seca — §4 del doc 89, "útil pero después".]*

## 4. Dónde está el alpha: la ventana "recién cruzado + aún no repreciado"
La aparente contradicción IA2 (buscar en el borde promesa→confirmación) ↔ IA3 (buscar en confirmado antes del
repricing) **se resuelve sola**: apuntan a la misma ventana por puertas distintas. La **excepción de
"monitoreo de transición" de IA3 (un hito concreto en un cuello promesa) ES el "primer hecho" de IA2**; y las
dos agregan el mismo filtro: **no comprar lo que el mercado YA repreció** (IA2 "test de novedad"; IA3 "antes
del 9× de Sivers"). Prioridad de búsqueda por estado del cuello:

| Estado del cuello | Prioridad de búsqueda |
|---|---|
| **Primer hecho / recién confirmado (≤2T)** + precio aún NO repreciado | **MÁXIMA** — es "detectar antes que el mercado" |
| Confirmado hace tiempo, aún no repreciado | Media (2º orden: proveedores de los líderes) |
| Confirmado y YA repreciado (subió mucho 12m / sobre mediana del cuello) | Baja — el mercado ya lo vio |
| Promesa SIN hechos | Nada (el tablero vigila gratis) |
| Disolución | Nada (value trap) |
| No medible | Solo a mano (operador) |

El estado **prioriza, no encierra**: confirmado = disparador por defecto; adyacente a confirmado también
califica; huérfano solo si el operador lo mete. **Prerrequisito:** hoy los 142 cuellos están en "promesa" →
hasta que corra el **mapa MVP (doc 89), el mapa no puede dirigir nada.** El mapa MVP es el paso 0.

## 5. Cómo dejar de ser buscador de CONSENSO (el aporte más profundo — las 3 lo dicen en capas)
El discovery actual es buscador de consenso **por diseño**: la web abierta refleja lo que el mercado YA
discutió (encuentra al Sivers cuando los artículos ya existen, no antes). Lo que lo vuelve un buscador que
encuentra ANTES **no es un modelo más grande ni un prompt más agresivo — es cambiar la FUENTE DE SEÑAL.** Las
tres capas se apilan:
1. **Hipótesis de desajuste (IA1):** cada candidato debe responder (a) ¿qué evidencia económica concreta está
   cambiando? (b) ¿por qué ESTA empresa la captura? (c) ¿por qué podría NO estar en el precio? Sin una
   hipótesis de desajuste → **no se promueve a deep.** Cambiar el prompt: de "empresas interesantes en X" a
   "empresas en estos cuellos con evidencia primaria reciente de mejora económica cuya relevancia futura puede
   estar subestimada; dame el observable, la exposición y una razón comprobable para investigar si el precio
   ya lo descuenta; no repitas una tesis sectorial conocida como oportunidad." Ojo: **noticia reciente ≠
   oportunidad nueva** (un buen contrato no hace barata a la acción).
2. **Números primero + seguir al cliente (IA2):** el screen XBRL ve los números el día que se presentan (la
   web, cuando alguien escribe la nota) — el post-earnings drift es más fuerte en small caps con poca
   cobertura. Los 10-K revelan clientes ≥10% de ventas (con nombre) y los líderes listan proveedores
   únicos/limitados en factores de riesgo → extraer esas relaciones con cita = **discovery de 2º orden** (ahí
   están los baratos).
3. **Indicadores adelantados (IA3):** fuentes primarias NO estructuradas que se mueven antes que la web —
   **patentes/solicitudes** en el cuello, **licitaciones/contratos/subsidios** (DOE, CE, defensa financian
   capacidad antes de que sea visible en revenue), **ofertas de empleo** en habilidades del cuello (bonding
   híbrido, láser InP = capacidad escalando no precificada), **cualificaciones/estándares** (aparecer en una
   lista de proveedores cualificados antes de que el mercado lo note). Es una **capa de fuentes sobre el
   MISMO agente barato**, usada como disparador — no un discovery más caro.

**El rol de Sonnet queda bien acotado:** ubicar al candidato en su cuello, verificar el vínculo con fuente
primaria y explicar qué hace. Eso lo hace bien; lo que NO hace es generar la ventaja temporal — esa la da la
fuente.

## 6. Métrica: conversión desde el día 1, registro append-only
**Un motor de alpha sin métrica es fe.** Lo mínimo a construir es un **registro de propuestas** al que solo se
agregan filas, que incluye **lo descartado y lo no-deepeado** (si solo registrás lo comprado, nunca sabés si
el filtro tira ganadores). Por propuesta: `fecha · cuello · precio + market_cap del día · evidencia · hipótesis
de desajuste · resultado de triage · deep sí/no · razón · decisión posterior`.

| Métrica | Qué mide | Cuándo da señal |
|---|---|---|
| **Admisión** = propuestas que pasan filtros+curador / total | Ruido del buscador | desde la 1ª corrida |
| **Rendimiento del deep** = deeps que llegan a ZONA DE COMPRA / total | Si discovery+pre-screen apuntan bien (= el gate "¿cambia una decisión del PM?") | a los ~20-30 deeps |
| **Contrafáctico** = retorno 12m de aceptados vs descartados vs canasta del cuello | Si hay alpha de verdad | a los 12 meses |

**Zona de compra** (output determinista de la ficha) es la métrica principal — más limpia que un "deep yield"
subjetivo. **Umbral:** si tras 20-30 deeps **menos de 1 de cada 5** llega a zona de compra → el problema está
en lo que ENTRA al deep, no en el deep. Primeras semanas: observar, **sin objetivos rígidos** (que el discovery
no aprenda a reducir propuestas para inflar su %). El retorno de cartera NO se usa como prueba de calidad hasta
los 12 meses (pocos casos, horizontes largos, ruido PM+mercado): se registra, no se decide con él.

## 7. Presupuesto ($100/mes)
- **Tablero · pre-screen · capa de fuentes · (huérfanos si se construye):** $0.
- **Discovery + curador:** tope ~**$10-15/mes**, solo sobre los cuellos priorizados por el mapa (~5-15, no 142).
- **Deeps + comité:** el resto, ~**$85**.
- Antes de fijar el tope, medir el costo real de una corrida dirigida; si son centavos, el tope que importa es
  el de **propuestas** (por la cola, no por el gasto).

## 8. La secuencia de los $50 (la decisión inmediata)
Síntesis de las 3 (gratis primero, LLM solo donde agrega):
1. **Tablero ($0)** → estados de cuello. (Los 10-Q del T3 ya están presentados: buen momento.)
2. **Pre-screen determinista ($0) sobre empresas YA en el mapa.** Para merecer un deep: cuello **confirmado o
   "primer hecho"** · **economía propia** (ventas materiales creciendo + margen bruto positivo y estable) ·
   **pureza** (el cuello es parte importante de ventas, no el 10%) · **todavía barata** (el precio exige menos
   crecimiento que el actual: `futuro.py` si corre sin deep, o proxy EV/ventas vs mediana del cuello + retorno
   12m) · **sin ficha reciente.** Ordenar por la **brecha** (crecimiento actual vs el que exige el precio).
3. **Pasada de discovery ACOTADA** (no 142): sobre cuellos **confirmado + adyacentes directos**, con tope de
   propuestas; cada candidato con **evidencia primaria de CAPTURA** (un pedido, cualificación, capacidad
   vendida — no solo mención) + hipótesis de desajuste. Solo si el pre-screen da menos candidatos que deeps
   pagables (para esta tanda, probablemente alcanza con lo del mapa).
4. **Competir:** los candidatos del pre-screen y del discovery compiten por los deeps (evidencia + mispricing
   + relevancia cartera + valor de la info faltante).
5. **Deeps en TRAMOS** (~$20 → mirar cuántos llegan a zona de compra → ajustar el pre-screen → usar el resto).
   No reservar de antemano un monto fijo por origen.
6. **Registrar todo** (incluido lo rechazado, con precio del día).

**Principio:** el deep PRUEBA una hipótesis que los números ya sugieren, no descubre. Un deep sobre una empresa
cuyo precio ya exige crecimiento heroico es plata tirada: el PM va a decir que no igual. *(Si el mapa MVP aún
no corrió, el pre-screen va solo con economía propia + valuación: peor que con estados de cuello, pero mucho
mejor que elegir por narrativa.)*

## 9. El orden mínimo de build
0. **(Prerrequisito) Mapa MVP (doc 89)** — sin estados de cuello, el mapa no dirige al discovery.
1. **Registro de propuestas** (append-only, con precio/fecha, incluye rechazados).
2. **Pre-screen determinista** para deeps ($0).
3. **Discovery recibe del mapa** la lista de cuellos priorizados (confirmado + adyacente) + tope de propuestas
   + el **prompt nuevo** (hipótesis de desajuste, no "empresas interesantes").
4. **Disparadores (Eje 1):** por evento (señal primaria en cuello confirmado/adyacente) + pasada post-earnings
   + lanzable a mano.
5. *(después del 1er tramo de deeps)* **capa de fuentes primarias no estructuradas** (patentes/contratos/
   empleo/cualificaciones) como disparador — el salto de "consenso" a "antes".
6. *(diferido, opcional)* **screen de huérfanos $0** — solo si el embudo se seca.
7. **Eje 2:** ventana de medición de 20-30 deeps → si la conversión da señal (§6), soltar a **full-auto-drain**.

## 10. El gate (idéntico al mapa, doc 89 §6)
Construir §9 pasos 0-3, correr la primera tanda, y mirar: **¿la conversión triage→deep→zona-de-compra muestra
que el discovery aporta candidatos que el sistema no tenía?** Si de 20 propuestas casi ninguna cambia una
decisión del PM → el discovery propone ruido y se ajusta la política (fuente/foco), NO se le da más autonomía.
Si aporta → se suelta el Eje 2 y se agregan las capas §9 pasos 5-6. **Medir antes de automatizar del todo.**
