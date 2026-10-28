"""Digest advisory del estado v2 (para que el operador LEA qué tiene, por qué, y qué lo mataría).

BORJA es ADVISORY: el operador replica a mano las propuestas. Este digest junta lo que hoy vive disperso
(paper fiel + ledger de decisiones + dossiers del cache) en un texto legible. Formatter PURO y testeable;
el ops `estado_v2` le pasa los datos reales (y un futuro endpoint del dashboard puede reusar `render_digest`).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PosicionResumen:
    ticker: str
    shares: float
    precio: float | None
    peso: float            # fracción de la cartera (0-1)

    @property
    def valor(self) -> float:
        return self.shares * (self.precio or 0.0)


@dataclass
class DossierResumen:
    veredicto: str                 # pass/review/fail
    bull: str = ""
    bear: str = ""
    falsador: str = ""
    falsador_fecha: str = ""
    red_flags: list[str] = field(default_factory=list)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_digest(*, ciclo: str, equity: float, caja_pct: float, posiciones: list[PosicionResumen],
                  decisiones: list, dossiers: dict[str, DossierResumen],
                  gasto_mes: float, tope_mes: float, sombras: dict[str, float] | None = None) -> str:
    """Arma el texto del digest. `decisiones` = RegistroDecision del último ciclo (o cualquier objeto con
    ticker/accion/peso_resultante/conviccion_0_1/verif_veredicto/tesis/falsador_afirmacion/…)."""
    L: list[str] = []
    L.append(f"═══ BORJA v2 — digest advisory · ciclo {ciclo} ═══")
    L.append(f"CARTERA: equity ${equity:,.0f} · caja {_pct(caja_pct)} · {len(posiciones)} posición(es)")
    for p in sorted(posiciones, key=lambda x: -x.peso):
        precio = f"${p.precio:,.2f}" if p.precio is not None else "s/precio"
        L.append(f"  {p.ticker:6s} {p.shares:>8,.0f} acc @ {precio} = ${p.valor:,.0f}  ({_pct(p.peso)})")
    if not posiciones:
        L.append("  (sin posiciones — 100% caja)")

    L.append("")
    L.append(f"DECISIONES DEL CICLO {ciclo}:")
    if not decisiones:
        L.append("  (ninguna)")
    for d in decisiones:
        ejec = "" if getattr(d, "ejecutada", True) else "  [NO EJECUTADA]"
        L.append(f"  {d.accion.upper()} {d.ticker} → {_pct(d.peso_resultante)} "
                 f"(conv {d.conviccion_0_1:.2f}, verif {str(d.verif_veredicto or '?').upper()}){ejec}")
        if d.tesis:
            L.append(f"      tesis: {d.tesis}")
        if d.falsador_afirmacion:
            L.append(f"      falsador: {d.falsador_afirmacion} (límite {d.falsador_fecha_limite})")

    L.append("")
    L.append("POR QUÉ (dossier verificado):")
    for tk, ds in dossiers.items():
        L.append(f"  {tk} [{ds.veredicto.upper()}]")
        if ds.bull:
            L.append(f"      bull: {ds.bull}")
        if ds.bear:
            L.append(f"      bear: {ds.bear}")
        if ds.red_flags:
            L.append(f"      red flags: {', '.join(ds.red_flags)}")
        if ds.falsador:
            L.append(f"      falsador: {ds.falsador} (límite {ds.falsador_fecha})")

    if sombras:
        L.append("")
        L.append("CARTERAS SOMBRA (índice equity, base 1.0; necesita varios ciclos para ser significativo):")
        for cart, idx in sorted(sombras.items(), key=lambda kv: -kv[1]):
            marca = "  ← PM" if cart == "pm" else ""
            L.append(f"  {cart:10s} {idx:.4f} ({_pct(idx - 1.0)}){marca}")

    L.append("")
    nivel = gasto_mes / tope_mes if tope_mes else 0.0
    L.append(f"PRESUPUESTO LLM: ${gasto_mes:.2f} / ${tope_mes:.0f} del mes ({_pct(nivel)})")
    return "\n".join(L)
