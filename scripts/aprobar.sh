#!/usr/bin/env bash
# aprobar.sh <locale> <id> — aprueba y publica UNA version.
set -euo pipefail

LOC="${1:?falta locale}"; ID="${2:?falta id}"
case "$LOC" in ca|es|cost) ;; *) echo "locale invalido: $LOC" >&2; exit 64 ;; esac

DIR="/var/lib/filosofadas/pending/$ID"
[ -f "$DIR/estado.json" ] || { echo "no existe el borrador $ID" >&2; exit 66; }

# Validar estado y caducidad (y marcarlo) ANTES de publicar
python3 - "$DIR" "$LOC" <<'PY'
import datetime as dt, json, pathlib, sys
d, loc = pathlib.Path(sys.argv[1]), sys.argv[2]
est = json.load(open(d / "estado.json"))

if est["estado"] in ("rechazado", "archivado"):
    sys.exit(f"estado {est['estado']}: no se puede publicar")
if dt.datetime.fromisoformat(est["expira"]) < dt.datetime.now(dt.timezone.utc):
    sys.exit("caducado (>72 h): regenerar antes de publicar")
if loc in est.get("aprobados", []):
    sys.exit(f"{loc} ya estaba aprobado")

est.setdefault("aprobados", []).append(loc)
est["estado"] = "publicado" if len(set(est["aprobados"])) == 3 else "parcial"
json.dump(est, open(d / "estado.json", "w"), ensure_ascii=False, indent=2)
print(f"estado: {est['estado']} ({len(set(est['aprobados']))}/3)")
PY

/etc/filosofadas/publicar.sh "$LOC" "$ID"
