"""Orquestador del comité (v2 Fase 3, doc 54 §4.6) — el capstone.

Flujo semanal: (Macro) → Triage todo el universo → ranking por (prioridad, incertidumbre) con posiciones/
eventos forzados → por cada seleccionado, bajo el ledger de presupuesto: reutiliza el Dossier si sigue
vigente (hash del data pack + TTL), o corre Analista → Bear → Verificador reservando el peor-caso antes y
confirmando el costo real después. La escalera de degradación del ledger decide qué se corre en cada nivel.

Todo inyectable (agentes, data_pack_fn, contexto_fn, verificar_fn, cache) → testeable sin API.
NOTA: la réplica del Analista al Bear (turno nuevo en su hilo) queda para un incremento posterior; el
Verificador corre sobre el Dossier emitido. El Analista en Batch (−50%) para agendados se cablea en Fase 4.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from backend.agentes.presupuesto import LedgerPresupuesto, peor_caso_usd
from backend.agentes.provenance import DataPack
from backend.agentes.schemas import BearAttack, Dossier, MacroMemo, TriageDecision, VerificationReport
from backend.agentes.triage import SenalesTriage
from backend.agentes.verificador import verificar as _verificar_det

# Peor-caso por nombre (para reservar antes de correr). Sobre-estima a propósito (el loop acumula input).
ANALISTA_MODEL, ANALISTA_MAXTOK, ANALISTA_USES, ANALISTA_IN = "claude-opus-5-5", 8192, 6, 200_000
BEAR_MODEL, BEAR_MAXTOK, BEAR_USES, BEAR_IN = "claude-sonnet-5-5", 4096, 3, 60_000
TTL_REUSO_DIAS = 35


def hash_pack(pack: DataPack) -> str:
    """Hash del contenido del data pack (métrica/valor/known_at) — clave de reutilización del Dossier."""
    base = ";".join(f"{p.metric}={p.value}@{p.known_at}" for p in sorted(pack.puntos, key=lambda x: x.metric))
    return hashlib.sha256(base.encode()).hexdigest()[:16]


@dataclass
class _Entrada:
    hash: str
    dossier: Dossier
    verif: VerificationReport
    fecha: date


class CacheDossiers:
    """Cache de Dossiers verificados, reusable mientras el hash del data pack no cambie y esté dentro del TTL."""

    def __init__(self):
        self._d: dict[str, _Entrada] = {}

    def vigente(self, ticker: str, hash_actual: str, hoy: date) -> _Entrada | None:
        e = self._d.get(ticker.upper())
        if e and e.hash == hash_actual and (hoy - e.fecha).days <= TTL_REUSO_DIAS:
            return e
        return None

    def guardar(self, ticker: str, hash_: str, dossier: Dossier, verif: VerificationReport, fecha: date) -> None:
        self._d[ticker.upper()] = _Entrada(hash=hash_, dossier=dossier, verif=verif, fecha=fecha)


@dataclass
class DecisionOrq:
    ticker: str
    accion: str                 # analizado | reutilizado | saltado_presupuesto | saltado_degradacion | triage_descarta | sin_dossier
    triage: TriageDecision
    dossier: Dossier | None = None
    bear: BearAttack | None = None
    verif: VerificationReport | None = None
    costo_usd: float = 0.0
    hash: str | None = None      # hash del data pack del dossier (clave para el ledger de decisiones)


@dataclass
class ResultadoSemana:
    memo: MacroMemo | None
    decisiones: list[DecisionOrq] = field(default_factory=list)
    gastado_usd: float = 0.0


class Orquestador:
    def __init__(self, *, triage, analista, bear, ledger: LedgerPresupuesto,
                 verificar_fn: Callable = _verificar_det, macro=None, cache: CacheDossiers | None = None,
                 data_pack_fn: Callable[[str], DataPack], contexto_fn: Callable[[str], str] | None = None):
        self.triage = triage
        self.analista = analista
        self.bear = bear
        self.verificar_fn = verificar_fn
        self.macro = macro
        self.ledger = ledger
        self.cache = cache or CacheDossiers()
        self.data_pack_fn = data_pack_fn
        self.contexto_fn = contexto_fn or (lambda _t: "")

    def correr_semana(self, candidatos: list[tuple[str, SenalesTriage, str]], *,
                      memo_macro: MacroMemo | None = None, hoy: date | None = None) -> ResultadoSemana:
        hoy = hoy or date.today()
        memo = memo_macro or (self.macro.evaluar() if self.macro else None)
        memo_txt = memo.resumen if memo else ""

        # 1. Triage de todos los candidatos.
        triages: list[tuple[SenalesTriage, str, TriageDecision]] = []
        for ticker, senales, resumen in candidatos:
            td = self.triage.evaluar(ticker, senales, resumen_hechos_nuevos=resumen)
            triages.append((senales, resumen, td))

        # 2. Ranking: research_profundo primero, por (prioridad, incertidumbre) desc.
        triages.sort(key=lambda x: (x[2].research_profundo, x[2].prioridad_0_3, x[2].incertidumbre_0_1),
                     reverse=True)

        res = ResultadoSemana(memo=memo)
        for senales, _resumen, td in triages:
            if not td.research_profundo:
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="triage_descarta", triage=td))
                continue

            modo = self.ledger.modo()
            if modo == "corte":
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="saltado_presupuesto", triage=td))
                continue

            para_evento = senales.es_posicion or senales.tiene_evento_fuerte
            pack = self.data_pack_fn(td.ticker)
            h = hash_pack(pack)

            # 2a. Reutilización: si hay Dossier vigente, no se gasta LLM.
            vig = self.cache.vigente(td.ticker, h, hoy)
            if vig is not None:
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="reutilizado", triage=td,
                                                  dossier=vig.dossier, verif=vig.verif, hash=h))
                continue
            if modo == "solo_reuso" or (modo == "restringido" and not para_evento):
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="saltado_degradacion", triage=td))
                continue

            # 2b. Reserva de peor-caso antes de correr.
            peor = (peor_caso_usd(ANALISTA_MODEL, max_tokens=ANALISTA_MAXTOK, max_uses=ANALISTA_USES,
                                  input_estimado=ANALISTA_IN)
                    + peor_caso_usd(BEAR_MODEL, max_tokens=BEAR_MAXTOK, max_uses=BEAR_USES, input_estimado=BEAR_IN))
            if not self.ledger.reservar(peor, para_evento=para_evento):
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="saltado_presupuesto", triage=td))
                continue

            # 2c. Analista → Bear → Verificador.
            r_an = self.analista.analizar(td.ticker, data_pack=pack, contexto_cuello=self.contexto_fn(td.ticker),
                                          memo_macro=memo_txt)
            costo = r_an.meta.cost_usd
            if r_an.dossier is None:
                self.ledger.confirmar(peor, costo)
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="sin_dossier", triage=td, costo_usd=costo))
                continue
            atk = self.bear.atacar(r_an.dossier)
            costo += atk.meta.cost_usd
            verif = self.verificar_fn(r_an.dossier, r_an.fuentes)
            costo += verif.meta.cost_usd
            self.ledger.confirmar(peor, costo)

            if verif.veredicto != "fail":      # un dossier fail no se cachea como usable
                self.cache.guardar(td.ticker, h, r_an.dossier, verif, hoy)
            res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="analizado", triage=td,
                                              dossier=r_an.dossier, bear=atk, verif=verif,
                                              costo_usd=round(costo, 6), hash=h))

        res.gastado_usd = round(self.ledger.gastado, 6)
        return res
