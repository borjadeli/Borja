"""Núcleo de decisión determinista (rediseño — Núcleo consolidado v3).

Paquete AISLADO que implementa el flujo cerrado del núcleo:
    arquetipo → gate → mérito (Quality × Asimetría) → sizing → 5 vías → re-gate.

Corre en SOMBRA durante la migración (Fase 1 del traspaso): no toca el Portfolio
vivo (backend/agents/portfolio.py) hasta el corte. El LLM nunca asigna el
resultado de una decisión del núcleo; trae hechos fechados con fuente y una
tabla determinista decide.

Estado de implementación (Fase 1):
  - constantes        — §18, completo.
  - arquetipo         — §4 (asignación + ex-top + excepción contrato-en-firme).
  - fragility         — §10/§11 (caps por arquetipo×Frag + cubo residual-cero).
  - sizing            — §9 (Hard Cap + clamp [5%, HardCap]).
  - salida            — §13 (5 vías deterministas + re-gate candados).
  - gate              — §5 (pendiente: necesita el extractor de hechos LLM).
"""
