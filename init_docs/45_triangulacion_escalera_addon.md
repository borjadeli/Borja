# 45 — Triangulación: escalera de add-on (underwriting escalonado / sostener y agregar)

> Bloque 4.2 del plan (doc 40). La ÚNICA decisión de método abierta que queda (docs 39 §3 la nombró como pieza
> crítica —"el retorno se gana sosteniendo y agregando"— pero NO cerró la mecánica). Está entangled con la banda
> de sizing (base<techo). El operador circula a 2 IAs; el asistente prepara. Ver [[rebalanceo-determinismo-juicio]].

---

## PROMPT (copiar tal cual a cada IA, por separado)

Sos un PM/quant worldclass con experiencia REAL en small/mid caps de tecnología emergente. Necesito cerrar UNA
mecánica: cómo escalar en una posición a lo largo del tiempo (add-on / underwriting escalonado). Sé adversarial
y concreto (specs implementables); no me halagues.

### Contexto del sistema (no negociable)

Sistema determinista y auditable para small/mid caps de "industrias del futuro" (~70% pre-revenue). El LLM solo
extrae hechos citados de filings (EDGAR/XBRL); tablas versionadas deciden. Ya tengo cerrado:
- **Valuación por reverse underwriting** (falsación, no proyección): para comerciales, despejo `T*` = años de
  crecimiento que el precio exige vs lo demostrado; para pre-revenue binarias, la probabilidad requerida vs base
  rate. Output = estado ∈ {COVERED, STRETCH, OPTION_PRICED, NON_UNDERWRITABLE}.
- **Sizing** = `min()` de caps independientes (supervivencia/tier, valuación, liquidez, arquetipo). Ese min es el
  **TECHO** de una posición.
- **Canal de juicio acotado:** un PM-LLM emite etiquetas discretas (no números); un allocator determinista las
  traduce; hay presupuesto de promociones + ledger de hit-rate.
- Filosofía: **disciplina sobre actividad, power-law** (los outliers pagan la cartera; casi todo el retorno viene
  de pocos nombres). No intento predecir CUÁL gana; busco RECALL (exposición disciplinada) + no fundirme + sizing.

### El problema exacto

Todo mi sistema es de ENTRADA (decide comprar o no, y a qué techo). Pero en esta clase de activo el retorno se
gana **sosteniendo y AGREGANDO** sobre confirmación, no eligiendo perfecto al inicio. El modelo VC: posición
inicial chica (probe), add-on sobre milestone. Quiero una **escalera de add-on PRE-REGISTRADA** (escrita ANTES,
para no mover el arco cuando el precio sube y la narrativa mejora). Hoy la posición se dimensiona de una a su
techo; falta la mecánica de empezar chico y escalar.

### La tensión central (resolvéla y atacá ambos lados)

Cuando agregás sobre confirmación, **pagás MÁS caro** (el precio subió tras el milestone). ¿Eso sigue siendo
disciplinado?
- **(a) Add-on por CONFIRMACIÓN DE EVIDENCIA** (milestone citado: contrato firmado, fase clínica pasada,
  program-of-record, inflexión de margen, RPO creciendo): agregás cuando el hito pre-escrito se cumple, y
  re-corrés la valuación al NUEVO precio — solo agregás si SIGUE underwritable. Disciplina = el hito baja el
  riesgo más de lo que el precio subió.
- **(b) Add-on por CONFIRMACIÓN DE PRECIO** (pyramiding / anti-martingala: agregás a lo que sube porque "el
  mercado confirma la tesis"). Es lo que hacen los trend-followers. Riesgo: comprar momentum/hype.

### Preguntas (respondé TODAS, con precisión de implementación)

1. **¿(a), (b) o híbrido?** ¿La escalera se dispara por evidencia, por precio, o por ambos (hito cumplido Y
   sigue underwritable al nuevo precio)? Dame la regla exacta.
2. **Triggers pre-registrados:** ¿cómo se escribe un tramo ANTES para que sea falsable y no se mueva el arco?
   (ej. "add-on si RPO > $X citado en el próximo 10-Q, antes de fecha F, Y el estado de valuación sigue ≤ STRETCH
   al precio de ese día"). ¿Qué hace un trigger válido vs uno tramposo?
3. **Tamaño de cada tramo:** ¿fracciones fijas del techo (ej. probe 25% → 50% → 100% del cap)? ¿proporcional a
   cuánto bajó el riesgo? ¿cuántos tramos máximo? ¿la posición nace en el probe y sube al techo, o hay otra base?
4. **Re-underwriting al agregar:** cuando el precio subió, ¿re-corrés el reverse-DCF/probabilidad al nuevo precio
   y solo agregás si el estado sigue admisible? ¿O el hito "compra" un tramo aunque la valuación se estire?
5. **Regla de TRIM (doc 29 la nombró):** una especulativa que hace +200% redefine la cartera sola. ¿Cuándo y
   cuánto recortás? ¿Por peso (>X% de cartera → trim), por valuación (pasó a NON_UNDERWRITABLE → trim), por ambos?
   ¿Cómo evitás cortar un ganador demasiado pronto (el pecado #1 en power-law)?
6. **Interacción con la banda de sizing:** mi sizing hoy da un TECHO (min de caps). Si la posición nace chica y
   escala, ¿el techo es el tope de la escalera? ¿la base inicial (probe) cómo se fija?
7. **Anti-hype / anti-auto-engaño:** ¿dónde re-entra el hype con una escalera (ej. relajar el trigger para
   "seguir agregando al ganador")? ¿Qué guarda determinista lo frena? ¿El trigger pre-registrado + hash?
8. **Pre-revenue binaria vs comercial:** ¿la escalera es distinta para una binaria (add-on al pasar el hito
   único) vs una comercial (add-on sobre inflexión de márgenes/RPO)? ¿Cómo?

### Formato
- Veredicto (a/b/híbrido) en 3 líneas.
- La mecánica implementable: trigger → re-underwrite → tamaño de tramo → trim, como pseudo-reglas deterministas.
- El modo de falla más peligroso + su guarda.
- Qué NO haría (sobre-ingeniería / hype disfrazado).

No asumas que tengo razón. Si la escalera de add-on es la abstracción equivocada para esta clase de activo,
decilo y dá la correcta.
