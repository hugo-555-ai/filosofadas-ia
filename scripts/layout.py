#!/usr/bin/env python3
"""layout.py — convierte la ficha del modelo en HTML5 completo.

El titulo, las fuentes y el aviso de IA los genera ESTE fichero, no el modelo:
asi la fecha y las atribuciones son siempre correctas.
"""

import html
import re

NOMBRE = {"ca": "FiloNotícies", "es": "FiloNoticias", "cost": "FiloNoticias — a lo bien"}
IDIOMA = {"ca": "ca", "es": "es", "cost": "es"}
TIT_FUENTES = {"ca": "Fonts", "es": "Fuentes", "cost": "Fuentes"}

AVISO = {
    "ca": ("Aquest text l'ha generat un sistema d'intel\u00b7lig\u00e8ncia artificial a partir "
           "de notícies publicades el {f}. No l'ha revisat cap persona abans de publicar-se. "
           "No és periodisme: és una reflexió filosòfica. Les fonts originals estan "
           "enllaçades més amunt."),
    "es": ("Este texto lo ha generado un sistema de inteligencia artificial a partir de "
           "noticias publicadas el {f}. No lo ha revisado ninguna persona antes de "
           "publicarse. No es periodismo: es una reflexión filosófica. Las fuentes "
           "originales están enlazadas más arriba."),
}
AVISO["cost"] = AVISO["es"]

# Banner superior: visible pero discreto, en las tres versiones
BANNER = {
    "ca": "Text generat per IA \u00b7 Sense revisió humana",
    "es": "Texto generado por IA \u00b7 Sin revisión humana",
}
BANNER["cost"] = BANNER["es"]

NOTA_TONO = {"cost": ("El tono guasón es una elección editorial: el análisis es idéntico al "
                      "de las otras dos versiones.")}

CAMPOS = {
    "NOTICIA":                ("fn-noticia",  "p",          "Noticia"),
    "NOTÍCIA":                ("fn-noticia",  "p",          "Notícia"),
    "LO QUE PARECE":          ("fn-parece",   "p",          "Lo que parece"),
    "EL QUE SEMBLA":          ("fn-parece",   "p",          "El que sembla"),
    "LA PREGUNTA REAL":       ("fn-pregunta", "blockquote", "La pregunta real"),
    "PUENTE DIVULGATIVO":     ("fn-puente",   "p",          "Puente divulgativo"),
    "POR QUÉ NO HABLAMOS DE": ("fn-descarte", "p",          "Por qué no hablamos de"),
    "PER QUÈ NO PARLEM DE":   ("fn-descarte", "p",          "Per què no parlem de"),
    "EN SÍNTESIS":            ("fn-sintesis", "p",          "En síntesis"),
    "EN SÍNTESI":             ("fn-sintesis", "p",          "En síntesi"),
}

RE_CAMPO = re.compile(r"^([A-ZÁÉÍÓÚÀÈÉÍÒÓÇÜ][A-ZÁÉÍÓÚÀÈÉÍÒÓÇÜ \t]{2,}):\s*(.*)$")
RE_FILOSOFO = re.compile(r"^([^.]{2,60}?)\s+→\s+(.*)$")
RE_MARCA = re.compile(r'^\[FICHA\s*\d*\]$', re.I)
RE_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
RE_INICIO = r"^\s*(?:NOTICIA|NOTÍCIA):"


def _enr(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return t


def _parsear(ficha):
    entradas, kind, label, buf = [], None, None, []

    def emitir():
        if kind:
            entradas.append((kind, label, " ".join(buf).strip()))

    for cruda in ficha.splitlines():
        s = cruda.strip()
        if not s:
            continue
        if RE_MARCA.match(s):
            continue
        m = RE_CAMPO.match(s)
        f = None if m else RE_FILOSOFO.match(s)
        if m:
            emitir()
            kind, label, buf = "campo", m.group(1).strip(), [m.group(2)]
        elif f:
            emitir()
            kind, label, buf = "filosofo", f.group(1).strip(), [f.group(2)]
        else:
            buf.append(s)
    emitir()
    return entradas


def _ficha_html(entradas):
    trozos, i = [], 0
    while i < len(entradas):
        kind, label, texto = entradas[i]
        if kind == "filosofo":
            filas = []
            while i < len(entradas) and entradas[i][0] == "filosofo":
                _, nom, txt = entradas[i]
                filas.append(f'<li><span class="fn-nombre">{_enr(nom)}</span> '
                             f'<span class="fn-flecha">&#8594;</span> {_enr(txt)}</li>')
                i += 1
            trozos.append('<ul class="fn-filosofos">' + "".join(filas) + "</ul>")
            continue
        clase, tag, etiqueta = CAMPOS.get(label.upper(), ("fn-campo", "p", label))
        cuerpo = _enr(texto)
        env = "blockquote" if tag == "blockquote" else "div"
        trozos.append(f'<{env} class="fn-campo {clase}">'
                      f'<span class="fn-etiqueta">{etiqueta}</span><p>{cuerpo}</p></{env}>')
        i += 1
    return "\n".join(trozos)


def titular_de(n, locale):
    """Titular para una version concreta.

    Regla: se muestra SIEMPRE el titular original en su idioma, y se anade la
    traduccion entre parentesis SOLO si el original esta en otro idioma distinto
    al de la pagina. Si coinciden, no se repite.
    """
    original = (n.get("titular") or "").strip()
    idioma = (n.get("idioma") or "").strip().lower()
    if locale == "ca":
        traduccion = (n.get("titular_ca") or "").strip()
        destino = "ca"
    else:
        traduccion = (n.get("titular_es") or "").strip()
        destino = "es"
    if not traduccion or not idioma or idioma == destino:
        return original, ""
    return original, traduccion


def fichas_de(texto):
    """Fichas que render producira. Se usa tambien para VALIDAR que el numero
    de fichas coincide con el de noticias (deteccion de contenido incompleto)."""
    fichas = RE_FENCE.findall(texto)
    if not fichas:
        partes = re.split(r"(?=(?:NOTICIA|NOTÍCIA):)", texto)
        fichas = [x for x in partes if re.match(RE_INICIO, x)]
    return fichas


def render(locale, fecha, texto, noticias):
    locale = locale if locale in NOMBRE else "es"

    fichas = RE_FENCE.findall(texto)
    if not fichas:
        partes = re.split(r"(?=(?:NOTICIA|NOTÍCIA):)", texto)
        fichas = [p for p in partes if re.match(RE_INICIO, p)]

    items = []
    for i, ficha in enumerate(fichas):
        n = noticias[i] if i < len(noticias) else {}
        orig, trad = titular_de(n, locale)
        _trad_html = (f' <span class="fn-trad">({_enr(trad)})</span>' if trad else "")
        url = html.escape(n.get("url", ""), quote=True)
        medio = html.escape(n.get("medio", ""))
        fuente = f'<a href="{url}">{medio}</a>' if url else medio
        items.append(
            '<article class="fn-item">'
            f'<h2 class="fn-titular">{_enr(orig)}{_trad_html}</h2>'
            f'<p class="fn-font">{fuente}</p>'
            f'{_ficha_html(_parsear(ficha))}'
            "</article>")

    fuentes = "".join(
        f'<li><a href="{html.escape(n.get("url", ""), quote=True)}">{html.escape(n.get("medio", ""))}</a>'
        f' — {html.escape(n.get("titular", ""))}</li>' for n in noticias)

    titulo = f"{NOMBRE[locale]} — {fecha}"
    nota = f'<p class="fn-nota-tono">{NOTA_TONO[locale]}</p>' if locale in NOTA_TONO else ""

    return f"""<!doctype html>
<html lang="{IDIOMA[locale]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<link rel="stylesheet" href="/filonoticies.css">
</head>
<body>
<main class="fn">
<header class="fn-capcalera">
<p class="fn-seccio">{html.escape(NOMBRE[locale])}</p>
<h1 class="fn-data">{fecha}</h1>
</header>
<p class="fn-banner">{html.escape(BANNER[locale])}</p>
{"".join(items)}
<footer class="fn-peu">
<h2 class="fn-peu-titulo">{TIT_FUENTES[locale]}</h2>
<ul class="fn-llista-fonts">{fuentes}</ul>
<p class="fn-aviso">{AVISO[locale].format(f=fecha)}</p>
{nota}
<p class="fn-autoria">Hugo Ballesteros i Mañes</p>
</footer>
</main>
</body>
</html>
"""
