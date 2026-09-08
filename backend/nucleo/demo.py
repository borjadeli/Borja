"""Ejemplos ilustrativos del núcleo nuevo para el dashboard (sombra).

Corre el flujo determinista §2 sobre empresas SINTÉTICAS representativas, para que
el operador VEA el rediseño funcionando sin gastar API ni depender de IBKR. NO son
posiciones reales: son ilustraciones del mecanismo (arquetipo → gate → mérito →
sizing → vías). Puro, instantáneo, sin red.
"""
from __future__ import annotations

from backend.nucleo.arquetipo import HechosArquetipo
from backend.nucleo.flujo import EntradaEmpresa, armar_cartera, evaluar_empresa
from backend.nucleo.fragility import HechosFragility
from backend.nucleo.gate import HechosGate, Trigger
from backend.nucleo.quality import HechosQuality
from backend.nucleo.salida import EstadoPosicion, evaluar_salida


def _u1():
    return [
        Trigger("dilución >20%", "20%", "2026-12-31", "A", es_estructura_capital=True),
        Trigger("pérdida cliente ancla", "churn", "2026-09-30", "A", atado_a_hecho_de_entrada=True),
    ]


def ejemplos_entrada() -> list[dict]:
    """Tres empresas sintéticas que muestran candidata / rechazo / watchlist."""
    casos = [
        EntradaEmpresa(
            ticker="DEMO·GROWTH-SANA",
            hechos_arquetipo=HechosArquetipo(revenue_elegible=120_000_000, crecimiento_elegible_yoy=0.40),
            hechos_gate=HechosGate(arquetipo="", triggers=_u1(),
                                   growth_desglose_organico_disponible=True, growth_organico_pct=0.85,
                                   growth_hecho_continuidad=True),
            hechos_fragility=HechosFragility(financiacion_completa_cerrada=True, redundancia_comercial_real=True),
            hechos_quality=HechosQuality(margen_bruto=0.60, margen_en_expansion=True,
                                         crecimiento_organico_elegible=0.40, revenue_recurrente=True,
                                         hechos_comerciales_independientes=3, ventaja_estructural=True),
            precio=50, bull=100, bear=40),
        EntradaEmpresa(
            ticker="DEMO·PREREV-LILIUM",
            hechos_arquetipo=HechosArquetipo(revenue_elegible=4_000_000),
            hechos_gate=HechosGate(arquetipo="", triggers=_u1(),
                                   prerev_p1_tipo="contrato_firmado", prerev_p1_fuente="A",
                                   prerev_catalizador_meses=10, prerev_catalizador_tiene_metrica=True,
                                   prerev_fecha_congelada=True,
                                   caja_ultimo_filing=20_000_000, burn_mensual_prom_2t=5_000_000,
                                   meses_hasta_hito_financiado=10),  # P3 NO cubre.
            hechos_fragility=HechosFragility(punto_unico_de_falla=True),
            hechos_quality=HechosQuality(margen_bruto=0.10),
            precio=8, bull=30, bear=5),
        EntradaEmpresa(
            ticker="DEMO·PREREV-TODAVIA-NO",
            hechos_arquetipo=HechosArquetipo(revenue_elegible=6_000_000),
            hechos_gate=HechosGate(arquetipo="", triggers=_u1(),
                                   prerev_p1_tipo="contrato_firmado", prerev_p1_fuente="A",
                                   prerev_catalizador_meses=14, prerev_catalizador_tiene_metrica=True,
                                   prerev_fecha_congelada=True,
                                   caja_ultimo_filing=100_000_000, burn_mensual_prom_2t=2_000_000,
                                   meses_hasta_hito_financiado=6),  # P2 a 14m → todavía no.
            hechos_fragility=HechosFragility(dependencia_con_respaldo=True),
            hechos_quality=HechosQuality(margen_bruto=0.30),
            precio=10, bull=40, bear=8),
    ]
    return [evaluar_empresa(c) for c in casos]


def ejemplos_salida() -> list[dict]:
    """Tres posiciones vivas sintéticas que muestran las 5 vías de salida."""
    return [
        evaluar_salida(EstadoPosicion(ticker="DEMO·GOVERNANCE", arquetipo="Growth",
                                      hard_governance_events=["auditor_resignation"])),
        evaluar_salida(EstadoPosicion(ticker="DEMO·ASIMETRIA-MUERTA", arquetipo="Growth",
                                      bull=60, precio=58, bear=45)),  # (60-58)/(58-45)=0.15<0.5
        evaluar_salida(EstadoPosicion(ticker="DEMO·SANA", arquetipo="Madura",
                                      bull=100, precio=50, bear=40, peso_vivo=0.10, hardcap_vigente=0.25)),
    ]


def cartera_demo() -> dict:
    """Arma el mix con las candidatas demo (muestra normalización + Hard Cap + cubo)."""
    return armar_cartera(ejemplos_entrada())
