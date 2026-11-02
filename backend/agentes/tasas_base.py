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
_UNIVERSO = "propio universo BORJA (a computar)"


@dataclass(frozen=True)
class TasaBase:
    id: str
    descripcion: str
    fuente: str
    tasa: float            # fracción histórica (0-1) de la cohorte que logró el resultado
    nota: str = ""         # cohorte / período / limitaciones (survivorship, selección)


_FILAS: tuple[TasaBase, ...] = (
    # Persistencia de crecimiento (Mauboussin/Callahan): decae fuerte con el umbral y el horizonte.
    TasaBase("gr_sales_20_3y", "Sostener ≥20% CAGR de ventas por 3 años", _MAUBOUSSIN, 0.22),
    TasaBase("gr_sales_20_5y", "Sostener ≥20% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.12),
    TasaBase("gr_sales_30_5y", "Sostener ≥30% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.06),
    TasaBase("gr_sales_40_5y", "Sostener ≥40% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.03),
    TasaBase("gr_sales_50_5y", "Sostener ≥50% CAGR de ventas por 5 años", _MAUBOUSSIN, 0.015,
             "cola extrema; <2% de las industriales lo logró"),
    TasaBase("margin_expand_5y", "Expansión de margen operativo sostenida 5 años (domina la reversión)",
             _MAUBOUSSIN, 0.20),
    # Megaproyectos (Flyvbjerg): sobrecostos y atrasos; nuclear en la PEOR cola.
    TasaBase("mega_ontime_onbudget", "Megaproyecto de infraestructura on-time Y on-budget", _FLYVBJERG, 0.085,
             "<8.5% cumple tiempo, presupuesto y beneficios"),
    TasaBase("mega_nuclear", "Central nuclear sin sobrecosto/atraso mayor", _FLYVBJERG, 0.05,
             "nuclear en la peor cola; sobrecosto medio ~120%"),
    TasaBase("mega_proc_minerales", "Planta de procesamiento de minerales en tiempo y presupuesto",
             _FLYVBJERG, 0.15, "alta tasa de atrasos en procesamiento"),
    # First-of-a-kind / primera planta comercial.
    TasaBase("foak_first_plant_ontime", "Primera planta comercial de tecnología nueva en la fecha guía",
             _UNIVERSO, 0.20, "FOAK: la fecha guía inicial casi nunca se cumple"),
    TasaBase("foak_guidance_12m", "Cumplir guidance de primera producción comercial sin atraso >12m",
             _UNIVERSO, 0.30),
    # Small/mid cap pre-revenue.
    TasaBase("prerev_to_profit_5y", "Small cap pre-revenue llega a rentabilidad operativa en 5 años",
             _UNIVERSO, 0.15),
    TasaBase("prerev_no_dilucion_25", "Pre-revenue financia su plan sin dilución acumulada >25%",
             _UNIVERSO, 0.25, "el financiamiento del gap suele diluir más de lo previsto"),
    # Hardware / deep tech / biotech.
    TasaBase("hw_scale_masivo", "Startup de hardware escala a producto comercial masivo", _UNIVERSO, 0.05),
    TasaBase("drug_ph1_approval", "Fármaco en Fase 1 llega a aprobación regulatoria", _CLINICO, 0.08,
             "~7.9% de éxito acumulado Fase 1→aprobación"),
    TasaBase("tech_leader_captura", "El líder tecnológico de una ola captura el valor económico de la ola",
             _MAUBOUSSIN, 0.25, "crecimiento del sector ≠ captura por una empresa"),
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


def calibracion_bull(prob_bull: float | None, ancla_id: str | None) -> tuple[bool, str]:
    """Control de calibración de D1 (doc 74 D3): la P(bull) no debería superar 2x la tasa base de su ancla.
    Devuelve (ok, motivo). `sin_muestra`/None = sin ancla empírica (permitido, es juicio; no se puntúa acá)."""
    if prob_bull is None:
        return True, ""
    if not ancla_id or ancla_id == SIN_MUESTRA:
        return True, ""
    fila = _TABLA.get(ancla_id)
    if fila is None:
        return False, f"ancla de tasa base desconocida: '{ancla_id}'"
    if fila.tasa > 0 and prob_bull > 2.0 * fila.tasa + 1e-9:
        return False, (f"P(bull)={prob_bull:.0%} > 2x la tasa base {fila.tasa:.0%} "
                       f"({ancla_id}: {fila.descripcion}) — optimismo sin sustento")
    return True, ""
