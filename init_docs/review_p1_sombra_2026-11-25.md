# Review: implementamos su diseño. ¿Qué nos falta o qué está mal?

Trabajaron con nosotros el diagnóstico de la corrida de BORJA del 25-nov y el diseño de la capa de calidad
económica. Implementamos todo. Antes de darle autoridad, queremos su devolución sobre lo construido.

## Qué quedó implementado (todo commiteado, 1034 tests verdes)

**P0 — autoridad (los bugs que encontraron):**
- Verificación = autoridad determinista en el gate (FAIL bloquea; el PM no lo anula).
- Falsador ESTRUCTURADO del dossier = fuente de verdad (no el texto libre del PM; se arregló la inversión de signo).
- 8-K Item 5.02 ya no afirma "salida de CEO/CFO" por el código de ítem.
- Invariante post-trade (señala stubs sub-piso en el estado final).
- Reconciliación interna del market cap (caso GLXY: mc de todas las clases vs shares de clase A) → BLOQUEA valuación.

**P2 — medición del edge:** contrafactual de ROTACIÓN (A vendida vs B comprada a 30/90/180/365d).

**P1 — calidad económica, EN MODO SOMBRA (computa, NO aplica — como pidieron):** 6 módulos deterministas, test-driven:
1. `tiers.py` — 4 tiers (OPTIONALITY 1.5-2.5 · CORE 5-10 · HIGH_CONVICTION >10-15 · EXCEPTIONAL >15-20; sin 3-5).
2. `arquetipo.py` — clasificador (precedencia infra→pre_revenue→ciclica→compounder; datos insuf.→UNCLASSIFIED).
3. `banda.py` — banda por arquetipo (COMPRA_FUERTE/COMPRA/MANTENER/RECORTE), recalculada cada ciclo, nunca persistida.
4. `permiso_ejecucion.py` — execution_permission (EJECUTAR/DIFERIR/BLOQUEAR), lo calcula el código.
5. `caps_posicion.py` — cap = min(tier, arquetipo, banda, evidencia) + registra qué cap ligó.
6. `comparacion_rotacion.py` — 3 condiciones no compensatorias (evidencia+margen+riesgo); conecta al contrafactual.

**Decisiones resueltas entre sus dos diseños** (sin 3ª IA): quitamos la convicción propia del PM (de IA2) · topes por
arquetipo (IA2: compounder 15·cíclica 10·infra 10·pre-rev 0) · stub = sacar la pieza (IA2) · guardarraíl de curva
forward en cíclicas (IA2) · falsador DURO sobre la métrica del arquetipo (IA2) · opcionalidad **8% agregado** (decisión
del operador, punto medio entre los 6% de uno y 15% del otro) · grilla-vs-rango continuo DIFERIDO (el shadow decide) ·
execution_permission de 3 estados (IA2). Método: SOMBRA primero, después autoridad, después freeze 90 días.

## El test clave: ¿qué habría decidido P1 sobre LA corrida que ustedes criticaron?

Corrimos el kit en sombra sobre los 7 nombres del 25-nov (NO aplica, solo computa). Resultado:

```
EXE   arquetipo=ciclica · banda=RECORTE · cap=0.0% · PERMISO=BLOQUEAR (aumento)
VST   arquetipo=ciclica · verif FAIL · cap=10% · PERMISO=BLOQUEAR (aumento)
IESC  arquetipo=ciclica · venta discrecional con dossier viejo · PERMISO=DIFERIR
CIFR  arquetipo=infra · banda=RECORTE · salida · PERMISO=EJECUTAR
GLXY  arquetipo=infra · cobertura IG~0 · banda=RECORTE · cap=0.0%
WOLF  arquetipo=pre_revenue · cap=0.0% en núcleo (solo opcionalidad)
EME   sin dossier · arquetipo=UNCLASSIFIED · PERMISO=BLOQUEAR (apertura)
```

Coincide con el trato que cada uno de ustedes esperaba: EXE/VST/EME se bloquean, IESC se difiere (no se ejecuta a
ciegas con datos viejos), CIFR sale como independiente, GLXY/WOLF no pueden ser núcleo. La única dependencia del harness
real: extraer del dossier los RANGOS de banda (valor mitad-de-ciclo, cobertura IG) — donde faltan, el kit devuelve
None honestamente en vez de inventar.

## Lo que les pedimos revisar

1. **¿La semántica de los módulos es fiel a su diseño?** Especialmente: la precedencia de arquetipos, la función de
   banda por tipo, el min() no-compensatorio de caps, y los 3 estados de permiso (¿DIFERIR está bien acotado a ventas
   discrecionales?).
2. **¿Los veredictos sobre los 7 nombres son correctos** dado lo que el sistema sabía ese día? ¿Alguno les parece mal?
3. **El harness de sombra** (lo que falta): va a EXTRAER del dossier los insumos (señales de arquetipo + rangos de
   banda) y loguear "qué habría cambiado" por decisión, sin aplicar. ¿Qué invariantes/trampas vigilarían en esa
   extracción? (ej. un rango de banda mal extraído da una banda falsa.)
4. **¿Qué de los 18 tests de aceptación que propuso IA1 todavía NO cubrimos** y es importante antes de darle autoridad?
5. **¿Algo del diseño cambiarían a la luz de verlo computado** sobre la corrida real?

Sean concretos y duros. El objetivo es que esto esté sólido ANTES de darle autoridad y entrar al freeze de 90 días.

---

# CÓDIGO COMPLETO (para revisar línea por línea)

Son 6 módulos deterministas nuevos (modo sombra: computan, NO aplican) + la config del IPS + el demo. Abajo el
source íntegro de cada uno.

## backend/agentes/tiers.py
```python
"""P1.3 (doc 91 §7) — IPS por TIERS: 4 categorías ECONÓMICAS que reemplazan al piso rígido de 5%.

IA1 it.2: OPTIONALITY 1-3% · CORE 5-10% · HIGH_CONVICTION >10-15% · EXCEPTIONAL >15-20% · EXIT 0%. SIN tier 3-5%
(la opcionalidad es una categoría económica distinta, no un CORE chico → evita que toda posición chica sea una
excepción al piso). El tier NO da derecho a usar todo su rango: aguas arriba siempre gana el cap más restrictivo
(liquidez/supervivencia/sector/cuello). Determinista, $0. Los números viven en `ips.yaml` (`tiers:`).
"""
from __future__ import annotations

TIERS_ORDEN = ("OPTIONALITY", "CORE", "HIGH_CONVICTION", "EXCEPTIONAL")
_EPS = 1e-9


def _en_banda(weight: float, banda: dict) -> bool:
    """¿`weight` cae en la banda? Soporta `min` (inclusivo), `min_exclusive` (exclusivo) y `max` (inclusivo)."""
    hi = banda.get("max")
    if hi is None or weight > hi + _EPS:
        return False
    if banda.get("min") is not None:
        return weight >= banda["min"] - _EPS
    if banda.get("min_exclusive") is not None:
        return weight > banda["min_exclusive"] + _EPS
    return False


def valid_target_weight(weight: float, tier: str, tiers_cfg: dict) -> bool:
    """¿`weight` es un peso objetivo VÁLIDO para el `tier` declarado? (regla exacta de IA1 §1.2). EXIT → 0."""
    if tier == "EXIT":
        return abs(weight) < _EPS
    banda = (tiers_cfg or {}).get(tier)
    return _en_banda(weight, banda) if banda else False


def tier_de_peso(weight: float, tiers_cfg: dict) -> str | None:
    """El tier al que pertenece `weight`, o None si cae en una zona INVÁLIDA (p.ej. 4% o 3.5% — entre tiers)."""
    if abs(weight) < _EPS:
        return "EXIT"
    for t in TIERS_ORDEN:
        if valid_target_weight(weight, t, tiers_cfg):
            return t
    return None


def peso_valido(weight: float, tiers_cfg: dict) -> bool:
    """¿`weight` cae en ALGÚN tier válido (o es 0)? Lo que reemplaza al chequeo del piso rígido."""
    return tier_de_peso(weight, tiers_cfg) is not None
```

## backend/agentes/arquetipo.py
```python
"""P1 (doc 91 §7, blueprint IA2) — clasificador de ARQUETIPO económico. MODO SOMBRA: computa el arquetipo
PROPUESTO desde señales deterministas del pack; NO aplica nada. El Analista confirma o hace override con fuente.

Precedencia: infra → pre_revenue → ciclica → compounder (la PRIMERA señal true gana; por eso CIFR cae en infra
aunque tenga OCF<0). Datos insuficientes para toda señal → None (UNCLASSIFIED): el Analista lo asigna, y a núcleo
solo si la métrica obligatoria tiene fuente primaria. Determinista, $0.
"""
from __future__ import annotations

ARQUETIPOS = ("infra", "pre_revenue", "ciclica", "compounder")

# sectores/tags estructuralmente cíclicos (IA2 §2.ciclica)
SECTORES_CICLICOS = {"e&p", "mineria", "minería", "ipp", "quimica", "química", "shipping", "semis_equipos",
                     "oil_gas", "gas", "uranio", "cobre", "commodities"}


def _frac(a, b):
    """a/b seguro: None si falta algún dato o b no es positivo."""
    if a is None or b is None or b <= 0:
        return None
    return a / b


def _señal_infra(d: dict) -> bool:
    # contratado_firme = valor TOTAL contratado firme (RPO XBRL + backlog de leasing + 8-K 1.01 con monto), NO anual.
    cob = _frac(d.get("contratado_firme"), d.get("ev"))
    capint = _frac(d.get("capex"), d.get("revenue"))
    return cob is not None and capint is not None and cob >= 0.5 and capint >= 0.5


def _señal_pre_revenue(d: dict) -> bool:
    rev, gm, ocf, runway = d.get("revenue_ltm"), d.get("margen_bruto_ltm"), d.get("ocf_ltm"), d.get("runway_meses")
    if rev is not None and rev < 50e6:
        return True
    if gm is not None and gm <= 0:
        return True
    if ocf is not None and ocf < 0 and runway is not None and runway < 36:
        return True
    return False


def _señal_ciclica(d: dict) -> bool:
    sector = (d.get("sector") or "").strip().lower()
    if sector in SECTORES_CICLICOS:
        return True
    cv = d.get("cv_margen_op_10a")
    if cv is not None and cv > 0.5:
        return True
    m_ltm, m_med = d.get("margen_op_ltm"), d.get("margen_op_mediana_10a")
    if m_ltm is not None and m_med is not None and m_med > 0 and m_ltm > 1.5 * m_med:
        return True
    return False


def _señal_compounder(d: dict) -> bool:
    fcf_a, roic_a = d.get("fcf_pos_anios_de5"), d.get("roic_gt15_anios_de5")
    return fcf_a is not None and roic_a is not None and fcf_a >= 4 and roic_a >= 4


def clasificar_arquetipo(datos: dict) -> str | None:
    """Arquetipo PROPUESTO (precedencia infra→pre_revenue→ciclica→compounder) o None si ninguna señal da true."""
    if _señal_infra(datos):
        return "infra"
    if _señal_pre_revenue(datos):
        return "pre_revenue"
    if _señal_ciclica(datos):
        return "ciclica"
    if _señal_compounder(datos):
        return "compounder"
    return None
```

## backend/agentes/banda.py
```python
"""P1 (doc 91 §7, blueprint IA2 §2) — BANDA por arquetipo. MODO SOMBRA: computa COMPRA_FUERTE/COMPRA/MANTENER/
RECORTE desde la métrica del arquetipo (rango del dossier) + el precio del día; NO aplica nada. Se recalcula CADA
ciclo y NUNCA se persiste → mata de raíz las "zonas viejas" (el bug que hizo que el PM operara sobre fichas de
días previos). Usa SIEMPRE el extremo DESFAVORABLE del rango del analista. Bordes versionados (cambiarlos = cambio
de sistema). Determinista, $0.

- infra        → cobertura del EV con contratos IG (extremo BAJO del rango).
- ciclica      → precio vs valor de mitad de ciclo / a la curva [bajo, alto].
- compounder   → g exigido por el precio vs g sostenible [bajo, alto].
- pre_revenue  → NO tiene banda de núcleo; elegible a opcionalidad si p_implícita.alto < p_razonada.bajo.
"""
from __future__ import annotations

BANDAS = ("COMPRA_FUERTE", "COMPRA", "MANTENER", "RECORTE")
_G_HOLGURA = 0.03   # 3pp: margen extra de COMPRA_FUERTE del compounder (versionado)


def banda_infra(cobertura_ig_bajo: float | None) -> str | None:
    c = cobertura_ig_bajo                       # extremo BAJO (desfavorable) del rango de cobertura
    if c is None:
        return None
    if c >= 1.0:
        return "COMPRA_FUERTE"
    if c >= 0.8:
        return "COMPRA"
    if c >= 0.5:
        return "MANTENER"
    return "RECORTE"


def banda_ciclica(precio: float | None, valor_bajo: float | None, valor_alto: float | None) -> str | None:
    if precio is None or valor_bajo is None or valor_alto is None:
        return None
    medio = (valor_bajo + valor_alto) / 2.0
    if precio < valor_bajo:
        return "COMPRA_FUERTE"
    if precio <= medio:
        return "COMPRA"
    if precio <= valor_alto:
        return "MANTENER"
    return "RECORTE"                            # precio por ENCIMA del rango de mitad de ciclo (caso EXE a la curva)


def banda_compounder(g_exigido: float | None, g_sost_bajo: float | None, g_sost_alto: float | None) -> str | None:
    if g_exigido is None or g_sost_bajo is None or g_sost_alto is None:
        return None
    if g_exigido < g_sost_bajo - _G_HOLGURA:
        return "COMPRA_FUERTE"
    if g_exigido < g_sost_bajo:
        return "COMPRA"
    if g_exigido <= g_sost_alto:
        return "MANTENER"
    return "RECORTE"                            # el precio exige MÁS crecimiento del que el negocio sostiene


def pre_revenue_elegible_opcionalidad(p_implicita_alto: float | None, p_razonada_bajo: float | None) -> bool:
    """pre_revenue NO va a núcleo; solo a opcionalidad si el precio implica MENOS éxito del razonado (margen)."""
    if p_implicita_alto is None or p_razonada_bajo is None:
        return False
    return p_implicita_alto < p_razonada_bajo


def calcular_banda(arquetipo: str, datos: dict) -> str | None:
    """Dispatcher. `datos` trae los insumos del dossier (rangos) + precio del día. pre_revenue → None (no hay banda
    de núcleo); su elegibilidad a opcionalidad se evalúa con `pre_revenue_elegible_opcionalidad`."""
    if arquetipo == "infra":
        return banda_infra(datos.get("cobertura_ig_bajo"))
    if arquetipo == "ciclica":
        return banda_ciclica(datos.get("precio"), datos.get("valor_mitad_ciclo_bajo"), datos.get("valor_mitad_ciclo_alto"))
    if arquetipo == "compounder":
        return banda_compounder(datos.get("g_exigido"), datos.get("g_sost_bajo"), datos.get("g_sost_alto"))
    return None   # pre_revenue o arquetipo desconocido: sin banda de núcleo
```

## backend/agentes/permiso_ejecucion.py
```python
"""P1 (doc 91 §7, blueprint IA2 §3) — execution_permission. MODO SOMBRA: lo CALCULA el código (el PM no lo
escribe) integrando verificación + arquetipo + banda + tier + flags + datos; por ahora se LOGUEA, no se aplica.

Tres estados (IA2):
  EJECUTAR  — salidas mecánicas (falsador DURO / techo / regla IPS); y todo lo que pasa los gates.
  BLOQUEAR  — apertura/aumento/compra-de-par o venta discrecional que choca con un blocker DURO.
  DIFERIR   — SOLO ventas discrecionales: datos viejos/bloqueados, o par de rotación cuya compra quedó bloqueada.

Principio (doc 91): una falla de valuación o un dossier FAIL NO debe impedir VENDER una posición — por eso la
salida mecánica siempre EJECUTA y la discrecional, en el peor caso, DIFIERE (no se traba una salida de riesgo).
Determinista, $0.
"""
from __future__ import annotations

_APERTURAS = ("abrir", "aumentar")
_REDUCCIONES = ("reducir", "salir")
_MECANICOS = ("falsador_duro", "techo_ips", "regla_ips")


def _blockers_apertura(ctx: dict) -> list[str]:
    """Blockers DUROS de una apertura/aumento/compra-de-par (IA2 §3.BLOQUEAR)."""
    m: list[str] = []
    if (ctx.get("verificacion") or "").upper() == "FAIL":
        m.append("verificación FAIL")
    if ctx.get("metrica_obligatoria_null"):
        m.append("métrica obligatoria del arquetipo = null")
    if not ctx.get("falsador_id") or not ctx.get("falsador_sobre_metrica"):
        m.append("falsador ausente o no mide la métrica del arquetipo")
    if not ctx.get("peso_en_grilla", True):
        m.append("peso objetivo fuera de la grilla del tier")
    if ctx.get("peso_sobre_min_caps"):
        m.append("peso objetivo > min(caps): tier/arquetipo/banda/evidencia")
    if not ctx.get("tier_elegible", True):
        m.append("tier no elegible (arquetipo/verificación/banda/flags)")
    if ctx.get("flags_alta_sin_responder"):
        m.append("flags ALTA sin responder")
    if ctx.get("bloqueo_datos"):
        m.append("bloqueo de datos (reconciliación / precio sin 2ª fuente)")
    if ctx.get("opcionalidad_sin_plaza_o_congelada"):
        m.append("opcionalidad sin plaza o manga congelada")
    if ctx.get("crea_stub_o_viola_ips"):
        m.append("el estado resultante crea un stub o viola el IPS por esta decisión")
    return m


def execution_permission(ctx: dict) -> tuple[str, list[str]]:
    """Devuelve (permiso, motivos). `ctx` = contexto de UNA decisión (acción/motivo + evidencia computada)."""
    accion = (ctx.get("accion") or "").lower()
    motivo = (ctx.get("motivo_accion") or "").lower()

    # 1. Salida MECÁNICA → EJECUTAR siempre (no la traba nada; no consume clip).
    if accion in _REDUCCIONES and motivo in _MECANICOS:
        return "EJECUTAR", ["salida mecánica"]

    # 2. Apertura / aumento / compra de un par → BLOQUEAR si choca con un blocker duro.
    if accion in _APERTURAS or ctx.get("es_compra_de_par"):
        bloq = _blockers_apertura(ctx)
        if bloq:
            return "BLOQUEAR", bloq
        return "EJECUTAR", []

    # 3. Venta/reducción DISCRECIONAL → DIFERIR con datos viejos/bloqueados o par trabado; BLOQUEAR sin motivo válido.
    if accion in _REDUCCIONES and motivo == "discrecional":
        difs: list[str] = []
        if not ctx.get("dossier_del_ciclo", True):
            difs.append("dossier no es del ciclo")
        if ctx.get("bloqueo_datos"):
            difs.append("datos bloqueados")
        if ctx.get("par_compra_bloqueada"):
            difs.append("par de rotación cuya compra quedó bloqueada/pendiente")
        if difs:
            return "DIFERIR", difs
        if ctx.get("venta_a_caja_sin_motivo_valido"):
            return "BLOQUEAR", ["venta discrecional a caja sin motivo válido (comparación vs caja)"]
        return "EJECUTAR", []

    # 4. Mantener u otros → EJECUTAR (ausencia de transacción; HOLD no aprueba economía, pero no se traba).
    return "EJECUTAR", []
```

## backend/agentes/caps_posicion.py
```python
"""P1 (doc 91 §7, blueprint IA2 §1) — CAP de posición = min(tier, arquetipo, banda, evidencia). MODO SOMBRA:
computa el techo económico de una posición y REGISTRA qué cap ligó; no aplica nada. "Nada compensa nada" —
el tamaño es el mínimo no-compensatorio de todos los caps, más los caps existentes del IPS (liquidez/
supervivencia/sector/cuello) que aplica el gate. Determinista, $0.
"""
from __future__ import annotations


def cap_posicion(*, tier: str, arquetipo: str | None, banda: str | None, verificacion: str | None,
                 cfg: dict) -> tuple[float, str]:
    """Devuelve (cap, liga). `liga` = qué cap fue el más restrictivo (tier/arquetipo/banda/evidencia). Si no hay
    ningún cap aplicable → (0.0, 'sin_caps'). pre_revenue (cap_arquetipo 0) → 0 en núcleo, como corresponde."""
    caps: dict[str, float] = {}

    tcfg = (cfg.get("tiers") or {}).get(tier or "", {})
    if tcfg.get("max") is not None:
        caps["tier"] = float(tcfg["max"])

    if arquetipo is not None:
        ca = (cfg.get("cap_por_arquetipo") or {}).get(arquetipo)
        if ca is not None:
            caps["arquetipo"] = float(ca)

    if banda is not None:
        cb = (cfg.get("cap_por_banda") or {}).get(banda)
        if cb is not None:
            caps["banda"] = float(cb)

    if tier == "opcionalidad" and verificacion is not None:
        ce = (cfg.get("cap_por_evidencia_opcionalidad") or {}).get((verificacion or "").upper())
        if ce is not None:
            caps["evidencia"] = float(ce)

    if not caps:
        return 0.0, "sin_caps"
    liga = min(caps, key=lambda k: caps[k])       # el cap más restrictivo
    return caps[liga], liga
```

## backend/agentes/comparacion_rotacion.py
```python
"""P1 (doc 91 §7, blueprint IA2 §5) — COMPARACIÓN antes de rotar. MODO SOMBRA: el código llena A y B desde los
dossiers; el PM solo escribe el argumento. Se rota SOLO si se cumplen las TRES condiciones (no compensatorio):
evidencia + margen + riesgo. Ante empate → se mantiene A (la carga de la prueba recae en la TRANSACCIÓN). Cada
rotación PERMITIDA alimenta el contrafactual A-vs-B (P2.1, ya implementado). Determinista, $0.

Caso IESC→EME de la corrida: B=EME no tenía dossier → falla la condición de evidencia → BLOQUEADA.
"""
from __future__ import annotations

_VERIF_ORD = {"FAIL": 0, "REVIEW": 1, "PASS": 2}
_BANDA_ORD = {"RECORTE": 0, "MANTENER": 1, "COMPRA": 2, "COMPRA_FUERTE": 3}
_SEV_ORD = {"leve": 0, "media": 1, "severa": 2}


def comparar_rotacion(a: dict, b: dict) -> tuple[str, list[str]]:
    """(resultado, motivos). `a`/`b` traen verificacion, banda, bear_severidad, nulls_portantes, dossier_del_ciclo.
    Para una venta a caja, `b={'es_caja': True}` y se evalúa la regla de caja sobre A."""
    # Venta a CAJA: válida solo si A ya no merece el capital (RECORTE / no elegible / flag ALTA 'no opera').
    if b.get("es_caja"):
        if a.get("banda") == "RECORTE" or a.get("no_elegible_tier") or a.get("flag_alta_no_opera"):
            return "PERMITIDA", ["venta a caja: A en RECORTE / no elegible / flag ALTA respondido no_opera"]
        return "BLOQUEADA", ["venta a caja sin motivo válido: A no está en RECORTE ni perdió elegibilidad"]

    motivos: list[str] = []
    # 1. Evidencia: verif(B) >= verif(A), sin nulls portantes en B, dossier de B del ciclo.
    if _VERIF_ORD.get((b.get("verificacion") or "").upper(), 0) < _VERIF_ORD.get((a.get("verificacion") or "").upper(), 0):
        motivos.append("evidencia: verificación de B peor que la de A")
    if b.get("nulls_portantes"):
        motivos.append("evidencia: B tiene nulls portantes")
    if not b.get("dossier_del_ciclo", True):
        motivos.append("evidencia: el dossier de B no es del ciclo")
    # 2. Margen: banda(B) al menos UN escalón por encima de banda(A).
    if _BANDA_ORD.get(b.get("banda"), -1) < _BANDA_ORD.get(a.get("banda"), -1) + 1:
        motivos.append("margen: la banda de B no está ≥1 escalón sobre la de A")
    # 3. Riesgo: bear de B no más severo que el de A.
    if _SEV_ORD.get(b.get("bear_severidad"), 9) > _SEV_ORD.get(a.get("bear_severidad"), 0):
        motivos.append("riesgo: el bear de B es más severo que el de A")

    return ("PERMITIDA", []) if not motivos else ("BLOQUEADA", motivos)
```

## config/ips.yaml — sección de tiers/arquetipos (lo demás del IPS no cambió)
```yaml
# --- IPS por TIERS (P1.3, doc 91 §7 — reemplaza al piso rígido con 4 categorías ECONÓMICAS) ---
# IA1 it.2: la opcionalidad es una categoría distinta, NO un CORE chico → NO hay tier 3-5% (evita que toda posición
# chica sea una excepción al piso). El tier NO da derecho a usar todo su rango: siempre gana el cap más restrictivo
# (liquidez/supervivencia/sector/cuello). Implementado test-driven (18 tests de aceptación en el acumulador).
tiers:
  OPTIONALITY:    {min: 0.015, max: 0.025}  # asimetría alta con incertidumbre material (max 2.5% = half-Kelly, IA2)
  CORE:           {min: 0.05, max: 0.10}   # tesis con margen de seguridad
  HIGH_CONVICTION: {min_exclusive: 0.10, max: 0.15}   # oportunidad excepcional con evidencia robusta
  EXCEPTIONAL:    {min_exclusive: 0.15, max: 0.20}   # concentración extraordinaria
# Tope por ARQUETIPO (IA2, resuelto 2026-11-25): la pieza que más protege el norte — capea cíclicas e infra a 10% y
# PROHÍBE pre-revenue en núcleo (solo opcionalidad). Gana el más restrictivo entre este y el tier/banda/evidencia.
cap_por_arquetipo: {compounder: 0.15, ciclica: 0.10, infra: 0.10, pre_revenue: 0.0}
# Caps de DINERO NUEVO por banda (IA2 §1) y por evidencia en opcionalidad (IA2 §1.opcionalidad). El tamaño final =
# min(tier, arquetipo, banda, evidencia, + caps existentes de liquidez/superv/sector/cuello). Nada compensa nada.
cap_por_banda: {COMPRA_FUERTE: 0.15, COMPRA: 0.10, MANTENER: 0.0, RECORTE: 0.0}
cap_por_evidencia_opcionalidad: {PASS: 0.025, REVIEW: 0.015, FAIL: 0.0}
optionality:
  max_positions: 4             # ~8% agregado / 2.5% por nombre ≈ 3-4 plazas
  max_aggregate_weight: 0.08   # cap AGREGADO (operador 2026-11-25: punto medio IA1 6% / IA2 15%); al tocarlo, se congela
  requires_verified_dossier: true       # excepción al TAMAÑO mínimo, NO a la calidad de evidencia
  requires_economic_justification: true
```

## ops/sombra_run.py — el demo que produjo los veredictos de arriba
```python
"""P1 MODO SOMBRA — aplica el kit de cómputo (arquetipo→banda→cap→permiso→rotación) a los 7 nombres de la corrida
del 25-nov y muestra "qué habría decidido P1", para contrastar con el trato esperado por IA1/IA2.

NO aplica nada — es el demo de sombra (computa + loguea). Insumos derivados del backup `backup_comite_2026-11-25.md`;
donde falta un rango numérico (valor mitad-de-ciclo, cobertura IG), la banda queda en None y se marca "[falta insumo:
lo extrae el harness real del dossier]". Determinista, $0.

  .venv/bin/python -m ops.sombra_run
"""
from __future__ import annotations

from backend.agentes.arquetipo import clasificar_arquetipo
from backend.agentes.banda import calcular_banda
from backend.agentes.caps_posicion import cap_posicion
from backend.agentes.ips import IPS
from backend.agentes.permiso_ejecucion import execution_permission

# Insumos por nombre, derivados del backup del 25-nov (señales de arquetipo + lo que haya para la banda).
# accion/motivo = lo que PROPUSO el PM esa corrida. verif = veredicto ciego/principal.
NOMBRES = {
    "EXE":  {"sig": {"sector": "E&P", "revenue_ltm": 7.5e9}, "verif": "REVIEW",
             "banda_in": {"precio": 95, "valor_mitad_ciclo_bajo": 40, "valor_mitad_ciclo_alto": 80},  # a la curva <$3
             "accion": "aumentar", "motivo": "discrecional", "esperado": "cíclica · precio sobre el rango → RECORTE · no aumentar"},
    "VST":  {"sig": {"sector": "IPP"}, "verif": "FAIL",   # verificación ciega FAIL
             "banda_in": {}, "accion": "aumentar", "motivo": "discrecional",
             "esperado": "cíclica · FAIL → bloquear hasta reconciliar (verif + FCF normalizado)"},
    "IESC": {"sig": {"sector": "contratista_electrico", "margen_op_ltm": 0.156, "margen_op_mediana_10a": 0.09},
             "verif": "REVIEW", "banda_in": {}, "accion": "salir", "motivo": "discrecional", "dossier_del_ciclo": False,
             "esperado": "cíclica (margen 1.5×+ mediana) · venta discrecional con datos viejos → DIFERIR"},
    "CIFR": {"sig": {"contratado_firme": 14.6e9, "ev": 7.8e9, "capex": 2.0e9, "revenue": 0.27e9, "ocf_ltm": -10e6},
             "verif": "PASS", "banda_in": {"cobertura_ig_bajo": 0.3}, "flag_alta": True,
             "accion": "salir", "motivo": "discrecional", "esperado": "infra · flag ALTA → salida independiente OK"},
    "GLXY": {"sig": {"contratado_firme": 30e9, "ev": 7.0e9, "capex": 3.5e9, "revenue": 0.5e9, "ocf_ltm": -5e6},
             "verif": "PASS", "banda_in": {"cobertura_ig_bajo": 0.0},  # CoreWeave no-IG → cobertura ~0
             "accion": "mantener", "motivo": "discrecional", "esperado": "infra · cobertura ~0 → RECORTE · no entra"},
    "WOLF": {"sig": {"revenue_ltm": 620e6, "margen_bruto_ltm": -0.22}, "verif": "REVIEW", "banda_in": {},
             "accion": "mantener", "motivo": "discrecional", "esperado": "pre_revenue · solo opcionalidad si p_impl<p_razon"},
    "EME":  {"sig": {}, "verif": "REVIEW", "banda_in": {}, "sin_dossier": True,
             "accion": "abrir", "motivo": "discrecional", "esperado": "sin dossier → BLOQUEAR"},
}


def _evaluar(cfg: dict, d: dict) -> dict:
    arq = clasificar_arquetipo(d["sig"])
    banda = calcular_banda(arq, {**d.get("banda_in", {})}) if arq else None
    tier = "opcionalidad" if (arq == "pre_revenue" or d.get("flag_alta")) else "nucleo"
    tier_cfg = "OPTIONALITY" if tier == "opcionalidad" else "CORE"
    cap, liga = cap_posicion(tier=tier_cfg, arquetipo=arq, banda=banda, verificacion=d["verif"], cfg=cfg)
    # contexto del permiso (shadow): tier no elegible si núcleo con verif != PASS; métrica/falsador asumidos presentes
    # salvo sin_dossier; banda RECORTE/None o cap 0 → no apto para apertura.
    ctx = {"accion": d["accion"], "motivo_accion": d["motivo"], "verificacion": d["verif"],
           "metrica_obligatoria_null": d.get("sin_dossier", False),
           "falsador_id": None if d.get("sin_dossier") else "f", "falsador_sobre_metrica": not d.get("sin_dossier"),
           "tier_elegible": (d["verif"] == "PASS") if tier == "nucleo" else True,
           "peso_sobre_min_caps": False, "crea_stub_o_viola_ips": False,
           "dossier_del_ciclo": d.get("dossier_del_ciclo", True)}
    permiso, motivos = execution_permission(ctx)
    return {"arquetipo": arq or "UNCLASSIFIED", "banda": banda or "—", "cap": cap, "liga": liga,
            "permiso": permiso, "motivos": motivos}


def main() -> int:
    cfg = IPS.cargar().cfg
    print("=== P1 EN SOMBRA — qué habría decidido sobre la corrida del 25-nov (NO aplica, solo computa) ===\n")
    for tk, d in NOMBRES.items():
        r = _evaluar(cfg, d)
        banda_nota = r["banda"] if r["banda"] != "—" else "— [falta rango: lo extrae el harness real del dossier]"
        print(f"{tk}  (PM propuso: {d['accion']})")
        print(f"   arquetipo={r['arquetipo']} · banda={banda_nota} · cap={r['cap']:.1%} (liga: {r['liga']}) · "
              f"PERMISO={r['permiso']}")
        if r["motivos"]:
            print(f"   motivos: {'; '.join(r['motivos'])}")
        print(f"   esperado (IA1/IA2): {d['esperado']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

# CÓDIGO P0 — cambios de AUTORIDAD (bloques clave, los bugs que encontraron)

Son ediciones a archivos existentes; acá van los bloques centrales. El diff completo de la rama está en GitHub.

## P0.1 — verificación = autoridad en el gate (backend/agentes/orquestador_decision.py)
```python
260:            # P0.1 (doc 91) — AUTORIDAD DE VERIFICACIÓN: el veredicto del Verificador manda, el PM no lo anula.
261-            # FAIL → bloqueo DURO (el PM no puede tratarlo como PASS). REVIEW → se MARCA (BORJA permite actuar con
262-            # REVIEW pero "no terminás con una posición grande"). La apertura sin dossier ya la cubre el CANDADO.
263-            v = verifs.get(tk, "")
264-            if v == "fail":
265-                alertas.append(f"{tk}: Verificador FAIL — autoridad de verificación: NO se abre/aumenta (el PM no lo anula)")
266-                continue
267-            if v == "review":
268-                alertas.append(f"{tk}: Verificador REVIEW — entrada/aumento MARCADO (no termina en posición grande)")
```

## P0.2 — falsador estructurado del dossier = fuente de verdad (ledger_decisiones.py + resolucion.py)
```python
70:    # P0.2 (doc 91) — falsador ESTRUCTURADO del dossier (fuente de verdad, correctamente firmado: lo escribió el
71-    # Analista con {metrica,operador,umbral,consecuencia,vara_externa}). El PM NO lo reescribe → no se invierte el
72-    # signo. La resolución ex-post debe evaluar ESTE predicado, no el texto libre del PM. None = legacy.
73-    falsador_dossier: dict | None = None
74-    conviccion_0_1: float
...
35:        # P0.2 (doc 91): mostrar la condición de muerte CORRECTAMENTE FIRMADA del dossier (el analista la escribió
36-        # bien), no el texto libre del PM —que puede venir con el signo invertido y arruinar la resolución—.
37-        fd = d.falsador_dossier or {}
38-        desc = fd.get("que_lo_mataria") or fd.get("afirmacion") or d.falsador_afirmacion
```

## P0.3 — el 8-K 5.02 ya no afirma salida (backend/agentes/reglas_salida.py)
```python
18:# P0.3 (doc 91): el Item 5.02 cubre salida DE directores/ejecutivos, nombramientos Y arreglos de compensación.
19-# A esta altura (poller) no hay cuerpo del 8-K para distinguirlos → la etiqueta NO afirma una salida (eso inyectaba
20-# una señal falsa al PM: el 5.02 de IESC era compensación/PSUs, no una salida). Queda como prompt de verificación;
21-# el deep lee el cuerpo y determina qué es. (Fiel a "ausencia de dato ≠ veto".)
22-_ITEMS_TIER_C = {"5.02": "cambio en directorio/management (5.02) — verificar si es salida, nombramiento o compensación",
23-                 "3.01": "aviso de deslistado / precio mínimo",
24-                 "4.01": "cambio de auditor (revisar si hay desacuerdos)"}
```

## P0.4 — invariante post-trade (orquestador_decision.py)
```python
363:        # P0.4 (doc 91) — INVARIANTE POST-TRADE: la cartera FINAL no debe quedar con stubs sub-piso (0<w<piso).
364-        # Nadie chequeaba el estado final (IA1+IA2): una REDUCCIÓN parcial podía dejar un stub (el piso solo se
365-        # aplicaba a aumentos). Se SEÑALA; NO se auto-corrige (reducir-a-stub → salida total es política de
366-        # atomicidad, diferida a P1). El Auditor recibe esta alerta.
367-        if piso > 0:
368-            _parking = tickers_parking(self.ips.cfg)
369-            _stubs = sorted(tk for tk, w in cand.items() if 1e-9 < w < piso - 1e-9 and tk not in _parking)
370-            if _stubs:
371-                alertas.append("INVARIANTE POST-TRADE: stubs sub-piso en el estado final — "
372-                               + ", ".join(f"{tk} {cand[tk]:.1%}" for tk in _stubs)
```

## P0.5 — reconciliación interna del market cap (data_pack.py) + bloqueo (backfill_fichas.py)
```python
471:    # 2b) MARKET CAP INTERNO (P0.5, doc 91): market_cap vs precio×acciones del MISMO feed. Divergencia → estructura
472-    # multi-clase o error de escala → el EV/valuación NO es confiable (caso GLXY: el market cap cuenta TODAS las
473-    # clases y shares_outstanding es solo clase A → mc/precio=584M vs 189M reportadas). Lo caza sin XBRL. Solo cuando
474-    # precio y market_cap están en la MISMA moneda (si difieren es conversión FX, no inconsistencia — las extranjeras
475-    # ya son 2ª clase de datos). IA2: la falta de reconciliación del equity debe BLOQUEAR la valuación.
476-    p_precio = next((p for p in puntos if p.metric == "precio" and p.value), None)
477-    p_mc = next((p for p in puntos if p.metric == "market_cap" and p.value is not None), None)
478-    if (p_precio and p_mc and feed_sh and feed_sh > 0 and p_precio.value > 0
479-            and getattr(p_precio, "currency", None) == getattr(p_mc, "currency", None)):
480-        implied = p_mc.value / p_precio.value
481-        div_mc = abs(implied - feed_sh) / max(implied, feed_sh)
...
40:    # P0.5 (doc 91): flags de VALUACIÓN ROTA (market cap que no reconcilia con precio×acciones, o escala errada)
41-    # → datos_conflicted. IA2: la falta de reconciliación del equity debe BLOQUEAR la valuación/compra (caso GLXY).
42-    _duros = {"flag_balance_desactualizado", "flag_market_cap_no_reconcilia", "flag_market_cap_escala"}
43-    if any(p.metric in _duros for p in puntos):
```

## P1.4 — el auditor recibe los controles deterministas (auditor.py)
```python
73:        # P1.4 (doc 91): surface los REVIEW (parcial) — el PM NO debe tratarlos como PASS (caso EXE/VST/EME).
74-        reviews = [t for t, v in _v.items() if v == "review"]
75-        reviews_txt = ", ".join(reviews) if reviews else "(ninguno en REVIEW)"
76-        # P1.4 — CONTROLES DETERMINISTAS (capa 1): lo que el código YA detectó en el gate (bloqueos por verificación,
77-        # stubs sub-piso, datos no reconciliados, entradas fuera de zona). El auditor NO debe ignorarlos.
78-        ctrl_txt = ("\n".join(f"- {c}" for c in controles_deterministas)
```
