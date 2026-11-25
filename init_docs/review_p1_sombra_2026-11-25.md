# Review: implementamos su diseño. ¿Qué nos falta o qué está mal?

Trabajaron con nosotros el diagnóstico de la corrida de BORJA del 25-nov y el diseño de la capa de calidad
económica. Implementamos todo. Antes de darle autoridad, queremos su devolución sobre lo construido.

## Qué quedó implementado (todo commiteado, 1034 tests verdes)

**P0 — autoridad (los bugs que encontraron):**
- Verificación = autoridad determinista en el gate (FAIL bloquea; el PM no lo anula).
- Falsador ESTRUCTURADO del dossier = fuente de verdad (no el texto libre del PM; se arregló la inversión de signo).
- 8-K Item 5.02 ya no afirma "salida de CEO/CFO" por el código de ítem.
- Invariante post-trade (señala stubs sub-piso en el estado final).
- Reconciliación interna del market cap (caso GLXY: mc de todas las clases vs shares de clase A) → BLOQUEA valuación.

**P2 — medición del edge:** contrafactual de ROTACIÓN (A vendida vs B comprada a 30/90/180/365d).

**P1 — calidad económica, EN MODO SOMBRA (computa, NO aplica — como pidieron):** 6 módulos deterministas, test-driven:
1. `tiers.py` — 4 tiers (OPTIONALITY 1.5-2.5 · CORE 5-10 · HIGH_CONVICTION >10-15 · EXCEPTIONAL >15-20; sin 3-5).
2. `arquetipo.py` — clasificador (precedencia infra→pre_revenue→ciclica→compounder; datos insuf.→UNCLASSIFIED).
3. `banda.py` — banda por arquetipo (COMPRA_FUERTE/COMPRA/MANTENER/RECORTE), recalculada cada ciclo, nunca persistida.
4. `permiso_ejecucion.py` — execution_permission (EJECUTAR/DIFERIR/BLOQUEAR), lo calcula el código.
5. `caps_posicion.py` — cap = min(tier, arquetipo, banda, evidencia) + registra qué cap ligó.
6. `comparacion_rotacion.py` — 3 condiciones no compensatorias (evidencia+margen+riesgo); conecta al contrafactual.

**Decisiones resueltas entre sus dos diseños** (sin 3ª IA): quitamos la convicción propia del PM (de IA2) · topes por
arquetipo (IA2: compounder 15·cíclica 10·infra 10·pre-rev 0) · stub = sacar la pieza (IA2) · guardarraíl de curva
forward en cíclicas (IA2) · falsador DURO sobre la métrica del arquetipo (IA2) · opcionalidad **8% agregado** (decisión
del operador, punto medio entre los 6% de uno y 15% del otro) · grilla-vs-rango continuo DIFERIDO (el shadow decide) ·
execution_permission de 3 estados (IA2). Método: SOMBRA primero, después autoridad, después freeze 90 días.

## El test clave: ¿qué habría decidido P1 sobre LA corrida que ustedes criticaron?

Corrimos el kit en sombra sobre los 7 nombres del 25-nov (NO aplica, solo computa). Resultado:

```
EXE   arquetipo=ciclica · banda=RECORTE · cap=0.0% · PERMISO=BLOQUEAR (aumento)
VST   arquetipo=ciclica · verif FAIL · cap=10% · PERMISO=BLOQUEAR (aumento)
IESC  arquetipo=ciclica · venta discrecional con dossier viejo · PERMISO=DIFERIR
CIFR  arquetipo=infra · banda=RECORTE · salida · PERMISO=EJECUTAR
GLXY  arquetipo=infra · cobertura IG~0 · banda=RECORTE · cap=0.0%
WOLF  arquetipo=pre_revenue · cap=0.0% en núcleo (solo opcionalidad)
EME   sin dossier · arquetipo=UNCLASSIFIED · PERMISO=BLOQUEAR (apertura)
```

Coincide con el trato que cada uno de ustedes esperaba: EXE/VST/EME se bloquean, IESC se difiere (no se ejecuta a
ciegas con datos viejos), CIFR sale como independiente, GLXY/WOLF no pueden ser núcleo. La única dependencia del harness
real: extraer del dossier los RANGOS de banda (valor mitad-de-ciclo, cobertura IG) — donde faltan, el kit devuelve
None honestamente en vez de inventar.

## Lo que les pedimos revisar

1. **¿La semántica de los módulos es fiel a su diseño?** Especialmente: la precedencia de arquetipos, la función de
   banda por tipo, el min() no-compensatorio de caps, y los 3 estados de permiso (¿DIFERIR está bien acotado a ventas
   discrecionales?).
2. **¿Los veredictos sobre los 7 nombres son correctos** dado lo que el sistema sabía ese día? ¿Alguno les parece mal?
3. **El harness de sombra** (lo que falta): va a EXTRAER del dossier los insumos (señales de arquetipo + rangos de
   banda) y loguear "qué habría cambiado" por decisión, sin aplicar. ¿Qué invariantes/trampas vigilarían en esa
   extracción? (ej. un rango de banda mal extraído da una banda falsa.)
4. **¿Qué de los 18 tests de aceptación que propuso IA1 todavía NO cubrimos** y es importante antes de darle autoridad?
5. **¿Algo del diseño cambiarían a la luz de verlo computado** sobre la corrida real?

Sean concretos y duros. El objetivo es que esto esté sólido ANTES de darle autoridad y entrar al freeze de 90 días.
