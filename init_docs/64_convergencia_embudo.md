# 64 — Embudo + verificador: resolución convergida (IA 1 + IA 2)

> Síntesis de las dos auditorías del brief doc 61 (IA 1 doc 62 · IA 2 doc 63). **Convergen fuerte.** Este doc
> CIERRA las decisiones y es de lo que se codea. No reabre paradigma/método/comité. Supera al brief doc 61
> en todo lo que contradiga.

## Los 2 insights que ordenan todo (uno de cada IA, compatibles)
- **IA 1:** el embudo gasta por **VALOR INFORMATIVO INCREMENTAL, no por existencia de un evento**; el
  verificador decide por **CONFIABILIDAD DE LOS HECHOS MATERIALES, no por cantidad de claims**.
- **IA 2:** con $40/mes el universo NUNCA estará todo vigente → el embudo es **PRIORIZACIÓN, no filtrado**; y
  hay **holgura** (2-4 deeps usan 15-30% del sobre) → el bootstrap puede ir MÁS rápido.

## Decisiones CERRADAS
### A — Embudo
- **A1 · Trigger ≠ deep (ambas, el cambio central).** Una señal genera un **candidato**; el **Triage (Haiku,
  ~gratis) decide** si va a deep. Nunca disparo automático de Analista+Bear. Pasos:
  - **Whitelist de filings** (lo demás = ruido, no dispara): 10-K/10-Q(+enmiendas); **8-K solo ítems
    1.01/1.02/2.01/2.02/2.05/2.06/3.01/4.01/4.02/5.02**; dilución S-1/S-3/424B5; SC 13D; **NT 10-K/NT 10-Q =
    alarma**; **Form 4 solo P > ~$100k o cluster ≥2/30d**. (Hoy `universo.py` ya excluye Form 4 y filtra por
    tipo; falta el nivel de ÍTEM del 8-K y las reglas de Form 4.)
  - **Posición = MODIFICADOR, no disparador** (IA 2): estar en cartera **baja los umbrales** de los otros
    disparadores; una posición sin novedades **reutiliza** (no deep semanal).
  - **Earnings: evento CONSUMADO, no anticipado** (ambas): dispara el 8-K 2.02 / 10-Q ya publicado. Para
    no-posiciones, `dias_a_evento ≤ 10` → **DIFERIR** (no gastar un deep que el balance deja obsoleto).
  - **Precio: movimiento residual normalizado**, no % fijo (IA 2): `z = (r_nombre − β·r_IWM)/(σ_resid,60d·√n)`,
    n=días desde dossier. Umbral **|z|≥2.5** no-posición, **≥2** posición; respaldo absoluto ±25%. (β/σ de la
    serie de precios ya disponible.)
  - **Orden de prioridad (no OR booleano):** (1) posición con evento · (2) red flag (4.02/4.01/NT/3.01) ·
    (3) dilución (S-1/S-3/424B5) · (4) earnings consumado con cambio que Haiku marque relevante · (5) precio ·
    (6) cobertura. `prioridad_cuello` = desempate dentro del nivel.
  - **Deduplicación:** N filings del mismo evento → **1 candidato** (IA 1).
- **A2 · Re-screening — CERRADO:** triage de las 135 **semanal** (sin rotación) + **detección diaria** de
  filings/precio/posiciones en días hábiles. Dossier al **día 36 sin novedades = sigue usable** ("sin hechos
  nuevos desde X"), no dispara deep; vigencia por eventos con **techo ~100 días**.
- **A3 · Bootstrap ACELERADO (IA 2):** **5-6/sem las primeras ~10 semanas** (~$15/mes del
  `presupuesto_bootstrap_usd`), después 1-2/sem. Orden: (1) **gate de invertibilidad** (market cap + ADV
  mínimos del IPS) · (2) `prioridad_cuello` · (3) desempate por 10-Q reciente · (4) excluir los que reportan
  ≤10d. **~1 de cada 5 slots a un nombre AL AZAR** entre los invertibles (chequeo del mapa).
- **A4 · Earnings — CERRADO:** solo sirve para **diferir** (no bloqueante). Estimación: **fecha del 8-K 2.02
  del mismo trimestre del año anterior** (±1 sem); respaldo plazos regulatorios; **NT 10-Q vencido = red flag
  fuerte**. Guardar `fecha, fuente, confidence, tipo_fecha`.
- **A5 · Presupuesto MENSUAL con arrastre (IA 2), no cupo semanal.** Escalera sobre el MES: <70% todo ·
  70-90% se cortan bootstrap+cobertura · 90-100% solo posiciones con evento + red flags · 100% solo red flag
  en posición con override. **Piso de cobertura 1/sem** (salvo escalón 90%). Reservar **~10% para re-corridas**
  (test B2). Prioridad de gasto (IA 1): riesgo material de posición > novedad material de candidata > cobertura
  > reanálisis sin novedades.

### B — Verificador
- **B1 · PASS con gaps secundarios documentados, con 3 guardas (ambas):**
  1. **"Central" lo define la ESTRUCTURA, no el Analista** (ambas, anti-gaming): es central todo claim en
     **valuación / catalizadores / kill-criteria**, + un **SET OBLIGATORIO small-cap**: ingresos, caja/runway,
     deuda, acciones + variación (dilución). **Falta uno → no hay PASS.** El verificador puede **RECLASIFICAR**
     a central lo que el Analista bajó a secundario.
  2. **Fuente, no formato:** afirmación de la compañía **en un filing SEC** (10-K/10-Q/8-K) = **primaria**
     (vale para el core cualitativo de pre-revenue: licencias/backlog/contratos); solo en press release/IR/
     entrevista = **REVIEW**; regulador (NRC/FAA) = primaria regulatoria. **Ausencia de XBRL ≠ contradicción**
     (es falta de contraste → otra fuente o REVIEW).
  3. **Tasa de gaps:** **PASS con notas** si los no-centrales sin procedencia ≤ **1/3 (o ≤3 absoluto)**;
     **REVIEW** por encima. **URL que no resuelve / no sostiene el claim = cita fabricada = contradicción →
     REVIEW aunque sea 1** (distinto de "falta URL" = gap). Contradicción secundaria **material** → REVIEW;
     trivial → nota. Advisory: mostrar **"PASS · N notas" ARRIBA** del dossier.
  - **Estados:** centrales verificados + gaps aislados → PASS+notas · central cualitativo con fuente primaria
    → PASS · central con procedencia pero corroboración insuficiente → REVIEW · contradicción secundaria
    material → REVIEW · central contradice primaria (chequeado período/unidad) → FAIL · central sin
    procedencia → FAIL · ningún central / falta del set obligatorio → FAIL. **Sin estado nuevo** (flags+notas).
- **B2 · NO anclar PASS solo en numéricos (ambas; el desacuerdo más fuerte con el default):** aprobaría una
  premisa cualitativa central falsa (contrato inventado, hito regulatorio que no ocurrió). Fix de estabilidad:
  **el verificador NO depende de qué citó el Analista** → contrasta **él** el set obligatorio contra el XBRL
  del pack aunque no esté citado; lo cualitativo central sigue siendo gate (reglas B1.2). **Medir antes de
  aflojar más:** **5 nombres × 3 corridas (~$10), objetivo ≥4/5 mismo veredicto en las 3**; si no, reforzar
  B1.1 (clasificación), no degradar lo cualitativo.

## Las 5 pruebas de regresión (IA 1) + el test de estabilidad (IA 2)
1. 135 sin eventos → **0 deeps** por re-screening (salvo cobertura). 2. 5 filings del mismo evento → **1**
candidato. 3. dossier vigente + 8-K material → la reutilización **no** lo oculta. 4. centrales verificados + 3
secundarios sin URL → **PASS con notas en ambas corridas**. 5. numéricos verificados + premisa cualitativa
central contradicha → **FAIL** sin importar la etiqueta del Analista. + **estabilidad:** 5×3 corridas, ≥4/5
igual.

## Orden de implementación (convergido; A1 primero = el riesgo de gasto)
1. **A1** — whitelist con ítems de 8-K + posición-como-modificador + earnings post-evento + orden de prioridad
   + dedup. **+ 2 bugs técnicos de IA 1:** el cache no puede ocultar un 8-K material (evento invalida reuse);
   `known_at=null` necesita **cursor de monitoreo inicial** (no tratar todo el historial como nuevo).
2. **B1** — central por estructura + set obligatorio + fuente-no-formato + tasa de gaps + reclasificación.
3. **Test de estabilidad B2** (5×3) — medir; recién si falla, reforzar.
4. **A3** — bootstrap acelerado 5-6/sem + gate de invertibilidad + slot al azar.
5. **A5** — presupuesto mensual con arrastre + escalera mensual.

## Lo que NO se re-abre
Paradigma, método, comité, capa de decisión, contraste numérico por `ref`. Esto es **priorización del gasto**
(A) y **veredicto por hechos materiales** (B).
