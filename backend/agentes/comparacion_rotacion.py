"""P1 (doc 91 §8, review IA2 §1.6) — COMPARACIÓN antes de rotar. REDISEÑO: el código valida que la comparación sea
POSIBLE y fail-closed; el MÉRITO económico (si el upside compensa el riesgo) lo decide el PM. MODO SOMBRA.

Por qué cambió: la versión anterior exigía SIMULTÁNEAMENTE mejor banda + igual/mejor evidencia + igual/menor riesgo
→ convertía una evaluación multidimensional en un VETO determinista, y eso contradice la razón de ser de un PM-LLM y
mata la power-law (una B con E[R] 137% vs 25% pero bear más severo quedaba rechazada). Las restricciones de
SUPERVIVENCIA/liquidez/concentración SÍ son no-compensatorias (las aplica el IPS aguas arriba); los ATRIBUTOS
ECONÓMICOS de la inversión NO (los compensa el PM: mayor incertidumbre ↔ mayor upside ↔ posición menor).

Resultado: PERMITIDA = la comparación es VÁLIDA (el PM decide si rota) · BLOQUEADA = la comparación es inválida
(fail-closed: destino sin verificar, nulls portantes, dossier viejo, banda de A o B desconocida → NO se premia la
ausencia de info). Determinista, $0.
"""
from __future__ import annotations


def comparar_rotacion(a: dict, b: dict) -> tuple[str, list[str]]:
    # ── Venta a CAJA: válida solo si A perdió el capital por una razón CLARA (no por ruido de REVIEW). ──
    if b.get("es_caja"):
        if a.get("banda") == "RECORTE" or a.get("flag_alta_no_opera"):
            return "PERMITIDA", ["A en RECORTE / flag ALTA respondido no_opera"]
        # perder elegibilidad por REVIEW (ruidoso — marcó el 10-K de IESC como no primario) → TRANSICIÓN, no venta
        return "BLOQUEADA", ["A no está en RECORTE ni perdió elegibilidad por una razón clara "
                             "(un REVIEW ruidoso NO habilita vender a caja → TRANSICIÓN)"]

    # ── Rotación A→B: VALIDEZ de la comparación (fail-closed). El mérito lo decide el PM, no el código. ──
    motivos: list[str] = []
    if (b.get("verificacion") or "").upper() not in ("PASS", "REVIEW"):
        motivos.append("destino B sin verificación válida (FAIL o ausente)")
    if b.get("nulls_portantes"):
        motivos.append("B tiene nulls portantes")
    if not b.get("dossier_del_ciclo", False):                 # fail-closed: debe ser del ciclo explícitamente
        motivos.append("el dossier de B no es del ciclo")
    if a.get("banda") is None or b.get("banda") is None:
        motivos.append("banda de A o B desconocida — comparación inválida (no se premia la ausencia de info)")
    if motivos:
        return "BLOQUEADA", motivos
    # Comparación VÁLIDA: el PM juzga si la ventaja económica compensa el costo/riesgo (dentro de los límites del IPS).
    return "PERMITIDA", ["comparación válida — el MÉRITO lo decide el PM (atributos económicos compensatorios)"]
