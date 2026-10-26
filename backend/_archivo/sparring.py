"""Sparring — segundo LLM fresco que ataca el mix del PM (Bloque C §2).

El PM es el único punto del sistema con criterio blando sin contrapeso
determinista; el sparring es su único adversario. Poder de repregunta, SIN veto,
SIN estado, SIN score. Cierra en HUECOS-SOBRE-LA-MESA para el operador, NUNCA en
consenso. Es fresco a propósito: no recibe las fichas detalladas.

Disparadores PESADOS (corre por DEFAULT salvo skip explícito, traspaso §7-C):
  - deploy grande (posición cerca del techo 40%),
  - choque del criterio del PM contra un dato duro del núcleo (opcionalidad
    priceada alta, factor_macro sobreconcentrado, momentum contra un trigger),
  - a pedido del operador.
El liviano es a pedido.
"""
from __future__ import annotations

from pathlib import Path

from backend.seleccion.constantes import TECHO_DEPLOY_SPARRING, UMBRAL_OPCIONALIDAD_SPARRING
from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent.parent / "prompts" / "sparring_v1.txt"
PROMPT_VERSION = "sparring_v1"


def debe_correr_pesado(mix: list[dict], *, factor_macro_sobreconcentrado: bool = False,
                       pedido_operador: bool = False) -> dict:
    """¿El sparring pesado corre por default? (traspaso §7-C: corre salvo skip).
    Devuelve {corre, motivos}."""
    motivos: list[str] = []
    for linea in mix:
        if not linea.get("incluir"):
            continue
        if (linea.get("sizing_nucleo") or 0) >= TECHO_DEPLOY_SPARRING:
            motivos.append(f"{linea['ticker']}: deploy grande ({linea['sizing_nucleo']:.0%} ≥ techo)")
        opc = linea.get("opcionalidad_priceada")
        if opc is not None and opc >= UMBRAL_OPCIONALIDAD_SPARRING:
            motivos.append(f"{linea['ticker']}: opcionalidad priceada alta ({opc:.0%})")
    if factor_macro_sobreconcentrado:
        motivos.append("factor_macro sobreconcentrado entre las posiciones")
    if pedido_operador:
        motivos.append("pedido del operador")
    return {"corre": bool(motivos), "motivos": motivos}


def _resumen_mix(mix: list[dict]) -> str:
    incluidas = [l for l in mix if l.get("incluir")]
    return "\n".join(
        f"- {l['ticker']} sizing={l.get('sizing_nucleo', 0):.0%} "
        f"sector={l.get('razon_sectorial', '')[:60]}" for l in incluidas
    ) or "(mix vacío)"


def atacar_mix(mix: list[dict], contexto: str = "", *, llm_json: dict | None = None,
               model: str | None = None, dry_run: bool = False) -> dict | None:
    """El sparring ataca el RESUMEN del mix (no las fichas detalladas). Devuelve
    {huecos, concentracion_observada, cierre}. Sin veto/estado/score."""
    if llm_json is None:
        res = call_llm_json(
            system_prompt=PROMPT_FILE.read_text(encoding="utf-8"),
            user_message=(f"=== RESUMEN DEL MIX DEL PM ===\n{_resumen_mix(mix)}\n\n"
                          f"=== CONTEXTO DE SECTORES ===\n{contexto}\n\n"
                          f"Atacá omisiones y concentraciones. Cerrá en huecos, NUNCA en consenso."),
            model=model, max_tokens=2048, dry_run=dry_run,
            extra_metadata={"agent": "sparring", "prompt_version": PROMPT_VERSION},
        )
        llm_json = res.parsed_json if isinstance(res.parsed_json, dict) else None
    if llm_json is None:
        return None
    # El sparring no decide: solo expone huecos. Se descarta cualquier campo de veto/score.
    return {
        "huecos": llm_json.get("huecos") or [],
        "concentracion_observada": llm_json.get("concentracion_observada", ""),
        "cierre": "huecos sobre la mesa para el operador (sin veto, sin consenso)",
    }
