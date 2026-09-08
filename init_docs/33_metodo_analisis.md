# 33 — Método de análisis (CANÓNICO Y CERRADO)

> Cómo BORJA analiza y compara una empresa. **Cerrado y triangulado** (docs 27/28/31, 2 IAs
> convergieron en cada uno). Confirmado con el operador el 2026-08-10. **No se re-abre sin evidencia.**
> Esto es el MÉTODO (el qué/cómo conceptual). El ESTADO de implementación vive en [doc 32](32_estado_y_plan.md).

## La pregunta que responde
No "¿es buena empresa?" sino: **"a ESTE precio, ¿vale la pena tenerla, y qué tan sólida es la evidencia?"**

## El método, en 8 pasos
1. **Datos deterministas; el LLM nunca inventa números.** Revenue, margen, FCF, caja, deuda, shares,
   precio ← XBRL (EDGAR) + feed de mercado. El LLM solo trae **hechos cualitativos citados** (oración
   verbatim del filing, verificada). Nunca un valor de decisión.
2. **Se parte según si genera caja del accionista** (owner-FCF = FCF − SBC):
   - **Sí** → valuación operable (owner-FCF a futuro / r, r por arquetipo, cohort-free).
   - **No** (mayoría pre-revenue) → **reverse underwriting**: "¿cuánta economía exige el precio, y está
     financiada?" (el *burden*), en vez de "¿cuánto vale?".
3. **Forward-looking = el burden, no una proyección del management.** `FCFE_req = OP × r_exit ×
   (1+r_hurdle)^t` = la caja futura que el precio de hoy obliga a explicar a *t* años. Vara de falsación,
   no castillo de supuestos. (R0 físico: funded critical path / q×u×P → **Fase 2**, diferido.)
4. **Dilución = EJE SEPARADO, no se mezcla en la valuación.** Crecimiento real de acciones, SBC/revenue,
   burn/runway. Se penaliza solo si falla en **ambos** ejes (cara Y diluyendo). No se le fabrican
   economics a una pre-revenue con caja.
5. **Demanda = etapa de comercialización CALIFICADA para la tesis** (refinado 2026-08-11, triangulado 4 IAs).
   No es "encontré un cliente nombrado → tier". Un evento comercial cuenta solo si es **ELEGIBLE**, y la
   evidencia inelegible se **EXCLUYE (no se degrada) y se re-calcula el tier con lo elegible** ("hecho
   descalificado ≠ empresa sin demanda"). Gates de elegibilidad (binarios, citables):
   - **G1 counterparty_specific:** resuelve a una entidad concreta / soberano (U.S. Government ✓) / "Customer
     A" cuantificado. Rechaza categorías ("MNOs", "significant customers", "a few customers", "hyperscalers").
   - **G2 not_related_at_event:** no era parte relacionada al momento de la transacción (que la matriz divista
     después NO limpia el período; SMR/Fluor). Parte relacionada → EXCLUYE + va a fragility como dependencia.
   - **G3 vigencia** (diferido): el hecho es del período actual, no una columna comparativa vieja.
   - **G4 thesis-scope** (diferido): el revenue es de la línea de la tesis, no no-core (ASTS: equipos ≠
     servicio satelital). "Cero revenue de la línea core" hard-excluye. La tesis la define el humano; la IA
     solo matchea la cita a esa línea, no decide cuál es el core.
   Sobre eventos elegibles: acuerdo activo → **VALIDATED** · mínimo/take-or-pay → **COMMITTED** · revenue
   vigente y repetido → **REALIZED**. `tier = max(COMMITTED, REALIZED)`, y firm_commitment se guarda aparte
   (revenue pasado ≠ demanda futura asegurada). Se guardan **dos salidas**: el evento crudo + el tier
   calificado + el vector de gates (el decisor ve *por qué*, no solo *cuánto*). Endpoints canónicos: SMR→0,
   ASTS→1 (si hay MNO nombrado ligado al core, si no 0), TER→0 (a fragility), BWXT→REALIZED.
6. **El riesgo CAPEA, no puntúa:** fragility (concentración, etc.) → caps de tamaño; + eje dilución/runway.
   El riesgo saca del juego, no suma puntos.
7. **Arquetipo** (Madura/Growth/Tracción/Pre-revenue/Binary) fija r, caps y template. Binary NO se castiga
   con r (riesgo idiosincrático): se maneja por PoS + cap.
8. **Comparación (ver abajo).**

## Comparación — DELIBERADAMENTE de dos niveles (doc 31 §6)
Toda empresa cae en un bucket (FCFE_OPERABLE · CASH_POSITIVE · NON_FCFE · pure_option/R0 ·
manual_data_check) — **ninguna queda afuera**.

- **Nivel 1 — DENTRO del arquetipo (manzanas con manzanas):** orden económico real. Ordinal por menor
  burden/múltiplo donde hay ancla; el resto se muestra descriptivo **sin puestos 1-2-3** (una lista con
  ranking se lee como recomendación). **No hay score cardinal 0-10** que mezcle todo (= narrativa encubierta).
- **Nivel 2 — ENTRE arquetipos: NO hay un número único que las ordene a todas.** Es una elección, no un
  olvido: el payoff de un SaaS rentable (caja que compone) ≠ el de un nuclear pre-revenue (opción binaria).
  Entran juntas a la cartera **por construcción**: **tier de riesgo de capital COMÚN** (A/B/C: ¿financiada
  hasta su hito?) + **caps por sector/driver + diversificación de catalizadores** + **"lo mejor de cada
  arquetipo"** bajo esos caps. No "los 12 mejores de una lista mezclada".

## Las 5 decisiones de método (confirmadas)
- **A.** Datos deterministas + LLM solo para hechos citados.
- **B.** Dividir por owner-FCF: caja→valuar / sin caja→reverse underwriting.
- **C.** Forward-looking = burden (qué exige el precio), no proyección de guidance.
- **D.** Dilución como eje separado (penaliza solo si falla en ambos).
- **E.** Comparar dentro de arquetipo, ordinal solo donde hay ancla, sin score único cross-universe.

## Principio: la evidencia viaja con la señal, y la derivación debe ser correcta (2026-08-11)
Toda señal derivada (ej. el tier de demanda) **viaja con su CITA** hasta el PM — el PM decide sobre el
**hecho citado**, no sobre la etiqueta pelada (si le pasás solo "realizada" no puede cazar el matiz; con
la cita, sí). PERO **no se depende de que el PM/humano cace el matiz** (ej. que "Fluor 92%" es la matriz
de SMR = parte relacionada; o que el revenue de ASTS es venta de equipos, no el servicio core): eso
reintroduce el criterio/memoria que el sistema evita. **La derivación determinista debe ser correcta de
entrada** (capturar parte-relacionada / core-vs-no-core como hechos citados, que el filing divulga). El
hover/cita es **transparencia + red de seguridad, no el guardrail principal.** (Pendiente: hecho de
parte-relacionada para corregir el tier de SMR/ASTS — ítem scopeado, ver doc 32.)

## Diferido POR DISEÑO (no es olvido)
- Scenario compiler determinista (bull/base/bear con haircuts citados) — próximo escalón; haircuts a triangular.
- Funded critical path / q×u×P físico (R0 nuclear/espacio) — Fase 2 (notas + reguladores).
