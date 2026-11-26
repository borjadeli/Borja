# 91 — Diseño cerrado: de sistema de INVESTIGACIÓN a sistema de DECISIÓN (2026-11-25)

> Validación externa de una corrida REAL del comité (2026-11-25) con **dos red-teams independientes** (IA1 code-
> level + IA2 diseño). Patrón del doc 82. **Convergencia casi total**, y —clave— coincide con la propia historia
> de BORJA: el riesgo que marca IA2 ("Analista+Bear+Verificador+Auditor no garantizan que los errores se cancelen;
> pueden reforzarse") es literalmente el doc 82 y el motivo por el que ya sacamos el Bear (doc 87).
>
> **Diagnóstico unánime:** BORJA **investiga excelente y decide inconsistente**. El arreglo **NO es más agentes ni
> más complejidad** (las dos IAs + la directiva r10 del operador coinciden): (A) que el determinismo sea
> **autoridad** en el borde de la decisión, (B) subir la **disciplina económica** de la decisión, (C) por fin
> **medir el edge**. **Norte a defender: no derivar a "value cíclico con temática tecnológica".**
>
> Artefactos: `data/corridas/backup_comite_2026-11-25.md` (la corrida), `evaluacion_externa_2026-11-25.md`
> (prompt+backup enviado a las IAs), `evaluacion_hallazgos.md` (acumulador con las 2 críticas + mi verificación
> de código + las convergencias). Memoria: [[validacion-externa-corrida-2026-11-25]].

## 1. Qué reveló la corrida (hechos, no opiniones)
El PM quiso bajar la caja del 91%: propuso aumentar EXE 9%/VST 8% y comprar EME 6%, y vender IESC y CIFR. **Solo
se ejecutaron las ventas.** Los aumentos quedaron bloqueados por violación agregada del IPS (clip=agregada,
`ejecutada=False`), EME no se registró, y la caja SUBIÓ. **El Auditor no objetó nada.** Usando solo los datos que
el propio sistema produjo, las dos IAs —por separado— objetan casi todas las decisiones.

Verificado en código (no es opinión):
- **No existe un gate determinista de verificación/IPS antes de la propuesta ejecutable.** El PM ve el veredicto
  del Verificador (`FAIL`/`REVIEW`) como texto y lo ignoró: afirmó "PASS para EXE/VST/EME" con VST=FAIL, EXE/EME=
  REVIEW, y EME sin dossier.
- **El falsador de la decisión es texto libre** (`falsador_afirmacion`), NO el predicado estructurado del dossier
  (`{métrica,operador,umbral,consecuencia}`). El PM lo reescribió y le **invirtió el signo** (VST/EXE guardaron la
  condición de ÉXITO), y `resolucion.py` sugiere `default="disparado"` por silencio → el escenario bueno se
  registraría como tesis muerta → corrompe Brier/hit-rate.
- **`reglas_salida.py:18`** mapea `"5.02" → "salida de CEO/CFO"` por el código de ítem, sin leer el cuerpo. El 5.02
  de IESC era compensación (PSUs) → falso positivo que el PM usó para justificar el timing.
- **No hay invariante post-trade:** vender A sin comprar B deja la cartera peor (caja ↑) sin que nadie lo vete.

## 2. Convergencias IA1 ∩ IA2 (dos red-teams independientes → alta confianza)
1. Falsador con signo invertido → medición ex-post rota. *(confirmado en código)*
2. Falsadores = el componente más débil; mezclan **falsador / catalizador / condición-de-entrada**; rediseñar.
3. VST: el falsador testea la "opción gratis" (PPA ≥1GW), no la tesis central → contradicción lógica.
4. Reverse-underwriting incompleto **por tipo**: commodity→a la curva · pre-revenue→por acción post-financiamiento
   · developers→EV a completion descontado.
5. Falta la **comparación económica entre oportunidades** / riesgo de portafolio; las zonas no reemplazan la decisión.
6. El **piso 5%** interfiere con la power-law (operar "porque hay stubs <5%" es mala razón).
7. **El Auditor es decorativo** → rediseñar (ve solo el texto del PM; darle el log + checklist determinista).
8. **Estacionamiento en ETFs** → rediseñar (beta al mismo factor / lo más caro; usar T-bills + manga explícita).
9. **El edge NO está demostrado**; hit-rate/Brier no miden alpha → faltan contrafácticos/ablaciones.
10. **P0 — el Verificador debe ser AUTORIDAD determinista fuera del LLM** (IA2 lo marca P0; confirmado: no hay gate).
11. Reemplazar el piso rígido 5% por **tiers** + sin liquidación automática por peso solo.
12. **Contrafactual de cada rotación** (A vendida vs B comprada a 30/90/180/365d) + carteras virtuales bajo el mismo IPS.
13. La **venta de IESC** es la decisión más cuestionable (vendida con números en aceleración y por debajo del EBIT
    que el propio underwriting exige). Las dos eligieron el mismo trade.
14. **Motivated reasoning SISTEMÁTICO** (IA2): estándares asimétricos — IESC "margen de pico" (normaliza agresivo) vs
    VST/EXE (no normaliza). "Compatible con un PM que racionaliza decisiones preexistentes."

## 3. El spec — una sola lista priorizada

### P0 — Autoridad + maquinaria (bugs; se arreglan ya)
- **P0.1 — Gate de ejecución determinista, independiente del PM.** Ninguna apertura/aumento sin: verificación
  válida (nada de `FAIL`/`REVIEW` sin reconciliar), reconciliación financiera e IPS. Guarda la versión exacta de
  evidencia que autorizó la decisión. **Bloqueo que el PM NO puede anular.** *(convergencia #1 + 10; único fix
  técnico que eligió IA2; empezar por acá.)*
- **P0.2 — Falsador estructurado dossier→decisión, en 3 campos** (falsador / catalizador / condición-de-entrada).
  Sin texto libre ni inversión de signo; el ledger evalúa el predicado estructurado. Si el PM lo modifica, diff explícito.
- **P0.3 — Sub-clasificar el 8-K 5.02** (no afirmar "salida de CEO/CFO" por el código de ítem; sin confirmación en
  el cuerpo → "cambio en directorio/management (5.02) — verificar").
- **P0.4 — Invariante post-trade / ejecución atómica.** Ningún estado final que viole el IPS; el plan se ejecuta
  como paquete (todo-o-nada o escalado proporcional), no asimétrico (ventas sí / compras no).
- **P0.5 — Gate de reconciliación de datos/precio.** Bloquear valuación si el precio se movió >X% sin explicar o el
  equity/NCI no reconcilia (GLXY, Doosan). Capa de corporate-actions + 2º proveedor de precio + paso "¿por qué
  cayó >30%?".

### P1 — Calidad de la decisión económica (diseño convergente)
- **P1.1 — Reverse-underwriting por ACCIÓN + por ARQUETIPO.** Cuatro arquetipos con preguntas obligatorias distintas:
  compounder→ROIC incremental+reinversión · cíclica/commodity→FCF normalizado al ciclo (valuar a la curva) ·
  infra contratada→FCFE/DSCR/contraparte/financiación · pre-revenue/turnaround→supervivencia+dilución+valor esperado.
  Incorporar tiempo, costo de capital, financiación, deuda futura y dilución → **valor por acción**, y una
  **superficie de escenarios** (el precio exige una COMBINACIÓN de futuros, no uno).
- **P1.2 — Comparación obligatoria antes de rotar.** Toda sustitución demuestra por qué mejora la distribución de
  retornos de la cartera (el "¿es el mejor destino para el próximo dólar?"). Las zonas COMPRA/RECORTE son info, no
  reemplazo de la decisión.
- **P1.3 — IPS: tiers en vez del piso rígido 5%** (opcionalidad 1-3% · inicial 3-5% · central 5-10% · extraordinaria
  10-15% · excepcional 15-20%; máx 20% y límites por cuello se mantienen) + **eliminar toda liquidación automática
  gatillada solo por el peso**. Separar **caja(T-bills) / ETF estructural (se gana el lugar por tesis+valuación) /
  alpha**. Además: caps por **factor**, no solo por sector.
- **P1.4 — Auditor de 3 capas** (sin agente nuevo): (1) controles DETERMINISTAS que auto-bloquean
  (verificación/elegibilidad/IPS/consistencia precio-deuda-acciones-propuesta-vs-registro) · (2) auditor económico
  LLM adversarial que cita claim + evidencia contradictoria y aplica la MISMA vara a todas · (3) resolución del PM
  registrada (un bloqueo determinista no lo puede anular el PM).
- **P1.5 — Schema mínimo de salida del PM** (estructurado, `null` EXPLÍCITOS; el sistema completa con evidencia o
  reconoce que no la tiene — NO inventa números para cumplir el schema; campo `execution_permission`).

### P2 — Probar el edge (medición)
- **P2.1 — Contrafactual de cada rotación** (A vendida vs B comprada a 30/90/180/365d). Descubre si BORJA es bueno
  encontrando pero malo vendiendo, o si vende ganadores temprano.
- **P2.2 — Carteras virtuales bajo el MISMO IPS/universo/precios/costos** (BORJA / opus-solo+IPS / factorial / sectorial)
  + ablaciones (sacar auditor/verificador una semana → ¿cambia algo?).
- **P2.3 — Experimento de anclaje** (dossiers sin zonas/posiciones/precios/recomendación → ¿cambia el ranking del PM
  cuando aparece COMPRA/RECORTE?).

### Discovery
- **P3.1 — Reemplazar "deep garantizado por contrato"** por **prioridad según impacto esperado en una DECISIÓN**
  ("¿qué investigación tiene la mayor prob. de cambiar una decisión material de cartera?"). El deep-por-contrato
  sesga hacia empresas que publican muchos anuncios.

## 4. Guardarraíles — qué NO hacer (= filosofía r10 / doc 82)
Sin otro agente (Macro ya se sacó) · sin Monte Carlo para todas · sin optimizador matemático de cartera · sin
scoring de decenas de variables · sin probabilidades artificialmente precisas (12% no es mejor que "razonado
10-25%"). **Mejorar la CALIDAD de la decisión, no la cantidad de componentes.**

## 5. El norte (los 3 riesgos estratégicos de IA2)
1. BORJA = excelente detector de RIESGO y mediocre detector de OPORTUNIDAD (descarta ganadores porque siempre
   desconfía de margen/crecimiento/valuación).
2. Confundir "aparentemente barato" con "alta calidad" → **DERIVA a value cíclico con temática tecnológica** (el
   sesgo EXE/VST vs vender IESC). Margen de seguridad ≠ contratos+caja; también es ROIC reinvertible.
3. La sofisticación del proceso da FALSA seguridad (los agentes refuerzan errores, no los cancelan — doc 82).

**La tríada de IA2 (si una de cada):** 1 investigación → reconstruir **IESC–EME–VST** bajo escenarios equivalentes ·
1 fix técnico → **el gate de verificación pre-ejecución (P0.1)** · 1 validación → **medir si cada rotación mejora vs
mantener (P2.1)**. Objetivo final: **no mejores dossiers que Opus-solo, sino mejores DECISIONES a igualdad de
universo/riesgo/restricciones.**

## 6. Orden de construcción
P0.1 primero (gate de ejecución: la convergencia #1 y el único fix técnico que eligió IA2). Luego P0.2–P0.5 (bugs
restantes), P2.1 (contrafactual de rotación: barato y es la validación elegida), y recién después P1 (el trabajo de
diseño económico, que es el grande). **Construir lo mínimo, medir si cambia una decisión del PM, recién después
automatizar del todo** (principio del doc 89/90).

**ESTADO (2026-11-25):** P0.1–P0.5 ✅ · P2.1 ✅ · P1.4 (auditor capa 1) ✅ — commiteados, 999 tests. P1 económico:
**diseño CERRADO** (iteración 2 con IA1, convergente con IA2) — detalle implementable en `data/corridas/
evaluacion_hallazgos.md` (config YAML + 18 tests de aceptación). Falta implementar.

## 7. P1 económico — diseño cerrado (IA1 it.2) + la TABLA DE AUTORIDAD
El corazón del diseño (define el futuro de BORJA):

| El DETERMINISMO tiene autoridad sobre… | El PM tiene autoridad sobre… |
|---|---|
| Integridad de los datos | Interpretación económica |
| Existencia de evidencia suficiente | Atractivo de esa evidencia |
| Consistencia de la valuación | Plausibilidad de los escenarios |
| Límites de riesgo | Convicción |
| Permisos de ejecución | Selección de inversiones |
| Validez del peso objetivo | Asignación dentro del rango permitido |

Piezas (todas sin agentes nuevos, reutilizando la máquina existente): **IPS 4 tiers** (OPTIONALITY 1-3% · CORE 5-10% ·
HIGH_CONVICTION >10-15% · EXCEPTIONAL >15-20%; sin el 3-5% — opcionalidad es categoría económica, no CORE chico; manga
3 plazas/6% agregado; residuales: drift pasivo ALLOW · voluntario inválido REJECT+alternativas · auto_liquidate=false)
· **4 arquetipos** (COMPOUNDER→ROIC incr · CYCLICAL→owner-FCF normalizado/acción · CONTRACTED_INFRA→FCFE estabilizado/
acción · PRE_REVENUE→funding gap; código propone, Analista confirma/override; falta métrica → `underwriting_status:
INCOMPLETE` → no abre/aumenta, SIN threshold universal) · **schema PM = `proposal`(PM) + `authorization`(código)**, el
PM NO reescribe hechos del dossier · **execution_permission 4 estados** (FULL/REDUCE_ONLY/EXIT_ONLY/BLOCKED;
REVIEW→REDUCE_ONLY; FAIL/valuación rota NO impide VENDER) · **atomicidad** (ventas STANDALONE indep · ROTATION vinculada ·
compras = batch sobre cartera proyectada, invalid_batch=REJECT) · **comparación de rotación** (1 pregunta: "¿con el
capital de A en caja, A o B?"; schema estructurado; carga de la prueba en la transacción, default KEEP).

**★ DIRECTIVA DE CONGELAMIENTO (IA1):** una vez implementado esto → **congelar la arquitectura ≥90 días de paper.** No
porque 90d prueben alpha, sino para observar decisiones reales SIN cambiar el método que se evalúa. Corregir bugs sí;
agregar reglas económicas nuevas por cada inversión que salga mal, NO. **El próximo salto de calidad debe venir de la
EVIDENCIA EMPÍRICA, no de seguir diseñando.** Implementar test-driven con los 18 tests de aceptación del acumulador.

## 8. P1 — REWORK post-review (IA1 + IA2 corrieron el código, 2026-11-25)
Las dos IAs reconstruyeron/ejecutaron los 6 módulos. Veredicto: **mantener en sombra, NO dar autoridad.** Defecto
raíz **sistémico: FAIL-OPEN** (un dato faltante/desconocido AGRANDA el permiso/cap en vez de achicarlo). El demo
"funcionó" en parte por inputs puestos a mano (circular) y en parte por bugs. Arquitectura 8/10 · implementación
observable 5.5/10 · harness 3/10. Es un **patch acotado, NO otra ronda de diseño** (ambas IAs). Detalle completo en
`data/corridas/evaluacion_hallazgos.md`.

**★ TABLA DE AUTORIDAD (IA2, "la resolución más importante"):** DURA → validación de datos · verificación · liquidez/
supervivencia/concentración · elegibilidad de tiers · límites de TAMAÑO · atomicidad de rotaciones vinculadas.
INFORMATIVA → arquetipo propuesto. DEFINE MÉTODO → arquetipo confirmado. GATE DE DINERO NUEVO (una vez validada) →
banda. **JUICIO DEL PM → comparación retorno/riesgo + severidad económica relativa (dentro del IPS).**

**★ PRINCIPIO DE ORO (el norte, IA2 §8):** **NO-compensatorio para supervivencia/riesgo de cartera; COMPENSATORIO
para la economía de la inversión.** El error que mata el alpha: meter la racionalidad económica en el CÓDIGO (vetos
no-compensatorios) → se compran solo empresas cuyo éxito ya es evidente. Una empresa NO compensa una violación de
liquidez con upside; SÍ compensa mayor incertidumbre económica con retorno extraordinario + posición MENOR.

**PLAN DE 5 COMMITS (patch, driven por el test fail-closed de IA1 + correcciones de diseño de IA2):**
1. **Autoridad** — eliminar defaults permisivos, enums cerrados, acción desconocida→BLOQUEAR, salida mecánica exige
   evidencia + pasa controles OPERATIVOS (no saltea todo), REVIEW una sola regla canónica (P0/P1/Auditor/harness).
2. **Caps y tiers** — ✅ caps fail-closed (HECHO, commit 1/5); falta: persistir el tier (no inferir del peso), separar
   tenencia de dinero nuevo (`max_target_weight` + `can_add`), remover EXCEPTIONAL como tier de entrada.
3. **Underwriting** — arquetipo ESTRUCTURAL (no depende del precio: infra sin `contratado/EV`), métricas comparables,
   banda infra = FCFE/acción (la cobertura IG informa RIESGO, no la banda), recalcular las variables DEPENDIENTES del
   precio (dos relojes: lento=analista / rápido=motor), señales robustas (revenue key, signo del capex, None≠pre_revenue).
4. **Rotación y atomicidad** — separar VALIDEZ de la comparación (código) del MÉRITO económico (PM); aflojar el veto
   (economía compensatoria); ventas discrecionales por EVENTO-invalidación no por ciclo; atomicidad de pares.
5. **Harness real** — consumir el dossier ESTRUCTURADO del Analista (NO extraer de narrativa con regex/LLM), sin inputs
   inventados, registrar contrafactuales permitidos Y BLOQUEADOS, agregar Doosan, correr los tests integrales.

**Decisiones económicas extra (IA2):** NO forzar que todo falsador sea DURO sobre la métrica exacta (ligado al
mecanismo + observable + regla de resolución; consecuencia dura si mata la tesis, revisión si solo baja el bull) ·
conservar `sizing_reason` del PM (una frase del por qué del tamaño dentro del cap; sin convicción numérica no calibrada).

**FIN DE LA SOMBRA (IA2, no solo calendario):** todos los tests críticos pasan · replay consume evidencia REAL sin
defaults de aprobación · ≥1 permitido y ≥1 bloqueado por cada gate · ninguna apertura con datos portantes desconocidos ·
revisar a mano las primeras 20 decisiones donde P1 cambiaría la propuesta del PM. Después: autoridad en paper → freeze 90d
(congelar bordes/parámetros, NO los fixes fail-closed).

### 8.bis — Estado del rework (2026-11-26, avance autónomo)
**Los 5 commits del rework ESTÁN HECHOS (código), 1065 tests verdes + los 24 tests fail-closed de IA1 pasan (antes
fallaban 23):** commit 1 caps fail-closed (02d458a) · 2 permiso fail-closed desde hechos crudos (8f33b38) · 3 arquetipo
robusto + banda con guardas (3417afe) · 4 rotación VALIDEZ-vs-MÉRITO (4ec7a0e) · 5 orquestador `evaluar_sombra` +
demo HONESTO sin inputs inventados + Doosan (5c97640). El demo honesto confirma: con los dossiers HISTÓRICOS (sin
campos económicos estructurados) P1 fail-closed BLOQUEA las compras y DIFIERE las ventas sin comparación — correcto.

**GATED POR EL OPERADOR (no se tocó autónomo — son cambios de autoridad VIVA o decisiones de schema):**
- **Conflictos P0 en el gate VIVO:** P0.1 `verifs.get(tk,"")` deja pasar "" como no-FAIL + REVIEW solo alerta (puede
  entrar a núcleo) · P0.4 el invariante de stubs usa el piso rígido 5% → marcaría toda OPTIONALITY como stub. Son
  cambios de comportamiento del gate con autoridad → requieren OK del operador (no se cambian a ciegas con él ausente).
- **El HARNESS REAL:** extender el schema del Analista para que EMITA los campos económicos estructurados (arquetipo,
  rango de banda/valor por acción, métrica obligatoria, falsador estructurado) → el orquestador los CONSUME (no los
  extrae de narrativa). Loguear "qué cambiaría" + registrar contrafactuales BLOQUEADOS. Es la pieza que falta para el
  replay real y la medición del edge. Decisión de diseño del operador.
- **Refinamientos de diseño de IA2 (fase del schema):** infra ESTRUCTURAL (no `contratado/EV`, que depende del precio) ·
  banda infra = FCFE/acción (cobertura IG → riesgo, no banda) · dos relojes (recalcular las variables dependientes del
  precio) · `sizing_reason` del PM (una frase) · falsador NO obligado a ser DURO sobre la métrica exacta · remover
  EXCEPTIONAL como tier de entrada (ya es inalcanzable) · separar `max_target_weight` de `can_add` (no liquidar MANTENER).

**FIN DE SOMBRA (IA2):** no activar hasta que el harness consuma evidencia REAL, ≥1 permitido y ≥1 bloqueado por gate,
ninguna apertura con datos portantes desconocidos, y revisión manual de las primeras 20 decisiones donde P1 cambiaría
la propuesta. Después: autoridad en paper → freeze 90d.

### 8.ter — Review 2 CERRADA: fail-closed INTEGRAL por confirmación positiva (2026-11-26, commit bfd06eb)
Las dos IAs EJECUTARON el código del rework (§8.bis) y convergieron: la integración seguía **fail-open**. El patrón:
los chequeos eran NEGATIVOS (`if ctx.get("campo_malo"): bloquear`) → una clave AUSENTE es falsy → no bloqueaba →
"bloquear todo" se volvía "ejecutar todo" cuando el caller olvidaba un campo (`execution_permission({abrir,PASS,CORE,
peso 6%})` → EJECUTAR). Rediseño por **CONFIRMACIÓN POSITIVA**, test-driven contra el spec combinado (24 tests de IA1 +
58 de IA2 = `tests/test_p1_fail_closed_v2.py`, los 82 verdes; suite 1162):
- **permiso**: apertura ejecuta SOLO con contexto completo (verif + tier con su banda de peso vía `tiers_cfg` +
  falsador ligado a la métrica + los 4 hechos operativos EXPLÍCITOS). Clave ausente = BLOQUEAR. Asimetría fail-closed:
  reducir/salir DIFIEREN ante info faltante (no atrapan). Evidencia mecánica = dict verificable. comparacion = enum
  cerrado. Stub bajo el mínimo del tier → BLOQUEAR. Rotación: `par_compra_bloqueada` explícito (atomicidad). pre_revenue
  exige margen p_implícita<p_razonada.
- **banda**: validación de UNIDAD (cobertura ∈[0,3]; precio/valor-medio ∈[0.2,5]; g como fracción) → unidad incoherente = None.
- **comparacion_rotacion**: 3 estados (PERMITIDA / BLOQUEADA — inválida o B DOMINADA / INDETERMINADA — falta info →
  difiere). El mérito NO lo veta el código (power-law).
- **evaluar_sombra**: arma el ExecutionContext tipado y lo COMPUTA; malformado → BLOQUEAR (no tumba la corrida); un
  override de arquetipo NO agranda el cap.
- **harness_sombra**: falsador debe medir un INSUMO del arquetipo; `falsador_id` estructurado; banda con el precio del
  DÍA, descarta insumos dependientes del precio si se movió >10%.

**Lo que NO forzó el spec (queda como refinamiento, NO bloquea Gate 0):** el contrato económico de unión-discriminada
de IA2 (Rango{bajo,alto,fuente} + clases UW por arquetipo con `status` COMPUTADO). Los tests pasan con el `Underwriting`
plano actual (+`precio_referencia`).

**GATE 0 ✅ HECHO (2026-11-26, commit 03464c5, $0, SIN autoridad viva):**
- **Tests de mutación** (`tests/test_p1_mutaciones.py`): propiedad contra el fail-open — partiendo de un input válido,
  CUALQUIER mutación (clave portante ausente, NaN/inf, %/fracción, precio 0, rango invertido, typo, tipo no-string)
  NUNCA da un resultado más permisivo. Cazó un crash real (`accion` no-string → AttributeError → ahora BLOQUEAR).
- **Log útil** (`shadow_log`, correcciones review-2 IA2): append FALLA VISIBLE (`registrar_corrida` chequea
  registros==decisiones) · 'cambiaría' mira el TAMAÑO (ACHICA: ejecuta con cap<peso) · motivos con CATEGORÍA
  DATO/ECONOMÍA/IPS/VERIF · peso_permitido · clave anti-duplicados.
- **Ensayo en seco** (`ops/gate0_dryrun.py`): fixtures (un Underwriting COMPLETO por arquetipo + legacy) por
  harness→orquestador→log; verifica precio del PACK, los 4 arquetipos EJECUTAN, el legacy BLOQUEA, la ATOMICIDAD de
  pares (compra de B bloqueada → venta de A DIFIERE), e invariante del log. **Suite 1225 verdes.**

**ANALISTA YA EMITE EL BLOQUE (2026-11-26, commit e7247d3):** `prompts/analista_v1.md` tiene la sección "ARQUETIPO Y
BANDA" (emite `underwriting`: arquetipo_confirmado + banda_inputs por arquetipo + métrica obligatoria + precio_referencia
+ status) y el Analista setea `falsador.id` (`Falsador.id` nuevo en el schema — gap que los fixtures tapaban: el harness
lee `falsador.id` y el Falsador real no lo tenía). SEAM con el tipo REAL (`Dossier` pydantic) probado end-to-end
(`tests/test_harness_dossier_real.py`): un Dossier COMPLETO ejecuta, sin underwriting fail-closed BLOQUEA. **Suite 1228.**

**PRÓXIMO (gated por el operador, 2 decisiones):** (1) **el HOOK en vivo** — dónde/ cuándo el runner del comité corre la
pasada en sombra (`evaluar_decision_sombra` + `construir_shadow_decision` + `registrar_corrida`) por cada decisión real,
append-only, SIN tocar autoridad (la superficie es `orquestador.py`/el runner del PM; es cambio del path vivo aunque solo
loguee → decisión del operador). (2) **piloto del Analista (3-5 nombres, 1-dic)** — correr el Analista con el prompt
nuevo, medir tasa de null/errores/fuentes/costo del bloque `underwriting`. Después: sombra por cantidad de decisiones
(≥20 con Underwriting, ≥5 ventas) → autoridad por etapas → freeze 90d. **Pendiente operador: revocar el PAT.**
