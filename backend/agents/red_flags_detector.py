"""Detector automático de red flags básicos (Tier 1 hardening).

Responsabilidad: escanear eventos recientes (noticias + filings) buscando patrones
que corresponden a los 8 red flags del doc 01 sec 3 Regla 2, y auto-incrementar
`Ficha.red_flags_count` + agregar detalle + disparar evento RED_FLAG.

Detectores implementados en Fase 1:
1. **ATM dilution** — keywords en noticias/filings: "at-the-market offering",
   "ATM program", "shelf offering announced", "direct offering".
2. **Guidance cut** — "lowered guidance", "reduced outlook", "guidance cut",
   "below consensus", "revised guidance downward".
3. **Auditor change / restatement** — "auditor resigned", "auditor change",
   "restatement", "CFO resigned", "material weakness".
4. **Short seller report** — "short report" + nombres conocidos (Hindenburg,
   Grizzly, Culper, Citron, Muddy Waters).
5. **SEC investigation** — "SEC investigation", "SEC probe", "Wells notice",
   "subpoena".

Logic: si detecta match, agrega +1 al red_flags_count (cap a 3), append al
red_flags_detalle con fecha+fuente, dispara evento tipo RED_FLAG.

Dedup: solo cuenta cada URL una vez (via metadata_json.url del evento).
"""
from __future__ import annotations

from datetime import timedelta

from backend.database import session_scope
from backend.models import EstadoEvento, EstadoFicha, Evento, Ficha, TipoEvento
from backend.utils import get_logger, utcnow

log = get_logger(__name__)


# Patrones por categoría (substrings case-insensitive)
PATRONES = {
    "ATM_DILUTION": [
        "at-the-market offering", "atm offering", "atm program",
        "direct offering announced", "shelf offering",
        "secondary offering", "registered direct offering",
    ],
    "GUIDANCE_CUT": [
        "lowered guidance", "cut guidance", "reduced guidance",
        "guidance cut", "lowered outlook", "reduces full-year outlook",
        "revised guidance lower", "falls short of guidance",
        "below consensus", "misses revenue", "misses estimates",
    ],
    "AUDITOR_RESTATEMENT": [
        "auditor resigned", "auditor change", "changes auditor",
        "restatement", "restate financials", "material weakness",
        "internal control failure", "delay filing", "delay annual report",
        "cfo resigned", "cfo fired", "cfo departure",
    ],
    "SHORT_REPORT": [
        "short report", "short seller", "hindenburg research",
        "grizzly research", "culper research", "citron research",
        "muddy waters", "kerrisdale", "wolfpack research",
    ],
    "SEC_INVESTIGATION": [
        "sec investigation", "sec probe", "wells notice",
        "sec subpoena", "sec inquiry", "sec charges",
        "sec fraud", "class action lawsuit", "securities fraud",
    ],
    # v4.2 Enmienda C — Insider Selling Atípico. Solo se activa si NO hay override
    # documentado en la ficha (10b5-1, founder_50, diversificacion_programada).
    "INSIDER_SELLING_ATIPICO": [
        "insider selling", "insiders sell", "ceo sells", "cfo sells",
        "executive selling", "officers sell", "director sells",
        "massive insider", "insider dump",
    ],
}

# Categorías que pueden ser overrideadas por la columna insider_selling_overrides_json.
CATEGORIAS_OVERRIDEABLES_POR_INSIDER_PLAN = {"INSIDER_SELLING_ATIPICO"}

# Estados donde los red flags importan (ignorar Eliminada/Candidata sin análisis)
ESTADOS_MONITOREADOS = [
    EstadoFicha.PORTFOLIO_ACTIVO.value,
    EstadoFicha.WL_PRIORITARIA.value,
    EstadoFicha.WL_ACTIVA.value,
    EstadoFicha.WL_SEGUIMIENTO.value,
    EstadoFicha.BUCKET_EXPLORATORIO.value,
]


def _clasificar_texto(texto: str) -> list[str]:
    """Retorna lista de categorías que matchean el texto (o vacía)."""
    if not texto:
        return []
    tlower = texto.lower()
    matches = []
    for categoria, patrones in PATRONES.items():
        for p in patrones:
            if p in tlower:
                matches.append(categoria)
                break  # una categoria solo una vez por texto
    return matches


def _url_ya_procesada(ticker: str, url: str) -> bool:
    """Chequea si este URL ya generó un evento RED_FLAG para este ticker."""
    if not url:
        return False
    with session_scope() as s:
        existe = (
            s.query(Evento)
            .filter(
                Evento.ticker == ticker,
                Evento.tipo == TipoEvento.RED_FLAG.value,
                Evento.timestamp > utcnow() - timedelta(days=30),
            )
            .all()
        )
        for e in existe:
            if (e.metadata_json or {}).get("url") == url:
                return True
    return False


def _aplicar_red_flag(ticker: str, categoria: str, descripcion: str, fuente: str, url: str | None = None) -> bool:
    """Incrementa red_flags_count, agrega detalle y dispara evento RED_FLAG. Retorna True si aplicó."""
    if url and _url_ya_procesada(ticker, url):
        return False

    now = utcnow()
    with session_scope() as s:
        f = s.query(Ficha).filter_by(ticker=ticker).first()
        if f is None or f.estado not in ESTADOS_MONITOREADOS:
            return False

        # Enmienda C v4.2: si la ficha tiene overrides documentados de insider
        # selling (10b5-1, founder_50, diversificacion_programada) la categoría
        # INSIDER_SELLING_ATIPICO NO activa red flag.
        if categoria in CATEGORIAS_OVERRIDEABLES_POR_INSIDER_PLAN:
            overrides = f.insider_selling_overrides_json or []
            if overrides:
                log.info(
                    "red_flag SKIP — ticker=%s categoria=%s override=%s",
                    ticker, categoria, overrides,
                )
                return False

        # Cap a 3 red flags (doc 01 sec 3 Regla 2)
        if f.red_flags_count >= 3:
            return False

        f.red_flags_count_anterior = f.red_flags_count
        f.red_flags_count += 1
        detalle_prev = f.red_flags_detalle or ""
        entry = f"[{now.strftime('%Y-%m-%d')} {categoria}] {descripcion[:200]}"
        f.red_flags_detalle = f"{detalle_prev}\n{entry}".strip()

        # Estado governance
        if f.red_flags_count >= 3:
            f.estado_governance = "kill_switch"
        elif f.red_flags_count >= 2:
            f.estado_governance = "amarillo"

        # Evento para auditoría + posible dispatch
        s.add(Evento(
            ticker=ticker,
            tipo=TipoEvento.RED_FLAG.value,
            descripcion=f"[{categoria}] {descripcion[:300]}",
            fuente=fuente,
            tier=1,
            estado=EstadoEvento.PENDIENTE.value,
            timestamp=now,
            metadata_json={
                "categoria_red_flag": categoria,
                "url": url,
                "red_flags_count_nuevo": f.red_flags_count,
            },
        ))

        log.warning(
            "RED_FLAG detectado — ticker=%s categoria=%s count=%d/3 (era %d)",
            ticker, categoria, f.red_flags_count, f.red_flags_count_anterior,
        )

    return True


# ---------- Escaneo principal ----------

def escanear_eventos_recientes(dias: int = 1) -> dict:
    """Escanea NOTICIA_MATERIAL recientes + descripciones de Form 4 buscando red flags.

    Llamado por el script_nocturno. Itera sobre eventos pendientes recientes,
    busca patrones, aplica red flags a las fichas correspondientes.
    """
    cutoff = utcnow() - timedelta(days=dias)
    detectados: list[dict] = []

    with session_scope() as s:
        eventos = (
            s.query(Evento)
            .filter(Evento.timestamp >= cutoff)
            .filter(Evento.tipo.in_([
                TipoEvento.NOTICIA_MATERIAL.value,
                TipoEvento.INSIDER_ACTIVITY.value,
            ]))
            .all()
        )
        eventos_data = [
            {"id": e.id, "ticker": e.ticker, "descripcion": e.descripcion,
             "fuente": e.fuente, "metadata": e.metadata_json or {}}
            for e in eventos
        ]

    for ev in eventos_data:
        categorias = _clasificar_texto(ev["descripcion"])
        if not categorias:
            continue

        # Metadata también puede contener título y resumen de la noticia
        for cat in categorias:
            url = (ev.get("metadata") or {}).get("url")
            aplicado = _aplicar_red_flag(
                ticker=ev["ticker"],
                categoria=cat,
                descripcion=ev["descripcion"],
                fuente=ev.get("fuente", "unknown"),
                url=url,
            )
            if aplicado:
                detectados.append({
                    "ticker": ev["ticker"],
                    "categoria": cat,
                    "descripcion": ev["descripcion"][:120],
                    "fuente": ev["fuente"],
                })

    return {
        "ventana_dias": dias,
        "eventos_escaneados": len(eventos_data),
        "red_flags_aplicados": len(detectados),
        "detectados": detectados,
        "timestamp": utcnow().isoformat(),
    }


def clasificar_texto_publico(texto: str) -> list[str]:
    """Wrapper público para tests — mismo que _clasificar_texto."""
    return _clasificar_texto(texto)
