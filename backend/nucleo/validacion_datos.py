"""Cross-validator de datos financieros — flags automáticos de plausibilidad (auditoría 2026-08).

`revenue_ttm` era un input muerto: ahora cruza contra el FCF y el capex para cazar SOLO los errores
de extracción, ANTES de que lleguen al PM. No es un gate ni corrige nada: emite FLAGS para revisión
(sistema advisory). Implementa la regla del operador "un dato mal no debería pasar" convirtiendo
"lo encontramos a mano esta vez" en "el sistema lo marca solo la próxima".

Cada flag captura un patrón real hallado en la validación:
  - capex nulo con revenue material  → tag de capex faltante (caso CLS: FCF quedaba = OCF, ~2× real).
  - margen FCF implícito fuera de banda → FCF inflado/mal (caso VRNS ~2×).
  - caja > 50% del market cap → caja/shares sospechosos (caso LEU: $136/acción con shares stale).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Bandas de plausibilidad (priors; anchas, para cazar errores gruesos, no juzgar calidad de negocio).
MARGEN_FCF_MAX = 0.40           # >40% de margen FCF es muy raro → probable inflación del FCF
MARGEN_FCF_MIN = -2.0           # <−200% de margen FCF → probable error
REVENUE_MATERIAL = 500e6        # umbral de "revenue material" para exigir que el capex exista
CAJA_FRAC_MCAP_MAX = 0.50       # caja > 50% del market cap → verificar caja/shares
STALE_SHARES_DIAS = 200         # dato de shares >~2 trimestres más viejo que el último Q → stale (doc 30)


@dataclass
class Flag:
    campo: str
    severidad: str              # "alta" | "media"
    detalle: str


def flags_plausibilidad(fin, precio: float | None = None) -> list[Flag]:
    """Devuelve la lista de flags de plausibilidad para un FinancialsQuarterly. Vacía = sin sospechas."""
    flags: list[Flag] = []
    rev = getattr(fin, "revenue_ttm", None)
    fcf = getattr(fin, "fcf_ttm", None)
    capex = getattr(fin, "capex_ttm", None)
    shares = getattr(fin, "shares_outstanding", None)
    caja = getattr(fin, "cash", None)

    # 1. Capex AUSENTE con revenue material → probable tag de capex faltante (caso CLS: FCF quedaba
    #    = OCF sin restar capex). NO se flaggea un capex bajo pero presente (software asset-light legítimo).
    if rev and rev >= REVENUE_MATERIAL and capex is None:
        flags.append(Flag("capex_ttm", "alta",
                          f"capex no encontrado con revenue ${rev/1e6:,.0f}M — probable tag faltante "
                          "→ FCF puede estar sin restar capex (inflado)"))

    # 2. Margen FCF implícito fuera de banda → FCF probablemente mal (caso VRNS).
    if rev and rev > 0 and fcf is not None:
        m = fcf / rev
        if m > MARGEN_FCF_MAX:
            flags.append(Flag("fcf_ttm", "media",
                              f"margen FCF implícito {m:.0%} > {MARGEN_FCF_MAX:.0%} — inusualmente alto, verificar FCF"))
        elif m < MARGEN_FCF_MIN:
            flags.append(Flag("fcf_ttm", "media",
                              f"margen FCF implícito {m:.0%} < {MARGEN_FCF_MIN:.0%} — verificar FCF"))

    # 3. Caja > 50% del market cap → caja o shares sospechosos (caso LEU).
    if precio and shares and caja and shares > 0:
        mcap = precio * shares
        if mcap > 0 and caja / mcap > CAJA_FRAC_MCAP_MAX:
            flags.append(Flag("cash", "media",
                              f"caja {caja/mcap:.0%} del market cap — verificar caja/shares"))

    # 4. Shares STALE por ANTIGÜEDAD (doc 30): el dato de shares (cover-page) mucho más viejo que el
    #    último trimestre → dei stale (caso LEU: shares de 2022). Mide FECHA, no cantidad → NO se confunde
    #    con dilución real (un nombre que diluye tiene shares recientes, no viejos). Severidad media (avisa,
    #    no saca del ranking) — el número por-acción (mcap, valuación) puede estar mal si las shares son viejas.
    shares_asof = getattr(fin, "shares_as_of", None)
    quarters = getattr(fin, "quarters", None) or []
    ref = quarters[-1].get("fecha") if quarters else None
    if shares_asof and ref:
        try:
            dias = (date.fromisoformat(ref[:10]) - date.fromisoformat(shares_asof[:10])).days
            if dias > STALE_SHARES_DIAS:
                flags.append(Flag("shares", "media",
                                  f"dato de shares de {shares_asof[:10]} ({dias}d antes del último Q) — "
                                  "posible stale → mcap/por-acción sospechoso, verificar"))
        except (ValueError, TypeError):
            pass

    return flags
