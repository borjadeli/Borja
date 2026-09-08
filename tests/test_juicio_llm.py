"""Interfaz PM-LLM del juicio (doc 39 §2.6, Bloque 3): validación de etiqueta + guardrails + allocator."""
from backend.nucleo import juicio_llm as JL
from backend.nucleo.juicio import Banda, aplicar_juicio


def test_etiqueta_invalida_cae_a_pass(monkeypatch):
    # el LLM devuelve una etiqueta fuera del set → PASS conservador (no promueve)
    class _R:
        parsed_json = {"etiqueta": "COMPRA_FUERTE", "bull": "x", "bear": "y"}
        metadata = {}
    monkeypatch.setattr(JL.llm, "call_llm_json", lambda *a, **k: _R())
    m = JL.evaluar_juicio("X", {}, usar_web=False)
    assert m.etiqueta == "PASS" and m.valido is False


def test_etiqueta_valida_se_conserva(monkeypatch):
    class _R:
        parsed_json = {"etiqueta": "priority_high", "bull": "recurrente 80% GM", "bear": "caro",
                       "falsador": "si NRR<100% en 2Q", "fecha_falsador": "2026-12-31", "razon": "calidad"}
        metadata = {}
    monkeypatch.setattr(JL.llm, "call_llm_json", lambda *a, **k: _R())
    m = JL.evaluar_juicio("RBRK", {}, usar_web=False)
    assert m.etiqueta == "PRIORITY_HIGH" and m.valido is True and m.falsador


def test_llm_error_cae_a_pass(monkeypatch):
    def _boom(*a, **k): raise RuntimeError("api down")
    monkeypatch.setattr(JL.llm, "call_llm_json", _boom)
    m = JL.evaluar_juicio("X", {}, usar_web=False)
    assert m.etiqueta == "PASS" and m.valido is False   # ausencia de juicio = PASS (no tumba el pipeline)


def test_memo_a_intervencion_y_allocator(monkeypatch):
    # el memo válido con falsador → Intervencion → allocator sube DENTRO de la banda
    class _R:
        parsed_json = {"etiqueta": "PRIORITY_HIGH", "bull": "b", "bear": "be",
                       "falsador": "si pierde cliente ancla", "fecha_falsador": "2026-12-31", "razon": "r"}
        metadata = {}
    monkeypatch.setattr(JL.llm, "call_llm_json", lambda *a, **k: _R())
    memo = JL.evaluar_juicio("RBRK", {}, usar_web=False)
    iv = JL.a_intervencion(memo, "2026-08-27")
    assert iv.falsador and iv.memo_hash
    res = aplicar_juicio([iv], {"RBRK": Banda(0.0, 0.04, 0.08)}, presupuesto=3)
    assert res[0].size_asignado == 0.08                 # PRIORITY_HIGH → sube al techo (dentro de banda)


def test_juicio_no_emite_numero():
    # el memo NO tiene ningún campo de tamaño/peso — solo etiqueta + memo (invariante de diseño)
    from dataclasses import fields
    campos = {f.name for f in fields(JL.MemoJuicio)}
    assert "size" not in campos and "peso" not in campos and "cap" not in campos
