# Publicar BORJA en https://borja.i-314.com

El DNS (Cloudflare) ya apunta acá y el cert `*.i-314.com` ya cubre el subdominio.
Solo falta decirle a nginx que enrute `borja.i-314.com` → la app en `127.0.0.1:4151`.

Correr en el server (necesita sudo):

```bash
# 1. instalar el vhost
sudo cp /opt/BORJA/ops/nginx/borja.i-314.com.conf /etc/nginx/sites-available/borja.i-314.com.conf
sudo ln -sf /etc/nginx/sites-available/borja.i-314.com.conf /etc/nginx/sites-enabled/borja.i-314.com.conf

# 2. validar que la config no tenga errores
sudo nginx -t

# 3. recargar (sin cortar el servicio)
sudo systemctl reload nginx   # o: sudo nginx -s reload
```

Después abrís **https://borja.i-314.com/hoja** → login con usuario `admin` + tu password.

## Nota Cloudflare
Si `borja.i-314.com` está en modo "proxied" (nube naranja) en Cloudflare, el SSL entre
Cloudflare y el origen tiene que estar en **Full (strict)** — el origin cert `*.i-314.com`
ya lo soporta. Si diera error 521/522, verificá que el registro DNS del subdominio exista
en el panel de Cloudflare apuntando a `136.116.113.253`.
