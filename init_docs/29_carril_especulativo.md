# 29 — Carril especulativo (opcionalidad en la selección)

> Cómo la opcionalidad influye en la SELECCIÓN sin contaminar el número duro ni el sizing.
> Producto de la 3ª triangulación (IA 1 agresiva + IA 2 adversarial, convergieron en la estructura;
> IA 2 corrigió el mecanismo). Diseño **cerrado**. Complementa docs 27/28. Regla rectora:
> **la evidencia contratada construye el núcleo; la opcionalidad puede construir hasta ~1/4 de la
> cartera, pero nunca puede disfrazarse de evidencia contratada ni escapar de sus límites.**

## 0. El insight que gobierna el diseño

Con el sizing, el número duro y la valuación ya determinizados, **el ranking ES la asignación** —
es la única palanca viva. Por eso el juicio especulativo NO entra como un escalar en el ranking:
- **La probabilidad de un LLM es un proxy de momentum narrativo, no una probabilidad.** Su "P" sale
  del mismo corpus que leyó el mercado (PRs, notas de sector); en small caps calientes, densidad de
  cobertura ≈ crowding retail. Medir eso es medir hype — lo que la arquitectura existe para excluir.
- Un escalar además **colapsa** la estructura O0→O5, que ya es más rica y falsable que un número.

Entonces se usa el **mismo patrón que el resto**: el LLM extrae **hechos citados**; una **tabla
versionada** produce el orden. El LLM nunca emite un número de decisión.

## 1. Dos carriles a la misma cartera (presupuesto propio)

Cartera de hasta ~8 posiciones:
- **Hasta 6 por evidencia dura** (el ranking operable de docs 27/28).
- **Hasta 2 por opcionalidad**, con **presupuesto propio** → la especulación **nunca desplaza** a un
  nombre contratado del ranking principal. Si no hay opcionalidades que pasen el gate, esos lugares
  vuelven al carril duro. Una empresa que ya clasifica por evidencia dura **no** consume plaza
  opcional (aunque además tenga opcionalidad).

Así la especulación **cambia materialmente la selección** (un nombre que por evidencia dura quedaría
12º puede entrar por opcionalidad), pero **por una razón explícita y separada**, no fingiendo que es
"solo 18% peor".

## 2. Gate de entrada al carril (no cualquier historia entra)

Todas obligatorias:
- **Supervivencia:** runway/financiamiento hasta el hito, o la dilución ya está capturada en fragilidad.
- **Evidencia externa real:** design-win, piloto pago, proceso de calificación, RFP concreto, cliente
  identificado, permiso en trámite. **NO** alcanza TAM, guidance, un deck, ni "hasta $X".
- **Hito cercano:** resoluble en ~12–18 meses.
- **Materialidad relativa al revenue:** si ocurre, cambia la ESCALA de la empresa. Se mide por la
  **definición del hito relativa a los ingresos actuales** (ej. "convierte el programa X en contratos
  ≥30% del revenue actual"), **NO** por el ceiling anunciado ($4B).
- **Falsabilidad escrita:** qué tiene que pasar, antes de qué fecha, verificable en qué documento.

## 3. Orden dentro del carril (rúbrica → tabla → ordinal; NO probabilidad)

Para cada hito, el PM-LLM responde una **rúbrica fija, cada respuesta con cita**:
1. ¿La contraparte está identificada y **financiada**?
2. ¿El dinero está **apropiado / autorizado / ninguno**?
3. ¿Hay **transacción precedente** con esa misma contraparte?
4. ¿Qué **documento específico y en qué fecha** lo falsa?

Una **tabla versionada** convierte esas respuestas en un **grado ordinal de opcionalidad**. Desempate
intra-grado por **densidad de falsabilidad**: cantidad de hitos fechados que resuelven en los
**próximos 2–4 trimestres** y son verificables en un documento específico (adjudicación DoD, lista
DOE, línea del 10-Q, 10-K del cliente). Premia **aprender rápido y barato si la historia era cierta**;
es casi todo conteo, no criterio. **El estudio del PM-LLM se conserva** — produce las respuestas
citadas de la rúbrica; lo que se descarta es el escalar sin calibrar.

## 4. Sizing y contención (donde estaban las fugas)

"El sizing no se toca" era demasiado débil: exposición = tamaño × cantidad; el arquetipo es un
multiplicador que la narrativa empuja hacia arriba; la fragilidad tiene juicio adentro. Guardas:
- **Cap por posición:** `option_selected=true` → tamaño = `min(tamaño arquetipo×fragilidad, 8%)`.
- **Cap de cantidad:** máx **2** plazas opcionales; **máx 1 por catalizador / cuello de botella**.
- **Cap AGREGADO a nivel cartera** sobre el peso de nombres con bull operable bajo el umbral de
  evidencia (§5) — el invariante que realmente ata; el cap por posición no controla la cartera.
- **Barrera de información estricta (obligatoria):** el extractor de fragilidad/arquetipo **NO** ve el
  corpus de noticias ni el contexto del PM-LLM. Si no, la especulación entra al tamaño por atrás.
- **Regla de trim post-entrada:** sin recorte, una especulativa que hace +200% redefine la cartera
  sola y la contención es ficción.
- **Fuga humana:** el operador ejecuta a mano y ve el orden. Riesgo #1 de fuga: dimensionar de más
  porque "el sistema lo puso primero". El cap agregado + el de cantidad son la defensa.

## 5. Presupuesto del carril (punto medio: piso fijo + techo ganado)

- **Piso fijo desde el día 1:** **10%** agregado (para que el carril sea real y se pueda actuar ya).
- **Crece +~4%/trimestre** hasta un **techo del 25%**, ganado por el **hit-rate sobre hitos resueltos
  (trailing 8 trimestres)**. Aggressive ahora, se gana el resto.
- Todos estos números son **priors de política versionados** (doc 28 §0): calibrables, con hash;
  cambiarlos bumpea la versión y recorre la cartera.

## 6. El log es un INTERRUPTOR DE APAGADO, no una licencia

El n es chico (30–60 nombres/año, lags 2–8Q → primera lectura útil en años) y la calibración mide lo
barato cuando el ranking necesita **discriminación** (lo caro). Pero el log sí sirve para **detectar
fracaso grosero barato**: **pre-registrado** — *si tras 8 hitos resueltos el bucket de grado alto
rinde por debajo del 25%, el carril se SUSPENDE (agregado → 0) hasta revisión.* Confirmar éxito es
caro; detectar que es groseramente malo es barato. El log apaga, no habilita.

## 7. Graduación

Cuando una opción convierte a **contrato admitido por el compiler** (llega a O4/O5, doc 28 §5), **deja
el carril especulativo** y compite normalmente en el libro duro. La opcionalidad es un estado
transitorio, no una etiqueta permanente.

## 8. Mayor riesgo de auto-engaño

No es que el LLM alucine un número (visible, auditable). Es la frase **"solo afecta al ranking"** —
en un sistema todo-determinista, el ranking es la asignación. Y es el log que **da la licencia hoy y
entrega la auditoría en cinco años**: entre esos momentos operarías con la confianza de un sistema
medido y los datos de uno que no lo está. Por eso el carril nace **contenido** (caps agregados) y el
log nace como **apagado**, no como credencial.

## 9. Estado

Diseño cerrado. **Construcción posterior** al núcleo operable (docs 27/28): este carril se apoya en el
option ledger (candidatos), la extracción de la rúbrica y el compiler admitiendo contratos. Prioridad
inmediata sigue siendo el núcleo operable (templates por arquetipo). El carril entra cuando el ledger
y la rúbrica existan, y **arranca en shadow** (log de apagado activo, exposición al piso).
