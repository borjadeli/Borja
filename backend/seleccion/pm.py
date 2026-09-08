"""Portfolio Manager — arma el mix sesgado sectorialmente (Bloque C §1).

Al final del embudo: el núcleo ya corrió y le pasa candidatas que pasaron el gate
con mérito y sizing DETERMINISTAS. El PM (LLM) elige el mix y lo sesga
sectorialmente; el operador confirma. El PM NUNCA toca un número del núcleo.

Este módulo arma la ficha del PM por candidata (con las dos señales de «caliente»
separadas), construye el prompt, llama al LLM y parsea el mix. La función
proponer_mix() acepta `llm_json` inyectado (test/operador sin gasto de API) y
GARANTIZA que el sizing del mix sale del núcleo, no del PM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent.parent / "prompts" / "pm_v1.txt"
PROMPT_VERSION = "pm_v1"


@dataclass
class FichaPM:
    """Lo que el PM ve por candidata. Tier/rank/cap vienen del núcleo y NO se tocan (doc 33/34).

    Sin `merito` cardinal (doc 33: "no hay score cardinal 0-10"): la prioridad la da el TIER (riesgo de
    capital A/B/C) + el RANK LEXICOGRÁFICO (ordinal). El PM propone tamaño DENTRO de [piso, cap]; no asigna
    un número del núcleo."""
    ticker: str
    tier_capital: str                      # A|B|C (riesgo de capital) — reemplaza el merito cardinal.
    rank: int | None                       # posición en el ranking LEXICOGRÁFICO (ordinal, no un score).
    cap: float                             # techo de sizing = min(caps); el PM propone DENTRO de [piso, cap].
    arquetipo: str
    fragilidad_porque: str                 # «Frag 2 porque cliente único >50%» (no el número pelado).
    precio_base_sin_contratos: float | None = None
    pct_opcionalidad_priceada: float | None = None
    factor_macro: str | None = None
    nodo_caliente: bool = False            # FÁCTICO (de la tabla de B). El PM lo CITA, no lo declara.
    hechos: list[str] = field(default_factory=list)


def ficha_desde_candidato(candidato, hoja, *, rank: int | None = None) -> FichaPM:
    """Compone la FichaPM (lo que ve el PM) desde el `CandidatoLex` (ranking) + la `HojaEvidencia` (números).
    Duck-typed (no acopla módulos). Tier/rank/cap salen del núcleo; el PM propone tamaño dentro de [piso, cap]
    (doc 34 §8). La evidencia viaja con la señal: se pasan la cita de demanda + flags como `hechos`."""
    frag = [f for f in (getattr(hoja, "flags", []) or [])
            if any(k in f.lower() for k in ("concent", "frag", "dilu", "runway"))]
    hechos: list[str] = []
    dq = getattr(hoja, "demanda_quote", None)
    if dq:
        hechos.append(f"demanda «{dq[:120]}»")
    hechos += list(getattr(hoja, "flags", []) or [])[:4]
    return FichaPM(
        ticker=candidato.ticker,
        tier_capital=candidato.tier_capital,
        rank=rank,
        cap=candidato.cap if candidato.cap is not None else 0.0,
        arquetipo=getattr(hoja, "arquetipo", ""),
        fragilidad_porque=frag[0] if frag else "s/d",
        precio_base_sin_contratos=getattr(hoja, "operable", None),
        pct_opcionalidad_priceada=getattr(hoja, "option_premium_pct", None),
        hechos=hechos,
    )


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def _fmt_ficha(f: FichaPM) -> str:
    cal = "CALIENTE (fáctico, tabla B)" if f.nodo_caliente else "no caliente"
    opc = f"{f.pct_opcionalidad_priceada:.0%}" if f.pct_opcionalidad_priceada is not None else "N/D"
    return (f"- {f.ticker} [{f.arquetipo}] tier={f.tier_capital} rank=#{f.rank} cap={f.cap:.0%} "
            f"| fragilidad: {f.fragilidad_porque} | opcionalidad priceada: {opc} "
            f"| factor_macro: {f.factor_macro or 'N/D'} | nodo: {cal} | hechos: {'; '.join(f.hechos) or '—'}")


def formatear_user_message(fichas: list[FichaPM], contexto: str) -> str:
    cuerpo = "\n".join(_fmt_ficha(f) for f in fichas)
    return (f"=== CONTEXTO (mercado/sectores/macro + estados de nodos) ===\n{contexto}\n\n"
            f"=== CANDIDATAS QUE PASARON EL GATE (tier/rank/cap del núcleo — NO tocar) ===\n{cuerpo}\n\n"
            f"Armá el mix sesgado sectorialmente. Separá nodo caliente (fáctico, citá) de "
            f"momentum (tu lectura, a confirmar). Devolvé el JSON pedido.")


def proponer_mix(fichas: list[FichaPM], contexto: str = "", *,
                 llm_json: dict | None = None, model: str | None = None,
                 dry_run: bool = False) -> dict | None:
    """Propone el mix. Devuelve dict con 'mix' (cada línea con el sizing del NÚCLEO
    re-inyectado, no el del PM), 'relevar_nodo', 'nota_concentracion'. None si falla.

    Garantía dura: el sizing del mix sale de las FichaPM (núcleo), no del LLM — el
    PM solo decide incluir/no y el sesgo; nunca asigna un número del núcleo.
    """
    if llm_json is None:
        res = call_llm_json(
            system_prompt=load_system_prompt(),
            user_message=formatear_user_message(fichas, contexto),
            model=model, max_tokens=4096, dry_run=dry_run,
            extra_metadata={"agent": "pm", "prompt_version": PROMPT_VERSION},
        )
        llm_json = res.parsed_json if isinstance(res.parsed_json, dict) else None
    if llm_json is None:
        return None

    cap_por_ticker = {f.ticker.upper(): f.cap for f in fichas}
    tier_por_ticker = {f.ticker.upper(): f.tier_capital for f in fichas}

    mix = []
    for linea in (llm_json.get("mix") or []):
        t = (linea.get("ticker") or "").upper()
        if t not in cap_por_ticker:
            continue  # el PM no puede inventar tickers fuera de las candidatas del núcleo.
        mix.append({
            "ticker": t,
            "incluir": bool(linea.get("incluir")),
            "razon_sectorial": linea.get("razon_sectorial", ""),
            "cita_nodo_caliente": bool(linea.get("cita_nodo_caliente")),
            "momentum_sectorial": linea.get("momentum_sectorial") or {"lectura": "", "a_confirmar": True},
            # Re-inyectados del núcleo — el PM NO los asigna (tier/cap ordinales, no un score cardinal):
            "cap_nucleo": cap_por_ticker[t],
            "tier_nucleo": tier_por_ticker[t],
        })
    return {
        "mix": mix,
        "relevar_nodo": llm_json.get("relevar_nodo") or {"pedir": False, "nodo_id": None, "motivo": ""},
        "nota_concentracion_factor_macro": llm_json.get("nota_concentracion_factor_macro", ""),
    }
