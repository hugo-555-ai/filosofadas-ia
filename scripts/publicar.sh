#!/usr/bin/env bash
# publicar.sh <locale> <id> — publica una version en su ruta, de forma atomica.
set -euo pipefail
umask 022

LOC="${1:?falta locale}"
ID="${2:?falta id}"
case "$LOC" in ca|es|cost) ;; *) echo "locale invalido: $LOC" >&2; exit 64 ;; esac

BASE=/var/lib/filosofadas
DIR="$BASE/pending/$ID"
DOCROOT=/var/www.hugo.cat/html
ORIGEN="$DIR/$LOC.html"
MAX=524288

exec 9>"$BASE/work/.lock"
flock -n 9 || { echo "publicacion en curso" >&2; exit 75; }

[ -f "$ORIGEN" ] || { echo "no existe $ORIGEN" >&2; exit 66; }
[ -f "$DIR/estado.json" ] || { echo "no existe estado.json" >&2; exit 66; }

FECHA="$(python3 -c "import json;print(json.load(open('$DIR/estado.json'))['fecha'])")"
ANIO="${FECHA%%-*}"; RESTO="${FECHA#*-}"; MES="${RESTO%%-*}"; DIA="${RESTO#*-}"

# --- validaciones antes de publicar nada ---
B="$(stat -c%s "$ORIGEN")"
[ "$B" -ge 500 ] || { echo "demasiado corto ($B B)" >&2; exit 65; }
[ "$B" -le "$MAX" ] || { echo "demasiado largo ($B B)" >&2; exit 65; }
head -c 100 "$ORIGEN" | tr 'A-Z' 'a-z' | grep -q '<!doctype html' \
  || { echo "no parece HTML" >&2; exit 65; }
if grep -qE '\{\{|\}\}|TODO|PLACEHOLDER' "$ORIGEN"; then
  echo "marcadores sin sustituir" >&2; exit 65
fi

# --- escritura atomica (mv en el mismo sistema de ficheros) ---
DEST="$DOCROOT/filonoticies-$LOC/$ANIO/$MES"
mkdir -p "$DEST"
cp -f "$ORIGEN" "$DEST/.$DIA.html.tmp"
chmod 644 "$DEST/.$DIA.html.tmp"
mv -f "$DEST/.$DIA.html.tmp" "$DEST/$DIA.html"

# --- indice de la ruta ---
python3 /etc/filosofadas/indice.py "$LOC"
python3 /etc/filosofadas/portada.py || echo "aviso: portada no regenerada" >&2

# --- historial git (nunca hace push) ---
if [ -d "$DOCROOT/.git" ]; then
  RUTAS=("filonoticies-$LOC" "filonoticies" "filonoticies.css")
  git -C "$DOCROOT" -c safe.directory="$DOCROOT" add -A -- "${RUTAS[@]}" 2>/dev/null || true
  git -C "$DOCROOT" -c safe.directory="$DOCROOT" \
      -c user.name="FiloNoticias" -c user.email="filonoticies@hugo.cat" \
      commit -m "publica $LOC $FECHA" --quiet 2>/dev/null || true
fi

echo "publicado $LOC $FECHA"
echo "  https://hugo.cat/filonoticies-$LOC/$ANIO/$MES/$DIA.html"
