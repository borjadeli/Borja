"""Embudo de priorización (v2, doc 64 §A1) — qué filing es MATERIAL y cuándo re-analizar.

El embudo gasta por VALOR INFORMATIVO INCREMENTAL, no por existencia de un evento (doc 64). Acá vive la
materialidad DETERMINISTA de un filing (whitelist por tipo + ítem de 8-K) y la detección de "evento material
nuevo desde el último dossier", que es la que:
  (1) saltea la reutilización del cache (un dossier vigente NO puede ocultar un 8-K material — garantía al
      operador: el PM nunca decide sobre un dossier obsoleto por un evento no incorporado), y
  (2) alimenta las SenalesTriage (`tiene_evento_fuerte`, prioridad).

`señal_prioridad` ordena los candidatos (no es un OR booleano): posición-con-evento > red flag > dilución >
earnings-consumado > precio > cobertura (doc 64).
"""
from __future__ import annotations

from datetime import date, datetime

# --- Whitelist de materialidad (doc 64 §A1; converge IA1+IA2) ---
# 8-K: SOLO estos ítems disparan (el resto, p.ej. 9.01 exhibits, es accesorio y NO dispara).
ITEMS_8K_MATERIALES = {
    "1.01",  # entrada en acuerdo material     "1.02",  # terminación de acuerdo material
    "2.01",  # adquisición/disposición         "2.02",  # resultados (earnings)
    "2.05",  # costos por salida/disposición   "2.06",  # deterioro material
    "3.01",  # delisting / incumplimiento      "4.01",  # cambio de auditor
    "4.02",  # no-confiabilidad de estados     "5.02",  # cambios en directorio/management
}
# Red flags (gobernanza/contabilidad): prioridad máxima.
ITEMS_8K_REDFLAG = {"4.02", "4.01", "3.01"}
# Formularios de dilución (crítico en small caps).
FORMS_DILUCION = {"S-1", "S-3", "424B5"}
# Reportes periódicos + activismo + alarmas.
FORMS_PERIODICOS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "6-K"}
FORMS_ACTIVISMO = {"SC 13D"}
FORMS_ALARMA = {"NT 10-K", "NT 10-Q"}   # retraso de reporte = red flag fuerte

_FORMS_MATERIALES = FORMS_PERIODICOS | FORMS_DILUCION | FORMS_ACTIVISMO | FORMS_ALARMA


def _items(f) -> set[str]:
    return {x.strip() for x in (getattr(f, "items", "") or "").split(",") if x.strip()}


def es_material(f) -> bool:
    """¿Este filing es material (dispara reconsiderar la empresa)? Whitelist por tipo + ítem de 8-K.
    Form 4 y demás ruido NO son materiales (el filtrado de Form 4 compra-insider vive en el caller)."""
    tipo = getattr(f, "tipo", "")
    if tipo in _FORMS_MATERIALES:
        return True
    if tipo == "8-K":
        return bool(_items(f) & ITEMS_8K_MATERIALES)
    return False


def es_red_flag(f) -> bool:
    """Red flag de gobernanza/contabilidad (prioridad máxima): 8-K 4.02/4.01/3.01 o NT 10-K/Q."""
    if getattr(f, "tipo", "") in FORMS_ALARMA:
        return True
    return getattr(f, "tipo", "") == "8-K" and bool(_items(f) & ITEMS_8K_REDFLAG)


def _fecha(f) -> date | None:
    d = getattr(f, "fecha", None)
    return d.date() if isinstance(d, datetime) else (d if isinstance(d, date) else None)


def eventos_materiales_desde(filings: list, desde: date | None) -> list:
    """Filings MATERIALES con fecha > `desde` (o todos los materiales si `desde` es None → caller decide el
    cursor). Es lo que invalida la reutilización de un dossier y arma la señal de evento."""
    out = []
    for f in (filings or []):
        if not es_material(f):
            continue
        fd = _fecha(f)
        if desde is None or (fd and fd > desde):
            out.append(f)
    return out


# Orden de prioridad del candidato (doc 64 §A1; menor = más prioritario). No es un OR: es una cola ordenada.
PRIORIDAD = {
    "posicion_con_evento": 0,
    "red_flag": 1,
    "dilucion": 2,
    "earnings_consumado": 3,
    "precio": 4,
    "cobertura": 5,
    "sin_trigger": 9,
}


def clasificar_candidato(*, es_posicion: bool, eventos_materiales: list, z_precio: float | None,
                         umbral_z: float) -> tuple[str, int]:
    """Clasifica el candidato en su nivel de prioridad (doc 64). `eventos_materiales` ya filtrado por cursor.
    Devuelve (motivo, prioridad). `sin_trigger` = no amerita deep (se reutiliza o se saltea)."""
    red = any(es_red_flag(f) for f in eventos_materiales)
    dil = any(getattr(f, "tipo", "") in FORMS_DILUCION for f in eventos_materiales)
    earn = any(getattr(f, "tipo", "") == "8-K" and "2.02" in _items(f) for f in eventos_materiales) \
        or any(getattr(f, "tipo", "") in ("10-Q", "10-K") for f in eventos_materiales)
    precio_fuerte = z_precio is not None and abs(z_precio) >= umbral_z

    if es_posicion and (red or dil or earn or eventos_materiales):
        return "posicion_con_evento", PRIORIDAD["posicion_con_evento"]
    if red:
        return "red_flag", PRIORIDAD["red_flag"]
    if dil:
        return "dilucion", PRIORIDAD["dilucion"]
    if earn:
        return "earnings_consumado", PRIORIDAD["earnings_consumado"]
    if precio_fuerte:
        return "precio", PRIORIDAD["precio"]
    return "sin_trigger", PRIORIDAD["sin_trigger"]
