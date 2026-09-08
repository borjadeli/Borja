"""Bloque B — Mapa de cuellos de botella (capa de worldview, Capa 1).

Capa anterior al núcleo que organiza DÓNDE mira el sistema y dispara la búsqueda
de candidatas, SIN decidir capital. El átomo es el cuello de botella: un punto de
dependencia económica por estrangulamiento, nombrado por su POSICIÓN ESTRUCTURAL,
nunca por su estado.

Obedece la misma ley que el núcleo (no se reabre):
  - El LLM trae el hecho de estrangulamiento (lead-time, contrato, precio); una
    tabla determinista decide si nace o cambia un nodo. El LLM nunca declara
    "esto es un cuello" ni "esto es importante".
  - No congelar conclusiones: hechos fechados, no estados que se pudren.
  - Anti-sobreingeniería: una sola pieza nueva aceptada en toda la triangulación
    (timestamp_revision por vínculo candidata↔nodo).
  - Unidad por dependencia económica real, no etiqueta GICS.

Módulos:
  nodo         — estructura del nodo (3 bloques §3) + vínculo + hecho.
  transiciones — tabla determinista apertura/transición/archivo (§4).
  brujula      — territorios-cuello de arranque (§9.1.1).

El contenido del mapa (los nodos concretos) lo puebla el Discovery con hechos
cuando el sistema corre; poblarlo a mano viola el principio rector (§10).
"""
