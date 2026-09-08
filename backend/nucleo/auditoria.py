"""Auditoría adversarial — ¿el análisis se equivocó o se perdió algo? (completeness critic).

Un crítico ESCÉPTICO y barato re-lee el filing con los hechos ya extraídos y flaggea errores u
omisiones (un hecho marcado UNKNOWN/False que el texto contradice, un riesgo no capturado, una
contradicción). Es DISCOVERY (candidatos a revisar), NO una fuente de hechos: cada flag se
VERIFICA contra su cita (si el pasaje no existe, se descarta — no se alucina una discrepancia).

Sirve para auditar TODAS las empresas de forma sistemática y encontrar los huecos de fact_key
que afectan a todas (ej. AAOI: demanda realizada subestimada + concentración top-N no capturada).
"""
from __future__ import annotations

import json

from backend.nucleo import extractor_citado as EX
from backend.nucleo import fact_store as FS
from backend.nucleo import retrieval
from backend.services.llm import call_llm_json
from backend.utils import get_logger

log = get_logger(__name__)

_SYSTEM_AUDIT = (
    "Sos un AUDITOR ESCÉPTICO de análisis de inversión. Te doy los HECHOS que un sistema extrajo "
    "de un filing, y el TEXTO del filing. Tu trabajo es encontrar qué SE EQUIVOCÓ o SE PERDIÓ:\n"
    "(a) un hecho marcado UNKNOWN/False/0 que el texto CLARAMENTE contradice;\n"
    "(b) un RIESGO importante NO capturado (concentración de clientes top-N, dilución, dependencia "
    "de un cliente/proveedor, going concern);\n"
    "(c) una contradicción entre los hechos y el texto.\n"
    "Para cada hallazgo: el fact_key afectado, qué está mal en una frase, y la CITA VERBATIM del "
    "texto que lo prueba. Máximo 5, los más importantes. Si no encontrás nada, lista vacía.\n"
    'JSON: {"discrepancias": [{"fact_key": "...", "problema": "...", "cita": "<verbatim>"}]}'
)


def auditar_ticker(session, ticker: str, *, texto: str | None = None,
                   model: str | None = None, max_chars: int = 22000) -> list[dict]:
    """Audita el análisis de `ticker`: flaggea errores/omisiones VERIFICADOS contra la cita."""
    snap = FS.snapshot_vigente(session, ticker)
    hechos = {k: FS._dec(f.value) for k, f in snap.items()}
    if texto is None:
        c = retrieval.resolver_corpus(ticker, con_exhibits=False)
        texto = (c.primary.texto or "") if c else ""
    if not texto:
        return []
    res = call_llm_json(
        system_prompt=_SYSTEM_AUDIT,
        user_message=(f"HECHOS EXTRAÍDOS: {json.dumps(hechos, ensure_ascii=False)}\n\n"
                      f"=== TEXTO DEL FILING ===\n{texto[:max_chars]}"),
        model=model or EX.MODELO_EXTRACCION, max_tokens=1400,
        extra_metadata={"agent": "auditor", "ticker": ticker},
    )
    d = res.parsed_json if isinstance(res.parsed_json, dict) else {}
    flags = d.get("discrepancias", []) if isinstance(d, dict) else []
    # Verificar cada flag contra su cita: si el pasaje no existe en el texto, se descarta.
    nt = EX._norm(texto[:max_chars])
    verificados = []
    for fl in flags:
        if isinstance(fl, dict) and EX._buscar_span(EX._norm(fl.get("cita", "")), nt):
            verificados.append(fl)
    return verificados
