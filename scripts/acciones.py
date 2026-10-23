#!/usr/bin/env python3
"""acciones.py — botones de aprobar/rechazar para la vista previa de FiloNoticias.

Escucha SOLO en 127.0.0.1. Apache le pasa las peticiones con ProxyPass.
No interpreta nada del contenido del borrador: valida un token y llama a los
MISMOS scripts que se usan por SSH (aprobar.sh / rechazar.sh). No duplica logica.
"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ENV     = Path("/etc/filosofadas/env")
APP     = Path("/opt/filosofia-ia/scripts")
BASE    = Path("/var/lib/filosofadas")
PUERTO  = 8791
MAX_CUERPO = 8192
LOCALES = ("ca", "es", "cost")

RE_ID    = re.compile(r"^\d{8}-\d{6}$")
RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


def log(msg):
    print(msg, flush=True)


def hash_token(t):
    return hashlib.sha256(t.encode()).hexdigest()


def cargar(id_):
    d = BASE / "pending" / id_
    f = d / "estado.json"
    if not f.exists():
        return None, "El borrador no existe"
    try:
        est = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None, "El borrador esta danado"
    if est.get("estado") in ("rechazado", "archivado"):
        return None, f"El borrador esta {est['estado']}"
    try:
        if datetime.fromisoformat(est["expira"]) < datetime.now(timezone.utc):
            return None, "El borrador ha caducado (mas de 72 h)"
    except Exception:
        pass
    return (d, est), None


def validar(par, token):
    d, est = par
    esperado = est.get("accion_hash")
    if not esperado:
        return "Este borrador no trae token de accion"
    if hash_token(token) != esperado:
        return "Token no valido"
    return None


def ejecutar(script, args, entrada=None):
    ruta = APP / script
    if not ruta.exists():
        return 70, f"No existe {ruta}"
    try:
        p = subprocess.run([str(ruta), *args], capture_output=True, text=True,
                           input=entrada, timeout=300)
    except subprocess.TimeoutExpired:
        return 124, "El comando tardo demasiado y se cortó"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def pagina(titulo, cuerpo, volver=None):
    enlace = f'<p><a href="{volver}">Volver a la vista previa</a></p>' if volver else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{titulo}</title>
<link rel="stylesheet" href="/filonoticies.css">
</head><body><main class="fn">
<header class="fn-capcalera"><p class="fn-seccio">FiloNoticias</p>
<h1 class="fn-data">{titulo}</h1></header>
<pre class="fn-salida">{cuerpo}</pre>
{enlace}
</main></body></html>"""


class Manejador(BaseHTTPRequestHandler):
    server_version = "FiloNoticiasAcciones/1.0"

    def log_message(self, fmt, *args):
        log("peticion: " + (fmt % args))

    def _responder(self, codigo, html):
        cuerpo = html.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self._responder(405, pagina("Metodo no permitido",
                                    "Este servicio solo acepta POST desde la vista previa."))

    def do_POST(self):
        accion = self.path.strip("/").split("/")[0].lower()
        if accion not in ("aprobar", "aprobar-todas", "rechazar"):
            self._responder(404, pagina("Accion desconocida", accion))
            return

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_CUERPO:
            self._responder(400, pagina("Peticion vacia", "Sin datos."))
            return

        datos = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        id_   = (datos.get("id") or [""])[0].strip()
        token = (datos.get("t")  or [""])[0].strip()
        loc   = (datos.get("loc") or [""])[0].strip()

        if not RE_ID.match(id_) or not RE_TOKEN.match(token):
            self._responder(400, pagina("Datos invalidos", "El id o el token no tienen el formato esperado."))
            return

        par, err = cargar(id_)
        if err:
            self._responder(409, pagina("No se puede actuar", err))
            return
        volver = (par[1].get("vista") or "").strip() or None
        err = validar(par, token)
        if err:
            log(f"rechazado por token: {id_}")
            self._responder(403, pagina("No autorizado", err, volver))
            return

        if accion == "aprobar":
            if loc not in LOCALES:
                self._responder(400, pagina("Version invalida", loc, volver))
                return
            cod, salida = ejecutar("aprobar.sh", [loc, id_])
            titulo = f"Publicado {loc}" if cod == 0 else f"Fallo al publicar {loc} (codigo {cod})"
        elif accion == "aprobar-todas":
            partes, peor = [], 0
            for l in LOCALES:
                cod, salida = ejecutar("aprobar.sh", [l, id_])
                peor = max(peor, cod)
                partes.append(f"--- {l} (codigo {cod}) ---\n{salida}")
            salida, cod = "\n\n".join(partes), peor
            titulo = "Publicadas las tres" if cod == 0 else f"Publicadas con fallos (codigo {cod})"
        else:
            cod, salida = ejecutar("rechazar.sh", [id_], entrada="SI\n")
            titulo = "Rechazado" if cod == 0 else f"Fallo al rechazar (codigo {cod})"

        log(f"{accion} {id_} ({loc or '-'}) -> codigo {cod}")
        self._responder(200 if cod == 0 else 500, pagina(titulo, salida or "(sin salida)", volver))


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    log(f"acciones.py escuchando en 127.0.0.1:{PUERTO}")
    servidor.serve_forever()
