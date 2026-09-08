"""Evalúa todas las fichas (excepto las ya tradeadas) y reporta motivo por ticker.

NO usa LLM. Corre Portfolio.evaluar_entrada (determinista) sobre cada ficha y
captura el campo no_entrar_razones. Para fichas sin score o sin datos completos,
reporta motivo específico.

Output: tabla 2 columnas: ticker | motivo.
"""
from __future__ import annotations

from backend.agents.portfolio import (
    evaluar_entrada,
    Accion,
)
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector


EXCLUIR = {"S", "TENB", "LEU"}  # ya tradeadas (S/TENB en Portfolio, LEU rotada)


# Estados terminales o no aplicables al "considerar para Portfolio"
ESTADOS_NO_APLICA = {
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
    EstadoFicha.SUSPENDIDA.value,
    EstadoFicha.ELIMINADA.value,
}


def evaluar_ficha(s, f, sectores_map, macro):
    """Devuelve (puede_entrar: bool, motivo: str)."""
    # Estados terminales
    if f.estado in (EstadoFicha.SUSPENDIDA.value, EstadoFicha.ELIMINADA.value):
        return (False, f"Estado {f.estado} — fuera del universo activo")

    # Sin score → Analista no corrió todavía
    if f.score_vigente is None:
        return (False, "Sin análisis del Analista (score=None) — requiere deep research primero")

    # Sin datos cualitativos → no se puede correr Portfolio agent
    if (
        f.bull_case_precio is None or f.bear_case_precio is None
        or f.nivel_r is None
    ):
        return (False, "Análisis incompleto (falta bull/bear/nivel_R) — re-correr Analista")

    sec = sectores_map.get(f.sector)
    rec = evaluar_entrada(s, f, sec, macro)

    if rec.accion == Accion.ENTRAR:
        return (True, f"PASA todos los filtros — sizing sugerido {rec.sizing_sugerido}%")
    if rec.accion == Accion.MANTENER:
        return (False, rec.justificacion)
    if rec.accion == Accion.WL_PRIORITARIA:
        # rec.justificacion empieza con "No entrar por: " seguido de razones
        return (False, rec.justificacion)
    return (False, f"acción={rec.accion}: {rec.justificacion}")


def main() -> None:
    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        sectores_map = {sec.nombre: sec for sec in s.query(Sector).all()}

        rows = (
            s.query(Ficha)
            .filter(~Ficha.ticker.in_(EXCLUIR))
            .order_by(Ficha.estado, Ficha.score_vigente.desc().nullslast(), Ficha.ticker)
            .all()
        )

        resultados = []
        for f in rows:
            puede, motivo = evaluar_ficha(s, f, sectores_map, macro)
            resultados.append({
                "ticker": f.ticker,
                "sector": f.sector,
                "estado": f.estado,
                "score": f.score_vigente,
                "puede_entrar": puede,
                "motivo": motivo,
            })

    # Reporte
    cabezal = f"{'Ticker':<8} | Motivo"
    print(cabezal)
    print("-" * 130)

    # Primero los que PUEDEN entrar
    pueden = [r for r in resultados if r["puede_entrar"]]
    no_pueden = [r for r in resultados if not r["puede_entrar"]]

    if pueden:
        print(">>> PASAN TODOS LOS FILTROS <<<")
        for r in pueden:
            print(f"{r['ticker']:<8} | {r['motivo']}")
        print()

    print(f">>> NO PASAN ({len(no_pueden)} fichas) <<<")
    for r in no_pueden:
        # Truncar motivo a 110 chars para que la tabla quepa
        motivo = r["motivo"][:115]
        print(f"{r['ticker']:<8} | {motivo}")

    # Resumen por motivo agregado
    print()
    print("=" * 130)
    print("RESUMEN POR CATEGORÍA")
    print("=" * 130)
    categorias = {}
    for r in resultados:
        m = r["motivo"]
        # Extraer primera causa (antes del primer '|')
        primera = m.split("|")[0].strip()
        # Acortar
        if "score" in primera.lower() and "<" in primera:
            cat = "Score < 6"
        elif "Sin análisis" in primera or "Analista no corrió" in primera:
            cat = "Sin análisis del Analista"
        elif "incompleto" in primera or "falta bull" in primera.lower():
            cat = "Análisis incompleto"
        elif "Estado" in primera and "fuera" in primera:
            cat = "Estado terminal (Suspendida/Eliminada)"
        elif "concentración sectorial" in primera.lower():
            cat = "Concentración sectorial llena"
        elif "concentración driver" in primera.lower():
            cat = "Concentración driver llena (capex_AI)"
        elif "asimetría" in primera.lower():
            cat = "Asimetría < umbral momentum"
        elif "confidence baja" in primera.lower():
            cat = "Confidence Baja en claim central"
        elif "checklist incompleto" in primera.lower():
            cat = "Checklist incompleto"
        elif "Capital Raise Risk" in primera:
            cat = "CRR Alto/Crítico"
        elif r["puede_entrar"]:
            cat = "PASA"
        else:
            cat = primera[:60]
        categorias[cat] = categorias.get(cat, 0) + 1

    for cat, n in sorted(categorias.items(), key=lambda x: -x[1]):
        print(f"  {n:>3}  {cat}")


if __name__ == "__main__":
    main()
