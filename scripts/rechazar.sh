#!/usr/bin/env bash
# rechazar.sh <id> — rechaza las TRES versiones y pide noticias nuevas.
set -euo pipefail

ID="${1:?falta id}"
DIR="/var/lib/filosofadas/pending/$ID"
[ -f "$DIR/estado.json" ] || { echo "no existe el borrador $ID" >&2; exit 66; }

echo "ATENCION: rechazar descarta las TRES versiones y pide otras noticias."
echo "Lo ya publicado (parcial) no se toca."
read -r -p "Escribe SI para confirmar: " r
[ "$r" = "SI" ] || { echo "cancelado"; exit 0; }

python3 - "$DIR" <<'PY'
import datetime as dt, json, pathlib, sys
d = pathlib.Path(sys.argv[1])
est = json.load(open(d / "estado.json"))
est["estado"] = "rechazado"
json.dump(est, open(d / "estado.json", "w"), ensure_ascii=False, indent=2)

n = json.load(open(d / "noticias.json"))
cola = d.parent.parent / "cola"
cola.mkdir(exist_ok=True)
(cola / f"{est['id']}.json").write_text(json.dumps({
    "fecha": est["fecha"],
    "rechazado": dt.datetime.now(dt.timezone.utc).isoformat(),
    "excluir": [x["titular"] for x in n["noticias"]],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"cola: {len(n['noticias'])} noticias a excluir")
PY

echo "rechazado. La proxima generacion excluira esas noticias."
