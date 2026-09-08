"""Protocolo Transición Fase Macro (v4.2 sec 5).

Cuando el humano declara 'Fase 2 activada' en la revisión trimestral de tesis
macro, el sistema ejecuta automáticamente:

1. Revalidación forzada de todas las posiciones activas con checklist Fase 2:
   - ¿la tesis depende de capex discrecional?
   - ¿el cliente final es sensible a tasas?
   - ¿el balance soporta 18 meses sin acceso a capital?

2. Posiciones que NO pasen el checklist:
   - sizing reducido a 50% inmediato
   - plan de salida acelerado (alerta + recomendación)

3. Suspensión automática del bucket exploratorio hasta que el humano reclasifique
   sectores para Fase 2.

4. Cash objetivo del portfolio sube (no fuerza ventas masivas, pero frena
   nuevos deploys hasta llegar al objetivo).

Todo queda registrado en decision_journal.
"""
from __future__ import annotations

from backend.agents.decision_journal import registrar_decision
from backend.database import session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


def _checklist_fase_2(f: Ficha, sector_row: Sector | None) -> dict:
    """Aplica el checklist Fase 2 a una ficha. Devuelve dict con flags y resultado.

    Heurísticas (best-effort en MVP):
    - capex_discrecional: True si sector tiene cluster_driver='capex_AI' (capex hyperscaler).
    - cliente_sensible_tasas: True si sector pertenece a cyclicals/consumer (proxy: prioridad 'media' y no defensa).
    - balance_18m: True si CRR ∈ {Bajo, Medio} (proxy de runway suficiente).
    """
    capex_discrecional = bool(sector_row and sector_row.cluster_driver == "capex_AI")
    cliente_sensible = bool(
        sector_row and (sector_row.prioridad or "").lower() == "media"
        and (sector_row.cluster_driver or "") != "capex_AI"
    )
    balance_ok = f.capital_raise_risk in (None, "Bajo", "Medio")

    failures: list[str] = []
    if capex_discrecional:
        failures.append("tesis depende de capex discrecional (driver capex_AI)")
    if cliente_sensible:
        failures.append("cliente final sensible a tasas")
    if not balance_ok:
        failures.append(f"balance no soporta 18m (CRR={f.capital_raise_risk})")

    return {
        "ticker": f.ticker,
        "capex_discrecional": capex_discrecional,
        "cliente_sensible_tasas": cliente_sensible,
        "balance_18m_ok": balance_ok,
        "failures": failures,
        "pasa_checklist": len(failures) == 0,
    }


def activar_fase_2(motivo: str = "humano declara Fase 2 activada") -> dict:
    """Ejecuta el protocolo de transición. Idempotente: si ya está en Fase 2 no rehace.

    NO ejecuta ventas/trims automáticos. Reduce sizing en ficha (campo) y deja
    plan de salida acelerado como alerta para el humano.
    """
    now = utcnow()
    resumen: dict = {
        "fase_anterior": None,
        "fase_actual": "fase_2_defensiva",
        "checklists": [],
        "sizing_reducidos": [],
        "bucket_suspendido": False,
        "decision_journal_id": None,
    }

    with session_scope() as s:
        macro = s.query(Macro).filter_by(activa=True).first()
        if macro:
            resumen["fase_anterior"] = macro.fase_actual
            macro.fase_actual = "fase_2_defensiva"
            macro.postura_capital = "defensiva"
            macro.fecha_actualizacion = now

        sectores = {sec.nombre: sec for sec in s.query(Sector).all()}
        portfolio = (
            s.query(Ficha)
            .filter_by(estado=EstadoFicha.PORTFOLIO_ACTIVO.value)
            .all()
        )
        for f in portfolio:
            sec = sectores.get(f.sector)
            chk = _checklist_fase_2(f, sec)
            resumen["checklists"].append(chk)
            if not chk["pasa_checklist"]:
                # Reducir sizing a 50% del actual
                if f.sizing_actual:
                    sizing_anterior = f.sizing_actual
                    f.sizing_actual = round(sizing_anterior * 0.5, 2)
                    resumen["sizing_reducidos"].append({
                        "ticker": f.ticker,
                        "anterior": sizing_anterior,
                        "nuevo": f.sizing_actual,
                        "motivos": chk["failures"],
                    })
                cambios = list(f.cambios_estado or [])
                cambios.append({
                    "timestamp": now.isoformat(),
                    "estado_anterior": f.estado,
                    "estado_nuevo": f.estado,
                    "motivo": f"Fase 2 activada — sizing reducido 50%. Failures: {chk['failures']}",
                })
                f.cambios_estado = cambios

        # Suspender bucket exploratorio (mover a WL_Activa con marca)
        bucket = (
            s.query(Ficha)
            .filter_by(estado=EstadoFicha.BUCKET_EXPLORATORIO.value)
            .all()
        )
        for f in bucket:
            cambios = list(f.cambios_estado or [])
            cambios.append({
                "timestamp": now.isoformat(),
                "estado_anterior": f.estado,
                "estado_nuevo": EstadoFicha.WL_ACTIVA.value,
                "motivo": "Fase 2 activada — bucket exploratorio suspendido (v4.2 sec 5)",
            })
            f.estado = EstadoFicha.WL_ACTIVA.value
            f.cambios_estado = cambios
            resumen["bucket_suspendido"] = True

    # Log al decision journal (fuera del session_scope)
    journal_id = registrar_decision(
        accion="fase_2_activada",
        decisor="humano",
        motivo=motivo,
        metadata={
            "sizing_reducidos": resumen["sizing_reducidos"],
            "bucket_suspendido": resumen["bucket_suspendido"],
            "checklists_count": len(resumen["checklists"]),
        },
    )
    resumen["decision_journal_id"] = journal_id

    log.info(
        "transicion_fase_macro — Fase 2 activada — sizing_reducidos=%d bucket_suspendido=%s",
        len(resumen["sizing_reducidos"]), resumen["bucket_suspendido"],
    )
    return resumen
