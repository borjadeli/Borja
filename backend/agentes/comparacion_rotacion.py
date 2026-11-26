"""P1 (doc 91 §8, review-2 IA1+IA2) — COMPARACIÓN antes de rotar. TRES estados (el bug de la review-1 era binario:
una venta a caja con la banda de A desconocida caía en BLOQUEADA = permanente → el pre_revenue quedaba atrapado para
siempre):

  PERMITIDA     la comparación es VÁLIDA → el PM decide el MÉRITO (atributos económicos compensatorios).
  BLOQUEADA     inválida CONOCIDA (fail-closed): destino B sin verificar / dossier viejo / banda inválida, o B
                DOMINADA (peor-o-igual en banda+evidencia+bear → no hay mérito posible que compensar).
  INDETERMINADA falta info para decidir (banda/elegibilidad de A desconocida) → el permiso lo DIFIERE (temporal),
                no lo bloquea. Reducir riesgo con info faltante difiere; nunca atrapa en la posición.

El MÉRITO económico NO lo veta el código (mata la power-law: una B con E[R] 137% vs 25% pero bear más severo es
VÁLIDA). SUPERVIVENCIA/liquidez/concentración sí son no-compensatorias, pero las aplica el IPS aguas arriba.
Determinista, $0.
"""
from __future__ import annotations

_BANDAS = ("COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE")
_BANDA_ORD = {"RECORTE": 0, "MANTENER": 1, "COMPRA": 2, "COMPRA_FUERTE": 3}
_EV_ORD = {"FAIL": 0, "REVIEW": 1, "PASS": 2}
_BEAR_ORD = {"leve": 0, "media": 1, "severa": 2}


def _dominada(a: dict, b: dict) -> bool:
    """¿B es peor-o-igual que A en TODAS las dimensiones (banda, evidencia, bear) y estrictamente peor en alguna?
    Entonces no hay mérito posible que compensar → se bloquea. Si falta alguna dimensión, NO se afirma dominancia."""
    try:
        ba, bb = _BANDA_ORD[a["banda"]], _BANDA_ORD[b["banda"]]
        ea, eb = _EV_ORD[(a.get("verificacion") or "").upper()], _EV_ORD[(b.get("verificacion") or "").upper()]
        ra, rb = _BEAR_ORD[a["bear_severidad"]], _BEAR_ORD[b["bear_severidad"]]
    except KeyError:
        return False
    no_mejor = bb <= ba and eb <= ea and rb >= ra       # B no supera a A en ninguna
    algo_peor = bb < ba or eb < ea or rb > ra           # y es estrictamente peor en al menos una
    return no_mejor and algo_peor


def _venta_a_caja(a: dict) -> tuple[str, list[str]]:
    """A→caja: válida solo si A perdió el capital por una razón CLARA; desconocida → INDETERMINADA (difiere)."""
    if a.get("flag_alta_no_opera"):
        return "PERMITIDA", ["flag ALTA respondido no_opera"]
    if a.get("banda") == "RECORTE":
        return "PERMITIDA", ["A en RECORTE"]
    # pre_revenue que PERDIÓ la elegibilidad de opcionalidad (tesis caída) → legítimo ir a caja.
    if a.get("arquetipo") == "pre_revenue" and a.get("elegible_opcionalidad") is False:
        return "PERMITIDA", ["pre_revenue perdió la elegibilidad de opcionalidad (tesis caída)"]
    # perdió elegibilidad por una razón CONOCIDA (p.ej. REVIEW ruidoso) → TRANSICIÓN, no venta a caja.
    if a.get("no_elegible_tier"):
        return "BLOQUEADA", ["A perdió elegibilidad por una razón conocida (REVIEW ruidoso) → TRANSICIÓN, no caja"]
    if a.get("banda") in _BANDAS:                 # banda conocida y sana (MANTENER/COMPRA…) → sin razón de caja
        return "BLOQUEADA", ["A no está en RECORTE ni perdió elegibilidad — no hay razón para vender a caja"]
    return "INDETERMINADA", ["la banda/elegibilidad de A es desconocida — falta info (diferir, no atrapar)"]


def comparar_rotacion(a: dict, b: dict) -> tuple[str, list[str]]:
    if b.get("es_caja"):
        return _venta_a_caja(a)

    # ── Rotación A→B: VALIDEZ de la comparación (fail-closed). El mérito lo decide el PM. ──
    motivos: list[str] = []
    if (b.get("verificacion") or "").upper() not in ("PASS", "REVIEW"):
        motivos.append("destino B sin verificación válida (FAIL o ausente)")
    if b.get("nulls_portantes"):
        motivos.append("B tiene nulls portantes")
    if not b.get("dossier_del_ciclo", False):                 # fail-closed: debe ser del ciclo explícitamente
        motivos.append("el dossier de B no es del ciclo")
    if a.get("banda") not in _BANDAS or b.get("banda") not in _BANDAS:
        motivos.append("banda de A o B desconocida/inválida — comparación inválida (no se premia la ausencia de info)")
    if motivos:
        return "BLOQUEADA", motivos
    if _dominada(a, b):
        return "BLOQUEADA", ["B está DOMINADA por A (peor o igual en banda, evidencia y bear) — sin mérito que compensar"]
    return "PERMITIDA", ["comparación válida — el MÉRITO lo decide el PM (atributos económicos compensatorios)"]
