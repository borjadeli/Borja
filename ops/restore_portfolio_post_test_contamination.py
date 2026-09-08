"""Restaura portfolio S/LEU/TENB tras contaminación por tests 2026-04-21.

Contexto: los tests en test_portfolio_juez::TestFlujoAprobacion forzaron
`Portfolio_Activo → Candidata` para vaciar el portfolio, y metieron NVTS como
ficha sintética (score 8.5, sizing 10, precio $13). Al correr el suite contra
la DB real, el portfolio quedó corrompido.

Esta restauración:
1. Pausa el sistema para que el scheduler no interfiera.
2. Devuelve S/LEU/TENB a Portfolio_Activo con sizings del checkpoint.
3. Saca NVTS del Portfolio y lo devuelve a Universo (su estado pre-contaminación).
4. Registra la restauración en cambios_estado de cada ficha.
5. Reanuda el sistema.
"""
from __future__ import annotations

from backend import panic
from backend.database import session_scope
from backend.models import Ficha
from backend.utils import utcnow


# Valores tomados del checkpoint project_checkpoint_paper_trading.md y del
# último análisis real registrado en cambios_estado (pre-contaminación).
PORTFOLIO_REAL = {
    "S":    {"sizing": 4.9, "precio_entrada": 14.32},
    "LEU":  {"sizing": 3.5, "precio_entrada": 199.61},
    "TENB": {"sizing": 4.9, "precio_entrada": 19.52},
}

# NVTS entró sintéticamente por tests. Su estado real pre-contaminación era
# Universo con score 4.96 (según cambios_estado del 2026-04-21T11:29).
NVTS_RESTORE = {"estado": "Universo", "sizing": None, "precio_entrada": None}


def _append_cambio(ficha: Ficha, estado_nuevo: str, motivo: str, now) -> None:
    cambios = list(ficha.cambios_estado or [])
    cambios.append({
        "timestamp": now.isoformat(),
        "estado_anterior": ficha.estado,
        "estado_nuevo": estado_nuevo,
        "motivo": motivo,
    })
    ficha.cambios_estado = cambios


def main() -> None:
    print("== Pausando sistema ==")
    panic.pausar(motivo="restauración portfolio post-contaminación tests", by="admin")

    try:
        now = utcnow()
        motivo_restore = "restauración post-contaminación tests 2026-04-21"

        with session_scope() as s:
            # 1) S / LEU / TENB → Portfolio_Activo
            for ticker, vals in PORTFOLIO_REAL.items():
                f = s.query(Ficha).filter_by(ticker=ticker).first()
                if f is None:
                    print(f"  WARNING {ticker}: ficha no existe — skip")
                    continue
                estado_pre = f.estado
                _append_cambio(f, "Portfolio_Activo", motivo_restore, now)
                f.estado = "Portfolio_Activo"
                f.sizing_actual = vals["sizing"]
                f.precio_entrada = vals["precio_entrada"]
                # piramidación: si el deep research post-contaminación re-evaluó
                # con score >= previo, el writer ya la re-armó. Si no, queda False.
                print(f"  {ticker}: {estado_pre} → Portfolio_Activo "
                      f"(sizing {vals['sizing']}%, entry ${vals['precio_entrada']})")

            # 2) NVTS → Universo
            f = s.query(Ficha).filter_by(ticker="NVTS").first()
            if f is None:
                print("  WARNING NVTS: ficha no existe — skip")
            else:
                estado_pre = f.estado
                _append_cambio(f, NVTS_RESTORE["estado"], motivo_restore, now)
                f.estado = NVTS_RESTORE["estado"]
                f.sizing_actual = NVTS_RESTORE["sizing"]
                f.precio_entrada = NVTS_RESTORE["precio_entrada"]
                print(f"  NVTS: {estado_pre} → {NVTS_RESTORE['estado']} "
                      f"(sizing cleared, precio_entrada cleared)")

        print("\n== Verificación final ==")
        with session_scope() as s:
            port = s.query(Ficha).filter_by(estado="Portfolio_Activo").all()
            print(f"Portfolio_Activo: {len(port)}/5 slots")
            for f in sorted(port, key=lambda x: x.score_vigente or 0, reverse=True):
                print(f"  {f.ticker:6} score={f.score_vigente:5} sizing={f.sizing_actual}% "
                      f"entry=${f.precio_entrada}")

    finally:
        print("\n== Reanudando sistema ==")
        panic.reanudar(by="admin")


if __name__ == "__main__":
    main()
