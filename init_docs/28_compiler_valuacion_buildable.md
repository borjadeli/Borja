# 28 — Compiler y valuación: síntesis buildable

> Detalle de valuación del scenario compiler (doc 27 §5). Síntesis de la 2ª triangulación (dos IAs
> que **convergieron por tercera vez**). Filtrado por un gate duro: **solo entra lo IMPLEMENTABLE
> bien hoy** (dato sourceable + extraíble con cita + computable). Lo que exige datos que no tenemos
> → binario/null o diferido. Complementa init_docs/27; no lo reemplaza.

## 0. Principio de gobernanza (habilita todo lo demás)

El juicio no se elimina; se **reubica**: de la instancia (este nombre, hoy) a la **política** (todos
los nombres, siempre, hasta que cambie la versión). Un número deja de ser "juicio razonable" cuando:
1. **Precedencia fijada ex ante** — la fuente se elige sola por disponibilidad, no la elegís.
2. **Estimador fijado ex ante** — declarado antes de ver el dato (p.ej. percentil 25).
3. **Constante global y versionada** — cambiarla **bumpea la versión y obliga a recorrer TODA la
   cartera.** (Si mover un múltiplo rompe otros 8 nombres, no lo movés para salvar 1. Es la regla
   más importante del sistema: mata la revisión de constantes para salvar una tesis.)

Los números de las tablas de acá son **priors de política versionados, no verdades empíricas**. Se
calibran contra historial propio a los ~8 trimestres de operación; al calibrar, se recorre la cartera.

## 1. Admisibilidad de lo contratado

**Regla dura: lo condicional NO lleva haircut — se saca del bull y va al option ledger.** El haircut
solo modela **ejecución imperfecta de algo YA obligatorio**. Un haircut sobre algo condicional es el
mecanismo por el que la opcionalidad se cuela en la valuación disfrazada de número.

**Tabla de retención por tipo de contrato** (retención = 1 − haircut; priors versionados):

| Tipo de contrato | Retención | Qué la invalida |
|---|---|---|
| Take-or-pay, mínimo especificado, contraparte solvente | fracción contractual mínima (cap 0.90) | renegociación, quiebra de contraparte |
| Task order gubernamental **fondeada y obligada** | 0.90 | rescisión, protesta sostenida, continuing resolution |
| Techo IDIQ / "valor potencial hasta $X" | **0 → ledger O3** (no es backlog) | — |
| PO comercial en firme, no cancelable | 0.85 | cambio a términos cancelables |
| Backlog cancelable sin penalidad | 0.60 | — |
| LTA con bandas | solo el **mínimo comprometido**; resto → O3 | — |
| Award con condición precedente (funding/licencia/FID) | **0 → ledger O3** | condición cumplida y citada → promueve a O4 |

**Solvencia de contraparte** (una de las reglas de mayor rendimiento — crítica en HALEU/SMR/fotónica
de defensa, donde la contraparte suele ser tan pre-revenue como el emisor). MVP **binario**:
investment-grade / soberano / gran-público → cubierto (coverage=1); contraparte desconocida o
pre-revenue → la porción no cubierta **degrada a O4** (contrato firmado, cobrabilidad no establecida),
no entra al operable.

**Filtro de horizonte** (separado del haircut): solo entra al bull el backlog con schedule dentro de
T. Sin schedule declarado → conversión lineal sobre el término del contrato. **T se fija por
arquetipo en la política, nunca por nombre** (anti horizon-creep).

**Fallback sin P1/P2/P3** (DECISIÓN adoptada — piso, no cero): todo hecho contratado sin cláusula ni
historia entra al **piso universal 0.50**. **Cap agregado:** si > 40% del incremento del bull
(bull − bear) viene de hechos con `haircut_source = piso`, el nombre se marca `evidencia_insuficiente`
y **no puede tomar sleeve completo**. (Excluir crearía el incentivo de no buscar el dato; piso + cap +
flag es más honesto: el número entra, pero el sistema avisa que el bull está construido sobre política.)

**P25 de conversión histórica** (el estimador real de ejecución) → **diferido** (necesita ≥6-8
vintages que hoy no tenemos). MVP: fallback de arriba + gate de entregabilidad binario {0,1}.

## 2. Bridge de valuación (cohort-free en el MVP)

Mismo bridge en los cuatro arquetipos; cambian solo margen/terminal/funding:

```
Revenue_operable(T) × margen(T) → métrica valuable → DCF a r → EV(0)
  + caja − deuda − FundingGap → equity(0) ÷ acciones_diluidas(T) → precio
```

**DECISIÓN: cohort-free.** Márgenes de **historia propia** (no de cohorte): bear = mínimo 8Q,
bull = mediana 8Q. Terminal = **UFCF/r con g=0** (no múltiplo de cohorte — evita el plumbing de peers
y la fuga de "cohorte elegida después de ver el nombre"). `r` = constante de política por arquetipo
(**12 / 15 / 20 / 25%** para madura / growth / tracción / pre-revenue), nunca por nombre.

**Tres invariantes que aplican siempre:**
- **I1 — Techo físico:** `Revenue_bull(T) ≤ capacidad_FONDEADA(T) × ASP_conservador`. Capacidad
  fondeada (FID cerrado o capex ya gastado citado), no anunciada.
- **I2 — Bear despojado:** bear = revenue actual **menos no-recurrentes** (NRE, grants, subsidios,
  venta de equipo, contratos de desarrollo únicos). Un bear con un grant del DOE es un bull disfrazado.
- **I3 — Dilución obligatoria:** si el FCF acumulado a T es negativo, el gap se financia con equity a
  **precio − 20%**; las acciones suben. Sin esto el bull de una pre-revenue es fraudulento por
  construcción (valuás el activo y te regalás el pasivo).

**Terminal por arquetipo:** madura sí (g=0) · growth solo con 4Q de FCF+ · tracción y pre-revenue **no**.

## 3. Templates por arquetipo (filtrados)

- **A. Madura:** métrica EBIT; bear = TTM despojado plano × margen mín-8Q; bull = TTM + contratado×retención × margen mediana-8Q; r 12%.
- **B. Growth:** igual pero métrica = **gross profit** (con opex de inversión, el EBITDA es decisión contable). r 15%; I3 muerde fuerte.
- **C. Tracción:** el múltiplo sobre revenue chico no significa nada → anclar en capacidad:
  `Revenue_bull(T) = min(capacidad_fondeada × ASP_contratado, volumen_contratado × ASP_contratado)`.
  ASP del **contrato citado**, no del mercado. Utilización = volumen_contratado / capacidad (no se
  asume). Bear = caja neta + PP&E×0.30 − burn a T; intangibles 0. r 20%.
- **D. Pre-revenue / física** (resolver sobre **cantidad**, no TAM): exponer **cuatro números por
  separado**: `S(T)` demanda global del cuello (fuente oficial fechada+versionada: WNA/USGS/DOE/SEMI),
  `q(T)` capacidad permisada Y fondeada (licencia+FID+hito, citados), `u` utilización (constante:
  60% FOAK / 85% NOAK), `P` precio (**p25 trailing 3y, nunca spot pico**). `Revenue_bull = q·u·P`.
  `share = q/S` es **output que se reporta, no input**; share > 20% sin planta operando = flag
  automático. Bear = caja neta − burn a T + PP&E×0.30, resto 0.

**Pre-revenue — no reportar el ratio de asimetría:** con bear→0, `(bull−precio)/(precio−bear)`
colapsa a `bull/precio` = upside, no asimetría; presentarlo como ratio es auto-engaño con formato de
rigor. Reportar **"capital en riesgo = 100%"** y dimensionar por eso (sleeve).

## 4. CAGR implícito — falsador, no generador

No produce el precio (sería circular). Invirtiendo el bridge desde el precio actual con la r del
arquetipo: **¿qué revenue(T) descuenta hoy el mercado?** Si `revenue_implícito ≥ revenue_bull_operable`,
el mercado **ya paga tu bull entero con evidencia contratada** → la tesis solo vive en el option
ledger, **fuera del libro principal.** Es el chequeo que **mata más tesis y el más barato**.

> ⚠️ **SUPERSEDED (doc 29):** el "**sleeve 2%** por nombre" que decía este §4 (y doc 27 §7) **se SACÓ**.
> Lo reemplazó el **carril especulativo** (doc 29, 3ª triangulación): un nombre ya-priceado no recibe un
> 2% fijo — es pura opcionalidad y solo entra si pasa el **gate del carril**, dimensionado por sus reglas
> (cap 8%/pos, máx 2 plazas, presupuesto agregado 10%→25% ganado por hit-rate). Ver doc 29.

## 5. Option ledger O0–O5

De **O2 para arriba, el avance exige un documento de contraparte / regulador / registro público.**
Comunicación de la empresa sola nunca promueve más allá de O1.

| Estado | Dispara el avance | Emisor válido | Regresión / caducidad |
|---|---|---|---|
| O0 Narrativa | intención / TAM / "conversaciones" | empresa | caduca a 12m sin avance |
| O1 Programa | nº de solicitación/RFP, línea de apropiación, capex del cliente que nombra la tecnología | registro/gobierno/cliente | programa cancelado/desfinanciado → O0 |
| O2 Calificación | vendor list, aceptación de muestras, cert (NQA-1/AS9100/ITAR), NRE pagado | cliente/certificador | descalificación, cert vencida → O1 |
| O3 Award/design-win | aviso de award con nº, registro de adjudicación, confirmación de design-win | cliente/registro público | protesta sostenida, 2ª fuente, rediseño → O2; 18m sin firma → O2 |
| O4 Contrato | filing de contrato material o ejecución explícita con valor+término | empresa (con filing) | cobrabilidad no establecida lo retiene; al entrar sale del ledger → Contratada con su haircut |
| O5 Revenue | línea financiera + disclosure de concentración | auditor | restatement → O4; Realizada = 100% |

**Mostrar del ledger, sin valuar:** conteo por estado y, por hecho, la **magnitud física** en juego
(t/año, obleas/año) + el revenue que implicaría si convirtiera, etiquetado **no-valuado**. **Nunca una
probabilidad ni una suma ponderada** (una suma ponderada es una probabilidad con otro nombre). **El
ratchet es el enemigo:** las regresiones/caducidades son la mitad del mecanismo.

## 6. Dos mecanismos transversales (baratos, van al MVP)

- **Archivo de política versionado:** todos los haircuts, retenciones, r, utilizaciones, horizontes,
  pisos en UN archivo con `version + fecha_efectiva + hash`. Cada output estampa la versión. **Un
  output sin versión de política no es auditable.** Cambiar una constante bumpea la versión (regla §0).
- **Registro de falsación por nombre:** 3-5 hechos pre-registrados que invalidarían el bull, cada uno
  con **fecha de chequeo**; si la fecha pasa sin que el hecho aparezca → **degradación automática**.
  Convierte "la tesis sigue viva" de omisión en decisión firmada. (Es el evidence-decay del doc 27 §11,
  hecho concreto y por-nombre.)

## 7. Los 10 vectores de auto-engaño (checklist del compiler)

1. Techo IDIQ / "hasta $X" como backlog (nº 1 en defensa/espacio/DOE) → ruteado a O3, sostener.
2. Contraparte insolvente con contrato firme (norma en SMR/HALEU) → §1 solvencia.
3. Dilución omitida → I3.
4. Bear con no-recurrentes (grant DOE, NRE) → I2.
5. Cohorte elegida después de ver el nombre → cohort-free en MVP (se evita de raíz).
6. `q` y `S` blandos en el template físico → exponer separados, fechados, versionados.
7. Doble conteo LTA + PO → una fuente canónica por flujo económico.
8. Horizon creep → T por arquetipo en política.
9. Precio de commodity en el pico → p25 trailing.
10. Revisión de constante para salvar una tesis → regla §0 (bumpea versión, recorre cartera).

## 8. Implementabilidad (el gate del operador)

- **Buildable bien hoy (XBRL + filings citados + precio + US10Y):** bridge DCF cohort-free (A/B/C con
  revenue), r policy, I2/I3, tabla de retención por tipo, ruteo condicional→ledger, solvencia binaria,
  CAGR falsador, O0-O5 como clasificación, archivo de política + registro de falsación, "null cuando
  no hay puente".
- **Binario/null:** EnforceableAmount por contrato (usar si está limpio; si no → ledger), ExecutionFactor {0,1}, serie temporal (distribución simple).
- **Diferido:** P25 de vintages (a los 8Q), template físico D (solo nombres con `q`/`S` curados a mano; si no → null/rango), calibración de priors.

## 9. Primera tajada a construir (propuesta)

Barato y de alto rendimiento, sin datos nuevos: **(1)** archivo de política versionado (esqueleto) ·
**(2)** tabla de retención por tipo de contrato en `admisibilidad` · **(3)** CAGR implícito falsador
sobre el bridge mínimo (madura/growth desde XBRL). Con eso el compiler ya emite bull/bear operable +
el chequeo que más tesis mata, todo trazable y versionado.
