# 79 — Brief de triangulación (r8): cómo BORJA elige universo, mapea, monitorea, prioriza, investiga, RECUERDA y decide

> **Para triangular (2-3 IAs independientes de alta calidad).** El operador: el diseño ACTUAL de todo este
> subsistema "pega en el palo" y es lo más importante. NO es un bug — es el rediseño del *sistema operativo de
> investigación y portfolio*. El brief cubre el DOMINIO COMPLETO (no solo los ejemplos del operador), con el
> estado real verificado + los huecos + las preguntas de diseño por área. Convergé en un DISEÑO, no en código.
> Secuela de los docs 76 (embudo), 74 (Tier B/valuación), 72 (calidad). Fecha: 2026-11-12.

## 0. Marco que NO cambia
- BORJA = PM de IA: agentes investigan/verifican/auditan, el **PM-LLM decide** nombres y tamaños; el
  determinismo informa (datos, cálculos, señales) y limita (IPS, presupuesto). **El PM no tiene web.**
- Universo: small/mid caps de industrias del futuro (AI infra, nuclear/energía, defensa, commodities, espacio,
  robótica, biotech, fotónica, semis). Rango $150M–$60B. Tope 160. Presupuesto LLM ~$40/mes (revisable).
  Advisory (el humano ejecuta). Tesis power-law.
- Principios: hecho verificado ≠ declarado (procedencia + known_at); nada de price targets libres;
  disciplina de costo (barato/determinista para monitorear, caro/LLM solo donde agrega); implementabilidad
  como gate (solo lo sourceable+extraíble+computable hoy; el resto se difiere con criterio).

## 1. El disparador (en palabras del operador)
1. **El deep research tiene que ser para las MEJORES OPORTUNIDADES, no para eventos.** El evento debe ser pre/
   post para la **cartera activa**; una acción que NO tengo no la compro antes de earnings por el precio (los
   fundamentals nuevos recién vienen con el filing). "Necesito poder GENERAR una priorización y entender cómo
   se maneja todo."
2. **Memoria de oportunidad (CRÍTICO).** "Analizo a fondo una acción buenísima pero cara; a los 2 meses cae y
   ahora SÍ es compra: ¿lo toma el sistema? ¿Dónde vive esa memoria? ¿Hay fichas por acción que el portfolio
   revise todo el tiempo?" (y el inverso: la tengo y se puso cara → recortar).
3. **Búsqueda activa + universo + memoria de discovery + mapa + info del PM.** ¿Criterio de reemplazo? Si una
   sale y a los 3 meses está regalada, ¿discovery lo recuerda? Si sale sin cambiar fundamentals, ¿lo recuerda
   para no re-ingresarla? ¿Quién arma el mapa de sectores/cuellos/picks-and-shovels y cómo? ¿Las posiciones
   tienen seguimiento continuo o semanal? El PM necesita info de acción + industria + sector + historia +
   proyecciones + capacidades, bien hecha y actualizada: ¿quién se la da si no tiene web? ¿Qué del universo
   seguimos: solo precio? ¿De los deep queda el core y actualizamos solo en earnings?

---

## 2. El dominio, área por área: ESTADO real · HUECOS · PREGUNTAS

### A. Universo (membresía)
- **Hoy:** rango $150M–$60B (gigantes >$60B comprables con cap 10%); liquidez no filtra (solo pct_adv_max);
  tope 160; reemplazo DIRECTO al llenarse (`elegir_a_archivar`: descartado → analizado-viejo-sin-valor →
  nunca-analizado); altas por discovery (agente) o seeds. Sin tiering interno (todos "candidatos").
- **Huecos:** reemplazo optimiza rotación, no CALIDAD; sin memoria de nombres que salieron; sin niveles
  (núcleo vigilado vs cola larga que solo se screenea barato).
- **Preguntas:** ¿criterio de reemplazo por calidad? ¿tiering del universo (ej. 20 vigilados de cerca + cola)?
  ¿160 es el número? ¿el universo lo define el MAPA (cuellos) o el screening bottom-up?

### B. El mapa (sectores / cuellos / picks-and-shovels)
- **Hoy:** **seed de una sola vez** del repo Sistema-Quant (`backend/seed/sistema_quant/`: bottlenecks + evidence
  + ~246 empresas); altas incrementales de cuellos nuevos que valida el **Map Curator** (agente, ≥2 fuentes
  primarias); cada cuello tiene estado (promesa/vigilancia/confirmado). El Macro memo trae `cuellos_prioridad`
  por ciclo. **Nadie re-investiga/actualiza el mapa, las proyecciones de sector, el TAM ni las capacidades.**
- **Huecos:** mapa estático; sin inteligencia de sector viva (dinámica competitiva, quién gana el cuello,
  proyecciones, capacidad instalada); el "picks-and-shovels" no se re-evalúa.
- **Preguntas:** ¿quién mantiene el mapa vivo (agente dedicado tipo "Analista de sector"), con qué cadencia y
  evidencia? ¿cómo se versiona y cita? ¿cómo el mapa DRIVE el universo y la priorización (top-down)?

### C. Monitoreo continuo (barato, determinista) — ¿qué seguimos entre deeps?
- **Hoy (lo que YA tenemos barato):** precio (z normalizado por sector), filings nuevos (EDGAR, ítems
  materiales), **insider Form 4** (compra/venta a mercado en USD, cacheado 24h), **news/RSS** (Yahoo+Google con
  keywords de red flag: "restatement", "guidance cut"…), fundamentals XBRL en el ciclo. En la práctica, entre
  deeps lo VIVO es **precio + filings + insider + news**.
- **Huecos:** no hay un "latido" por nombre que consolide estas señales en un estado; los deltas de fundamentals
  (guidance, backlog/RPO, acciones) no se vigilan de forma continua; short interest / opciones no están.
- **Preguntas:** ¿cuál es el SET MÍNIMO de señales a seguir continuamente por nombre (precio + insider + news +
  Δfilings) sin gastar LLM? ¿qué dispara una revisión? ¿cadencia (diaria/continua vs semanal)?

### D. Triage / priorización (qué merece el deer caro)
- **Hoy:** señales deterministas → `triage.prioridad` 0-3: nunca-analizado · materialidad (Haiku) · evento
  ≤14d · **+1 si barato en su cuello** · posición (≥2) · evento fuerte (=3). El deep lo seleccionan los
  CARRILES del embudo (forzados/precio/pre-earnings/cupo). → **el deep lo mandan los EVENTOS; la oportunidad es
  solo un +1.**
- **Huecos:** no hay un carril de OPORTUNIDAD con cupo propio; el pre-earnings mete NO-posiciones (no tiene
  sentido: no comprás por precio antes del earnings y los fundamentals llegan con el filing); el score de
  oportunidad es pobre (solo percentil de valor).
- **Preguntas:** ¿cómo se define "las mejores oportunidades" (score determinista = valuación × calidad del
  cuello × momentum de fundamentals × asimetría)? ¿cuánto del score es determinista y cuánto juicio LLM?
  ¿cómo compiten oportunidad vs evento por el presupuesto? ¿cómo se evita el gaming y el deep-value trap? ¿el
  evento pre/post se restringe a la cartera activa?

### E. Deep research (el comité)
- **Hoy:** Analista (Opus+web) → Bear (Sonnet+web) → Verificador (determinista) producen un **Dossier** rico:
  claims con cita/known_at/refs numéricas; clasificación de invertibilidad; bull/bear independientes
  contrastados con calculadoras; **escenarios bull/base/bear** (métrica terminal, múltiplo, prob, ancla de tasa
  base); **falsador fechado**; red flags; posición en el cuello; "qué exige el precio". Costo ~$0.68/nombre.
- **Huecos:** el disparo es por evento, no por oportunidad (ver D); el "qué exige el precio" no se traduce en un
  GATILLO accionable guardado (ver F).
- **Preguntas:** ¿cuáles son los CRITERIOS para gastar un deep? ¿qué del dossier es "core" que persiste vs qué
  se actualiza barato? ¿cuándo re-correr el comité entero vs un refresh parcial?

### F. MEMORIA VIVA — ficha por acción (el núcleo del rediseño)
- **Hoy:** el dossier se cachea por **hash del data pack que EXCLUYE el precio** + TTL 35 días. Un filing nuevo
  re-analiza; **una caída de precio NO refresca el dossier.** Una caída grande (z≥2.5 / −25%) re-dispara un deep
  DE CERO vía el embudo; una caída moderada no dispara nada. **NO existe "comprar si cae de $X" guardado y
  vigilado**, ni "vender si sube de $Y"; el falsador es por fecha/evento, no un gatillo de valuación. **No hay
  fichas vivas que el portfolio revise continuamente.**
- **Huecos:** el caso del operador (cara→cae→compra, y su inverso) NO se captura. El trabajo caro del deep se
  "olvida" salvo re-correrlo. No hay separación entre la TESIS (estable) y el GATILLO DE PRECIO (que se mueve
  solo).
- **Preguntas:** ¿estructura de la ficha viva? (tesis + clasificación + **precio/valuación que dispara compra/
  venta** + falsadores + known_at + escenarios). ¿Quién la actualiza y cada cuánto? ¿Cómo se vigila el gatillo
  de precio BARATO (determinista, continuo) sin re-correr el comité? ¿Cómo convive con el cache de dossiers y el
  ledger de decisiones? ¿Cuándo caduca/se revalida la tesis?

### G. Capa de contexto para el PM (industria / sector / historia / proyecciones / capacidades)
- **Hoy:** el PM (sin web) recibe: dossiers del Analista (traen la visión de industria de CADA nombre,
  cacheados ≤35d) + memo Macro (ciclo capex IA, energía, commodities, tasas, cuellos_prioridad) + contexto del
  cuello (nx: cluster, factor macro, empresas vinculadas) + hit-rate + flags. **No hay un brief de sector/
  industria vivo por cuello, independiente del nombre.**
- **Huecos:** la "visión de sector" está fragmentada en los dossiers; el PM no tiene un panorama de industria
  actualizado, con proyecciones y capacidades, para decidir con criterio top-down.
- **Preguntas:** ¿un "brief de cuello/industria" mantenido por un agente, que el PM recibe junto a los
  dossiers? ¿Cómo se mantiene fresco sin reventar el presupuesto? ¿Es el mismo que mantiene el mapa (B)?

### H. Construcción de portfolio y sizing (el PM decide)
- **Hoy:** PM-LLM sizea bajo IPS (máx 20 pos, 20%/nombre, caps sector/cuello); bandas D4 por clasificación en
  SOMBRA (no gatean); valuación como MOTOR (preferir barato/contratado por $ de EV); residual sin margen →
  ETFs de estacionamiento; mandato "casi totalmente invertido salvo macro".
- **Huecos:** la decisión no se ata a una ficha viva con gatillos (ver F); las bandas no gatean; la calidad del
  input de industria es limitada (ver G).
- **Preguntas:** ¿cómo se ata entrada/add/trim/salida a los gatillos de la ficha viva? ¿cuándo D4 pasa a duro?
  ¿cómo entra la convicción vs la valuación en el tamaño?

### I. Salidas / rotación / revisión de tenencias
- **Hoy:** posiciones → deep SIEMPRE en el ciclo semanal + eventos abren revisión; las reducciones nunca se
  bloquean (risk-off); el falsador fechado es la invalidación. Hay ~5 vías de salida heredadas (concepto), pero
  la lógica está distribuida, no centralizada en una ficha viva.
- **Huecos:** sin techo de valuación vigilado para recortar al ganador caro; sin "vender porque apareció algo
  mejor" explícito; seguimiento semanal, no continuo.
- **Preguntas:** ¿reglas de trim/salida (techo de valuación, falsador, ruptura de tesis, mejor oportunidad)?
  ¿cadencia de revisión de tenencias (continuo barato + comité por evento)? ¿rotación vs disciplina?

### J. Discovery (búsqueda activa) + memoria de lo que salió
- **Hoy:** agente LLM (Sonnet+web) propone nombres + cuellos nuevos; validadores exigen fuente primaria +
  encaje en el mapa + cap resuelto; cursor de barrido con tope de gasto; embudo/hit-rate visible. **Sin memoria
  de archivadas:** una que salió y se abarata no vuelve sola; una que salió sin cambiar fundamentals puede
  re-proponerse (el validador solo chequea que no esté YA en el universo).
- **Huecos:** no hay "re-ingreso por abaratamiento" ni "supresión por fundamentals sin cambio"; discovery no
  aprende de sus aciertos/errores pasados.
- **Preguntas:** ¿memoria de archivadas (por qué salió + gatillo de re-ingreso)? ¿discovery mira valuación, no
  solo narrativa? ¿cómo se mide y realimenta el hit-rate de discovery?

### K. Evaluación / aprendizaje (¿se realimenta?)
- **Hoy:** carteras sombra (pm, ew_pass, ETFs, "Opus+web solo") + Brier/hit-rate de falsadores + ledger de
  decisiones. Mide, pero **no está claro que realimente la priorización o la memoria.**
- **Preguntas:** ¿cómo el track record (qué cuellos/señales aciertan, calibración del PM) ALIMENTA la
  priorización, el sizing y la membresía del universo? ¿aprendizaje explícito vs solo medición?

### L. Datos y presupuesto (qué podemos captar y cuánto cuesta)
- **Hoy:** yfinance (precio/market cap/ADV, FX), EDGAR/XBRL (financials point-in-time, filings, **insider Form
  4**), RSS (news/guidance), USAspending (contratos gobierno, en Bloque 2). Barato+determinista. El caro es el
  comité (Opus/Sonnet+web).
- **Preguntas:** ¿qué fundamentals se pueden seguir barato y continuamente (Δacciones, backlog/RPO, guidance,
  insider) para mantener viva la ficha sin LLM? ¿cómo entra todo el rediseño en ~$40/mes (o cuánto subir y por
  qué)? ¿qué es continuo/determinista vs semanal/comité vs por evento?

---

## 3. La pregunta integradora (lo que el diseño tiene que resolver de punta a punta)
Diseñá el **sistema operativo de investigación y portfolio**: cómo un nombre ENTRA al universo (del mapa o del
screening), cómo se MONITOREA barato y continuamente, qué lo gradúa a DEEP (oportunidad, no solo evento), qué
MEMORIA viva deja ese deep (tesis + gatillos de precio/valuación vigilados barato), cómo el PM recibe el
CONTEXTO (acción + industria + sector) sin web, cómo se DECIDE y SIZEA atado a esa memoria, cómo se REVISAN las
tenencias y se ROTA, cómo lo que SALE se recuerda, cómo el mapa se mantiene VIVO, y cómo todo esto APRENDE —
todo dentro del presupuesto y respetando los principios del §0. Marcá lo FIRME, los cortes por sobreingeniería,
y qué se puede implementar hoy vs diferir.
