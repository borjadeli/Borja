"""P1 (doc 91 §7, blueprint IA2 §5) — COMPARACIÓN antes de rotar. MODO SOMBRA: el código llena A y B desde los
dossiers; el PM solo escribe el argumento. Se rota SOLO si se cumplen las TRES condiciones (no compensatorio):
evidencia + margen + riesgo. Ante empate → se mantiene A (la carga de la prueba recae en la TRANSACCIÓN). Cada
rotación PERMITIDA alimenta el contrafactual A-vs-B (P2.1, ya implementado). Determinista, $0.

Caso IESC→EME de la corrida: B=EME no tenía dossier → falla la condición de evidencia → BLOQUEADA.
"""
from __future__ import annotations

_VERIF_ORD = {"FAIL": 0, "REVIEW": 1, "PASS": 2}
_BANDA_ORD = {"RECORTE": 0, "MANTENER": 1, "COMPRA": 2, "COMPRA_FUERTE": 3}
_SEV_ORD = {"leve": 0, "media": 1, "severa": 2}


def comparar_rotacion(a: dict, b: dict) -> tuple[str, list[str]]:
    """(resultado, motivos). `a`/`b` traen verificacion, banda, bear_severidad, nulls_portantes, dossier_del_ciclo.
    Para una venta a caja, `b={'es_caja': True}` y se evalúa la regla de caja sobre A."""
    # Venta a CAJA: válida solo si A ya no merece el capital (RECORTE / no elegible / flag ALTA 'no opera').
    if b.get("es_caja"):
        if a.get("banda") == "RECORTE" or a.get("no_elegible_tier") or a.get("flag_alta_no_opera"):
            return "PERMITIDA", ["venta a caja: A en RECORTE / no elegible / flag ALTA respondido no_opera"]
        return "BLOQUEADA", ["venta a caja sin motivo válido: A no está en RECORTE ni perdió elegibilidad"]

    motivos: list[str] = []
    # 1. Evidencia: verif(B) >= verif(A), sin nulls portantes en B, dossier de B del ciclo.
    if _VERIF_ORD.get((b.get("verificacion") or "").upper(), 0) < _VERIF_ORD.get((a.get("verificacion") or "").upper(), 0):
        motivos.append("evidencia: verificación de B peor que la de A")
    if b.get("nulls_portantes"):
        motivos.append("evidencia: B tiene nulls portantes")
    if not b.get("dossier_del_ciclo", True):
        motivos.append("evidencia: el dossier de B no es del ciclo")
    # 2. Margen: banda(B) al menos UN escalón por encima de banda(A).
    if _BANDA_ORD.get(b.get("banda"), -1) < _BANDA_ORD.get(a.get("banda"), -1) + 1:
        motivos.append("margen: la banda de B no está ≥1 escalón sobre la de A")
    # 3. Riesgo: bear de B no más severo que el de A.
    if _SEV_ORD.get(b.get("bear_severidad"), 9) > _SEV_ORD.get(a.get("bear_severidad"), 0):
        motivos.append("riesgo: el bear de B es más severo que el de A")

    return ("PERMITIDA", []) if not motivos else ("BLOQUEADA", motivos)
