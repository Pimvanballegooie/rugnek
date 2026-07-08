#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync protocollen vanuit Google Docs — Rug Nek Netwerk (rugnek.net)

Werking:
1. Leest protocollen-config.json:
   {
     "protocollen": [
       {
         "id": "lage-rugpijn",
         "naam": "Lage rugpijn",
         "zone": "lumbosacraal",          <- cervicaal | thoracaal | lumbosacraal | algemeen
         "niveaus": {
           "makkelijk": "<GoogleDocID>",   <- patiëntversie
           "complex":   "<GoogleDocID>"    <- therapeutversie
         }
       }
     ]
   }
2. Haalt elke Google Doc op via de publieke exportlink (doc moet op
   'Iedereen met de link kan bekijken' staan — geen API-key nodig).
3. Zet de tekst (markdown of platte tekst) om naar nette HTML.
4. Genereert per protocol: protocollen/<id>-makkelijk.html en
   protocollen/<id>-complex.html, plus protocollen.html (overzicht)
   en sitemap.xml.

Draait in GitHub Actions (zie .github/workflows/sync.yml) — alleen
Python-standaardbibliotheek, geen pip-installaties nodig.
"""

import json
import re
import html
import sys
import urllib.request
from datetime import date
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# SITE-INSTELLINGEN — Rug Nek Netwerk
# ══════════════════════════════════════════════════════════════════
SITE_URL     = "https://rugnek.net"
SITE_NAAM    = "Rug Nek Netwerk"
LOGO_BESTAND = "rugnek_logo.png"

KLEUR_TEAL    = "#1BA098"
KLEUR_TEAL_L  = "#E6F5F4"
KLEUR_TEAL_D  = "#14807A"
KLEUR_NAVY    = "#22384A"
KLEUR_NAVY_D  = "#16242F"

# De drie domeinen + netwerkbrede zone (zelfde indeling als index.html)
ZONES = {
    "cervicaal":    "Nek & hoofd",
    "thoracaal":    "Borstwervelkolom & ribben",
    "lumbosacraal": "Lage rug & SI-gewricht",
    "algemeen":     "Voor elk gebied",
}
ZONE_ICONS = {
    "cervicaal": "💆",
    "thoracaal": "🫁",
    "lumbosacraal": "🔻",
    "algemeen": "🏥",
}
ZONE_KLEUREN = {
    "cervicaal":    "#1BA098",
    "thoracaal":    "#6ABF4B",
    "lumbosacraal": "#2E7DD1",
    "algemeen":     "#F5A623",
}

CONFIG_BESTAND = "protocollen-config.json"
OUTPUT_MAP     = Path("protocollen")


# ══════════════════════════════════════════════════════════════════
# GOOGLE DOC OPHALEN (publieke exportlink, geen API-key)
# ══════════════════════════════════════════════════════════════════
def haal_doc_tekst(doc_id: str) -> str | None:
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RugNekNetwerk-Sync/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tekst = resp.read().decode("utf-8", errors="replace")
        # Google zet soms een BOM voor de tekst
        return tekst.lstrip("\ufeff").strip()
    except Exception as e:
        print(f"  ⚠️  Doc {doc_id} niet opgehaald: {e}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════
# MARKDOWN → HTML
# ══════════════════════════════════════════════════════════════════
def is_markdown(tekst: str) -> bool:
    """Minimaal 2 markdown-signalen = markdown behandelen."""
    signalen = 0
    if re.search(r"^#{1,4}\s+\S", tekst, re.M): signalen += 1
    if re.search(r"^[-*]\s+\S", tekst, re.M):   signalen += 1
    if re.search(r"^\d+\.\s+\S", tekst, re.M):  signalen += 1
    if re.search(r"\*\*[^*\n]+\*\*", tekst):     signalen += 1
    if re.search(r"^---\s*$", tekst, re.M):     signalen += 1
    return signalen >= 2


def inline_md(t: str) -> str:
    """Inline markdown binnen een al ge-escapete regel."""
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    return t


def markdown_naar_html(tekst: str) -> str:
    regels = tekst.split("\n")
    out, i = [], 0
    in_ul, in_ol = False, False

    def sluit_lijsten():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    while i < len(regels):
        raw = regels[i].rstrip()
        regel = html.escape(raw, quote=False)

        if not raw.strip():
            sluit_lijsten()
            i += 1
            continue

        # Scheidingslijn
        if re.match(r"^---+\s*$", raw):
            sluit_lijsten()
            out.append('<hr class="scheiding">')
            i += 1
            continue

        # Koppen
        m = re.match(r"^(#{1,4})\s+(.*)$", raw)
        if m:
            sluit_lijsten()
            niveau = min(len(m.group(1)) + 1, 5)   # doc-# wordt h2, ## wordt h3...
            inhoud = inline_md(html.escape(m.group(2), quote=False))
            out.append(f"<h{niveau}>{inhoud}</h{niveau}>")
            i += 1
            continue

        # Ongeordende lijst
        m = re.match(r"^[-*]\s+(.*)$", raw)
        if m:
            if in_ol: out.append("</ol>"); in_ol = False
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline_md(html.escape(m.group(1), quote=False))}</li>")
            i += 1
            continue

        # Geordende lijst
        m = re.match(r"^\d+\.\s+(.*)$", raw)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            if not in_ol: out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline_md(html.escape(m.group(1), quote=False))}</li>")
            i += 1
            continue

        # Gewone alinea — opeenvolgende regels samenvoegen
        sluit_lijsten()
        alinea = [regel]
        while i + 1 < len(regels) and regels[i+1].strip() \
              and not re.match(r"^(#{1,4}\s|[-*]\s|\d+\.\s|---)", regels[i+1]):
            i += 1
            alinea.append(html.escape(regels[i].rstrip(), quote=False))
        out.append(f"<p>{inline_md(' '.join(alinea))}</p>")
        i += 1

    sluit_lijsten()
    return "\n".join(out)


def platte_tekst_naar_html(tekst: str) -> str:
    blokken = re.split(r"\n\s*\n", tekst)
    out = []
    for blok in blokken:
        blok = blok.strip()
        if not blok:
            continue
        # Korte regel zonder leesteken aan het eind → waarschijnlijk een kop
        if len(blok) < 70 and "\n" not in blok and not blok.endswith((".", ":", ";", "?", "!")):
            out.append(f"<h2>{html.escape(blok, quote=False)}</h2>")
        else:
            regels = " ".join(r.strip() for r in blok.split("\n"))
            out.append(f"<p>{html.escape(regels, quote=False)}</p>")
    return "\n".join(out)


def naar_html(tekst: str) -> str:
    return markdown_naar_html(tekst) if is_markdown(tekst) else platte_tekst_naar_html(tekst)


# ══════════════════════════════════════════════════════════════════
# GEDEELDE PAGINA-ONDERDELEN
# ══════════════════════════════════════════════════════════════════
def basis_css() -> str:
    return f"""
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-regular.woff2') format('woff2'); font-weight: 400; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-600.woff2') format('woff2'); font-weight: 600; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-700.woff2') format('woff2'); font-weight: 700; font-display: swap; }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --teal: {KLEUR_TEAL}; --teal-light: {KLEUR_TEAL_L}; --teal-dark: {KLEUR_TEAL_D};
      --navy: {KLEUR_NAVY}; --navy-dark: {KLEUR_NAVY_D};
      --grey-bg: #F8F9FA; --grey-border: #E8ECF0;
      --text: {KLEUR_NAVY}; --text-muted: #75828E; --white: #FFFFFF;
    }}
    body {{ font-family: 'Inter', sans-serif; font-size: 16px; color: var(--text); background: var(--white); line-height: 1.7; }}
    header {{ background: var(--white); border-bottom: 1px solid var(--grey-border); position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    .header-inner {{ max-width: 1100px; margin: 0 auto; padding: 0 clamp(1rem,4vw,2rem); display: flex; align-items: center; justify-content: space-between; height: 72px; gap: 16px; }}
    .logo {{ display: flex; align-items: center; gap: 12px; text-decoration: none; }}
    .logo img {{ height: 44px; width: 44px; object-fit: contain; }}
    .logo-text {{ font-weight: 700; font-size: 0.95rem; color: var(--navy); }}
    .logo-text span {{ color: var(--teal); }}
    .terug-link {{ font-size: 0.85rem; font-weight: 600; color: var(--teal); text-decoration: none; white-space: nowrap; }}
    footer {{ background: var(--navy-dark); color: rgba(255,255,255,0.5); text-align: center; padding: 28px 24px; font-size: 0.82rem; margin-top: 56px; }}
    footer a {{ color: rgba(255,255,255,0.7); text-decoration: none; }}
    """


def header_html(root_pad: str = "") -> str:
    return f"""<header>
  <div class="header-inner">
    <a href="{root_pad}index.html" class="logo">
      <img src="{root_pad}{LOGO_BESTAND}" alt="{SITE_NAAM}" />
      <div class="logo-text"><span>Rug Nek</span> Netwerk</div>
    </a>
    <a class="terug-link" href="{root_pad}protocollen.html">← Alle protocollen</a>
  </div>
</header>"""


def footer_html(root_pad: str = "") -> str:
    jaar = date.today().year
    return f"""<footer>
  <p>© {jaar} {SITE_NAAM} · <a href="{root_pad}index.html">Home</a> · <a href="{root_pad}privacy.html">Privacyverklaring</a> · Onderdeel van het <a href="https://vindjefysio.net">VindJeFysio Netwerk</a></p>
</footer>"""


# ══════════════════════════════════════════════════════════════════
# PROTOCOL-DETAILPAGINA
# ══════════════════════════════════════════════════════════════════
def bouw_protocol_pagina(protocol: dict, niveau: str, inhoud_html: str) -> str:
    naam = protocol["naam"]
    zone = protocol.get("zone", "algemeen")
    zone_naam = ZONES.get(zone, "Protocol")
    zone_kleur = ZONE_KLEUREN.get(zone, KLEUR_TEAL)
    zone_icon = ZONE_ICONS.get(zone, "🦴")
    is_patient = (niveau == "makkelijk")

    ander_niveau = "complex" if is_patient else "makkelijk"
    heeft_ander = ander_niveau in protocol.get("niveaus", {})
    wissel_knop = ""
    if heeft_ander:
        wissel_tekst = "📕 Bekijk de versie voor therapeuten" if is_patient else "📗 Bekijk de versie voor patiënten"
        wissel_knop = f'<a class="wissel-knop" href="{protocol["id"]}-{ander_niveau}.html">{wissel_tekst}</a>'

    if is_patient:
        badge = '<span class="niveau-badge patient">📗 Voor patiënten</span>'
        disclaimer = """<div class="disclaimer">
      ℹ️ Deze uitleg hoort bij een behandelprotocol van het Rug Nek Netwerk en is geen vervanging
      van persoonlijk advies. Uw therapeut bespreekt met u wat past bij uw situatie.
    </div>"""
        voorlees = """<div class="voorlees-balk">
      <button class="voorlees-knop" id="voorlees-knop" onclick="toggleVoorlezen()">🔊 Lees voor</button>
      <span class="voorlees-hint">Laat deze pagina hardop voorlezen</span>
    </div>"""
        voorlees_js = """<script>
let aanHetLezen = false;
function toggleVoorlezen() {
  const knop = document.getElementById('voorlees-knop');
  if (aanHetLezen) {
    speechSynthesis.cancel();
    aanHetLezen = false;
    knop.textContent = '🔊 Lees voor';
    return;
  }
  const tekst = document.getElementById('protocol-inhoud').innerText;
  const uiting = new SpeechSynthesisUtterance(tekst);
  uiting.lang = 'nl-NL';
  uiting.rate = 0.95;
  uiting.onend = () => { aanHetLezen = false; knop.textContent = '🔊 Lees voor'; };
  speechSynthesis.speak(uiting);
  aanHetLezen = true;
  knop.textContent = '⏹ Stop voorlezen';
}
window.addEventListener('beforeunload', () => speechSynthesis.cancel());
</script>"""
    else:
        badge = '<span class="niveau-badge therapeut">📕 Voor therapeuten</span>'
        disclaimer = """<div class="disclaimer klinisch">
      ⚕️ Klinische versie voor aangesloten therapeuten van het Rug Nek Netwerk. Toepassing vraagt
      professionele afweging binnen de eigen bevoegd- en bekwaamheid.
    </div>"""
        voorlees = ""
        voorlees_js = ""

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(naam)} ({'patiëntversie' if is_patient else 'therapeutversie'}) – {SITE_NAAM}</title>
  <meta name="description" content="Behandelprotocol {html.escape(naam)} van het {SITE_NAAM} — {zone_naam}." />
  <style>
    {basis_css()}
    .artikel {{ max-width: 720px; margin: 0 auto; padding: 40px clamp(1rem,4vw,2rem) 64px; }}
    .artikel-kop {{ border-bottom: 1px solid var(--grey-border); padding-bottom: 22px; margin-bottom: 26px; }}
    .zone-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; color: white; background: {zone_kleur}; margin-bottom: 12px; }}
    .niveau-badge {{ display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; margin-left: 6px; }}
    .niveau-badge.patient {{ background: #EDF7EE; color: #2e7d32; border: 1px solid #A5D6A7; }}
    .niveau-badge.therapeut {{ background: #FDEDEC; color: #922B21; border: 1px solid #F1948A; }}
    .artikel h1 {{ font-size: clamp(1.5rem,3.5vw,2rem); font-weight: 700; color: var(--navy); line-height: 1.25; margin-top: 10px; }}
    .voorlees-balk {{ display: flex; align-items: center; gap: 12px; background: var(--teal-light); border: 1px solid rgba(27,160,152,0.3); border-radius: 12px; padding: 12px 16px; margin-bottom: 22px; }}
    .voorlees-knop {{ background: var(--teal); color: white; border: none; border-radius: 8px; padding: 9px 18px; font-family: 'Inter', sans-serif; font-size: 0.85rem; font-weight: 700; cursor: pointer; }}
    .voorlees-knop:hover {{ background: var(--teal-dark); }}
    .voorlees-hint {{ font-size: 0.78rem; color: var(--teal-dark); }}
    .disclaimer {{ background: #FEF9E7; border: 1px solid rgba(243,156,18,0.35); border-radius: 10px; padding: 13px 16px; font-size: 0.8rem; color: #7d5a00; line-height: 1.6; margin-bottom: 26px; }}
    .disclaimer.klinisch {{ background: var(--grey-bg); border-color: var(--grey-border); color: var(--text-muted); }}
    #protocol-inhoud h2 {{ font-size: 1.25rem; font-weight: 700; color: var(--navy); margin: 30px 0 10px; }}
    #protocol-inhoud h3 {{ font-size: 1.05rem; font-weight: 700; color: var(--navy); margin: 24px 0 8px; }}
    #protocol-inhoud h4, #protocol-inhoud h5 {{ font-size: 0.95rem; font-weight: 700; color: var(--navy); margin: 20px 0 6px; }}
    #protocol-inhoud p {{ margin-bottom: 14px; }}
    #protocol-inhoud ul, #protocol-inhoud ol {{ margin: 0 0 16px 22px; }}
    #protocol-inhoud li {{ margin-bottom: 6px; }}
    #protocol-inhoud a {{ color: var(--teal); }}
    #protocol-inhoud strong {{ color: var(--navy); }}
    .scheiding {{ border: none; border-top: 1px solid var(--grey-border); margin: 28px 0; }}
    .wissel-knop {{ display: inline-block; margin-top: 32px; background: var(--navy); color: white; text-decoration: none; border-radius: 10px; padding: 12px 22px; font-size: 0.88rem; font-weight: 700; }}
    .wissel-knop:hover {{ background: var(--navy-dark); }}
  </style>
</head>
<body>
{header_html("../")}
<article class="artikel">
  <div class="artikel-kop">
    <span class="zone-badge">{zone_icon} {zone_naam}</span>{badge}
    <h1>{html.escape(naam)}</h1>
  </div>
  {voorlees}
  {disclaimer}
  <div id="protocol-inhoud">
{inhoud_html}
  </div>
  {wissel_knop}
</article>
{footer_html("../")}
{voorlees_js}
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════
# OVERZICHTSPAGINA protocollen.html
# ══════════════════════════════════════════════════════════════════
def bouw_overzicht(protocollen: list, previews: dict) -> str:
    zone_filters = '<button class="zone-filter actief" data-zone="alle" onclick="filterZone(this)">Alle gebieden</button>'
    for zkey, znaam in ZONES.items():
        zone_filters += (f'<button class="zone-filter" data-zone="{zkey}" '
                         f'style="--zk:{ZONE_KLEUREN[zkey]}" onclick="filterZone(this)">'
                         f'{ZONE_ICONS[zkey]} {znaam}</button>')

    if protocollen:
        kaarten = ""
        for p in protocollen:
            zone = p.get("zone", "algemeen")
            zone_naam = ZONES.get(zone, "Protocol")
            zone_kleur = ZONE_KLEUREN.get(zone, KLEUR_TEAL)
            preview = html.escape(previews.get(p["id"], ""))
            niveaus = p.get("niveaus", {})
            knoppen = ""
            if "makkelijk" in niveaus:
                knoppen += f'<a class="p-knop patient" href="protocollen/{p["id"]}-makkelijk.html">📗 Voor patiënten</a>'
            if "complex" in niveaus:
                knoppen += f'<a class="p-knop therapeut" href="protocollen/{p["id"]}-complex.html">📕 Voor therapeuten</a>'
            kaarten += f"""
      <div class="protocol-kaart" data-zone="{zone}" data-zoek="{html.escape(p['naam'].lower())}">
        <span class="zone-badge" style="background:{zone_kleur}">{ZONE_ICONS.get(zone,'🦴')} {zone_naam}</span>
        <h3>{html.escape(p['naam'])}</h3>
        {f'<p class="preview">{preview}</p>' if preview else ''}
        <div class="p-knoppen">{knoppen}</div>
      </div>"""
        inhoud = f'<div class="protocol-grid" id="protocol-grid">{kaarten}\n    </div>'
    else:
        inhoud = """<div class="leeg-blok">
      <div style="font-size:3rem;margin-bottom:12px">🦴</div>
      <h3 style="color:var(--navy);margin-bottom:8px">Protocollen in ontwikkeling</h3>
      <p style="color:var(--text-muted);font-size:0.9rem;max-width:440px;margin:0 auto">
        Onze expertteams werken aan de eerste behandelprotocollen voor nek, borstwervelkolom en lage rug.
        Zodra een protocol is vastgesteld, verschijnt het hier.</p>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Behandelprotocollen – {SITE_NAAM}</title>
  <meta name="description" content="Behandelprotocollen van het {SITE_NAAM}: nek & hoofd, borstwervelkolom & ribben, lage rug & SI-gewricht. Elk protocol in een leesbare versie voor patiënten en een klinische versie voor therapeuten." />
  <style>
    {basis_css()}
    .hero {{ background: linear-gradient(160deg, #1BA098 0%, #6ABF4B 45%, #2E7DD1 100%); position: relative; color: white; text-align: center; padding: 56px 24px 48px; }}
    .hero::before {{ content:''; position:absolute; inset:0; background:rgba(0,0,0,0.32); }}
    .hero-content {{ position: relative; z-index: 1; max-width: 640px; margin: 0 auto; }}
    .hero h1 {{ font-size: clamp(1.7rem,4vw,2.4rem); font-weight: 700; margin-bottom: 12px; text-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
    .hero p {{ opacity: 0.92; font-size: 0.98rem; line-height: 1.7; }}
    .pagina {{ max-width: 1000px; margin: 0 auto; padding: 36px clamp(1rem,4vw,2rem) 64px; }}
    .zoek-rij {{ display: flex; gap: 10px; margin-bottom: 16px; }}
    .zoek-input {{ flex: 1; min-width: 0; padding: 12px 16px; border: 1.5px solid var(--grey-border); border-radius: 10px; font-family: 'Inter', sans-serif; font-size: 0.92rem; outline: none; }}
    .zoek-input:focus {{ border-color: var(--teal); box-shadow: 0 0 0 3px rgba(27,160,152,0.12); }}
    .zone-filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 26px; }}
    .zone-filter {{ padding: 7px 15px; border-radius: 999px; border: 1.5px solid var(--grey-border); background: white; color: var(--text-muted); font-family: 'Inter', sans-serif; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }}
    .zone-filter:hover {{ border-color: var(--zk, var(--teal)); color: var(--zk, var(--teal)); }}
    .zone-filter.actief {{ background: var(--zk, var(--teal)); border-color: var(--zk, var(--teal)); color: white; }}
    .protocol-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
    .protocol-kaart {{ border: 1.5px solid var(--grey-border); border-radius: 16px; padding: 22px; background: white; display: flex; flex-direction: column; gap: 10px; transition: box-shadow 0.2s; }}
    .protocol-kaart:hover {{ box-shadow: 0 8px 28px rgba(0,0,0,0.09); }}
    .zone-badge {{ display: inline-flex; align-items: center; gap: 6px; width: fit-content; font-size: 0.7rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; color: white; }}
    .protocol-kaart h3 {{ font-size: 1rem; font-weight: 700; color: var(--navy); line-height: 1.35; }}
    .preview {{ font-size: 0.82rem; color: var(--text-muted); line-height: 1.55; }}
    .p-knoppen {{ display: flex; flex-direction: column; gap: 6px; margin-top: auto; }}
    .p-knop {{ display: block; text-align: center; padding: 10px; border-radius: 9px; font-size: 0.83rem; font-weight: 700; text-decoration: none; }}
    .p-knop.patient {{ background: var(--teal); color: white; }}
    .p-knop.patient:hover {{ background: var(--teal-dark); }}
    .p-knop.therapeut {{ background: var(--grey-bg); color: var(--navy); border: 1.5px solid var(--grey-border); }}
    .p-knop.therapeut:hover {{ border-color: var(--navy); }}
    .leeg-blok {{ text-align: center; padding: 56px 24px; background: var(--grey-bg); border: 1px solid var(--grey-border); border-radius: 16px; }}
    .geen-match {{ display: none; text-align: center; padding: 32px; color: var(--text-muted); font-size: 0.9rem; }}
  </style>
</head>
<body>
{header_html("")}
<section class="hero">
  <div class="hero-content">
    <h1>Behandelprotocollen</h1>
    <p>Onze expertteams schrijven en onderhouden behandelprotocollen op basis van de laatste wetenschappelijke inzichten. Elk protocol is beschikbaar in een leesbare versie voor patiënten en een klinische versie voor therapeuten.</p>
  </div>
</section>
<div class="pagina">
  <div class="zoek-rij">
    <input type="text" class="zoek-input" id="zoek-input" placeholder="🔍 Zoek bijv. hernia, nekpijn, SI-gewricht..." oninput="filterProtocollen()" />
  </div>
  <div class="zone-filters">{zone_filters}</div>
  {inhoud}
  <div class="geen-match" id="geen-match">Geen protocollen gevonden voor deze zoekopdracht.</div>
</div>
{footer_html("")}
<script>
let actieveZone = 'alle';
function filterZone(knop) {{
  actieveZone = knop.dataset.zone;
  document.querySelectorAll('.zone-filter').forEach(b => b.classList.toggle('actief', b === knop));
  filterProtocollen();
}}
function filterProtocollen() {{
  const q = (document.getElementById('zoek-input')?.value || '').toLowerCase().trim();
  let zichtbaar = 0;
  document.querySelectorAll('.protocol-kaart').forEach(k => {{
    const zoneOk = actieveZone === 'alle' || k.dataset.zone === actieveZone;
    const zoekOk = !q || k.dataset.zoek.includes(q);
    const toon = zoneOk && zoekOk;
    k.style.display = toon ? 'flex' : 'none';
    if (toon) zichtbaar++;
  }});
  const geenMatch = document.getElementById('geen-match');
  if (geenMatch) geenMatch.style.display = (zichtbaar === 0 && document.querySelector('.protocol-kaart')) ? 'block' : 'none';
}}
</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════
# SITEMAP
# ══════════════════════════════════════════════════════════════════
def bouw_sitemap(protocollen: list) -> str:
    vandaag = date.today().isoformat()
    urls = [
        f"{SITE_URL}/",
        f"{SITE_URL}/protocollen.html",
        f"{SITE_URL}/therapeut-aanmelden.html",
    ]
    for p in protocollen:
        for niveau in p.get("niveaus", {}):
            urls.append(f"{SITE_URL}/protocollen/{p['id']}-{niveau}.html")
    entries = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{vandaag}</lastmod></url>" for u in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
"""


# ══════════════════════════════════════════════════════════════════
# HOOFDPROGRAMMA
# ══════════════════════════════════════════════════════════════════
def maak_preview(tekst: str, max_len: int = 140) -> str:
    """Eerste inhoudelijke zin(nen) als preview, zonder markdown-tekens."""
    schoon = re.sub(r"^#{1,4}\s+.*$", "", tekst, flags=re.M)      # koppen weg
    schoon = re.sub(r"[*_#>\-]{1,3}", "", schoon)                  # md-tekens weg
    schoon = " ".join(schoon.split())
    if len(schoon) <= max_len:
        return schoon
    afgekapt = schoon[:max_len]
    return afgekapt[:afgekapt.rfind(" ")] + "..."


def main() -> int:
    config_pad = Path(CONFIG_BESTAND)
    if not config_pad.exists():
        print(f"⚠️  {CONFIG_BESTAND} niet gevonden — niets te doen.")
        return 0

    config = json.loads(config_pad.read_text(encoding="utf-8"))
    protocollen = config.get("protocollen", [])
    OUTPUT_MAP.mkdir(exist_ok=True)

    previews = {}
    gelukt = 0

    for protocol in protocollen:
        pid = protocol.get("id", "").strip()
        naam = protocol.get("naam", pid)
        if not pid:
            print("  ⚠️  Protocol zonder id overgeslagen.")
            continue
        print(f"▸ {naam} ({pid})")

        for niveau, doc_id in protocol.get("niveaus", {}).items():
            if not doc_id:
                continue
            tekst = haal_doc_tekst(doc_id)
            if tekst is None:
                print(f"  ✗ {niveau}: ophalen mislukt — bestaande versie blijft staan.")
                continue
            if niveau == "makkelijk" and pid not in previews:
                previews[pid] = maak_preview(tekst)
            inhoud_html = naar_html(tekst)
            pagina = bouw_protocol_pagina(protocol, niveau, inhoud_html)
            doel = OUTPUT_MAP / f"{pid}-{niveau}.html"
            doel.write_text(pagina, encoding="utf-8")
            print(f"  ✓ {doel}")
            gelukt += 1

    Path("protocollen.html").write_text(bouw_overzicht(protocollen, previews), encoding="utf-8")
    print("✓ protocollen.html")
    Path("sitemap.xml").write_text(bouw_sitemap(protocollen), encoding="utf-8")
    print("✓ sitemap.xml")
    print(f"\nKlaar: {gelukt} protocolpagina('s) gegenereerd uit {len(protocollen)} protocol(len).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
