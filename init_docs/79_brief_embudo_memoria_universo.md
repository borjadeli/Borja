# 79 — Brief de triangulación: embudo, priorización, universo, MEMORIA viva y deep research

> **Para triangular (2-3 IAs independientes de alta calidad).** El operador considera que esta es la pieza más
> importante y que el diseño ACTUAL "pega en el palo". No es un bug: es un rediseño de CÓMO el sistema elige
> universo, prioriza, decide el deep research, y recuerda. Convergé en un DISEÑO (no en código). Secuela del
> doc 76 (embudo) y del doc 74 (Tier B / valuación). Fecha: 2026-11-12.

## 0. Marco que NO cambia
- BORJA = PM de IA: agentes investigan/verifican, el **PM-LLM decide** nombres y tamaños; el determinismo
  informa (datos, cálculos, señales) y limita (IPS, presupuesto). El PM **no tiene web**: alguien le tiene que
  dar la info rica y fresca.
- Universo: small/mid caps de industrias del futuro. Rango $150M–$60B. Tope 160 nombres. Presupuesto LLM
  ~$40/mes (revisable). Advisory (el humano ejecuta).

## 1. El problema (en palabras del operador)
1. **El deep research tiene que ser para las MEJORES OPORTUNIDADES, no para eventos.** Hoy el deep lo dominan
   los forzados por evento + pre-earnings. El evento debe ser **pre y post para la cartera ACTIVA**; una acción
   que NO tengo, no la voy a comprar antes de earnings por el precio — no tiene sentido (salvo que cambien
   fundamentals, y hay que ver cuáles podemos captar; el precio seguro, los fundamentals recién con el filing).
2. **Memoria de oportunidad (CRÍTICO).** "Si analizo a fondo una acción buenísima pero cara, y a los 2 meses
   cae y ahora SÍ es buenísima, ¿lo toma el sistema?" Y al revés (la tengo, se puso cara → recortar). ¿Dónde
   vive esa memoria? ¿Hay fichas por acción que el portfolio revise todo el tiempo?
3. **Búsqueda activa + gestión de universo + memoria de discovery.** ¿Bajo qué criterio reemplazo nombres?
   Si una acción SALE del universo y a los 3 meses está regalada, ¿discovery lo recuerda? Si salió y NO
   cambiaron fundamentals, ¿lo recuerda para no re-ingresarla? ¿Quién arma el mapa de sectores / cuellos /
   picks-and-shovels y CÓMO? Las posiciones, ¿seguimiento activo continuo o semanal? El PM necesita info no
   solo de la acción, sino de la industria, el sector, la historia de la empresa, las proyecciones del sector,
   las capacidades — actualizada y bien hecha. ¿Quién se la provee? ¿Qué datos del universo seguimos: solo
   precio? ¿De los deep nos queda el core y actualizamos solo en earnings?

## 2. Estado REAL hoy (verificado en el código — el punto de partida honesto)
- **Deep research — qué lo dispara** (`embudo.seleccionar_para_deep` + `triage.prioridad`): posición (siempre,
  reserva fuera del cupo) · evento fuerte no-posición (cupo 8, rankeado por prioridad de cuello) · precio-z
  grande (≥2.5 no-posición / ≥2.0 posición / ±25% abs) · **pre-earnings top-3 TAMBIÉN para no-posiciones** ·
  nunca-analizado (cupo bootstrap) · **+1 si está barato en su cuello** (señal de valor r7 §3). Capeado arriba
  por presupuesto. → el deep hoy lo MANDAN los eventos; la oportunidad es solo un empujón de +1.
- **Memoria del análisis** (`orquestador.CacheDossiers`): dossier cacheado por **hash del data pack (que
  EXCLUYE precio/market_cap)** + **TTL 35 días**. Un filing nuevo cambia el hash → re-analiza. **Una caída de
  precio NO cambia el hash → NO refresca el dossier.** No existe "comprar si cae de $X" guardado y vigilado; el
  bull/bear prohíbe price targets libres; el falsador es por fecha/evento, no un techo/piso de valuación
  monitoreado. → **NO hay ficha viva por acción con tesis + gatillo de precio que el portfolio revise
  continuamente.** Una caída grande re-dispara un deep DE CERO (caro), no una acción sobre la tesis guardada.
- **Universo** (`descubrimiento.elegir_a_archivar` + validadores): tope 160; reemplazo directo (descartado →
  analizado-viejo-sin-valor → nunca-analizado). Discovery (agente LLM Sonnet+web) propone; validadores exigen
  fuente primaria + encaje en el mapa + cap resuelto. **NO hay memoria de re-ingreso** (una archivada que se
  abarata no vuelve sola) **ni de supresión** (una que salió sin cambiar fundamentals puede re-proponerse).
- **El mapa (sectores/cuellos/picks-and-shovels)** (`backend/seed/sistema_quant/` + Map Curator): **seed de una
  sola vez** del repo Sistema-Quant (bottlenecks + evidence + ~246 empresas) + altas incrementales de cuellos
  nuevos que valida el curador-agente (≥2 fuentes primarias). **Nadie re-investiga ni actualiza el mapa, las
  proyecciones de sector o las capacidades de forma viva.** Es estático + ad-hoc.
- **Seguimiento de posiciones**: el runner **semanal** mete toda posición a deep + eventos abren revisión. El
  intradía es solo MtM de precio ($0), sin análisis. **No es continuo.**
- **Info que recibe el PM** (sin web): dossiers del Analista (Opus+web, cacheados ≤35d) + memo Macro
  (Opus+web) + contexto del cuello (nx) + hit-rate + flags. No hay brief de sector/industria vivo aparte; la
  "visión de industria" viene empaquetada en el dossier de cada nombre.
- **Qué seguimos del universo entre deeps**: filings (ítems materiales), precio (z normalizado por sector),
  días a evento, edad del dossier, + la lente de valuación XBRL en el ciclo. En la práctica, entre deeps:
  **precio + filings nuevos.**

## 3. Los HUECOS que esto expone (a resolver en el diseño)
- **H1 — Prioridad centrada en eventos, no en oportunidad.** Falta un carril de deep por OPORTUNIDAD/CALIDAD
  con cupo propio, y sacar el pre-earnings de las no-posiciones (esperar el dato post-earnings salvo reacción
  de precio anómala).
- **H2 — No hay MEMORIA VIVA de tesis + gatillo de valuación.** El caso "buenísima pero cara → cae → comprar"
  (y su inverso) no se captura. Falta una ficha viva por nombre analizado: tesis + el **precio/valuación que la
  vuelve compra o venta**, vigilada barato y continuamente (sin re-correr el deep caro cada vez).
- **H3 — Gestión de universo sin memoria.** Falta: criterio de reemplazo que mejore la CALIDAD (no solo rotar);
  memoria de discovery de **re-ingreso si se abarata** y de **supresión si no cambiaron fundamentals**.
- **H4 — Mapa estático.** El mapa de sectores/cuellos/proyecciones/capacidades no se mantiene vivo. ¿Quién lo
  actualiza, cada cuánto, con qué evidencia? ¿Es un agente dedicado (Macro/Map Curator ampliado)?
- **H5 — El PM a ciegas de la industria.** Si el PM decide y no tiene web, necesita que alguien le provea
  —actualizado y bien hecho— acción + industria + sector + historia + proyecciones + capacidades. ¿Dónde vive
  esa capa y cómo se mantiene fresca sin reventar el presupuesto?
- **H6 — Qué se puede seguir barato y continuamente** (precio seguro; ¿qué señales de fundamentals se pueden
  captar sin re-análisis caro: nuevos filings, revisiones de guidance, cambios de backlog/RPO, insider, FX)?

## 4. Preguntas de diseño para converger
1. **Priorización del deep:** ¿cómo se define "las mejores oportunidades"? ¿Un score de oportunidad
   determinista (valuación vs calidad del cuello vs momentum de fundamentals) que compite con los eventos por
   el cupo? ¿Qué parte es determinista y qué juzga el LLM? ¿Cómo se evita el gaming y el deep-value trap?
2. **Memoria viva (ficha por acción):** ¿qué estructura? (tesis + clasificación + el precio/valuación que
   dispara compra/venta + falsadores + known_at). ¿Quién la actualiza y cada cuánto? ¿Cómo se vigila barato el
   gatillo de precio sin re-correr el comité? ¿Cómo convive con el cache de dossiers y el ledger de decisiones?
3. **Universo con memoria:** criterio de reemplazo (calidad, no rotación); memoria de archivadas (re-ingreso
   por abaratamiento; supresión por fundamentals sin cambio). ¿Cuánto universo conviene (160 está bien)?
4. **Mapa vivo:** ¿quién mantiene sectores/cuellos/proyecciones/capacidades actualizados, con qué cadencia y
   evidencia? ¿Agente dedicado? ¿Cómo se versiona y se cita?
5. **Capa de contexto para el PM (sin web):** ¿un "brief de industria/sector" por cuello, mantenido por un
   agente, que el PM recibe junto a los dossiers? ¿Cómo se mantiene fresco dentro del presupuesto?
6. **Qué seguir continuamente y barato:** el set mínimo de señales (precio + ¿qué fundamentals?) que mantiene
   viva la ficha entre deeps sin gastar LLM.
7. **Cadencia:** ¿qué es continuo (barato, determinista), qué es semanal (el comité), qué es por evento?
8. **Presupuesto:** cómo entra todo esto en ~$40/mes (o cuánto habría que subirlo y por qué).

## 5. Principios que el diseño debe respetar
- Determinismo informa/limita; el PM-LLM decide. El PM no tiene web → la capa de contexto es responsabilidad
  del sistema.
- Hecho verificado ≠ declarado (procedencia + known_at). Nada de price targets libres: supuestos explícitos.
- Disciplina de costo: barato y determinista para seguir/monitorear; caro (LLM+web) solo donde agrega.
- Implementabilidad como gate: adoptar solo lo sourceable + extraíble + computable hoy; el resto, diferir con
  criterio.
