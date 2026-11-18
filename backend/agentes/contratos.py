"""Parser de contratos (Bloque 2, doc 80 §D/§E · r9a #3) — clasifica un 8-K Item 1.01.

Hallazgo del gold set (35 filings, 2026-11): el Item 1.01 ("entry into a material definitive
agreement") está DOMINADO por financiamiento (ATM/notas/créditos) y M&A; solo ~6% son contratos
de INGRESOS/offtake (y tienden a ser de gobierno). Por eso el parser primero FILTRA "¿es revenue?"
antes de dar señal.

Dos piezas:
- `clasificar_contrato(excerpt, ...)`: Verificador (Haiku) → {label, tipo, contraparte, monto}. Mismo
  prompt y schema que la auditoría del gold set (`ops/auditar_gold_contratos.py`), que midió 35/35 de
  acuerdo con las etiquetas humanas → es el parser medido.
- `bonus_contrato(label, dias)`: traduce un contrato FRESCO firme/condicional en un bonus aditivo al
  score de oportunidad (doc 80 §D: score = (V·M·C)^⅓·A + bonus). Decae con la antigüedad; 0 si no cuenta.

El determinismo pre-filtra (solo Item 1.01 es candidato) para no gastar LLM en lo que no aplica.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.agentes.base import Agente

VERIF_MODEL = "claude-haiku-5-5"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "tipo", "contraparte", "monto_usd", "razon"],
    "properties": {
        "label": {"type": "string", "enum": ["firme", "condicional", "no_cuenta"]},
        "tipo": {"type": "string"},
        "contraparte": {"type": "string"},    # "" si no aparece
        "monto_usd": {"type": "number"},       # 0 si no aparece
        "razon": {"type": "string"},
    },
}

SYS = """Sos un Verificador financiero. Clasificás un 8-K (Item 1.01 acuerdo definitivo, o 7.01/8.01 anuncio)
según si es un CONTRATO DE INGRESOS/OFFTAKE para la empresa que reporta.

label:
- "firme": contrato vinculante de VENTA/OFFTAKE/suministro donde la empresa COBRA ingresos,
  con precio o volumen comprometido (incluye price floor de gobierno, offtake a plazo fijo).
- "condicional": contrato de ingresos cuyo cumplimiento depende de opciones/hitos/aprobaciones
  futuras (p.ej. fases dependientes de ejercicio de opción del comprador).
- "no_cuenta": NO es un contrato de ingresos de la empresa. Incluye financiamiento (ATM, notas
  convertibles, créditos, PIPE, underwriting), M&A (fusión, adquisición), gobierno corporativo
  (poison pill, rights agreement) y contratos donde la empresa PAGA (EPC, construcción, capex).

tipo: etiqueta corta (financiamiento | m&a | gobierno_offtake | gobierno_price_floor | costo | corporativo | venta_privada).
contraparte: la otra parte, "" si no aparece. monto_usd: número en USD, 0 si no aparece.
razon: 1 frase citando qué del texto lo define. NO inventes cifras que no estén en el texto."""

# Bonus al score por un contrato FRESCO de ingresos (doc 80 §D). Decae a 0 pasados `VENTANA_DIAS`.
BONUS_FIRME = 0.05
BONUS_CONDICIONAL = 0.02
VENTANA_DIAS = 90


@dataclass
class ContratoClasificado:
    label: str                 # firme | condicional | no_cuenta
    tipo: str
    contraparte: str
    monto_usd: float
    razon: str
    cuenta: bool               # label in (firme, condicional)


def clase_item(items: str | list | None) -> str | None:
    """Pre-filtro determinista → qué clase de candidato es el 8-K (P1-5, doc 85):
    - "definitivo": Item 1.01 (material definitive agreement) → puede ser 'firme'.
    - "anuncio": Item 7.01 (Reg FD) / 8.01 (Other Events) → press-release/aviso; a lo sumo 'condicional'
      (no es un acuerdo vinculante, aunque mencione un contrato o monto).
    - None: ningún ítem de contrato → no se gasta LLM."""
    if not items:
        return None
    s = ",".join(items) if isinstance(items, (list, tuple)) else str(items)
    if "1.01" in s:
        return "definitivo"
    if "7.01" in s or "8.01" in s:
        return "anuncio"
    return None


def es_item_contrato(items: str | list | None) -> bool:
    """Candidato a contrato de ingresos: Item 1.01 (definitivo) o 7.01/8.01 (anuncio). Evita gastar LLM en el resto."""
    return clase_item(items) is not None


def clasificar_contrato(excerpt: str, *, items: str | list | None = None, fecha: str | None = None,
                        modelo: str = VERIF_MODEL, cliente=None) -> ContratoClasificado:
    """Clasifica un filing. Sin ítem de contrato → no_cuenta sin LLM. Si lo es → Verificador (Haiku). Un
    7.01/8.01 (anuncio) se CAPEA a 'condicional' aunque el LLM diga 'firme': sin el 1.01 no hay acuerdo
    definitivo, es un aviso (P1-5)."""
    clase = clase_item(items)
    if clase is None:
        return ContratoClasificado("no_cuenta", "no_contrato", "", 0.0, "no es ítem de contrato (1.01/7.01/8.01)",
                                    cuenta=False)
    ag = Agente("parser-contratos", "contratos-v1", modelo, cliente=cliente)
    nota = "" if clase == "definitivo" else ("\n\n[ES UN 7.01/8.01 — ANUNCIO/PRESS RELEASE, NO un acuerdo "
                                             "definitivo: a lo sumo 'condicional', NUNCA 'firme'.]")
    user = f"Items: {items}\nFecha: {fecha}{nota}\n\nExcerpt del filing:\n{excerpt}"
    j, _meta = ag.estructurado(system=SYS, user=user, payload_schema=SCHEMA, max_tokens=1024)
    label = j.get("label", "no_cuenta")
    razon = j.get("razon", "")
    if clase == "anuncio" and label == "firme":          # cap duro: un aviso no es firme aunque el LLM se entusiasme
        label = "condicional"
        razon = f"[capeado a condicional: es 7.01/8.01, no 1.01] {razon}"
    return ContratoClasificado(
        label=label, tipo=j.get("tipo", ""), contraparte=j.get("contraparte", "") or "",
        monto_usd=float(j.get("monto_usd") or 0.0), razon=razon,
        cuenta=label in ("firme", "condicional"))


@dataclass
class ContratoFresco:
    ticker: str
    label: str                 # firme | condicional
    dias_desde: float
    bonus: float
    contraparte: str
    monto_usd: float
    url: str
    fecha: str


def detectar_contratos_universo(tickers: list[str], *, filings_fn=None, excerpt_fn=None,
                                hoy=None, modelo: str = VERIF_MODEL, cliente=None) -> dict[str, ContratoFresco]:
    """Feed → parser (r9a #3): para cada ticker busca 8-K con Item 1.01 dentro de la ventana (VENTANA_DIAS),
    clasifica cada uno y QUEDA con el contrato de ingresos (firme/condicional) MÁS FRESCO. Devuelve
    ticker→ContratoFresco (solo los que cuentan). `filings_fn`/`excerpt_fn` son inyectables para test.
    Gasta LLM solo en los 8-K 1.01 reales (el pre-filtro ya descartó el resto)."""
    from datetime import date, datetime
    if filings_fn is None:
        from backend.services.edgar import get_recent_filings
        filings_fn = lambda tk: get_recent_filings(tk, tipos=("8-K",), dias=VENTANA_DIAS)  # noqa: E731
    if excerpt_fn is None:
        from ops.gold_contratos import _excerpt
        excerpt_fn = _excerpt
    hoy = hoy or date.today()
    out: dict[str, ContratoFresco] = {}
    for tk in tickers:
        mejor: ContratoFresco | None = None
        for f in filings_fn(tk):
            items = getattr(f, "items", None)
            if not es_item_contrato(items):
                continue
            fecha_dt = getattr(f, "fecha", None)
            fstr = fecha_dt.date().isoformat() if isinstance(fecha_dt, datetime) else str(fecha_dt or "")
            try:
                dias = (hoy - (fecha_dt.date() if isinstance(fecha_dt, datetime) else date.fromisoformat(fstr))).days
            except Exception:
                continue
            if dias < 0 or dias > VENTANA_DIAS:
                continue
            c = clasificar_contrato(excerpt_fn(f.url), items=items, fecha=fstr, modelo=modelo, cliente=cliente)
            if not c.cuenta:
                continue
            b = bonus_contrato(c.label, dias)
            if b <= 0:
                continue
            cf = ContratoFresco(tk.upper(), c.label, float(dias), b, c.contraparte, c.monto_usd,
                                getattr(f, "url", ""), fstr)
            if mejor is None or cf.dias_desde < mejor.dias_desde:
                mejor = cf
        if mejor is not None:
            out[tk.upper()] = mejor
    return out


def bonus_contrato(label: str | None, dias_desde: float | None) -> float:
    """Bonus aditivo por un contrato de ingresos FRESCO. Firme > condicional; decae lineal a 0 en VENTANA_DIAS.
    0 si no cuenta, sin fecha, o fuera de ventana. NO es un multiplicador del size (doc 80: el contrato aporta
    al RANKING de oportunidad, nunca agranda el peso)."""
    base = BONUS_FIRME if label == "firme" else BONUS_CONDICIONAL if label == "condicional" else 0.0
    if base == 0.0 or dias_desde is None or dias_desde < 0 or dias_desde > VENTANA_DIAS:
        return 0.0
    decay = 1.0 - (dias_desde / VENTANA_DIAS)
    return round(base * decay, 4)
