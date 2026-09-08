# Consola Claude Code embebida — BORJA (deploy GCP)

> Objetivo: que un Quant del equipo, al entrar a BORJA vía web, tenga en el sidebar
> un acceso a una **consola Claude Code idéntica** a la CLI — corriendo dentro de un
> **sandbox aislado** (contenedor), detrás de auth fuerte, sobre una VM de GCP
> internet-facing.
>
> **Estado:** artefactos listos, **NO activados**. Nada de esto toca la app viva
> hasta que apliques los "diffs de activación" (§5) y despliegues en la VM.
>
> **➡️ ¿Sólo querés el DEMO en IP pública:4151? Andá a [`DEMO.md`](DEMO.md).**
> Este README es la referencia de **producción / hardening** (IAP, Caddy, Docker),
> para cuando la seguridad importe.

---

## 0. La verdad sin vueltas (leer antes de desplegar)

"Exactamente como esta consola" = el binario `claude` real en una terminal web. Claude
Code **ejecuta bash** → quien llegue a esa terminal puede correr comandos arbitrarios.
El sandbox protege el **host** (DB viva de prod, API keys, otros proyectos); pero dentro
del contenedor hay una shell Claude Code con **tu API key** y **acceso de lectura a los
datos**. Por eso, internet-facing, **el gateway de identidad es todo**. Este diseño usa
**dos candados en serie** (IAP + auth de BORJA) y un contenedor endurecido.

Residual risk que NO desaparece: costo de API (poné spend-cap), y que un Quant autorizado
haga algo tonto dentro del sandbox (mitigado con DB read-only + workspace aislado + sin
acceso a secretos de prod).

---

## 1. Arquitectura (topología recomendada en GCP)

```
Internet
  │  (GCP VPC firewall: sólo 443; SSH sólo por IAP tunnel)
  ▼
GCP Identity-Aware Proxy (IAP)        ← SSO Google por-usuario (dominio i-314.com)
  │  sólo identidades IAM autorizadas pasan
  ▼
Caddy  (:443, auto-TLS Let's Encrypt) ── en la VM
  ├─ /                → BORJA uvicorn 127.0.0.1:8111   (dashboard, systemd, auth cookie)
  └─ /consola/term/*  → ttyd 127.0.0.1:7681            (contenedor sandbox)
                         (además, forward_auth a /auth/check si NO usás IAP)
  ▼
Docker: contenedor "borja-consola"   (non-root, rootfs read-only, caps dropped,
  └─ ttyd --writable → claude          mem/pids limit, sin docker.sock)
       · workspace = clone AISLADO (writable, no es el checkout de prod)
       · /workspace/data = DB de prod montada READ-ONLY
       · HOME = tmpfs (claude escribe su sesión ahí)
       · ANTHROPIC_API_KEY = inyectada desde GCP Secret Manager (nunca en git)
```

**Por qué IAP:** cierra de un saque los 3 hallazgos de seguridad (§4): nada de la VM
—ni `/api/*`, ni la consola— es accesible sin una identidad Google autorizada. Es
per-usuario, auditable en Cloud Logging y revocable por IAM. Si por algún motivo no
podés usar IAP, Caddy hace `forward_auth` contra `/auth/check` (cookie de BORJA) — pero
IAP es netamente superior para esto.

---

## 2. Componentes de este directorio

**Piezas del DEMO (existen ya — ver `DEMO.md`):**

| Archivo | Qué es |
|---|---|
| `DEMO.md` | Runbook simple para IP pública:4151 (lo que querés ahora). |
| `borja-consola.service` | systemd unit: corre `ttyd` con `claude` (con basic-auth `-c`). |
| `../../backend/consola.py` | Router FastAPI: página `/consola` (iframe) + `/auth/check`. **Nuevo, sin cablear.** |
| `../../frontend/templates/consola.html` | La página que embebe la terminal en el dashboard. |

**Piezas de PRODUCCIÓN / hardening (plantillas a generar cuando endurezcas):**
`Dockerfile` + `entrypoint.sh` (sandbox no-root), `docker-compose.yml` (contenedor
endurecido), `Caddyfile` (TLS + forward_auth). No hacen falta para el demo. Avisá y
las genero.

---

## 3. Runbook de deploy en la VM de GCP

Prerrequisitos en la VM (Debian/Ubuntu): Docker + compose, Caddy, el repo clonado en
`/opt/borja` (prod) y BORJA corriendo bajo systemd en `127.0.0.1:8111`.

```bash
# 3.1 — Workspace AISLADO para la consola (clone separado, writable; NO es prod)
sudo git clone /opt/borja /opt/borja-consola-workspace
sudo chown -R 1000:1000 /opt/borja-consola-workspace   # uid del usuario 'quant'

# 3.2 — Secreto: API key dedicada con spend-cap (Anthropic Console → Workspaces/Keys)
#        Guardarla en GCP Secret Manager y materializarla como env-file (git-ignored):
gcloud secrets versions access latest --secret=borja-consola-anthropic-key \
  | sudo tee /opt/borja/ops/consola/.env.consola >/dev/null
sudo sed -i '1s/^/ANTHROPIC_API_KEY=/' /opt/borja/ops/consola/.env.consola
sudo chmod 600 /opt/borja/ops/consola/.env.consola

# 3.3 — Construir y levantar el sandbox
cd /opt/borja/ops/consola
export CONSOLA_WORKSPACE=/opt/borja-consola-workspace
export BORJA_DATA_RO=/opt/borja/data
docker compose up -d --build
docker compose logs -f consola     # verificar que ttyd quedó en 127.0.0.1:7681

# 3.4 — Edge: Caddy con TLS + ruteo (editar dominio en Caddyfile)
sudo cp Caddyfile /etc/caddy/Caddyfile      # ajustar consola.tu-dominio antes
sudo systemctl reload caddy

# 3.5 — IAP (recomendado): activar Identity-Aware Proxy sobre el backend de la VM
#        y conceder rol roles/iap.httpsResourceAccessor sólo a los Quants autorizados.
#        (Guía: cloud.google.com/iap/docs/enabling-compute-howto)

# 3.6 — Firewall VPC: permitir 443 (o sólo rangos IAP 35.235.240.0/20 si usás IAP),
#        cerrar 8111/7681 al exterior (quedan en 127.0.0.1). SSH sólo por IAP tunnel.

# 3.7 — Activar en BORJA los 3 diffs de §5 y reiniciar el servicio.
```

---

## 4. Hallazgos de seguridad del código actual (arreglar para internet-facing)

1. **`/api/*` sin auth** — `backend/auth.py:_PATHS_SIN_AUTH` incluye `/api/`, así que
   todos los `/api/*` (varios POST que cambian estado o gastan API) quedan abiertos.
   → **IAP delante lo cierra.** Alternativa: quitar `/api/` de esa lista y usar API-keys
   por header para los scripts que hoy dependen de `/api/` abierto.
2. **Cookie `secure=False`** — `do_login()` setea la cookie sin `Secure`. Sobre HTTPS
   poné `secure=True` (ver diff §5.3) y considerá `samesite="strict"`.
3. **Password admin único compartido** — sin identidad/revocación/auditoría por-usuario.
   → **IAP da identidad Google per-Quant.** La cookie de BORJA queda como 2º candado.

---

## 5. Diffs de activación (aplicar recién en la VM, tras probar)

**5.1 — Cablear el router** (`backend/main.py`, tras `app.include_router(ui_router)`):
```python
from backend.consola import router as consola_router
app.include_router(consola_router)
```

**5.2 — Link en el sidebar** (`frontend/templates/base.html`, dentro de `<nav>`):
```html
<a href="/consola" class="sidebar-link {% if active == 'consola' %}active{% endif %}">
  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
  Consola
  <span class="ml-auto text-[9px] font-semibold bg-indigo-600 text-white rounded px-1.5 py-0.5">quant</span>
</a>
```

**5.3 — Cookie segura en prod** (`backend/auth.py`, en `do_login()`):
```python
resp.set_cookie(
    COOKIE_NAME, cookie_val, max_age=COOKIE_MAX_AGE,
    httponly=True, samesite="lax",
    secure=(get_settings().app_env != "dev"),   # True detrás de HTTPS
)
```

Luego: `sudo systemctl restart borja` en la VM.

---

## 6. Operación

- **Logs de la consola:** `docker compose logs -f consola`.
- **Actualizar Claude Code:** `docker compose build --no-cache && docker compose up -d`.
- **Costo:** la consola gasta contra la API key dedicada — poné un **spend-cap** a esa
  key en la Anthropic Console y revisá el uso ahí. Es independiente de la key del sistema.
- **Cortar acceso a un Quant:** quitarle el rol IAP (o rotar el password admin si no usás IAP).
- **Concurrencia:** ttyd está capado a pocos clientes (`-m`); subir en `entrypoint.sh` si hace falta.

## 7. Pendiente / decisiones abiertas

- ¿Workspace **writable-aislado** (default acá, el Quant puede editar/correr sin tocar prod)
  o **read-only** total? Cambia el mount en `docker-compose.yml`.
- ¿Egress del contenedor restringido sólo a `api.anthropic.com`? (hoy egress abierto;
  se puede meter un egress-proxy si querés cerrarlo).
- ¿Un contenedor por-Quant (aislamiento total entre usuarios) o uno compartido? (default: compartido).
