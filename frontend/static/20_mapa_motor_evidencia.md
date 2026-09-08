# 20 — El mapa de cuellos como MOTOR DE EVIDENCIA (diseño)

> El núcleo del núcleo. Donde se construye —o no— el edge. Tesis del operador: el edge
> no está en la aritmética del score, sino en que **la IA procese EVIDENCIA PRIMARIA
> FRESCA a escala** para detectar cuellos de botella **apretándose antes del consenso**,
> con **disciplina de falsificación**. Diseño para triangular. Sin código hasta aprobar.

## La tesis de edge — y su versión peligrosa
Dos versiones de "la IA tiene el insight", opuestas:
- **A — la IA sabe qué está de moda (su conocimiento guardado).** ❌ NO es edge: es el
  **consenso** hasta su fecha de corte, con **look-ahead** en el training. Si la IA lo
  sabe, el mercado ya lo pricéo.
- **B — la IA sintetiza evidencia primaria FRESCA a escala.** ✅ Acá puede haber edge:
  leer cientos de filings/transcripts/contratos/precios de una cadena entera y detectar
  el cuello **apretándose antes de que sea titular**, trazando el **cuello del cuello**
  (el upstream oscuro que nadie mapeó).

**Este doc diseña la Versión B. La A está prohibida por construcción.**

## Principio no negociable
El LLM **NO aporta su opinión** (consenso + stale). El LLM **lee evidencia primaria
fresca, traza cadenas, y propone cuellos que DEBEN venir con evidencia citada +
falsificadores — o se descartan.** Es el U1 del gate (hecho + umbral + fecha + fuente)
extendido al descubrimiento.

## Qué es un cuello de botella REAL (definición económica, no narrativa)
Un nodo es cuello si cumple las tres:
1. **Oferta inelástica** — no puede responder rápido aunque el precio incentive: capex
   alto, lead-time largo, permisos, IP, qualification cycle, insumo escaso.
2. **Captura de renta observable** — quien tiene el cuello sube precios / vende capacidad /
   take-or-pay.
3. **Durabilidad** — el desequilibrio dura el horizonte de inversión (estructural, no
   transitorio; ver Art. 12.2).
**Señales de EVIDENCIA (no opinión):** lead-times crecientes · take-or-pay · backlog /
capacidad vendida · precio spot subiendo · shortage declarado en filing · design-win con
obligación económica. Todo con fecha y fuente.

## El motor — tres funciones
### 1. Ingesta de evidencia primaria fresca
- **Fuentes:** filings (EDGAR + reguladores), transcripts de earnings, contratos
  materiales (8-K), precios spot de commodities, capacidad anunciada, lead-times.
  **NO la memoria del LLM. NO notas de research de consenso.**
- El LLM extrae **señales de estrangulamiento** fechadas y con fuente. Nada más.
- Jerarquía de fuentes: **primaria (10-K/contrato/regulador) > secundaria (nota que
  "dice que hay shortage")**. Una nota de prensa que repite consenso NO abre un nodo.
### 2. Trazado de cadena de valor — el cuello del cuello
- Desde una demanda (ej. cómputo AI) hacia arriba: datacenter → óptica → EML/InP →
  sustrato InP. El LLM traza la cadena y ubica el nodo **MÁS restringido**.
- Ahí el consenso es **más delgado** (el proveedor upstream oscuro). Es donde vive el edge.
### 3. Falsificación — U1 del descubrimiento
- Cada nodo propuesto DEBE traer: (a) la **evidencia citada** del estrangulamiento, (b)
  **qué lo destruiría** (nueva capacidad anunciada, tecnología sustituta, resolución del
  shortage) con fecha esperada. **Sin evidencia nombrable → no es nodo.**
- `transiciones.evaluar_apertura` ya tiene esta forma (abre solo con hecho de
  estrangulamiento + umbral + fuente A/B).

## Estado del nodo — determinista desde evidencia
`promesa → confirmado → debilitándose`, por **hechos citados** (no juicio del LLM):
- **promesa:** cuello identificado, sin monetización verificable.
- **confirmado:** revenue / capacidad / precio monetizando el cuello, citado.
- **debilitándose:** nueva capacidad / sustituto / shortage resolviéndose → los
  falsificadores empiezan a dispararse.
Caso testigo: CDMO de GLP-1 → archivado cuando la FDA declaró resuelto el shortage.

## De nodo a cartera
- Una empresa entra al universo por estar **vinculada a un nodo con evidencia de
  exposición REAL** (revenue del cuello, no "está en el sector").
- **Máx 2 nombres por nodo** (diversificación en tesis, no en tickers).
- El vínculo empresa↔nodo se persiste (`nx_empresa_nodo`) y no se borra.

## Anti-consenso — cómo evitamos ser un factor de momentum caro
1. Un nodo requiere **evidencia primaria** del estrangulamiento, no "está de moda".
2. Evidencia **fresca** (filings/contratos/spot recientes), no el conocimiento del LLM.
3. **Falsificadores obligatorios** por nodo.
4. **Preferencia por nodos upstream/oscuros** (el cuello del cuello) donde el consenso es delgado.
5. **MEDIR:** correlación del set de nodos/nombres con **momentum 6-12m**. Alta → estamos
   replicando consenso, no encontrando edge. Es el test que dice si el motor funciona.

## Cadencia (ya diseñada — `mapa/discovery.py`)
Vigilancia por estado (confirmado 14d / promesa 10d / caliente 2d) · nodo caliente
(catalizador PO/orden/partnership ≤30d) · exploración esporádica (buscar cuellos nuevos,
disparada por firmas de hecho).

## Qué existe en código (conservar / construir)
- **CONSERVAR:** brújula (34 territorios de arranque, `brujula.py`) · `nodo.py`
  (estructura) · `discovery.py` (frecuencias) · `transiciones.py` (apertura/transición por
  hechos) · `nx_nodo`/`nx_empresa_nodo` (persistencia, ya construidos en el ledger).
- **CONSTRUIR:** el **orquestador** + la **ingesta de evidencia** (el LLM leyendo fuentes
  frescas para abrir/actualizar nodos con hechos citados) — hoy "wiring pendiente".

## Costo
LLM solo para extraer evidencia (cacheado, event-driven). El barrido de nodos es barato;
el costo escala con **candidatas investigadas a profundidad**, no con cantidad de nodos.

## Preguntas para triangular
1. ¿La distinción **opinión vs. evidencia-fresca** es la correcta, o hay una tercera vía?
2. En la práctica, ¿cómo evitar que el LLM "cite" evidencia que en realidad es **consenso
   reciclado** (un artículo que dice "hay shortage")? ¿Exigir fuente **primaria** (10-K,
   contrato, regulador) y descartar secundaria?
3. **Trazar la cadena de valor:** ¿el LLM lo hace confiable, o conviene **darle la
   topología** (la brújula, curada) y que solo llene/actualice el **estado** de los nodos
   con evidencia?
4. ¿El **test de momentum** alcanza para saber si hay edge, o qué otra medición?
5. ¿**Máx 2 por nodo** es el número, o depende de la concentración/amplitud del nodo?
6. ¿Cómo evitar que esto termine siendo **"AI infra + nuclear + defensa"** (los consensos
   obvios de 2024-25)? ¿El sistema debería **penalizar** explícitamente los nodos ya
   saturados de atención?
7. ¿Es realista que la IA encuentre cuellos **pre-consenso**, o su ventaja real es solo de
   **velocidad/amplitud** sobre cuellos ya conocidos (que sigue siendo útil pero es otro edge)?

Devolvé crítica concreta y priorizada. Sin sobreingeniería: buscamos algo implementable y
honesto, no un sistema omnisciente.
