"""Tests del contraste numérico claim↔XBRL (v2 P1 paso 3). Casos reales del smoke. Sin API."""
from datetime import date

from backend.agentes.contraste import contrastar_numero
from backend.agentes.provenance import DataKind, DataPoint, Source


def _ref(value, metric="x", period_type="FY"):
    return DataPoint(entity="OKLO", metric=metric, value=value, unit="USD", kind=DataKind.ORIGINAL,
                     source=Source(name="SEC XBRL"), known_at=date(2026, 3, 17), period_type=period_type)


def test_signo_perdida_coincide_en_magnitud():
    # "pérdida de US$139.3M" (magnitud) vs OperatingIncomeLoss = −139.294M → NO se rechaza (el bug de IA 1)
    r = contrastar_numero(139.3, _ref(-139_294_000), escala="M", decimales=1)
    assert r.ok and r.estado == "match_magnitud"


def test_signo_firmado_coincide_exacto():
    # si el extractor ya firmó la pérdida (−139.3), coincide exacto
    r = contrastar_numero(-139.3, _ref(-139_294_000), escala="M", decimales=1)
    assert r.estado == "match"


def test_redondeo_miles_de_millones_no_se_rechaza():
    # "~US$1.4B" vs 1.43B: 2.1% lo rechazaba; media-unidad del último dígito (0.05B) lo acepta
    r = contrastar_numero(1.4, _ref(1_430_000_000), escala="B", decimales=1)
    assert r.estado == "match"


def test_escala_se_normaliza():
    # el mismo número en miles (139300 K) contra 139.3M
    r = contrastar_numero(139_300, _ref(139_300_000), escala="K", decimales=0)
    assert r.estado == "match"


def test_periodo_distinto_no_contrastable():
    r = contrastar_numero(155, _ref(600_000_000, period_type="FY"), escala="M", periodo="Q")
    assert r.estado == "no_contrastable" and not r.ok


def test_contradiccion_real_es_contradice():
    # claim 200M vs XBRL 139M (fuera de tolerancia, mismo signo) → contradice (→ FAIL en el verificador)
    r = contrastar_numero(200, _ref(139_294_000), escala="M", decimales=0)
    assert r.contradice and not r.ok


def test_sin_referencia_no_contrastable():
    assert contrastar_numero(100, None, escala="M").estado == "no_contrastable"
    assert contrastar_numero(100, _ref(None), escala="M").estado == "no_contrastable"
