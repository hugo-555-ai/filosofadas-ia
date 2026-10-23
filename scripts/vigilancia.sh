#!/usr/bin/env bash
# vigilancia.sh — dead-man switch: avisa si HOY no se ha generado el borrador.
# El generador nombra los borradores con la fecha de AYER (las noticias que usa),
# asi que aqui hay que buscar por esa misma fecha.
set -euo pipefail
BASE=/var/lib/filosofadas
AYER="$(TZ=Europe/Madrid date -d 'yesterday' +%Y%m%d)"

if compgen -G "$BASE/pending/${AYER}-*" > /dev/null; then
  echo "OK: existe borrador de hoy (noticias de $AYER)"
  exit 0
fi

MSG="FiloNoticias: NO se ha generado el borrador de hoy (noticias del $AYER).
Revisa: journalctl -u filonoticias-generar -n 50 --no-pager"

echo "$MSG" >&2
if [ -f /etc/msmtprc ] && command -v msmtp >/dev/null 2>&1; then
  DEST="$(awk -F= -v k=CORREO_DESTINO '$1==k{sub(/^[^=]*=/,"");print;exit}' /etc/filosofadas/env)"
  printf 'Subject: FiloNoticias - SIN borrador hoy\n\n%s\n' "$MSG" | msmtp -a dondominio "${DEST:-hugo@hugo.cat}"
fi
exit 1
