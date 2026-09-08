"""Constantes de la capa de selección (Bloque C). Calibrables.

La forma (qué dispara) está cerrada en C; los números finos se calibran con
tracking, igual que las del núcleo (§18) y las del mapa (§9.2).
"""
from __future__ import annotations

# Sparring pesado — disparadores (traspaso §7-C).
TECHO_DEPLOY_SPARRING = 0.30        # deploy "grande" (cerca del techo 40%) que gatilla sparring por default.
UMBRAL_OPCIONALIDAD_SPARRING = 0.70  # % opcionalidad priceada "alta" que choca con criterio del PM.
