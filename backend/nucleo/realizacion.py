"""Escalera de realización + router de valuación (doc 31 §1, + review de build 2026-08).

Dos preguntas DISTINTAS, dos salidas independientes (no una sola variable para las dos):
  - `stage` (R0-R5, secuencial): ¿hasta dónde llegó ECONÓMICAMENTE? (madurez contable)
  - `route` (método): ¿le aplica el FCFE operable? → decidido por **owner_fcf = FCF − SBC**.

Por qué owner_fcf y no FCF crudo: el FCF de software growth está inflado por el add-back de SBC
(stock-based comp) — no-cash para liquidez pero COSTO REAL para el accionista (paga trabajo con
dilución). Como la perpetuidad usa el share count actual, hay que restar SBC (o modelar dilución
futura — una de las dos, nunca ambas ni ninguna). Así CRWD queda `stage=R2` (pérdida operativa GAAP,
verdad contable) pero `route=FCFE_OPERABLE` (genera caja real tras pagar en papel) con flag de SBC.

Se computa el VECTOR de booleanos tri-estado (True/False/None) y se mapea vector→etiqueta — NO una
cascada de elif (que descartaba info en el corte de OI). Propagación monótona por identidad contable:
OI>0 ⇒ GP>0 (OI = GP − opex, opex≥0) → clasifica defensa/servicios sin tag de GrossProfit. La
monotonía NO cruza al lado cash (OI>0 no implica CFO>0 por accruals/working capital).

Límite conocido (diferido): "revenue" es el XBRL headline, no el COMERCIAL del core (grants/NRE/
collaboration inflan la etapa) → flag `revenue_sin_depurar`; separar requiere segmentos/notas (§8).
"""
from __future__ import annotations

from dataclasses import dataclass, field

_DESC = {
    "R0": "sin revenue reportado material", "R1": "revenue, gross profit ≤ 0",
    "R2": "gross profit > 0, operating income ≤ 0", "R3": "operating income > 0, CFO ≤ 0",
    "R4": "CFO > 0, FCF ≤ 0 (capex)", "R5": "FCF > 0",
}
MATERIALIDAD_REV = 1e6            # revenue > $1M para no ser R0 (evita collaboration/grant trivial)


@dataclass
class Realizacion:
    stage: str | None                 # "R0".."R5" | "INDETERMINATE_AT_{GP,OI,CFO,FCF}" | None
    route: str                        # FCFE_OPERABLE | CASH_POSITIVE_NOT_OWNER_PROFITABLE | NON_FCFE | INDETERMINATE_*
    descripcion: str
    revenue_ttm: float | None
    gross_profit_ttm: float | None
    operating_income_ttm: float | None
    cfo_ttm: float | None
    fcf_ttm: float | None
    sbc_ttm: float | None
    owner_fcf_ttm: float | None       # FCF − SBC
    flags: list[str] = field(default_factory=list)


def _ttm(quarters: list[dict], key: str) -> float | None:
    vals = [q[key] for q in quarters if q.get(key) is not None]
    return sum(vals[-4:]) if len(vals) >= 4 else None


def _pos(x: float | None) -> bool | None:
    """Tri-estado: >0 → True, ≤0 → False, None → None (unknown)."""
    return None if x is None else x > 0


def etapa_realizacion(fin) -> Realizacion:
    quarters = getattr(fin, "quarters", []) or []
    rev = getattr(fin, "revenue_ttm", None)
    gp = _ttm(quarters, "gross_profit")
    oi = _ttm(quarters, "operating_income")
    cfo = _ttm(quarters, "ocf")
    fcf = getattr(fin, "fcf_ttm", None)
    sbc = getattr(fin, "sbc_ttm", None)
    owner_fcf = (fcf - sbc) if (fcf is not None and sbc is not None) else None

    gp_p, oi_p, cfo_p, fcf_p = _pos(gp), _pos(oi), _pos(cfo), _pos(fcf)
    ofcf_p = _pos(owner_fcf)
    flags = ["revenue_sin_depurar"]

    # Propagación monótona por identidad: OI>0 ⇒ GP>0 (resuelve nombres sin tag de GrossProfit).
    if oi_p is True and gp_p is None:
        gp_p = True
        flags.append("gp_inferido_de_oi_positivo")

    # --- STAGE (secuencial, descriptivo) ---
    rev_material = rev is not None and rev > MATERIALIDAD_REV
    if not rev_material:
        stage = "R0"
    elif gp_p is False:
        stage = "R1"
    elif gp_p is None:
        stage = "INDETERMINATE_AT_GP"
    elif oi_p is False:
        stage = "R2"
    elif oi_p is None:
        stage = "INDETERMINATE_AT_OI"
    elif cfo_p is False:
        stage = "R3"
    elif cfo_p is None:
        stage = "INDETERMINATE_AT_CFO"
    elif fcf_p is False:              # FCF ≤ 0 (breakeven NO es R5 — bug corregido)
        stage = "R4"
    elif fcf_p is None:
        stage = "INDETERMINATE_AT_FCF"
    else:
        stage = "R5"

    # --- ROUTE (método de valuación) — independiente del stage, sobre owner_fcf ---
    if ofcf_p is True:
        route = "FCFE_OPERABLE"      # genera caja real tras SBC (CRWD aunque OI<0)
    elif fcf_p is True and ofcf_p is None:
        route = "INDETERMINATE_SBC"  # FCF>0 pero SBC desconocida → no asumir SBC=0
    elif fcf_p is True:              # FCF>0 pero owner_fcf ≤ 0 → caja solo por el add-back
        route = "CASH_POSITIVE_NOT_OWNER_PROFITABLE"
    elif fcf_p is False:
        route = "NON_FCFE"           # → motores pre-revenue (reverse underwriting / funded path)
    else:
        route = "INDETERMINATE_FCF"

    # Flags de contexto
    if oi_p is False:
        flags.append("gaap_operating_loss")
    if fcf_p is True and sbc and fcf:
        flags.append(f"sbc_dependency={sbc / fcf:.0%}")
    if stage and stage.startswith("INDETERMINATE") and route == "FCFE_OPERABLE":
        flags.append("stage_indeterminado_pero_metodo_decidible")

    desc = _DESC.get(stage, stage or "indeterminada")
    return Realizacion(stage, route, desc, rev, gp, oi, cfo, fcf, sbc, owner_fcf, flags)
