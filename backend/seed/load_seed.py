"""Carga seed inicial: 7 sectores, macro v1.0, 20 tickers iniciales.

Idempotente — se puede correr múltiples veces. No sobrescribe datos existentes.
Uso:
    python -m backend.seed.load_seed
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from backend.database import init_db, session_scope
from backend.models import EstadoFicha, Ficha, Macro, Sector

SEED_DIR = Path(__file__).resolve().parent


def _load_yaml(filename: str) -> Any:
    path = SEED_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seed_sectores() -> int:
    data = _load_yaml("sectores.yaml")
    created = 0
    with session_scope() as session:
        for row in data:
            exists = session.query(Sector).filter_by(nombre=row["nombre"]).first()
            if exists:
                continue
            session.add(
                Sector(
                    nombre=row["nombre"],
                    prioridad=row.get("prioridad"),
                    horizonte=row.get("horizonte"),
                    notas=row.get("notas"),
                    ultima_actualizacion=datetime.utcnow(),
                )
            )
            created += 1
    return created


def seed_macro() -> bool:
    data = _load_yaml("macro_v1.yaml")
    with session_scope() as session:
        exists = session.query(Macro).filter_by(version=data["version"], activa=True).first()
        if exists:
            return False
        session.query(Macro).update({"activa": False})
        session.add(
            Macro(
                fase_actual=data["fase_actual"],
                postura_capital=data["postura_capital"],
                version=data["version"],
                notas=data["notas"],
                fecha_actualizacion=datetime.utcnow(),
                activa=True,
            )
        )
    return True


def seed_tickers() -> int:
    data = _load_yaml("tickers_iniciales.yaml")
    created = 0
    with session_scope() as session:
        for row in data:
            ticker = row["ticker"].upper()
            exists = session.query(Ficha).filter_by(ticker=ticker).first()
            if exists:
                continue
            session.add(
                Ficha(
                    ticker=ticker,
                    nombre=row["nombre"],
                    sector=row["sector"],
                    driver_macro=row.get("driver_macro"),
                    origen="Manual",
                    estado=EstadoFicha.CANDIDATA.value,
                    version_tesis_macro="v1.0",
                    cambios_score=[],
                    cambios_estado=[
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "estado_anterior": None,
                            "estado_nuevo": EstadoFicha.CANDIDATA.value,
                            "motivo": "seed inicial",
                        }
                    ],
                )
            )
            created += 1
    return created


def main() -> None:
    init_db()
    sectores = seed_sectores()
    macro_loaded = seed_macro()
    tickers = seed_tickers()
    print(f"✓ Sectores creados:  {sectores}")
    print(f"✓ Macro v1.0 activa: {'sí' if macro_loaded else 'ya existía'}")
    print(f"✓ Tickers cargados:  {tickers}")


if __name__ == "__main__":
    main()
