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

import math
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


def es_evento_fuerte(f) -> bool:
    """¿Es un EVENTO FUERTE que fuerza reconsiderar la empresa aunque NO sea posición (r4 #1a)? Red flag +
    dilución (S-1/S-3/424B5) + activismo (SC 13D) + 8-K material. Un 10-Q/10-K de RUTINA NO es fuerte por sí
    solo (suma a hechos_nuevos → materialidad del Triage); solo fuerza si el nombre es posición en cartera."""
    tipo = getattr(f, "tipo", "")
    if es_red_flag(f) or tipo in FORMS_DILUCION or tipo in FORMS_ACTIVISMO:
        return True
    return tipo == "8-K" and bool(_items(f) & ITEMS_8K_MATERIALES)


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


# Umbrales de precio (doc 64 §A1): movimiento residual normalizado |z|, más bajo para posiciones.
UMBRAL_Z_NO_POSICION = 2.5
UMBRAL_Z_POSICION = 2.0
RESPALDO_ABS_PCT = 25.0            # respaldo absoluto: ±25% desde el dossier siempre es señal


def _retornos(serie: list[float]) -> list[float]:
    return [serie[i] / serie[i - 1] - 1.0 for i in range(1, len(serie)) if serie[i - 1]]


def precio_z(precio_hist: list[float] | None, *, mercado_hist: list[float] | None = None,
             n_desde_dossier: int | None = None) -> float | None:
    """Movimiento residual normalizado desde el inicio de la serie (doc 64 §A1): cuánto se movió el nombre,
    en desviaciones estándar de su propia volatilidad, descontando el mercado si se pasa `mercado_hist`.
    `z = (r_nombre − β·r_mercado) / (σ_resid · √n)`. Sin `mercado_hist` → β=0 (z crudo vol-normalizado).
    Devuelve None si no hay serie suficiente."""
    if not precio_hist or len(precio_hist) < 20 or not precio_hist[0]:
        return None
    r_tot = precio_hist[-1] / precio_hist[0] - 1.0
    rn = _retornos(precio_hist)
    beta, resid = 0.0, rn
    if mercado_hist and len(mercado_hist) == len(precio_hist):
        rm = _retornos(mercado_hist)
        var_m = sum(x * x for x in rm) / len(rm) if rm else 0.0
        if var_m > 0:
            beta = (sum(a * b for a, b in zip(rn, rm)) / len(rn)) / var_m
            resid = [a - beta * b for a, b in zip(rn, rm)]
    r_mercado_tot = (mercado_hist[-1] / mercado_hist[0] - 1.0) if (mercado_hist and mercado_hist[0]) else 0.0
    mu = sum(resid) / len(resid) if resid else 0.0
    sigma = math.sqrt(sum((x - mu) ** 2 for x in resid) / len(resid)) if resid else 0.0
    n = n_desde_dossier or len(rn)
    if sigma <= 0 or n <= 0:
        return None
    return round((r_tot - beta * r_mercado_tot) / (sigma * math.sqrt(n)), 2)


def precio_dispara(z: float | None, pct_abs: float | None, *, es_posicion: bool) -> bool:
    """¿El movimiento de precio amerita ser candidato? |z| sobre el umbral (más bajo para posiciones) O el
    respaldo absoluto (±25%)."""
    umbral = UMBRAL_Z_POSICION if es_posicion else UMBRAL_Z_NO_POSICION
    if z is not None and abs(z) >= umbral:
        return True
    return pct_abs is not None and pct_abs >= RESPALDO_ABS_PCT


# --------------------------------------------------------------------------- cobertura / bootstrap (doc 64 §A3)

def gate_invertibilidad(ctx, ips_cfg: dict) -> bool:
    """¿El nombre es INVERTIBLE bajo el IPS (market cap + ADV en rango)? No gastar $0.68 en algo que no se
    puede comprar al tamaño de posición del operador (doc 64 §A3). Sin datos → se asume invertible (el
    screening barato ya lo trajo; el gate duro real lo aplica el orquestador de decisión)."""
    mc = getattr(ctx, "market_cap", None)
    adv = getattr(ctx, "adv_usd", None)
    if mc is not None and not (float(ips_cfg.get("market_cap_min_usd", 0)) <= mc
                               <= float(ips_cfg.get("market_cap_max_usd", 1e18))):
        return False
    if adv is not None and adv < float(ips_cfg.get("adv_min_usd", 0)):
        return False
    return True


def cupo_bootstrap(semana_n: int, *, semanas_aceleradas: int = 10, cupo_inicial: int = 6,
                   cupo_regimen: int = 2) -> int:
    """Nombres nuevos a promover esta semana (doc 64 §A3): BOOTSTRAP acelerado (6/sem) las primeras ~10
    semanas para cubrir el universo, luego régimen (2/sem). `semana_n` arranca en 1."""
    return cupo_inicial if semana_n <= semanas_aceleradas else cupo_regimen


def ordenar_cobertura(nuevos: list, *, ips_cfg: dict, ctx_fn, dias_a_evento_fn=None,
                      slot_azar_cada: int = 5, rng=None) -> list:
    """Ordena los candidatos NUEVOS (nunca analizados) para la cobertura (doc 64 §A3):
    (1) gate de invertibilidad · (2) excluir los que reportan ≤10d (conviene esperar el balance) ·
    (3) orden por `prioridad_cuello` desc, desempate 10-Q reciente (implícito en el orden de entrada) ·
    (4) reservar ~1 de cada `slot_azar_cada` a un nombre AL AZAR entre los invertibles (chequeo del mapa).
    `nuevos` = tuplas (ticker, SenalesTriage, resumen). `ctx_fn(ticker)->ContextoTicker`."""
    import random
    rng = rng or random.Random(0)
    invertibles = [c for c in nuevos if gate_invertibilidad(ctx_fn(c[0]), ips_cfg)]
    elegibles = [c for c in invertibles
                 if not (dias_a_evento_fn and (dias_a_evento_fn(c[0]) or 99) <= 10)]
    por_cuello = sorted(elegibles, key=lambda c: getattr(c[1], "prioridad_cuello", 0), reverse=True)
    # Insertar un slot al azar cada `slot_azar_cada` posiciones (entre los invertibles no ya elegidos arriba).
    if por_cuello and len(por_cuello) > slot_azar_cada:
        resto = por_cuello[slot_azar_cada:]
        azar = rng.choice(resto)
        por_cuello = por_cuello[:slot_azar_cada] + [azar] + [c for c in resto if c is not azar]
    return por_cuello


# --------------------------------------------------------------------------- selección de deep (una sola fuente)

def _seleccionar_carriles(candidatos, *, invertible_fn=None, gigante_barato_fn=None,
                          cupo_gigantes: int = 0, cupo_oportunidad: int | None = None) -> dict:
    """Selección LIMPIA del doc 80 §D (r9): tenencias (siempre) + oportunidad (no-tenencias, capeado). Los
    eventos de no-tenencias NO fuerzan deep (solo mueven el score, computado aguas arriba)."""
    posiciones, oportunidad, espera, no_invertible, gig_rank = [], [], [], [], []
    for tk, s, _res in candidatos:
        if not s.es_posicion and invertible_fn is not None and not invertible_fn(tk):
            if gigante_barato_fn is not None and gigante_barato_fn(tk):
                gig_rank.append((s.precio_vs_tesis_pct if s.precio_vs_tesis_pct is not None else 0.0, tk))
            else:
                no_invertible.append((tk, "fuera de rango IPS (market cap)"))
            continue
        if s.es_posicion:
            posiciones.append((tk, "posición (evento pre/post → refresh)"))
        elif getattr(s, "forzado_oportunidad", False):
            oportunidad.append((tk, "oportunidad (top score / banca en zona)"))
        else:
            espera.append((tk, "no-tenencia sin oportunidad (el evento solo mueve el score)"))
    if cupo_oportunidad is not None and len(oportunidad) > cupo_oportunidad:
        espera += [(tk, "oportunidad sobre el cupo") for tk, _m in oportunidad[cupo_oportunidad:]]
        oportunidad = oportunidad[:cupo_oportunidad]
    gig_rank.sort(key=lambda x: x[0])
    gigantes_watch = [(tk, "gigante caído (deep → ¿barato? → ALERTA)") for _z, tk in gig_rank[:cupo_gigantes]]
    no_invertible += [(tk, "gigante caído (sobre el cupo)") for _z, tk in gig_rank[cupo_gigantes:]]
    deep = {tk for tk, _ in posiciones + oportunidad + gigantes_watch}
    return {"forzados": posiciones, "oportunidad": oportunidad, "precio": [], "pre_earnings": [],
            "promovidos": [], "gigantes_watch": gigantes_watch, "espera": espera,
            "no_invertible": no_invertible, "deep": deep}


def seleccionar_para_deep(candidatos, *, cupo: int, pre_earnings_top_n: int = 3,
                          dias_earnings: int = 10, invertible_fn=None, cupo_forzados=None,
                          gigante_barato_fn=None, cupo_gigantes: int = 0,
                          eventos_solo_posiciones: bool = False, cupo_oportunidad: int | None = None) -> dict:
    """r9 §D (doc 80): con `eventos_solo_posiciones=True` el deep queda LIMPIO —
    - **TENENCIAS** → deep siempre (eventos: pre Y post earnings, red flags; ya tienen ficha → el runner las
      rutea a REFRESH barato, no comité completo).
    - **NO-TENENCIAS** → SOLO por OPORTUNIDAD (`forzado_oportunidad`, capeado a `cupo_oportunidad`); los eventos
      de una no-tenencia **mueven su score aguas arriba, NO fuerzan deep**. Sin carril de evento/precio/
      pre-earnings para no-posiciones.
    (default False = comportamiento viejo, para compat de tests.) El filtro de admisibilidad + gigantes siguen."""
    if eventos_solo_posiciones:
        return _seleccionar_carriles(candidatos, invertible_fn=invertible_fn, gigante_barato_fn=gigante_barato_fn,
                                     cupo_gigantes=cupo_gigantes, cupo_oportunidad=cupo_oportunidad)
    """ÚNICA fuente de verdad de 'qué va a análisis profundo' — la usan el dry-run Y el runner real (así lo
    que ves en --dry-run es lo que corre). Opera sobre las `SenalesTriage` de cada candidato
    `(ticker, señal, resumen)`. Reglas (doc 64 + doc 76):
    - posición en cartera → deep SIEMPRE (monitoreo; NUNCA se la filtra por tamaño ni se la capea).
    - `invertible_fn(ticker)->bool` (doc 76): para NO-posiciones, excluye las que el IPS no puede comprar
      (market cap/ADV fuera de rango) ANTES del deep → bucket `no_invertible`. None = no filtra (tests).
    - evento fuerte → carril forzado, RANKEADO por prioridad de cuello y CAPEADO a `cupo_forzados` (doc 76:
      el carril por evento no es ilimitado; el overflow se arrastra y se ve). None = sin tope (compat).
    - precio fuerte (|z| ≥ umbral) → deep.
    - EARNINGS PRÓXIMO (≤ `dias_earnings`, no consumado): deep SOLO para los `pre_earnings_top_n` MEJORES.
    - nunca analizado sin trigger → CUPO (los `cupo` mejores por prioridad de cuello).
    - resto → espera.
    Devuelve dict con listas de (ticker, motivo) y el set `deep` de tickers a analizar."""
    forzados, precio_f, pre_earn, nuevos, espera, no_invertible = [], [], [], [], [], []
    earnings_pendientes = []   # earnings próximo, no forzado por otra vía → candidatos a pre-earnings top
    forz_rank = []             # (prioridad_cuello, ticker) de no-posiciones con evento, para rankear y capear
    gig_rank = []              # (z_precio, ticker) de gigantes que cayeron fuerte → candidatos a alerta-si-barato
    for tk, s, _res in candidatos:
        # filtro de admisibilidad del IPS: SOLO a no-posiciones (una posición se monitorea a cualquier tamaño).
        if not s.es_posicion and invertible_fn is not None and not invertible_fn(tk):
            # gigante que cayó fuerte → carril chico de "¿barato?" (el puente confirma → ALERTA, no compra; doc 76).
            if gigante_barato_fn is not None and gigante_barato_fn(tk):
                gig_rank.append((s.precio_vs_tesis_pct if s.precio_vs_tesis_pct is not None else 0.0, tk))
            else:
                no_invertible.append((tk, "fuera de rango IPS (market cap)"))
            continue
        if s.es_posicion:
            forzados.append((tk, "posición"))
        elif s.tiene_evento_fuerte:
            forz_rank.append((s.prioridad_cuello, tk))
        elif precio_dispara(s.precio_vs_tesis_pct, None, es_posicion=False):
            precio_f.append((tk, "precio"))
        elif s.dias_a_evento is not None and s.dias_a_evento <= dias_earnings:
            earnings_pendientes.append((tk, s.prioridad_cuello))
        elif s.dias_desde_dossier is None:
            nuevos.append((tk, s.prioridad_cuello))
        else:
            espera.append((tk, "sin trigger"))
    # carril forzado por evento (no-posiciones): rankea por prioridad de cuello y capea; overflow → espera (visible).
    forz_rank.sort(key=lambda x: -x[0])
    tope_f = len(forz_rank) if cupo_forzados is None else max(0, cupo_forzados)
    forzados += [(tk, "evento fuerte") for _p, tk in forz_rank[:tope_f]]
    espera += [(tk, "evento fuerte (sobre el tope, arrastrado)") for _p, tk in forz_rank[tope_f:]]
    # carril gigantes (alerta-si-barato): los que más cayeron primero, capeado a cupo_gigantes; el resto → no_inv.
    gig_rank.sort(key=lambda x: x[0])    # z más negativo (más caído) primero
    gigantes_watch = [(tk, "gigante caído (deep → ¿barato? → ALERTA)") for _z, tk in gig_rank[:cupo_gigantes]]
    no_invertible += [(tk, "gigante caído (sobre el cupo de gigantes)") for _z, tk in gig_rank[cupo_gigantes:]]
    # earnings próximo: los top-N por prioridad de cuello van pre-earnings; el resto espera el dato.
    earnings_pendientes.sort(key=lambda x: -x[1])
    for i, (tk, _p) in enumerate(earnings_pendientes):
        (pre_earn if i < pre_earnings_top_n else espera).append(
            (tk, "pre-earnings (top)" if i < pre_earnings_top_n else "espera post-earnings"))
    nuevos.sort(key=lambda x: -x[1])
    promovidos = [(tk, "cupo") for tk, _ in nuevos[:cupo]]
    espera += [(tk, "nunca analizado en espera") for tk, _ in nuevos[cupo:]]
    deep = {tk for tk, _ in forzados + precio_f + pre_earn + promovidos + gigantes_watch}
    return {"forzados": forzados, "precio": precio_f, "pre_earnings": pre_earn,
            "promovidos": promovidos, "gigantes_watch": gigantes_watch, "espera": espera,
            "no_invertible": no_invertible, "deep": deep}


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


def clasificar_candidato(*, es_posicion: bool, eventos_materiales: list, z_precio: float | None = None,
                         precio_vs_pct: float | None = None, dias_a_evento: int | None = None,
                         diferir_dias: int = 10) -> tuple[str, int]:
    """Clasifica el candidato en su nivel de prioridad (doc 64 §A1). `eventos_materiales` ya filtrado por el
    cursor. Devuelve (motivo, prioridad). `sin_trigger`/`diferido` = no amerita deep ahora.

    Earnings DIFERIDO (doc 64): una NO-posición con earnings dentro de `diferir_dias` no dispara deep — se
    espera al evento consumado (el 10-Q/8-K-2.02 posterior) para no pagar un análisis que el balance deja
    obsoleto. El earnings YA publicado (en `eventos_materiales`) sí dispara."""
    red = any(es_red_flag(f) for f in eventos_materiales)
    dil = any(getattr(f, "tipo", "") in FORMS_DILUCION for f in eventos_materiales)
    earn = any(getattr(f, "tipo", "") == "8-K" and "2.02" in _items(f) for f in eventos_materiales) \
        or any(getattr(f, "tipo", "") in ("10-Q", "10-K") for f in eventos_materiales)
    precio_fuerte = precio_dispara(z_precio, precio_vs_pct, es_posicion=es_posicion)

    if es_posicion and eventos_materiales:
        return "posicion_con_evento", PRIORIDAD["posicion_con_evento"]
    if red:
        return "red_flag", PRIORIDAD["red_flag"]
    if dil:
        return "dilucion", PRIORIDAD["dilucion"]
    if earn:
        return "earnings_consumado", PRIORIDAD["earnings_consumado"]
    # earnings PRÓXIMO (no consumado) en una no-posición → diferir (no gastar un deep que el balance invalida)
    if not es_posicion and dias_a_evento is not None and dias_a_evento <= diferir_dias:
        return "diferido", PRIORIDAD["sin_trigger"]
    if precio_fuerte:
        return "precio", PRIORIDAD["precio"]
    return "sin_trigger", PRIORIDAD["sin_trigger"]


# --------------------------------------------------------------------------- señal de valor (r7 §3, doc 78)
# La valuación PRIORIZA: lo barato respecto de lo contratado+facturado, DENTRO de su cuello, sube en la fila.
# Determinista, API-free: consume las métricas de la lente (fuente_valuacion) ya calculadas por nombre.

def ratio_valor(metricas: dict) -> float | None:
    """EV / (valor contratado ajustado + revenue). MENOR = más barato. `metricas` = {metric: value|None} del
    pack (enterprise_value, valor_contratado_ajustado, revenue). None si no hay EV o el denominador es ≤ 0
    (pre-revenue SIN backlog contratado = opción pura → NO se le exige valuación, r7 §6)."""
    ev = metricas.get("enterprise_value")
    if ev is None:
        return None
    denom = (metricas.get("valor_contratado_ajustado") or 0.0) + (metricas.get("revenue") or 0.0)
    if denom <= 0:
        return None
    return round(ev / denom, 4)


def percentiles_valor_por_cuello(ratios: dict[str, float | None],
                                 cuellos: dict[str, str | None]) -> dict[str, float | None]:
    """Percentil de valor de cada nombre DENTRO de su cuello: 1.0 = el más barato del cuello, 0.0 = el más
    caro. None si el nombre no tiene ratio o su cuello tiene <2 nombres comparables (no hay con qué rankear)."""
    from collections import defaultdict
    grupos: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for tk, r in ratios.items():
        c = cuellos.get(tk)
        if r is not None and c:
            grupos[c].append((tk, r))
    out: dict[str, float | None] = {tk: None for tk in ratios}
    for items in grupos.values():
        if len(items) < 2:
            continue
        ordenado = sorted(items, key=lambda x: x[1])      # ascendente: más barato primero
        n = len(ordenado)
        for i, (tk, _r) in enumerate(ordenado):
            out[tk] = round(1 - i / (n - 1), 3)            # i=0 (más barato) → 1.0
    return out


def top_por_valor(ratios: dict[str, float | None], cuellos: dict[str, str | None],
                  metricas_por_tk: dict[str, dict], n: int = 15) -> list[dict]:
    """Top-N más baratos por valor dentro de su cuello (para el reporte del dry-run, r7 §8). Ordena por
    percentil desc (más barato primero), con el ratio y las métricas crudas para leer el porqué."""
    pct = percentiles_valor_por_cuello(ratios, cuellos)
    filas = [{"ticker": tk, "cuello": cuellos.get(tk), "percentil_valor": pct.get(tk),
              "ratio_valor": ratios.get(tk), "ev": metricas_por_tk.get(tk, {}).get("enterprise_value"),
              "revenue": metricas_por_tk.get(tk, {}).get("revenue"),
              "valor_contratado": metricas_por_tk.get(tk, {}).get("valor_contratado_ajustado")}
             for tk in ratios if pct.get(tk) is not None]
    filas.sort(key=lambda f: -(f["percentil_valor"] or 0.0))
    return filas[:n]
