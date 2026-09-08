"""Registro de decisiones / ledger de rechazos (doc 40 Bloque 0.1 · doc 39 §3) — el instrumento anti-ceguera.

Registra TODA decisión (comprada Y rechazada) con su regla exacta, precio y fecha, para medir DESPUÉS el
retorno forward. Sin esto, un sistema determinista solo ve que sus posiciones se comportaron razonablemente y
NUNCA detecta los falsos negativos — los 10x que rechazó. Este único artefacto habría cazado los dos bugs
(g=0, r=15%) automáticamente. Determinista, versionado, sin LLM. El objetivo NO es minimizar errores: es
comprar suficientes outliers para la cola derecha, limitando cuánto cuesta equivocarse — y para saber si lo
estamos logrando hay que medir lo que NO compramos.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ledger_decisiones.json"

# Clases de decisión agrupadas por si el sistema COMPRARÍA o RECHAZARÍA (para el diagnóstico de separación).
# El ledger es agnóstico al esquema exacto de estados (que va a cambiar con el rebalanceo); estas listas se
# actualizan a mano y lo desconocido cae en "otros" (no rompe).
CLASES_COMPRA = {"COVERED", "STRETCH", "UNDERWRITTEN", "PROBE", "HARD_EVIDENCE", "ADMIT_PROBE"}
CLASES_RECHAZO = {"NON_UNDERWRITABLE", "REJECT", "DESCARTE", "OPTION_PRICED", "PASS", "HURDLE_FAIL"}


@dataclass
class Decision:
    """Una decisión FECHADA sobre un nombre. `estado` y `reason_code` capturan QUÉ se decidió y POR QUÉ regla —
    para poder atribuir después un falso negativo a dato / parámetro / reference-class / juicio (doc 39 §3)."""
    ticker: str
    fecha: str                     # ISO (fecha de la decisión) — se pasa desde afuera (no Date.now)
    precio: float                  # precio al momento de la decisión (para el retorno forward)
    estado: str                    # COVERED | OPTION_PRICED | NON_UNDERWRITABLE | REJECT | CARRIL | DESCARTE | ...
    reason_code: str = ""          # la regla EXACTA que produjo el estado (auditable)
    arquetipo: str = ""
    sector: str = ""
    politica_version: str = ""
    politica_hash: str = ""


def _clave(d: dict) -> tuple:
    return (d["ticker"], d["fecha"], d.get("politica_version", ""))


def _cargar(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _guardar(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def registrar(decisiones: list[Decision], *, path: Path = LEDGER_PATH) -> int:
    """Agrega decisiones al ledger, DEDUP por (ticker, fecha, versión de política). Devuelve cuántas NUEVAS se
    escribieron. Idempotente: re-registrar el mismo snapshot no duplica."""
    data = _cargar(path)
    vistas = {_clave(d) for d in data}
    nuevas = 0
    for dec in decisiones:
        d = asdict(dec)
        if _clave(d) in vistas:
            continue
        data.append(d)
        vistas.add(_clave(d))
        nuevas += 1
    if nuevas:
        _guardar(path, data)
    return nuevas


def _dias(desde: str, hasta: str) -> int | None:
    """Días entre dos fechas ISO (solo la parte YYYY-MM-DD). None si no parsea."""
    from datetime import date
    try:
        a = date.fromisoformat(desde[:10])
        b = date.fromisoformat(hasta[:10])
        return (b - a).days
    except Exception:
        return None


def marcar_forward(precios_actuales: dict[str, float], fecha_actual: str,
                   *, path: Path = LEDGER_PATH) -> list[dict]:
    """Para cada decisión registrada, computa el retorno forward (`precio_actual/precio_decisión − 1`) y los
    días transcurridos. SOLO LECTURA (no muta el ledger). Nombres sin precio actual → retorno None."""
    out = []
    for d in _cargar(path):
        p_act = precios_actuales.get(d["ticker"])
        p0 = d.get("precio")
        ret = (p_act / p0 - 1.0) if (p_act and p0 and p0 > 0) else None
        out.append({**d, "precio_actual": p_act, "retorno_fwd": ret,
                    "dias": _dias(d["fecha"], fecha_actual)})
    return out


def _resumen(rets: list[float]) -> dict:
    if not rets:
        return {"n": 0, "media": None, "mediana": None, "min": None, "max": None}
    xs = sorted(rets)
    n = len(xs)
    mediana = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return {"n": n, "media": round(sum(xs) / n, 4), "mediana": round(mediana, 4),
            "min": round(xs[0], 4), "max": round(xs[-1], 4)}


def metricas_por_clase(precios_actuales: dict[str, float], fecha_actual: str,
                       *, path: Path = LEDGER_PATH) -> dict:
    """Diagnóstico de SEPARACIÓN (doc 39 §3): ¿las clases que COMPRARÍAMOS superan a las que RECHAZARÍAMOS en
    retorno forward? Si no separan, el frame no discrimina — y eso es la señal de ceguera que buscamos. Agrega
    por `estado`, y arma el contraste compra-vs-rechazo. (Al principio, con pocos días, es ruido — es un
    instrumento que gana valor con el tiempo.)"""
    marcados = [m for m in marcar_forward(precios_actuales, fecha_actual, path=path) if m["retorno_fwd"] is not None]
    por_estado: dict[str, list[float]] = {}
    compra, rechazo = [], []
    for m in marcados:
        por_estado.setdefault(m["estado"], []).append(m["retorno_fwd"])
        if m["estado"] in CLASES_COMPRA:
            compra.append(m["retorno_fwd"])
        elif m["estado"] in CLASES_RECHAZO:
            rechazo.append(m["retorno_fwd"])
    r_compra, r_rechazo = _resumen(compra), _resumen(rechazo)
    sep = (r_compra["media"] - r_rechazo["media"]) if (r_compra["media"] is not None
                                                       and r_rechazo["media"] is not None) else None
    return {
        "por_estado": {k: _resumen(v) for k, v in sorted(por_estado.items())},
        "compra": r_compra, "rechazo": r_rechazo,
        "separacion_media": round(sep, 4) if sep is not None else None,
        "total_marcadas": len(marcados),
    }


def desde_candidatos(candidatos, precios: dict[str, float], fecha: str) -> list[Decision]:
    """Convierte una lista de `CandidatoLex` (shadow) + precios en `Decision`s fechadas, usando la clasificación
    de 2 ejes como estado y el reason code del sizing. Puente para snapshotear el universo del cutover al ledger."""
    from backend.nucleo import politica
    from backend.nucleo.ranking_lexicografico import clasificacion_2ejes
    sello = politica.sello()
    out = []
    for c in candidatos:
        p = precios.get(c.ticker)
        if not p:
            continue
        cls = clasificacion_2ejes(c)
        out.append(Decision(
            ticker=c.ticker, fecha=fecha, precio=p,
            estado=cls["eje_evidencia"], reason_code=f"{cls['eje_valuacion']}/{c.cap_reason}",
            arquetipo=c.arquetipo, politica_version=sello["politica_version"],
            politica_hash=sello["politica_hash"]))
    return out
