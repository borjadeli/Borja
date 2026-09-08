"""Scenario compiler (doc 27 §1/§5) — la mecánica de ruteo + trazabilidad.

Verifica: realizado entra al operable; contratado entra con haircut autorizado; management-claim
va al option ledger (no valúa); sin valor de haircut → excluido (no se inventa); todo trazable.
"""
from types import SimpleNamespace

from backend.nucleo import admisibilidad as AD
from backend.nucleo import compilador as C


def _snap(n_fundados=3):
    facts = {f"k{i}": SimpleNamespace(support_type="DIRECT") for i in range(n_fundados)}
    return facts


DET = {"revenue_ttm": 100e6}


def test_realizado_entra_como_suelo():
    esc = C.compilar_escenario("X", _snap(), DET, "Growth")
    t = [t for t in esc.terminos if t.concepto == "revenue_realizado"]
    assert len(t) == 1
    assert t[0].haircut == AD.SIN_HAIRCUT and t[0].valor == 100e6
    assert esc.revenue_por_escenario()["bear"] == 100e6


def test_contratado_entra_con_haircut_autorizado():
    mags = {"backlog": {"monto": 50e6, "fact_key": "respaldo_backlog",
                        "evidence_class": AD.CONTRACT_COUNTERPARTY, "cita": "backlog $50M"}}
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags,
                               politicas_haircut={AD.CONVERSION_HISTORICA: 0.7})
    bk = [t for t in esc.terminos if t.concepto == "backlog"]
    assert len(bk) == 1
    assert bk[0].valor == 50e6 * 0.7            # haircut aplicado
    assert bk[0].valor_bruto == 50e6            # bruto trazado
    assert bk[0].haircut == AD.CONVERSION_HISTORICA


def test_management_claim_va_al_option_ledger():
    # AAOI/Amazon $4B: citado, pero management_claim → no valúa, va al ledger.
    mags = {"amazon_4b": {"monto": 4000e6, "fact_key": "respaldo_backlog",
                          "evidence_class": AD.MANAGEMENT_CLAIM, "cita": "up to $4 billion"}}
    esc = C.compilar_escenario("AAOI", _snap(), DET, "Growth", magnitudes=mags,
                               politicas_haircut={AD.CONVERSION_HISTORICA: 0.7})
    assert not [t for t in esc.terminos if t.concepto == "amazon_4b"]     # NO en el operable
    assert any(o.concepto == "amazon_4b" for o in esc.option_ledger)      # SÍ en el ledger
    assert esc.revenue_por_escenario()["bull"] == 100e6                    # el $4B no infló el bull


def test_sin_valor_de_haircut_se_excluye_no_se_inventa():
    mags = {"backlog": {"monto": 50e6, "fact_key": "respaldo_backlog",
                        "evidence_class": AD.CONTRACT_COUNTERPARTY}}
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags)  # sin politicas_haircut
    assert not [t for t in esc.terminos if t.concepto == "backlog"]
    assert any(r["destino"] == "excluido" for r in esc.rechazados)


def test_cobertura_se_reporta():
    esc = C.compilar_escenario("X", _snap(2), DET, "Growth")
    assert 0.0 < esc.cobertura <= 1.0


# --- Vía contract_type (doc 28 §1): retención por tipo de contrato desde política ---

def test_rpo_como_cancelable_backlog_entra_con_retencion_060():
    mags = {"rpo": {"monto": 100e6, "contract_type": "cancelable_backlog",
                    "fact_key": "respaldo_backlog", "cita": "XBRL RPO"}}
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags)
    t = [t for t in esc.terminos if t.concepto == "rpo"][0]
    assert t.valor == 100e6 * 0.60 and t.valor_bruto == 100e6   # retención 0.60 de política
    assert t.regla == "retencion_por_tipo_contrato" and t.haircut_source == "cancelable_backlog"
    assert esc.revenue_por_escenario()["bull"] == 100e6 + 100e6 * 0.60


def test_tipo_asumido_marca_es_piso_y_dispara_evidencia_insuficiente():
    # RPO asumido que DOMINA el incremento del bull → evidencia_insuficiente (no sleeve completo).
    mags = {"rpo": {"monto": 100e6, "contract_type": "cancelable_backlog", "tipo_asumido": True}}
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags)
    t = [t for t in esc.terminos if t.concepto == "rpo"][0]
    assert t.es_piso and t.haircut_source == "cancelable_backlog(asumido)"
    assert esc.evidencia_insuficiente is True


def test_tipo_extraido_no_dispara_evidencia_insuficiente():
    # el mismo backlog, pero con el tipo EXTRAÍDO (no asumido) → el flag se apaga (premia extraer).
    mags = {"rpo": {"monto": 100e6, "contract_type": "cancelable_backlog"}}  # sin tipo_asumido
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags)
    assert esc.evidencia_insuficiente is False


def test_contract_type_condicional_va_al_ledger_no_valua():
    # IDIQ ceiling / conditional award → ledger O3, no infla el bull (doc 28 §1).
    mags = {"idiq": {"monto": 500e6, "contract_type": "idiq_ceiling", "cita": "up to $500M"}}
    esc = C.compilar_escenario("X", _snap(), DET, "Growth", magnitudes=mags)
    assert not [t for t in esc.terminos if t.concepto == "idiq"]
    assert any(o.concepto == "idiq" for o in esc.option_ledger)
    assert esc.revenue_por_escenario()["bull"] == 100e6


def test_tipo_contrato_rpo_mapea_cancelabilidad():
    # E1: el hecho citado backlog_no_cancelable → (contract_type, tipo_asumido)
    assert C.tipo_contrato_rpo(True) == ("firm_po", False)      # firme extraído
    assert C.tipo_contrato_rpo(False) == ("cancelable_backlog", False)  # cancelable extraído
    assert C.tipo_contrato_rpo(None) == ("cancelable_backlog", True)    # sin extraer → asumido
