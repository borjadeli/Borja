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
                      hoy: date | None = None) -> tuple[bool, list[str]]:
    """Validadores DUROS deterministas (doc 76): sin esto no llega al humano. Liquidez NO se valida."""
    motivos: list[str] = []
    if not _ticker_valido(p.ticker):
        motivos.append(f"ticker inválido: '{p.ticker}'")
    if p.ticker.strip().upper() in {t.upper() for t in universo_actual}:
        motivos.append("duplicado: ya está en el universo")
    mc_min = float(ips_cfg.get("market_cap_min_usd", 0))
    mc_max = float(ips_cfg.get("market_cap_max_usd", 1e18))
    if p.market_cap is None:
        motivos.append("sin market cap (pendiente de verificación, no inelegible)")   # blando: a verificar
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
                  hoy: date | None = None) -> tuple[str, list[str]]:
        """Valida y registra. Devuelve (estado, motivos). Pasa → 'observacion'; falla → 'rechazada'."""
        ok, motivos = validar_propuesta(p, ips_cfg=ips_cfg, universo_actual=universo_actual, hoy=hoy)
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


# --------------------------------------------------------------------------- el AGENTE LLM (Sonnet + web)
# El motor de alpha (doc 76 §4): explora cuellos NUEVOS y produce propuestas a la cola de arriba. Es "otro
# productor" — no toca el universo ni decide nada; registrar→validar→observación→promover sigue igual.

PROMPT_VERSION_DISCOVERY = "discovery_v1"
_PROMPT_DISCOVERY = (Path(__file__).resolve().parent.parent.parent / "prompts" / "discovery_v1.md").read_text()

# Acotado por presupuesto: discovery es el motor de alpha pero debe ser BARATO (Sonnet + pocas búsquedas).
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

_S = {"type": "string"}


def _emitir_propuestas_schema() -> dict:
    prop = {
        "type": "object",
        "properties": {
            "ticker": _S, "cuello": _S, "tesis_corta": _S, "por_que_ahora": _S,
            "fuentes": {"type": "array", "items": _S},
            "market_cap": {"type": ["number", "null"]},
        },
        "required": ["ticker", "cuello", "tesis_corta", "por_que_ahora", "fuentes", "market_cap"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"propuestas": {"type": "array", "items": prop}},
            "required": ["propuestas"], "additionalProperties": False}


EMITIR_PROPUESTAS_TOOL = {
    "name": "emitir_propuestas",
    "description": ("Emití las empresas candidatas que encontraste. Es tu única salida; llamala cuando "
                    "terminaste de investigar. Pocas y bien fundadas."),
    "input_schema": _emitir_propuestas_schema(),
}


class AgenteDiscovery:
    """Sonnet+web explora cuellos nuevos y propone empresas FUERA del universo. Produce `PropuestaEmpresa`;
    NO toca la cola ni el universo (eso lo hace el caller con `encolar_propuestas`: registrar→validar→
    observación, y el humano promueve). Acotado por presupuesto (pocas búsquedas + tope de propuestas)."""

    def __init__(self, agente):
        self.ag = agente

    def explorar(self, *, universo_actual, nodos_mapa=None, foco: str = "",
                 max_propuestas: int = 6, max_tokens: int = 8192):
        universo = sorted({t.upper() for t in universo_actual})
        nodos = ", ".join(nodos_mapa or []) or "(sin mapa explícito: usá tu conocimiento de los cuellos del sector)"
        user = (
            f"Fecha de hoy: {date.today().isoformat()}\n"
            f"Proponé HASTA {max_propuestas} empresas nuevas (no más; preferí pocas y buenas).\n\n"
            f"=== YA EN EL UNIVERSO (NO las propongas) ===\n{', '.join(universo) or '(vacío)'}\n\n"
            f"=== CUELLOS YA MAPEADOS (buscá adyacencias / nodos faltantes) ===\n{nodos}\n\n"
            f"=== FOCO DE ESTA RONDA ===\n"
            f"{foco or '(sin foco: explorá donde veas un cambio estructural reciente en los cuellos)'}\n\n"
            f"Investigá con web_search (pocas búsquedas dirigidas) y llamá a emitir_propuestas."
        )
        payload, fuentes, meta = self.ag.agentico(
            system=_PROMPT_DISCOVERY, user=user,
            tools=[WEB_SEARCH_TOOL, EMITIR_PROPUESTAS_TOOL],
            emisor="emitir_propuestas", max_tokens=max_tokens,
        )
        props: list[PropuestaEmpresa] = []
        vistos: set[str] = set()
        for raw in ((payload or {}).get("propuestas") or []):
            if len(props) >= max_propuestas:
                break
            tk = str((raw or {}).get("ticker", "")).strip().upper()
            if not tk or tk in vistos:
                continue
            srcs = [f for f in ((raw or {}).get("fuentes") or []) if (f or "").strip()]
            try:
                p = PropuestaEmpresa(
                    ticker=tk, cuello=str(raw.get("cuello", "")).strip(),
                    tesis_corta=str(raw.get("tesis_corta", "")).strip(),
                    por_que_ahora=str(raw.get("por_que_ahora", "")).strip(),
                    fuentes=srcs or list(fuentes)[:2],   # fallback: las URLs que trajo web_search (procedencia)
                    market_cap=raw.get("market_cap"),
                )
            except Exception:  # noqa: BLE001 — propuesta malformada → se descarta, no tumba la ronda
                continue
            vistos.add(tk)
            props.append(p)
        return props, meta


def encolar_propuestas(cola: ColaPropuestas, props, *, ips_cfg: dict, universo_actual: set[str]) -> list[dict]:
    """Registra en la cola cada propuesta del agente (valida → observación|rechazada). Devuelve el resumen
    por ticker. El agente propone; los validadores deterministas filtran; el humano promueve."""
    out = []
    for p in props:
        estado, motivos = cola.registrar(p, ips_cfg=ips_cfg, universo_actual=universo_actual)
        out.append({"ticker": p.ticker, "estado": estado, "motivos": motivos})
    return out
