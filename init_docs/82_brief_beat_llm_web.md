# Doc 82 — Brief de triangulación: que nuestro método le gane a un LLM+web

> **Para IAs externas.** Autocontenido: no necesitás el código. Objetivo: converger sobre **4 cambios
> estructurales** del sistema de valuación/decisión de BORJA. Devolvé, por cada punto: (a) si estás de
> acuerdo con la dirección, (b) la forma concreta que recomendás, (c) qué romperías si lo implementamos mal.
> Sucesor del doc 79→80. Fecha: 2026-11-16.

## 0. Qué es BORJA (contexto mínimo)

Sistema **advisory** (asesora; el humano ejecuta) para small/mid caps de "industrias del futuro" (AI infra,
nuclear/energía, defensa, minerales, espacio, robótica, biotech, fotónica, semis). Tesis **power-law**:
concentrarse donde la disciplina genera más diferencial.

Arquitectura: **el determinismo informa y limita; un comité de agentes LLM decide.**
- **Datos deterministas** (XBRL de EDGAR point-in-time + calculadoras citadas) arman un *data pack* por nombre.
- **Comité LLM**: Macro → Triage → **Analista (Opus+web)** arma el dossier → **Bear** lo ataca → **Verificador**
  contrasta claims vs XBRL → **PM** sizea bajo el IPS (límites del operador) → **Auditor** cuestiona la decisión.
- **Ficha viva** (doc 80): cada nombre tiene una ficha con **dos relojes**. El LENTO (tesis, escenarios,
  falsadores) lo escribe el comité citando hechos nuevos. El RÁPIDO (precio → zonas de compra/venta) lo computa
  el código todos los días, gratis.

### El puente (equity bridge) — la fórmula que está en discusión
Cada nombre tiene 3 escenarios (bear/base/bull), cada uno con una **métrica terminal** (p.ej. EBITDA o ventas
a 4-6 años), un **múltiplo de salida**, y una **probabilidad**. El valor por acción de cada escenario:

```
V_i = (métrica_terminal_i × múltiplo_i − deuda_neta) / (acciones × (1 + dilución_total))
E[V] = Σ prob_i · V_i
r(P) = (E[V] / P)^(1/T) − 1          # retorno anual implícito al precio P
```

Con `r(P)` y un hurdle por clase se derivan las zonas (COMPRA/MANTENER/RECORTE/SALIDA). **La dilución es un eje
propio**: un único `dilución_total` (fracción) que diluye las acciones. El `deuda_neta` es **un solo número: el
de hoy**.

## 1. Por qué este brief: validamos contra un LLM+web y perdimos en profundidad

Exportamos 4 nombres (VST, MP, IESC, OKLO) y los hicimos analizar por un **LLM independiente con acceso web**
(mismo tipo que nuestro Analista). Resultado:

- **Coincidió con nuestro ranking y zona en 3 de 4.** El output ordinal aguanta. Bien.
- **Pero cazó cosas que nuestro comité entero no**, y todas cambian magnitudes:
  - **IESC**: encontró una adquisición de $691M (DBM Global, $525M de deuda nueva, +$1.500M de revenue) vía un
    8-K del 6-oct. Nuestro dossier decía "sin deuda / sin filings desde julio". **[YA RESUELTO deterministamente:
    ahora un chequeo detecta 8-K materiales posteriores al último XBRL y marca el balance como no confiable.]**
  - **OKLO**: el puente suma la caja de hoy ($3,13B) como equity terminal **y** las plantas construidas — pero esa
    caja ES el presupuesto de obra, se consume. Doble conteo.
  - **MP**: usamos 196M de acciones; las reales son ~235-240M (converts in-the-money + preferida del DoD). El bear
    quedó demasiado benigno porque no modelamos converts/preferidas como senior al común.
  - **VST**: dos errores que se cancelan; entre ellos, deuda mal cargada.

**Meta-hallazgo:** nuestra maquinaria (determinismo + verificación + varios agentes) **todavía no produce un
edge** sobre un solo LLM+web en profundidad. Y hay una razón estructural: **todos nuestros agentes consumen el
mismo data pack** → sus errores están correlacionados; ninguno re-verifica la fuente primaria en vivo. El LLM
externo sí salió a buscar.

El objetivo de este brief: cerrar esa brecha. 4 cambios.

---

## 2. Punto #1 — Balance terminal congelado (prioridad máxima)

**El problema (verificado en nuestro propio código):** el puente resta `deuda_neta` **de hoy** en el año
terminal de todos los escenarios. Pero a 4-6 años:
- una empresa que **genera caja** (VST, IESC) tendría mucha menos deuda neta (o caja neta) → su equity terminal
  está **subestimado**.
- una que **quema** (OKLO, MP) tendría más deuda / más dilución → su equity terminal está **sobrestimado**.

BORJA las trata igual → **castiga sistemáticamente a las generadoras y premia a las quemadoras**, lo opuesto a
lo que querés en una cartera de calidad.

**La tensión / el riesgo:** la deuda neta terminal ≈ deuda hoy − FCF acumulado (+ caja levantada por dilución).
Pero parte de la quema ya la capturamos en `(1 + dilución_total)`. **Hay riesgo de doble conteo** entre el eje
dilución y la evolución del balance. El caso OKLO es agudo: la caja de hoy es el capex que se consume; contarla
como equity terminal es el error, pero el burn está parcialmente financiado por esa misma caja y parcialmente
por dilución.

**Nuestra propuesta tentativa (criticar):** evolucionar la deuda neta al año terminal por escenario:
`deuda_neta_terminal_i = deuda_neta_hoy − FCF_acumulado_i`, donde FCF_acumulado sale de la trayectoria implícita
del escenario; y **coordinar con el eje dilución** para no doble-contar (la dilución capta la caja levantada por
emisión; la evolución de deuda capta la generación/consumo operativo). Para pre-revenue que queman y financian el
capex con caja + emisión, el FCF_acumulado es negativo y la caja de hoy **no** es equity terminal.

**Preguntas para ustedes:**
1. ¿Evolucionar la deuda neta por FCF acumulado es correcto, o preferís modelar el balance terminal de otra forma
   (p.ej. valor presente del FCF intermedio aparte del terminal)?
2. ¿Cómo evitar el doble conteo con el eje dilución de forma limpia y auditable?
3. ¿Qué haríamos cuando no tenemos trayectoria de FCF confiable (gran parte del universo es pre-revenue)?

---

## 3. Punto #2 — Cascada de capital (converts / preferidas en el bear)

**El problema:** la dilución es un **haircut plano** (`dilución_total`), no una **cascada** que se activa cuando
el precio cae bajo la conversión. En MP: $862,8M de converts 2030 a ~$21,74 (~39,7M acciones in-the-money) + una
preferida del DoD (13,3M acciones a $30,03, preferencia de liquidación $435,6M). Cuando la acción cae, esos
instrumentos quedan **senior al común**. Por eso nuestros **bears salen demasiado benignos** (el revisor externo
pone bears de −85/−90%; nosotros −50/−73%).

**Nuestra propuesta tentativa:** en el escenario bear, tratar converts/preferidas como **deuda senior** (suman a
`deuda_neta` del bear en vez de diluir), y en bull/base como **dilución** (convierten). Es decir, el instrumento
cambia de naturaleza según el escenario (deuda si out-of-the-money, equity si in-the-money).

**Preguntas:** ¿Es correcta esta dependencia del instrumento con el escenario? ¿Cómo lo mantenemos auditable sin
una cascada de capital completa (que sería mucha ingeniería)? ¿Qué datos mínimos necesitamos del filing?

---

## 4. Punto #3 — Correlación / factor común

**El problema:** las 4 son **una sola apuesta** (capex de IA + política industrial de EE.UU.), como mostró el
co-movimiento del 4-5 de noviembre (elecciones). El IPS capea por **sector** y por **cuello**, pero estas 4
cruzan sectores (energía/materiales/nuclear/infra) y comparten un **driver común** que ningún cap ve. **La
concentración real de la cartera está subestimada.**

**Nuestra propuesta tentativa:** un **tag de driver/factor compartido** por nombre (p.ej. "AI-datacenter-capex",
"US-industrial-policy", "tasas") + un **cap por factor** en el IPS (análogo al cap por sector), para que la suma
de exposición a un mismo driver no supere un tope.

**Preguntas:** ¿Un tag discreto + cap es suficiente, o hace falta algo más cuantitativo (betas/correlaciones)?
¿Cómo asignamos el tag sin sobre-ingeniería (lo pone el Analista? una lista curada?)? ¿Qué tope es razonable?

---

## 5. Punto #4 — Auditor independiente (acceso a fuente primaria)

**El contexto:** nuestro **Auditor** hoy cuestiona la decisión del PM leyendo lo que el comité ya armó — sobre el
**mismo data pack**. No sale a EDGAR/web por su cuenta. Por eso no caza un agujero de datos (como el 8-K de IESC):
audita sobre inputs ya incompletos. El LLM externo funcionó justamente porque **re-investigó desde cero, con
inputs no correlacionados**.

**Nuestra propuesta tentativa:** darle al Auditor **mandato + herramientas de fuente primaria**, pero **acotado y
disparado**, no navegador libre siempre-encendido (sería un segundo Analista y volaría el presupuesto):
- **Scope:** re-verifica **a ciegas solo los 2-3 hechos que cargan la tesis** (deuda neta, acciones, eventos
  materiales recientes, el contrato clave) — no re-hace el dossier.
- **Trigger:** corre el pase independiente **cuando el PM va a comprometer capital** (ahí vale el costo) y/o
  **cuando una guarda determinista marcó conflicto**.

**Preguntas:** ¿Es la forma correcta de meter "verificación independiente no correlacionada" sin duplicar al
Analista? ¿El pase independiente debería ser un rol nuevo o es correcto cargárselo al Auditor? ¿Hay un diseño
mejor para romper la correlación de errores entre agentes (p.ej. que el Verificador sea el independiente)?

---

## 6. Lo que NO está en discusión (ya resuelto / fuera de alcance)
- **Frescura del balance (IESC/DBM):** ya hay un chequeo determinista que detecta 8-K 2.01/2.03/1.01 posteriores
  al último XBRL y marca el nombre como no comprable hasta reconciliar. **No re-triangular.**
- **Zonas, hurdles, piso por clase, paciencia, estacionamiento:** cerrados en doc 80. No re-abrir.
- **Quién decide:** el PM-LLM decide; el determinismo informa y limita. No re-abrir.

## 7. Qué devolver
Por cada punto (#1–#4): acuerdo/desacuerdo con la dirección · la forma concreta recomendada · el modo de falla si
lo implementamos mal · datos mínimos que requiere. Y una lectura transversal: **¿cuál de los 4 cierra más brecha
contra un LLM+web?** Priorizá.
