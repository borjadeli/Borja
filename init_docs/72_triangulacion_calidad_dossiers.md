# 72 — Triangulación de CALIDAD de los dossiers (3 IAs independientes · smoke 2026-11-02)

> Tres IAs externas criticaron la **calidad del análisis** (no la gobernanza) de los 3 dossiers del smoke
> de futuro: **MP** (comprada 3%), **OKLO** (mantenida 2,8%) y **RGTI** (0%). Insumo: doc 71. Este doc
> **triangula** las 3 devoluciones: lo que **convergió** (señal fuerte → fix seguro) vs lo que es juicio de
> una sola. Cierra con el **plan ordenado**: bugs deterministas / cambios de prompt / datos a verificar.

## Veredicto agregado

| Empresa | IA1 | IA2 | IA3 | Decisión del PM | ¿La respaldan? |
|---|---|---|---|---|---|
| MP (comprada 3%) | 7,0 | 6,5 | **5,0** | comprar 3% / conv 0,45 | defendible como satélite chico, PERO sizing/convicción altos y **ejecutada con errores de dato** |
| OKLO (mantenida 2,8%) | 6,5 | 5,5 | 6,0 | mantener 2,8% / conv 0,30 | **la más cuestionada**: a 2,8% una especulativa pesa ≈ la satélite |
| RGTI (0%) | 5,5 | 6,0 | 7,0 | pasar (0%) | **las 3 coinciden con 0%** |

**Dato incómodo:** la IA que verificó contra filings (IA3) puso la **peor nota a MP, la que efectivamente se
compró**. No analizamos mejor la que arriesgamos plata; analizamos mejor la que descartamos (RGTI).

## 1. El hallazgo central (CONVERGEN LAS 3)

> **El sistema analiza bien el RIESGO y mal la OPORTUNIDAD. El futuro sale NARRATIVO, no ECONÓMICO.**
> No hay un puente trazable `hechos → tesis → precio → retorno del accionista`.

IA2 lo operacionaliza: el Analista debería contestar 4 preguntas y que las respuestas tengan relación
económica con el precio (sin volverse calculadora determinista ni sacarle la decisión al PM):
1. ¿Qué futuro puede construir? → escenarios concretos.
2. ¿Con qué probabilidades? → rangos defendibles, incertidumbre explícita.
3. ¿Cuánto captura el accionista? → flujos, capital adicional, dilución.
4. ¿Qué retorno implica al precio de HOY? → **IRR/CAGR por escenario**, con plazos.

Esto encaja con la directiva del operador: **el futuro es UNA pata, no todo** — el reclamo no es que pese
más, sino que esté **cuantificado y atado al precio**.

## 2. Convergencias 3/3 (fix seguro)

1. **"Lo que exige el precio" no está descontado.** Se compara valor de hoy con un múltiplo sobre flujos de
   2029-2034 sin traerlos a VP. Cuantificado por IA2 e IA3:
   - MP: $470-580M → **$625-815M** descontado.
   - RGTI: $3,2B en 8a @15% = ~$1,05B hoy → para justificar $3,2B hoy hace falta **~$1,2B revenue** (CAGR
     ~67%, no 45%); el dossier pedía $400M.
2. **Tasas base sin fuente.** "<10% industriales" (MP), "<20% primeros de su clase" (OKLO), "<5% hardware"
   (RGTI) aparecen como dato y parecen inventadas. Fix (IA3): citar *The Base Rate Book* (Mauboussin/Callahan)
   / Flyvbjerg (sobrecostos de megaproyectos), **o** marcarlas explícitamente como juicio del analista.
3. **Falsadores calibrados para CONFIRMAR, no para TESTEAR**, y sin pata económica/competitiva:
   - MP: $40M/q de Magnetics puede dispararse por *precursores* o por capacidad, sin validar imanes
     terminados rentables; falta gatillo político (PPA/presupuesto). 3T27 se publica en nov-2027 → usar 2T27.
   - OKLO: "capex que haga inviables los PPA" no es medible (falta umbral $/kW o $/MWh); "mantener 2028" lo
     puede sostener el management sin avanzar → pedir hitos físicos (DSA, inicio de construcción, combustible
     fabricado); dilución>10% **no es falsador tecnológico** (mezcla financiamiento con tesis).
   - RGTI: **autorreferencial** (usa la vara de su propio roadmap). Llegar a 99,5% no valida (sigue detrás de
     IBM/Google ~99,8%). Fix: vara **relativa** (brecha de error 2Q vs mejor superconductor comparable, o
     coherencia mínima) + definir la medición (mediana sobre todos los pares, datos públicos de Braket,
     sostenida semanas).
4. **El "test de atraso" se queda en runway de caja.** Ignora: (a) revenue contratado que no arranca durante
   el atraso (MP: el offtake de 10X empieza con 10X), (b) costo de oportunidad competitivo (RGTI: si llega
   tarde el mercado ya no existe), y (c) confunde estrés con caso base (OKLO: 2029-30 es el central).

## 3. Bugs DETERMINISTAS (nuestros, verificables → reproducir + test de regresión)

| # | Bug | Evidencia (3 IAs) | Dónde |
|---|---|---|---|
| B1 | **Dilución mal en las 3.** No captura preferidas convertibles + warrants ITM ni dilución latente por FV. | MP ficha 0,49% vs ~9% as-converted (pref 13,32M@30,03 + warrant 11,2M@30,03, ITM a 39,57); OKLO 19% vs ~25% (147,6→185,1M acc); RGTI 1,1% vs ~3,1% | `dilucion.py` / `fuente_calculadoras` |
| B2 | **Runway ignora capex y toma mal el concepto de caja.** | MP: pack dio $429M vs $1.452,6M real (excluye inversiones de corto plazo); runway = caja/opex-FY ignorando capex. OKLO/RGTI: excluye capex ($16,4M RGTI 1S26). | `fuente_xbrl` (concepto de caja) + `cash_runway_months` |
| B3 | **Criterio desparejo del runway.** El Analista detectó el bug en RGTI y OKLO pero **no en MP**, la comprada. | IA3 | prompt Analista (protocolo de frescura/consistencia) |
| B4 | **Cita `primaria_regulatoria` a `browse-edgar`** (página de búsqueda, no documento). | IA3 (MP c3, OKLO c3) | `clase_por_url` (una URL de búsqueda no es primaria) |
| B5 | **Point-in-time viejo.** C17 (MP) cita notas 2026 ya canceladas como deuda corriente ($67,4M→0). | IA3 | frescura / data pack |
| B6 | **Runway inconsistente en el propio output.** RGTI: C4 dice 5,7 meses, la ficha dice 4,4. | IA3 | consistencia pack↔ficha |

## 4. Hallazgo de DISEÑO: el sizing no diferencia la clasificación

OKLO (**especulativa**, conv 0,30) quedó en **2,8%**, casi igual que MP (**satélite**, conv 0,45) en 3%.
IA3: una especulativa con piso de liquidez justifica tamaño de **opción (~1%)**, no 2,8%. **El motor de
convicción-vs-madurez que se construyó (doc 70) no se está traduciendo en tamaño.** Hay que revisar si el
PM/IPS mapea clasificación → rango de peso, o si quedó como texto en el prompt sin consecuencia.

Además (IA3): la decisión de **mantener OKLO 2,8% es incoherente** con el propio material — Verificador en
REVIEW + Auditor marcando "tesis cambió vs entrada" + el escenario más probable (atraso) con retorno
negativo. Si la tesis cambió, la pregunta correcta no es "¿mantengo?" sino "**¿compraría 2,8% hoy?**".

## 5. MP (la comprada) — errores forenses de IA3 (verificar contra 10-K/10-Q antes de re-decidir)

- **Contrato DoD de 10X = estructura tipo *lease*** (reconcilia el conflicto IA1↔IA2): EBITDA garantizado
  ≥$140M/año indexado 2% **Y** clawback del 30% sobre $110/kg; el DoW tiene derecho a sustancialmente todo el
  beneficio económico de la planta → 10X es **cuasi-regulado con upside limitado**, no apuesta comercial a
  imanes. El bear "offtake cubre volumen no rentabilidad" es **falso para 10X** (vale para Independence/GM/
  Apple). El target de $1,2B revenue **cuenta dos veces** el NdPr que se consume en imanes.
- Liquidez real $1.452,6M (no $429M) → **el test de atraso de MP se apoya en un dato mal**.
- Deuda LP ~$934,6M ≈ dic → el préstamo JPM/GS de $1B **no se desembolsó** (el dossier lo da por hecho).
- "Pérdidas de Magnetics" **falso**: 2T26 segmento +$7,5M Adj EBITDA.
- "Cayó >50% en 2026" → en realidad **−20% YTD** (el −50% es desde el máximo de oct-2025). Bull y tesis PM
  ("ya descuenta") apoyados en dato mal fechado (C13 cortada en "since…").
- Base de crecimiento mezclada: FY2025 ($224M) para el CAGR + run-rate 2T26 para el múltiplo → desde $505M es
  **~28% CAGR, no 50%**.
- PPA Income $51M (FY2025) → $17,6M (2T26): la variable que define si el upside es todo de MP o 70/30 con el
  DoW; el dossier **no la sigue**.
- Faltan: Dy/Tb (Mountain Pass es de livianas; 10X necesita pesadas, dependencia), **vencimiento chino del
  10/11/2026** (controles — evento más binario del spot, a 8 días, 5 tras earnings; no está en catalizadores),
  y **Lynas** (el "hemisferio occidental" lo esconde).
- Decisión: lo indefendible **no es el 3%** sino **ejecutar el 2/11 sin modelar earnings del 5/11 ni el
  vencimiento chino del 10/11** → correspondía reconstruir la valuación y escalonar la entrada.

## 6. OKLO / RGTI — ajustes de contenido (van a prompt o a verificación)

- **OKLO:** falta el **acuerdo con Meta** (1,2 GW Pike County, prepago + fondos para combustible; ES el
  escenario "1-2 GW" que justifica el precio) → tracción **2, no 1**. Groves **sobreponderado** (reactor de
  pileta 15 MWt, 100 W autorizados, sin electricidad; vía DOE compartida, no es foso). Combustible: el riesgo
  2028 es **fabricación**, no oferta de HALEU (INL ya asignó el primer núcleo; Centrus 2029 es para Ohio).
  Faltan: **rechazo NRC 2022** (el mejor precedente del bear) y competidores de sodio (**TerraPower**, Kairos,
  X-energy). Riesgo remanente → **costo/regulación**, no ingeniería. "1-2 GW" sin modelo: en owner-operator el
  valor = TIR − costo de capital; la variable que manda es **capex/kW**. Liquidez/acción ~$16 vs $25 (64%),
  dato clave para valuar la opción, ausente.
- **RGTI** (el dossier más coherente según IA3): faltan datos de los propios reportes — **gradiente de
  fidelidad** (99,8%@9q / 99,6%@36q / 99,1%@108q = la tesis en una línea), **coherencia 25-30µs** como causa
  (líderes ~100µs+), update de roadmap en 2026 (suele anticipar atrasos), revenue **concentrado** (C-DAC
  $8,4M en 4T26 = pico, no tendencia). Riesgo **"científico" mal etiquetado** → ingeniería/materiales +
  captura + mercado (IBM/Google ya probaron que es físicamente posible). Gatillo de entrada = mismo umbral del
  falsador → **débil** (comprarías la noticia a peor precio por un hito que no cambia competitividad).

## 7bis. ESTADO (2026-11-02)

**Tier A — CERRADO** (reproducido con datos reales → fix → test de regresión → commit, 689 tests verdes):
- **B2** ✅ liquidez (resolver de valores negociables por candidatos: reconstruye EXACTO $1.452,6M MP /
  $3.006B OKLO / $541,3M RGTI) + runway capex-aware (quema FCF = operativo − capex). commit 59215d1.
- **B4** ✅ `browse-edgar`/full-text-search ya NO es `primaria_regulatoria`. commit 59215d1.
- **B1** ✅ señal `dilucion_overhang` (convertibles/warrants que XBRL no cuantifica) + ventana explícita del %
  realizado. NO se fabrica el as-converted (es Fase 2). MP/RGTI disparan, OKLO no. commit 173f99d.
- **B6/B5 → reclasificados a Tier B**: no son del pack determinista sino del LLM (escribe su runway en la
  ficha / cita dato viejo). Se arreglan con disciplina de prompt + Verificador.

**Limitación conocida (→ Tier B):** para nombres **pre-construcción** (OKLO) el capex HISTÓRICO es chico; la
restricción real es el capex FUTURO de la flota ($525M/planta según Piper), que es forward-looking y lo modela
el Analista con escenarios, NO el pack histórico. El determinismo ahora da el dato correcto; el futuro lo razona
el LLM (es justo el límite determinismo↔juicio).

## 7. Plan ordenado

**Tier A — bugs deterministas (reproducir → fix → test → commit).** No requieren triangulación, son defectos.
B1 (dilución as-converted), B2 (runway con capex + concepto de caja correcto), B4 (browse-edgar no es
primaria), B6 (consistencia pack↔ficha), B5 (frescura). Impacto directo en la calidad del dato que recibe el
Analista.

**Tier B — cambio de método (DISEÑO antes de codear, patrón de triangulación del repo).** El puente económico
al precio (4 preguntas de IA2 + descuento/IRR por escenario), falsadores con vara competitiva/económica, tasas
base con fuente o marcadas como juicio, y el **sizing que diferencie clasificación** (§4). Esto toca prompts
(Analista/Bear/PM), probablemente el schema de la ficha, y la lógica de tamaño. Se diseña y se consensúa antes
de tocar.

**Tier C — verificación puntual MP (§5)** contra 10-K/10-Q: términos del contrato DoD, liquidez, deuda,
dilución as-converted, estado del préstamo JPM/GS. Define si la posición comprada se sostiene.

**Conclusión para el operador:** la intuición de **congelar la corrida del universo** fue correcta. El sistema
caza riesgos bien, pero todavía no valora la oportunidad ni ata el futuro al precio, y compró el nombre con más
errores de dato. Primero Tier A + C (que el dato sea correcto), después Tier B (que el análisis del futuro sea
económico), y recién ahí el universo.
