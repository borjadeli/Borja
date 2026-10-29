# 63 — Auditoría del brief embudo + verificador (doc 61) — IA 2

> Devolución de **IA 2** (2026-10-28). Converge fuerte con IA 1 (doc 62) y la complementa con una **cuenta de
> capacidad** que cambia el encuadre. Captura fiel. Convergencia → doc 64.

## La cuenta que enmarca todo (aporte propio de IA 2)
$40/mes ≈ **$9.2/semana** ≈ ~13 profundos/sem si todo fuera deep. Los 2-4 previstos ($1.4-2.7) usan **apenas
15-30% del sobre**. Cubrir los 135 una vez = **~$92**; mantenerlos vigentes a 35d exigiría ~27 deeps/sem
(~$79/mes) → **imposible**. **Dos conclusiones:** (1) la mayor parte del universo estará SIEMPRE sin dossier
vigente → **el embudo es un problema de PRIORIZACIÓN, no de filtrado**; (2) hay **holgura real para más de 4
deeps/sem**, y quien más la necesita es el **bootstrap (A3)**.

## A. Embudo
- **A1 — el default NO es correcto (3 problemas):**
  - **"posición" como disparador solo rompe el sobre** (8 posiciones = 8 deeps/sem = 60% del sobre sin que
    pase nada). Ser posición debe **BAJAR los umbrales de los otros disparadores**, no disparar por sí misma;
    una posición sin novedades reutiliza.
  - **"filing nuevo" dispara casi todo** → **whitelist** (coincide y precisa a IA 1): periódicos
    10-K/10-Q(+enmiendas); **8-K solo ítems 1.01/1.02/2.01/2.02/2.05/2.06/3.01/4.01/4.02/5.02**; dilución
    S-1/S-3/424B5; activismo SC 13D; **NT 10-K/NT 10-Q como alarma**; **Form 4 solo compras P > ~$100k o
    cluster ≥2 insiders/30d**. El filing que pasa la whitelist va **primero a Haiku** (¿toca la tesis?) y
    recién ahí a deep — **la doble etapa es lo que hace funcionar el embudo**.
  - **"earnings ≤14d" está AL REVÉS:** un deep 10 días antes del balance queda obsoleto y el 10-Q redispara →
    pagás dos veces. El disparador correcto es el **evento CONSUMADO** (8-K 2.02 / 10-Q). Para no-posiciones,
    `dias_a_evento ≤ 10` → **señal para DIFERIR**, no para disparar.
  - **precio > X% fijo no sirve** (vol heterogénea; OKLO/RKLB mueven 15% sin noticias, otro rompe tesis con
    8%). Usar **movimiento residual normalizado** desde la fecha del dossier:
    `z = (r_nombre − β·r_IWM) / (σ_resid,60d · √n)`, n=días desde dossier. Umbral **|z| ≥ 2.5** no-posición,
    **≥ 2** posición, con respaldo absoluto ±25%.
  - **OR booleano contra ranking:** en temporada reportan 25-30/sem; con OR todos elegibles → hace falta
    **orden explícito:** (1) posición con evento · (2) red flag (4.02/4.01/NT/3.01) · (3) dilución · (4)
    earnings con cambio que Haiku marque relevante · (5) precio · (6) cobertura. `prioridad_cuello` = desempate
    dentro de cada nivel.
- **A2 — correcto.** Triage de todo semanal + posiciones a diario (EDGAR gratis). 2 verificaciones: (1) el
  hash del data pack **no** debe incluir precio/fechas diarias (si no, nunca reutiliza) — *ya resuelto en
  nuestro paso 2*; (2) **día 36 sin novedades:** el dossier **sigue usable** marcado "sin hechos nuevos desde
  X", NO dispara deep; vigencia por eventos (filing material / |z|), con **techo ~100 días**.
- **A3 — 1-2/sem es DEMASIADO LENTO.** Si casi todo está sin analizar, la 1ª pasada tarda 70-135 semanas →
  >1 año rankeando por mapa, no por evidencia. **5-6/sem las primeras ~10 semanas** (~$15/mes del
  `presupuesto_bootstrap_usd`), después bajar a 1-2. Orden: (1) **gate de invertibilidad** (market cap + ADV
  mínimos del IPS — no gastar en lo que no se puede comprar) · (2) `prioridad_cuello` · (3) desempate por
  10-Q reciente (data pack fresco = dossier dura más) · (4) excluir los que reportan ≤10d. **Reservar ~1 de
  cada 5 slots a un nombre AL AZAR** entre los invertibles (si el mapa está mal, es la única forma de
  enterarte).
- **A4 — default correcto + mejora.** Con A1 corregido, la fecha futura solo sirve para **diferir** → no es
  bloqueante. Mejor que el ciclo de 10-Q: la **fecha del 8-K ítem 2.02 del mismo trimestre del año anterior**
  (el release precede al 10-Q; error ±1 semana). Respaldo: plazos regulatorios (10-Q 40/45d, 10-K 60/75/90d
  según filer); si vence y no hay filing → buscar **NT 10-Q = red flag fuerte** para `tiene_evento_fuerte`.
- **A5 — orden bien, ventana mal.** **Sobre MENSUAL con arrastre, no cupo semanal rígido** (demanda
  estacional: el cupo semanal desperdicia en semanas vacías y recorta en temporada). Escalera sobre el MES:
  <70% todo · 70-90% se cortan bootstrap+cobertura · 90-100% solo posiciones con evento + red flags · 100%
  solo red flag en posición con override manual. **Piso de cobertura 1/sem** salvo en el escalón 90%.
  Reservar **~10% del sobre para re-corridas** (ver B2).

## B. Verificador
- **B1 — dirección correcta, 3 ajustes:**
  1. **Quién define "central".** Si lo etiqueta el Analista, baja a secundario lo que no pudo probar
     (coincide con IA 1). "Central" por **estructura:** todo claim que aparece en **valuación, catalizadores o
     kill-criteria**. + **set OBLIGATORIO para small caps:** ingresos, caja/runway, deuda, acciones + su
     variación (dilución). Si falta alguno → **no hay PASS**.
  2. **"company_statement sin contraste → REVIEW" castiga a las pre-revenue** (su core — licencias/backlog/
     contratos — no está en XBRL). Distinguir por **tipo de fuente:** afirmación de la compañía **en un filing
     SEC** (10-K/10-Q/8-K, con responsabilidad legal) = **primaria**; solo en press release/IR/entrevista =
     **REVIEW**; licencia contrastada contra el regulador (NRC/FAA) = primaria regulatoria.
  3. **Sí se pierde señal ignorando los secundarios.** Un gap aislado no dice nada; una **tasa alta** dice que
     el Analista citó de memoria → contamina todo. Regla: **PASS con notas mientras los no-centrales sin
     procedencia sean ≤ 1/3 (o ≤ 3 absoluto); REVIEW por encima.** Separar: **falta URL = gap**; **URL que no
     resuelve o no sostiene el claim = cita fabricada = contradicción → REVIEW aunque sea 1**. Advisory:
     mostrar **"PASS · 3 notas" ARRIBA** del dossier, no enterrado.
- **B2 — NO anclar solo en numéricos** (coincide con IA 1: laxo donde importa; un contrato inventado pasaría
  como "nota"). La inestabilidad real = el veredicto depende de **qué claims eligió citar el Analista**. Fix:
  **el verificador deja de depender de esa selección** → siempre contrasta el **set obligatorio de B1.1
  contra XBRL tomándolo ÉL del data pack, aunque el Analista no lo cite**; lo cualitativo central sigue siendo
  gate (reglas de fuente de B1.2). **Probablemente B1 sola elimine la mayor parte de la oscilación** (venía de
  C7-C9/C14, que son secundarios). **Medir antes de aflojar más:** 5 nombres × 3 corridas (~$10), objetivo
  **≥4/5 con el mismo veredicto en las 3**; si no se llega, el problema es la clasificación central/secundario
  (reforzar B1.1), no degradar lo cualitativo.

## Orden sugerido por IA 2
1. **A1** (whitelist + posición como modificador de umbrales + earnings post-evento) — ahí está el riesgo de
   gasto. 2. **B1**. 3. **test de B2** (estabilidad). 4. **bootstrap acelerado A3**.
