"""Orquestador de decisión (v2 Fase 4, doc 55 §4) — el capstone de la capa de decisión.

Une PM → **gate duro del IPS** → **Auditor** → **ledger**. Desacoplado del PM: recibe una `PMDecision` ya
emitida + el contexto mecánico, así es testeable y el runner semanal cablea `pm.decidir() → procesar()`.

Principio del gate (doc 55 §4.1/§4.7 + auditoría externa 2026-10-27):
- **Las REDUCCIONES (vender/recortar/bajar peso) SIEMPRE se ejecutan** — en risk-off la velocidad importa;
  nunca las bloquea una violación agregada ni la admisibilidad.
- El gate DURO aplica **solo a lo que agrega riesgo** (abrir/aumentar):
  - `admisibilidad` (market cap / ADV fuera de rango) → NO se abre/aumenta ese nombre; una tenencia que ya
    quedó inadmisible se **ALERTA, nunca se vende a la fuerza**.
  - cap por nombre: un aumento se recorta al cap (estricto); una posición EXISTENTE que derivó sobre el cap
    se recorta solo si supera el cap + banda (evita churn por drift de precio).
  - flag de supervivencia NO resuelto → el aumento se topea a `cap_flag_supervivencia` (doc 55 §4.5).
  - violación `agregada` (sector/cuello/caja/ops/turnover) → el código NO elige qué recortar → **NO_ACTION
    sobre los aumentos** (se caen todos); las reducciones ya aplicadas quedan.
- `operar_ahora=False` → no se ejecuta nada (se registra la intención).
- `max_ops_semana` se cuenta por **semana calendario** desde el ledger (no por decisión); `turnover_max_semana`
  = suma de |Δpeso| de la decisión.

El ledger es por ACCIÓN; la auditoría es por DECISIÓN → las objeciones se anclan a la primera acción.
La ejecución efectiva (aplicar `pesos_finales`, honrar `demoradas`) es del paper nuevo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.agentes.auditor import Auditor
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.schemas import AuditReport, PMDecision

_AUMENTOS = {"comprar", "aumentar"}
_REDUCCIONES = {"vender", "recortar"}
_OPS_QUE_MUEVEN = _AUMENTOS | _REDUCCIONES


def aplicar_decision(cartera_actual: dict[str, float], acciones) -> dict[str, float]:
    """Cartera-objetivo NAIVE (pre-gate), para reporte: cada acción fija el `peso_objetivo` de su nombre;
    vender/caja lo sacan; los no mencionados quedan como están. Caja = 1 − suma."""
    pesos = {t.upper(): w for t, w in cartera_actual.items() if w > 0}
    for a in acciones:
        tk = a.ticker.upper()
        if a.accion in ("vender", "caja") or a.peso_objetivo <= 0:
            pesos.pop(tk, None)
        else:
            pesos[tk] = a.peso_objetivo
    return {t: w for t, w in pesos.items() if w > 0}


def _inadmisible(ctx: ContextoTicker | None, ips: IPS) -> bool:
    """¿El nombre viola admisibilidad mecánica (market cap fuera de rango / ADV bajo)?"""
    if ctx is None:
        return False
    mc_min = float(ips.cfg.get("market_cap_min_usd", 0.0))
    mc_max = float(ips.cfg.get("market_cap_max_usd", 1e18))
    adv_min = float(ips.cfg.get("adv_min_usd", 0.0))
    if ctx.market_cap is not None and not (mc_min <= ctx.market_cap <= mc_max):
        return True
    if ctx.adv_usd is not None and ctx.adv_usd < adv_min:
        return True
    return False


@dataclass
class ResultadoDecision:
    pesos_objetivo: dict[str, float]           # cartera-objetivo naive del PM (pre-gate)
    pesos_finales: dict[str, float]            # post-gate (lo que ejecuta el paper)
    caja_final: float
    clip: str                                  # none | local_simple | agregada
    no_action: bool                            # True si los aumentos se cayeron por violación agregada
    auditoria: AuditReport | None = None
    demoradas: list[str] = field(default_factory=list)   # aumentos demorados 1 ciclo por objeción alta
    alertas: list[str] = field(default_factory=list)     # p.ej. tenencia inadmisible (no se vende), no-opera
    decision_ids: list[str] = field(default_factory=list)


class OrquestadorDecision:
    def __init__(self, ips: IPS, ledger: LedgerDecisiones, auditor: Auditor | None = None):
        self.ips = ips
        self.ledger = ledger
        self.auditor = auditor

    def procesar(self, decision: PMDecision, *, cartera_actual: dict[str, float], caja_actual: float,
                 contexto: dict[str, ContextoTicker], ciclo: str, hoy: date | None = None,
                 precios: dict[str, float] | None = None,
                 dossier_hash_por_ticker: dict[str, str] | None = None,
                 verif_por_ticker: dict[str, str] | None = None,
                 flags_por_ticker: dict[str, list[str]] | None = None,
                 memo_macro: str = "") -> ResultadoDecision:
        hoy = hoy or date.today()
        cartera = {t.upper(): w for t, w in cartera_actual.items() if w > 0}
        precios = {t.upper(): p for t, p in (precios or {}).items()}
        hashes = {t.upper(): h for t, h in (dossier_hash_por_ticker or {}).items()}
        verifs = {t.upper(): v for t, v in (verif_por_ticker or {}).items()}
        flags = {t.upper(): list(f) for t, f in (flags_por_ticker or {}).items()}
        objetivo = aplicar_decision(cartera, decision.acciones)

        # operar_ahora=False → no se ejecuta nada (se registra la intención).
        if not decision.operar_ahora:
            res = ResultadoDecision(pesos_objetivo=objetivo, pesos_finales=dict(cartera),
                                    caja_final=caja_actual, clip="none", no_action=False,
                                    alertas=["PM no opera ahora (operar_ahora=False)"])
            self._auditar_y_registrar(res, decision, cartera, caja_actual, contexto, ciclo, precios,
                                      hashes, verifs, memo_macro, viol=[])
            return res

        # 1. Reducciones primero (SIEMPRE se aplican); juntar aumentos aparte.
        pesos = dict(cartera)
        aumentos: dict[str, float] = {}
        alertas: list[str] = []
        clip_local = False
        for a in decision.acciones:
            tk = a.ticker.upper()
            cur = cartera.get(tk, 0.0)
            tgt = 0.0 if a.accion in ("vender", "caja") else a.peso_objetivo
            if a.accion in _REDUCCIONES or tgt < cur - 1e-9:
                pesos.pop(tk, None) if tgt <= 0 else pesos.__setitem__(tk, tgt)
            elif a.accion in _AUMENTOS or tgt > cur + 1e-9:
                aumentos[tk] = tgt
            # else: mantener al mismo peso → sin cambio
        pesos_tras_reduccion = {t: w for t, w in pesos.items() if w > 0}

        # 2. Clip de AUMENTOS: admisibilidad (no abrir inadmisible) + cap local (estricto) + flag supervivencia.
        peso_max = float(self.ips.cfg.get("peso_max_nombre", 1.0))
        cap_flag = float(self.ips.cfg.get("cap_flag_supervivencia", peso_max))
        candidato = dict(pesos_tras_reduccion)
        for tk, tgt in aumentos.items():
            if _inadmisible(contexto.get(tk), self.ips):
                alertas.append(f"{tk}: inadmisible (market cap/ADV) — no se abre/aumenta")
                continue
            tope = peso_max
            if _flag_no_resuelto(tk, flags.get(tk, []), decision.respuestas_flags):
                tope = min(tope, cap_flag)
                alertas.append(f"{tk}: flag de supervivencia no resuelto → tope {tope:.0%}")
            if tgt > tope + 1e-9:
                tgt, clip_local = tope, True
            candidato[tk] = tgt

        # 3. Trim por DRIFT de posiciones existentes (banda) — mecánico, es reducción.
        banda = float(self.ips.cfg.get("banda_peso_existente", 0.03))
        for tk, w in list(candidato.items()):
            if tk not in aumentos and w > peso_max + banda + 1e-9:
                candidato[tk], clip_local = peso_max, True
        candidato = {t: w for t, w in candidato.items() if w > 0}

        # 4. Gate AGREGADO sobre el candidato (solo bloquea aumentos). ops por semana calendario + turnover.
        caja_cand = round(1.0 - sum(candidato.values()), 6)
        ops_dec = sum(1 for a in decision.acciones if a.accion in _OPS_QUE_MUEVEN)
        ops_semana = self.ledger.ops_en_semana(hoy) + ops_dec
        turnover = sum(abs(candidato.get(t, 0.0) - cartera.get(t, 0.0))
                       for t in set(candidato) | set(cartera))
        viol = self.ips.validar(candidato, contexto, caja=caja_cand, ops_semana=ops_semana, turnover=turnover)
        aumentos_efectivos = {tk for tk in aumentos
                              if candidato.get(tk, 0.0) > pesos_tras_reduccion.get(tk, 0.0) + 1e-9}

        if aumentos_efectivos and IPS.hay_agregada(viol):  # NO_ACTION sobre los aumentos; las reducciones quedan
            res = ResultadoDecision(pesos_objetivo=objetivo, pesos_finales=pesos_tras_reduccion,
                                    caja_final=round(1.0 - sum(pesos_tras_reduccion.values()), 6),
                                    clip="agregada", no_action=True, alertas=alertas)
        else:
            res = ResultadoDecision(pesos_objetivo=objetivo, pesos_finales=candidato, caja_final=caja_cand,
                                    clip="local_simple" if clip_local else "none", no_action=False,
                                    alertas=alertas)

        # Alertas por tenencia EXISTENTE inadmisible (1a: se avisa, NO se vende).
        for tk in res.pesos_finales:
            if tk in cartera and _inadmisible(contexto.get(tk), self.ips):
                res.alertas.append(f"{tk}: posición existente quedó inadmisible (market cap/ADV) — "
                                   f"ALERTA al PM, no se vende a la fuerza")

        self._auditar_y_registrar(res, decision, cartera, caja_actual, contexto, ciclo, precios,
                                  hashes, verifs, memo_macro, viol=viol)
        return res

    def _auditar_y_registrar(self, res, decision, cartera, caja_actual, contexto, ciclo, precios,
                             hashes, verifs, memo_macro, *, viol) -> None:
        if self.auditor is not None:
            res.auditoria = self.auditor.auditar(
                decision, cartera_actual=cartera, caja_actual=caja_actual,
                memo_macro=memo_macro, verif_por_ticker=verifs, ips_violaciones=viol)
            if any(o.severidad == "alta" for o in res.auditoria.objeciones):
                res.demoradas = [a.ticker.upper() for a in decision.acciones if a.accion in _AUMENTOS]

        for i, a in enumerate(decision.acciones):
            tk = a.ticker.upper()
            resultante = res.pesos_finales.get(tk, 0.0)
            self._id_append(res, self.ledger.registrar_decision(
                a.model_copy(update={"dossier_hash": hashes.get(tk, a.dossier_hash)}),
                ciclo=ciclo, peso_resultante=resultante, clip=res.clip,
                precio=precios.get(tk), verif_veredicto=verifs.get(tk), ips_hash=self.ips.hash(),
                prompt_version=decision.meta.prompt_version, model=decision.meta.model,
                auditoria=res.auditoria if i == 0 else None))

    @staticmethod
    def _id_append(res: ResultadoDecision, did: str) -> None:
        res.decision_ids.append(did)


def _flag_no_resuelto(ticker: str, flags: list[str], respuestas) -> bool:
    """¿La empresa tiene un flag de supervivencia que el PM NO resolvió? Resuelto = hay una `RespuestaFlag`
    para ese flag con acción distinta de `no_opera` (refutó o lo aceptó como riesgo; doc 55 §4.5)."""
    if not flags:
        return False
    resueltos = {r.flag_id for r in respuestas if getattr(r, "accion", None) != "no_opera"}
    for f in flags:
        if f"{ticker}:{f}" not in resueltos and f not in resueltos:
            return True
    return False
