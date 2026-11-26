"""P1 (doc 91 §8, IA2 §3.5/3.6 + review-2) — registro de la decisión en SOMBRA. Por cada decisión del comité guarda qué
habría decidido P1 (el VeredictoSombra), si eso CAMBIARÍA la propuesta del PM (BLOQUEA/DIFIERE/ACHICA), con qué peso la
habría dejado (`peso_permitido`), y qué campos portantes faltaron. Append-only a `data/shadow_p1.jsonl`. NO aplica nada.

Correcciones review-2 (IA2): (a) el append FALLA VISIBLE — `registrar_corrida` chequea registros==decisiones y levanta
si se perdió uno (la sombra que pierde registros silenciosamente miente la medición); (b) 'cambiaría' mira también el
TAMAÑO (P1 a veces ACHICA en vez de bloquear), no solo acción+permiso; (c) cada motivo lleva CATEGORÍA
DATO/ECONOMÍA/IPS/VERIF para medir de qué tipo es el bloqueo; (d) clave anti-duplicados ciclo+ticker+versión.
Determinista, $0.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shadow_p1.jsonl"

# ¿la acción del PM BUSCA desplegar/mover capital? (si P1 la bloquea/difiere/achica, cambia la decisión)
_ACCIONES_QUE_MUEVEN = {"abrir", "aumentar", "reducir", "salir"}
_APERTURAS = {"abrir", "aumentar"}
_EPS = 1e-9


def categoria_motivo(motivo: str) -> str:
    """Clasifica un motivo de P1 en DATO / VERIF / IPS / ECONOMÍA / OTRO (IA2 §3.6: medir DE QUÉ tipo es el bloqueo)."""
    m = (motivo or "").lower()
    if any(k in m for k in ("verificación", "verif", " fail", "review", "pass")):
        return "VERIF"
    if any(k in m for k in ("no chequeado", "ausente", "null", "no finito", "no computado", "malformado",
                            "bloqueo de datos", "desconocid", "sin comparación", "dossier", "excepción")):
        return "DATO"
    if any(k in m for k in ("tier", "cap", "stub", "banda de peso", "mínimo", "máximo", "concentrac", "ips",
                            "opcionalidad", "peso objetivo")):
        return "IPS"
    if any(k in m for k in ("banda", "recorte", "margen", "p_implícita", "pre_revenue", "dominada", "mérito",
                            "falsador", "métrica")):
        return "ECONOMIA"
    return "OTRO"


def _tipo_cambio(accion_pm: str, permiso: str, peso_propuesto, peso_permitido) -> str | None:
    """Cómo cambiaría P1 la propuesta del PM, o None si no la cambia."""
    accion = (accion_pm or "").strip().lower()
    if accion not in _ACCIONES_QUE_MUEVEN:
        return None
    if permiso == "BLOQUEAR":
        return "BLOQUEA"
    if permiso == "DIFERIR":
        return "DIFIERE"
    # EJECUTAR: cambia solo si el cap de P1 ACHICA el peso que proponía el PM (apertura/aumento).
    if accion in _APERTURAS and peso_propuesto is not None and peso_permitido is not None \
            and peso_permitido < peso_propuesto - _EPS:
        return "ACHICA"
    return None


def construir_shadow_decision(*, ciclo: str, ticker: str, accion_pm: str, veredicto, dossier_ref: str | None = None,
                              peso_propuesto: float | None = None, ips_version: str = "p1-v1") -> dict:
    """`veredicto` = VeredictoSombra (de evaluar_sombra/harness). `peso_propuesto` = el peso que pedía el PM (para
    detectar cuándo P1 ACHICA en vez de bloquear)."""
    tk = ticker.upper()
    tipo_cambio = _tipo_cambio(accion_pm, veredicto.permiso, peso_propuesto, veredicto.cap)
    return {
        "tipo": "shadow_p1",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ciclo": ciclo,
        "ips_version": ips_version,
        "dedup_key": f"{ciclo}|{tk}|{ips_version}",         # anti-duplicados: una decisión por ciclo+ticker+versión
        "ticker": tk,
        "evidence_ref": dossier_ref,
        "propuesta_pm": accion_pm,
        "peso_propuesto": peso_propuesto,
        "shadow": {
            "arquetipo": veredicto.arquetipo,
            "banda": veredicto.banda,
            "tier": veredicto.tier,
            "cap": veredicto.cap,
            "peso_permitido": veredicto.cap,               # con qué peso P1 dejaría la posición (techo)
            "permiso": veredicto.permiso,
            "liga": getattr(veredicto, "liga", None),
            "motivos": [{"motivo": m, "categoria": categoria_motivo(m)} for m in veredicto.motivos],
        },
        "tipo_cambio": tipo_cambio,                         # BLOQUEA / DIFIERE / ACHICA / None
        "cambiaria_la_decision": tipo_cambio is not None,
        "data_quality": {"missing_fields": list(veredicto.missing_fields)},
    }


def registrar_shadow(record: dict, *, path: Path | str | None = None) -> None:
    """Append de UN registro. NO atrapa errores de IO: la sombra que pierde registros en silencio miente la medición."""
    p = Path(path or _PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def registrar_corrida(records: list[dict], *, path: Path | str | None = None) -> int:
    """Registra TODOS los records de una corrida y chequea el invariante registros_escritos == decisiones (IA2:
    el append debe fallar VISIBLE). Devuelve cuántas líneas se agregaron; levanta si no coincide."""
    p = Path(path or _PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    antes = sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0
    for r in records:
        registrar_shadow(r, path=p)
    despues = sum(1 for _ in p.open(encoding="utf-8"))
    escritos = despues - antes
    if escritos != len(records):
        raise RuntimeError(f"shadow log perdió registros: escritos={escritos} != decisiones={len(records)}")
    return escritos


def resumen_sombra(records: list[dict]) -> dict:
    """Agregados de IA2 §3.6 sobre los registros de un período (para el monitor)."""
    n = len(records) or 1
    cambios = sum(1 for r in records if r.get("cambiaria_la_decision"))
    bloqueadas = sum(1 for r in records if r.get("shadow", {}).get("permiso") == "BLOQUEAR")
    por_datos = sum(1 for r in records if r.get("data_quality", {}).get("missing_fields"))
    # de qué tipo son los motivos que P1 usó para cambiar la decisión
    cat: dict[str, int] = {}
    for r in records:
        if not r.get("cambiaria_la_decision"):
            continue
        for mo in r.get("shadow", {}).get("motivos", []):
            c = mo.get("categoria", "OTRO")
            cat[c] = cat.get(c, 0) + 1
    return {"n": len(records), "cambiaria_%": round(100 * cambios / n, 1),
            "bloqueadas_%": round(100 * bloqueadas / n, 1),
            "con_datos_faltantes_%": round(100 * por_datos / n, 1),
            "motivos_por_categoria": cat,
            "fecha": date.today().isoformat()}
