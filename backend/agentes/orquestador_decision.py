"""Orquestador de decisión (v2 Fase 4, doc 55 §4) — el capstone de la capa de decisión.

Une PM → **gate duro del IPS** → **Auditor** → **ledger**. Desacoplado del PM: recibe una `PMDecision` ya
emitida + el contexto mecánico, así es testeable y el runner semanal cablea `pm.decidir() → procesar()`.

Gate (doc 55 §4.1/§4.3):
- `local_simple` (peso por nombre sobre el cap, market cap / ADV inadmisible) → **recorte mecánico**: el
  nombre se recorta a su cap (o a 0 si es inadmisible) y el excedente va a **cash, sin redistribuir**.
  Se marca `clip="local_simple"`.
- `agregada` (sector/cuello/caja/ops) → el código NO elige qué recortar → **NO_ACTION** (la decisión no se
  ejecuta; se registra con `clip="agregada"`). La "1 re-propuesta" explícita se difiere: el dry-run del IPS
  ya fue la segunda chance del PM.

Auditor (doc 55 §4.4): objeta sin vetar. Objeción de **severidad alta** cuando hay un **aumento** (comprar/
aumentar) → esos aumentos quedan **demorados 1 ciclo** (no se ejecutan ahora; no es bloqueo). Las objeciones
quedan en el ledger como predicciones falsables.

El ledger es por ACCIÓN y la auditoría es por DECISIÓN → las objeciones se anclan a la primera acción
registrada (coarse, anotado). La ejecución efectiva (aplicar `pesos_finales`, honrar `demoradas`) es del
paper nuevo, que se reescribe después.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.agentes.auditor import Auditor
from backend.agentes.ips import IPS, ContextoTicker
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.schemas import AuditReport, PMDecision

_OPS_QUE_MUEVEN = {"comprar", "vender", "aumentar", "recortar"}
_AUMENTOS = {"comprar", "aumentar"}


def aplicar_decision(cartera_actual: dict[str, float], acciones) -> dict[str, float]:
    """Cartera-objetivo resultante (pre-clip): cada acción fija el `peso_objetivo` de su nombre; vender/caja
    lo sacan; los nombres no mencionados quedan como están. Caja = 1 − suma."""
    pesos = {t.upper(): w for t, w in cartera_actual.items() if w > 0}
    for a in acciones:
        tk = a.ticker.upper()
        if a.accion in ("vender", "caja") or a.peso_objetivo <= 0:
            pesos.pop(tk, None)
        else:
            pesos[tk] = a.peso_objetivo
    return {t: w for t, w in pesos.items() if w > 0}


def _clip_local(pesos: dict[str, float], contexto: dict[str, ContextoTicker], ips: IPS) -> tuple[dict[str, float], bool]:
    """Recorte mecánico de violaciones local_simple: nombre > cap → cap; market cap / ADV inadmisible → 0.
    El excedente NO se redistribuye (queda como cash). Devuelve (pesos_clip, hubo_clip)."""
    peso_max = float(ips.cfg.get("peso_max_nombre", 1.0))
    mc_min = float(ips.cfg.get("market_cap_min_usd", 0.0))
    mc_max = float(ips.cfg.get("market_cap_max_usd", 1e18))
    adv_min = float(ips.cfg.get("adv_min_usd", 0.0))
    out: dict[str, float] = {}
    hubo = False
    for tk, w in pesos.items():
        ctx = contexto.get(tk)
        if ctx is not None:
            if (ctx.market_cap is not None and not (mc_min <= ctx.market_cap <= mc_max)) or \
               (ctx.adv_usd is not None and ctx.adv_usd < adv_min):
                hubo = True
                continue                                  # inadmisible → fuera (peso 0)
        if w > peso_max + 1e-9:
            out[tk] = peso_max
            hubo = True
        else:
            out[tk] = w
    return {t: w for t, w in out.items() if w > 0}, hubo


@dataclass
class ResultadoDecision:
    pesos_objetivo: dict[str, float]           # cartera-objetivo del PM (pre-clip)
    pesos_finales: dict[str, float]            # post-clip (vacío/igual a actual si NO_ACTION)
    caja_final: float
    clip: str                                  # none | local_simple | agregada
    no_action: bool                            # True si hubo violación agregada irresoluble
    auditoria: AuditReport | None = None
    demoradas: list[str] = field(default_factory=list)   # aumentos demorados 1 ciclo por objeción alta
    decision_ids: list[str] = field(default_factory=list)


class OrquestadorDecision:
    def __init__(self, ips: IPS, ledger: LedgerDecisiones, auditor: Auditor | None = None):
        self.ips = ips
        self.ledger = ledger
        self.auditor = auditor

    def procesar(self, decision: PMDecision, *, cartera_actual: dict[str, float], caja_actual: float,
                 contexto: dict[str, ContextoTicker], ciclo: str,
                 precios: dict[str, float] | None = None,
                 dossier_hash_por_ticker: dict[str, str] | None = None,
                 verif_por_ticker: dict[str, str] | None = None,
                 memo_macro: str = "") -> ResultadoDecision:
        cartera_actual = {t.upper(): w for t, w in cartera_actual.items()}
        precios = {t.upper(): p for t, p in (precios or {}).items()}
        hashes = {t.upper(): h for t, h in (dossier_hash_por_ticker or {}).items()}
        verifs = {t.upper(): v for t, v in (verif_por_ticker or {}).items()}

        objetivo = aplicar_decision(cartera_actual, decision.acciones)
        caja_obj = round(1.0 - sum(objetivo.values()), 6)
        ops = sum(1 for a in decision.acciones if a.accion in _OPS_QUE_MUEVEN)
        viol = self.ips.validar(objetivo, contexto, caja=caja_obj, ops_semana=ops)

        if IPS.hay_agregada(viol):                        # el código no elige qué recortar → NO_ACTION
            res = ResultadoDecision(pesos_objetivo=objetivo, pesos_finales=dict(cartera_actual),
                                    caja_final=caja_actual, clip="agregada", no_action=True)
        else:
            finales, hubo = _clip_local(objetivo, contexto, self.ips)
            res = ResultadoDecision(pesos_objetivo=objetivo, pesos_finales=finales,
                                    caja_final=round(1.0 - sum(finales.values()), 6),
                                    clip="local_simple" if hubo else "none", no_action=False)

        # Auditor (sin veto) + regla de demora de aumentos ante objeción alta.
        if self.auditor is not None:
            res.auditoria = self.auditor.auditar(
                decision, cartera_actual=cartera_actual, caja_actual=caja_actual,
                memo_macro=memo_macro, verif_por_ticker=verifs, ips_violaciones=viol)
            if any(o.severidad == "alta" for o in res.auditoria.objeciones):
                res.demoradas = [a.ticker.upper() for a in decision.acciones if a.accion in _AUMENTOS]

        # Ledger (append-only). Objeciones ancladas a la primera acción (coarse, anotado).
        for i, a in enumerate(decision.acciones):
            tk = a.ticker.upper()
            resultante = cartera_actual.get(tk, 0.0) if res.no_action else res.pesos_finales.get(tk, 0.0)
            did = self.ledger.registrar_decision(
                a.model_copy(update={"dossier_hash": hashes.get(tk, a.dossier_hash)}),
                ciclo=ciclo, peso_resultante=resultante, clip=res.clip,
                precio=precios.get(tk), verif_veredicto=verifs.get(tk), ips_hash=self.ips.hash(),
                prompt_version=decision.meta.prompt_version, model=decision.meta.model,
                auditoria=res.auditoria if i == 0 else None)
            res.decision_ids.append(did)
        return res
