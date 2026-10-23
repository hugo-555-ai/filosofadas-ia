#!/usr/bin/env python3
"""portada.py — pagina fija /filonoticies/ con la ultima publicacion.

Muestra el dia mas reciente publicado, con tres pestanas de idioma (CA/ES/COST)
en la MISMA url, y un archivo de dias anteriores.

No duplica contenido: incrusta lo que ya hay publicado en las rutas por idioma.
"""
import html
import re
import sys
from pathlib import Path

DOCROOT = Path("/var/www.hugo.cat/html")
LOCALES = ("ca", "es", "cost")
IDIOMA  = {"ca": "ca", "es": "es", "cost": "es"}
NOMBRE  = {"ca": "FiloNotícies", "es": "FiloNoticias", "cost": "FiloNoticias — a lo bien"}
PESTANA = {"ca": "Català", "es": "Castellà", "cost": "Castellà costeño"}


def dias(loc):
    """Fechas publicadas, de mas reciente a mas antigua."""
    base = DOCROOT / f"filonoticies-{loc}"
    fuera = []
    for p in base.glob("*/*/*.html"):
        try:
            a, m, d = p.relative_to(base).parts
            fuera.append((f"{a}-{m}-{d[:-5]}", p))
        except Exception:
            continue
    fuera.sort(reverse=True)
    return fuera


def cuerpo_de(p):
    """El <main class='fn'> de una pagina ya publicada, sin su cabecera."""
    h = p.read_text(encoding="utf-8")
    m = re.search(r"<main class=\"fn\">(.*?)</main>", h, re.S)
    return m.group(1) if m else h


def main():
    todos = {l: dias(l) for l in LOCALES}
    disponibles = [l for l in LOCALES if todos[l]]
    if not disponibles:
        sys.exit("no hay ninguna publicacion todavia")

    ultimo = max(todos[l][0][0] for l in disponibles)
    anio, mes, dia = ultimo.split("-")

    pestanas, paneles = [], []
    for i, l in enumerate(LOCALES):
        activo = " activo" if l == disponibles[0] else ""
        pestanas.append(
            f'<a class="pt-pestana{activo}" href="#{l}">{PESTANA[l]}</a>')

    for l in LOCALES:
        f = DOCROOT / f"filonoticies-{l}/{anio}/{mes}/{dia}.html"
        if f.exists():
            contenido = cuerpo_de(f)
        else:
            contenido = (f'<p class="fn-aviso">Encara no hi ha publicació en '
                         f'{PESTANA[l]} per a aquest dia.</p>')
        paneles.append(f'<section class="pt-panel" id="{l}">{contenido}</section>')

    archivo = []
    for l in disponibles:
        enlaces = "".join(
            f'<li><a href="/filonoticies-{l}/{a}/{m}/{d}.html">{fecha}</a></li>'
            for fecha, p in todos[l][:15]
            for a, m, d in [p.relative_to(DOCROOT / f"filonoticies-{l}").parts])
        archivo.append(
            f'<section class="pt-panel" id="arch-{l}">'
            f'<ul class="fn-arxiu">{enlaces}</ul></section>')

    (DOCROOT / "filonoticies" / "index.html").write_text(f"""<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FiloNotícies</title>
<link rel="stylesheet" href="/filonoticies.css">
</head>
<body class="pt">
<main class="fn">
<header class="fn-capcalera">
<p class="fn-seccio">Reflexions filosòfiques sobre les notícies del dia anterior</p>
<p class="fn-banner">Text generat per IA · Sense revisió humana</p>
<h1 class="fn-data">FiloNotícies</h1>
</header>

<nav class="pt-pestanas">{"".join(pestanas)}</nav>
{"".join(paneles)}

<details class="pt-arxiu">
<summary>Dies anteriors</summary>
{"".join(archivo)}
</details>
</main>
</body>
</html>
""", encoding="utf-8")
    print(f"portada: {ultimo} ({len(disponibles)} idiomes, {sum(len(v) for v in todos.values())} dies)")


if __name__ == "__main__":
    main()
