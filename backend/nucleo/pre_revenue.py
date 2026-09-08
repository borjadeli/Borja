"""Motor de reverse underwriting para pre-revenue (doc 31 §2, §5, §6) — capa buildable hoy.

Extiende el operable (NO lo reemplaza). Para la mayoría pre-revenue del universo, la pregunta no es
"¿cuánto vale el flujo?" sino **"¿cuánta economía exige el precio, y está financiada?"**. Este módulo
computa la parte que sale 100% de XBRL + feed de mercado, sin inventar nada:

  OptionPremium  OP = max(0, mcap − V_operable)            (lo que el precio paga por encima del piso)
  FCFE_req       = OP × r_exit × (1+r_hurdle)^t            (la caja que el precio obliga a explicar a t años)
  reverse_burden = (opex_cash_TTM + FCFE_req) / GP_TTM     (cuántas× debe multiplicarse el gross profit)

**Doble castigo desacoplado (fix triangulación 2026-08, doc 31 §2):** los dos `r` de la fórmula vieja
`OP × r × (1+r)^t` significaban cosas distintas. El `(1+r_hurdle)^t` es el retorno exigido DURANTE el
camino riesgoso (r de la etapa de hoy); el factor de adelante es el **cap yield terminal** del estado
YA de-riesgado al que la empresa migra a t años → `r_exit = min(r_hurdle, R_TERMINAL≈0.15)`. Usar
r_hurdle en ambos castigaba dos veces el ser pre-revenue hoy. IA1+IA2 convergieron independientemente.

**El nudo de honestidad (doc 31 §5):** la fórmula completa divide por ρ = mcap/(mcap+G), con G = costo
de capital restante hasta el hito. G casi nunca está divulgado → parsearlo (notas/reguladores) es Fase 2.
NO lo inventamos: computamos el burden con **ρ = 1 (piso optimista, sin dilución)** y mostramos la
presión de dilución (burn_yield/runway, `dilucion.py`) COMO EJE SEPARADO. Un nombre se penaliza solo si
falla en ambos. Así RKLB (R4, burden calculable) recibe tracción objetiva sin fabricarle economics a
OKLO/NNE (R0, `pure_option`).

Lo que este módulo DIFIERE explícitamente a Fase 2 (no lo aproxima con supuestos):
  - ρ real desde G (funded gap) — requiere costo-al-hito divulgado.
  - R0 físico q×u×P — requiere capacidad permitida/financiada/feedstock (notas + scrapers reguladores).
  - Funded critical path (grafo de carriles) — requiere niveles de hito verificables (ADAMS/FAA/FCC/DOE).
Cada salida trae flags que dicen qué NO está incluido (sin huecos silenciosos, doc 31 §8).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import politica

# --- Tiers de riesgo de CAPITAL (doc 31 §6) — mecánicos desde runway + banda de burn, NO narrativa.
# Refinamiento por funded-critical-path = Fase 2; hoy es un proxy duro y auditable.
RUNWAY_TIER_A = 3.0    # años de pista → dependencia baja del mercado de capitales
RUNWAY_TIER_B = 1.5    # entre B y A


@dataclass
class ReverseUnderwriting:
    price_anchor_status: str                 # ANCHORED | PURE_OPTION | NA
    reverse_burden_type: str                 # GP_MULTIPLE | NA
    reverse_burden: float | None             # (opex_cash + FCFE_req)/GP_TTM  a t, ρ=1
    fcfe_req: float | None                   # OP × r_exit × (1+r_hurdle)^t
    option_premium: float | None             # max(0, mcap − V_operable)  (USD)
    opex_cash_ttm: float | None
    t_anios: int | None
    r: float                                 # r_hurdle (retorno exigido de la etapa de hoy)
    r_exit: float | None = None              # cap yield terminal = min(r_hurdle, R_TERMINAL)
    capital_risk_tier: str = "NA"            # A | B | C | NA
    peer_rank: int | None = None             # asignado por hoja_evidencia._peer_rank_por_arquetipo (solo ANCHORED)
    flags: list[str] = field(default_factory=list)


def fcfe_requerido(option_premium: float | None, r_hurdle: float, t: int,
                   r_exit: float | None = None) -> float | None:
    """FCFE que el precio obliga a explicar a `t` años (doc 31 §2, fix 2026-08). ρ=1 (piso optimista).
    `r_exit` = cap yield terminal del estado de-riesgado (default = r_hurdle si no se pasa, retrocompat).
    FCFE_req = OP × r_exit × (1+r_hurdle)^t — desacopla el múltiplo de salida del descuento del camino."""
    if option_premium is None or option_premium <= 0:
        return 0.0 if option_premium == 0 else None
    exit_yield = r_hurdle if r_exit is None else r_exit
    return option_premium * exit_yield * (1.0 + r_hurdle) ** t


def opex_cash_ttm(gross_profit_ttm: float | None, operating_income_ttm: float | None,
                  sbc_ttm: float | None) -> float | None:
    """Opex de caja TTM ≈ (GP − OI) − SBC. GP−OI = gasto operativo bajo la línea de margen (R&D+SG&A);
    se le resta el SBC (no-cash). Aproximación: el SBC total puede incluir algo en COGS → flag aparte."""
    if gross_profit_ttm is None or operating_income_ttm is None:
        return None
    opex = gross_profit_ttm - operating_income_ttm              # gasto operativo (incluye SBC)
    return max(0.0, opex - (sbc_ttm or 0.0))                    # a caja: sin el componente SBC


def reverse_burden_gp(fcfe_req: float | None, opex_cash: float | None,
                      gross_profit_ttm: float | None) -> float | None:
    """(opex_cash_TTM + FCFE_req) / GP_TTM (doc 31 §2). Solo con GP > 0; None si no computable."""
    if fcfe_req is None or opex_cash is None:
        return None
    if not gross_profit_ttm or gross_profit_ttm <= 0:
        return None
    return (opex_cash + fcfe_req) / gross_profit_ttm


def gap_financiamiento(burn_anual: float | None, runway_anos: float | None, t: int) -> float:
    """G = la caja que hay que RAISEAR para financiar el burn hasta el horizonte t (doc 34 §3ter, fix IA1
    2026-08-18). `G = burn_anual × max(0, t − runway)`: si el runway ya cubre el horizonte, no diluye en t
    (G=0). Todo desde hechos citados (burn del FCF, runway de caja/quema) — NO es el 'G no divulgado' de Fase 2."""
    if not burn_anual or burn_anual <= 0 or runway_anos is None:
        return 0.0
    return burn_anual * max(0.0, t - runway_anos)


def burden_con_rho(burden_rho1: float | None, mcap: float | None, G: float) -> float | None:
    """Aplica ρ = mcap/(mcap+G) al burden (doc 34 §3ter): `burden_ρ = burden_ρ=1 × (mcap+G)/mcap`. El burden
    sobre GP y shares ACTUALES SUBESTIMA al quemador — financiar el burn diluye antes de que llegue el GP;
    el precio debe explicar el equity de HOY más el que se emite para sobrevivir. (Un-difiere el ρ de doc 31 §5.)"""
    if burden_rho1 is None or not mcap or mcap <= 0:
        return burden_rho1
    return burden_rho1 * (mcap + G) / mcap


def capital_risk_tier(runway_anos: float | None, banda_dilucion: str,
                      runway_critico: bool) -> str:
    """Tier de riesgo de capital (doc 31 §6), mecánico desde financiación. A=baja dependencia del
    mercado de capitales, C=dependencia dura. Sin burn (banda bajo/n-a) y sin runway ⇒ A (cash-rich)."""
    if banda_dilucion in ("severo", "extraordinario") or runway_critico:
        return "C"
    if runway_anos is None:                     # no quema → no depende de raise
        return "A" if banda_dilucion in ("bajo", "n/a") else "B"
    if runway_anos >= RUNWAY_TIER_A and banda_dilucion in ("bajo", "material"):
        return "A"
    if runway_anos >= RUNWAY_TIER_B:
        return "B"
    return "C"


def evaluar(*, stage: str | None, route: str, gross_profit_ttm: float | None,
            operating_income_ttm: float | None, sbc_ttm: float | None,
            operable_por_accion: float | None, precio: float | None, shares: float | None,
            mcap: float | None, arquetipo: str, dilucion) -> ReverseUnderwriting:
    """Ensambla el reverse underwriting de un nombre desde primitivos ya extraídos.

    `dilucion` = objeto `Dilucion` (dilucion.py). `operable_por_accion` = base_price del operable.
    No decide sizing ni ranking absoluto — solo produce las varas comparables DENTRO de arquetipo.
    """
    r = politica.r_efectiva(arquetipo)                 # r_hurdle: retorno exigido de la etapa de hoy
    r_ex = politica.r_exit(r)                           # cap yield terminal = min(r_hurdle, R_TERMINAL)
    t = politica.HORIZONTE_T.get(arquetipo, politica.HORIZONTE_T.get("Growth", 5))
    flags: list[str] = ["burden_rho=1 (dilución NO incluida; G no divulgado → Fase 2)"]
    if arquetipo not in politica.R_ARQUETIPO:          # hueco silencioso cerrado (fix C2, triangulación)
        flags.append(f"arquetipo_default_r=Growth (arquetipo '{arquetipo}' desconocido → r/t de Growth)")

    # Option premium = max(0, mcap − V_operable). Preferir mcap del feed; fallback precio×shares.
    v_operable = (operable_por_accion * shares) if (operable_por_accion is not None and shares) else None
    mcap_efectivo = mcap if mcap else (precio * shares if (precio and shares) else None)
    if mcap_efectivo is None or v_operable is None:
        op = None
        flags.append("option_premium_no_computable (falta mcap u operable)")
    else:
        op = max(0.0, mcap_efectivo - v_operable)
    if mcap is None and mcap_efectivo is not None:
        flags.append("mcap=precio×shares (feed no disponible) → FD aproximado")

    fcfe = fcfe_requerido(op, r, t, r_exit=r_ex)
    opex = opex_cash_ttm(gross_profit_ttm, operating_income_ttm, sbc_ttm)
    if sbc_ttm is None and opex is not None:
        flags.append("sbc_desconocida → opex_cash puede estar sobrestimado")

    tier = capital_risk_tier(getattr(dilucion, "runway_anos", None),
                             getattr(dilucion, "banda", "n/a"),
                             getattr(dilucion, "runway_critico", False))

    # Anchor status: ANCHORED solo con economía real (GP>0) Y revenue material confirmado (R2-R5).
    # El Burden_GP del doc 31 §2 está scopeado a "R1–R4 (con revenue)": un R0 (o revenue no material/no
    # extraído) es opción pura aunque se filtre un gross_profit — no se le calcula burden.
    tiene_gp = gross_profit_ttm is not None and gross_profit_ttm > 0
    stage_con_revenue = stage in ("R2", "R3", "R4", "R5")     # R1 tiene GP≤0 por definición
    if route == "FCFE_OPERABLE":
        # Genera caja del accionista → lo ancla el operable, no el reverse underwriting.
        status, btype, burden = "ANCHORED", "NA", None
        flags.append("route=FCFE_OPERABLE → anclado por operable (no reverse underwriting)")
    elif tiene_gp and op is not None and stage_con_revenue:
        burden_rho1 = reverse_burden_gp(fcfe, opex, gross_profit_ttm)
        # ρ real (fix IA1 2026-08-18, doc 34 §3ter): el burden ρ=1 subestima al quemador. G = caja a raisear
        # para financiar el burn hasta el horizonte; ρ=mcap/(mcap+G); burden /= ρ. Desde burn/runway citados.
        burn_anual = (getattr(dilucion, "burn_yield", None) or 0.0) * (mcap_efectivo or 0.0)
        G = gap_financiamiento(burn_anual, getattr(dilucion, "runway_anos", None), t)
        burden = burden_con_rho(burden_rho1, mcap_efectivo, G)
        flags = [f for f in flags if "burden_rho=1" not in f]
        if burden is not None:
            status, btype = "ANCHORED", "GP_MULTIPLE"
            if G > 0:
                flags.append(f"burden con ρ real: dilución de financiamiento G≈${G/1e6:.0f}M, "
                             f"ρ={mcap_efectivo/(mcap_efectivo+G):.2f} (burden ρ=1 era {burden_rho1:.0f}×)")
            else:
                flags.append("burden ρ=1 efectivo (runway ≥ horizonte → sin dilución de financiamiento en t)")
        else:                                                 # GP>0 pero opex/OI desconocido → no computable
            status, btype = "NA", "NA"
            flags.append("burden no computable (operating_income/opex desconocido)")
    else:
        # R0 / GP≤0 / revenue no material → opción pura, descriptivo, sin ranking (doc 31 §6).
        status, btype, burden = "PURE_OPTION", "NA", None
        if stage == "R0" and tiene_gp:
            flags.append("R0 (revenue no material/no extraído) pese a gross_profit>0 → pure_option; revisar revenue")
        elif stage == "R0":
            flags.append("R0 sin economía comercial → pure_option (funded critical path = Fase 2)")
        elif not tiene_gp:
            flags.append("gross_profit ≤ 0 o desconocido → aún sin economía para anclar el precio")

    return ReverseUnderwriting(
        price_anchor_status=status, reverse_burden_type=btype, reverse_burden=burden,
        fcfe_req=fcfe, option_premium=op, opex_cash_ttm=opex, t_anios=t, r=r, r_exit=r_ex,
        capital_risk_tier=tier, flags=flags)
