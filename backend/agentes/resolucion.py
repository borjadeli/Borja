"""Ciclo de RESOLUCIÓN de predicciones (doc 74) — cierra el loop del ledger para que el Brier sea real.

Cada decisión del PM deja predicciones fechadas: el **falsador** (¿la tesis se sostuvo al vencer?) y el
**bull** (¿el escenario optimista se materializó al horizonte?). Al vencer su fecha hay que RESOLVERLAS; recién
ahí el Brier (`ledger.metricas()`) mide si el análisis calibra. Dos caminos:
  - `resolver(...)`: resolución EXPLÍCITA con evidencia (operador o un agente de monitoreo).
  - `aplicar_silencio_falsadores(...)`: la regla de IA2 — un falsador con fecha vencida y SIN evidencia cuenta
    como **disparado** (la tesis no mostró el hito prometido). Es un default deliberado (no automático en la
    corrida): se marca como "silencio" para distinguirlo de una resolución con evidencia.

Consecuencia pre-comprometida (D2/D4): un falsador DISPARADO abre una **revisión** del nombre (alerta para el
PM del próximo ciclo) y sugiere bajar un escalón de clasificación. ADVISORY: abre review, NO vende solo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Pendiente:
    decision_id: str
    ticker: str
    tipo: str                    # "falsador" | "bull"
    fecha_limite: str
    descripcion: str             # afirmación del falsador / resumen del bull
    default_sugerido: str        # resolución recomendada (falsador: "disparado" por silencio; bull: "" = explícita)


def pendientes(ledger, hoy: date | None = None) -> list[Pendiente]:
    """Predicciones vencidas sin resolver (falsadores + bull), para el monitor/operador."""
    hoy = hoy or date.today()
    out: list[Pendiente] = []
    for d in ledger.pendientes(hoy):                 # falsadores vencidos
        # P0.2 (doc 91): mostrar la condición de muerte CORRECTAMENTE FIRMADA del dossier (el analista la escribió
        # bien), no el texto libre del PM —que puede venir con el signo invertido y arruinar la resolución—.
        fd = d.falsador_dossier or {}
        desc = fd.get("que_lo_mataria") or fd.get("afirmacion") or d.falsador_afirmacion
        out.append(Pendiente(d.decision_id, d.ticker, "falsador", d.falsador_fecha_limite,
                             desc, default_sugerido="disparado"))
    for d in ledger.pendientes_bull(hoy):            # bull vencidos (resolución explícita: materialización no es silencio)
        out.append(Pendiente(d.decision_id, d.ticker, "bull", d.horizonte_bull_fecha or "",
                             f"P(bull)={d.prob_bull:.0%} a {d.horizonte_bull_fecha}", default_sugerido=""))
    return out


def resolver(ledger, decision_id: str, tipo: str, estado: str, *, nota: str | None = None) -> None:
    """Resolución EXPLÍCITA (con evidencia). tipo: 'falsador' (estado disparado|no_disparado) · 'bull'
    (materializado|no_materializado)."""
    if tipo == "falsador":
        ledger.resolver_falsador(decision_id, estado, nota=nota)
    elif tipo == "bull":
        ledger.resolver_bull(decision_id, estado, nota=nota)
    else:
        raise ValueError(f"tipo de predicción desconocido: {tipo}")


def consecuencia(ticker: str, afirmacion: str) -> str:
    """Alerta de revisión por falsador disparado (D2/D4): abre review + sugiere bajar de banda. NO vende."""
    return (f"{ticker}: FALSADOR DISPARADO — '{afirmacion}'. Revisá la posición: la tesis se falsó; "
            f"corresponde bajar un escalón de clasificación (D4) o salir. (advisory: no se vende solo)")


def aplicar_silencio_falsadores(ledger, hoy: date | None = None) -> list[str]:
    """Regla de IA2: todo falsador vencido y SIN resolver se marca `disparado` por SILENCIO (la tesis no mostró
    el hito al vencimiento). Devuelve las alertas de consecuencia. Deliberado (lo corre el operador/monitor);
    idempotente (una vez resuelto, deja de estar pendiente). El bull NO entra (su materialización no es silencio)."""
    hoy = hoy or date.today()
    alertas: list[str] = []
    for d in ledger.pendientes(hoy):
        ledger.resolver_falsador(d.decision_id, "disparado", nota="silencio (sin evidencia al vencimiento)")
        alertas.append(consecuencia(d.ticker, d.falsador_afirmacion))
    return alertas


def render_pendientes(items: list[Pendiente]) -> str:
    if not items:
        return "(sin predicciones vencidas por resolver)"
    L = [f"PREDICCIONES VENCIDAS POR RESOLVER ({len(items)}):"]
    for p in items:
        suf = f" → default sugerido: {p.default_sugerido}" if p.default_sugerido else " → requiere evidencia"
        L.append(f"  · [{p.tipo}] {p.ticker} (venció {p.fecha_limite}): {p.descripcion}{suf}")
    return "\n".join(L)
