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
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backend.agentes.presupuesto import LedgerPresupuesto, peor_caso_usd
from backend.agentes.provenance import DataPack
from backend.agentes.schemas import BearAttack, Dossier, MacroMemo, TriageDecision, VerificationReport
from backend.agentes.triage import SenalesTriage
from backend.agentes.verificador import verificar as _verificar_det

# Peor-caso por nombre (para reservar antes de correr). Sobre-estima a propósito (el loop acumula input).
log = logging.getLogger("agentes.orquestador")
# max_tokens 16384 (no 8192): con los claims numéricos + ref el dossier se agrandó y topaba el límite ANTES
# del falsador (regresión del smoke #6/7). Opus 5.5 lo soporta de sobra.
ANALISTA_MODEL, ANALISTA_MAXTOK, ANALISTA_USES, ANALISTA_IN = "claude-opus-5-5", 16384, 6, 200_000
BEAR_MODEL, BEAR_MAXTOK, BEAR_USES, BEAR_IN = "claude-sonnet-5-5", 4096, 3, 60_000
TTL_REUSO_DIAS = 35


# Métricas de mercado VOLÁTILES: cambian cada día y NO deben invalidar un dossier (auditoría P0.2a).
_METRICAS_VOLATILES = {"precio", "adv_30d_usd", "market_cap", "shares_outstanding"}


def hash_pack(pack: DataPack) -> str:
    """Hash de los insumos MATERIALES ORIGINALES del data pack — clave de reutilización del Dossier.
    EXCLUYE: (a) métricas de mercado volátiles (precio/ADV/market cap/shares) y (b) DataPoints DERIVED
    (calculadoras): son función de los originales, y un derivado como `dilucion_12m_pct` puede moverse por
    un insumo volátil (shares de Yahoo) sin que haya cambiado nada material (auditoría r3 #4). Si un
    ORIGINAL material cambia (otro valor/`known_at`, p.ej. un filing nuevo) → el hash cambia y re-analiza."""
    from backend.agentes.provenance import DataKind
    materiales = [p for p in pack.puntos
                  if p.metric not in _METRICAS_VOLATILES and p.kind == DataKind.ORIGINAL]
    base = ";".join(f"{p.metric}={p.value}@{p.known_at}"
                    for p in sorted(materiales, key=lambda x: (x.metric, str(x.known_at))))
    return hashlib.sha256(base.encode()).hexdigest()[:16]


@dataclass
class _Entrada:
    hash: str
    dossier: Dossier
    verif: VerificationReport
    fecha: date


_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache_dossiers_v2.json"


class CacheDossiers:
    """Cache de Dossiers verificados, reusable mientras el hash del data pack no cambie y esté dentro del TTL.

    Puede PERSISTIR a disco (`data/cache_dossiers_v2.json`) para que la reutilización sobreviva al reinicio
    del proceso (auditoría P0.2b): pasá `path=_CACHE_PATH` (lo hace el ops). `path=None` → solo memoria
    (default; tests hermético)."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self._d: dict[str, _Entrada] = {}
        if self.path and self.path.exists():
            self._cargar()

    def _cargar(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for tk, e in data.items():
            self._d[tk] = _Entrada(hash=e["hash"], fecha=date.fromisoformat(e["fecha"]),
                                   dossier=Dossier.model_validate(e["dossier"]),
                                   verif=VerificationReport.model_validate(e["verif"]))

    def _persistir(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {tk: {"hash": e.hash, "fecha": e.fecha.isoformat(),
                     "dossier": e.dossier.model_dump(mode="json"),
                     "verif": e.verif.model_dump(mode="json")} for tk, e in self._d.items()}
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def vigente(self, ticker: str, hash_actual: str, hoy: date) -> _Entrada | None:
        e = self._d.get(ticker.upper())
        if e and e.hash == hash_actual and (hoy - e.fecha).days <= TTL_REUSO_DIAS:
            return e
        return None

    def guardar(self, ticker: str, hash_: str, dossier: Dossier, verif: VerificationReport, fecha: date) -> None:
        self._d[ticker.upper()] = _Entrada(hash=hash_, dossier=dossier, verif=verif, fecha=fecha)
        self._persistir()


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
                      memo_macro: MacroMemo | None = None, hoy: date | None = None,
                      cupo_cobertura: int = 0, bootstrap: bool = False,
                      pre_earnings_top_n: int = 3, dias_earnings: int = 10) -> ResultadoSemana:
        """`cupo_cobertura`: cuántos nombres NUNCA analizados se promueven a research esta semana aunque el
        triage no los marque (ordenados por la prioridad de su cuello) — resuelve que un nombre nuevo
        prometedor nunca entre (auditoría P0.3). `bootstrap=True`: promueve TODOS los nuevos (primera pasada
        del universo); el gasto lo acota igual el ledger de presupuesto (su propio tope)."""
        hoy = hoy or date.today()
        memo = memo_macro or (self.macro.evaluar() if self.macro else None)
        memo_txt = memo.resumen if memo else ""

        # 1. Triage de todos los candidatos.
        triages: list[tuple[SenalesTriage, str, TriageDecision]] = []
        for ticker, senales, resumen in candidatos:
            td = self.triage.evaluar(ticker, senales, resumen_hechos_nuevos=resumen)
            triages.append((senales, resumen, td))

        # 1b. SELECCIÓN de deep por el EMBUDO (doc 64 + regla de earnings): la MISMA función que usa el
        #     dry-run decide qué va a análisis profundo (así lo que se ve en --dry-run es lo que corre). El
        #     Triage (Haiku) ya juzgó la materialidad; acá el embudo decide deep/no-deep sobre las señales.
        from backend.agentes.embudo import seleccionar_para_deep
        cands_sel = [(td.ticker, senales, resumen) for senales, resumen, td in triages]
        cupo = len([c for c in cands_sel if c[1].dias_desde_dossier is None]) if bootstrap else cupo_cobertura
        sel = seleccionar_para_deep(cands_sel, cupo=cupo, pre_earnings_top_n=pre_earnings_top_n,
                                    dias_earnings=dias_earnings)
        motivos_sel = {tk: m for grupo in ("forzados", "precio", "pre_earnings", "promovidos")
                       for tk, m in sel[grupo]}
        for _s, _r, td in triages:
            td.research_profundo = td.ticker in sel["deep"]      # el embudo manda, no el prioridad≥2 legacy
            if td.ticker in motivos_sel:
                td.motivo = motivos_sel[td.ticker]

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

            # 2a. Reutilización: si hay Dossier vigente, no se gasta LLM. Un EVENTO FUERTE saltea el caché
            #     y fuerza re-análisis (el dossier vigente pudo quedar viejo por el evento; auditoría r2 item 3).
            vig = None if senales.tiene_evento_fuerte else self.cache.vigente(td.ticker, h, hoy)
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

            # 2c. Analista → Bear → Verificador. Una falla en UN nombre (LLM flojo, red, validación) no debe
            #     tumbar el ciclo entero → se saltea y se sigue (resiliencia; auditoría del smoke #6).
            try:
                r_an = self.analista.analizar(td.ticker, data_pack=pack,
                                              contexto_cuello=self.contexto_fn(td.ticker), memo_macro=memo_txt,
                                              max_tokens=ANALISTA_MAXTOK)
                costo = r_an.meta.cost_usd
                if r_an.dossier is None:
                    self.ledger.confirmar(peor, costo)
                    res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="sin_dossier", triage=td,
                                                      costo_usd=costo))
                    continue
                atk = self.bear.atacar(r_an.dossier)
                costo += atk.meta.cost_usd
                # el verificador recibe el pack (para contraste XBRL) + el known_at más nuevo de los datos de
                # FILING (XBRL), para la regla de vigencia 1d, + hoy (falsador vencido 1e). OJO: NO usar el
                # max del pack entero — los datos de mercado (Yahoo) tienen known_at=hoy y contaminarían el
                # proxy del "último filing" (bug detectado en el smoke #3: todo quedaba "dato viejo").
                knowns = [p.known_at for p in pack.puntos
                          if p.known_at is not None and "xbrl" in (p.source.name or "").lower()]
                verif = self.verificar_fn(r_an.dossier, r_an.fuentes,
                                          pack={p.metric: p for p in pack.puntos},
                                          ultimo_filing_periodico=max(knowns) if knowns else None, hoy=hoy)
                costo += verif.meta.cost_usd
                self.ledger.confirmar(peor, costo)
            except Exception as e:  # noqa: BLE001
                log.warning("orquestador: falló el análisis de %s (%s) → saltado", td.ticker, e)
                self.ledger.confirmar(peor, 0.0)   # libera la reserva de peor-caso
                res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="error_analisis", triage=td))
                continue

            if verif.veredicto != "fail":      # un dossier fail no se cachea como usable
                self.cache.guardar(td.ticker, h, r_an.dossier, verif, hoy)
            res.decisiones.append(DecisionOrq(ticker=td.ticker, accion="analizado", triage=td,
                                              dossier=r_an.dossier, bear=atk, verif=verif,
                                              costo_usd=round(costo, 6), hash=h))

        res.gastado_usd = round(self.ledger.gastado, 6)
        return res
