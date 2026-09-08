"""Canal de juicio (doc 39 §2.6, Bloque 3): allocator etiqueta→banda + invariantes duros + presupuesto."""
from backend.nucleo.juicio import Banda, Intervencion, asignar_size, aplicar_juicio


def _b(piso=0.0, base=0.04, techo=0.08):
    return Banda(piso, base, techo)


# --- invariantes duros del allocator ---
def test_veto_va_a_cero():
    assert asignar_size(_b(), "VETO")[0] == 0.0
    assert asignar_size(_b(), "THESIS_BROKEN")[0] == 0.0


def test_pass_hold_no_mueven():
    assert asignar_size(_b(base=0.04), "PASS")[0] == 0.04
    assert asignar_size(_b(base=0.04), "HOLD")[0] == 0.04


def test_priority_sube_dentro_de_banda():
    # base 0.04, techo 0.08. HIGH → todo el gap (0.08), MEDIUM → mitad (0.06), LOW → cuarto (0.05)
    assert asignar_size(_b(base=0.04, techo=0.08), "PRIORITY_HIGH")[0] == 0.08
    assert asignar_size(_b(base=0.04, techo=0.08), "PRIORITY_MEDIUM")[0] == 0.06
    assert asignar_size(_b(base=0.04, techo=0.08), "PRIORITY_LOW")[0] == 0.05


def test_priority_NUNCA_supera_el_techo():
    # el juicio jamás pasa el cap de supervivencia
    s, _ = asignar_size(_b(base=0.08, techo=0.08), "PRIORITY_HIGH")
    assert s == 0.08


def test_admit_probe_rescata_falso_negativo():
    # un nombre con base 0 (el determinista lo puso en 0) → ADMIT_PROBE le da un probe chico
    s, _ = asignar_size(_b(base=0.0, techo=0.08), "ADMIT_PROBE")
    assert 0 < s <= 0.02


def test_etiqueta_desconocida_es_pass():
    assert asignar_size(_b(base=0.04), "CUALQUIERA")[0] == 0.04


# --- presupuesto de promociones ---
def test_presupuesto_limita_promociones():
    ivs = [Intervencion(f"T{i}", "PRIORITY_HIGH", "2026-01-01", falsador="x", fecha_falsador="2026-06") for i in range(5)]
    bandas = {f"T{i}": _b(base=0.04, techo=0.08) for i in range(5)}
    res = aplicar_juicio(ivs, bandas, presupuesto=2)
    promovidas = [r for r in res if r.size_asignado > 0.04 + 1e-9]
    assert len(promovidas) == 2                          # solo 2 promociones (presupuesto)
    assert any("presupuesto" in r.motivo for r in res)


def test_promocion_sin_falsador_no_se_ejecuta():
    iv = Intervencion("X", "PRIORITY_HIGH", "2026-01-01")   # sin falsador
    res = aplicar_juicio([iv], {"X": _b(base=0.04, techo=0.08)}, presupuesto=3)
    assert res[0].size_asignado == 0.04 and "SIN falsador" in res[0].motivo


def test_veto_no_consume_presupuesto():
    ivs = [Intervencion("V", "VETO", "2026-01-01"),
           Intervencion("P", "PRIORITY_HIGH", "2026-01-01", falsador="x", fecha_falsador="2026-06")]
    res = aplicar_juicio(ivs, {"V": _b(base=0.04), "P": _b(base=0.04, techo=0.08)}, presupuesto=1)
    d = {r.ticker: r for r in res}
    assert d["V"].size_asignado == 0.0 and d["P"].size_asignado == 0.08   # el veto no gastó presupuesto
