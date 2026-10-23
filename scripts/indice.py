#!/usr/bin/env python3
"""indice.py <locale> — regenera el indice (archivo de dias) de una ruta."""
import html, sys
from pathlib import Path

DOCROOT = Path("/var/www.hugo.cat/filonoticies")
NOMBRE = {"ca": "FiloNotícies", "es": "FiloNoticias", "cost": "FiloNoticias — a lo bien"}
IDIOMA = {"ca": "ca", "es": "es", "cost": "es"}

DESCRIP = {
    "ca": ("FiloNotícies és un experiment: un sistema d'intel\u00b7lig\u00e8ncia artificial "
           "llegeix les notícies del dia anterior i en fa una reflexió filosòfica. "
           "L'objectiu és acostar la filosofia a persones que no hi tenen formació "
           "específica i mostrar, de passada, com es pot fer servir la IA per a una "
           "tasca creativa amb criteri."),
    "es": ("FiloNoticias es un experimento: un sistema de inteligencia artificial lee las "
           "noticias del día anterior y hace una reflexión filosófica. El objetivo es "
           "acercar la filosofía a personas sin formación específica y mostrar, de paso, "
           "cómo puede usarse la IA para una tarea creativa con criterio."),
}
DESCRIP["cost"] = (DESCRIP["es"] +
                   " Eso sí: la guasa va en cómo se cuenta, no en lo que se piensa.")


def main(loc):
    if loc not in NOMBRE:
        sys.exit(f"locale invalido: {loc}")
    base = DOCROOT / f"filonoticies-{loc}"

    dias = []
    for p in base.glob("*/*/*.html"):
        partes = p.relative_to(base).parts          # (anio, mes, "dia.html")
        try:
            dias.append((f"{partes[0]}-{partes[1]}-{partes[2][:-5]}", p))
        except Exception:
            continue
    dias.sort(reverse=True)

    filas = "".join(
        f'<li><a href="{a[0]}/{a[1]}/{a[2]}.html">{f}</a></li>'
        for f, p in dias
        for a in [(p.relative_to(base).parts[0], p.relative_to(base).parts[1],
                   p.relative_to(base).parts[2][:-5])])

    (base / "index.html").write_text(f"""<!doctype html>
<html lang="{IDIOMA[loc]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(NOMBRE[loc])}</title>
<link rel="stylesheet" href="/filonoticies.css">
</head>
<body><main class="fn">
<header class="fn-capcalera">
<p class="fn-seccio">Arxiu</p>
<h1 class="fn-data">{html.escape(NOMBRE[loc])}</h1>
</header>
<p class="fn-descr">{html.escape(DESCRIP[loc])}</p>
<ul class="fn-arxiu">{filas}</ul>
<p class="fn-aviso">Reflexions filosofiques generades amb IA a partir de noticies.
No les ha revisat cap persona abans de publicar-se.</p>
</main></body></html>
""", encoding="utf-8")
    print(f"indice {loc}: {len(dias)} dias")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ca")
