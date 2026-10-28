# 61 — Brief para triangular: el EMBUDO de costo + la semántica del verificador (v2)

> Para iterar con 2+ IAs antes de codear (mismo método que docs 56-60). Contexto: P1 está hecho y validado
> (el PM compró OKLO en vivo); docs canónicos 51/52/53; economía real medida abajo. Dos preguntas de diseño:
> **(A)** cómo screenear MUCHAS empresas sin quemar el presupuesto (el embudo), **(B)** si el verificador es
> demasiado estricto para uso ADVISORY.

## 0. Economía real (medida, oct-2026) — no re-discutir, es el dato
- **Análisis profundo caro = Analista (Opus 5.5 + web) $0.55/nombre + Bear (Sonnet+web) $0.13 ≈ $0.68/nombre.**
- **Triage (Haiku 5.5) ≈ $0** — y solo llama al LLM si hay hechos nuevos; si no, es determinista puro (gratis).
- Reutilización de un dossier vigente (<35d, hash estable del data pack) = **$0**.
- Presupuesto del operador: **$40/mes** (IPS). Dimensionado para: triage de TODO el universo + **~2-4 análisis
  profundos/semana** + monitoreo barato de posiciones.
- Universo hoy: ~135 empresas en `nx_empresa`.

## A. EL EMBUDO ("candidatos desde el universo") — lo que falta para "analizar muchas, pagar pocas"
**Arquitectura ya construida:** Triage (barato, todo el universo) → ranking → solo los seleccionados pasan al
Analista (caro) → reutilización + escalera de presupuesto (70%/90%/100%). **Lo que FALTA:** las
`SenalesTriage` REALES por nombre (hoy el smoke las fuerza → analiza todo → caro). Hay que computarlas
determinísticamente desde `nx_empresa` + EDGAR + precio, para que el Triage filtre barato.

**Señales deterministas propuestas (por nombre, sin LLM):**
- `dias_desde_dossier` (del cache) · `hechos_nuevos` = filings de EDGAR nuevos desde el `known_at` del último
  dossier · `dias_a_evento` = próximo earnings · `precio_vs_tesis_pct` = movimiento de precio · `es_posicion`
  (en cartera) · `tiene_evento_fuerte` (filing material / red flag) · `prioridad_cuello` (del mapa nx_nodo).

### ⭐ Decisiones abiertas (A)
A1. **¿Qué dispara el análisis profundo caro?** *Default:* una posición en cartera · un evento fuerte (8-K
    material / earnings dentro de ~14d) · un filing nuevo desde el último dossier · un movimiento de precio
    > X% · o el cupo de cobertura. Un nombre sin nada de eso → NO se analiza (se reutiliza o se saltea). ¿Los
    umbrales (X% de precio, N días a earnings) son los correctos?
A2. **Re-screening del universo:** ¿todo nx_empresa cada semana, o rotación (p.ej. 1/4 por semana)? *Default:*
    triage de todo (es ~gratis) + deep solo lo disparado.
A3. **Cupo de cobertura de nombres nuevos** (ya existe `cupo_cobertura`/`bootstrap`): ¿cuántos nombres nunca
    analizados se promueven por semana, y ordenados por qué? *Default:* 1-2/semana por prioridad de cuello.
A4. **Fuente del `dias_a_evento` (earnings):** EDGAR no da la fecha futura de earnings directo. ¿De dónde?
    (calendario de earnings de un feed; o se aproxima por el patrón trimestral de filings). *Default:*
    aproximar por el ciclo de 10-Q; feed de earnings = mejora.
A5. **Reparto del sobre semanal:** forzados (posiciones/eventos) primero, cobertura con el resto, bootstrap con
    tope propio (`presupuesto_bootstrap_usd`, ya existe). ¿Prioridad correcta?

## B. ¿El VERIFICADOR es demasiado estricto para ADVISORY?
**Hoy:** PASS exige que TODO claim (central Y secundario) sea trazable; un solo claim **no-central** sin URL
trazable → **REVIEW** (doc 54: "REVIEW = faltantes en lo no-central"). En el smoke, OKLO/RKLB cayeron a REVIEW
por claims SECUNDARIOS (C7/C8/C9, C14) sin procedencia — **sus centrales financieros SÍ verificaron contra
XBRL**. O sea: una tesis con los hechos críticos probados queda REVIEW por un detalle periférico.

**Tensión:** las auditorías de P1 (docs 57/58, D1) convergieron en que el veredicto debe ser sobre los
**HECHOS CRÍTICOS (centrales)**, no sobre todo. La regla actual contradice un poco eso. Y BORJA es ADVISORY:
el humano LEE el dossier; un secundario sin URL no invalida la tesis (el humano lo ve).

### ⭐ Decisión abierta (B)
B1. **¿Un gap NO-central baja a REVIEW, o la tesis puede dar PASS con los gaps listados como notas?**
    *Default propuesto:* **PASS** si (i) TODOS los centrales verifican (contraste XBRL por `ref_metrica`, o
    fuente primaria regulatoria) y (ii) ningún central contradice el XBRL. Los gaps no-centrales se reportan
    como **notas** (no bajan a REVIEW). **REVIEW** se reserva para: un central que es `company_statement` sin
    contraste, o una contradicción NO-central. **FAIL**: central sin procedencia, central contradice XBRL, o
    sin claims centrales. ¿Es correcto, o se pierde señal útil al no mirar los secundarios?
B2. **Estabilidad del veredicto:** el mismo nombre dio PASS y REVIEW en corridas distintas según qué claims
    citó el Analista. ¿El PASS debería anclarse SOLO en los centrales numéricos contra XBRL (deterministas y
    estables), y lo cualitativo ser siempre "nota", nunca gate? ¿O eso lo vuelve demasiado laxo?

## Lo que NO se re-abre
El paradigma (el LLM decide, el determinismo informa/limita), el método de análisis canónico, el comité ya
construido, la capa de decisión, el contraste numérico por `ref` (ya validado). Esto es sobre **(A) cómo
alimentar el Triage barato** y **(B) qué veredicto da el verificador** — no sobre quién decide ni cómo se analiza.
