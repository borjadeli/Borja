# 62 — Auditoría del brief embudo + verificador (doc 61) — IA 1

> Devolución de **IA 1** (2026-10-28). **Pendiente converger con IA 2** antes de codear. Dictamen: la
> arquitectura del embudo es correcta, pero modifica 6 de 7 decisiones. Dos errores con consecuencia
> económica: **A1** (trigger→deep automático) y **B2** (anclar PASS solo en XBRL). Captura fiel.

## Regla de cierre (el insight que ordena todo)
> **El embudo debe gastar por VALOR INFORMATIVO INCREMENTAL, no por mera existencia de un evento. El
> verificador debe decidir por CONFIABILIDAD DE LOS HECHOS MATERIALES, no por cantidad de claims citados.**

## A. Embudo
- **A1 — MODIFICAR (error económico).** Separar **trigger** (pasó algo) de **promoción a deep** (el Triage
  decide que amerita gastar). Un trigger genera un **candidato para el ranking**, NO una ejecución automática
  de Analista+Bear. Umbrales iniciales (defaults a calibrar, no óptimos):
  - posición en cartera → siempre monitoreo barato; **deep solo ante cambio material** (no todas las semanas).
  - 8-K **material** (financiamiento/equity/default/contrato — item, no 9.01 accesorio) → prioridad alta.
  - 10-Q/10-K con resultados nuevos no incorporados → prioridad alta.
  - earnings < 7d confirmados → candidato (no deep obligatorio).
  - movimiento > 12% **y** > 2σ a 5 ruedas (σ = vol realizada 20 ruedas, ajustada) → candidato.
  - movimiento acumulado > 20% sin explicar desde la última eval → candidato.
  - sin novedades + dossier vigente → reutilizar. Nunca analizada sin trigger → solo por cupo.
  - **3 correcciones:** (1) el TIPO de filing da prioridad preliminar, no materialidad (hay que mirar el item;
    sumar S-3/424B5/NT 10-Q/6-K); (2) un movimiento de precio NO es info fundamental (genera candidato, no
    deep); (3) una posición no justifica deep semanal si nada cambió.
  - **2 bugs técnicos señalados:** (a) **el cache de 35d no puede ocultar un evento nuevo** — un 8-K material
    debe invalidar la evidencia / saltear la reutilización, sin que el cambio diario de precio invalide todo
    el cache; (b) **empresas nunca analizadas (`known_at=null`) NO deben tratar todo el historial como
    nuevo** → hace falta un **cursor de monitoreo inicial** separado de la fecha del último dossier, o el
    bootstrap dispara el universo entero.
  - **Veredicto:** mantener las familias de señales; cambiar "disparo automático" por "candidato elegible con
    prioridad + **deduplicación de eventos**" (5 filings del mismo evento = 1 candidato).
- **A2 — MANTENER.** Screenear las 135 semanal, sin rotación por cuartos (triage ~gratis). Pero **2
  frecuencias:** señales completas semanal; **detección de filings nuevos + precio + monitoreo de cartera
  DIARIA** en días hábiles (un 8-K del martes no espera al screening semanal).
- **A3 — MODIFICAR levemente.** Objetivo **1 nombre nuevo/semana** (no 1-2 fijo); 2º solo si hay capacidad y
  no desplaza mejor candidato; 0 es válido; sin obligación de agotar cupo. Ordenar por `prioridad_cuello +
  encaje_tesis + novedad + información_faltante + diversificación_de_cobertura` (dimensiones para el Triage,
  no un score rígido) — evita gastar el bootstrap en empresas del mismo cuello con poca info incremental.
- **A4 — RECHAZAR el default.** El ciclo de 10-Q NO estima earnings (el 10-Q se presenta 40-45d post-cierre;
  la empresa anuncia antes). Jerarquía: IR oficial (confirmada) > comunicado/conference call > feed de
  earnings (confirmada vs estimada) > historial de anuncios > **historial de 10-Q solo como fallback de
  PERÍODO, nunca fecha de evento**. El **8-K Item 2.02** reconstruye anuncios históricos. Cada evento guarda
  `fecha, fuente, confidence, tipo_fecha (confirmed/estimated)`. Ventanas: 14d vigilancia → 7d candidato →
  publicación efectiva = prioridad alta. **Sin fecha confirmada no se fabrica countdown.** (Para una ya
  analizada, a menudo conviene esperar los resultados y gastar el deep con info nueva.)
- **A5 — MODIFICAR el concepto de "forzados".** No todo evento/posición activa gasto obligatorio. Prioridad:
  (1) **riesgo material de una posición** (liquidez/financiamiento/dilución/deuda/pérdida de contrato/tesis
  invalidada); (2) **novedad material de cualquier candidata** (una fuera de cartera con contrato
  transformacional puede ir antes que una posición que solo osciló de precio); (3) cobertura de nuevas
  (capacidad flexible); (4) reanálisis sin novedades (último; preferir reutilización). **Economía:** 2
  deeps/sem ≈ **$5.89/mes**, 4/sem ≈ **$11.79/mes** (Analista+Bear) → el resto de los $40 queda para lo demás.
  **2-4 deeps/sem es objetivo operativo, NO límite inamovible**: si hay 6 oportunidades una semana y 0 la
  siguiente, adaptarse dentro del **IPS mensual**. Mantener escalera 70/90/100% + cola de candidatos +
  reserva para eventos críticos; el bootstrap no debe comerse el presupuesto de monitoreo de posiciones.

## B. Verificador
- **B1 — ACEPTAR, con 2 correcciones.** Quitar el gate por gaps no-centrales (son notas). PERO: (1) **no todo
  lo no-XBRL es inverificable** — un central cualitativo (contrato de suministro por $X, cliente que concentra
  60%, obligación que requiere financiamiento, aprobación regulatoria necesaria) se verifica con filing/
  contrato/disclosure, sin `ref_metrica`; (2) **no toda contradicción secundaria es nota** — si afecta
  ejecución/riesgo financiero/dilución/catalizadores/premisas materiales → REVIEW. **Ausencia de XBRL ≠
  contradicción** (es ausencia de contraste → buscar otra fuente idónea o REVIEW). **No crear estado nuevo:**
  se conserva PASS/REVIEW/FAIL + flags y notas estructuradas.
  - **Tabla de estados:** centrales verificados + gaps secundarios aislados → **PASS+notas** · central num
    XBRL + central cualitativo con fuente primaria → **PASS** · central con procedencia pero corroboración
    insuficiente → **REVIEW** · contradicción secundaria sin impacto → **PASS+nota** · contradicción
    secundaria MATERIAL → **REVIEW** · central contradice fuente primaria (chequeados período/unidad) →
    **FAIL** · central sin procedencia → **FAIL** · ningún central identificable/verificable → **FAIL**.
- **B2 — RECHAZAR (demasiado laxo). El desacuerdo más fuerte.** Anclar PASS SOLO en XBRL permite aprobar un
  dossier con una **premisa cualitativa central FALSA** (ej.: todos los números de OKLO verifican, pero la
  tesis dice que un hito regulatorio YA ocurrió cuando no — no debería dar PASS). Tres categorías: hecho
  central **numérico** → XBRL; central **cualitativo** → verificación documental con **fuente primaria**;
  **proyección/hipótesis/juicio** → no se exige probar la conclusión, pero SÍ sus **premisas materiales**.
  La pregunta correcta no es numérico vs cualitativo, es: **"si este hecho fuera falso, ¿cambiaría la tesis /
  el riesgo de supervivencia / la decisión?"** → si sí, es central y se verifica con evidencia apropiada.
  - **Inestabilidad entre corridas (error real del diseño actual):** anclar la verificación a **hechos
    NORMALIZADOS**, no al número/redacción de las frases. Mismo estado de info + mismas fuentes ⇒ mismo
    veredicto, aunque el Analista cite distintos claims secundarios. El conjunto de **centrales surge de las
    dependencias de la tesis + riesgos de supervivencia, NO solo de la etiqueta del Analista**: el Verificador
    **debe poder RECLASIFICAR** un central que el Analista bajó a secundario (anti-gaming). Normalizar también
    el objeto del claim cualitativo (contrato/fecha/contraparte/importe/evento regulatorio/obligación).
    Estabilidad **condicional**: si cambia una fuente o aparece un central nuevo, el veredicto puede cambiar.

## Las 5 pruebas de regresión que exige
1. 135 sin eventos → cero deeps por re-screening (salvo cobertura promovida).
2. 5 filings del mismo evento → **un** candidato consolidado, no 5 análisis.
3. Dossier vigente + 8-K material nuevo → la reutilización **no** oculta el evento.
4. Centrales verificados + 3 secundarios sin URL → **PASS con notas**, en **ambas** corridas (estabilidad).
5. Numéricos verificados + premisa cualitativa central contradicha → **FAIL**, sin importar cómo la etiquetó
   el Analista.

## Cierre (defaults que IA 1 dejaría cerrados)
A1 señales→candidatos, deep no automático · A2 universo semanal + detección diaria · A3 1 nuevo/sem objetivo ·
A4 earnings confirmado, 10-Q solo fallback de período · A5 riesgo/oportunidad primero, cobertura flexible, IPS
mensual · B1 PASS con gaps secundarios no-materiales documentados · B2 verificar TODOS los hechos críticos
normalizados (num Y cualitativos), nunca solo XBRL. **Sin nuevo comité, sin capa decisoria extra, sin score
determinista de inversión.**
