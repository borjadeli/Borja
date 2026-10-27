"""Orquestador de decisión (v2 Fase 4, doc 55 §4) — el capstone de la capa de decisión.

Une PM → **gate duro del IPS** → **Auditor** → **ledger**. Desacoplado del PM: recibe una `PMDecision` ya
emitida + el contexto mecánico (el runner cablea `pm.decidir() → procesar()`).

Principio del gate (doc 55 §4 + auditoría externa 2026-10-27, r1 y r2):
- **Las REDUCCIONES (vender/recortar/bajar peso) SIEMPRE se ejecutan** (risk-off; nunca las bloquea nada).
- El gate DURO aplica solo a lo que AGREGA riesgo (abrir/aumentar):
  - admisibilidad (market cap/ADV) → no se abre/aumenta; una tenencia ya inadmisible se ALERTA, no se vende.
  - cap por nombre: aumento recortado al cap (estricto); existente sobre el cap solo con banda (drift).
  - flag de supervivencia no resuelto → aumento topeado a `cap_flag_supervivencia`.
  - violación AGREGADA de grupo (sector/cuello) → bloquea SOLO los aumentos que empeoran ESE grupo (1c);
    violación global (caja/ops/turnover/max_pos) → bloquea todos los aumentos restantes.
  - lo bloqueado se devuelve al PM UNA vez con la holgura exacta (`repropuesta_fn`); si no hay re-propuesta
    válida → NO_ACTION sobre esos aumentos (1d). Las reducciones ya aplicadas quedan.
- `max_ops_semana` = SESIONES con ops ejecutadas por semana calendario (1a); `turnover` = ROTACIÓN =
  compras financiadas con ventas = min(Σaumentos, Σreducciones) (1b, el despliegue desde caja no cuenta).
- `operar_ahora=False` → no se ejecuta nada y NO se llama al Auditor (6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.agentes.auditor import Auditor
from backend.agentes.ips import IPS, ContextoTicker, Violacion
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.schemas import AuditReport, PMDecision

_AUMENTOS = {"comprar", "aumentar"}
_REDUCCIONES = {"vender", "recortar"}
_OPS_QUE_MUEVEN = _AUMENTOS | _REDUCCIONES
_GRUPO_REGLAS = {"max_por_sector", "max_por_cuello"}


def aplicar_decision(cartera_actual: dict[str, float], acciones) -> dict[str, float]:
    """Cartera-objetivo NAIVE (pre-gate), para reporte."""
    pesos = {t.upper(): w for t, w in cartera_actual.items() if w > 0}
    for a in acciones:
        tk = a.ticker.upper()
        if a.accion in ("vender", "caja") or a.peso_objetivo <= 0:
            pesos.pop(tk, None)
        else:
            pesos[tk] = a.peso_objetivo
    return {t: w for t, w in pesos.items() if w > 0}


def _inadmisible(ctx: ContextoTicker | None, ips: IPS) -> bool:
    if ctx is None:
        return False
    mc_min = float(ips.cfg.get("market_cap_min_usd", 0.0))
    mc_max = float(ips.cfg.get("market_cap_max_usd", 1e18))
    adv_min = float(ips.cfg.get("adv_min_usd", 0.0))
    if ctx.market_cap is not None and not (mc_min <= ctx.market_cap <= mc_max):
        return True
    return ctx.adv_usd is not None and ctx.adv_usd < adv_min


def _rotacion(cartera: dict[str, float], finales: dict[str, float]) -> float:
    """Rotación = compras financiadas con ventas = min(Σaumentos, Σreducciones). El despliegue neto desde
    caja (aumentos sin ventas que los financien) NO cuenta como rotación (auditoría r2 1b)."""
    tk = set(cartera) | set(finales)
    incr = sum(max(0.0, finales.get(t, 0.0) - cartera.get(t, 0.0)) for t in tk)
    decr = sum(max(0.0, cartera.get(t, 0.0) - finales.get(t, 0.0)) for t in tk)
    return round(min(incr, decr), 6)


def _grupos_excedidos(pesos: dict[str, float], contexto: dict[str, ContextoTicker],
                      ips: IPS) -> tuple[set[str], set[str], list[Violacion]]:
    """Sectores y cuellos que superan su cap en `pesos`. Devuelve (sectores_over, cuellos_over, holguras)."""
    cap_s, cap_c = float(ips.cfg.get("max_por_sector", 1.0)), float(ips.cfg.get("max_por_cuello", 1.0))
    acc_s: dict[str, float] = {}
    acc_c: dict[str, float] = {}
    for tk, w in pesos.items():
        ctx = contexto.get(tk)
        if ctx and ctx.sector:
            acc_s[ctx.sector] = acc_s.get(ctx.sector, 0.0) + w
        if ctx and ctx.cuello:
            acc_c[ctx.cuello] = acc_c.get(ctx.cuello, 0.0) + w
    sec = {s for s, v in acc_s.items() if v > cap_s + 1e-9}
    cue = {c for c, v in acc_c.items() if v > cap_c + 1e-9}
    holg = [Violacion("max_por_sector", f"sector={s}: {acc_s[s]:.1%} > {cap_s:.0%}",
                      round(cap_s - acc_s[s], 6), "agregada") for s in sec]
    holg += [Violacion("max_por_cuello", f"cuello={c}: {acc_c[c]:.1%} > {cap_c:.0%}",
                       round(cap_c - acc_c[c], 6), "agregada") for c in cue]
    return sec, cue, holg


@dataclass
class ResultadoDecision:
    pesos_objetivo: dict[str, float]
    pesos_finales: dict[str, float]
    caja_final: float
    clip: str                                  # none | local_simple | agregada
    no_action: bool                            # True si cayeron aumentos (agregado)
    auditoria: AuditReport | None = None
    demoradas: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    holguras: list[Violacion] = field(default_factory=list)   # para la re-propuesta del PM
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
                 memo_macro: str = "", repropuesta_fn=None) -> ResultadoDecision:
        hoy = hoy or date.today()
        cartera = {t.upper(): w for t, w in cartera_actual.items() if w > 0}
        precios = {t.upper(): p for t, p in (precios or {}).items()}
        hashes = {t.upper(): h for t, h in (dossier_hash_por_ticker or {}).items()}
        verifs = {t.upper(): v for t, v in (verif_por_ticker or {}).items()}
        flags = {t.upper(): list(f) for t, f in (flags_por_ticker or {}).items()}

        # operar_ahora=False → no se ejecuta nada; NO se llama al Auditor (item 6).
        if not decision.operar_ahora:
            res = ResultadoDecision(pesos_objetivo=aplicar_decision(cartera, decision.acciones),
                                    pesos_finales=dict(cartera), caja_final=caja_actual, clip="none",
                                    no_action=False, alertas=["PM no opera ahora (operar_ahora=False)"])
            self._registrar(res, decision, cartera, precios, hashes, verifs, ciclo)
            return res

        res = self._gate(decision, cartera, contexto, flags, hoy)

        # 1d: re-propuesta UNA vez con las holguras exactas; si no hay válida, NO_ACTION sobre esos aumentos.
        if res.no_action and repropuesta_fn is not None:
            nueva = repropuesta_fn(res.holguras)
            if nueva is not None:
                res2 = self._gate(nueva, cartera, contexto, flags, hoy)
                res, decision = res2, nueva

        self._auditar_y_registrar(res, decision, cartera, caja_actual, contexto, ciclo, precios,
                                  hashes, verifs, memo_macro)
        return res

    def _gate(self, decision: PMDecision, cartera: dict[str, float],
              contexto: dict[str, ContextoTicker], flags: dict[str, list[str]], hoy: date) -> ResultadoDecision:
        peso_max = float(self.ips.cfg.get("peso_max_nombre", 1.0))
        cap_flag = float(self.ips.cfg.get("cap_flag_supervivencia", peso_max))
        banda = float(self.ips.cfg.get("banda_peso_existente", 0.03))
        alertas: list[str] = []
        clip_local = False

        # 1. Reducciones (siempre) y aumentos aparte.
        pesos = dict(cartera)
        aumentos: dict[str, float] = {}
        hay_reduccion = False
        for a in decision.acciones:
            tk = a.ticker.upper()
            cur = cartera.get(tk, 0.0)
            tgt = 0.0 if a.accion in ("vender", "caja") else a.peso_objetivo
            if a.accion in _REDUCCIONES or tgt < cur - 1e-9:
                pesos.pop(tk, None) if tgt <= 0 else pesos.__setitem__(tk, tgt)
                hay_reduccion = True
            elif a.accion in _AUMENTOS or tgt > cur + 1e-9:
                aumentos[tk] = tgt
        tras_red = {t: w for t, w in pesos.items() if w > 0}

        # 2. Clip de aumentos: admisibilidad + cap + flag supervivencia.
        ok: dict[str, float] = {}
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
            ok[tk] = tgt

        # 3. Drift trim de existentes (banda).
        cand = {**tras_red, **ok}
        for tk, w in list(cand.items()):
            if tk not in aumentos and w > peso_max + banda + 1e-9:
                cand[tk], clip_local = peso_max, True
        cand = {t: w for t, w in cand.items() if w > 0}

        holguras: list[Violacion] = []
        caidos = False

        # 4. Agregado de GRUPO (sector/cuello): bloquea SOLO aumentos que empeoran el grupo violado (1c).
        sec_over, cue_over, holg_grp = _grupos_excedidos(cand, contexto, self.ips)
        if sec_over or cue_over:
            for tk in list(ok):
                ctx = contexto.get(tk)
                if ctx and (ctx.sector in sec_over or ctx.cuello in cue_over):
                    del ok[tk]
                    caidos = True
                    holguras += [h for h in holg_grp
                                 if (ctx.sector and h.detalle.startswith(f"sector={ctx.sector}"))
                                 or (ctx.cuello and h.detalle.startswith(f"cuello={ctx.cuello}"))]
            cand = {t: w for t, w in {**tras_red, **ok}.items() if w > 0}

        # 5. Agregado GLOBAL (caja/ops-sesión/turnover-rotación/max_pos): bloquea TODOS los aumentos restantes.
        caja_cand = round(1.0 - sum(cand.values()), 6)
        ops_sesiones = self.ledger.sesiones_ops_en_semana(hoy) + (1 if (hay_reduccion or ok) else 0)
        rot = _rotacion(cartera, cand)
        glob = [v for v in self.ips.validar(cand, contexto, caja=caja_cand, ops_semana=ops_sesiones,
                                            turnover=rot)
                if v.tipo == "agregada" and v.regla not in _GRUPO_REGLAS]
        if glob and ok:
            holguras += glob
            caidos = True
            ok = {}
            cand = {t: w for t, w in tras_red.items() if w > 0}
            caja_cand = round(1.0 - sum(cand.values()), 6)

        clip = "agregada" if caidos else ("local_simple" if clip_local else "none")
        res = ResultadoDecision(pesos_objetivo=aplicar_decision(cartera, decision.acciones),
                                pesos_finales=cand, caja_final=caja_cand, clip=clip, no_action=caidos,
                                alertas=alertas, holguras=holguras)
        for tk in res.pesos_finales:
            if tk in cartera and _inadmisible(contexto.get(tk), self.ips):
                res.alertas.append(f"{tk}: posición existente quedó inadmisible (market cap/ADV) — "
                                   f"ALERTA al PM, no se vende a la fuerza")
        return res

    def _auditar_y_registrar(self, res, decision, cartera, caja_actual, contexto, ciclo, precios,
                             hashes, verifs, memo_macro) -> None:
        if self.auditor is not None:
            viol = list(res.holguras)
            res.auditoria = self.auditor.auditar(
                decision, cartera_actual=cartera, caja_actual=caja_actual,
                memo_macro=memo_macro, verif_por_ticker=verifs, ips_violaciones=viol)
            if any(o.severidad == "alta" for o in res.auditoria.objeciones):
                res.demoradas = [a.ticker.upper() for a in decision.acciones if a.accion in _AUMENTOS]
        self._registrar(res, decision, cartera, precios, hashes, verifs, ciclo)

    def _registrar(self, res, decision, cartera, precios, hashes, verifs, ciclo) -> None:
        for i, a in enumerate(decision.acciones):
            tk = a.ticker.upper()
            resultante = res.pesos_finales.get(tk, 0.0)
            ejecutada = abs(resultante - cartera.get(tk, 0.0)) > 1e-9
            self._id_append(res, self.ledger.registrar_decision(
                a.model_copy(update={"dossier_hash": hashes.get(tk, a.dossier_hash)}),
                ciclo=ciclo, peso_resultante=resultante, ejecutada=ejecutada, clip=res.clip,
                precio=precios.get(tk), verif_veredicto=verifs.get(tk), ips_hash=self.ips.hash(),
                prompt_version=decision.meta.prompt_version, model=decision.meta.model,
                auditoria=res.auditoria if i == 0 else None))

    @staticmethod
    def _id_append(res: ResultadoDecision, did: str) -> None:
        res.decision_ids.append(did)


def _flag_no_resuelto(ticker: str, flags: list[str], respuestas) -> bool:
    if not flags:
        return False
    resueltos = {r.flag_id for r in respuestas if getattr(r, "accion", None) != "no_opera"}
    return any(f"{ticker}:{f}" not in resueltos and f not in resueltos for f in flags)
