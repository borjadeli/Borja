"""Scenario compiler determinista (doc 27 §1, §5) — el corazón de la costura fact store→valuación.

Toma los hechos del fact store + las magnitudes deterministas (XBRL) y RUTEA cada uno:
  - admisible (reportado/contrato/regulatorio) → término OPERABLE, con la regla de transformación
    AUTORIZADA y su haircut. Cada término lleva {hecho fuente, regla, haircut, vigencia, cita}.
  - no admisible (guidance/management/promocional, opcionalidad) → OPTION LEDGER: se muestra, no
    se valúa (doc 27 §3, §7).
  - sin regla/haircut autorizado → NO entra (no se inventa; doc 27 §5).

El LLM nunca decide un valor acá: la elegibilidad la fija `admisibilidad`, la magnitud sale de XBRL.
Una sola FECHA DE CORTE por escenario (doc 27 §6.2) — prohibido mezclar hechos posteriores.

Estado (doc 27 §14): la MECÁNICA de ruteo + trazabilidad está construida y testeada. Los VALORES
de haircut y el template revenue→precio por arquetipo se pasan como parámetros — PENDIENTES de
triangulación. No hay números de juicio hardcodeados: si falta la política, el término se excluye.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.nucleo import admisibilidad as AD
from backend.nucleo import politica
from backend.nucleo.fact_keys import FACT_KEYS


@dataclass
class TerminoValuacion:
    """Un término del escenario operable, con su transformación trazable (doc 27 §5)."""
    concepto: str
    escenario: str          # "bear" | "base" | "bull"
    valor: float            # aporte ya con haircut aplicado
    valor_bruto: float      # antes del haircut
    hecho_fuente: str       # fact_key / origen XBRL
    regla: str              # nombre de la regla de transformación autorizada
    haircut: str | None     # política de haircut (nombre; el valor vino por parámetro)
    vigencia: date | None   # as-of del hecho fuente (= fecha de corte)
    cita: str = ""
    haircut_source: str = ""   # de dónde salió el recorte: tipo_de_contrato | piso | sin_haircut (doc 28 §1)
    es_piso: bool = False      # retención NO respaldada por tipo de contrato EXTRAÍDO (piso universal O tipo
                               # ASUMIDO en el MVP) → alimenta el flag evidencia_insuficiente (doc 28 §1)


@dataclass
class OportunidadOpcion:
    """Entrada del option ledger (doc 27 §7): fechada, falsable, NO valuada."""
    concepto: str
    hecho_fuente: str
    evidence_class: str | None
    cita: str = ""
    estado_O: str | None = None      # O0..O5 (a poblar por la extracción; None si aún no)
    proximo_hito: str | None = None
    fecha_limite: date | None = None


@dataclass
class EscenarioOperable:
    ticker: str
    arquetipo: str
    fecha_corte: date | None
    terminos: list[TerminoValuacion] = field(default_factory=list)
    option_ledger: list[OportunidadOpcion] = field(default_factory=list)
    rechazados: list[dict] = field(default_factory=list)   # trazabilidad de lo excluido
    cobertura: float = 0.0
    evidencia_insuficiente: bool = False   # >40% del (bull−bear) viene del piso → no toma sleeve completo (doc 28 §1)
    politica_version: str = ""      # sello de política (doc 28 §6): sin versión no es auditable
    politica_hash: str = ""

    def revenue_por_escenario(self) -> dict[str, float]:
        """Suma de términos por escenario. bear = solo realizado; base/bull suman lo contratado
        (según cómo cada regla haya clasificado su término). El paso revenue→precio es aparte."""
        out = {"bear": 0.0, "base": 0.0, "bull": 0.0}
        for t in self.terminos:
            out[t.escenario] = out.get(t.escenario, 0.0) + t.valor
        # bear ⊆ base ⊆ bull: lo realizado entra a los tres; lo contratado a base/bull.
        out["base"] += out["bear"]
        out["bull"] += out["base"]
        return out


def _cobertura(snap: dict) -> float:
    """Evidence coverage (doc 27 §4): fracción del registry con hecho fundado (DIRECT/DERIVED)."""
    total = len(FACT_KEYS) or 1
    fundados = sum(1 for f in snap.values()
                   if getattr(f, "support_type", None) in ("DIRECT", "DERIVED"))
    return round(min(fundados / total, 1.0), 3)


def tipo_contrato_rpo(no_cancelable: bool | None) -> tuple[str, bool]:
    """Mapea el hecho citado `backlog_no_cancelable` → (contract_type, tipo_asumido) para el RPO (E1, doc 14).

    - True  (firme/no-cancelable, EXTRAÍDO) → `firm_po` (retención 0.85), tipo_asumido=False.
    - False (cancelable, EXTRAÍDO)          → `cancelable_backlog` (0.60), tipo_asumido=False.
    - None  (sin extraer / desconocido)      → `cancelable_backlog` (0.60), tipo_asumido=True (conservador,
      penaliza sleeve vía evidencia_insuficiente hasta que se extraiga el hecho).
    """
    if no_cancelable is True:
        return "firm_po", False
    if no_cancelable is False:
        return "cancelable_backlog", False
    return "cancelable_backlog", True


def compilar_escenario(ticker: str, snap: dict, det: dict, arquetipo: str, *,
                       magnitudes: dict | None = None,
                       politicas_haircut: dict[str, float] | None = None,
                       fecha_corte: date | None = None) -> EscenarioOperable:
    """Compila el escenario operable de forma determinista y trazable.

    magnitudes: concepto → {monto, fact_key, evidence_class, cita} (backlog, awards…). Los montos
                salen de fuente dura (XBRL/EDGAR), NO del LLM.
    politicas_haircut: nombre_de_política → factor 0-1 (PENDIENTE triangulación). Sin el factor, el
                término se excluye (no se inventa).
    """
    magnitudes = magnitudes or {}
    politicas_haircut = politicas_haircut or {}
    sello = politica.sello()
    esc = EscenarioOperable(ticker=ticker, arquetipo=arquetipo, fecha_corte=fecha_corte,
                            politica_version=sello["politica_version"],
                            politica_hash=sello["politica_hash"])

    # 1) Término base: revenue realizado (reportado/auditado, sin haircut) — el suelo defendible.
    rev = det.get("revenue_ttm")
    if rev is not None:
        esc.terminos.append(TerminoValuacion(
            concepto="revenue_realizado", escenario="bear", valor=float(rev), valor_bruto=float(rev),
            hecho_fuente="revenue_ttm(XBRL)", regla="realizado_100pct", haircut=AD.SIN_HAIRCUT,
            vigencia=fecha_corte, cita="XBRL companyfacts"))

    # 2) Magnitudes adicionales.
    for concepto, m in magnitudes.items():
        # Vía A — magnitud con TIPO DE CONTRATO (doc 28 §1): retención por tipo desde política.
        ctype = m.get("contract_type")
        if ctype:
            ret = politica.retencion_contrato(ctype)
            monto = float(m["monto"])
            if ret["destino"] == "ledger_O3":         # condicional / ceiling ("hasta $X") → no valúa
                esc.option_ledger.append(OportunidadOpcion(
                    concepto=concepto, hecho_fuente=m.get("fact_key", concepto),
                    evidence_class=m.get("evidence_class"), cita=m.get("cita", "")))
                esc.rechazados.append({"concepto": concepto,
                                       "motivo": f"contract_type '{ctype}' condicional/ceiling → ledger O3",
                                       "destino": "option_ledger"})
                continue
            # tipo ASUMIDO (MVP: RPO tratado como cancelable sin extraer el término) O piso fallback →
            # es_piso=True: cuenta para evidencia_insuficiente (el atajo es visible y penaliza el sleeve).
            asumido = bool(m.get("tipo_asumido"))
            es_piso = asumido or bool(ret.get("fallback"))
            src = "piso" if ret.get("fallback") else (f"{ctype}(asumido)" if asumido else ctype)
            esc.terminos.append(TerminoValuacion(
                concepto=concepto, escenario="bull", valor=monto * ret["retencion"], valor_bruto=monto,
                hecho_fuente=m.get("fact_key", concepto), regla="retencion_por_tipo_contrato",
                haircut=ctype, vigencia=m.get("vigencia") or fecha_corte, cita=m.get("cita", ""),
                haircut_source=src, es_piso=es_piso))
            continue
        # Vía B — magnitud SIN tipo de contrato: admisibilidad por evidence_class (claims → option ledger).
        adm = AD.es_admisible(m.get("fact_key", concepto), m.get("evidence_class"))
        if not adm["valuation_eligible"]:
            esc.option_ledger.append(OportunidadOpcion(
                concepto=concepto, hecho_fuente=m.get("fact_key", concepto),
                evidence_class=m.get("evidence_class"), cita=m.get("cita", "")))
            esc.rechazados.append({"concepto": concepto, "motivo": adm["motivo"],
                                   "destino": "option_ledger"})
            continue
        pol = adm["haircut"]
        factor = 1.0 if pol == AD.SIN_HAIRCUT else politicas_haircut.get(pol)
        if factor is None:                       # sin valor de haircut autorizado → NO se inventa
            esc.rechazados.append({"concepto": concepto,
                                   "motivo": f"haircut '{pol}' sin valor autorizado → excluido",
                                   "destino": "excluido"})
            continue
        monto = float(m["monto"])
        esc.terminos.append(TerminoValuacion(
            concepto=concepto, escenario="bull", valor=monto * factor, valor_bruto=monto,
            hecho_fuente=m.get("fact_key", concepto), regla="contratado_con_haircut",
            haircut=pol, vigencia=fecha_corte, cita=m.get("cita", "")))

    esc.cobertura = _cobertura(snap)

    # Flag evidencia_insuficiente (doc 28 §1): si el PISO/tipo-asumido domina el incremento del bull
    # (>40%), el nombre no puede tomar sleeve completo → el bull está construido sobre política, no evidencia.
    rev = esc.revenue_por_escenario()
    incremento = rev["bull"] - rev["bear"]
    piso_contrib = sum(t.valor for t in esc.terminos if t.es_piso)
    if incremento > 0 and piso_contrib > politica.CAP_AGREGADO_PISO * incremento:
        esc.evidencia_insuficiente = True
    return esc
