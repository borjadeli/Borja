# 17 — Etapa 4: Deep research + ficha rica (diseño)

> 🏗️ **ANDAMIAJE (diseño; parcialmente implementado) — ver `00_MAPA_DOCUMENTOS.md`.** El bull/bear
> disciplinado ya está en el compiler (doc 32 §8); falta enchufe + dashboard. Estado: doc 32.

> Diseño en doc, **sin código** hasta acordar. Ancla en la constitución (`13_`):
> evidencia (Art. 3), gate/quality/fragility (Art. 4), refinamientos del análisis
> (Art. 12), ledger (Art. 16). Regla: **construir sobre el núcleo que ya existe**,
> no reescribir la lógica de inversión.

## Qué YA existe (se CONSERVA / se ENCHUFA)
El núcleo ya hace casi todo el análisis por empresa:
- `extractor.py` — trae hechos: capa determinista (EDGAR/market: revenue, deuda, caja,
  dilución, precio) + capa LLM (arquetipo-inputs, gate, P1/triggers, fragilidad, calidad,
  **bull/bear**). Compone un `EntradaEmpresa`.
- `flujo.evaluar_empresa()` — corre `arquetipo → gate → Quality × Asimetría → Fragility →
  Hard Cap`. Todo determinista; el LLM solo trajo hechos.

**La "ficha rica" NO es un motor nuevo:** es (a) esos hechos + (b) las salidas
deterministas del núcleo, **persistidas y versionadas**. Etapa 4 = enchufar eso al ledger
+ las dos mejoras del Art. 12.

## 4a — Ficha versionada + persistencia `ENCHUFE` (build)
Cuando una empresa llega a **En-deep-research** (pasó Filtro 0), se corre el extractor +
`evaluar_empresa` y se persiste una **versión de ficha** en el ledger.

- **`nx_ficha_version`** (append-only): `id, ticker, version, fecha, arquetipo, quality_tier,
  fragility_score, bull, base, bear, asimetria, cap_celda, cap_crr, hard_cap, es_binary,
  decision (candidata/watchlist/rechazo), vencimiento, estado_vigencia`.
- **`nx_hecho`** (append-only): cada hecho con `campo, valor, tipo (HECHO/INFERENCIA/
  HIPOTESIS), verdad (TRUE/FALSE/UNKNOWN), fuente (A/B/C), documento, fecha_hecho` (Art. 3).
- Transición: `evaluar_empresa` devuelve `candidata` → **Elegible**; `watchlist` (gate
  "todavía-no") → **Esperando-evidencia**; `rechazo` → **Descartada**.
- **Costo:** el LLM del extractor corre **solo sobre los que pasan Filtro 0** (conjunto
  chico) y se **cachea** (`data/nucleo_hechos/`); re-extracción solo por evento (Art. 7).

## 4b — Mejora 1: bull/bear disciplinado (Art. 12.1) `DISEÑO+BUILD`
**Hoy:** el LLM emite el bull/bear como **precio final** (el prompt pide múltiplos, pero el
número lo pone el LLM). Es la pata más blanda: maneja asimetría → mérito → sizing.

**Cambio de contrato:** el LLM deja de emitir el precio y pasa a traer, por escenario
(bear/base/bull), **el fundamento citado + el múltiplo justificado**:
- `fundamento` (revenue documentado / backlog / contrato firmado / EBITDA) **con fuente**.
- `múltiplo` (EV/S, EV/EBITDA, P/E) **con justificación** (rango de pares / histórico).
- Un **paso determinista computa** `precio_objetivo = fundamento × múltiplo / shares` (o el
  puente correcto EV→equity). El LLM **no** pone el número final.
- **Bull** solo con hechos ocurridos (dieta anti-IONQ, ya existe); **bear** = downside sobre
  riesgos documentados + residual de balance. Asimetría **winsorizada ~5:1**.
- Regla dura: **ningún bull/bear sin (hecho+fuente) × (múltiplo+justificación)**.

`A DECIDIR`: el puente EV→equity (restar deuda neta) y qué múltiplo por arquetipo se admite.

## 4b — Mejora 2: durabilidad del cuello (Art. 12.2) `DISEÑO+BUILD`
La tesis es "cuellos"; hay que analizar **por qué no se replica/sustituye y por cuánto**.
- **Hechos nuevos (con fuente):** barreras a nueva oferta (capex, lead-time para sumar
  capacidad, IP/moat regulatorio, ciclos de calificación); riesgo de sustitución; **vida útil
  del shortage** (estructural / cíclico / transitorio).
- **Dónde entra:** un **piso de durabilidad en el gate** (cuello sin evidencia de durabilidad
  + shortage transitorio → "todavía-no" / tier menor) **y** durabilidad sumando a Quality.
- Se conecta con el estado del nodo (`confirmado / debilitándose`), llevándolo a nivel empresa.
- `A DECIDIR`: ¿piso duro en el gate, o solo un input de Quality? Caso testigo: CDMO de GLP-1.

## Modelo de costo (limitaciones)
- LLM (caro) **solo detrás del Filtro 0** → conjunto chico.
- Hechos **cacheados**; re-extracción por evento, no por reloj.
- Las mejoras 12.1/12.2 **agregan campos al mismo prompt del extractor**, no una corrida
  nueva → costo marginal ~cero.

## Orden propuesto
1. **4a** (enchufe + persistencia de ficha) — build, con tests. Bajo riesgo.
2. **4b.1** (bull/bear disciplinado) — diseño fino + build. Es la mejora de mayor impacto.
3. **4b.2** (durabilidad) — diseño fino + build.

## Decisiones abiertas (para el operador)
- Puente EV→equity y múltiplos admitidos por arquetipo (12.1).
- Durabilidad: ¿gate duro o input de Quality? (12.2).
- ¿Arrancamos por 4a (enchufe, seguro) o querés cerrar primero el diseño de 4b?
