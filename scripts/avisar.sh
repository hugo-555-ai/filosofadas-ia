#!/usr/bin/env bash
# avisar.sh <id> — crea la vista previa y envia el correo de aviso.
set -euo pipefail
umask 022

ID="${1:?falta el id}"
BASE=/var/lib/filosofadas
DOCROOT=/var/www.hugo.cat/html
DIR="$BASE/pending/$ID"
ENV=/etc/filosofadas/env

[ -d "$DIR" ] || { echo "No existe $DIR" >&2; exit 66; }

leer_env() { awk -F= -v k="$1" '$1==k{sub(/^[^=]*=/,""); print; exit}' "$ENV"; }

TOKEN_VISTA="$(leer_env TOKEN_VISTA)"
BASE_VISTA="$(leer_env BASE_VISTA)"
CORREO_DESTINO="$(leer_env CORREO_DESTINO)"
REMITENTE="$(leer_env REMITENTE)"
# Token de accion para los botones (se guarda SOLO el hash, nunca el token)
TOKEN="$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)"
HASH_ACCION="$(printf '%s' "$TOKEN" | sha256sum | cut -d' ' -f1)"
python3 - "$DIR" "$HASH_ACCION" <<'PYX'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
est = json.load(open(d / "estado.json"))
est["accion_hash"] = sys.argv[2]
json.dump(est, open(d / "estado.json", "w"), ensure_ascii=False, indent=2)
PYX

FECHA="$(python3 -c "import json;print(json.load(open('$DIR/estado.json'))['fecha'])")"
EXPIRA="$(python3 -c "import json;print(json.load(open('$DIR/estado.json'))['expira'])")"

# --- vista previa (ruta ofuscada, solo lectura, noindex) ---
HASH="$(printf '%s' "${ID}${TOKEN_VISTA}" | sha256sum | cut -c1-20)"
DEST="$DOCROOT/o/$HASH/$ID"
mkdir -p "$DEST"
chmod 755 "$DEST"
for t in ca es cost; do
  cp -f "$DIR/$t.html" "$DEST/$t.html"
  chmod 644 "$DEST/$t.html"
done

cat > "$DEST/index.html" <<HTML
<!doctype html>
<html lang="ca"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
<title>Esborrany FiloNotícies $FECHA</title>
<link rel="stylesheet" href="/filonoticies.css">
</head><body><main class="fn">
<header class="fn-capcalera">
<p class="fn-seccio">Esborrany — pendent de revisió</p>
<h1 class="fn-data">$FECHA</h1></header>
<p>Tres versions amb les mateixes notícies:</p>
<ul class="fn-versions">
<li><a href="ca.html">CA — català</a></li>
<li><a href="es.html">ES — castellà</a></li>
<li><a href="cost.html">COST — castellà costeño</a></li>
</ul>

<section class="fn-accions">
<h2 class="fn-peu-titulo">Decisió</h2>
<form method="post" action="/fn-accion/aprobar-todas">
  <input type="hidden" name="id" value="$ID">
  <input type="hidden" name="t" value="$TOKEN">
  <button class="fn-boto fn-boto-ok" type="submit">Publicar les tres</button>
</form>
<form method="post" action="/fn-accion/aprobar">
  <input type="hidden" name="id" value="$ID">
  <input type="hidden" name="t" value="$TOKEN">
  <label>Només una versió:
    <select name="loc">
      <option value="ca">CA</option>
      <option value="es">ES</option>
      <option value="cost">COST</option>
    </select>
  </label>
  <button class="fn-boto" type="submit">Publicar</button>
</form>
<form method="post" action="/fn-accion/rechazar"
      onsubmit="return confirm('Rechazar las TRES versiones y pedir otras noticias?')">
  <input type="hidden" name="id" value="$ID">
  <input type="hidden" name="t" value="$TOKEN">
  <button class="fn-boto fn-boto-no" type="submit">Rebutjar les tres</button>
</form>
</section>

<p class="fn-aviso">Pàgina privada d'esborrany. Caduca el $EXPIRA.</p>
</main></body></html>
HTML
chmod 644 "$DEST/index.html"

URL_VISTA="${BASE_VISTA%/}/$HASH/$ID"
python3 - "$DIR" "$URL_VISTA" <<'PYX'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
est = json.load(open(d / "estado.json"))
est["vista"] = sys.argv[2]
json.dump(est, open(d / "estado.json", "w"), ensure_ascii=False, indent=2)
PYX
echo "vista previa: $URL_VISTA"

# --- correo (si hay msmtp configurado) ---
if [ -f /etc/msmtprc ] && command -v msmtp >/dev/null 2>&1; then
  {
    printf 'Subject: FiloNoticias %s - borrador listo\n' "$FECHA"
    printf 'From: %s\n' "$REMITENTE"
    printf 'To: %s\n' "$CORREO_DESTINO"
    printf 'Content-Type: text/plain; charset=utf-8\n'
    printf '\n'
    printf 'Tres versions amb les mateixes noticies. Obre la vista previa:\n\n'
    printf '  %s\n\n' "$URL_VISTA"
    printf 'A la pagina tens tres botons:\n\n'
    printf '  [ Publicar les tres ]  publica CA + ES + COST alhora (cas habitual)\n'
    printf '  [ Publicar ]           nomes una versio, triada al desplegable\n'
    printf '  [ Rebutjar les tres ]  descarta el borrador i demana altres noticies\n\n'
    printf 'Els botons fan una peticio POST autenticada amb un token d un sol us\n'
    printf 'que viatja dins la propia pagina. No cal SSH ni copiar cap ordre.\n\n'
    printf 'Linia de comandes (alternativa, per SSH):\n\n'
    printf '  sudo -u filosofadas /etc/filosofadas/aprobar.sh ca   %s\n' "$ID"
    printf '  sudo -u filosofadas /etc/filosofadas/aprobar.sh es   %s\n' "$ID"
    printf '  sudo -u filosofadas /etc/filosofadas/aprobar.sh cost %s\n' "$ID"
    printf '  sudo -u filosofadas /etc/filosofadas/rechazar.sh %s\n\n' "$ID"
    printf 'Caduca: %s\n' "$EXPIRA"
  } | msmtp "$CORREO_DESTINO"
  echo "avis enviat a $CORREO_DESTINO"
else
  echo "AVISO: msmtp no configurado todavia - correo NO enviado" >&2
fi
