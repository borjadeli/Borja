"""SMTP mailer — alertas críticas + digest + reporte semanal.

Si SMTP_HOST o SMTP_PASSWORD están vacíos, el mailer opera en modo **dry_run**:
loguea el email completo (subject + body HTML) en vez de enviarlo. Esto permite
desarrollo y tests sin SMTP real.

Al configurar el .env con credenciales válidas, los emails se envían a SMTP_TO
desde SMTP_FROM (por default `contact@i-314.com`).
"""
from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import get_settings  # noqa: F401 (usado arriba)
from backend.utils import get_logger, utcnow

log = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates" / "emails"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass
class MailResult:
    enviado: bool
    dry_run: bool
    destinatario: str
    subject: str
    body_html: str
    body_text: str | None = None
    error: str | None = None
    timestamp: Any = field(default_factory=utcnow)


# ---------- Sent emails log (en memoria — para tests e inspección rápida) ----------

_sent_log: list[MailResult] = []


def get_sent_log() -> list[MailResult]:
    return list(_sent_log)


def clear_sent_log() -> None:
    _sent_log.clear()


# ---------- Envío ----------

def _smtp_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_password and s.smtp_user)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((smtplib.SMTPException, OSError)),
    reraise=True,
)
def _send_smtp(msg: EmailMessage) -> None:
    s = get_settings()
    if s.smtp_port == 465:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20) as server:
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)


def send_email(
    subject: str,
    body_html: str,
    body_text: str | None = None,
    to: str | None = None,
    tag: str = "",
) -> MailResult:
    """Envía email. En modo dry_run (SMTP no configurado) solo loguea."""
    s = get_settings()
    destinatario = to or s.smtp_to
    dry = not _smtp_configured()

    subject_prefix = f"[BORJA{' · ' + tag if tag else ''}] "
    subject_full = subject_prefix + subject

    result = MailResult(
        enviado=False,
        dry_run=dry,
        destinatario=destinatario,
        subject=subject_full,
        body_html=body_html,
        body_text=body_text,
    )

    if dry:
        log.info("mailer DRY_RUN — to=%s subject=%r (SMTP no configurado, loguea en vez de enviar)", destinatario, subject_full)
        _sent_log.append(result)
        return result

    try:
        msg = EmailMessage()
        msg["From"] = s.smtp_from or s.smtp_user
        msg["To"] = destinatario
        msg["Subject"] = subject_full
        if body_text:
            msg.set_content(body_text)
            msg.add_alternative(body_html, subtype="html")
        else:
            msg.set_content("Versión HTML en el email.")
            msg.add_alternative(body_html, subtype="html")
        _send_smtp(msg)
        result.enviado = True
        log.info("mailer SENT — to=%s subject=%r", destinatario, subject_full)
    except Exception as e:  # noqa: BLE001
        result.error = f"{type(e).__name__}: {e}"
        log.error("mailer FAILED — to=%s subject=%r error=%s", destinatario, subject_full, e)

    _sent_log.append(result)
    return result


def render_template(nombre: str, **ctx) -> str:
    """Renderiza un template HTML de emails/."""
    try:
        tmpl = _jinja_env.get_template(nombre)
    except Exception as e:
        log.error("mailer: template %s no encontrado: %s", nombre, e)
        raise
    ctx.setdefault("generado", utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    ctx.setdefault("base_url", get_settings().base_url)
    return tmpl.render(**ctx)


# ---------- Alertas específicas ----------

def alert_kill_switch(ticker: str, red_flags: int, detalle: str | None, rec_id: int | None = None) -> MailResult:
    body = render_template("alert_kill_switch.html",
        ticker=ticker, red_flags=red_flags, detalle=detalle, rec_id=rec_id,
    )
    return send_email(
        subject=f"KILL SWITCH · {ticker} · {red_flags}/3 red flags",
        body_html=body,
        tag="CRITICAL",
    )


def alert_bucket_stop_loss(ticker: str, caida_pct: float, stop_pct: float, precio_entrada: float | None) -> MailResult:
    body = render_template("alert_bucket_stop_loss.html",
        ticker=ticker, caida_pct=caida_pct, stop_pct=stop_pct, precio_entrada=precio_entrada,
    )
    return send_email(
        subject=f"STOP LOSS bucket · {ticker} · {caida_pct:.1f}% vs stop {stop_pct}%",
        body_html=body,
        tag="CRITICAL",
    )


def alert_red_flags_nivel_2(ticker: str, red_flags: int, detalle: str | None) -> MailResult:
    body = render_template("alert_red_flags.html",
        ticker=ticker, red_flags=red_flags, detalle=detalle,
    )
    return send_email(
        subject=f"Red flags · {ticker} · {red_flags}/3 activos",
        body_html=body,
        tag="ALERTA",
    )


def digest_nocturno(resumen: dict) -> MailResult | None:
    """Envía digest solo si hay items materiales. Si todo vacío, no envía nada."""
    total = (
        len(resumen.get("entry_ranges_vencidos", []))
        + len(resumen.get("triggers_sin_evaluar", []))
        + len(resumen.get("deep_research_vencido", []))
        + len(resumen.get("sectores_sin_actualizar", []))
        + len(resumen.get("mapas_sectoriales_vencidos", []))
    )
    if total == 0:
        log.info("mailer digest — sin items materiales, skip envío")
        return None

    body = render_template("digest_nocturno.html", r=resumen)
    return send_email(
        subject=f"Digest diario · {total} items materiales",
        body_html=body,
        tag="DIGEST",
    )


def reporte_semanal_email(reporte_html: str, estado_general: str = "estable") -> MailResult:
    """Envía el reporte semanal del Juez al admin."""
    return send_email(
        subject=f"Reporte semanal · Estado {estado_general}",
        body_html=reporte_html,
        tag="REPORTE",
    )


def ping() -> bool:
    """Verifica que la configuración esté presente (no envía email de prueba)."""
    return _smtp_configured()
