#!/usr/bin/env python3
"""
FiloNoticias — genera el borrador diario.

  1. Lee los RSS de /etc/filosofadas/fuentes.txt
  2. Filtra las noticias publicadas AYER (Europe/Madrid)
  3. Pide al modelo que elija las 3-4 con mas sustancia filosofica
  4. Genera tres versiones (ca / es / cost) con EL MISMO set de noticias
  5. Escribe pending/<id>/ y avisa por correo

La inferencia se hace en OpenWebUI (servidor casero) por el tunel WireGuard.
Este proceso NO tiene herramientas: solo HTTP y escritura de ficheros.
"""
import fcntl, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/etc/filosofadas")
import layout
import unicodedata

import feedparser

ETC  = Path("/etc/filosofadas")
BASE = Path("/var/lib/filosofadas")
TZ   = ZoneInfo("Europe/Madrid")
AYER = (datetime.now(TZ) - timedelta(days=1)).date()
FECHA = AYER.isoformat()
TONOS = ("ca", "es", "cost")


# ---------- utilidades ----------

def log(msg):
    print(f"[{datetime.now(TZ):%H:%M:%S}] {msg}", flush=True)


def entorno():
    d = {}
    for linea in (ETC / "env").read_text().splitlines():
        if "=" in linea and not linea.strip().startswith("#"):
            k, v = linea.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


class TextoPlano(HTMLParser):
    """Extrae texto de un HTML, descartando scripts y estilos."""
    def __init__(self):
        super().__init__()
        self.trozos, self._saltar = [], False

    def handle_starttag(self, tag, _):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._saltar = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._saltar = False

    def handle_data(self, datos):
        if not self._saltar and datos.strip():
            self.trozos.append(datos.strip())

    def texto(self):
        return " ".join(self.trozos)


def descargar(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "FiloNoticias/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def texto_de(url):
    """Texto completo de un articulo. Devuelve '' si no se puede leer."""
    try:
        bruto = descargar(url, timeout=25)
    except Exception as e:
        log(f"  no se pudo leer {url}: {e}")
        return ""
    p = TextoPlano()
    p.feed(bruto)
    return p.texto()[:12000]


# ---------- OpenWebUI ----------

def preguntar(cfg, mensaje, intentos=3, max_tokens=4000):
    """Una llamada a OpenWebUI. Reintentos con espera creciente."""
    cuerpo = json.dumps({
        "model": "filonoticias",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": mensaje}],
    }).encode()
    for i in range(intentos):
        try:
            req = urllib.request.Request(
                cfg["OPENWEBUI_URL"].rstrip("/") + "/api/chat/completions",
                data=cuerpo,
                headers={"Authorization": f"Bearer {cfg['OPENWEBUI_API_KEY']}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"]
        except Exception as e:
            if i == intentos - 1:
                raise
            log(f"  fallo ({e}); reintento {i + 2}/{intentos}")
            time.sleep(20 * (i + 1))    # 20s, 40s


def solo_json(texto):
    """Extrae el primer objeto JSON del texto del modelo."""
    i, j = texto.find("{"), texto.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("el modelo no devolvio JSON")
    return json.loads(texto[i:j + 1])


# ---------- pasos ----------


def titulares_excluidos():
    """Titulares de la cola de rechazo, para no volver a elegirlos."""
    fuera = set()
    for f in (BASE / "cola").glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            fuera.update(d.get("excluir", []))
        except Exception:
            continue
    return fuera

def recoger_noticias():
    """Lee los feeds y devuelve las entradas de AYER."""
    urls = [l.strip() for l in (ETC / "fuentes.txt").read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]
    ayer, encontradas, vistos = [], [], set()
    for u in urls:
        try:
            f = feedparser.parse(u)
        except Exception as e:
            log(f"feed con problemas {u}: {e}")
            continue
        for e in f.entries:
            # fecha de publicacion
            t = e.get("published_parsed") or e.get("updated_parsed")
            if not t:
                continue
            fecha = datetime(*t[:6], tzinfo=timezone.utc).astimezone(TZ).date()
            if fecha != AYER:
                continue
            titular = (e.get("title") or "").strip()
            enlace = (e.get("link") or "").strip()
            if not titular or not enlace or titular in vistos:
                continue
            vistos.add(titular)
            resumen = re.sub(r"<[^>]+>", "", e.get("summary") or "").strip()
            encontradas.append({
                "titular": titular,
                "medio": f.feed.get("title", u),
                "url": enlace,
                "resumen": resumen[:400],
                "fecha_pub": str(fecha),
                "via": "published" if e.get("published_parsed") else "updated",
            })
    log(f"{len(encontradas)} noticias de {FECHA} en {len(urls)} fuentes")
    return encontradas


def elegir(cfg, candidatas, excluidos=None):
    """Pide al modelo que elija las 3-4 con mas sustancia filosofica."""
    listado = "\n".join(
        f'{i}. [{n["medio"]}] {n["titular"]}\n   {n["resumen"][:200]}\n   {n["url"]}'
        for i, n in enumerate(candidatas))
    aviso = ""
    if excluidos:
        aviso = ("NO elijas ninguna de estas, ya se usaron y se rechazaron:\n"
                 + "\n".join(f"- {t}" for t in excluidos) + "\n\n")
    respuesta = preguntar(cfg, (
        f"Estas son las noticias publicadas el {FECHA} (Europe/Madrid).\n\n"
        f"{aviso}"
        f"{listado}\n\n"
        "Aplica el PASO 0 (filtro de entrada) y el PASO 1 de tu PROMPT MAESTRO.\n"
        "Elige las 3-4 con MAS sustancia filosofica genuina. Descarta sucesos, "
        "deportes, cotizaciones y lo puramente factual. No elijas dos del mismo asunto.\n\n"
        "Devuelve SOLO un JSON, sin texto alrededor, con este formato:\n"
        '{"noticias":[{"titular":"...","medio":"...","url":"...","linea":"resumen de una linea"}]}'
    ), max_tokens=1500)
    datos = solo_json(respuesta)
    return datos["noticias"]


def traducir_titulares(cfg, noticias):
    """Idioma de cada titular y su traduccion al catalan y al castellano.

    Se calcula UNA vez y se guarda en noticias.json: asi la traduccion es un dato
    estructurado (como la fecha), no algo que el modelo deba recordar al redactar.
    """
    listado = json.dumps([n["titular"] for n in noticias], ensure_ascii=False)
    respuesta = preguntar(cfg, (
        "Para cada titular de esta lista, indica en que idioma esta y traducelo.\n\n"
        f"{listado}\n\n"
        "Reglas:\n"
        "- idioma: codigo ISO 639-1 (es, ca, en, fr, ...).\n"
        "- ca: el titular en catalan. Si ya esta en catalan, repitelo tal cual.\n"
        "- es: el titular en castellano. Si ya esta en castellano, repitelo tal cual.\n"
        "- Conserva nombres propios y siglas. No resumas, no interpretes ni anadas datos.\n\n"
        'Devuelve SOLO un JSON, un objeto por titular y en el mismo orden:\n'
        '{"titulares":[{"idioma":"es","ca":"...","es":"..."}]}'
    ), max_tokens=1500)
    return solo_json(respuesta)["titulares"]


RE_MARCA = re.compile(r"\[FICHA\s*([^\]]*)\]", re.I)

STOP = {"esta", "este", "esto", "esos", "esas", "para", "pero", "como", "cómo",
        "cuando", "mientras", "después", "tras", "entre", "sobre", "desde",
        "hacia", "según", "ante", "unos", "unas"}


def _palabras(t):
    """Palabras clave de un titular: terminos largos + NOMBRES PROPIOS.

    Incluir los nombres propios es lo que permite casar titulares parafraseados
    (p. ej. "Gaza bajo el silencio" con una ficha que dice "Gaza mientras...").
    """
    t = t or ""
    largas = [w.lower() for w in re.findall(r"\w{6,}", t)]
    propias = [w.lower() for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]{2,}\b", t)
               if w.lower() not in STOP]
    return list(set(largas) | set(propias))


def _norm(t):
    """Titular normalizado para comparar: sin acentos, sin puntuacion, minusculas."""
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def componer(texto, noticias):
    """Fichas indexadas por noticia.

    1) Marcador [FICHA <titular>]: el propio modelo dice a que noticia pertenece
       copiando el titular. La coincidencia es EXACTA (normalizada) y por tanto
       independiente del orden. Se prefiere esto a numeros porque el modelo
       numera mal: se ha comprobado que produce fichas cruzadas.
    2) Sin marcador util, emparejamiento por palabras clave (incluye nombres propios).
    3) Sin coincidencia clara, hueco (dispara el reintento) en vez de atribuir mal.
    """
    fichas = layout.fichas_de(texto)
    n = len(noticias)
    resultado = [None] * n
    usadas = set()
    titulos = [[_norm(x.get("titular", "")), _norm(x.get("titular_ca", ""))]
               for x in noticias]

    for j, f in enumerate(fichas):
        m = RE_MARCA.search(f)
        if not m:
            continue
        p = _norm(m.group(1))
        if len(p) < 8:
            continue
        for i, ts in enumerate(titulos):
            if resultado[i] is not None:
                continue
            if any(t and (p == t or p in t or t in p) for t in ts):
                resultado[i] = fichas[j]
                usadas.add(j)
                break

    for i, noti in enumerate(noticias):
        if resultado[i] is not None:
            continue
        claves = (set(_palabras(noti.get("titular", ""))) |
                  set(_palabras(noti.get("titular_ca", ""))))
        mejor, puntos = None, 0
        for j, f in enumerate(fichas):
            if j in usadas:
                continue
            c = sum(1 for k in claves if k in f.lower())
            if c > puntos:
                mejor, puntos = j, c
        if mejor is not None and puntos > 0:
            resultado[i] = fichas[mejor]
            usadas.add(mejor)

    return resultado


def _faltantes(texto, noticias):
    return [i for i, f in enumerate(componer(texto, noticias)) if f is None]


def redactar(cfg, noticias, tono, solo_faltantes=False, ya_incluidas=""):
    """Genera una version en el tono indicado.

    Con solo_faltantes=True pide UNICAMENTE las fichas ausentes, para el reintento.
    """
    directrices = (ETC / "tonos" / f"{tono}.md").read_text()

    if solo_faltantes:
        idx = _faltantes(ya_incluidas, noticias)
        if not idx:
            return ""
        sub = [{"n": i + 1, **noticias[i]} for i in idx]
        setn = json.dumps({"fecha": FECHA, "noticias": sub}, ensure_ascii=False)
        return preguntar(cfg, (
            f"Faltan fichas de este set. Escribe la ficha del PROMPT MAESTRO "
            f"(pasos 0 a 4) SOLO para estas {len(sub)} noticias:\n{setn}\n\n"
            f"Empieza cada ficha con una linea exacta [FICHA <titular>], donde "
            f"<titular> es el titular COPIADO TAL CUAL de la noticia.\n\n"
            f"Directrices de tono y idioma:\n{directrices}\n\n"
            f"No repitas fichas de otras noticias."
        ), max_tokens=8000)

    setn = json.dumps({"fecha": FECHA, "noticias": noticias}, ensure_ascii=False)
    return preguntar(cfg, (
        f"Noticias ya elegidas (NO cambies la seleccion):\n{setn}\n\n"
        f"Aplica el PROMPT MAESTRO completo (pasos 0 a 4) a estas noticias, "
        f"UNA FICHA POR NOTICIA. "
        f"Empieza cada ficha con una linea exacta de la forma "
        f"[FICHA <titular>], donde <titular> es el titular de esa noticia "
        f"COPIADO TAL CUAL de la lista, sin traducir ni resumir.\n\n"
        f"Directrices de tono y idioma:\n{directrices}"
    ), max_tokens=8000)


def main():
    BASE.joinpath("work").mkdir(parents=True, exist_ok=True)
    os.chdir(BASE)

    lock = open(BASE / "work" / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("Ya hay una ejecucion en curso")

    cfg = entorno()
    for clave in ("OPENWEBUI_API_KEY", "OPENWEBUI_URL"):
        if clave not in cfg:
            sys.exit(f"Falta {clave} en /etc/filosofadas/env")

    # Idempotencia: si ya hay borrador de hoy, no repetir
    for d in (BASE / "pending").glob(f"{FECHA.replace('-', '')}-*"):
        est = d / "estado.json"
        estado = None
        if est.exists():
            try:
                estado = json.loads(est.read_text(encoding="utf-8")).get("estado")
            except Exception:
                estado = None
        if estado in ("rechazado", "archivado"):
            continue          # un rechazo SI debe permitir regenerar
        sys.exit(f"Ya existe el borrador {d.name} ({estado}): nada que hacer")

    noticias = recoger_noticias()
    if len(noticias) < 3:
        sys.exit(f"Solo {len(noticias)} noticias de ayer: insuficiente para generar")

    elegidas = elegir(cfg, noticias, titulares_excluidos())

    # Idioma de cada titular y traducciones (dato estructurado, no depende del modelo)
    try:
        trad = traducir_titulares(cfg, elegidas)
        if len(trad) == len(elegidas):
            for n, t in zip(elegidas, trad):
                n["idioma"]     = (t.get("idioma") or "").strip().lower()
                n["titular_ca"] = (t.get("ca") or "").strip()
                n["titular_es"] = (t.get("es") or "").strip()
            log("idiomas: " + ", ".join(n.get("idioma") or "?" for n in elegidas))
        else:
            log(f"aviso: {len(trad)} traducciones para {len(elegidas)} noticias; se ignoran")
    except Exception as e:
        log(f"aviso: sin traducciones ({e})")
    log(f"elegidas {len(elegidas)}: " + " | ".join(n["titular"][:40] for n in elegidas))

    id_ = f"{FECHA.replace('-', '')}-{datetime.now(TZ):%H%M%S}"
    destino = BASE / "pending" / id_
    destino.mkdir(parents=True)

    for tono in TONOS:
        esperadas = len(elegidas)
        crudo = redactar(cfg, elegidas, tono)
        fichas = componer(crudo, elegidas)
        dudosas = [i for i, f in enumerate(fichas)
                   if f and not any(k in f.lower()
                                    for k in (set(_palabras(elegidas[i].get("titular", ""))) |
                                              set(_palabras(elegidas[i].get("titular_ca", "")))))]
        if dudosas:
            log(f"  AVISO {tono}: fichas sin coincidencia con su titular: {dudosas}")

        # Reintento: solo las fichas ausentes, hasta 2 veces
        for intento in range(2):
            faltan = [i for i, f in enumerate(fichas) if f is None]
            if not faltan:
                break
            log(f"  {tono}: faltan {len(faltan)} fichas; reintento {intento + 1}")
            extra = redactar(cfg, elegidas, tono, solo_faltantes=True,
                             ya_incluidas=crudo)
            if extra.strip():
                crudo = crudo + "\n\n" + extra
                fichas = componer(crudo, elegidas)

        huecos = [i for i, f in enumerate(fichas) if f is None]
        if huecos:
            log(f"  AVISO {tono}: sin ficha para las noticias {huecos}")
        texto_final = "\n\n".join(f for f in fichas if f)
        (destino / f"{tono}.html").write_text(
            layout.render(tono, FECHA, texto_final, elegidas), encoding="utf-8")
        (destino / f"crudo_{tono}.txt").write_text(texto_final, encoding="utf-8")
        log(f"  {tono}: {len(texto_final)} caracteres, "
            f"{esperadas - len(huecos)}/{esperadas} fichas")

    (destino / "noticias.json").write_text(
        json.dumps({"fecha": FECHA, "noticias": elegidas},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (destino / "estado.json").write_text(json.dumps({
        "id": id_, "fecha": FECHA, "estado": "pendiente",
        "expira": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
        "aprobados": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"borrador {id_} listo")
    os.execv("/etc/filosofadas/avisar.sh", ["avisar.sh", id_])


if __name__ == "__main__":
    main()
