
# Instalación

## Ficheros systemd
Los ficheros de systemd/ debe habilitarse como:

Las unidades:

```# systemctl list-units 'filo*' --all
  UNIT                            LOAD   ACTIVE   SUB     DESCRIPTION
  filonoticias-acciones.service   loaded active   running Botones de aprobacion de FiloNoticias (solo 127.0.0.1)
  filonoticias-generar.service    loaded inactive dead    Genera el borrador diario de FiloNoticias
  filonoticias-limpieza.service   loaded inactive dead    Retencion de borradores de FiloNoticias
  filonoticias-vigilancia.service loaded inactive dead    Comprueba que hoy se haya generado el borrador
  filonoticias-generar.timer      loaded active   waiting Genera FiloNoticias cada dia a las 07:00
  filonoticias-limpieza.timer     loaded active   waiting Retencion de FiloNoticias (08:00)
  filonoticias-vigilancia.timer   loaded active   waiting Dead-man switch de FiloNoticias (09:00)
```
y los timers:

```
# systemctl list-timers 'filo*' --all
NEXT                        LEFT     LAST                        PASSED       UNIT                          ACTIVATES
Sat 2026-10-24 05:02:53 UTC 19h left Fri 2026-10-23 05:02:56 UTC 4h 38min ago filonoticias-generar.timer    filonoticias-generar.service
Sat 2026-10-24 06:00:00 UTC 20h left Fri 2026-10-23 06:00:10 UTC 3h 41min ago filonoticias-limpieza.timer   filonoticias-limpieza.service
Sat 2026-10-24 07:00:00 UTC 21h left Fri 2026-10-23 07:00:02 UTC 2h 41min ago filonoticias-vigilancia.timer filonoticias-vigilancia.service
```

## Ficheros de script

La lógica (scripts, `fuentes.txt`, `tonos/`) vive en este repo, en `/opt/filosofia-ia/scripts`.
Los ficheros `.sh` deben ser ejecutables.

## Directorios web

Los directorios servidos por Apache cuelgan de `/var/www.hugo.cat/filonoticies`
(ver los `Alias` en `/etc/apache2/sites-available/hugo.cat.conf`):

- `filonoticies/` portada
- `filonoticies-ca/`, `filonoticies-es/`, `filonoticies-cost/` publicaciones por idioma
- `o/` vistas previas de borradores
- `filonoticies.css` hoja de estilos

Los datos de trabajo (borradores, archivo, cola) siguen en `/var/lib/filosofadas`.

## Fichero de secretos

se espera un fichero /etc/filosofadas/env con la siguiente estructura:

```
MISTRAL_API_KEY=<tu-clave-mistral>
OPENWEBUI_API_KEY=<tu-clave-openwebui>
OPENWEBUI_URL=http://<ip-openwebui>:<puerto>
TOKEN_VISTA=<tu-token-vista>
BASE_VISTA=https://hugo.cat/o
CORREO_DESTINO=hugo@hugo.cat
REMITENTE=FiloNoticias <filosofadas@hugo.cat>
```

## Publicar cambios en GitHub

El remoto es `https://github.com/hugo-555-ai/filosofadas-ia` por HTTPS y el servidor
no guarda credenciales, así que cada push pide un token.

1. Trabaja siempre con el usuario `adminlechuga`, nunca como root. Si ejecutas git
   como root, deja `.git/config` y las refs con propietario root y `adminlechuga`
   ya no puede usar git. Se arregla con:
   ```
   chown -R adminlechuga:adminlechuga /opt/filosofia-ia/.git
   ```
2. Crea una rama, commitea y haz push de la rama:
   ```
   git checkout -b mi-cambio
   git add -A && git commit -m "Descripción del cambio"
   sudo -u adminlechuga git push -u origin mi-cambio
   ```
3. Cuando pida credenciales: *Username* `hugo-555-ai` y *Password* un token de GitHub
   (no la contraseña de la cuenta).
4. Fusiona con un Pull Request en GitHub (`https://github.com/hugo-555-ai/filosofadas-ia/pull/new/mi-cambio`)
   o en local y sube `main`:
   ```
   git checkout main
   git merge --no-ff mi-cambio
   sudo -u adminlechuga git push origin main
   ```
5. Borra la rama ya fusionada:
   ```
   sudo -u adminlechuga git push origin --delete mi-cambio
   git branch -d mi-cambio
   ```

### Generar el token

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
→ Generate new token:

- *Resource owner*: `hugo-555-ai`
- *Repository access*: Only select repositories → `filosofadas-ia`
- *Repository permissions*: `Contents: Read and write` (y `Pull requests: Read and write`
  si se van a abrir PRs)
- *Expiration*: la más corta que sirva (el token solo se muestra una vez).

Un 403 con el usuario correcto casi siempre es que al token le falta `Contents: Read and write`
o no incluye este repo. Revoca el token cuando termines.
