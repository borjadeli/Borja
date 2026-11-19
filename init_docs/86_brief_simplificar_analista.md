# 86 — Brief para triangular: ¿simplificar el pipeline de análisis? (2026-11-19)

> **Qué es esto:** un brief para que una IA externa (Opus+web) critique UNA decisión de diseño acotada.
> **NO re-abrir** lo ya triangulado (doc 49, doc 82). Foco de la crítica: §4 pregunta 1 (plegar el Bear + aflojar
> el schema). El resto está casi cerrado por evidencia.

## 1. La pregunta
BORJA analiza cada empresa con un **comité**: `data_pack` (XBRL point-in-time + calculadoras) → **Analista**
(Opus+web, agéntico, emite un dossier estructurado) → **Bear** (Sonnet, ataca) → **Verificador** (Sonnet,
contrasta claims vs XBRL + clasifica fuentes). El operador preguntó: *¿no es mejor correr un Opus+web que cree la
ficha y listo, en lugar del comité que "a veces se manda cagadas"?* Lo medimos antes de decidir.

## 2. Lo YA zanjado (no re-abrir)
- **doc 49 (ablation):** el valor es **Opus investigando agénticamente**; los atajos baratos (gather→judge)
  colapsan. → el análisis lo tiene que hacer un Opus+web de verdad.
- **doc 82 (doble validación):** el **comité NO le gana en profundidad a un solo Opus+web**. → el andamiaje
  no compra mejor análisis.

## 3. La evidencia nueva — A/B Opus+web CRUDO vs nuestro XBRL (n=5, 2026-11-19)
Le pedí a un Opus+web crudo los números clave de 5 nombres y los comparé contra nuestro XBRL (ground truth).

| Nombre | costo/web | resultado |
|---|---|---|
| CIFR | $1.64 / 23 | 4/5 exacto; deuda +2.5% (Opus más fino); acciones -9% (mi prompt pedía mal: promedio pond.) |
| OKLO | $0.78 / 12 | acciones/rev/opex exacto; caja +61% = **definicional** (Opus suma inversiones) |
| MP | $1.48 / 15 | deuda/acc/rev/opex exacto; caja "414%" = **error MÍO** (comparé vs tag `cash` angosto; nuestro `liquidez`=cash+STI matchea a Opus al dólar) |
| RXRX | $1.09 / 12 | caja/rev/opex exacto; **deuda: NUESTRO dato viejo** (tag 2022, $723K vs $11.9M real — inmaterial); acciones: Opus **puntó** (no entregó) |
| IESC | $0.79 / 12 | rev/opex exacto; caja/deuda/acciones: Opus **puntó** ("pendiente de verificar") |

**Hallazgos (robustos a n=5):**
1. **Opus NUNCA fabricó un número.** Cuando dudó (IESC, RXRX-acciones) **puntó y lo dijo** — no alucinó.
2. **Clavó el income statement 5/5** (revenue + operativo), exacto.
3. **Pero deja AGUJEROS de cobertura:** puntó cash/deuda/acciones enteros en IESC, acciones en RXRX. Una ficha de
   Opus crudo vendría con huecos; el XBRL siempre los llena.
4. **Las divergencias no son errores de Opus — son definicionales** (caja ± inversiones) o **bugs NUESTROS**
   (deuda stale de RXRX, ya arreglada con un guard de frescura).
5. **Costo: empate.** Opus crudo $0.78–1.64 (12–23 búsquedas) vs comité ~$1.2–1.5. El XBRL no encarece: ABARATA
   (el Analista gasta 2.9 búsquedas porque le damos los números; el crudo gasta 15–23 buscándolos).

## 4. El diseño propuesto (a criticar)
**Se MANTIENE** (la evidencia lo defiende):
- **data_pack XBRL + calculadoras** — por cobertura completa + consistencia entre nombres (comparás cartera) +
  costo. Es lo único "nuestro" que gana claramente.
- **El contrato de salida mínimo** (escenarios, falsador fechado, valuación, invertibilidad) — lo necesita todo
  lo de abajo (zonas, packet, Brier, PM).
- **El Auditor** (downstream, modelo distinto, 2º cheque).
- **El chequeo de números vs XBRL** — pero RE-ENTENDIDO: no es solo seguro anti-alucinación (Opus casi no
  alucina), es **cazador de bugs de NUESTRO propio XBRL** (cazó la deuda stale). Vale.

**Se SACA / COLAPSA:**
- **El Bear como agente separado → se pliega al prompt del Analista** ("armá la tesis bull Y atacála vos").
- **El schema rígido del Analista → se afloja:** Opus razona libre y recién al final emite los campos.

**→ de 3 agentes LLM (Analista+Bear+Verificador) a 1 (Analista v2) + chequeo de números.** Más barato, más
simple, menos superficie de bugs.

### LAS PREGUNTAS A ATACAR (en orden de importancia)
1. **(la que importa) ¿Plegar el Bear al Analista pierde adversarialidad real?** Mismo modelo + mismo contexto =
   ¿razonamiento motivado (no se ataca en serio a sí mismo)? ¿O el Auditor (modelo distinto, downstream) ya lo
   cubre? Es la única capa de seguridad que sacamos — acá puedo estar racionalizando a favor de simplificar.
2. ¿"Razonar libre y emitir schema al final" **de verdad** evita el corsé, o cualquier schema ya condiciona el
   pensamiento?
3. El chequeo de números: ¿puede ser **100% determinista** (diff ficha vs XBRL), o los desvíos definicionales
   (caja ± inversiones) necesitan juicio LLM para resolver "cuál es el número correcto"?
4. Los red flags de supervivencia (going concern / material weakness / restatement): hoy los ve el Verificador.
   ¿Los cubre el event_monitor (que ya los caza por 8-K), o hace falta un Verificador liviano?

## 5. Qué NO estamos preguntando
No "¿Opus+web o determinismo?" (doc 49 lo cerró), ni "¿el comité analiza mejor?" (doc 82 lo cerró: no). Solo:
**dado que el análisis lo hace Opus+web igual, ¿cuánto andamiaje alrededor vale la pena?**
