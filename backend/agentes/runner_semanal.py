"""Runner semanal (v2 Fase 4, doc 55) — cablea el ciclo completo end-to-end.

research (Macro→Triage→Analista→Bear→Verificador, bajo presupuesto) → **PM** (sizea bajo IPS) →
**orquestador de decisión** (gate IPS + Auditor + ledger) → **paper nuevo** (fills contra el ledger fiel).

Todo inyectable (igual que `orquestador.py`): recibe los agentes ya construidos y los DATOS REALES como
parámetros —`precios`, `contexto` (sector/cuello/market cap/ADV por ticker, de `nx_nodo` + market data),
`session` del ledger fiel del paper—. Así es testeable con stubs y el cableado a datos reales son
adaptadores finos que provee el caller (los armamos junto con el smoke real).

La cartera actual (pesos + caja) se PROYECTA del ledger fiel point-in-time; el hit-rate del PM sale del
ledger de decisiones (se inyecta solo si hay N suficiente, doc 55 §4.8).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

from backend.agentes.ips import ContextoTicker, Violacion
from backend.agentes.orquestador import Orquestador, ResultadoSemana
from backend.agentes.orquestador_decision import OrquestadorDecision, ResultadoDecision
from backend.agentes.paper_pm import ResultadoPaper
from backend.agentes.paper_pm import ejecutar as ejecutar_paper
from backend.agentes.pm import PM
from backend.agentes.schemas import Dossier, PMDecision, VerificationReport
from backend.ledger import core

MIN_N_HIT_RATE = 20              # doc 55 §4.8: no inyectar track record con menos de ~20-30 resueltos
_ALERTAS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "alertas_pm_v2.json"


def _fmt_holguras(holguras: list[Violacion]) -> str:
    return "\n".join(f"- {v.regla}: {v.detalle} (holgura {v.holgura:+.3f})" for v in holguras) or "(sin detalle)"


def cartera_desde_ledger(session, precios: dict[str, float]) -> tuple[dict[str, float], float, float]:
    """Proyecta el ledger fiel → (pesos por ticker, fracción en caja, equity). Point-in-time con `precios`."""
    est = core.proyectar(session, precios)
    equity = est["equity"]
    if equity <= 0:
        return {}, 1.0, equity
    pesos = {t: (p.shares * precios.get(t.upper(), 0.0)) / equity for t, p in est["posiciones"].items()}
    return {t: w for t, w in pesos.items() if w > 0}, est["caja"] / equity, equity


@dataclass
class ResultadoRunner:
    research: ResultadoSemana
    decision: PMDecision
    resultado_decision: ResultadoDecision
    paper: ResultadoPaper
    hit_rate_resumen: str
    dossiers_considerados: list[str] = field(default_factory=list)   # PASS/REVIEW que vio el PM


class RunnerSemanal:
    def __init__(self, *, research: Orquestador, pm: PM, decision: OrquestadorDecision,
                 alertas_path: Path | str | None = _ALERTAS_PATH, verif_ciego_fn=None):
        self.research = research
        self.pm = pm
        self.decision = decision          # su `.ledger` es el ledger de decisiones (fuente del hit-rate)
        self.alertas_path = Path(alertas_path) if alertas_path else None   # None → sin persistencia (tests)
        # F3 (doc 83 §4): verificación ciega de los aumentos. OPT-IN explícito (gasta LLM+red): None → apagada
        # (tests + default). El caller real pasa `verif_ciego_fn(aumentos, fichas, cutoff) -> {tk: VerificacionCiega}`.
        self.verif_ciego_fn = verif_ciego_fn

    def _cargar_alertas(self) -> list[str]:
        if self.alertas_path and self.alertas_path.exists():
            try:
                return list(json.loads(self.alertas_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                return []
        return []

    def _guardar_alertas(self, alertas: list[str]) -> None:
        if not self.alertas_path:
            return
        self.alertas_path.parent.mkdir(parents=True, exist_ok=True)
        self.alertas_path.write_text(json.dumps(alertas, ensure_ascii=False), encoding="utf-8")

    def _estacionar(self, res_dec: ResultadoDecision, contexto: dict[str, ContextoTicker]) -> None:
        """r7a #1: aparca el residual de `res_dec.pesos_finales` en ETFs temáticos ponderados por los clusters
        del mapa (sector del nombre). Weighting: por los sectores donde el PM TIENE convicción (nombres con
        peso); si no hay nombres, por la distribución de sectores del universo (contexto). Mutá res_dec."""
        from collections import Counter

        from backend.agentes.estacionamiento import aplicar_estacionamiento, tickers_parking
        cfg = self.decision.ips.cfg
        if not (cfg.get("estacionamiento") or {}).get("activo"):
            return
        park = tickers_parking(cfg)
        nombres = {t: w for t, w in res_dec.pesos_finales.items() if t.upper() not in park and w > 0}
        clusters: Counter = Counter()
        for t, w in nombres.items():                              # donde el PM tiene convicción
            ctx = contexto.get(t.upper())
            if ctx and ctx.sector:
                clusters[ctx.sector] += w
        if not clusters:                                          # sin nombres → diversifica por el mapa
            clusters = Counter(c.sector for c in contexto.values() if c and c.sector)
        if not clusters:
            return
        finales, caja = aplicar_estacionamiento(nombres, dict(clusters), cfg)
        res_dec.pesos_finales = finales
        res_dec.caja_final = caja

    def _packet_txt(self, pesos: dict, caja_pct: float, equity: float, memo: str, hoy) -> str:
        """Arma + renderiza el PM Decision Packet (r9 P2) desde el store de fichas + el ledger de decisiones.
        Best-effort: si no hay fichas todavía, devuelve "" (el PM sigue con dossiers + cartera como antes)."""
        try:
            from backend.agentes.estacionamiento import tickers_parking
            from backend.agentes.ficha_store import StoreFichas
            from backend.agentes.packet_pm import construir_packet, render_packet
            fichas = StoreFichas().todos()
            if not fichas:
                return ""
            ult_dec: dict[str, dict] = {}
            for reg in self.decision.ledger.decisiones():
                ult_dec[reg.ticker.upper()] = {"ticker": reg.ticker.upper(), "accion": reg.accion,
                                               "tesis": reg.tesis}
            pack = construir_packet(fichas=fichas, posiciones=pesos, caja_pct=caja_pct, equity=equity,
                                    memo_macro=memo, decisiones_previas=list(ult_dec.values()),
                                    tickers_etf=tickers_parking(self.decision.ips.cfg), as_of=hoy)
            return render_packet(pack)
        except Exception:  # noqa: BLE001 — el packet es contexto; si falla, el PM decide igual
            return ""

    def _hit_rate_resumen(self) -> str:
        m = self.decision.ledger.metricas()
        if m.n_resueltos < MIN_N_HIT_RATE:
            return f"(histórico insuficiente: {m.n_resueltos} falsadores resueltos, se necesitan ≥{MIN_N_HIT_RATE})"
        buckets = " · ".join(f"{b.bucket}: {b.falsados}/{b.n} falsados" for b in m.por_bucket if b.n)
        return (f"Falsadores resueltos: {m.n_resueltos} · Brier={m.brier} · "
                f"hit-rate falsadores={m.hit_rate_falsadores} · por convicción: {buckets}")

    def correr(self, candidatos, *, session, precios: dict[str, float],
               contexto: dict[str, ContextoTicker], memo_macro=None, hoy: date | None = None,
               ciclo: str | None = None, comision: float = 0.0,
               cupo_cobertura: int = 0, bootstrap: bool = False,
               invertible_fn=None, cupo_forzados=None, gigante_barato_fn=None,
               cupo_gigantes: int = 0, precios_meta: dict[str, dict] | None = None,
               eventos_solo_posiciones: bool = False, cupo_oportunidad: int | None = None) -> ResultadoRunner:
        hoy = hoy or date.today()
        ciclo = ciclo or hoy.isoformat()

        # 1. Research bajo presupuesto → dossiers verificados por nombre (con cupo de cobertura/bootstrap).
        # Los filtros del embudo (market cap pre-deep, carril forzado capeado, gigantes) se pasan iguales que
        # en el dry-run → "dry-run = corrida real" (doc 76).
        research = self.research.correr_semana(candidatos, memo_macro=memo_macro, hoy=hoy,
                                               cupo_cobertura=cupo_cobertura, bootstrap=bootstrap,
                                               invertible_fn=invertible_fn, cupo_forzados=cupo_forzados,
                                               gigante_barato_fn=gigante_barato_fn, cupo_gigantes=cupo_gigantes,
                                               eventos_solo_posiciones=eventos_solo_posiciones,
                                               cupo_oportunidad=cupo_oportunidad)
        memo_txt = research.memo.resumen if research.memo else ""

        dossiers: list[tuple[Dossier, VerificationReport]] = []
        hashes: dict[str, str] = {}
        verifs: dict[str, str] = {}
        flags: dict[str, list[str]] = {}
        for d in research.decisiones:
            if d.dossier is None or d.verif is None:
                continue
            tk = d.ticker.upper()
            verifs[tk] = d.verif.veredicto
            if d.verif.flags_supervivencia:
                flags[tk] = list(d.verif.flags_supervivencia)
            if d.hash:
                hashes[tk] = d.hash
            if d.verif.veredicto in ("pass", "review"):          # FAIL no justifica compra/aumento
                dossiers.append((d.dossier, d.verif))

        # D4 (doc 74 + r5 item 2): clasificación por nombre para la señal de sizing (sombra). El techo de hechos
        # usa DATOS DUROS del pack (NO traccion_0_4, que la declara el Analista): revenue recurrente = revenue FY
        # ≥ umbral del IPS; fcf_negativo/runway capex-aware del pack. tiene_puente = hay escenarios.
        from backend.agentes.clasificacion import ClasifTicker
        umbral_rev = float(self.decision.ips.cfg.get("umbral_revenue_recurrente_usd", 50e6))
        clasif_por_ticker: dict[str, ClasifTicker] = {}
        for d in research.decisiones:
            if d.dossier is None or d.verif is None or d.verif.veredicto not in ("pass", "review"):
                continue
            inv = d.dossier.invertibilidad
            if inv is None:
                continue
            clasif_por_ticker[d.ticker.upper()] = ClasifTicker(
                analyst_clasif=inv.analyst_classification,
                revenue_recurrente=(d.revenue_fy is not None and d.revenue_fy >= umbral_rev),
                tiene_puente=bool(d.dossier.escenarios),
                fcf_negativo=d.fcf_negativo,
                runway_meses=d.runway_meses)

        # Persistencia Brier (doc 74 D1): snapshot del puente por nombre para puntuar ex-post la P(bull) del
        # analista (¿se materializó al horizonte?) + la implícita como contexto. Lo que mide si Tier B mejoró
        # la OPORTUNIDAD o solo la vistió de números.
        from datetime import timedelta
        from backend.agentes.futuro import Escenario as _EscFut
        from backend.agentes.futuro import probabilidad_implicita_bull as _pimpl
        bull_por_ticker: dict[str, dict] = {}
        for d, _v in dossiers:
            bull = next((e for e in d.escenarios if e.nombre == "bull"), None)
            if bull is None:
                continue
            ctx = contexto.get(d.ticker.upper())
            prob_impl = None
            if ctx is not None and ctx.market_cap:
                escs = [_EscFut(e.nombre, e.metrica_terminal, e.multiplo_salida, e.anios, e.prob)
                        for e in d.escenarios]
                resto = [e for e in escs if e.nombre != "bull"]
                if resto:
                    prob_impl = _pimpl(ctx.market_cap, next(e for e in escs if e.nombre == "bull"), resto,
                                       anios=bull.anios, dilucion_pct=(d.dilucion_esperada_pct or 0.0),
                                       caja_neta_terminal=(d.caja_neta_terminal or 0.0)).p_bull
            bull_por_ticker[d.ticker.upper()] = {
                "prob": bull.prob, "prob_implicita": prob_impl,
                "horizonte_fecha": (hoy + timedelta(days=365 * bull.anios)).isoformat(),
                "escenarios": [{"nombre": e.nombre, "metrica_terminal": e.metrica_terminal,
                                "multiplo_salida": e.multiplo_salida, "anios": e.anios, "prob": e.prob}
                               for e in d.escenarios]}

        # 2. Cartera actual (proyección del ledger fiel) + hit-rate + ops de la semana + alertas previas.
        pesos_actual, caja_pct, _equity = cartera_desde_ledger(session, precios)
        hr = self._hit_rate_resumen()
        ops_previas = self.decision.ledger.sesiones_ops_en_semana(hoy)
        alertas_previas = self._cargar_alertas()
        # ciclo de resolución (doc 74): surfacear predicciones vencidas sin resolver (falsadores + bull) para
        # que el PM sepa que el track record está incompleto. NO se auto-resuelve acá (el Brier se puntúa con
        # resoluciones deliberadas, por evidencia o por la regla de silencio — ver ops/resolucion).
        from backend.agentes.resolucion import pendientes as _pendientes
        _pend = _pendientes(self.decision.ledger, hoy)
        if _pend:
            alertas_previas = alertas_previas + [
                f"{len(_pend)} predicciones vencidas SIN resolver (correr el ciclo de resolución): "
                + ", ".join(f"{p.ticker}[{p.tipo}]" for p in _pend[:5])]

        # 2bis. PM Decision Packet (r9 P2, doc 80 §G): la memoria viva (fichas/zonas/banca/alertas/decisiones
        # previas) que el PM recibe junto a los dossiers frescos. Best-effort: sin store de fichas, se saltea.
        packet_txt = self._packet_txt(pesos_actual, caja_pct, _equity, memo_txt, hoy)

        # 3. PM decide (con las ops ya usadas en la semana para su dry-run y las alertas previas).
        def _pm(feedback: str = ""):
            return self.pm.decidir(dossiers=dossiers, cartera_actual=pesos_actual, caja_actual=caja_pct,
                                   contexto=contexto, memo_macro=memo_txt, hit_rate_resumen=hr,
                                   ops_semana_previas=ops_previas, alertas_previas=alertas_previas,
                                   packet_txt=packet_txt, feedback=feedback)
        decision = _pm()

        # 3bis. Verificación CIEGA (F3, doc 83 §4): solo sobre los nombres que el PM quiere COMPRAR/AUMENTAR
        # (trigger por decisión de capital). El canal ciego re-extrae la evidencia primaria SIN ver el dossier;
        # si no reconcilia (FAIL) el gate bloquea el aumento. Fail-open ante error (no tumba el ciclo); la
        # AUSENCIA de verificación no es PASS (no desbloquea nada: el gate solo frena los FAIL explícitos).
        ciego_vered: dict[str, str] = {}
        if self.verif_ciego_fn is not None:              # opt-in: solo si el caller real lo cableó (gasta LLM+red)
            try:
                aumentos = [a.ticker for a in decision.acciones if a.accion in ("comprar", "aumentar")]
                if aumentos:
                    from backend.agentes.ficha_store import StoreFichas
                    vcs = self.verif_ciego_fn(aumentos, StoreFichas().todos(), hoy.isoformat())
                    ciego_vered = {tk: vc.veredicto for tk, vc in vcs.items()}
                    for tk, vc in vcs.items():
                        if vc.veredicto != "PASS":
                            _log.warning("verificación ciega %s = %s: %s", tk, vc.veredicto,
                                         "; ".join(f"{d.campo}({d.severidad})" for d in vc.discrepancias))
            except Exception as e:  # noqa: BLE001 — la verificación ciega no debe tumbar el ciclo
                _log.warning("verificación ciega falló (fail-open): %s", e)

        # 4. Gate duro del IPS + Auditor + ledger; re-propuesta UNA vez si el gate rechaza aumentos (1d).
        res_dec = self.decision.procesar(
            decision, cartera_actual=pesos_actual, caja_actual=caja_pct, contexto=contexto, ciclo=ciclo,
            hoy=hoy, precios=precios, dossier_hash_por_ticker=hashes, verif_por_ticker=verifs,
            flags_por_ticker=flags, ciego_por_ticker=ciego_vered,
            clasif_por_ticker=clasif_por_ticker, bull_por_ticker=bull_por_ticker,
            memo_macro=memo_txt, repropuesta_fn=lambda holg: _pm(feedback=_fmt_holguras(holg)))

        # 4bis. Estacionamiento (r7a #1): el residual que el PM NO desplegó en nombres con margen de seguridad
        # se aparca en ETFs temáticos (ponderados por los clusters del mapa), NUNCA en nombres caros. Solo si
        # el PM opera (operar_ahora): si eligió NO operar, es caja macro-justificada y se respeta.
        if decision.operar_ahora:
            self._estacionar(res_dec, contexto)

        # 5. Paper + persistir alertas para la corrida siguiente (item 5).
        paper = ejecutar_paper(session, res_dec, precios=precios, fecha_fill=hoy, comision=comision,
                               precios_meta=precios_meta)
        self._guardar_alertas(res_dec.alertas)

        return ResultadoRunner(research=research, decision=decision, resultado_decision=res_dec,
                               paper=paper, hit_rate_resumen=hr,
                               dossiers_considerados=[d.ticker for d, _ in dossiers])
