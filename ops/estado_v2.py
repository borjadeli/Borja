"""Digest advisory del estado v2: qué tenés, por qué, y qué lo mataría. Para LEER entre ciclos.

Junta el paper fiel (`data/paper_v2.db`) + el ledger de decisiones + los dossiers del cache en un texto
legible. NO gasta API (solo precios de market_data para marcar las posiciones).

Uso:  .venv/bin/python -m ops.estado_v2
"""
from __future__ import annotations

import json
import sys
from datetime import date

from backend.agentes.datos_reales import abrir_paper, precios_de, recolectar_snapshots
from backend.agentes.ips import IPS
from backend.agentes.ledger_decisiones import LedgerDecisiones
from backend.agentes.orquestador import _CACHE_PATH
from backend.agentes.presupuesto import gastado_mes_usd
from backend.agentes.resumen_v2 import DossierResumen, PosicionResumen, render_digest
from backend.ledger import core


def construir_digest() -> str:
    """Arma el digest advisory y lo DEVUELVE (texto). `main()` lo imprime; el job semanal lo mail-ea/persiste."""
    ips = IPS.cargar()
    tope = float(ips.cfg.get("presupuesto_usd_mes", 40.0))

    s = abrir_paper()
    try:
        tickers = list(core.proyectar(s, {})["posiciones"].keys())
        precios = precios_de(recolectar_snapshots(tickers)) if tickers else {}
        est = core.proyectar(s, precios)
    finally:
        s.close()
    equity = est["equity"]
    posiciones = [PosicionResumen(t, p.shares, precios.get(t),
                                  (p.shares * precios.get(t, 0.0)) / equity if equity > 0 else 0.0)
                  for t, p in est["posiciones"].items()]
    caja_pct = est["caja"] / equity if equity > 0 else 1.0

    ledger_dec = LedgerDecisiones().decisiones()
    ciclo = max((d.ciclo for d in ledger_dec), default="(sin decisiones)")
    decisiones = [d for d in ledger_dec if d.ciclo == ciclo]

    cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8")) if _CACHE_PATH.exists() else {}
    relevantes = {d.ticker for d in decisiones} | set(est["posiciones"])
    dossiers: dict[str, DossierResumen] = {}
    for tk in sorted(relevantes):
        e = cache.get(tk)
        if not e:
            continue
        d, v = e["dossier"], e["verif"]
        dossiers[tk] = DossierResumen(
            veredicto=v["veredicto"], bull=d["bull"]["tesis"][:220], bear=d["bear"]["tesis"][:220],
            falsador=d["falsador"]["afirmacion"][:180], falsador_fecha=d["falsador"]["fecha_limite"],
            red_flags=[f"{r['tipo']}[{r['severidad']}]" for r in d.get("red_flags", [])])

    from backend.agentes.carteras_sombra import LedgerSombras
    return render_digest(ciclo=ciclo, equity=equity, caja_pct=caja_pct, posiciones=posiciones,
                         decisiones=decisiones, dossiers=dossiers,
                         gasto_mes=(gastado_mes_usd(date.today()) or 0.0), tope_mes=tope,
                         sombras=LedgerSombras().resumen())


def enviar_digest_semanal() -> str:
    """Job semanal (scheduler, lunes 8:00 ET): arma el digest, lo PERSISTE en data/digests/ y lo mail-ea
    (dry-run si no hay SMTP). Así la evaluación semanal sale sola. Devuelve el texto (para logs/tests)."""
    from pathlib import Path
    texto = construir_digest()
    d = Path("data/digests")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"digest_{date.today().isoformat()}.txt").write_text(texto, encoding="utf-8")
    try:
        from backend.services.mailer import send_email
        send_email(subject=f"Digest semanal {date.today().isoformat()}",
                   body_html=f"<pre>{texto}</pre>", body_text=texto, tag="digest")
    except Exception as e:  # noqa: BLE001 — el mail no debe tumbar el job; el archivo ya quedó persistido
        print(f"aviso: no pude enviar el digest por mail: {e}")
    return texto


def main() -> int:
    print(construir_digest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
