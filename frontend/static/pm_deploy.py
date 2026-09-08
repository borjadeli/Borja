"""Deploy de un mix aprobado al ledger fiel (Etapa 6).

Convierte pesos objetivo en **fills reales** de acciones enteras sobre el ledger
(Art. 11): ventas antes que compras (§7.4), fill a un precio dado (el caller lo
setea a apertura+30′), con slippage + comisión, respetando el **cap de participación
sobre ADV** y sin dejar la caja en negativo. Determinista; testeable con datos
inyectados.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.ledger.core import proyectar, registrar_fill


def desplegar(session: Session, *, mix: dict, precios: dict, fecha: date,
              adv_usd: dict | None = None, participacion_adv: float = 0.15,
              slippage_bps: float = 25.0, comision_por_accion: float = 0.005,
              comision_min: float = 1.0) -> dict:
    """Lleva la cartera hacia `mix` (dict ticker->peso). Un ticker con peso 0 o
    ausente se vende a cero. Devuelve {ventas, compras, cash, invertido, equity}.
    """
    precios = {k.upper(): v for k, v in precios.items()}
    adv_usd = {k.upper(): v for k, v in (adv_usd or {}).items()}
    mix_peso = {k.upper(): v for k, v in mix.items()}

    est = proyectar(session, precios)
    equity = est["equity"]
    pos = est["posiciones"]

    # ---- Calcular órdenes (delta a target, en acciones enteras) ----
    ordenes: list[tuple[str, int, float]] = []
    for t in set(mix_peso) | set(pos):
        precio = precios.get(t)
        if not precio or precio <= 0:
            continue  # sin precio válido no se opera
        target_val = mix_peso.get(t, 0.0) * equity
        cur_shares = pos[t].shares if t in pos else 0.0
        delta_sh = round((target_val - cur_shares * precio) / precio)
        if delta_sh == 0:
            continue
        # Cap de participación sobre ADV.
        adv = adv_usd.get(t)
        if adv and adv > 0:
            max_sh = int(participacion_adv * adv / precio)
            if abs(delta_sh) > max_sh:
                delta_sh = max_sh if delta_sh > 0 else -max_sh
        if delta_sh != 0:
            ordenes.append((t, delta_sh, precio))

    ordenes.sort(key=lambda o: o[1])   # negativas (ventas) primero
    ventas, compras = [], []

    def _fill(t, n, precio, lado):
        eff = precio * (1 + slippage_bps / 10_000) if lado == "buy" else precio * (1 - slippage_bps / 10_000)
        comision = max(comision_min, comision_por_accion * n)
        registrar_fill(session, ticker=t, lado=lado, shares=n, precio=eff,
                       comision=comision, slippage_bps=slippage_bps, fecha_fill=fecha)
        (compras if lado == "buy" else ventas).append({"ticker": t, "shares": n, "precio": eff})

    for t, sh, precio in ordenes:
        if sh < 0:
            _fill(t, abs(sh), precio, "sell")

    for t, sh, precio in ordenes:
        if sh <= 0:
            continue
        n = sh
        # Guard de caja: no dejar la caja en negativo (compra parcial si hace falta).
        cash = proyectar(session, precios)["caja"]
        eff = precio * (1 + slippage_bps / 10_000)

        def _costo(k: int) -> float:
            return k * eff + max(comision_min, comision_por_accion * k)

        if _costo(n) > cash:
            n = int(cash / (eff + comision_por_accion))   # estimación con comisión por acción
            while n > 0 and _costo(n) > cash:
                n -= 1
        if n > 0:
            _fill(t, n, precio, "buy")

    final = proyectar(session, precios)
    return {"ventas": ventas, "compras": compras, "cash": final["caja"],
            "invertido": final["valor_posiciones"], "equity": final["equity"]}
