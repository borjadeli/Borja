# 58 — Auditoría externa del brief de P1 (doc 56) — IA 2

> Devolución de la **IA 2** (2026-10-27) sobre el brief de P1. **Converge fuerte con IA 1 (doc 57).**
> ⚠️ El pegado del operador se cortó en §4 (implementabilidad XBRL); si aparece el resto se agrega.
> No reescribir el brief ni codear hasta cerrar la convergencia (doc 59).

## Dictamen
P1 es la dirección correcta, pero **no aprueba los 6 defaults como están**. Tres problemas que pueden impedir
que opere bien:
1. **Bug temporal en `known_at` (§2.1)** → información futura en cálculos históricos → falsos PASS.
2. **Error de diseño en el verificador (§2.3):** contrastar una cifra con XBRL **no** es corroboración
   independiente de lo que afirma la empresa.
3. **Bloqueo estructural del universo pre-revenue:** si "sin XBRL → REVIEW" siempre, las calculadoras no
   resuelven el problema del smoke (nunca compra).
No cambia paradigma/método/comité/quién decide — son correcciones de contratos, evidencia y ejecución.

## Las 6 decisiones
- **D1 · Umbral de PASS — MODIFICAR.** Correcto exigir todos los soportes centrales; mal definir el universo
  como "todos los `tesis_claims_soporte`". Una inferencia económica ("se beneficia del cuello de interconexión")
  no es contrastable con XBRL ni tiene por qué serlo. **Propuesta:** congelar el inventario de centrales ANTES
  de verificar; separar **hechos observables** de **inferencias/proyecciones**; exigir verificación de todos los
  **hechos críticos** necesarios para la tesis; tratar inferencias como razonamiento sobre esos hechos.
  `critical_claims.length > 0`; ningún central contradicho oculto en un secundario. (No cambia la unanimidad de
  evidencia crítica; cambia **qué entra** en ese conjunto.)
- **D2 · Orden de calculadoras — MODIFICAR.** No por cantidad de inputs: por **cobertura efectiva del universo +
  capacidad de desbloquear**. Secuencia: **P1-A** runway/dilución/capital_raise_risk/financiación del critical
  path (supervivencia+capital) · **P1-B** reverse burden de GP (exigencia implícita en el precio) · **P1-C**
  owner-FCF (empresas maduras) · **P1-D** t_star/g_D/burden (más supuestos). Nota: owner-FCF **no** es de pocos
  inputs confiables (maintenance capex, SBC requieren juicio).
- **D3 · Pre-revenue — MANTENER con condiciones.** Método correcto. El contrato debe distinguir
  **`cash_runway`** (tiempo financiable con liquidez) · **`funding_gap`** (capital adicional al hito) ·
  **`funded_critical_path`** (si lo disponible o jurídicamente comprometido cubre el camino al hito). **NO**
  contar como asegurada: shelf registration, capacidad de ATM, promesas de equity, ronda futura. Y:
  sobrevivir al próximo hito **no** demuestra demanda económica — la evidencia comercial se verifica aparte.
- **D4 · Batch Sonnet — MANTENER** con salida **estructurada por claim** (`claim_id, evidence_id, entailment,
  limitations, contradiction_found`); un batch no recibe un único PASS global. Primero `verificar_cita` +
  controles numéricos deterministas; Sonnet solo para centrales que requieren interpretación semántica. Caché
  por `hash(claim, evidencia, versión del verificador, modelo)`.
- **D5 · Freshness — MODIFICAR.** Evento + TTL **diferenciado por métrica** (precio/shares/balance/contrato/
  catalizador tienen dinámicas distintas). Un hecho no deja de haber sido conocido porque venció el TTL; lo que
  caduca es su **utilidad para una decisión actual**. Separar `known_at / observed_at / extracted_at /
  valid_until`. Al cambiar un input, **invalidar todos los cálculos dependientes** (un 10-Q nuevo fuerza
  recomputar runway y dilución aunque estén dentro del TTL).
- **D6 · XBRL — RECHAZAR parte del default.** Medir cobertura: sí. "Sin XBRL = REVIEW automático": **no**. Una
  empresa puede divulgar un contrato relevante en un exhibit de 8-K o un hecho operativo en un documento
  regulatorio sin cifra en companyfacts. Exigir XBRL ahí confunde **disponibilidad de un formato contable con
  verificación económica**. La alternativa son **rutas de validación según la naturaleza del claim** (es el
  cambio más importante de P1).

## §2.1 — Contrato data-pack↔calculadoras (BLOQUEANTE)
- **`known_at = <hecho más viejo>` está MAL → `known_at = max(input.known_at)`** + `assert all(input.known_at
  <= as_of)`. El mínimo produce look-ahead en backtests/snapshots. (Coincide con IA 1.)
- **`inputs=["revenue_ttm",...]` es insuficiente** (los nombres no identifican qué dato se usó: revenue FY2025
  ≠ revenue TTM a sep-2026; diluidas promedio ≠ en circulación a una fecha). Cada input debe atar:
  **id inmutable del hecho + versión de fuente, valor/unidad/moneda, período económico, `known_at` + accession,
  estado de validación.** DataPoint derivado: `metric, value, kind=DERIVED, formula_id, input_refs=[...@filing],
  known_at=max(inputs), computed_as_of, validation="COMPUTED", source_lineage`. **COMPUTED** = la operación
  corrió bien, **no** que ya cumple PASS. Distinguir internamente **MISSING / STALE / CONFLICTED /
  NOT_APPLICABLE** (no son el mismo problema ni la misma respuesta del verificador).

## §2.3 — Error conceptual del verificador (el riesgo más grande de falso PASS)
`verificar_cita + contrastar_xbrl + verificar_entailment` pueden validar **aspectos distintos de una ÚNICA
declaración de la empresa**. Ej.: backlog de US$400M en el 10-K → cita OK + XBRL OK + entailment OK **prueba
que la empresa lo informó y que BORJA lo extrajo bien, NO que sean US$400M de ingresos futuros comprometidos.**
**XBRL no es fuente independiente del filing: es otra representación de lo reportado por el emisor.**
**Corrección — dos dimensiones:** (1) **validación técnica** (cita/número/período/fórmula/entailment) y
(2) **suficiencia probatoria** (¿el documento demuestra el *hecho económico* que exige el claim?). PASS solo si
las dos satisfacen la política del tipo de claim. Implementar en `verificador.py`, sin agregar agente.
Ejemplos de política: "US$200M de caja" → financial statement/XBRL contrastado · "creció 35% orgánico" →
revenue comparable + conciliación del componente inorgánico · "contrato de compra US$500M" → contrato
vinculante con términos verificables · "acuerdo por *hasta* US$500M" → **no** demuestra compras comprometidas ·
"generará US$500M en 2028" → guidance/proyección, no hecho realizado. El verificador también debe leer
**negaciones/contingencias/lenguaje contractual** alrededor de la cita (un "agreement for $500M" cancelable).
**Independencia ficticia:** 3 URLs que reproducen el mismo comunicado = 1 fuente → agregar `root_source_id` +
`issuer_id` a la procedencia. **Regla:** una cita verificada demuestra lo que dice la fuente; no convierte una
expectativa en hecho ni una relación comercial en obligación económica.

## §4 — Implementabilidad XBRL y el 70% pre-revenue
La doc oficial de la SEC confirma el techo: **companyfacts** agrega conceptos de taxonomías **no
personalizadas** + hechos de la entidad completa → deja afuera buena parte de los **extension tags** y los
**datos dimensionales**. Los datasets **Financial Statement and Notes** sí traen tags custom + dimensiones +
texto etiquetado → sirven de **fallback** (más complejidad, interpretación cuidadosa).
**Estimación cualitativa de cobertura (juicios de viabilidad, NO % observados — no es riguroso afirmar 60%
sin correr el ETL sobre muestra real):** caja/resultados consolidados ALTA · deuda/cash flow MEDIA-ALTA ·
dilución/obligaciones futuras PARCIAL · guidance/márgenes futuros BAJA · contratos comerciales MUY BAJA ·
design-in/validación comercial MUY BAJA · hitos regulatorios/tecnológicos MUY BAJA. **Para pre-revenue:** hay
datos para caja/runway, pero **casi ninguna afirmación de adopción comercial está en companyfacts.**
**Tres rutas de validación (sin agrandar P1):** **A — Financiera estructurada** (XBRL + períodos + unidades +
fórmulas: revenue/cash/deuda/CF/ratios) · **B — Documental verificable** (filing/notas/exhibits/contrato/
regulatorio; el verificador comprueba la **naturaleza económica**, no solo la existencia textual) · **C —
Declaración no corroborada** (guidance/comercial/comunicado sin evidencia suficiente → **REVIEW si es central**).
**La ruta B es imprescindible** para que un pre-revenue llegue a PASS sin inventar un dato XBRL. Caveats: FPI
20-F/6-K con periodicidad/forma distinta (Inline XBRL no uniforme); empresas sin reporting SEC comparable →
otra fuente o **explícitamente fuera** de la cobertura automática de este P1. EDGAR: 10 req/s + User-Agent,
manejable con caché + incremental (no es el cuello).

## §5 — Pruebas de aceptación (batería adversarial, antes de conectar a producción)
| Caso | Resultado obligatorio |
|---|---|
| Dato publicado después del `as_of` | nunca entra en un cálculo histórico |
| Revenue trimestral confundido con YTD | error detectado; no usar el número |
| Guidance futura idéntica a un número citado | validar que existe la proyección, no que se cumplió |
| Contrato vinculante en exhibit sin XBRL | **puede** ser evidencia elegible para PASS |
| "Up to $1B" sin obligación de compra | no acredita US$1B de demanda comprometida |
| Dilución nueva en 8-K | recalcular métricas dependientes |
| Filing corregido después | preservar el dato conocido en el snapshot histórico |
| Todos los claims citan el mismo press release | no contar corroboración independiente inexistente |

**Medición previa al rollout:** piloto de ~20 empresas (≥12 pre-revenue), cobertura **por claim Y por
arquetipo**: % de centrales con evidencia suficiente · % verificado por XBRL/documentos/otras · % de REVIEW
por límite del extractor vs debilidad de tesis · **falsos PASS/REVIEW vs clasificación humana de referencia**.
Exigir **cero falsos PASS críticos** en la batería adversarial.

## §6 — Recomendación final de implementación (orden)
1. `known_at = max(inputs)` + consistencia temporal — **CRÍTICA**
2. Lineage: unidades, períodos, versiones de inputs — **CRÍTICA**
3. Separar extracción correcta de **suficiencia probatoria** — **CRÍTICA**
4. Validación **documental** sin XBRL obligatorio (ruta B) — **CRÍTICA**
5. Priorizar calculadoras relevantes para pre-revenue — **ALTA**
6. Cache + batch + actualización incremental — **MEDIA**
7. Medir cobertura efectiva por arquetipo antes de ampliar el rollout — **ALTA**

**Conclusión:** el mayor problema no es Sonnet, la lista de calculadoras ni el costo: es que el brief todavía
**equipara dato trazable, dato bien calculado y evidencia económicamente suficiente.** Aprobación condicional
a 4 correcciones críticas: **temporalidad, lineage, suficiencia probatoria y alternativa documental a XBRL.**

> **Nota de alcance:** IA 2 auditó el brief y sus contratos; **no** inspeccionó el código real → sus hallazgos
> son defectos de diseño/riesgos, no bugs confirmados por ejecución (a diferencia de IA 1, que sí leyó el código).
