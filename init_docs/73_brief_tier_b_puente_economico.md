# 73 — Brief de diseño Tier B (para triangular): el puente económico al precio

> Secuela del doc 72. Las 3 IAs convergieron: **el sistema analiza el RIESGO bien y la OPORTUNIDAD mal — el
> futuro sale narrativo, no económico.** Tier A (bugs deterministas de datos) quedó CERRADO. Tier B hace que
> el análisis del futuro sea ECONÓMICO. Esto NO se codea sin acuerdo: es el brief para mandar a 2 IAs y
> converger, como hicimos con el embudo (61-64) y la ficha de futuro (67-70).

## Principio rector (no se toca)

El futuro sigue siendo **UNA pata**, no pesa más (lo que hace hoy la empresa, sus números y su historial
siguen valiendo). Lo que cambia: la conclusión del Analista tiene que tener **relación económica TRAZABLE con
el precio**. El determinismo hace la **aritmética** (descontar, per-share, ponderar); el LLM pone los
**escenarios y las probabilidades** (juicio). El determinismo NO decide tamaños ni nombres; el PM decide. Si el
analista no puede dar números defendibles → **UNKNOWN**, no se fabrica (regla de implementabilidad como gate).

## D1 — Puente económico: retorno por escenario (el núcleo)

**Problema (3/3):** se compara el valor de hoy con un múltiplo sobre flujos de 2029-34 **sin descontar** y sin
traducirlo a retorno del accionista. RGTI es el caso límite: $400M @ 8x = $3,2B = el mismo EV que hoy → aun
acertando en 8 años, el EV no crece.

**Diseño:** el Analista emite, para **bull / base / bear**: métrica terminal (revenue o EBITDA), año, múltiplo
de salida, y **probabilidad**. El determinismo computa por escenario:
`valor_terminal → descontado a hoy (tasa fija) → ajustado por dilución esperada → IRR/CAGR implícito vs precio`.
Salida: tabla de retorno por escenario + **retorno esperado ponderado**. Helper nuevo en `futuro.py`:
`retorno_por_escenario(precio, escenarios, tasa, dilucion)` (aritmética pura, testeable).

- **Honestidad:** son los escenarios del analista; la aritmética no inventa. El Verificador exige que los
  números del escenario tengan la misma procedencia que cualquier claim.
- **DECISIÓN ABIERTA 1:** ¿tasa de descuento **fija** (recomiendo 15% para small/mid cap especulativa, + nota)
  o **variable por `riesgo_remanente`** (científico > escala)? Recomiendo fija para no sobre-parametrizar.

## D2 — Falsadores con vara competitiva/económica (no autorreferencial)

**Problema (3/3):** el falsador se calibra para CONFIRMAR la tesis (RGTI 99,5% = su propio roadmap; OKLO
"mantener 2028" lo sostiene el management sin avanzar; MP $40M Magnetics puede dispararse por precursores).

**Diseño:** el falsador debe incluir **al menos una condición relativa a competidor o económica**
(precio/costo/margen/demanda comercial), no solo un hito propio. Ej. RGTI: "fidelidad 2Q a ≤X de brecha vs el
mejor superconductor comparable" en vez de "99,5% absoluto".
- Implementación: prompt del Analista + **check del Verificador** que marca REVIEW si el falsador es puramente
  self-referential o sin umbral económico/competitivo.
- **DECISIÓN ABIERTA 2:** ¿agregar un campo explícito `vara_competitiva` al schema del falsador (fuerza la
  disciplina) o dejarlo como requisito de prompt? Recomiendo el campo explícito.

## D3 — Tasas base con fuente o marcadas como juicio

**Problema (3/3):** "<10% industriales / <20% primeros de su clase / <5% hardware" sin cohorte ni fuente —
"impresiones cuantificadas".

**Diseño:** toda tasa base **se cita** (Mauboussin/Callahan *The Base Rate Book*; Flyvbjerg para sobrecostos
de megaproyectos) **o** se etiqueta explícitamente "juicio del analista, sin muestra". El Verificador marca
como nota las afirmaciones tipo-tasa-base sin fuente.

## D4 — Sizing que diferencia la clasificación (el de más leverage)

**Problema (IA3):** el PM sizeó OKLO (**especulativa**, conv 0,30) en **2,8%**, casi igual que MP (**satélite**,
conv 0,45) en 3%. La clasificación de la ficha de futuro **no tiene consecuencia en el tamaño** → el motor de
convicción-vs-madurez (doc 70) no se traduce en peso.

**Diseño:** la `analyst_classification` mapea a una **BANDA de peso** (cap duro en el IPS); el PM sizea DENTRO
de la banda. Esto es **determinismo-como-LÍMITE** (coherente con el paradigma y con [[sizing-burden-es-un-cap-no-el-size]]):
la IA clasifica y sizea, el código capea. NO le saca la decisión al PM.
- **Propuesta de bandas:** `watchlist` 0% · `especulativa` ≤1,5% (tamaño de opción) · `satelite` ≤4% ·
  `core` ≤ IPS max. Downside de una especulativa a valor de liquidación (~−40/−50%) con 1,5% pesa ~−0,7% del
  portafolio — asimétrico y barato.
- **DECISIÓN ABIERTA 3:** los números de las bandas (¿1,5%/4%? ¿otros?) — dependen del apetito de riesgo del
  operador y de cuántas plazas. Es la decisión más "del operador" de todo Tier B.

## D5 — ¿El Auditor con web? (propuesta del operador)

**Contexto:** hoy el PM y el Auditor NO tienen web (el research agéntico lo hacen Analista y Bear). La
triangulación del doc 72 fue, en los hechos, **un auditor con web**: 3 IAs que leyeron filings encontraron
omisiones MATERIALES que el comité no vio (clawback del 30% del DoD, capex revisado de OKLO, el **vencimiento
chino del 10/11** a 8 días, el acuerdo con Meta, la vara competitiva de fidelidad). Un auditor solo-contexto
NO puede cazar eso: solo chequea coherencia interna (concentración, memo-vs-peso, rotación).

**Propuesta:** darle web **al Auditor** (no al PM). Se distingue limpio del PM:
- El **PM sintetiza y decide** sobre evidencia ya verificada → sin web, para no re-investigar y mantener la
  disciplina (doc 51).
- El **Auditor es el adversario independiente**; su trabajo es encontrar **lo que el comité MISSED**, que
  justamente suele vivir **fuera del dossier** (un competidor, una cláusula, un evento vinculante próximo).
  Darle web institucionaliza lo que hicimos a mano con las 3 IAs.

**Guardarraíles (para que audite, no re-escriba):** (a) sus hallazgos web entran como **objeciones falsables**
(el mecanismo que ya existe: `devuelve_al_pm`), NO como un dossier nuevo; (b) no sizea ni elige nombres; (c)
cap de `max_uses` de web y de costo (corre 1 vez/ciclo sobre pocos nombres → barato vs el Analista).

**Recomendación:** **sí**, con esos guardarraíles. Es coherente con el paradigma ("los agentes de investigación
usan web; el PM no") y es el mayor multiplicador de calidad a bajo costo que vimos.
- **DECISIÓN ABIERTA 4:** ¿se acepta Auditor-con-web con esos límites? ¿algún riesgo de que el Auditor se
  vuelva un segundo Analista en vez de un adversario?

## Qué NO cambia

El PM sigue **sin web** y decide. El determinismo informa/limita. El futuro sigue siendo una pata. No se agrega
un DCF que reemplace el juicio: el LLM pone escenarios+probabilidades, el código solo hace la aritmética
honesta de llevarlos al precio de hoy.

## Orden de implementación propuesto (tras converger)

1. D1 helper `retorno_por_escenario` + schema de escenarios en la ficha (aritmética testeable, bajo riesgo).
2. D4 bandas por clasificación en el IPS (cap duro; el gate ya existe).
3. D2/D3 prompt (Analista/Bear) + checks del Verificador.
