"""Ledger de decisiones del PM (v2 Fase 4, doc 55 §1.4 + §4).

Registro **append-only e inmutable** de cada decisión del PM. Igual patrón que el ledger fiel
(`backend/ledger/core.py`): el log de eventos es la verdad; el estado (si un falsador se cumplió, el
hit-rate, el Brier) es SIEMPRE una **proyección** del log, nunca se guarda mutado.

Eventos (una línea JSON por evento, con `tipo`):
- `decision`            — el PM decidió sobre un nombre: acción, peso objetivo vs resultante, marca
                          "PM+clip" (none/local_simple/agregada), tesis, falsador fechado, convicción,
                          precio, hashes (dossier/IPS), versiones prompt/modelo, veredicto del verificador,
                          y las objeciones del auditor como **predicciones falsables**.
- `resolucion_falsador` — al vencer `fecha_limite`: `disparado` (tesis FALSADA) | `no_disparado` (se
                          sostuvo). El **signo está fijado en el schema** (doc 55 §4.8).
- `resolucion_objecion` — puntuación ex-post de una objeción del auditor (`acertada` | `errada`).

Métricas (proyección): hit-rate de falsadores por bucket de convicción con conteos (doc 55 §4.8:
"alta: 7/12", NO un número único), Brier de calibración, N resueltos (el caller exige N≥20-30 antes de
inyectarlo al PM).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.agentes.schemas import AuditReport, PMAccion

_LEDGER_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ledger_decisiones_v2.jsonl"

# Buckets de convicción para el hit-rate calibrado (doc 55 §4.8: conteos por bucket, no número único).
BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("alta", 0.67, 1.01),
    ("media", 0.34, 0.67),
    ("baja", 0.0, 0.34),
)

ClipTipo = Literal["none", "local_simple", "agregada"]          # "PM+clip" para la atribución (doc 55 §4.1)
EstadoFalsador = Literal["disparado", "no_disparado"]           # disparado = tesis FALSADA; no_disparado = se sostuvo
EstadoObjecion = Literal["acertada", "errada"]


# --------------------------------------------------------------------------- eventos (inmutables)

class ObjecionRegistrada(BaseModel):
    """Objeción del auditor como predicción falsable puntuable ex-post (doc 55 §4.4)."""
    tipo: str
    detalle: str
    severidad: str
    horizonte_fecha: str | None = None       # YYYY-MM-DD para puntuarla (si es una predicción con plazo)


class RegistroDecision(BaseModel):
    tipo: Literal["decision"] = "decision"
    decision_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ciclo: str                                # fecha del ciclo semanal o id del evento (point-in-time)
    ticker: str
    accion: str                               # schemas.AccionTipo
    peso_objetivo: float
    peso_resultante: float                    # tras el clip del IPS (= objetivo si no hubo clip)
    clip: ClipTipo = "none"
    tesis: str
    falsador_afirmacion: str
    falsador_fecha_limite: str                # YYYY-MM-DD
    conviccion_0_1: float
    precio: float | None = None
    dossier_hash: str | None = None
    verif_veredicto: str | None = None        # pass/review/fail
    ips_hash: str = ""
    prompt_version: str = ""
    model: str = ""
    objeciones_auditor: list[ObjecionRegistrada] = Field(default_factory=list)


class ResolucionFalsador(BaseModel):
    tipo: Literal["resolucion_falsador"] = "resolucion_falsador"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decision_id: str
    estado: EstadoFalsador
    nota: str | None = None


class ResolucionObjecion(BaseModel):
    tipo: Literal["resolucion_objecion"] = "resolucion_objecion"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decision_id: str
    objecion_idx: int                         # índice en objeciones_auditor de la decisión
    estado: EstadoObjecion
    nota: str | None = None


# --------------------------------------------------------------------------- proyecciones

class CalibracionBucket(BaseModel):
    bucket: str
    n: int = 0                                # falsadores resueltos en el bucket
    sostenidos: int = 0                       # no_disparado (tesis se sostuvo)
    falsados: int = 0                         # disparado (tesis falsada)


class Metricas(BaseModel):
    n_resueltos: int = 0                      # total de falsadores vencidos y resueltos
    brier: float | None = None                # calibración de convicción (None si no hay resueltos)
    hit_rate_falsadores: float | None = None  # fracción de falsadores que se cumplieron (disparado/resueltos)
    por_bucket: list[CalibracionBucket] = Field(default_factory=list)
    objeciones_resueltas: int = 0
    objeciones_acertadas: int = 0


def _bucket(conv: float) -> str:
    for nombre, lo, hi in BUCKETS:
        if lo <= conv < hi:
            return nombre
    return "alta" if conv >= 1.0 else "baja"


# --------------------------------------------------------------------------- ledger

class LedgerDecisiones:
    """Wrapper del log JSONL append-only. Inyectá `path` para tests (ej. tmp_path)."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or _LEDGER_PATH)

    # --- escritura (solo append; nunca reescribe ni muta) ---

    def _append(self, evento: BaseModel) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(evento.model_dump_json() + "\n")

    def registrar_decision(self, accion: PMAccion, *, ciclo: str,
                            peso_resultante: float | None = None,
                            clip: ClipTipo = "none", precio: float | None = None,
                            verif_veredicto: str | None = None, ips_hash: str = "",
                            prompt_version: str = "", model: str = "",
                            auditoria: AuditReport | None = None) -> str:
        """Append de una decisión del PM. Devuelve `decision_id`. `peso_resultante` = objetivo si no hubo clip.

        La convicción (P tesis se sostiene, insumo del Brier) la lleva la propia `PMAccion`.
        """
        objeciones = [ObjecionRegistrada(tipo=o.tipo, detalle=o.detalle, severidad=o.severidad)
                      for o in (auditoria.objeciones if auditoria else [])]
        reg = RegistroDecision(
            ciclo=ciclo, ticker=accion.ticker.upper(), accion=accion.accion,
            peso_objetivo=accion.peso_objetivo,
            peso_resultante=accion.peso_objetivo if peso_resultante is None else peso_resultante,
            clip=clip, tesis=accion.tesis,
            falsador_afirmacion=accion.falsador.afirmacion,
            falsador_fecha_limite=accion.falsador.fecha_limite,
            conviccion_0_1=accion.conviccion_0_1, precio=precio, dossier_hash=accion.dossier_hash,
            verif_veredicto=verif_veredicto, ips_hash=ips_hash,
            prompt_version=prompt_version, model=model, objeciones_auditor=objeciones)
        self._append(reg)
        return reg.decision_id

    def resolver_falsador(self, decision_id: str, estado: EstadoFalsador, *, nota: str | None = None) -> None:
        self._append(ResolucionFalsador(decision_id=decision_id, estado=estado, nota=nota))

    def resolver_objecion(self, decision_id: str, objecion_idx: int, estado: EstadoObjecion, *,
                          nota: str | None = None) -> None:
        self._append(ResolucionObjecion(decision_id=decision_id, objecion_idx=objecion_idx,
                                         estado=estado, nota=nota))

    # --- lectura / proyección ---

    def _eventos(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        for linea in self.path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea:
                out.append(json.loads(linea))
        return out

    def decisiones(self) -> list[RegistroDecision]:
        return [RegistroDecision.model_validate(e) for e in self._eventos() if e.get("tipo") == "decision"]

    def ops_en_semana(self, hoy: date) -> int:
        """Cantidad de operaciones (compras/ventas/aumentos/recortes) ya registradas en la SEMANA CALENDARIO
        (ISO) de `hoy` — para el límite `max_ops_semana` del IPS (se cuenta por semana, no por decisión)."""
        wk = hoy.isocalendar()[:2]
        mueven = {"comprar", "vender", "aumentar", "recortar"}
        return sum(1 for d in self.decisiones()
                   if d.accion in mueven and d.ts.date().isocalendar()[:2] == wk)

    def pendientes(self, hoy: date | None = None) -> list[RegistroDecision]:
        """Falsadores VENCIDOS (fecha_limite <= hoy) y aún sin resolver — insumo del monitor de eventos."""
        hoy = hoy or date.today()
        resueltos = {e["decision_id"] for e in self._eventos() if e.get("tipo") == "resolucion_falsador"}
        out = []
        for d in self.decisiones():
            if d.decision_id in resueltos:
                continue
            try:
                vence = date.fromisoformat(d.falsador_fecha_limite)
            except ValueError:
                continue
            if vence <= hoy:
                out.append(d)
        return out

    def metricas(self) -> Metricas:
        """Proyección: Brier + hit-rate de falsadores calibrado por bucket (doc 55 §4.8)."""
        eventos = self._eventos()
        decisiones = {d.decision_id: d for d in self.decisiones()}
        resoluciones = [e for e in eventos if e.get("tipo") == "resolucion_falsador"]

        buckets = {nombre: CalibracionBucket(bucket=nombre) for nombre, _, _ in BUCKETS}
        suma_brier = 0.0
        n = disparados = 0
        for r in resoluciones:
            d = decisiones.get(r["decision_id"])
            if d is None:                       # resolución sin decisión conocida: se ignora
                continue
            sostenido = r["estado"] == "no_disparado"
            outcome = 1.0 if sostenido else 0.0  # convicción = P(tesis se sostiene)
            suma_brier += (d.conviccion_0_1 - outcome) ** 2
            b = buckets[_bucket(d.conviccion_0_1)]
            b.n += 1
            b.sostenidos += int(sostenido)
            b.falsados += int(not sostenido)
            disparados += int(not sostenido)
            n += 1

        obj_res = [e for e in eventos if e.get("tipo") == "resolucion_objecion"]
        return Metricas(
            n_resueltos=n,
            brier=round(suma_brier / n, 4) if n else None,
            hit_rate_falsadores=round(disparados / n, 4) if n else None,
            por_bucket=[buckets[nombre] for nombre, _, _ in BUCKETS],
            objeciones_resueltas=len(obj_res),
            objeciones_acertadas=sum(1 for e in obj_res if e.get("estado") == "acertada"))
