# 18 — Mapa de una página: dónde estamos

> ⚠️ **SUPERADO (2026-07) — ver `00_MAPA_DOCUMENTOS.md`.** Cifras viejas ("78 tests", "PM no existe",
> "ledger fiel implementado" = todos falsos hoy). Para el estado vigente manda **doc 32**.

> Para recuperar la foto completa sin perderse en el detalle. Honesto.

## La foto grande
Estamos **reconstruyendo el sistema sobre bases honestas** (contabilidad fiel, tests,
un LLM que trae hechos pero no inventa los números de decisión), **sin romper lo que
corre**. El grueso de la lógica de inversión del núcleo **se conserva**; el trabajo real
es **contabilidad + conexión + pruebas**, no reescribir la estrategia.

## Qué está CONSTRUIDO y probado — 78 tests (el sistema viejo tenía 0)
1. **Ledger fiel** — acciones y caja reales, costos, corporate actions, reconciliación.
   Sin look-ahead. (Reemplaza el paper viejo, que estaba inflado.)
2. **Identidad + 9 estados + mapa persistido** — el ciclo de vida de una empresa.
3. **Entrada + universo + Filtro 0** — corre sobre **datos reales** (yfinance/EDGAR).
4. **Ficha versionada** — enchufa el núcleo real (gate/arquetipo/quality/…) al ledger.
5. **Motor de valuación disciplinado** — el bull/bear sale de un motor determinista,
   no de un número libre del LLM.

## Qué FALTA para el pipeline completo
- Conectar el LLM al motor de valuación (extracción de fundamento + pares).  *(medio)*
- **El PM que construye la cartera dentro de los caps** — la pieza central, hoy no existe. *(grande)*
- Sparring + aprobación.  *(medio)*
- Discovery automático (que descongele el universo heredado).  *(medio)*
- Vistas nuevas + desacople del sistema viejo.  *(grande)*

## Lo que NO está probado (la verdad)
Que el sistema nuevo **gane más plata** que el viejo. Tenemos **mejor proceso**
(más honesto, más correcto, testeado), pero **cero evidencia de mejores retornos**.
Eso solo se prueba con un **backtest / forward-test** que todavía no corrimos.

## Las dos cosas que conviven hoy
- **Viejo:** completo, corriendo, con contabilidad **inflada** y score subjetivo.
- **Nuevo:** esqueleto **sólido y honesto**, pero **incompleto** (le falta el PM y el
  cableado end-to-end).

## El camino a "provably better" (el norte de mediano plazo)
1. Terminar el **pipeline mínimo end-to-end**: entrada → ficha → **PM** → paper fiel.
2. Correr un **backtest / forward-test** comparando nuevo vs viejo **con la misma vara honesta**.
3. Recién ahí sabemos, con datos, si es mejor de verdad — no por fe.

## En una frase
Construimos algo **objetivamente más honesto, correcto y confiable de mantener** —
pero que **aún no demostró** ser mejor invirtiendo, y **no está terminado**. El próximo
gran objetivo es **cerrar el mínimo que se pueda comparar** contra el viejo.
