"""Bloque C — Capa de selección (agentes que rodean al núcleo).

Los agentes ALIMENTAN y EJECUTAN el núcleo; no lo reemplazan. No se crean agentes
desde cero: se reposicionan los que ya corren. Principios heredados que C obedece
y NO reabre:
  - El núcleo manda y es determinista. El LLM nunca asigna el resultado de una
    decisión del núcleo (gate, mérito, sizing, vías de salida).
  - El momentum sectorial es input de SELECCIÓN, nunca determinante del núcleo.
  - No congelar conclusiones. Anti-sobreingeniería.

Módulos:
  presupuesto — freno único de gasto + desfreno por fecha + prioridad de cola (§3).
  watchlist   — watchlist VIVA + MAX_WATCHLIST (§5).
  pm          — Portfolio Manager: arma el mix sesgado sectorialmente (LLM) (§1).
  sparring    — segundo LLM fresco que ataca el mix del PM (§2).

La varianza del LLM queda enjaulada en esta capa y NUNCA toca el núcleo.
"""
