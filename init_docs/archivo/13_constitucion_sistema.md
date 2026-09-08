# 13 — Constitución del sistema (Etapa 1 del rediseño)

> 🏗️ **ANDAMIAJE DEL REDISEÑO — ver `00_MAPA_DOCUMENTOS.md`.** Guía de diseño (límites determinista/PM,
> estados, evidencia); se implementa por detrás. ⚠️ "cero tests" (art. 9) es viejo (hoy 276). Estado: doc 32.

> **Qué es este documento.** La "constitución" del sistema reconstruido: define la
> frontera exacta entre datos, reglas deterministas, agentes LLM y Portfolio Manager,
> antes de escribir una línea de código. Es la Etapa 1 del plan (ver
> `12_diagnostico_estado_real.md`).
>
> **Estado:** BORRADOR DE TRABAJO. Se redacta y critica sección por sección (operador
> + IAs de triangulación). Nada se implementa hasta que cada artículo esté cerrado.
>
> **Convenciones:** `PROPUESTA` = valor/criterio que propongo, sujeto a acuerdo.
> `A DECIDIR` = decisión abierta que necesita al operador. `CERRADO` = acordado (se
> marca cuando lo confirmamos).
>
> **Secuencia acordada (revisada 2026-07):**
> `0 Congelamiento · 1 Constitución (acá) · 2 Ledger/fuente de verdad · 3 Entrada
> manual + Filtro 0 · 4 Deep research + ficha rica · 5 Universo vivo · 6 PM +
> guardrails · 7 Sparring + aprobación + rotación · 8 Mapa + Discovery auto ·
> 9 Dashboard + desacople + forward test`

---

## Índice de artículos

1. Objetivo del sistema y definición de "funciona perfecto" — *borrador abajo*
2. Universo permitido (qué entra, qué nunca entra) — *borrador abajo*
3. Estándar de evidencia — *borrador abajo*
4. Frontera determinista ↔ Portfolio Manager — *borrador abajo*
5. Estados y ciclo de vida de una empresa — *borrador abajo*
6. Puertas de entrada — *borrador abajo*
7. Reglas de actualización y vigencia — *borrador abajo*
8. Política de errores y fallo seguro — *borrador abajo*
9. Modo shadow y estándar de testing — *borrador abajo*
10. Criterios de cierre de cada etapa — *borrador abajo*
11. Ejecución en paper y contabilidad — *cerrado (triangulado)*

---

## Artículo 1 — Objetivo y "funciona perfecto"

### 1.1 Objetivo
Sistema quant que **analiza y opera (hoy en paper)** small & mid caps de industrias
del futuro, bajo una regla de gobierno única:

> **Los datos y los límites duros son deterministas; el LLM (PM) ejerce criterio solo
> dentro de esos límites.** El LLM nunca inventa números, contratos ni fundamentos.

Filosofía operativa: **disciplina sobre actividad**. Se prefieren slots vacíos y cash
a forzar entradas. No se despliega capital por obligación.

### 1.2 Qué significa "funciona perfecto" `PROPUESTA` (adoptado de la triangulación)
NO significa "nunca elige una acción que caiga" — eso no existe. Significa que el
sistema cumple, siempre, estas propiedades de **fallo seguro**:

1. No inventa información (todo hecho es trazable a una fuente).
2. No opera con datos vencidos sin advertirlo explícitamente.
3. No viola sus propios límites (caps, exclusiones, concentración).
4. No mezcla el sistema viejo en ninguna decisión nueva.
5. No despliega capital por obligación (el piso de inversión no fuerza compras).
6. No cambia la cartera sin una razón registrada.
7. Cada decisión es **reproducible** desde su snapshot (qué sabía, qué versión de
   ficha usó, qué propuso el PM, qué objetó el sparring, qué regla se activó).
8. Cada hecho es trazable a evidencia.
9. Cada módulo falla de manera segura (ante duda: no actuar / degradar, no romper).
10. El comportamiento observado coincide con el comportamiento diseñado.

Estas 10 propiedades se vuelven **invariantes ejecutables** (tests) en la Etapa 9.

---

## Artículo 2 — Universo permitido

Distinción rectora (de la visión original): **interesante para vigilar ≠ apta para
analizar como inversión ≠ apta para cartera.** Este artículo define solo el segundo
conjunto: qué empresa es **admisible para entrar al pipeline de análisis**. El mapa
(Art. 8 del plan) puede vigilar tecnologías más tempranas sin que produzcan candidatas
invertibles.

> Esto NO es el Filtro 0 ni el gate. Es el **filtro de universo**: define quién *puede*
> ser analizado. El Filtro 0 (Etapa 3) decide si *vale la pena* el deep research; el
> gate (núcleo) decide si es *invertible*.

### 2.1 Criterios de admisibilidad
- **Mercado / bróker** `CERRADO`: se opera vía **Interactive Brokers** (acceso a casi
  todos los mercados). Se admite la acción **listada directamente en su bolsa**;
  **NO se admiten ADRs**. (No es "solo EE. UU.": puede ser una small cap listada en su
  bolsa local, siempre operable por IBKR y sin pasar por ADR.)
- **Jurisdicciones permitidas** `CERRADO` (decisión del operador): **EE. UU., Canadá,
  Europa y países de Asia relevantes en tecnología (p. ej. Japón, Corea del Sur, Taiwán).
  China queda EXCLUIDA** (por domicilio/control del emisor, y reforzado por opacidad de
  divulgación / VIEs). *(Nota: la mayoría de las tech israelíes ya cotizan en EE. UU. →
  entran por esa vía; confirmar si se agrega Israel/Singapur como domicilio propio.)*
  - **Anclaje en calidad de información:** cada jurisdicción admitida debe proveer
    divulgación **verificable, primaria y parseable** (grado-EDGAR: estados auditados,
    concentración de clientes, hechos materiales, insiders). Todo el sistema (gate,
    arquetipo, evidencia) **exige información de calidad**; un mercado que no la produce
    **se autoexcluye igual** en el gate (no hay hechos con fuente A).
  - **Política vs. operación (qué significa "ampliable"):** la POLÍTICA permite esas
    jurisdicciones ya. Pero cada mercado necesita su **extractor** propio para operar de
    verdad: hoy solo existe **EDGAR (EE. UU.)**; Canadá (SEDAR+), Europa (reguladores
    nacionales/RNS), Japón (EDINET/TDnet), Corea (DART), Taiwán (MOPS) requieren construir
    su extractor antes. → **Universo operativo hoy = US-listed**; los demás se habilitan por
    etapas, priorizando donde se concentran los cuellos del mapa.
  - *Si reaparecen los docs canónicos con una lista distinta, se reconcilia.*
- **Tamaño** `CERRADO`: **piso ~$50M**, **sin techo** (decisión del operador). Ver 2.3.
- **Liquidez mínima** `CERRADO` (calibrable): **$1M/día** de volumen (constante
  `LIQUIDEZ_SCREENER` ya existente). Filtro de universo, no gate. El número se recalibra
  con tracking; la regla (piso de liquidez en el universo) queda cerrada.
- **Israel / Singapur** `CERRADO`: hoy entran **vía US-listing** (donde cotiza la mayoría
  de sus tech). Sumarlos como domicilio propio se difiere junto con el resto de extractores
  no-US (no cambia nada operativo hoy).
- **Vínculo estructural** `CERRADO`: debe vincularse a un **nodo/territorio del mapa**
  (industria del futuro). Sin vínculo → no es del universo (aunque sea buena empresa).
- **Evidencia de monetización** `CERRADO`: admitir Pre-revenue **solo con evidencia
  contractual firme** (contrato firmado / LOI económica con contraparte y compromiso).
  **Un simple design-in NO alcanza** (ni el técnico, ni uno sin compromiso económico).
  Se excluye la pura promesa / TAM sin hecho comercial citable.

### 2.2 Exclusiones duras (nunca entra) `PROPUESTA` (salvo lo ya `CERRADO`)
- **ADRs** `CERRADO`.
- OTC / pink sheets / no listada en bolsa mayor operable por IBKR.
- SPACs pre-fusión.
- Empresas sin ningún vínculo con el mapa `CERRADO`.
- Emisores de jurisdicción excluida (según 2.1, pendiente de re-enunciar).
- Pura promesa / TAM sin evidencia comercial `CERRADO`.

### 2.3 Sin techo — el filtrado lo hace el pipeline, no el tamaño `CERRADO` (decisión del operador)
**No hay techo de market cap ni exclusión por tamaño.** Si una mega-cap está subvaluada y
puede ser buena inversión, **no se desestima**. El trabajo de filtrar lo hace el
**Filtro 0** (Etapa 3) y la valoración/asimetría aguas abajo, empresa por empresa — no un
corte de tamaño mecánico.

- El foco **small/mid cap** es el **terreno de caza** (donde está el diferencial y donde
  Discovery concentra la búsqueda), **no un muro**. Sesgo, no exclusión.
- El requisito estructural real sigue siendo el **vínculo con un nodo del mapa**
  (industria del futuro): una mega-cap entra solo si es una expresión genuina de un cuello
  **y** pasa el Filtro 0 por mérito/valuación. El tamaño no la admite ni la rechaza; su
  tesis sí.
- Consecuencia: se elimina el corte $2B del screener viejo. El bug histórico (AAPL/IBM
  "colados") no se resuelve con un techo, sino con un **Filtro 0 que evalúe valuación y
  calidad de tesis** (una mega-cap cara y sin asimetría cae ahí, no por su tamaño).

---

## Artículo 3 — Estándar de evidencia

Pilar del sistema. Un LLM no puede afirmar un contrato, un moat, una concentración o
un backlog sin apuntar a evidencia concreta.

### 3.1 Tipos de afirmación `PROPUESTA`
- **HECHO** — evidencia primaria verificable (filing, contrato, transcript), con
  **fuente citable** (documento + fecha + tipo).
- **INFERENCIA** — conclusión razonada a partir de hechos identificados. Se marca como
  tal; nunca se presenta como hecho.
- **HIPÓTESIS** — posibilidad todavía no validada. Explícita, no accionable como hecho.

### 3.2 Campos críticos: lógica de tres valores `PROPUESTA`
Todo campo crítico (concentración de clientes, existencia de contrato, cobertura de
financiación, etc.) admite **TRUE / FALSE / UNKNOWN**. Reglas duras:
- **Nunca** convertir ausencia de información en `False` en el dato.
- **Nunca** convertir una inferencia del LLM en un hecho.

### 3.3 Dos capas — datos vs. decisión `PROPUESTA` (reconciliación con el gate actual)
El gate hoy, a propósito, trata "sin divulgación" como fallo (default-exclude, p. ej.
G1 "sin desglose → falla"). Es una decisión conservadora **correcta**. Para que no
choque con 3.2:
- **Capa de datos:** `UNKNOWN` es `UNKNOWN`. Se persiste como tal. Nunca se coacciona
  silenciosamente a `False`.
- **Capa de decisión:** para *gatear*, un `UNKNOWN` **puede tratarse**
  conservadoramente (como si fallara / default-exclude), pero ese tratamiento es
  **explícito y queda logueado** en la traza. No es una mentira en el dato: es una
  política de decisión visible.

### 3.4 Jerarquía de fuentes `PROPUESTA`
Formalizar la ya usada por el gate: **A** (filing oficial / documento primario),
**B** (fuente secundaria verificable), **C** (fuente débil / con contraparte, admisible
solo en casos definidos). Cada hecho lleva su nivel de fuente.

---

## Artículo 4 — Frontera determinista ↔ Portfolio Manager

El corazón del norte. Contrato estricto + validador determinista posterior.

### 4.1 Lo DETERMINISTA (el sistema calcula; el PM NO puede tocarlo) `PROPUESTA`
- **Elegibilidad** (gate de evidencia por arquetipo): invertible / todavía-no / no.
- **Arquetipo** (Madura / Growth / Tracción / Pre-revenue / Binary).
- **Hard caps de riesgo** (por arquetipo × fragilidad, CRR, techo absoluto = `min()`).
- **Piso y techo de posición** (piso 5 %, techo por cap).
- **Exclusiones** (Art. 2.2) y riesgo de financiación crítico (CRR-crítico → veto).
- **Liquidez** y **concentración** máximas (por sector / factor macro).
- **Triggers de salida** deterministas (governance hard, CRR, vías mecánicas).
- **Vigencia** de fichas y evidencia (vencido no compite con dato desactualizado).
- **Reconciliación del ledger** (caja + shares + equity siempre cuadran).

### 4.2 Lo que decide el PM-LLM (dentro de esos límites) `PROPUESTA`
- **Inclusión:** sí/no de cada empresa **elegible** (no puede incluir no-elegibles).
- **Peso:** cualquier valor en **[piso, hard cap]** de esa posición.
- **Timing, priorización, rotaciones propuestas** (con motivo registrado). El **nivel de cash
  lo fija el operador** (4.7); el PM despliega el resto.
- Todo con **criterio contextual**: macro (lectura del LLM), sector, correlaciones, costo de
  oportunidad (marcado como lectura, no como hecho).
- **El PM EXPLICA su cartera:** por qué entra cada empresa/sector/driver, y también **las que
  quedaron afuera y por qué** (sus drivers). El operador ve esa explicación y **puede
  intervenir** (hacerle cambiar algo) antes de aprobar.

### 4.3 Lo que el PM NO puede hacer (invariantes duros) `PROPUESTA`
Alterar hechos · superar un cap · ignorar una exclusión · usar evidencia vencida ·
violar concentración · operar sin preflight · inventar un ticker fuera del conjunto
elegible.

### 4.4 Validador determinista posterior `CERRADO` (corrección del operador)
**Toda** salida del PM pasa por un validador determinista **antes de tocar el ledger**.
**El validador NO modifica silenciosamente la propuesta del PM.** Ante cualquier
violación de 4.1/4.3 (cap superado, exclusión ignorada, ticker no elegible, evidencia
vencida, concentración violada, etc.):

> **rechazar propuesta → informar los errores concretos → el PM genera otra.**

El validador nunca "recorta y sigue": la propuesta inválida se devuelve entera con el
detalle del incumplimiento y el PM re-propone con esa información. Bucle acotado de
re-intentos (`A DECIDIR`: N máximo); si tras N intentos sigue inválida → **no se opera**
esa vuelta y queda registrado (fallo seguro, Art. 8). Así la frontera es *enforced* y
además **auditable**: nunca hay una cartera "arreglada por la máquina" que el PM no pidió.

### 4.5 Macro y concentración `CORREGIDO` (anclado en el código)
**Lo que YA existe (se conserva):**
- **Cap de concentración por SECTOR:** `MAX_POR_SUBSECTOR = 3` (sobre `Ficha.sector`), ya
  enforceado en el deploy del paper. **El sector es la unidad de cap establecida.**
- **`factor_macro`** (capex hyperscaler / defensa / export-control) es hoy una **etiqueta de
  VISIBILIDAD, NO decisoria** (código: *"NUNCA entran a una fórmula"*); se muestra al operador
  en el pre-flight antes de confirmar.

**Decisiones (tuyas):**
- **El macro lo LEE el LLM** (coyuntura + datos verídicos con fuente) → alimenta al PM como
  **contexto** (postura por sector/driver). NO una tabla estática ni una predicción del LLM que
  bloquee una empresa.
- **El macro solo APRIETA, nunca AFLOJA:** viento a favor = contexto (inclusión/timing/
  desempate), nunca sube un cap. Viento en contra documentado (export-control, fin de subsidio,
  arancel) sí puede recortar.

**Decidido `CERRADO` (operador):**
- Se agrega un **factor-cap**: tope de **% de cartera** expuesto a un mismo factor macro,
  **adicional** al cap por sector (no lo reemplaza). Ataca el caso que el cap por sector NO ve
  (datacenter + energía + semis-upstream + fotónica cuelgan todos de "capex hyperscaler", el
  riesgo de concentración más fuerte del mapa). Se promueve `factor_macro` de etiqueta visible a
  **cap duro**, vía la tabla ticker→factor versionada. El % concreto = calibrable.

### 4.6 Mérito y sizing `CORREGIDO` (anclado en el código)
**Lo que YA existe (se conserva):** los **caps de tamaño por riesgo ya están** —
`CAPS_ARQUETIPO_FRAGILITY` (celda arquetipo × fragilidad) + `hard_cap = min(cap_celda, cap_CRR,
techo)` + piso 5 %. **Esto manda y se queda tal cual.** El riesgo ya limita el tamaño.

**Ajuste `CERRADO` (operador):** se **desacopla** el reparto proporcional. El mérito **ordena**
(rankea); el **tamaño lo elige el PM-LLM dentro de [piso, hard cap]** — el LLM juega adentro del
rango, un cambio marginal de score ya no mueve todos los pesos. La asimetría cruda sin techo se
**winsoriza ~5:1**. **Los caps por riesgo no se tocan** (ya existen y mandan). *(Probabilidades
deterministas / Kelly: diferido, no v1.)*

### 4.7 Política de cash `CERRADO` (decisión del operador)
- **El nivel de cash lo fija y lo cambia el OPERADOR.** El resto se despliega. *(El código ya
  tiene `OBJETIVO_INVERTIDO`/`TOPE_INVERTIDO`; se reemplaza el "piso 70 % / techo 100 %" por un
  parámetro que setea el operador.)*
- **No se fuerza un mal negocio, pero el objetivo es estar comprado:** el sesgo es a deployment;
  si parte del capital no encuentra nada que califique, queda en cash (por encima del objetivo)
  hasta que aparezca — no se compra por obligación.
- Instrumentación liviana: si el cash queda alto por N ciclos, se reporta **qué gate rechazó a
  cada candidato** (diagnóstico de calibración) y se trackea el **cash drag**. En paper se
  acredita **tasa libre de riesgo** al cash.

### 4.8 Exposición por factores y clusters de dependencia `CERRADO` (triangulado)
Control de correlación **estructural primero, estadística como auditor** (no al revés):
- **(a) Caps por factor** (4.5): el validador suma exposiciones por factor y aplica caps.
- **(b) Grafo de dependencias documentadas** (de HECHOS citados, no de retornos): cliente
  final compartido, proveedor único compartido, misma fab/mina, misma aprobación regulatoria,
  mismo nodo, mismo driver de ingresos. **Un conjunto que comparte una dependencia crítica se
  trata como UNA sola posición para el cap** (esto sí captura "la misma apuesta"; el cap
  sectorial no). Incluir explícito el cluster **"ventana de capital"** (todos los pre-revenue/
  binary comparten que la financiación siga abierta).
- **(c) Chequeos de cartera:** stress test determinista ("un cluster entero cae 40 %, ¿cuánto
  pierde el NAV?") vs. límite duro; **cap de nombres por cluster** con **default de no
  redundancia** (dos nombres del mismo cluster → el mejor, no los dos, salvo razón específica).
- **Estadística = tripwire, no driver (diferido/alerta):** correlación rolling de residuos
  (sacando mercado y sector) como **alerta** para que el PM explique o se agregue una arista —
  nunca control principal (en small caps de historia corta la covarianza es ruido).

---

## Artículo 5 — Estados y ciclo de vida de una empresa `PROPUESTA` (borrador)

Una empresa es una entidad viva con un estado explícito en el ledger. Toda transición
queda registrada con **quién la disparó** (regla determinista / PM / humano), **motivo**,
**evidencia**, **timestamp** y **versión de ficha**. Nada cambia de estado en silencio.

### 5.1 Estados
1. **Candidata** — ingresada (manual o Discovery), aún sin Filtro 0.
2. **Descartada** — el Filtro 0 dijo NO (con motivo). No terminal: revive si aparece un
   hecho nuevo en su nodo.
3. **Esperando-evidencia** — el Filtro 0 dijo "esperar un hecho concreto" (casi, pero
   falta un catalizador/hecho citable). Vigilada por su nodo.
4. **En-deep-research** — el Filtro 0 dijo "investigar"; research en curso.
5. **Elegible** — pasó deep research + gate; tiene **ficha rica comparable**. Apta para que
   el PM la considere.
6. **Watchlist (universo vivo)** — elegible que el PM no eligió. Sigue viva, se actualiza y
   **re-compite** en cada revisión.
7. **Posición** — en cartera (paper).
8. **Tesis-invalidada** — una vía de salida / re-gate la sacó de posición.
9. **Archivada** — nodo resuelto/archivado o ficha sin vigencia; fuera del monitor.

### 5.2 Transiciones y quién las dispara
- `Candidata → Descartada | Esperando-evidencia | En-deep-research` — **Filtro 0**
  (determinista + LLM barato).
- `En-deep-research → Elegible | Descartada | Esperando-evidencia` — **deep research + gate**
  (gate determinista; "todavía-no" por timing → Esperando-evidencia).
- `Elegible → Posición` — **PM** propone + validador + **aprobación humana**.
- `Elegible → Watchlist` — el PM no la eligió (queda viva).
- `Watchlist ↔ Elegible` — re-compite cada revisión; el PM puede promoverla a Posición.
- `Posición → Tesis-invalidada` — salió porque la **tesis se rompió** (gate/re-gate,
  trigger de invalidación, governance hard, CRR-crítico). No vuelve a Watchlist.
- `Posición → Watchlist` — salió por una razón que **NO invalida la tesis** (precio /
  asimetría agotada, recorte por concentración, o rotación por mejor oportunidad / costo de
  oportunidad) **y la tesis sigue vigente** → vuelve al universo vivo y **re-compite**.
- `* → Archivada` — nodo archivado / ficha sin vigencia (Art. 7).
- `Descartada | Archivada → Candidata (fría)` — aparece **hecho nuevo** en su nodo (no se
  pierde la 2ª/3ª ola).

### 5.3 Reglas duras
- El **vínculo empresa↔nodo NUNCA se borra** al salir/archivar (preserva olas futuras).
- Una ficha **vencida no compite** con información desactualizada (Art. 7).
- Toda posición nace de: Elegible → PM → validador → aprobación. **No hay atajos** a
  Posición.
- **Re-entrada tras tesis invalidada:** un nombre que salió por **tesis rota** solo vuelve como
  **Candidata nueva** si aparece una **tesis reconstruida o nueva** (hecho documentado); arranca
  de cero (Filtro 0 → research → gate). Límite: **una sola re-entrada** por nombre (Candado B)
  para no rebotar sobre el mismo perdedor.
- **Re-evaluación de Descartada — por NODO, no por empresa (límite de costo):** no se monitorea
  cada descartada individualmente. Sigue en la base **tagueada** (estado + motivo del rechazo) y
  **vinculada a su nodo**. Cuando el discovery/monitor detecta un **cambio en su nodo** (nuevo
  catalizador, transición de estado, se pone caliente), **re-emite las empresas vinculadas —
  incluidas las descartadas— a un re-chequeo BARATO del Filtro 0** (determinista, sin LLM). El
  LLM solo corre detrás del Filtro 0. Una empresa que necesite seguimiento propio va a
  **Esperando-evidencia** (vigilada por su hecho puntual) o la re-ingresa el operador a mano.

---

## Artículo 6 — Puertas de entrada `PROPUESTA` (borrador)

### 6.1 Dos puertas, una sola cantera
- **Manual:** el operador ingresa un ticker (lo descubrió, se lo recomendaron, le interesa).
- **Discovery:** el sistema lo propone desde el mapa por hechos económicos (Etapa 8).

**Ambas convergen en la MISMA puerta:** crean una **Candidata** que entra al **mismo
Filtro 0**. *Discovery descubre; no selecciona.* No hay atajo: un candidato de Discovery
**no** se auto-promueve más allá de Candidata (esto corrige el problema actual, donde el
discovery viejo genera hipótesis que nadie convierte y el nuevo no filtra).

### 6.2 Contrato de ingreso
Una Candidata se crea con: `ticker`, `fuente_ingreso` (manual/discovery), `timestamp`,
`quién`, y **vínculo tentativo a un nodo** del mapa (obligatorio — sin vínculo no es del
universo, Art. 2).

### 6.3 Filtro de universo en el ingreso
Al ingresar se aplica el **filtro de universo** (Art. 2): jurisdicción permitida, listada y
operable por IBKR (no ADR), liquidez ≥ $1M/día, vínculo con nodo. Si no cumple → no se crea
Candidata (o se registra como Descartada con motivo "fuera de universo"). El **Filtro 0**
(mérito de investigar) es el paso siguiente, distinto de este.
- **Candidata sin nodo existente:** si es de una **industria relevante**, se **crea el nodo**
  (se actualiza el mapa versionado) y la candidata sigue. Si el sector **no sirve**, se
  **descarta**. No queda en limbo.

### 6.4 Idempotencia
Si el ticker ya existe en cualquier estado, **no se duplica**: se actualiza o re-activa
según su estado (p. ej. Archivada + hecho nuevo por Discovery → Candidata fría, 5.2).

### 6.5 Naturaleza del Filtro 0 `CORREGIDO` (anclado en el código)
**Lo que YA existe (se conserva y se refuerza):** `agents/descubrimiento.py` ya tiene un
**screener de 5 filtros reales** (market cap, crecimiento >20 %, margen bruto >30 %, deuda/rev
<2x, volumen >$1M) que crea Candidatas. **Ese es el Filtro 0 base — sustantivo, no esquelético.**

**Decisiones:**
- **Determinista, sin LLM en el pipeline** (el pre-screen busca recall; un LLM mete varianza
  invisible). El vínculo ticker → nodo NO se resuelve con LLM en runtime: **artefacto versionado**
  (el LLM ayuda a construirlo offline, con fuente; runtime lo consulta determinista).
- **Refuerzos sobre lo existente:** datos **point-in-time** (evita look-ahead / survivorship) y
  **loguear cada rechazo** con el criterio y el valor que falló.
- El juicio "¿evidencia real o marketing?" NO vive acá: va al deep research/gate (Etapa 4).
- El detalle fino de umbrales se cierra en la **Etapa 3**, partiendo de los 5 filtros que ya están.

---

## Artículo 7 — Reglas de actualización y vigencia `PROPUESTA` (borrador)

Una ficha no es una foto: es un objeto **vivo y fechado**. Envejece, y se actualiza por
**hechos**, no solo por reloj.

### 7.1 Disparadores de actualización
- **Hechos nuevos** (crean versión de ficha, 7.4): earnings · contrato/orden material ·
  capital raise / dilución · cambio de guidance · **cambio de estado del nodo** · trigger
  específico de la tesis. Cada uno gatilla una **actualización incremental**.
- **Input vivo** (recomputa, NO versiona): el **precio** alimenta de forma continua la
  asimetría, el sizing y las vías de salida 4/5, **sin crear una versión por cada
  movimiento**.

### 7.2 Actualización incremental (no re-research desde cero)
Se **re-extraen solo los hechos afectados**, pero se **recalculan TODOS los resultados
dependientes** (arquetipo, gate, Quality, mérito, asimetría, fragilidad, caps, vías de
salida) — ninguna conclusión derivada queda vieja. Ni se re-investiga todo desde cero, ni
se congelan conclusiones. Barato y trazable.

### 7.3 Vigencia — una ficha vencida no compite
Una ficha está **vencida** si: (a) supera su edad máxima para su arquetipo/volatilidad, o
(b) ocurrió un hecho material posterior a su última actualización aún no incorporado.
**Una ficha vencida no puede entrar a Posición ni competir en el PM** con información
desactualizada: primero se refresca (7.2) o se marca y se excluye de la selección hasta
refrescar (extiende el pre-flight de staleness ya existente).

### 7.4 Versionado y frescura del nodo
- Cada actualización **por hecho** crea una **nueva versión** de la ficha; toda decisión
  referencia la versión que usó (reproducibilidad, Art. 1.2). Cada hecho lleva su **fecha y
  fuente**. El **precio NO versiona** (es input vivo, 7.1): se marca de forma continua sin
  generar versiones.
- El **nodo** tiene su propia frescura por estado (confirmado 14d / promesa 10d / caliente
  2d — ya en `mapa/discovery.py`). Un hecho en el nodo puede vencer fichas vinculadas.

### 7.5 Cadencia operativa `PROPUESTA` (frecuencias calibrables)
El PM **no** se reconstruye todos los días (ruido, costo, rotación innecesaria). Tres
ritmos:

**Diario — precios y riesgos (determinista, $0 LLM). NO reconstruye cartera.**
- Actualiza precio, pesos, P&L, asimetría vigente y alertas.
- Evalúa las **salidas URGENTES deterministas** (governance hard, CRR-crítico, trigger de
  invalidación disparado). Estas **no esperan al PM semanal**: pueden gatillar (con
  aprobación, Art. 8/9) el mismo día.

**Semanal — PM completo (principal costo LLM).**
- El PM compara **posiciones actuales vs. todo el universo elegible** y propone.
- **Correr ≠ operar:** el PM puede (y muchas semanas debe) concluir **"mantener cartera
  actual: no hay mejora suficiente que justifique rotar"**. Ese es el resultado **normal**.
  Toda propuesta pasa por validador → sparring → aprobación.
- **Frecuencia de corrida ≠ frecuencia de decisión:** correr semanal da **muestra para
  calibrar al PM**; para que la varianza de muestreo del LLM no se vuelva turnover, el peso
  solo cambia si la mejora **supera una banda de histéresis** (se calibra en Etapa 7).

**Por evento material — PM extraordinario (fuera de ciclo).**
- Dispara re-derivación de la ficha afectada (7.2) y un pase del PM, que puede ser
  **acotado** (la afectada + su competencia directa) o completo según el impacto.
- **Eventos materiales:** earnings · contrato relevante · dilución / nueva deuda · cambio de
  guidance · cambio importante de management · trigger de tesis (estos disparan revisión
  **independientemente del precio**) · **movimiento fuerte de precio: ±15 % en un día O ±20 %
  acumulado en 3 ruedas (calibrable)**.

**Mensual — contexto ampliado.** Revisión de macro, sectores, concentración y narrativa.
Puede ser **el mismo PM semanal con más contexto**, no un motor aparte.

**Regla simple:** precios/riesgos = diario · PM de cartera = semanal · PM extraordinario =
ante evento material.

**Rotación deliberada:** "otra acción con mérito marginalmente superior" NO gatilla rotación
automática (hay costo y churn); sí lo hacen invalidación, riesgo, concentración o costo de
oportunidad **material** (banda de histéresis, se calibra en Etapa 7).

---

## Artículo 8 — Política de errores y fallo seguro `PROPUESTA` (borrador)

Principio: **ante la duda, no actuar** (o degradar), **nunca romper ni inventar**.
Coherente con "disciplina sobre actividad": el default es **inacción** (hold / slot vacío /
cash), no una acción forzada o incierta.

### 8.1 Por tipo de falla
- **Dato faltante / UNKNOWN:** nunca se coacciona a `False` en el dato; la decisión lo trata
  conservadoramente y lo **loguea** (Art. 3.3).
- **Fuente caída** (EDGAR / mercado / feed): se admite usar **caché todavía vigente**
  (dentro de su vigencia, Art. 7.3), pero **nunca información vencida**. Si no hay caché
  vigente → el módulo **se abstiene** para ese ticker/ciclo y lo registra. Nunca opera sobre
  datos vencidos ni inventa (sin precio vigente → no marca; sin EDGAR y ficha vencida → no
  refresca, queda marcada vencida).
- **LLM no responde / responde inválido** (schema roto, hecho sin fuente): re-intento
  acotado; si falla → **se abstiene y loguea**. Nunca se acepta un hecho no citado o no
  parseable.
- **PM inválido tras N re-intentos** (Art. 4.4): no se opera esa vuelta; queda registrado.

### 8.2 Atomicidad y visibilidad
- **Sin escrituras parciales:** una decisión commitea entera con su traza, o no commitea.
  El ledger nunca queda a medias.
- **Degradaciones visibles:** toda falla/abstención queda en el ledger y el operador la ve.
  Nada se degrada en silencio.

---

## Artículo 9 — Modo shadow y estándar de testing `PROPUESTA` (borrador)

### 9.1 Modo shadow (obligatorio para módulos decisorios / que escriben estado)
El modo shadow es **obligatorio para todo módulo que decide o que escribe estado** (Filtro 0,
PM, validador, vías de salida, ledger) — **no** para cada función auxiliar o de solo lectura.
Durante su construcción/calibración, el módulo **propone, registra y explica** pero **no toca
ni la cartera paper** hasta que se apruebe su comportamiento. Progresión de autonomía:

`shadow (sin escribir) → paper con aprobación humana → [más adelante] paper autónomo →
[política aparte] capital real`

### 9.2 Invariantes ejecutables (las 10 propiedades del Art. 1.2 hechas test)
- Filtro 0 **determinista**: mismos inputs → mismo resultado.
- Extractor: no devuelve un hecho **sin fuente**; `UNKNOWN` se preserva.
- PM: **no** excede un hard cap; **no** inventa un ticker fuera de los elegibles;
  **pesos + cash = 100 %**.
- Validador: **rechaza** toda violación; **no** modifica en silencio.
- Preflight: **ninguna** orden se ejecuta si el preflight falla.
- Vigencia: una ficha **vencida no compite**.
- Ledger: **reconcilia** caja + shares + equity siempre.
- Aislamiento: **ningún job viejo** modifica el universo/ledger nuevo.
- Reproducibilidad: cada decisión se **re-deriva** desde su snapshot.

Un módulo no está "hecho" hasta que sus invariantes pasan (tests, no aspiración).

---

## Artículo 10 — Criterios de cierre de cada etapa `PROPUESTA` (borrador)

Ninguna etapa avanza sin una **definición de terminado** explícita y simple:
1. **Comportamiento acordado.**
2. **Invariantes aprobados.**
3. **Shadow satisfactorio.**
4. **Documentación actualizada.**

### Definición de "hecho" por etapa
- **0 Congelamiento:** ambos libros viejos congelados read-only; sin decisiones automáticas
  nuevas; 18 jobs inventariados; backups; acople viejo↔nuevo etiquetado.
- **1 Constitución:** los 10 artículos acordados.
- **2 Ledger:** esquema construido; reconcilia; reproducible; ningún write del sistema viejo.
- **3 Entrada manual + Filtro 0:** un ticker ingresado a mano recorre el Filtro 0 de forma
  determinista con resultado logueado; invariantes pasan.
- **4 Deep research + ficha:** produce ficha **comparable y citada**, con tipos de evidencia
  (HECHO/INFERENCIA/HIPÓTESIS), **sin score 0-10**; actualización incremental funciona.
- **5 Universo vivo:** estados + versionado + re-competencia operativos.
- **6 PM + guardrails:** el PM propone dentro de los límites; el validador enforcea (Art. 4.4);
  loop de aprobación; invariantes pasan.
- **7 Sparring + aprobación + rotación:** sparring ataca; rotación de 3 cadencias; nada llega
  a paper sin aprobación.
- **8 Mapa + Discovery:** mapa persistido/versionado; Discovery alimenta el **mismo** Filtro 0.
- **9 Dashboard + desacople:** vistas nuevas; cortado el cordón `Ficha.estado`; jobs viejos
  apagados; forward-test con métricas reales.

---

## Artículo 11 — Ejecución en paper y contabilidad `CERRADO` (triangulado)

### 11.1 Precio de fill
**Sesión siguiente, al menos 30 minutos después de la apertura** (para que el mercado se
acomode), nunca el cierre del mismo día de decisión (usar ese cierre es look-ahead — la fuente
nº 1 de alpha fantasma en paper). Ej.: el PM decide tras el cierre del lunes → fill el martes
~30 min post-apertura.

### 11.2 Costos modelados (no idealizados)
- **Slippage:** se modela, no se idealiza. v1 simple y **configurable**: medio spread + ~25 bps
  por lado (conservador). Mejorable luego con un término de impacto `k·(valor_orden/ADV)^0.5·σ`.
- **Comisiones:** **tabla versionada por venue** (verificar contra el schedule vigente de IBKR;
  US por acción con mínimos/tope %, Europa a menudo % del valor). Segundo orden frente al
  slippage en small caps, pero se incluyen: penalizan turnover (conducta a disciplinar).
- **Tasa libre de riesgo** acreditada al cash (4.7).

### 11.3 Cap de participación sobre ADV — alimenta el SIZING
Límite duro, probablemente **el más vinculante** en este universo: ninguna orden supera
**~10-15 % del ADV** diario. Por lo tanto **posición máxima ≤ participación % × ADV ×
días_de_construcción**. **Retroalimenta el sizing** (4.6), no solo la ejecución. (Ej.: 2 % en
una cartera de $10M sobre un nombre de $1M ADV = $200k = 20 % del ADV → varios días de
construcción.)

### 11.4 Realismo de mercado
Sin fills en **halts / limit-up**; los **gaps atraviesan stops** (un stop ejecuta en la
apertura si el gap lo salta) — afecta directo a las 5 vías de salida.

### 11.5 Reproducibilidad y doble P&L
Por cada fill se registra: timestamp de decisión, timestamp del dato usado, precio, slippage,
comisión, cantidad de acciones, cash resultante y **hash del estado de entrada**. Se llevan
**dos series de P&L**: **ideal** (apertura, sin costos) y **modelada**; su diferencia es la
**atribución de costo de ejecución**.

### 11.6 Corporate actions
El ledger las aplica de forma **determinista** desde un feed de corporate actions y loguea cada
una (sin esto el P&L y la reconciliación se rompen):
- **Split / reverse split:** ajusta acciones y costo unitario; sin impacto en P&L.
- **Dividendo:** acredita cash; se registra como retorno.
- **M&A / adquisición:** se reciben cash y/o acciones → cierra o convierte la posición y realiza P&L.
- **Delisting / quiebra:** marca la posición a valor de recupero (o cero) y **fuerza la salida**.

---

## Artículo 12 — Refinamientos del análisis `COMPROMETIDO` (se implementa en Etapa 4)

Dos mejoras al análisis por empresa, identificadas al auditar el núcleo. No cambian la
estructura (gate / motores / caps); afinan los **inputs**, que hoy son la parte más blanda.

### 12.1 Disciplinar el bull/bear (la asimetría)
Bull y bear **no son targets libres del LLM**. Se derivan:
- **Fundamento citado** (revenue documentado, backlog, contrato firmado, unit economics) ×
  **múltiplo justificado** (rango de pares / histórico, no inventado) = precio objetivo.
- **Bull:** solo con **hechos ocurridos** (dieta anti-IONQ, ya existe). **Base:** trayectoria
  actual. **Bear:** downside sobre riesgos documentados + stress de balance.
- El LLM **propone los inputs con fuente**; un paso determinista **computa** el target
  (fundamento × múltiplo). Asimetría **winsorizada ~5:1**.
- Regla dura: **ningún bull/bear sin (hecho + fuente) × (múltiplo + justificación)**. Nada de
  price targets desnudos. *(Es la pata más blanda del sistema hoy — la que maneja el sizing.)*

### 12.2 Durabilidad del cuello (dimensión de primera clase)
La tesis es "cuellos de botella" → analizar explícito **por qué el cuello no se replica ni se
sustituye, y por cuánto tiempo**:
- **Inputs (con fuente):** barreras a nueva oferta (capex, lead-time para sumar capacidad,
  IP/moat regulatorio, ciclos de calificación); riesgo de sustitución (¿tecnología alternativa?);
  **vida útil del shortage** (estructural vs. cíclico vs. transitorio).
- **Dónde entra:** un **piso de durabilidad en el gate** (cuello sin evidencia de durabilidad +
  shortage transitorio → "todavía-no" o tier menor) **y** durabilidad sumando a Quality.
- Se conecta con el estado del nodo del mapa (confirmado / debilitándose), llevándolo al nivel
  empresa. Caso testigo: el CDMO de GLP-1 archivado cuando la FDA declaró resuelto el shortage —
  tesis muerta por falta de durabilidad.

---

*Constitución completa. Artículos 1–12 **acordados con el operador**; finos triangulados con dos
IAs (2026-07). Comprometido para Etapa 4: refinamientos del análisis (Art. 12). Diferido (no v1):
probabilidad determinista + Kelly (4.6), correlación estadística como driver (4.8). Próximo paso:
Etapa 2 — fuente de verdad + ledger, que ya debe incorporar el Art. 11.*
