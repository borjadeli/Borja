"""Discovery — cola de propuestas de empresas (doc 76 §4, la base del motor de alpha).

IA2: "antes del agente, sin LLM, construir la cola `propuestas_empresa` con su esquema y flujo de aprobación
+ el estado OBSERVACIÓN. Cuando llegue el agente, es solo otro productor." Esto es eso: determinista,
append-only, sin API. El agente LLM de discovery (Sonnet+web, tras confiar en las corridas) producirá
propuestas que entran acá; hoy se alimenta a mano.

Flujo (doc 76): propuesta → VALIDADORES DUROS (deterministas) → si pasa, estado `observacion` (se la sigue
con datos/eventos pero NO es investible ni comprable hasta que el humano la promueve); el humano aprueba →
`aprobada` (un op la inserta a nx_empresa como activa). Si no se aprueba en `dias_vigencia` → `vencida`
(NUNCA se acepta por silencio). El filtro NO es el humano nombre-por-nombre: el humano solo promueve; los
validadores deterministas + el pipeline (embudo→IPS→PM→ejecución) son el filtro (decisión del operador).

Liquidez NO es validador (el operador entra con poco capital). El gate duro real del IPS sigue aguas abajo.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_COLA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cola_propuestas_v2.jsonl"

EstadoPropuesta = Literal["observacion", "aprobada", "rechazada", "vencida", "retirada"]


class PropuestaEmpresa(BaseModel):
    """Una empresa candidata a entrar al universo (del agente discovery o del operador a mano)."""
    ticker: str
    cuello: str                                  # nodo/cuello del mapa donde participa (la tesis estructural)
    tesis_corta: str
    por_que_ahora: str                           # el catalizador/cambio que la hace relevante HOY
    fuentes: list[str] = Field(default_factory=list)   # ≥1 fuente primaria (filing/comunicado) para el "por qué ahora"
    market_cap: float | None = None
    dias_vigencia: int = 30                      # si el humano no la promueve en N días → vence (no se acepta sola)


def _ticker_valido(tk: str) -> bool:
    tk = (tk or "").strip().upper()
    base = tk.split(".")[0]                       # admite sufijo de bolsa extranjera (3661.TW)
    return 1 <= len(base) <= 6 and base.isalnum()


def validar_propuesta(p: PropuestaEmpresa, *, ips_cfg: dict, universo_actual: set[str],
                      nodos_conocidos: set[str] | None = None,
                      hoy: date | None = None) -> tuple[bool, list[str]]:
    """Validadores DUROS deterministas (doc 76). Liquidez NO se valida. Si se pasa `nodos_conocidos`, se exige
    ENCAJE EN EL MAPA (el cuello debe ser un nodo real de la brújula) — el mapa es el que valida, no el humano."""
    motivos: list[str] = []
    if not _ticker_valido(p.ticker):
        motivos.append(f"ticker inválido: '{p.ticker}'")
    if p.ticker.strip().upper() in {t.upper() for t in universo_actual}:
        motivos.append("duplicado: ya está en el universo")
    if nodos_conocidos is not None and p.cuello.strip() not in nodos_conocidos:
        motivos.append(f"sin encaje en el mapa: '{p.cuello[:60]}' no es un cuello conocido")
    mc_min = float(ips_cfg.get("market_cap_min_usd", 0))
    mc_max = float(ips_cfg.get("market_cap_max_usd", 1e18))
    if p.market_cap is None:
        motivos.append("sin market cap (pendiente de verificación, no inelegible)")   # blando: a verificar
    elif 0 < p.market_cap < 1e6:
        # número sospechosamente chico ⇒ casi seguro MAL ESCALADO (5=$5B, 500=$500M), no un cap real <$1M.
        # No se rechaza en duro por un error de escala del LLM (ya nos pasó en el puente): queda a verificar.
        motivos.append(f"market cap sospechoso ({p.market_cap}) — ¿mal escalado? pendiente de verificación")
    elif not (mc_min <= p.market_cap <= mc_max):
        motivos.append(f"market cap {p.market_cap/1e9:.1f}B fuera del rango IPS "
                       f"[{mc_min/1e9:.2f}B, {mc_max/1e9:.0f}B]")
    if not (p.por_que_ahora or "").strip():
        motivos.append("sin 'por qué ahora'")
    if not [f for f in p.fuentes if (f or '').strip()]:
        motivos.append("sin fuente primaria para el 'por qué ahora'")
    if not (p.cuello or "").strip():
        motivos.append("sin cuello/nodo del mapa (la tesis estructural)")
    # "sin market cap" es BLANDO (no inelegible definitivo): si es el único motivo, pasa a observación igual.
    duros = [m for m in motivos if "pendiente de verificación" not in m]
    return (len(duros) == 0), motivos


# --------------------------------------------------------------------------- eventos (append-only)

class _RegistroPropuesta(BaseModel):
    tipo: Literal["propuesta"] = "propuesta"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    propuesta: PropuestaEmpresa
    estado: EstadoPropuesta                      # observacion (validó) | rechazada (no validó)
    motivos: list[str] = Field(default_factory=list)


class _Resolucion(BaseModel):
    tipo: Literal["resolucion"] = "resolucion"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ticker: str
    estado: EstadoPropuesta                      # aprobada | rechazada | retirada | vencida
    nota: str | None = None


class ColaPropuestas:
    """Cola append-only de propuestas (patrón ledger). El estado por ticker es PROYECCIÓN del log."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or _COLA_PATH)

    def _append(self, ev: BaseModel) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(ev.model_dump_json() + "\n")

    def _eventos(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def registrar(self, p: PropuestaEmpresa, *, ips_cfg: dict, universo_actual: set[str],
                  nodos_conocidos: set[str] | None = None,
                  hoy: date | None = None) -> tuple[str, list[str]]:
        """Valida y registra. Devuelve (estado, motivos). Pasa → 'observacion'; falla → 'rechazada'."""
        ok, motivos = validar_propuesta(p, ips_cfg=ips_cfg, universo_actual=universo_actual,
                                        nodos_conocidos=nodos_conocidos, hoy=hoy)
        estado: EstadoPropuesta = "observacion" if ok else "rechazada"
        reg = _RegistroPropuesta(propuesta=p, estado=estado, motivos=motivos)
        self._append(reg)
        return estado, motivos

    def resolver(self, ticker: str, estado: EstadoPropuesta, *, nota: str | None = None) -> None:
        """El humano promueve ('aprobada'), rechaza o retira. Append-only."""
        self._append(_Resolucion(ticker=ticker.upper(), estado=estado, nota=nota))

    def _estado_actual(self) -> dict[str, dict]:
        """Proyección: último estado por ticker (el registro + la última resolución)."""
        prop: dict[str, dict] = {}
        for e in self._eventos():
            if e.get("tipo") == "propuesta":
                prop[e["propuesta"]["ticker"].upper()] = {"estado": e["estado"], "propuesta": e["propuesta"],
                                                          "motivos": e.get("motivos", [])}
            elif e.get("tipo") == "resolucion":
                tk = e["ticker"].upper()
                if tk in prop:
                    prop[tk] = {**prop[tk], "estado": e["estado"]}
        return prop

    def en_observacion(self) -> list[dict]:
        """Propuestas que validaron y esperan la decisión del humano (no aprobadas/rechazadas/vencidas)."""
        return [v for v in self._estado_actual().values() if v["estado"] == "observacion"]

    def promover(self, ticker: str, *, alta_fn, nota: str | None = None) -> None:
        """El humano PROMUEVE una propuesta en observación al universo investible: `alta_fn(ticker, propuesta)`
        la inserta en nx_empresa (inyectable → testeable) y se marca 'aprobada' en la cola. Falla si no está
        en observación (no se promueve algo rechazado/vencido)."""
        act = self._estado_actual().get(ticker.upper())
        if not act or act["estado"] != "observacion":
            raise ValueError(f"{ticker}: no está en observación (estado={act.get('estado') if act else 'inexistente'})")
        alta_fn(ticker.upper(), act["propuesta"])
        self.resolver(ticker, "aprobada", nota=nota)

    def vencer_pendientes(self, hoy: date | None = None) -> list[str]:
        """Marca 'vencida' las que pasaron su `dias_vigencia` sin aprobarse (NUNCA se aceptan por silencio).
        Devuelve los tickers vencidos."""
        hoy = hoy or date.today()
        vencidos = []
        for e in self._eventos():
            if e.get("tipo") != "propuesta":
                continue
            tk = e["propuesta"]["ticker"].upper()
            act = self._estado_actual().get(tk, {})
            if act.get("estado") != "observacion":
                continue
            prop_fecha = datetime.fromisoformat(e["ts"]).date()
            if (hoy - prop_fecha).days > int(e["propuesta"].get("dias_vigencia", 30)):
                self.resolver(tk, "vencida", nota="sin promoción en la ventana de vigencia")
                vencidos.append(tk)
        return vencidos


# =========================================================================== CUELLOS NUEVOS (write-back al mapa)
# El agente discovery puede proponer un CUELLO que el mapa no tiene. Un agente CURADOR lo valida (es un cuello
# real, no narrativa) y, si pasa, el nodo entra al overlay del mapa (doc 76). El humano NO decide: valida un agente.

class PropuestaNodo(BaseModel):
    """Un cuello de botella candidato a entrar al mapa (lo propone discovery, lo valida el curador-agente)."""
    nombre: str
    cluster: str = "descubierto"
    factor_macro: str | None = None
    subnodos: list[str] = Field(default_factory=list)
    tesis_cuello: str                            # por qué ES un cuello (oferta restringida / pricing power / insumo crítico)
    por_que_ahora: str
    fuentes: list[str] = Field(default_factory=list)
    dias_vigencia: int = 30


def validar_nodo(p: PropuestaNodo, *, nodos_conocidos: set[str]) -> tuple[bool, list[str]]:
    """Validadores duros de un cuello nuevo (previos al curador). Dedup contra el mapa conocido."""
    motivos: list[str] = []
    if not (p.nombre or "").strip():
        motivos.append("sin nombre de cuello")
    if p.nombre.strip() in nodos_conocidos:
        motivos.append("duplicado: el cuello ya está en el mapa")
    if not (p.tesis_cuello or "").strip():
        motivos.append("sin tesis (por qué es un cuello)")
    if not (p.por_que_ahora or "").strip():
        motivos.append("sin 'por qué ahora'")
    if not [f for f in p.fuentes if (f or "").strip()]:
        motivos.append("sin fuente")
    return (len(motivos) == 0), motivos


class _RegistroNodo(BaseModel):
    tipo: Literal["propuesta_nodo"] = "propuesta_nodo"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    propuesta: PropuestaNodo
    estado: EstadoPropuesta
    motivos: list[str] = Field(default_factory=list)


class _ResolucionNodo(BaseModel):
    tipo: Literal["resolucion_nodo"] = "resolucion_nodo"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nombre: str
    estado: EstadoPropuesta
    nota: str | None = None


_COLA_NODOS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cola_nodos_v2.jsonl"


class ColaNodos:
    """Cola append-only de cuellos nuevos (mismo patrón que ColaPropuestas; clave = nombre del nodo)."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or _COLA_NODOS_PATH)

    def _append(self, ev: BaseModel) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(ev.model_dump_json() + "\n")

    def _eventos(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def registrar(self, p: PropuestaNodo, *, nodos_conocidos: set[str]) -> tuple[str, list[str]]:
        ok, motivos = validar_nodo(p, nodos_conocidos=nodos_conocidos)
        estado: EstadoPropuesta = "observacion" if ok else "rechazada"
        self._append(_RegistroNodo(propuesta=p, estado=estado, motivos=motivos))
        return estado, motivos

    def resolver(self, nombre: str, estado: EstadoPropuesta, *, nota: str | None = None) -> None:
        self._append(_ResolucionNodo(nombre=nombre, estado=estado, nota=nota))

    def _estado_actual(self) -> dict[str, dict]:
        prop: dict[str, dict] = {}
        for e in self._eventos():
            if e.get("tipo") == "propuesta_nodo":
                prop[e["propuesta"]["nombre"]] = {"estado": e["estado"], "propuesta": e["propuesta"]}
            elif e.get("tipo") == "resolucion_nodo" and e["nombre"] in prop:
                prop[e["nombre"]] = {**prop[e["nombre"]], "estado": e["estado"]}
        return prop

    def en_observacion(self) -> list[dict]:
        return [v for v in self._estado_actual().values() if v["estado"] == "observacion"]

    def promover(self, nombre: str, *, alta_fn, nota: str | None = None) -> None:
        """Agrega el cuello al mapa: `alta_fn(propuesta)` escribe el overlay y se marca 'aprobada'."""
        act = self._estado_actual().get(nombre)
        if not act or act["estado"] != "observacion":
            raise ValueError(f"{nombre}: no está en observación")
        alta_fn(act["propuesta"])
        self.resolver(nombre, "aprobada", nota=nota)


# --------------------------------------------------------------------------- los AGENTES (Sonnet + web)
# Discovery (motor de alpha) + Curador (valida los cuellos nuevos). Ambos Sonnet+web; salida por tool emisor.

PROMPT_VERSION_DISCOVERY = "discovery_v1"
_PROMPT_DISCOVERY = (Path(__file__).resolve().parent.parent.parent / "prompts" / "discovery_v1.md").read_text()
PROMPT_VERSION_CURADOR = "curador_mapa_v1"
_PROMPT_CURADOR = (Path(__file__).resolve().parent.parent.parent / "prompts" / "curador_mapa_v1.md").read_text()

# Acotado por presupuesto: discovery es el motor de alpha pero debe ser BARATO (Sonnet + pocas búsquedas).
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
WEB_SEARCH_CURADOR = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}

_S = {"type": "string"}


def _emitir_propuestas_schema() -> dict:
    # empresa que ocupa un cuello EXISTENTE: nodo_ref = el ID del nodo que le doy (encaje determinista).
    prop = {
        "type": "object",
        "properties": {
            "ticker": _S, "nodo_ref": _S, "tesis_corta": _S, "por_que_ahora": _S,
            "fuentes": {"type": "array", "items": _S},
            "market_cap": {"type": ["number", "null"]},
        },
        "required": ["ticker", "nodo_ref", "tesis_corta", "por_que_ahora", "fuentes", "market_cap"],
        "additionalProperties": False,
    }
    # cuello NUEVO que el mapa no tiene (va al curador, no trae empresas todavía).
    nodo = {
        "type": "object",
        "properties": {
            "nombre": _S, "cluster": _S, "factor_macro": {"type": ["string", "null"]},
            "subnodos": {"type": "array", "items": _S},
            "tesis_cuello": _S, "por_que_ahora": _S, "fuentes": {"type": "array", "items": _S},
        },
        "required": ["nombre", "cluster", "factor_macro", "subnodos", "tesis_cuello", "por_que_ahora", "fuentes"],
        "additionalProperties": False,
    }
    return {"type": "object",
            "properties": {"propuestas": {"type": "array", "items": prop},
                           "cuellos_nuevos": {"type": "array", "items": nodo}},
            "required": ["propuestas", "cuellos_nuevos"], "additionalProperties": False}


EMITIR_PROPUESTAS_TOOL = {
    "name": "emitir_propuestas",
    "description": ("Emití empresas (para cuellos existentes, por nodo_ref) y/o cuellos nuevos que el mapa no "
                    "tiene. Es tu única salida; llamala cuando terminaste de investigar."),
    "input_schema": _emitir_propuestas_schema(),
}

EMITIR_VEREDICTO_TOOL = {
    "name": "emitir_veredicto",
    "description": "Emití tu veredicto sobre si el cuello propuesto es real. Es tu única salida.",
    "input_schema": {
        "type": "object",
        "properties": {"aprobar": {"type": "boolean"}, "motivo": _S},
        "required": ["aprobar", "motivo"], "additionalProperties": False,
    },
}


def _norm_nodos(nodos_mapa) -> list[tuple[str, str]]:
    """Normaliza nodos_mapa a [(nombre_canonico, display)]. Acepta dicts {nombre, info} o strings."""
    out: list[tuple[str, str]] = []
    for n in (nodos_mapa or []):
        if isinstance(n, dict):
            nombre = str(n.get("nombre", "")).strip()
            out.append((nombre, str(n.get("info") or nombre)))
        else:
            out.append((str(n).strip(), str(n).strip()))
    return [(nombre, disp) for nombre, disp in out if nombre]


class AgenteDiscovery:
    """Sonnet+web: el motor de alpha. Propone EMPRESAS (que ocupan un cuello existente, por nodo_ref) y CUELLOS
    nuevos que el mapa no tiene. No decide: el caller valida/encola; el mapa y los validadores son el filtro."""

    def __init__(self, agente):
        self.ag = agente

    def explorar(self, *, universo_actual, en_observacion=None, nodos_mapa=None, foco: str = "",
                 max_propuestas: int = 6, max_tokens: int = 8192):
        universo = sorted({t.upper() for t in universo_actual})
        obs = sorted({t.upper() for t in (en_observacion or [])})
        norm = _norm_nodos(nodos_mapa)
        id_map = {f"C{i:02d}": nombre for i, (nombre, _) in enumerate(norm, 1)}
        listado = "\n".join(f"{cid}: {disp}" for cid, (nombre, disp) in zip(id_map, norm)) or \
            "(sin mapa explícito)"
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Proponé HASTA {max_propuestas} empresas nuevas (preferí pocas y buenas) y/o los cuellos que "
            f"el mapa no tenga.\n\n"
            f"=== YA EN EL UNIVERSO (NO las propongas) ===\n{', '.join(universo) or '(vacío)'}\n\n"
            f"=== YA EN OBSERVACIÓN (NO las re-propongas) ===\n{', '.join(obs) or '(ninguna)'}\n\n"
            f"=== CUELLOS DEL MAPA (cada empresa va con el nodo_ref del cuello que ocupa) ===\n{listado}\n\n"
            f"=== FOCO DE ESTA RONDA ===\n"
            f"{foco or '(sin foco: explorá donde veas un cambio estructural reciente en los cuellos)'}\n\n"
            f"Para cada empresa, poné nodo_ref = el ID (Cxx) del cuello que ocupa. Si ves un cuello que el mapa "
            f"NO tiene, proponelo en cuellos_nuevos (sin empresas todavía: sus jugadores se mapean cuando el "
            f"cuello se valide). Investigá con web_search y llamá a emitir_propuestas."
        )
        payload, fuentes, meta = self.ag.agentico(
            system=_PROMPT_DISCOVERY, user=user,
            tools=[WEB_SEARCH_TOOL, EMITIR_PROPUESTAS_TOOL],
            emisor="emitir_propuestas", max_tokens=max_tokens,
        )
        payload = payload or {}
        props: list[PropuestaEmpresa] = []
        vistos: set[str] = set(universo) | set(obs)
        for raw in (payload.get("propuestas") or []):
            if len(props) >= max_propuestas:
                break
            tk = str((raw or {}).get("ticker", "")).strip().upper()
            cuello = id_map.get(str((raw or {}).get("nodo_ref", "")).strip())  # ID → nombre canónico del nodo
            if not tk or tk in vistos or not cuello:                           # sin encaje a un nodo real → descartar
                continue
            srcs = [f for f in ((raw or {}).get("fuentes") or []) if (f or "").strip()]
            try:
                p = PropuestaEmpresa(
                    ticker=tk, cuello=cuello,
                    tesis_corta=str(raw.get("tesis_corta", "")).strip(),
                    por_que_ahora=str(raw.get("por_que_ahora", "")).strip(),
                    fuentes=srcs or list(fuentes)[:2],
                    market_cap=raw.get("market_cap"),
                )
            except Exception:  # noqa: BLE001
                continue
            vistos.add(tk)
            props.append(p)
        nodos: list[PropuestaNodo] = []
        for raw in (payload.get("cuellos_nuevos") or []):
            try:
                nodos.append(PropuestaNodo(
                    nombre=str(raw.get("nombre", "")).strip(), cluster=str(raw.get("cluster") or "descubierto"),
                    factor_macro=raw.get("factor_macro"), subnodos=list(raw.get("subnodos") or []),
                    tesis_cuello=str(raw.get("tesis_cuello", "")).strip(),
                    por_que_ahora=str(raw.get("por_que_ahora", "")).strip(),
                    fuentes=[f for f in (raw.get("fuentes") or []) if (f or "").strip()] or list(fuentes)[:2]))
            except Exception:  # noqa: BLE001
                continue
        return props, nodos, meta


class AgenteCurador:
    """Sonnet+web: valida que un cuello propuesto sea REAL (oferta restringida / pricing power / insumo
    crítico), no narrativa. Reemplaza el ok humano para agregar un nodo al mapa."""

    def __init__(self, agente):
        self.ag = agente

    def validar(self, nodo: PropuestaNodo):
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Cuello propuesto: {nodo.nombre}\nCluster: {nodo.cluster}\n"
            f"Tesis (por qué sería un cuello): {nodo.tesis_cuello}\n"
            f"Por qué ahora: {nodo.por_que_ahora}\nFuentes: {', '.join(nodo.fuentes)}\n\n"
            f"Verificá con web_search y emití el veredicto (aprobar solo si es un cuello económico real)."
        )
        payload, _fuentes, meta = self.ag.agentico(
            system=_PROMPT_CURADOR, user=user, tools=[WEB_SEARCH_CURADOR, EMITIR_VEREDICTO_TOOL],
            emisor="emitir_veredicto", max_tokens=4096,
        )
        payload = payload or {}
        return bool(payload.get("aprobar", False)), str(payload.get("motivo", "")), meta


# --------------------------------------------------------------------------- encolado (auto, sin humano)

def encolar_propuestas(cola: ColaPropuestas, props, *, ips_cfg: dict, universo_actual: set[str],
                       nodos_conocidos: set[str] | None = None, alta_fn=None) -> list[dict]:
    """Registra cada empresa (valida facts + ENCAJE EN EL MAPA). Si pasa y hay `alta_fn`, ENTRA SOLA al
    universo (el mapa valida, no el humano). Sin alta_fn, queda en observación. Devuelve el resumen por ticker."""
    out = []
    for p in props:
        estado, motivos = cola.registrar(p, ips_cfg=ips_cfg, universo_actual=universo_actual,
                                         nodos_conocidos=nodos_conocidos)
        if estado == "observacion" and alta_fn is not None:
            alta_fn(p.ticker, p)
            cola.resolver(p.ticker, "aprobada", nota="auto: validada + encaje en el mapa")
            estado = "aprobada"
        out.append({"ticker": p.ticker, "cuello": p.cuello, "estado": estado, "motivos": motivos})
    return out


def encolar_nodos(cola: ColaNodos, nodos, curador: "AgenteCurador", *, nodos_conocidos: set[str],
                  alta_fn) -> tuple[list[dict], float]:
    """Registra cada cuello nuevo (valida facts + dedup) y lo manda al CURADOR; si aprueba, entra al mapa
    (overlay) vía alta_fn. Devuelve (resumen por nodo, costo total del curador)."""
    out, costo = [], 0.0
    for n in nodos:
        estado, motivos = cola.registrar(n, nodos_conocidos=nodos_conocidos)
        veredicto = ""
        if estado == "observacion":
            aprobar, veredicto, meta = curador.validar(n)
            costo += meta.cost_usd
            if aprobar:
                cola.promover(n.nombre, alta_fn=alta_fn, nota=f"curador: {veredicto}")
                estado = "aprobada"
            else:
                cola.resolver(n.nombre, "rechazada", nota=f"curador: {veredicto}")
                estado = "rechazada"
        out.append({"nombre": n.nombre, "estado": estado, "motivos": motivos, "veredicto": veredicto})
    return out, round(costo, 6)
