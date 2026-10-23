#!/usr/bin/env bash
# limpiar.sh — archiva borradores viejos y borra vistas previas caducadas.
set -euo pipefail
BASE=/var/lib/filosofadas
DOCROOT=/var/www.hugo.cat/filonoticies
DIAS=90

# 1) pending -> archivo si tiene mas de DIAS
find "$BASE/pending" -mindepth 1 -maxdepth 1 -type d -mtime +$DIAS -print0 |
while IFS= read -r -d '' d; do
  ID="$(basename "$d")"
  if [ -f "$d/estado.json" ]; then
    E="$(python3 -c "import json;print(json.load(open('$d/estado.json'))['estado'])" 2>/dev/null || echo '?')"
  else
    E="?"
  fi
  case "$E" in
    publicado|parcial) ;;   # lo ya publicado se conserva en el archivo
    *) rm -rf "$d"; echo "borrado pendiente $ID ($E)"; continue ;;
  esac
  mv "$d" "$BASE/archivo/$ID" && gzip -f "$BASE/archivo/$ID"/*.html 2>/dev/null || true
  echo "archivado $ID ($E)"
done

# 2) vistas previas -> borrar si el borrador ya no esta pendiente
for dir in "$DOCROOT"/o/*/*/; do
  [ -d "$dir" ] || continue
  ID="$(basename "$dir")"
  if [ ! -d "$BASE/pending/$ID" ]; then
    rm -rf "$dir"; echo "vista previa borrada $ID"
  fi
done

# 3) colas de rechazo antiguas
find "$BASE/cola" -name '*.json' -mtime +30 -delete 2>/dev/null || true
