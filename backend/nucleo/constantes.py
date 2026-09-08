"""Constantes del núcleo — Núcleo consolidado v3, §18.

«Primera aproximación menos mala — no validadas, están mejor. La forma y los
principios están sólidos; los números finos se calibran con tracking histórico
cuando el diseño se estabilice.»

Todo valor acá es [IMPLEMENTACIÓN] calibrable salvo donde el doc lo marca como
estructural. No inventar constantes nuevas: el rediseño cerró con cero scores
nuevos y muy pocas constantes nuevas (cubo 8%, banda 1.25, vidas, ciclos).
"""
from __future__ import annotations

# ---- Cartera (§7, §18) ----
MAX_POSICIONES = 12          # Techo de slots. Operador 2026-06-30: 8→12 para desplegar el 70→100% con nombres NUEVOS (no piramidando). Real corre 10.
MAX_POR_SUBSECTOR = 3         # Máx posiciones por sector (operador 2026-06-30: 2→3). Se enforcea sobre Ficha.sector en el deploy del paper.
# Despliegue de capital: el 70% es PISO (floor), NO techo. Por debajo, con
# candidatas claras disponibles, la cartera está SUBINVERTIDA (capital ocioso). El
# despliegue sube hasta TOPE_INVERTIDO guiado por mérito; el cash que sobre emerge
# solo de los Hard Caps + piso 5% (no se fuerza si no hay oportunidad clara).
OBJETIVO_INVERTIDO = 0.70     # PISO de inversión. Estar por debajo (cash) es la excepción a documentar.
TOPE_INVERTIDO = 1.00         # Techo de despliegue: hasta 100% si el mérito y los Hard Caps lo permiten.
PERMITIR_PIRAMIDAR = False    # Operador 2026-06-30: el 70→100% se despliega comprando nombres NUEVOS, no topeando existentes. (La lógica de topeo queda disponible si se reactiva.)
INCREMENTO_MIN_TOPEO = 0.01   # No topear por menos de 1% de cartera (evita micro-churn cada ciclo).
PISO_POSICION = 0.05          # Mérito normalizado < 5% → watchlist (no entra).
TECHO_POSICION = 0.40         # Cap absoluto por posición.
SLOT_BUCKET_MAX = 0           # Bucket disuelto (era 1).

# ---- Riesgo agregado / recorte (§11.2, §13.2) ----
CUBO_RESIDUAL_CERO = 0.08     # Máx agregado en posiciones de ruptura cuasi-total.
BANDA_RECORTE = 1.25          # Vía 5 recorta cuando peso vivo > HardCap_vigente × 1.25.

# ---- Salida (§13, §18) ----
VIDAS_REENTRADA = 1           # Una re-entrada post-trigger por posición (Candado B).
# Earnings sin hecho a favor que disparan el stop de progreso (vía 1):
CICLOS_SIN_PROGRESO_BASE = 2  # Madura / Growth / Tracción.
CICLOS_SIN_PROGRESO_FRAGIL = 1  # Pre-revenue / Binary.
ROTATION_UMBRAL_SALIDA = 0.5  # Asimetría vigente < 0.5x → vía 4 (solo arquetipos elegibles).

# ---- Gate / arquetipo (§4, §5, §18) ----
UMBRAL_PREREV = 10_000_000     # Piso de revenue elegible para salir de Pre-revenue ($10M).
UMBRAL_GROWTH = 50_000_000     # Piso para Growth/Madura (revenue elegible limpio) ($50M).
CRECIMIENTO_GROWTH = 0.25      # Crecimiento elegible que separa Growth de Madura (25%).
EXTOP_TOP1 = 0.50              # Top-1 > 50% dispara ex-top.
EXTOP_TOP1_TOP2 = 0.66         # Top-1 + Top-2 > 66% dispara ex-top.
VENTANA_P2_MESES = 12          # Catalizador definitorio Pre-revenue (regla «todavía no»).
VENTANA_T1_TRIMESTRES = 4      # Hecho comercial nuevo de Tracción.
VENTANA_T2_MESES = 18          # Catalizador de Tracción.
MARGEN_FINANCIACION_MESES = 6  # Margen sobre el hito en P3/B3.
LIQUIDEZ_SCREENER = 1_000_000  # $1M/día — filtro de universo, NO gate.

# Muro de vencimientos de deuda → CRR-crítico (§9). Calibrable 18-24 meses.
MURO_DEUDA_MESES = 18

# Ventana de proximidad de catalizador que protege de rotación / expulsión
# (§14 núcleo y §5 watchlist de C): 45-60 días.
VENTANA_CATALIZADOR_PROTEGIDA_DIAS = (45, 60)

# ---- Tabla de caps por arquetipo × Fragility Score (§11) ----
# Cada celda es el TECHO de sizing (% de cartera). El mérito decide cuánto del
# techo se llena; el piso de 5% corta abajo. Columna Frag 3 = recta iso-pérdida.
CAPS_ARQUETIPO_FRAGILITY: dict[str, dict[int, float]] = {
    "Madura":      {0: 0.40, 1: 0.33, 2: 0.25, 3: 0.13},
    "Growth":      {0: 0.33, 1: 0.27, 2: 0.19, 3: 0.11},
    "Tracción":    {0: 0.27, 1: 0.21, 2: 0.14, 3: 0.08},
    "Pre-revenue": {0: 0.22, 1: 0.17, 2: 0.12, 3: 0.07},
    "Binary":      {0: 0.08, 1: 0.07, 2: 0.06, 3: 0.05},
}

ARQUETIPOS = tuple(CAPS_ARQUETIPO_FRAGILITY.keys())
# Arquetipos con negocio base (residual sobrevive si muere la tesis de upside).
ARQUETIPOS_CON_REVENUE = ("Madura", "Growth", "Tracción")

# ---- Constantes del sistema viejo que MUEREN (§16, §18) ----
# Documentadas acá para que quede explícito qué se elimina en el corte:
#   SCORE_MIN_ENTRADA, UMBRAL_DRIFT_SCORE, multiplicadores CRR 0.70/0.85,
#   vocabulario de momentum de 4 estados como determinante.
