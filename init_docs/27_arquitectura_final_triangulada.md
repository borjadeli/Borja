# 27 — Arquitectura final (triangulada) — selección, valuación y salida

> Esquema **cerrado y mínimo** del sistema de análisis→selección→cartera→rotación.
> Producto de triangular la pregunta con dos IAs externas independientes (ver §0).
> Es la fuente de verdad del DISEÑO; el código y los umbrales exactos se derivan de acá.
> Regla rectora: **no sobrecomplejizar, no inventar.** Sistema **advisory** (el operador
> ejecuta a mano en Interactive; es el humano en el loop).

## 0. Procedencia y confianza

Se planteó a dos IAs el problema (asimetría en empresas en desarrollo · mérito cardinal vs.
pilares · embudo · integración motor-de-evidencia↔esqueleto determinista). **Las dos
convergieron, de forma independiente, en la MISMA arquitectura.** Esta convergencia es la razón
de la confianza. Donde difirieron, se tomó la versión más conservadora / más simple.

## 1. La esencia (una línea)

**El LLM CLASIFICA hechos citados; un _scenario compiler_ determinista, por arquetipo, los
convierte en bull/base/bear con reglas escritas por nosotros. El LLM nunca decide un valor.**

La integración correcta **NO** es `fact store → LLM → bull/bear` (eso es el problema actual con
mejores citas). Es:

```
fact store → normalización semántica → reglas de admisibilidad
           → scenario compiler determinista (por arquetipo) → bull/base/bear
           → auditoría de cada transformación
```

**El punto más peligroso del sistema es la transformación hecho→bull/bear.** "Determinista" no
significa "fundado": el riesgo real no es que el LLM invente un hecho (eso está defendido), sino
tomar hechos verdaderos y, vía probabilidades / múltiplos / haircuts discrecionales, producir una
valuación que sigue siendo narrativa pero **parece** determinista. Y su gemelo: **verificado ≠
verdadero, citado ≠ material** — la incertidumbre real la domina *lo que nunca se extrajo*.

## 2. La cadena de decisión (la espina)

```
0.  Mapa sectorial → universo            (macro acá: DEFINE, no puntúa)
1.  Screen $0        → elimina lo NO analizable (no busca "las mejores")
2.  Priority score → triage barato → deep dive de evidencia (caro) sobre pool limpio
3.  Motor de evidencia: hechos citados+verificados → fact store  +  COBERTURA como número
4.  Elegibilidad: 3 pilares conjuntivos (demanda/cuello · economía · ejecución) = Pass/Fail/Unknown
                  Fail elimina · Unknown ≠ neutral → no posición normal (a lo sumo option sleeve)
5.  Valuación = GATE SEPARADO de falsificación: CAGR implícito (o participación FÍSICA si rev≈0)
6.  Caso operable: bull/base/bear SOLO de evidencia admisible, con REGLA AUTORIZADA por término
7.  Option ledger (aparte, no contamina): oportunidades fechadas/falsables O0→O5. Se MUESTRAN.
8.  Tier (fortaleza + evidencia, NO upside) → CAP (A/B/C → 8/5/2.5%)
9.  Ranking LEXICOGRÁFICO: gate → tier → cobertura → asimetría operable (cap 5x) → catalizador → liquidez
10. Sizing = min(caps): arquetipo · evidencia · fragilidad · liquidez · sector
11. Cartera: caps por sector (macro abajo) · máx N · margen 20% para desplazar al incumbente
12. Rotación: 5 vías + milestone-miss + evidence-decay
```

## 3. Asimetría en empresas en desarrollo (el nudo resuelto)

Tres capas de evidencia; el corte NO es "ocurrido vs. posible":

| Capa | Qué es | ¿Entra al bull operable? |
|------|--------|--------------------------|
| **Realizado** | revenue reconocido, márgenes actuales | Sí (100% como punto de partida; el pasado NO es un piso garantizado) |
| **Contratado / underwritten** | backlog financiado, LTA, take-or-pay, award **irrevocable**, calificación con cliente nombrado | Sí, con **haircut** (conversión histórica) |
| **Opcionalidad** | RFP, design-win en calificación, MoU, pipeline, TAM | **NO — 0 en el bull.** Va al option ledger |

- No se llama "piso": en development lo ocurrido puede erosionarse (dilución, quema, fracaso
  técnico). Es el **caso *underwritten* / defendible**.
- **Opcionalidad = 0 en la asimetría.** Determina en qué sleeve vive el nombre, no el precio.
- **Sin probabilidades.** No se convierte la opcionalidad en expected value. La opcionalidad se
  **muestra** como hitos fechados y falsables (escalera O0→O5); el margen para el "posible bull
  con delirio" es del **operador**, acotado por el cap del sleeve (§7).
- **Revenue ≈ 0 → resolver sobre cantidad FÍSICA, no dólares.** "El precio implica 22% del
  suministro global de HALEU en 2032" es falsable; "35% de CAGR" no lo es y es narrable. Los plays
  son de cuello de botella; el cuello es físico = contable.
- **CAGR implícito y asimetría no compiten:** el CAGR implícito es el **gate de falsificación**
  (¿el precio exige más de lo que capacidad/demanda/financiación/ejecución sostienen? → afuera);
  la asimetría operable ordena capital **dentro** de lo ya underwritten.

## 4. Los seis estados (modelo de datos)

```
L1 Evidence state   : hechos atómicos · contradicciones · missingness · milestones · cobertura · fecha de corte
L2 Company state    : Demand/Economics/Execution = Pass/Fail/Unknown · Valuation-sanity · Tier · {Operable|Option-only|Rejected}
L3 Valuation state  : operativa → bear/base/bull operable · asimetría · CAGR implícito
                      development → bear de financiación/dilución · caso underwritten · CAGR implícito · option ledger
L4 Ranking          : gate → tier → cobertura → asimetría operable (cap 5x) → catalizador → liquidez
L5 Sizing           : min(target_ranking, cap_arquetipo, cap_evidencia, cap_fragilidad, cap_liquidez, cap_sector)
L6 Rotación         : 5 vías + milestone-miss + evidence-decay
```

**Evidence cap (la "ignorancia como variable de primera clase"):**
operable + evidencia completa → 100% del target · parcial → 50% · option-only → ≤25% · unknown crítico → 0%.

## 5. Contrato de datos: fact store → scenario compiler (LA PIEZA CRÍTICA)

Cada hecho debe cargar: empresa/entidad legal · concepto normalizado · valor · **unidad** ·
**moneda** · **período** · **as-of** · fecha de publicación · fuente · cita textual · método de
verificación · versión · confianza · **clase** (reported/audited · contrato/contraparte ·
regulatorio/tercero · guidance formal · management claim · promocional) · **reglas de valuación
para las que es elegible** (`valuation_eligible`).

Ejemplo: un "pipeline de USD 2.000M" puede estar bien citado, pero `valuation_eligible=false`.

**Regla de transformación autorizada:** cada término del bull/base/bear lleva
`{hecho fuente, regla, haircut, origen del haircut, vigencia}`. **Sin regla autorizada → el
término vale 0.** Los haircuts salen de: historial propio · cohorte · contractual · o política
conservadora fija del sistema. **Nunca de "juicio razonable".**

## 6. Las 8 cosas que se rompen (checklist de defensa del compiler)

1. **Hecho correcto, interpretación falsa** ("design win" difiere entre semis/defensa/fotónica) → glosario por sector.
2. **Desalineación temporal** → todo escenario tiene UNA fecha de corte; prohibido mezclar hechos posteriores.
3. **Unidades/perímetros** (millones vs miles · moneda · FY vs CY · total vs segmento · gross vs funded backlog · bookings vs revenue · capacidad nominal vs utilizable).
4. **Missingness → 0** es un bug: distinguir cero-reportado · no-aplica · no-divulgado · no-encontrado · contradictorio.
5. **Doble conteo** (contrato + backlog + guidance + capacity ramp = el MISMO flujo) → **una fuente canónica por flujo económico**; dedup económico, no documental.
6. **Management claim como evidencia independiente** → que esté en la SEC no lo hace externo; clasificar por fuerza de fuente.
7. **Haircuts arbitrarios** → el lugar donde reaparece el LLM; solo históricos/cohorte/contractuales/política fija.
8. **Auditoría no independiente** → si el auditor usa la misma ontología/prompts que el extractor, confirma los mismos errores. La auditoría busca evidencia CONTRADICTORIA, notas al pie, restatements, definiciones del management y **hechos omitidos que empeoran la tesis** — no que la frase exista.

## 7. Option sleeve (donde vive el delirio del PM, acotado)

> ⚠️ **SUPERADO por doc 29.** El "sleeve ~2% por nombre" de esta sección **se sacó**. Lo reemplazó el
> **carril especulativo** (doc 29): gate de entrada + cap 8%/pos + máx 2 plazas + presupuesto agregado
> 10%→25% ganado por hit-rate. NO citar el 2% fijo. El resto de este doc (flujo, decisiones) sigue vigente.

- Nombres **Option-only** (evidencia insuficiente para underwriting, pero con hito falsable + runway).
- **Cap fijo chico: ~2% por nombre (≈25% del cap normal del arquetipo). Sin estimar probabilidades.**
- Es más honesto que "27,5% de chance": *"no sé valuarla todavía, acepto pérdida acotada para no quedar afuera"*.
- **Salida por CALENDARIO DE HITOS, no por asimetría<0.5x** — un nombre-opción destruye el ratio
  mecánicamente cuando la opción se realiza (el precio sube antes que el bull); operar el ratio ahí
  vende al ganador temprano.

## 8. Macro / mapa sectorial — dos lugares, nunca en el mérito

- **Arriba:** define el universo (qué cuellos existen y qué los restringe) + **distribuye
  presupuesto de investigación** (dónde el cuello se aprieta, dónde cambió la evidencia).
- **Abajo:** caps por sector/tema, stress tests, evitar exposición duplicada.
- **Nunca** como multiplicador del mérito de un nombre (si el cuello ya está en el pilar de
  demanda, un tilt macro lo cuenta dos veces y concentra sin querer). La macro nunca rescata a una
  empresa que falla ejecución o economía.

## 9. Screen $0 y priority score

**Screen $0 — elimina lo NO analizable (no rankea calidad):** investabilidad (posición objetivo
≤ 1-2% del volumen diario mediano — duro por ejecución manual) · relevancia REAL al cuello (no que
el management diga "AI") · fuente primaria al día · supervivencia financiera (runway al próximo
hito o financiación comprometida; **no** eliminar dilutivas salvo que la dilución sea necesaria
ANTES de poder falsar la tesis) · **falsabilidad** (≥1 KPI/hito observable en horizonte definido).
**NO va en el screen:** rentabilidad, nivel de revenue, múltiplos, piso de market cap, cobertura.
**Distinto por arquetipo** (operativas: crecimiento/margen/backlog; development:
runway/madurez técnica/proceso comercial/hito próximo). **Carril de rescate:** un nombre que falla
el screen pero dispara un trigger de evento (award DoD, selección DOE, calificación) salta al triage.

**Priority score (cola de investigación, NO score de inversión):**
`relevancia al cuello + evidencia disponible + hito falsable cercano + supervivencia + investabilidad`,
cada uno 0/1/2. NO incluye precio objetivo, asimetría, múltiplos, "calidad", ni opinión del LLM.

## 10. Ranking y sizing

- **Lexicográfico** (no un score fusionado): gate → tier → cobertura → asimetría operable **capada
  a 5x** → catalizador verificable → liquidez. Un Tier 1 rankea sobre un Tier 3 aunque el 3 tenga
  10x (ese 10x casi siempre es fragilidad del modelo, no oportunidad superior).
- **Tier → cap, no score.** El tier fija el peso máximo; no suma puntos compensables.
- **Con evidencia rala, bucketear en cuartiles**; un 7.3 vs 7.1 con 3 hechos cada uno es ruido.
- **Margen 20%** para que un candidato desplace al incumbente (evita rotación por ruido trimestral).
- **Near-miss queue:** un 0.49 en un pilar no ablanda el gate — queda en watchlist con trigger
  fechado ("cuando el 10-Q publique gross margin ≥ X").

## 11. Rotación (extiende las 5 vías del núcleo)

Las 5 vías (governance · CRR · invalidación · asimetría muerta · recorte) **+ 2 triggers**:
- **Milestone-miss:** pasó la fecha del hito sin el avance requerido.
- **Evidence-decay:** el hecho que sostenía la tesis dejó de ser actual / fue redefinido / no se
  confirmó. **El mero paso del tiempo puede deteriorar una tesis** — anclaje viejo → *degradar el
  cap*, no forzar venta (staleness > 1 trimestre + 45 días).

## 12. Filtro MVP — qué se construye ahora y qué se difiere

**En el MVP (esencial, ambas IAs):** scenario compiler determinista + contrato de datos ·
caso operable con reglas autorizadas · option ledger + sleeve 2% (sin probabilidades) ·
3 pilares→gate/tier · valuación como gate separado · ranking lexicográfico · evidence cap ·
milestone-miss + evidence-decay.

**Diferido / minimizado:** ontologías por industria (MVP: glosario chico de los cuellos que
jugamos) · grafo de procedencia para dedup (MVP: una fuente canónica por flujo) · tablas de tasas
base + expected value (**afuera**; el sleeve 2% lo reemplaza) · harness de replay bit-idéntico
(el principio —congelar+versionar el fact set— ya existe; el test formal, incremental).
**Se mantiene:** shadow-run viejo‖nuevo con atribución (cutover seguro, no directo).

## 13. Contra lo que ya existe (no es un rewrite)

- **Ya está:** fact store · extractor citado (el LLM ya *trae* hechos, no decide valores) ·
  pilares/tiers conjuntivos · fragility/`min()` de caps · 5 vías de salida.
- **Ajustar:** valuación fuera de los pilares → gate separado · tier → cap · ranking →
  lexicográfico · extender el contrato de datos del hecho.
- **Construir (lo nuevo y central):** **scenario compiler** (templates fact→bull/base/bear por
  arquetipo) · **option ledger** · **evidence cap**.

## 14. Orden de implementación

1. **Definir el contrato fact store → scenario compiler** (el punto más crítico; todo depende de él).
2. Separar caso operable y option ledger.
3. Convertir los 4 pilares en gate/tier (no otro score multiplicativo).
4. Reemplazar Quality × Asimetría por ranking lexicográfico.
5. CAGR implícito (o participación física) como test de falsificación.
6. Templates de valuación por arquetipo.
7. Shadow-run viejo ‖ nuevo con **atribución**: cada cambio de posición explicable por un hecho
   nuevo, una regla, o un movimiento de precio.

## 15. Test de aceptación de la costura

Para **cada número** del sistema, poder responder: **qué hecho lo originó · qué regla lo
transformó · por qué existe esa regla · qué observación futura la invalida.** Y poder replayear
cualquier decisión pasada desde un `fact_store_version_id` con output reproducible. Si no se
cumple, no es un sistema determinista: es uno estocástico con buena documentación.
