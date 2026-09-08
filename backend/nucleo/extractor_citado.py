"""Extractor citado (D) + verificador (E) — el corazón del motor de evidencia (doc 22 §7).

El LLM lee UN chunk de texto real y emite un hecho con `value + support_type + quote VERBATIM`.
El verificador (determinista, fuera del LLM) confirma que la cita existe en el texto (substring
normalizado + offsets) y, si es numérico, la contrasta contra XBRL. Si la cita no existe → el
hecho se degrada a UNKNOWN (nunca se sirve un hecho no fundado). 1 reintento de reparación.

Reglas de soporte (§2): DIRECT (el texto lo declara) · DERIVED (fórmula sobre números citados) ·
INFERRED (interpretación — no alimenta hard gates) · UNKNOWN (sin soporte). El LLM NO usa memoria.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

PROMPT_VERSION = "extractor_citado_v1"

# Extraer es LEER+CITAR, no razonar → Haiku (validado = Opus en hechos cualitativos vs. gold,
# 18× más barato). Los NÚMEROS no pasan por acá: salen de XBRL. Facts con derivación pesada
# pueden overridear a Opus. La verificación determinista guarda a cualquier modelo.
MODELO_EXTRACCION = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "Sos un EXTRACTOR DE UN HECHO de un texto de filing. Te doy el TEXTO y la PREGUNTA. "
    "Respondé SOLO con lo que el texto dice — NUNCA con conocimiento externo ni memoria.\n"
    "Reglas de `support_type`:\n"
    "- DIRECT: el texto declara el hecho explícitamente.\n"
    "- DERIVED: lo calculás con una fórmula determinista sobre números citados del texto "
    "(incluí la fórmula en `derivacion`).\n"
    "- UNKNOWN: el texto no lo dice → `value` null. NO inventes.\n"
    "`quote` DEBE ser un fragmento VERBATIM del texto (copiá EXACTO, 10 a 300 caracteres, el "
    "pasaje que sostiene el hecho). Sin cita verbatim → support_type=UNKNOWN.\n"
    'Devolvé EXACTAMENTE: {"value": <valor|null>, "support_type": "DIRECT|DERIVED|UNKNOWN", '
    '"quote": "<verbatim|null>", "derivacion": "<fórmula si DERIVED|null>"}'
)


@dataclass
class HechoCitado:
    fact_key: str
    value: object
    support_type: str
    quote: str | None
    quote_start: int | None = None
    quote_end: int | None = None
    derivacion: str | None = None
    grounded: bool = False
    xbrl_ok: bool | None = None


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = (s.replace(" ", " ").replace("’", "'").replace("‘", "'")
          .replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", s).strip().casefold()


def _buscar_span(nq: str, nt: str) -> tuple[int, int] | None:
    """Match VERBATIM SUSTANCIAL: exacto, o tolerando puntuación de borde, o un substring
    contiguo de ≥40 chars y ≥80% de la cita. Tolera el "punto de más" del modelo SIN dejar
    pasar paráfrasis (una alucinación no tiene 40+ chars contiguos reales del texto)."""
    if len(nq) < 10:
        return None
    pos = nt.find(nq)                                  # exacto
    if pos >= 0:
        return pos, pos + len(nq)
    core = nq.strip(" .,:;\"'()-–—")                   # tolerar puntuación/espacios de borde
    if len(core) >= 20:
        pos = nt.find(core)
        if pos >= 0:
            return pos, pos + len(core)
    need = max(40, int(len(nq) * 0.8))                 # substring contiguo sustancial
    if len(nq) >= need:
        for s in range(0, len(nq) - need + 1):
            p = nt.find(nq[s:s + need])
            if p >= 0:
                return p, p + need
    return None


def verificar_cita(hecho: HechoCitado, texto: str) -> HechoCitado:
    """Determinista: ¿la cita existe (verbatim sustancial) en el texto? Setea offsets y grounded.
    Sin cita fundada → degrada a UNKNOWN (fail-safe)."""
    if not hecho.quote:
        hecho.grounded = False
        hecho.support_type = "UNKNOWN"
        hecho.value = None          # UNKNOWN ⇒ sin valor (consistencia)
        return hecho
    span = _buscar_span(_norm(hecho.quote), _norm(texto))
    if span is None:
        hecho.grounded = False
        hecho.support_type = "UNKNOWN"    # cita inexistente/trivial/parafraseada → no fundado
        hecho.value = None
        return hecho
    hecho.grounded = True
    hecho.quote_start, hecho.quote_end = span
    return hecho


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def contrastar_xbrl(hecho: HechoCitado, xbrl_value: float, tol: float = 0.02) -> HechoCitado:
    """Números → contra XBRL (§7): si difieren más que tol relativo, se rechaza (XBRL manda)."""
    v = _num(hecho.value)
    if v is None:
        hecho.xbrl_ok = None
        return hecho
    base = abs(xbrl_value) if xbrl_value else 1.0
    hecho.xbrl_ok = abs(v - xbrl_value) / (base or 1.0) <= tol
    if not hecho.xbrl_ok:
        hecho.support_type = "UNKNOWN"   # texto contradice XBRL → no confiable
        hecho.value = None
    return hecho


def extraer_hecho(texto: str, *, fact_key: str, pregunta: str, model: str | None = None,
                  xbrl_value: float | None = None) -> HechoCitado:
    """Una extracción citada + verificada (1 reintento si la cita no matchea)."""
    def _una() -> HechoCitado:
        res = call_llm_json(
            system_prompt=_SYSTEM,
            user_message=f"PREGUNTA ({fact_key}): {pregunta}\n\n=== TEXTO ===\n{texto}",
            model=model or MODELO_EXTRACCION, max_tokens=800, temperature=0.0,   # leer+citar es determinista
            extra_metadata={"fact_key": fact_key, "agent": "extractor_citado",
                            "prompt_version": PROMPT_VERSION},
        )
        d = res.parsed_json if isinstance(res.parsed_json, dict) else {}
        return HechoCitado(fact_key=fact_key, value=d.get("value"),
                           support_type=(d.get("support_type") or "UNKNOWN").upper(),
                           quote=d.get("quote"), derivacion=d.get("derivacion"))

    h = verificar_cita(_una(), texto)
    if not h.grounded:                       # 1 reintento de reparación
        h = verificar_cita(_una(), texto)
    if h.grounded and xbrl_value is not None:
        h = contrastar_xbrl(h, xbrl_value)
    return h


_SYSTEM_ENTAILMENT = (
    "Sos un verificador ADVERSARIAL y ESTRICTO. Ves SOLO un pasaje y una afirmación, sin "
    "conocimiento externo ni contexto de la empresa. ¿El pasaje, POR SÍ SOLO, ESTABLECE la "
    "afirmación? Sé estricto: lenguaje genérico ('partnership', 'commitment', 'strong demand', "
    "'we expect'), un forecast o una intención NO establecen una obligación específica. Ante la "
    'duda, NO_SUPPORTS. Devolvé JSON: {"veredicto": "SUPPORTS|NOT_SUPPORTS|INSUFFICIENT", "por_que": "..."}'
)


def verificar_entailment(claim: str, quote: str | None, *, model: str | None = None) -> bool:
    """¿El pasaje SOSTIENE el claim estricto? (no solo que exista verbatim). Adversarial, barato.
    Cierra el hueco 'cita verbatim pero no entails' que infla las tiers y engaña al PM."""
    if not quote or not claim:
        return False
    res = call_llm_json(
        system_prompt=_SYSTEM_ENTAILMENT,
        user_message=f"AFIRMACIÓN: {claim}\n\nPASAJE: «{quote}»",
        model=model or MODELO_EXTRACCION, max_tokens=250, temperature=0.0,
        extra_metadata={"agent": "entailment"},
    )
    d = res.parsed_json if isinstance(res.parsed_json, dict) else {}
    return (d.get("veredicto") or "").strip().upper() == "SUPPORTS"


_SYSTEM_BATCH = _SYSTEM + (
    '\n\nMODO BATCH: te paso VARIOS hechos (una línea por fact_key). Devolvé UN objeto con TODOS, '
    'cada uno con la MISMA disciplina (cita verbatim o UNKNOWN). Formato EXACTO:\n'
    '{"facts": {"<fact_key>": {"value":..., "support_type":"DIRECT|DERIVED|UNKNOWN", '
    '"quote":"<verbatim|null>", "derivacion":"<fórmula|null>"}, ...}}'
)


def extraer_hechos_batch(texto: str, specs: list[tuple[str, str]], *, model: str | None = None,
                         xbrl: dict[str, float] | None = None) -> dict[str, HechoCitado]:
    """UNA llamada → TODOS los hechos (batch). Abarata sin tocar la fidelidad: cada hecho pasa por
    `verificar_cita` igual que la vía individual (verificación determinista, model-agnostic).

    specs: [(fact_key, pregunta), ...]. Devuelve {fact_key: HechoCitado (verificado)}.
    """
    pedido = "\n".join(f"- {fk}: {preg}" for fk, preg in specs)
    res = call_llm_json(
        system_prompt=_SYSTEM_BATCH,
        user_message=f"HECHOS A EXTRAER:\n{pedido}\n\n=== TEXTO ===\n{texto}",
        model=model or MODELO_EXTRACCION, max_tokens=2500, temperature=0.0,
        extra_metadata={"agent": "extractor_citado_batch", "prompt_version": PROMPT_VERSION,
                        "n_hechos": len(specs)},
    )
    data = res.parsed_json if isinstance(res.parsed_json, dict) else {}
    facts = data.get("facts", data) if isinstance(data, dict) else {}
    out: dict[str, HechoCitado] = {}
    for fk, _ in specs:
        d = facts.get(fk, {}) if isinstance(facts, dict) else {}
        h = HechoCitado(fact_key=fk, value=d.get("value"),
                        support_type=(d.get("support_type") or "UNKNOWN").upper(),
                        quote=d.get("quote"), derivacion=d.get("derivacion"))
        h = verificar_cita(h, texto)                        # ← MISMA verificación, por hecho
        if h.grounded and xbrl and fk in xbrl:
            h = contrastar_xbrl(h, xbrl[fk])
        out[fk] = h
    return out
