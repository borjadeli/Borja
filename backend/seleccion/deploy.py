"""Deploy de un mix aprobado al ledger fiel (Etapa 6).

Convierte pesos objetivo en fills reales de acciones ENTERAS (Art. 11).

Ajustes tras revisión externa (AI 1 + AI 2):
  - **floor** (no round) → nunca supera el peso objetivo / hard cap;
  - **fail-closed** si falta precio de una posición viva o de un nombre del mix
    (un precio faltante corrompe el equity, que es el denominador de todos los targets);
  - **barrera**: si una venta necesaria no se completa, NO se compra;
  - guard de caja envuelve TODOS los fills (venta de producido neto negativo no se ejecuta);
  - cap de ADV como límite duro: fail-closed si falta ADV, presupuesto diario ACUMULADO;
  - **validación post-trade**: se corre el validador sobre los pesos EJECUTADOS y se
    reportan las violaciones (residuales por venta truncada, overage por costos, etc.);
  - `truncadas` reportadas (target vs ejecutado); orden determinista.
"""
from __future__ import annotations

import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ledger.core import proyectar, registrar_fill
from backend.ledger.models import NxFill


def _fin_pos(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def _operadas_hoy(session: Session, ticker: str, fecha: date) -> float:
    return sum(f.shares for f in session.execute(
        select(NxFill).where(NxFill.ticker == ticker.upper(), NxFill.fecha_fill == fecha)
    ).scalars())


def desplegar(session: Session, *, mix: dict, precios: dict, fecha: date,
              adv_usd: dict | None = None, participacion_adv: float = 0.15,
              slippage_bps: float = 25.0, comision_por_accion: float = 0.005,
              comision_min: float = 1.0, candidatas: list | None = None,
              cash_objetivo: float | None = None) -> dict:
    """Lleva la cartera hacia `mix` (dict ticker->peso). Devuelve {completo,
    pendientes, truncadas, ventas, compras, cash, invertido, equity,
    violaciones_post}. Si se pasan `candidatas` + `cash_objetivo`, valida los pesos
    ejecutados (post-trade)."""
    if not (math.isfinite(participacion_adv) and 0.0 <= participacion_adv <= 1.0):
        raise ValueError(f"participacion_adv inválida: {participacion_adv}")

    precios = {k.upper(): v for k, v in precios.items()}
    mix_peso = {k.upper(): v for k, v in mix.items()}
    enforce_adv = adv_usd is not None
    adv_usd = {k.upper(): v for k, v in (adv_usd or {}).items()}
    slip = slippage_bps / 10_000.0

    est = proyectar(session, precios)
    pos = est["posiciones"]

    # Fail-closed: toda posición viva o nombre del mix con peso>0 debe tener precio válido
    # (si no, el equity queda mal y corre toda la cartera).
    requeridos = set(pos) | {t for t, w in mix_peso.items() if w > 0}
    faltan = sorted(t for t in requeridos if not _fin_pos(precios.get(t)))
    if faltan:
        raise ValueError(f"precios faltantes/inválidos para: {faltan}")

    equity = est["equity"]
    pendientes: list[dict] = []
    truncadas: list[dict] = []
    bloquear = False
    ventas_ord: list[tuple] = []
    compras_ord: list[tuple] = []

    for t in sorted(set(mix_peso) | set(pos)):
        precio = precios.get(t)
        if not _fin_pos(precio):
            continue   # nombre del mix con peso 0 y sin tenencia → no requiere precio
        cur = int(pos[t].shares) if t in pos else 0
        target_shares = math.floor(mix_peso.get(t, 0.0) * equity / precio)   # long-only, floor
        delta = target_shares - cur
        if delta == 0:
            continue
        if enforce_adv:
            adv = adv_usd.get(t)
            if not _fin_pos(adv):
                pendientes.append({"ticker": t, "motivo": "ADV faltante"})
                if delta < 0:
                    bloquear = True
                continue
            eff = precio * (1 + slip) if delta > 0 else precio * (1 - slip)
            restante = participacion_adv * adv - _operadas_hoy(session, t, fecha) * eff
            max_sh = max(0, int(restante / eff))
            if abs(delta) > max_sh:
                truncadas.append({"ticker": t, "target_sh": abs(delta), "ejecutado_sh": max_sh,
                                  "motivo": "cap de ADV"})
                if delta < 0:
                    bloquear = True
                delta = max_sh if delta > 0 else -max_sh
        if delta < 0:
            ventas_ord.append((t, -delta, precio))
        elif delta > 0:
            compras_ord.append((t, delta, precio))

    ventas, compras = [], []

    def _fill(t, n, precio, lado):
        eff = precio * (1 + slip) if lado == "buy" else precio * (1 - slip)
        comision = max(comision_min, comision_por_accion * n)
        registrar_fill(session, ticker=t, lado=lado, shares=n, precio=eff,
                       comision=comision, slippage_bps=slippage_bps, fecha_fill=fecha)
        (compras if lado == "buy" else ventas).append({"ticker": t, "shares": n, "precio": eff})

    # --- Ventas (el guard de caja también las cubre) ---
    for t, n, precio in sorted(ventas_ord, key=lambda o: o[0]):
        eff = precio * (1 - slip)
        neto = n * eff - max(comision_min, comision_por_accion * n)
        if neto < 0:
            pendientes.append({"ticker": t, "motivo": "venta de producido neto negativo"})
            bloquear = True
            continue
        _fill(t, n, precio, "sell")

    completo = not bloquear
    if completo:
        for t, n, precio in sorted(compras_ord, key=lambda o: o[0]):
            eff = precio * (1 + slip)
            peso_obj = mix_peso.get(t, 0.0)
            snap = proyectar(session, precios)
            cash, eq = snap["caja"], snap["equity"]
            cur = snap["posiciones"][t].shares if t in snap["posiciones"] else 0.0

            def _costo(k, eff=eff): return k * eff + max(comision_min, comision_por_accion * k)
            def _peso_post(k, cur=cur, precio=precio, eq=eq, eff=eff):
                # equity POST-costos: el drag de ejecución achica el equity → sube el peso.
                drag = k * (eff - precio) + max(comision_min, comision_por_accion * k)
                eq_new = eq - drag
                return ((cur + k) * precio) / eq_new if eq_new > 0 else 1.0

            objetivo = n
            while n > 0 and (_costo(n) > cash or _peso_post(n) > peso_obj + 1e-9):
                n -= 1
            if n < objetivo:
                truncadas.append({"ticker": t, "target_sh": objetivo, "ejecutado_sh": n,
                                  "motivo": "caja / peso objetivo"})
            if n > 0:
                _fill(t, n, precio, "buy")
    else:
        for t, n, precio in compras_ord:
            pendientes.append({"ticker": t, "motivo": "compra bloqueada por venta incompleta"})

    final = proyectar(session, precios)
    resultado = {"completo": completo, "pendientes": pendientes, "truncadas": truncadas,
                 "ventas": ventas, "compras": compras, "cash": final["caja"],
                 "invertido": final["valor_posiciones"], "equity": final["equity"]}

    # --- Validación post-trade: el validador sobre los pesos EJECUTADOS ---
    if candidatas is not None and cash_objetivo is not None:
        from backend.seleccion.validador import LineaPropuesta, validar_propuesta
        eq = final["equity"]
        pesos = [LineaPropuesta(t, p.shares * precios[t] / eq)
                 for t, p in final["posiciones"].items() if eq > 0 and t in precios]
        chk = validar_propuesta(pesos, candidatas, cash_objetivo=cash_objetivo)
        resultado["violaciones_post"] = chk["errores"]

    return resultado
