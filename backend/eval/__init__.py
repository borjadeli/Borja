"""Evaluación del extractor (P0 del motor de evidencia, doc 22).

Herramientas para medir OBJETIVAMENTE si el extractor mejora, antes de reescribirlo:
  - gold set: hechos etiquetados a mano contra el filing REAL (data/gold_set/).
  - harness: precisión/recall + estabilidad entre corridas + violaciones de grounding.

Sin esto, cualquier cambio al extractor es opinión (ver COHR: flip 2/4 sobre inputs idénticos).
"""
