"""Orquestación del canal de juicio (flujo_pm) — determinismo pone el techo, el PM elige adentro (doc 39/47)."""
from backend.nucleo import flujo_pm, juicio, politica
from backend.nucleo.juicio_llm import MemoJuicio


class _C:
    def __init__(self, ticker, cap, elegible=True):
        self.ticker = ticker; self.cap = cap; self.elegible = elegible


class _H:
    def __init__(self, ticker, a_carril=False):
        self.ticker = ticker; self.a_carril_burden = a_carril
        self.estado_ruteo = "COMERCIAL_MADURO"; self.revenue_ttm = 1e9
        self.g_D_reverse = 0.15; self.sbc_over_revenue = 0.2; self.runway_anos = 4
        self.flags = []; self.demanda_quote = None; self.revenue_contratado = None
        self.shares_growth_24m = 0.05


# --- banda desde el cap: techo = cap, base = piso (4%) ---
def test_banda_base_es_piso():
    b = flujo_pm.banda_desde_candidato(_C("S", 0.054))
    assert b.techo == 0.054
    assert abs(b.base - politica.CAP_FLOOR_BURN) < 1e-9      # base = piso 4%, no el techo
    assert b.piso == 0.0


def test_banda_cap_en_piso_sin_tramo():
    b = flujo_pm.banda_desde_candidato(_C("NET", 0.04))
    assert b.techo == 0.04 and b.base == 0.04                # cap = piso → sin tramo para PRIORITY


def _judge_factory(mapa):
    def judge(ticker, ev, **kw):
        return mapa.get(ticker, MemoJuicio(ticker=ticker, etiqueta="PASS"))
    return judge


# --- orquestación end-to-end (stub judge, sin LLM) ---
def test_pass_despliega_piso():
    items = [(_C("S", 0.054), _H("S"))]
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory({}), usar_web=False)
    d = libro.decisiones[0]
    assert d.etiqueta == "PASS"
    assert abs(d.size_final - politica.CAP_FLOOR_BURN) < 1e-9   # PASS → base = piso


def test_priority_con_falsador_sube_hacia_techo():
    memo = MemoJuicio(ticker="S", etiqueta="PRIORITY_HIGH", falsador="si pierde el cliente X",
                      fecha_falsador="2026-12-31", bull="b", bear="be")
    items = [(_C("S", 0.08), _H("S"))]
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory({"S": memo}), usar_web=False)
    d = libro.decisiones[0]
    assert d.size_final > politica.CAP_FLOOR_BURN     # subió por encima del piso
    assert d.size_final <= 0.08                        # NUNCA supera el techo


def test_priority_sin_falsador_no_promueve():
    memo = MemoJuicio(ticker="S", etiqueta="PRIORITY_HIGH")   # sin falsador
    items = [(_C("S", 0.08), _H("S"))]
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory({"S": memo}), usar_web=False)
    assert abs(libro.decisiones[0].size_final - politica.CAP_FLOOR_BURN) < 1e-9   # cae a base (PASS)


def test_veto_a_cero():
    memo = MemoJuicio(ticker="X", etiqueta="THESIS_BROKEN")
    items = [(_C("X", 0.06), _H("X"))]
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory({"X": memo}), usar_web=False)
    assert libro.decisiones[0].size_final == 0.0


def test_carril_se_saltea():
    items = [(_C("RKLB", 0.0), _H("RKLB", a_carril=True)), (_C("S", 0.054), _H("S"))]
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory({}), usar_web=False)
    tickers = [d.ticker for d in libro.decisiones]
    assert "RKLB" not in tickers and "S" in tickers    # el carril no pasa por el PM


def test_presupuesto_limita_promociones():
    # 3 PRIORITY con falsador, presupuesto=1 → solo 1 promueve, el resto cae a base
    memo = lambda t: MemoJuicio(ticker=t, etiqueta="PRIORITY_HIGH", falsador="f", fecha_falsador="2026-12-31")
    items = [(_C(t, 0.08), _H(t)) for t in ("A", "B", "C")]
    mapa = {t: memo(t) for t in ("A", "B", "C")}
    libro = flujo_pm.orquestar_pm(items, "2026-09-04", judge=_judge_factory(mapa), usar_web=False, presupuesto=1)
    subieron = [d for d in libro.decisiones if d.size_final > politica.CAP_FLOOR_BURN + 1e-9]
    assert len(subieron) == 1                          # presupuesto respetado
