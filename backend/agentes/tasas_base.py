"""D3 (doc 74) — tabla curada de TASAS BASE que el sistema POSEE (determinismo trae el dato).

Problema que resuelve: el "<10% de comparables logró esto" aparecía sin cohorte ni fuente, y pedirle una cita
al LLM invita al LAVADO DE CITAS (citar el Base Rate Book para lo que no dice — peor que "juicio sin muestra"
porque parece fundado). Solución: una tabla acotada, con fuente y cohorte, de la que el Analista ELIGE una
fila para anclar la probabilidad del escenario bull. Si ninguna aplica → "sin_muestra" (juicio explícito).

Conexión con D1 (el control de calibración): si la P(bull) del analista supera 2x la tasa base de su ancla,
el Verificador baja a REVIEW. Así D3 deja de ser nota al pie y calibra D1.

Valores ORIENTATIVOS (orden de magnitud + fuente); varias filas son computables del propio universo (TODO).
NO son verdad estadística fina — son el contraste anti-optimismo.
"""
from __future__ import annotations

from dataclasses import dataclass

_MAUBOUSSIN = "Mauboussin & Callahan, 'The Base Rate Book' (2016)"
_FLYVBJERG = "Flyvbjerg, 'How Big Things Get Done' (2023)"
_CLINICO = "BIO/Informa/QLS, clinical development success rates"


@dataclass(frozen=True)
class TasaBase:
    id: str
    descripcion: str
    fuente: str
    tasa: float            # fracción histórica (0-1) de la cohorte que logró el resultado
    nota: str = ""         # cohorte / período / limitaciones (survivorship, selección)
    verificada: bool = False   # r5 item 1: True solo cuando se verificó contra la fuente (tabla/página).
    cita: str = ""             # referencia exacta (tabla/página) — se completa al verificar

    @property
    def gatea(self) -> bool:
        """Solo una fila VERIFICADA contra la fuente puede bajar un dossier a REVIEW; si no, solo informa."""
        return self.verificada


# NOTA (r5 item 1): ninguna fila está `verificada` todavía → por ahora TODAS son "juicio del operador" e
# INFORMAN (no gatean). El operador o una IA externa verifica cada una contra la fuente (tabla/página),
# completa `cita` y pone `verificada=True`. Las filas "propio universo (a computar)" se sacaron hasta que se
# computen de verdad desde el universo. Los valores son ORIENTATIVOS (orden de magnitud).
_FILAS: tuple[TasaBase, ...] = (
    # Persistencia de crecimiento (Mauboussin/Callahan): decae fuerte con el umbral y el horizonte.
    TasaBase("gr_sales_20_3y", "Sostener ≥20% CAGR de ventas por 3 años", _MAUBOUSSIN, 0.22),
    TasaBase("gr_sales_20_5y", "Sostener ≥20% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.12),
    TasaBase("gr_sales_30_5y", "Sostener ≥30% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.06),
    TasaBase("gr_sales_40_5y", "Sostener ≥40% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.03),
    TasaBase("gr_sales_50_5y", "Sostener ≥50% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.015,
             "cola extrema"),
    TasaBase("margin_expand_5y", "Expansión de margen operativo sostenida 5 años (domina la reversión)",
             _MAUBOUSSIN, 0.20),
    TasaBase("tech_leader_captura", "El líder tecnológico de una ola captura el valor económico de la ola",
             _MAUBOUSSIN, 0.25, "crecimiento del sector ≠ captura por una empresa"),
    # Megaproyectos (Flyvbjerg): sobrecostos y atrasos; nuclear en la PEOR cola.
    TasaBase("mega_ontime_onbudget", "Megaproyecto de infraestructura on-time Y on-budget", _FLYVBJERG, 0.085,
             "8,5% cumple tiempo+presupuesto; solo ~0,5% también cumple beneficios"),
    TasaBase("mega_nuclear", "Central nuclear sin sobrecosto/atraso mayor", _FLYVBJERG, 0.05,
             "nuclear en la peor cola; sobrecosto medio alto"),
    TasaBase("mega_proc_minerales", "Planta de procesamiento de minerales en tiempo y presupuesto",
             _FLYVBJERG, 0.15, "alta tasa de atrasos en procesamiento"),
    # Biotech.
    TasaBase("drug_ph1_approval", "Fármaco en Fase 1 llega a aprobación regulatoria", _CLINICO, 0.08,
             "~7.9% de éxito acumulado Fase 1→aprobación"),
)

_TABLA = {f.id: f for f in _FILAS}
SIN_MUESTRA = "sin_muestra"


def filas() -> list[TasaBase]:
    return list(_FILAS)


def tasa_base(id: str | None) -> TasaBase | None:
    return _TABLA.get(id) if id else None


def render_tabla() -> str:
    """Para inyectar en el prompt del Analista: las filas disponibles (id — descripción (tasa) [fuente])."""
    lineas = [f"- {f.id}: {f.descripcion} (~{f.tasa:.0%}) [{f.fuente.split(',')[0]}]" for f in _FILAS]
    return "\n".join(lineas) + f"\n- {SIN_MUESTRA}: ninguna fila aplica (juicio del analista, sin cohorte)"


def calibracion_bull(prob_bull: float | None, ancla_id: str | None) -> tuple[str, str]:
    """Control de calibración de D1 (doc 74 D3, r5 item 1): la P(bull) no debería superar 2x la tasa base de su
    ancla. Devuelve (estado, motivo), estado ∈ {'ok','review','nota'}. REVIEW SOLO si la fila está `verificada`
    contra la fuente; si no (o `sin_muestra`/sin ancla), INFORMA (nota). Una id inexistente sí es review (ancla
    inventada). El `sin_muestra` se reporta para que el Auditor vea que el bull no tiene ancla empírica."""
    if prob_bull is None:
        return "ok", ""
    if not ancla_id or ancla_id == SIN_MUESTRA:
        return "nota", "bull sin ancla empírica (sin_muestra): juicio del analista, no calibrable"
    fila = _TABLA.get(ancla_id)
    if fila is None:
        return "review", f"ancla de tasa base desconocida (inventada): '{ancla_id}'"
    excede = fila.tasa > 0 and prob_bull > 2.0 * fila.tasa + 1e-9
    if not fila.gatea:                      # fuente sin verificar → informa, NO gatea (r5 item 1)
        suf = f"; además P(bull)={prob_bull:.0%} > 2x tasa {fila.tasa:.0%}" if excede else ""
        return "nota", f"ancla '{ancla_id}' no verificada contra la fuente — informa, no gatea{suf}"
    if excede:
        return "review", (f"P(bull)={prob_bull:.0%} > 2x la tasa base {fila.tasa:.0%} "
                          f"({ancla_id}: {fila.descripcion}) — optimismo sin sustento")
    return "ok", ""
