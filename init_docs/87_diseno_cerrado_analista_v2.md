# 87 — Diseño cerrado: Analista v2 (comité → 1 agente + chequeos deterministas) (2026-11-19)

> Converge el brief doc 86 con la crítica externa + dos diagnósticos de código/logs. **El análisis lo hace
> Opus+web igual (doc 49); el comité no le gana en profundidad (doc 82). La pregunta era cuánto andamiaje vale.**
> Respuesta medida: **casi todo el andamiaje valioso ya es determinista o barato; los 2 agentes Sonnet
> (Bear/Verificador) se disuelven.** Falta un adversario de verdad, que NO era el Bear.

## 1. Lo que los diagnósticos PROBARON (no opinión)
- **El Bear es DECORATIVO (write-only).** `atacar()` se calcula (~$8 gastados en 56 corridas) y se **guarda**,
  pero el dossier NO se re-corre, la invertibilidad/zonas/PM/Verificador **no lo leen** — solo lo muestra el
  dashboard. Cero impacto en decisiones **por construcción**. (Esto prueba que ESTE Bear no servía, NO que no
  haga falta un adversario.)
- **El valor del Verificador NO es el contraste de números — es la CLASIFICACIÓN DE FUENTES, y ya es
  determinista.** `clase_por_url` clasifica por dominio (sec.gov=primaria · IR/EX-99=company_statement ·
  news/browse-edgar=media). El check de **procedencia** (la URL del claim ∈ URLs que trajo web_search) = el
  "cruzar citas contra el tool-log" de la crítica, **ya construido**. En 17 nombres del cache los números
  matchean XBRL; los 7 "review" son todos legítimos (tesis sobre comunicados/MOUs, p.ej. NBIS con 6 claims
  centrales sobre press releases).
- **n=5 A/B:** Opus no fabrica números (puntea cuando duda), clava el income statement, deja agujeros de
  cobertura que el XBRL llena. Caveat: n=5 → hasta ~15% de invento posible por la regla de tres.

## 2. Diseño cerrado

**SE MANTIENE:**
- **data_pack XBRL + calculadoras** — cobertura + consistencia entre nombres + costo. (Con el guard de frescura
  de hoy, commit 768e9f1.)
- **El contrato de salida mínimo** (escenarios, falsador fechado, valuación, invertibilidad) + **un campo libre**
  "lo que más importa y no entra en estos campos".
- **El Auditor**, re-mandatado como ADVERSARIO (ver §3).

**SE DISUELVE (2 agentes Sonnet → 0):**
- **Bear** → eliminado. Su función (adversarial) se reemplaza, no se pierde (§3).
- **Verificador LLM** → disuelto en **checks deterministas** que ya existían: `clase_por_url` (clase de fuente) +
  procedencia (anti-cita-inventada) + la regla "central sobre fuente no-primaria → review". Un modelo barato
  queda SOLO para el residuo (un claim cuya clase no se resuelve por URL).

**CAMBIA:**
- **Analista → Analista v2:** (a) **pre-mortem ANTES de la tesis** ("si a 12m cae 50%, ¿por qué?"); el orden
  importa (ataque antes de comprometerse = menos motivado); la tesis responde cada punto; el falsador fechado
  sale del punto más fuerte. Costo ~0. (b) **Razona en PROSA (memo libre)**, no JSON mientras piensa (Tam et al
  2024: el formato forzado degrada el razonamiento). (c) Un **paso barato extrae** el contrato del memo: permite
  **null**, cada campo **cita el párrafo** del memo (string-match); la **tasa de null mide los huecos**.
- **Chequeo de números — MARCA, NO CORRIGE** (RXRX: con autoridad para pisar a Opus, el chequeo inyectaba el
  dato viejo). Guarda **dos** números con su `as_of`: point-in-time XBRL (comparar/backtest) y pro-forma último
  (valuar hoy: ATM/converts/emisión post-cierre). **Matching de definiciones:** si el número del Analista no
  pega, probarlo contra agregaciones candidatas (caja: cash / +STI / +LTI; deuda: ±leases, ±corriente;
  acciones: portada/pond./diluidas) → si matchea una, resuelto+etiquetado (OKLO/MP/CIFR se resuelven solos).
  Divergencia **no declarada** = flag; declarada con fuente post-cierre = se acepta y loguea. El residuo
  (no matchea, no declarado, **material** vs market cap o vs lo que usa la tesis) → revisión (persona o modelo
  barato, no agente).
- **Red flags de supervivencia — NO los cubre el 8-K.** Going concern / material weakness viven en el 10-K
  (informe auditor, Item 9A) y 10-Q (nota de liquidez), pueden arrastrarse trimestres sin 8-K; + NT 10-K/10-Q
  (presentación tardía) + restatements chicos (casillas dei de clawback en la portada). → **scan determinista
  acotado** (informe auditor + sección de controles + nota de liquidez; acotado porque el boilerplate de risk
  factors los menciona condicionalmente) + **clasificador barato solo si pega** (real vs hipotético). Los flags
  entran al data_pack con fecha (point-in-time) y el Analista está obligado a responderlos.
- **Claims no-XBRL (backlog/contratos/guidance):** el Analista cita los 3-5 claims que sostienen la tesis →
  cruce contra el tool-log (URL nunca abierta = cita inventada, sin LLM). Es el check de procedencia extendido.

## 3. El adversario (la decisión de fondo)
El Bear no cumplía 3 de las 4 condiciones de un adversario útil (contexto independiente / mandato de matar /
capacidad pareja / consecuencias). Reemplazo en **dos capas**, sin agente nuevo:
1. **Pre-mortem dentro del Analista** (barato, ataca su propio futuro ANTES de la tesis).
2. **El Auditor como adversario con mandato explícito:** recibe data_pack + dossier, arma el **kill-case más
   fuerte**, dice si cambia la invertibilidad; no pisa al Analista pero marca "revisar" para el PM. Es de **otra
   familia de modelo** (errores descorrelacionados) y ya se paga.

## 4. Lo que falta medir antes de codear (o en paralelo)
- **El experimento de ~20 nombres** (plegado/pre-mortem vs separado) para confirmar que el pre-mortem baja
  sobreconfianza (más prob bull / más upside / más "invertible" sin info nueva = razonamiento motivado).
- **Plantar fallas**: inyectar un hecho negativo al data_pack (going concern / pérdida de cliente / dilución) y
  ver qué versión lo pondera.
- **Confirmar que 2.9 búsquedas del Analista no recortan la investigación del NEGOCIO** (solo la de números, que
  ya le damos). Si la narrativa sale de memoria y no de la web, el ahorro es falso.
- **Diagnóstico #1 incompleto:** no hay set etiquetado de "cagadas"; las del cache no lo son. Hipótesis: si
  existen, son tesis sobreconfiadas (no números) → v2 las ataca; conviene juntar 5-10 ejemplos reales del
  operador para confirmar el origen.

## 5. Neto
3 agentes LLM (Analista+Bear+Verificador) → **1 (Analista v2) + Auditor-adversario + chequeos deterministas**.
Más barato a escala, menos superficie de bugs, y **sin perder** lo que el comité aportaba de verdad (grounding,
clasificación de fuentes, anti-cita-inventada) — porque casi todo eso ya era determinista.
