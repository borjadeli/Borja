# 49 — Ablation del PM + conclusión: el determinista es TRIAGE, no un segundo analista

> Estado: CERRADA (2026-09-21). Origen: revisión punto 1 (método). Disparador: el PM en Opus+web costó
> ~$1.40/nombre y surgió la duda de si el input determinista suma o si el LLM solo lo hace mejor/más barato.
> Método: ablation medido (no especulación). Relacionado: [[canal-juicio-pm-llm-bloque3]], doc 39 (sándwich).

## El experimento (`ops/ablation_pm.py`, 3 nombres: RBRK/VRNS/NABL)

Baseline real = Opus+web (el PM investiga solo): RBRK PRIORITY_MEDIUM · VRNS PRIORITY_MEDIUM · NABL VETO.

| Config | RBRK | VRNS | NABL | $/nombre |
|---|---|---|---|---|
| **Opus + web** (investiga solo) | PRIORITY_MED | PRIORITY_MED | VETO | ~$1.40 |
| Opus **sin web** (solo nuestros fundamentals) | PASS | PASS | PASS | ~$0.15 |
| Haiku + web | PRIORITY_MED | PASS | PASS | ~$0.08 |
| Haiku sin web | PRIORITY_MED | PASS | PASS | ~$0.02 |
| **gather→judge** (Haiku junta citado → Opus juzga sin web) | PASS | PASS | PASS | ~$0.25 |

## Conclusión (nítida)

**El valor NO es "tener hechos web" — es que Opus investigue AGÉNTICAMENTE** (formula la búsqueda, lee, sigue el
hilo, razona *mientras* busca). Todos los atajos colapsan a PASS:
- Determinista solo (sin web) → PASS.
- Facts web PASIVOS (gather→judge, aun con 12-15 hechos citados de Haiku) → PASS.
- Modelo chico + web (Haiku) → acierta lo fácil (RBRK) pero se pierde lo sutil (VRNS artefacto de g_D, NABL
  material weakness).

**No se puede decodificar la búsqueda del razonamiento: el razonamiento-durante-la-búsqueda ES el producto.**
El costo (~$1.40) es intrínseco al mecanismo; no hay atajo de pipeline ni de modelo.

## Qué implica para la arquitectura (DECISIÓN)

Si no se abarata el *mecanismo*, el costo se controla en **dónde y cuándo se gasta**. El determinista deja de
ser "un segundo analista redundante" y se gana el lugar como **TRIAGE + LÍMITES**:

1. **Límites (gratis, sin LLM):** cap = min(arquetipo, tier, valuación), veto de supervivencia, banda [piso,techo],
   cluster/sector caps. El ancla anti-hype. Se queda sí o sí.
2. **Triage:** decide qué POCOS nombres merecen el deep-dive caro de Opus+web. El resto los resuelve el
   determinista solo (veto→0, carril→base-rate, COVERED-en-piso-sin-upside→despliega el piso), SIN llamar al PM.
   → Opus+web quirúrgico sobre ~3-4 nombres/semana, no 12 → de ~$17/sem a ~$5, sin perder el edge.

**Respuesta a "¿el determinismo suma?": SÍ, como límites + triage; NO como análisis (ahí sí duplica al LLM).**

## Sub-decisión ABIERTA (a cerrar antes de codear el rearme)

VRNS destapó un borde: su cap salió bajo porque usó `g_D=2.9%`, que el PM identificó como **artefacto contable**
(fin del on-prem; recurrente real ~20-25%). O sea el *input del cap* estaba mal → el PM quedó boxeado (aun
promoviendo, el techo=piso=4% no dejaba subir). ¿El hallazgo del PM debe poder **corregir el cap** (override
acotado, falsador-gated, doc 39) o solo mueve el size dentro del cap dado? → definir en el esquema del rearme.

## Caveats
n=3, un fallback. Gastado ~$8.5/$20 en la validación + ablations. La señal "pasivo ≠ agéntico" es fuerte pero
el n es chico; si aparece contradicción en más nombres, reabrir.
