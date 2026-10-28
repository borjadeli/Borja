"""Contraste numérico claim ↔ XBRL (v2 P1 paso 3, doc 59).

Arregla los 4 bugs que IA 1 encontró en `extractor_citado.contrastar_xbrl`, y lo hace **por referencia a un
`DataPoint` del pack** (no adivinando el concepto por NLP): el claim numérico central lleva a qué métrica se
contrasta, y acá se compara contra ese DataPoint.

- **signo:** "pérdida de US$139.3M" (magnitud) vs `OperatingIncomeLoss = −139.3M` → coincide en MAGNITUD
  (convención de pérdida), no se rechaza. El signo/dirección (ganancia vs pérdida) es cuestión SEMÁNTICA →
  la resuelve la capa de suficiencia/entailment (paso 4), no el número.
- **escala:** el claim trae su escala (M/B/miles) → se normaliza a valor absoluto antes de comparar.
- **período:** no se compara un Q contra un FY → `no_contrastable` si los períodos difieren.
- **tolerancia:** `max(2% , media unidad del último dígito informado)` → "~US$1.4B" vs 1.43B = MATCH
  (antes 2.1% lo rechazaba).

Estados: `match` · `match_magnitud` (coincide en magnitud, signo opuesto = convención de pérdida) ·
`contradice` (→ el verificador lo trata como FAIL) · `no_contrastable` (sin ref o período distinto → REVIEW).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.agentes.provenance import DataPoint

# Multiplicadores de escala declarada en el claim.
ESCALAS = {"": 1.0, "unidad": 1.0, "K": 1e3, "miles": 1e3, "M": 1e6, "millones": 1e6,
           "B": 1e9, "miles_de_millones": 1e9, "bn": 1e9}


@dataclass
class ResultadoContraste:
    estado: str                 # match | match_magnitud | contradice | no_contrastable
    detalle: str
    claim_abs: float | None = None
    ref_abs: float | None = None

    @property
    def ok(self) -> bool:            # sirve para PASS (coincide, exacto o en magnitud)
        return self.estado in ("match", "match_magnitud")

    @property
    def contradice(self) -> bool:    # → FAIL en el verificador
        return self.estado == "contradice"


def _decimales_de(valor: float) -> int:
    """Decimales informados del número (1.4 → 1; 139300 → 0) para la media-unidad del último dígito."""
    s = repr(float(valor))
    if "e" in s or "E" in s:
        return 0
    return len(s.split(".", 1)[1].rstrip("0")) if "." in s else 0


def _half_ulp(valor: float, escala: float, decimales: int | None) -> float:
    """Media unidad del último dígito informado (para no rechazar redondeos como '~1.4B'). Si no se pasan
    `decimales`, se infieren del propio número."""
    d = _decimales_de(valor) if decimales is None else decimales
    return 0.5 * (10.0 ** (-d)) * escala


def contrastar_numero(valor_claim: float, dp_ref: DataPoint | None, *, escala: str | float = 1.0,
                      decimales: int | None = None, periodo: str | None = None,
                      tol_rel: float = 0.02) -> ResultadoContraste:
    """Contrasta el número de un claim contra un `DataPoint` del pack (su referencia). Ver docstring del módulo."""
    if dp_ref is None or dp_ref.value is None:
        return ResultadoContraste("no_contrastable", "sin DataPoint de referencia en el pack")
    if periodo and dp_ref.period_type and periodo != dp_ref.period_type:
        return ResultadoContraste("no_contrastable",
                                  f"período distinto: claim={periodo} vs ref={dp_ref.period_type}")
    mult = ESCALAS.get(escala, None) if isinstance(escala, str) else float(escala)
    if mult is None:
        return ResultadoContraste("no_contrastable", f"escala desconocida: {escala!r}")
    claim = valor_claim * mult
    ref = float(dp_ref.value)
    tol = max(tol_rel * max(abs(claim), abs(ref)), _half_ulp(valor_claim, mult, decimales))
    if abs(claim - ref) <= tol:
        return ResultadoContraste("match", f"coincide ({claim:.4g} ≈ {ref:.4g})", claim, ref)
    if abs(abs(claim) - abs(ref)) <= tol:
        return ResultadoContraste("match_magnitud",
                                  f"coincide en magnitud, signo opuesto (convención de pérdida): "
                                  f"{claim:.4g} vs {ref:.4g}", claim, ref)
    return ResultadoContraste("contradice", f"difiere: claim {claim:.4g} vs XBRL {ref:.4g}", claim, ref)
