"""Reverse-DCF unificado (doc 36) — el solver de T* + el estado de valuación. Reemplaza el falsador binario.

Falsación, no proyección: se fija el crecimiento en lo DEMOSTRADO-fadeado (crecimiento.py) y se despeja
`T*` = cuántos años de compounding EXIGE el precio, a través de la superficie de margen {P25,P50,P75}.
`V(T)` es monótona no-decreciente y converge → bisección/interpolación, raíz única. Colapsa a owner-FCF/r
(T*=0) para una madura: el g=0 es el PISO, no el denominador. El estado sale de plegar la superficie de
margen en la escalera de T* (COVERED a P25, STRETCH a P50, OPTION a P75) y tomar el PEOR con data_state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.nucleo import crecimiento, politica

_ORDEN = {"COVERED": 0, "STRETCH": 1, "OPTION_PRICED": 2, "NON_UNDERWRITABLE": 3}


def _peor(a: str, b: str) -> str:
    return a if _ORDEN[a] >= _ORDEN[b] else b


def valor_a_T(T: int, R0: float, g_D: float, m0: float, mj: float, r: float, *,
              estres: bool = False, h_margen: int = politica.H_MARGEN) -> tuple[float, float]:
    """`V(T; m_j)` (doc 36 §1): PV del path explícito (crecimiento demostrado FADEADO, margen m_0→m_j) +
    PV del terminal (perpetuidad g=0 a r sobre el revenue del año T). Devuelve (V, PV_terminal)."""
    R, V, disc = R0, 0.0, 1.0
    for t in range(1, T + 1):
        R *= (1 + crecimiento.fade(g_D, t, estres=estres))
        m = m0 + (mj - m0) * min(t, h_margen) / h_margen
        disc *= (1 + r)
        V += R * m / disc
    pv_term = (R * mj / r) / disc
    return V + pv_term, pv_term


def t_star(P_ops: float, R0: float, g_D: float, m0: float, mj: float, r: float, *,
           estres: bool = False) -> dict:
    """Despeja `T*` tal que `V(T*) = P_ops`. T*=0 si el piso g=0 (owner-FCF/r) ya cubre el precio. None si el
    precio supera el valor máximo alcanzable (sin raíz antes de T_MAX → el precio pide más que ∞ años al ritmo
    demostrado). Devuelve {t_star, tv_share} (tv_share = PV(terminal)/P_ops en la raíz)."""
    if not P_ops or P_ops <= 0 or not R0 or R0 <= 0 or r <= 0:
        return {"t_star": None, "tv_share": None}
    v0 = (R0 * m0) / r                                   # piso g=0 (owner-FCF/r) = V(T=0)
    if P_ops <= v0:
        return {"t_star": 0.0, "tv_share": 1.0}          # cubierto sin crecimiento → madura
    prev_v, prev_t, prev_tv = v0, 0.0, v0
    for T in range(1, politica.T_MAX_REVERSE + 1):
        V, pv_term = valor_a_T(T, R0, g_D, m0, mj, r, estres=estres)
        if V >= P_ops:
            frac = (P_ops - prev_v) / (V - prev_v) if V > prev_v else 0.0
            return {"t_star": round(prev_t + frac, 2), "tv_share": round(pv_term / P_ops, 3)}
        prev_v, prev_t, prev_tv = V, float(T), pv_term
    return {"t_star": None, "tv_share": None}            # sin raíz → NON_UNDERWRITABLE


@dataclass
class ResultadoReverse:
    ticker: str
    estado: str                                 # COVERED | STRETCH | OPTION_PRICED | NON_UNDERWRITABLE
    t_star: dict = field(default_factory=dict)  # {"P25":.., "P50":.., "P75":..}
    tv_share: dict = field(default_factory=dict)
    g_D: float | None = None
    rev_req: float | None = None                # revenue que el precio exige a T* (falsable vs TAM/líder)
    modelo: str = "default"
    traza: list[str] = field(default_factory=list)


def estado_valuacion_reverse(ticker: str, *, P_ops: float, R0: float, g_D: float, m0: float, r: float,
                             modelo: str = "default", data_state: str = "COVERED",
                             owner_fcf_positivo: bool = True, cap_estado: str | None = None) -> ResultadoReverse:
    """Estado de valuación por reverse-DCF (doc 36 §6). Barre la superficie de margen y pliega en la escalera:
    COVERED se juzga a P25 (conservador), STRETCH a P50, OPTION_PRICED a P75. `estado = peor(growth, data)`.
    `data_state` (tope por cobertura de datos: <3FY→no COVERED, <8q→máx STRETCH, M&A sin bridge→máx OPTION)
    se pasa desde el llamador. COVERED exige además owner-FCF trailing > 0 y TV_share ≤ tope."""
    surf = politica.MARGEN_TERMINAL_MODELO.get(modelo, politica.MARGEN_TERMINAL_MODELO["default"])
    res = ResultadoReverse(ticker=ticker, estado="NON_UNDERWRITABLE", g_D=g_D, modelo=modelo)
    ts = {}
    for p in ("P25", "P50", "P75"):
        r_ts = t_star(P_ops, R0, g_D, m0, surf[p], r)
        ts[p] = r_ts["t_star"]
        res.t_star[p] = r_ts["t_star"]
        res.tv_share[p] = r_ts["tv_share"]

    def _fin(t):  # T* finito y dentro del techo
        return t is not None

    # Escalera con la superficie de margen plegada (doc 36 §6). El guard TV_share (valor mayormente en el
    # terminal lejano = especulativo) NO aplica a T*=0: ahí el terminal ES el piso owner-FCF/r (lo más seguro).
    tv_ok = ts["P25"] == 0.0 or (res.tv_share["P25"] or 0) <= politica.TV_SHARE_MAX_COVERED
    if _fin(ts["P25"]) and ts["P25"] <= politica.UMBRAL_T_COVERED and owner_fcf_positivo and tv_ok:
        growth = "COVERED"
    elif _fin(ts["P50"]) and ts["P50"] <= politica.UMBRAL_T_STRETCH:
        growth = "STRETCH"
    elif _fin(ts["P75"]) and ts["P75"] <= politica.UMBRAL_T_OPTION:
        growth = "OPTION_PRICED"
    else:
        growth = "NON_UNDERWRITABLE"

    res.estado = _peor(growth, data_state)
    if cap_estado is not None:                          # tope de severidad (doc 42 §3): un ESCALANDO sin
        res.estado = _peor(res.estado, cap_estado)      # apalancamiento demostrado NO puede autorizar core
    res.traza = [f"modelo={modelo}", f"g_D={g_D:.1%}", f"T*(P25/P50/P75)={ts['P25']}/{ts['P50']}/{ts['P75']}",
                 f"growth={growth}", f"data={data_state}", f"owner_fcf+={owner_fcf_positivo}",
                 *(["cap=" + cap_estado] if cap_estado else [])]
    # Rev_req a T*_P50 (o el que exista) — para el techo físico (P1, vs TAM/líder).
    t_ref = ts["P50"] if _fin(ts["P50"]) else (ts["P75"] if _fin(ts["P75"]) else ts["P25"])
    if _fin(t_ref):
        R = R0
        for t in range(1, int(t_ref) + 1):
            R *= (1 + crecimiento.fade(g_D, t))
        res.rev_req = round(R, 0)
    return res


def estado_comercial(ticker: str, *, revenue_ttm: float | None, fcf_ttm: float | None,
                     sbc_ttm: float | None, cash: float | None, shares: float | None,
                     precio: float | None, g_D: float | None, modelo: str = "default") -> ResultadoReverse | None:
    """Estado de valuación por reverse-DCF para un nombre COMERCIAL (owner-FCF durable positivo, doc 37 §7).
    Devuelve None si NO es comercial → el llamador usa el path burden/pre-revenue (doc 36 §8). Usa `r_mkt`
    (lente de LECTURA, doc 37), NO el hurdle. owner-FCF = FCF − SBC (doc 36 §0: SBC restado una vez).

    ⚠️ Ruteo v1: usa owner-FCF TTM > 0 como switch. El tri-estado DURABLE (ΣOFCF_3FY>0 ∧ ≥2/3 FY+) de doc 37
    §7 queda diferido (necesita la serie anual de owner-FCF) — el signo puntual es necesario pero no suficiente."""
    owner_fcf = (fcf_ttm or 0.0) - (sbc_ttm or 0.0)
    if not (revenue_ttm and revenue_ttm > 0 and shares and precio and owner_fcf > 0):
        return None                                          # NO comercial → path burden/pre-revenue
    m0 = owner_fcf / revenue_ttm
    P_ops = precio * shares - (cash or 0.0)
    r = politica.r_mkt(modelo)
    return estado_valuacion_reverse(ticker, P_ops=P_ops, R0=revenue_ttm, g_D=g_D or 0.0, m0=m0, r=r,
                                    modelo=modelo, owner_fcf_positivo=True)


def estado_por_ruteo(ticker: str, estado_ruteo: str, *, revenue_ttm: float | None, owner_fcf: float | None,
                     shares: float | None, precio: float | None, cash: float | None, g_D: float | None,
                     modelo: str = "default") -> ResultadoReverse | None:
    """Estado de valuación ROUTER-AWARE (doc 42 §2/§3) — reemplaza el switch crudo owner-FCF>0. El ruteo (4
    estados, `ruteo.rutear`) decide la GRAMÁTICA:
      · COMERCIAL_MADURO   → reverse-DCF as-is (owner-FCF>0, margen demostrado).
      · COMERCIAL_ESCALANDO→ reverse-DCF con m0 ACTUAL (puede ser negativo, NO se borra) + superficie de margen
        madura, pero **capado a OPTION_PRICED** (doc 42 §3: sin apalancamiento demostrado autoriza probe, NO core;
        el good-loser es probe hasta que prueba la economía). ⚠️ La valuación §3 fina (locus∩hull + superficie τ)
        queda pendiente; este es el interim honesto (mejor que caer a burden = sin valuación).
      · PRE_REVENUE_BINARIO / BURDEN → None (path binario/burden, no comercial)."""
    if not (revenue_ttm and revenue_ttm > 0 and shares and precio):
        return None
    m0 = (owner_fcf or 0.0) / revenue_ttm
    P_ops = precio * shares - (cash or 0.0)
    r = politica.r_mkt(modelo)
    if estado_ruteo == "COMERCIAL_MADURO":
        return estado_valuacion_reverse(ticker, P_ops=P_ops, R0=revenue_ttm, g_D=g_D or 0.0, m0=m0, r=r,
                                        modelo=modelo, owner_fcf_positivo=(owner_fcf or 0) > 0)
    if estado_ruteo == "COMERCIAL_ESCALANDO":
        return estado_valuacion_reverse(ticker, P_ops=P_ops, R0=revenue_ttm, g_D=g_D or 0.0, m0=m0, r=r,
                                        modelo=modelo, owner_fcf_positivo=False, cap_estado="OPTION_PRICED")
    return None                                              # PRE_REVENUE_BINARIO / BURDEN → no comercial
