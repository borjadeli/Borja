"""Auditoría INDEPENDIENTE del gold set de contratos (Bloque 2, doc 80 §E).

El gold set lo etiquetó el asistente (`etiquetado.por == "assistant"`). Medir el
parser contra esas etiquetas sería CIRCULAR si nadie las verifica de forma
independiente. Este script cierra ese hueco SIN involucrar al operador:

  1. Un **Verificador** (Haiku) re-etiqueta cada contrato A CIEGAS: ve solo el
     excerpt del Item 1.01, NO ve mi etiqueta.
  2. Se compara verificador vs etiqueta original → `coincide` / `diverge`.
  3. Las **divergencias escalan al Auditor** (Sonnet) que dirime leyendo el
     excerpt + ambas etiquetas y emite el veredicto final.

Usa `Agente.estructurado` (la misma vía del comité: json_schema estricto), no el
`call_llm_json` viejo. Salida: reescribe `auditoria` en cada entrada + resumen de
acuerdo. El operador NO participa (decisión 2026-11-16: "yo no quiero chequear
nada; que lo chequee el analista, el pm, el auditor o un nuevo agente").

Uso:
    .venv/bin/python -m ops.auditar_gold_contratos [--verif MODELO] [--auditor MODELO]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from backend.agentes.base import Agente

GOLD = Path("tests/gold_contratos/gold_contratos.json")

VERIF_DEFAULT = "claude-haiku-5-5"      # barato: clasificación de 1 documento
AUDITOR_DEFAULT = "claude-sonnet-5-5"   # dirime divergencias (más fuerte)

SCHEMA_VERIF = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "tipo", "razon"],
    "properties": {
        "label": {"type": "string", "enum": ["firme", "condicional", "no_cuenta"]},
        "tipo": {"type": "string"},
        "razon": {"type": "string"},
    },
}
SCHEMA_AUDITOR = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "razon", "a_favor_de"],
    "properties": {
        "label": {"type": "string", "enum": ["firme", "condicional", "no_cuenta"]},
        "razon": {"type": "string"},
        "a_favor_de": {"type": "string", "enum": ["original", "verificador", "ninguno"]},
    },
}

SYS_VERIF = """Sos un Verificador financiero. Clasificás un acuerdo material (SEC 8-K, Item 1.01)
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
razon: 1 frase citando qué del texto lo define. NO inventes cifras que no estén en el texto."""

SYS_AUDITOR = """Sos el Auditor. Dos etiquetadores difieren sobre un acuerdo 8-K Item 1.01.
Leé el texto y dirimí cuál etiqueta es correcta, o proponé una tercera.
Criterio: "firme"/"condicional" SOLO si la empresa COBRA ingresos bajo el acuerdo. Financiamiento,
M&A, gobierno corporativo y contratos donde la empresa paga son "no_cuenta".
a_favor_de: "original" | "verificador" | "ninguno" (si proponés una tercera)."""


def _msg(e: dict) -> str:
    return f"Items: {e.get('items')}\nFecha: {e.get('fecha')}\n\nExcerpt del filing:\n{e.get('excerpt','')}"


def auditar(verif_model: str = VERIF_DEFAULT, auditor_model: str = AUDITOR_DEFAULT) -> dict:
    d = json.loads(GOLD.read_text())
    verif = Agente("verificador-gold", "gold-v1", verif_model)
    auditor = Agente("auditor-gold", "gold-v1", auditor_model)
    agree: Counter = Counter()
    costo = 0.0
    divergencias = []

    for tk, ents in d["nombres"].items():
        for e in ents:
            original = e.get("label")
            vj, mv = verif.estructurado(system=SYS_VERIF, user=_msg(e),
                                        payload_schema=SCHEMA_VERIF, max_tokens=512)
            costo += mv.cost_usd
            vlabel = vj.get("label")
            coincide = (vlabel == original)
            aud = None
            if not coincide:
                aj, ma = auditor.estructurado(
                    system=SYS_AUDITOR,
                    user=_msg(e) + f"\n\nEtiqueta ORIGINAL: {original}\nEtiqueta VERIFICADOR: {vlabel}",
                    payload_schema=SCHEMA_AUDITOR, max_tokens=512)
                costo += ma.cost_usd
                aud = aj
                divergencias.append({"ticker": tk, "accession": e.get("accession"),
                                     "original": original, "verificador": vlabel,
                                     "auditor": aj.get("label"), "razon": aj.get("razon")})
            e["auditoria"] = {
                "verificador": {"label": vlabel, "razon": vj.get("razon"), "modelo": verif_model},
                "coincide": coincide,
                "auditor": aud,  # None si coincidió
            }
            agree["coincide" if coincide else "divergencia"] += 1

    d["etiquetado"]["pendiente_auditoria"] = False
    d["etiquetado"]["auditado_por"] = {"verificador": verif_model, "auditor": auditor_model,
                                       "operador": "excluido (decisión 2026-11-16)"}
    d["etiquetado"]["metodo"] = ("etiqueta asistente + verificación ciega independiente (agente); "
                                 "divergencias dirimidas por el Auditor")
    GOLD.write_text(json.dumps(d, ensure_ascii=False, indent=2))

    print(f"acuerdo: {dict(agree)}  ·  costo ${costo:.4f}")
    if divergencias:
        print(f"\n{len(divergencias)} divergencia(s) dirimidas por el Auditor:")
        for x in divergencias:
            print(f"  {x['ticker']} {x['accession']}: orig={x['original']} verif={x['verificador']} "
                  f"→ auditor={x['auditor']} ({x['razon']})")
    return {"acuerdo": dict(agree), "costo": costo, "divergencias": divergencias}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verif", default=VERIF_DEFAULT)
    ap.add_argument("--auditor", default=AUDITOR_DEFAULT)
    args = ap.parse_args()
    auditar(verif_model=args.verif, auditor_model=args.auditor)
