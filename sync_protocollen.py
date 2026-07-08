import json, urllib.request, urllib.parse, re, os
from html.parser import HTMLParser
from datetime import date

# ─────────────────────────────────────────────────────────────
# CONFIG — pas aan per protocol dat je toevoegt
# ─────────────────────────────────────────────────────────────
#
# protocollen-config.json structuur:
# {
#   "protocollen": [
#     {
#       "id": "functionele-neurologische-stoornis-fns",
#       "naam": "Functionele Neurologische Stoornis (FNS)",
#       "zone": "fns",
#       "niveaus": {
#         "makkelijk": "GOOGLE_DOC_ID_HIER",
#         "complex":   "GOOGLE_DOC_ID_HIER"
#       }
#     }
#   ]
# }
#
# Zone-waarden:
#   psychosomatiek · ademhaling · fns

with open('protocollen-config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# ─────────────────────────────────────────────────────────────
# ZONES & BRANDING (Mentaal Gezond)
# ─────────────────────────────────────────────────────────────
ZONES = {
    'psychosomatiek': 'Psychosomatische klachten',
    'ademhaling':     'Ademhaling & hyperventilatie',
    'fns':            'Functionele neurologische stoornis',
}

ZONE_ICONS = {
    'psychosomatiek': '🫁',
    'ademhaling':     '💨',
    'fns':            '🧠',
}

SITE_URL       = 'https://mentaalgezond.net'
SITE_NAAM      = 'Mentaal Gezond'
LOGO_BESTAND   = 'LogoMentaleGezondheid.jpeg'
KLEUR_TEAL     = '#2A9D8F'
KLEUR_TEAL_L   = '#E8F5F4'
KLEUR_TEAL_D   = '#1f7a6e'
KLEUR_NAVY     = '#264653'
KLEUR_NAVY_D   = '#1a2f38'
KLEUR_GREY_BG  = '#F8F9FA'
KLEUR_GREY_B   = '#E8ECF0'

# ─────────────────────────────────────────────────────────────
# SHORTCODE VERWERKING
# Ondersteunde shortcodes in Google Docs:
#
#   [CALLOUT: groen | 💡 Titel]   → groen infoblock
#   [CALLOUT: geel | ⚠️ Titel]   → gele waarschuwing
#   [CALLOUT: blauw | 📌 Titel]  → blauwe info
#   [CALLOUT: rood | 🚫 Titel]   → rode waarschuwing
#   [CALLOUT: teal | 💬 Titel]   → teal info (huisstijl)
#   [/CALLOUT]                    → sluit callout
#
#   [TABEL]                       → start tabel
#   | Kolom 1 | Kolom 2 |        → header rij
#   | cel 1   | cel 2   |        → data rij
#   [/TABEL]                      → sluit tabel
#
#   [VIDEO: naam | url]           → video knop
# ─────────────────────────────────────────────────────────────

CALLOUT_KLEUREN = {
    'groen': {'bg': '#EDF7EE', 'border': '#4CAF50', 'titel': '#2e7d32'},
    'geel':  {'bg': '#FEF9E7', 'border': '#F39C12', 'titel': '#7d5a00'},
    'blauw': {'bg': '#EAF4FB', 'border': '#2980B9', 'titel': '#1a4a72'},
    'rood':  {'bg': '#FDEDEC', 'border': '#C0392B', 'titel': '#7b1a12'},
    'teal':  {'bg': KLEUR_TEAL_L, 'border': KLEUR_TEAL, 'titel': KLEUR_TEAL_D},
}

def verwerk_shortcodes(body):
    """Verwerk [CALLOUT:] en [TABEL] shortcodes naar HTML."""

    def vervang_callout(m):
        kleur = m.group(1).strip().lower()
        titel = m.group(2).strip()
        inhoud = m.group(3).strip()
        k = CALLOUT_KLEUREN.get(kleur, CALLOUT_KLEUREN['teal'])
        return (
            f'<div style="background:{k["bg"]};border-left:4px solid {k["border"]};'
            f'border-radius:12px;padding:18px 20px;margin:20px 0;">'
            f'<div style="font-size:0.82rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.06em;color:{k["titel"]};margin-bottom:8px;">{titel}</div>'
            f'<div style="font-size:0.92rem;color:{KLEUR_NAVY};line-height:1.65;">'
            f'{inhoud}</div></div>'
        )

    body = re.sub(
        r'\[CALLOUT:\s*(\w+)\s*\|\s*([^\]]+)\](.*?)\[/CALLOUT\]',
        vervang_callout,
        body,
        flags=re.DOTALL
    )

    def vervang_tabel(m):
        regels = [r.strip() for r in m.group(1).strip().split('\n') if r.strip()]
        if not regels:
            return ''
        html = (
            f'<table style="width:100%;border-collapse:collapse;margin:16px 0;'
            f'font-size:0.88rem;border-radius:10px;overflow:hidden;">'
        )
        for i, regel in enumerate(regels):
            cellen = [c.strip() for c in regel.strip('|').split('|')]
            if i == 0:
                html += '<thead><tr>'
                for cel in cellen:
                    html += (
                        f'<th style="background:{KLEUR_NAVY};color:white;'
                        f'padding:10px 14px;text-align:left;font-size:0.82rem;'
                        f'font-weight:600;">{cel}</th>'
                    )
                html += '</tr></thead><tbody>'
            else:
                bg = KLEUR_GREY_BG if i % 2 == 0 else 'white'
                html += f'<tr style="background:{bg};">'
                for cel in cellen:
                    html += (
                        f'<td style="padding:10px 14px;border-bottom:1px solid '
                        f'{KLEUR_GREY_B};vertical-align:top;">{cel}</td>'
                    )
                html += '</tr>'
        html += '</tbody></table>'
        return html

    body = re.sub(
        r'\[TABEL\](.*?)\[/TABEL\]',
        vervang_tabel,
        body,
        flags=re.DOTALL
    )

    return body


# ─────────────────────────────────────────────────────────────
# MARKDOWN → HTML
# Zet platte-tekst Markdown (# ## ### ** - 1. --- ) om naar HTML.
# Wordt toegepast NA het strippen van Google's opmaak, zodat je
# gewoon Markdown-tekst in de Google Doc kunt plakken en er toch
# nette koppen/lijsten/vet uit komen.
# ─────────────────────────────────────────────────────────────
def markdown_naar_html(tekst):
    # Normaliseer regeleindes
    tekst = tekst.replace('\r\n', '\n').replace('\r', '\n')
    regels = tekst.split('\n')

    html_blokken = []
    lijst_buffer = []
    lijst_type = None  # 'ul' of 'ol'

    def flush_lijst():
        nonlocal lijst_buffer, lijst_type
        if lijst_buffer:
            items = ''.join(f'<li>{inline_md(x)}</li>' for x in lijst_buffer)
            html_blokken.append(f'<{lijst_type}>{items}</{lijst_type}>')
            lijst_buffer = []
            lijst_type = None

    def inline_md(s):
        # **vet** en *cursief* en [tekst](url)
        s = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', r'<em>\1</em>', s)
        return s

    for rauw in regels:
        regel = rauw.rstrip()
        strip = regel.strip()

        # Lege regel = blokscheiding
        if strip == '':
            flush_lijst()
            continue

        # Horizontale lijn
        if re.match(r'^-{3,}$', strip) or re.match(r'^\*{3,}$', strip):
            flush_lijst()
            html_blokken.append('<hr>')
            continue

        # Koppen
        m = re.match(r'^(#{1,4})\s+(.*)$', strip)
        if m:
            flush_lijst()
            niveau = len(m.group(1))
            inhoud = inline_md(m.group(2).strip())
            # # → h1 wordt overgeslagen (titel staat al in de header van de pagina)
            if niveau == 1:
                continue
            html_blokken.append(f'<h{niveau}>{inhoud}</h{niveau}>')
            continue

        # Ongenummerde lijst
        m = re.match(r'^[-*+]\s+(.*)$', strip)
        if m:
            if lijst_type not in (None, 'ul'):
                flush_lijst()
            lijst_type = 'ul'
            lijst_buffer.append(m.group(1).strip())
            continue

        # Genummerde lijst
        m = re.match(r'^\d+[\.\)]\s+(.*)$', strip)
        if m:
            if lijst_type not in (None, 'ol'):
                flush_lijst()
            lijst_type = 'ol'
            lijst_buffer.append(m.group(1).strip())
            continue

        # Gewone alinea
        flush_lijst()
        html_blokken.append(f'<p>{inline_md(strip)}</p>')

    flush_lijst()
    return '\n'.join(html_blokken)


def lijkt_op_markdown(tekst):
    """Detecteer of de platte tekst Markdown-syntax bevat."""
    signalen = 0
    if re.search(r'^#{1,4}\s+\S', tekst, re.MULTILINE): signalen += 1
    if re.search(r'^\s*[-*+]\s+\S', tekst, re.MULTILINE): signalen += 1
    if re.search(r'\*\*[^*]+\*\*', tekst): signalen += 1
    if re.search(r'^-{3,}$', tekst, re.MULTILINE): signalen += 1
    return signalen >= 2


# ─────────────────────────────────────────────────────────────
# HTML VERWERKING (Google Docs → schone HTML)
# ─────────────────────────────────────────────────────────────
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.skip = False
        if tag in ('p', 'li', 'h1', 'h2', 'h3', 'br', 'tr'):
            self.text.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
    def get_text(self):
        return ' '.join(' '.join(self.text).split())


class PlainTextExtractor(HTMLParser):
    """Haalt platte tekst uit Google's HTML mét behoud van regeleindes,
    zodat we Markdown-tekens (# ## - **) kunnen terugvinden."""
    def __init__(self):
        super().__init__()
        self.regels = []
        self.huidig = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.skip = True
        if tag == 'br':
            self.regels.append(''.join(self.huidig)); self.huidig = []
    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.skip = False
        if tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'tr'):
            self.regels.append(''.join(self.huidig)); self.huidig = []
    def handle_data(self, data):
        if not self.skip:
            # Vervang regeleindes binnen data door spaties, zodat losse
            # whitespace tussen tags geen valse lege regels veroorzaakt
            self.huidig.append(data.replace('\n', ' ').replace('\r', ' '))
    def handle_entityref(self, name):
        mapping = {'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', 'nbsp': ' ', 'apos': "'"}
        self.huidig.append(mapping.get(name, ''))
    def get_text(self):
        if self.huidig:
            self.regels.append(''.join(self.huidig)); self.huidig = []
        return '\n'.join(self.regels)


def verwijder_google_backslashes(body):
    body = body.replace('\\[', '[')
    body = body.replace('\\]', ']')
    body = body.replace('\\+', '+')
    body = body.replace('\\-', '-')
    body = body.replace('\\*', '*')
    body = body.replace('\\|', '|')
    body = body.replace('\\#', '#')
    return body


def opschonen_html(body):
    # ALTIJD als eerste: Google Docs escape-tekens verwijderen
    body = verwijder_google_backslashes(body)

    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
    body = re.sub(r'<img[^>]*/?>', '', body)
    body = re.sub(r'<figure[^>]*>.*?</figure>', '', body, flags=re.DOTALL)

    # Ontgoogle links
    def ontgoogle(match):
        href = match.group(1)
        if 'google.com/url' in href:
            href = href.replace('&amp;', '&')
            parsed = urllib.parse.urlparse(href)
            params = urllib.parse.parse_qs(parsed.query)
            echte_url = params.get('q', [href])[0]
            return f'href="{echte_url}"'
        return match.group(0)
    body = re.sub(r'href="([^"]*)"', ontgoogle, body)

    body = re.sub(r' style="[^"]*"', '', body)
    body = re.sub(r' class="[^"]*"', '', body)
    body = re.sub(r' id="[^"]*"', '', body)
    body = re.sub(r'<hr[^>]*>', '<hr>', body)
    body = re.sub(r'\n{3,}', '\n\n', body)

    # ── MARKDOWN-DETECTIE ──
    # Als de Doc Markdown-tekst bevat (zoals geplakte platte tekst),
    # negeer Google's tag-structuur en herbouw vanuit de Markdown.
    plain = PlainTextExtractor()
    plain.feed(body)
    platte_tekst = verwijder_google_backslashes(plain.get_text())
    if lijkt_op_markdown(platte_tekst):
        body = markdown_naar_html(platte_tekst)

    # [VIDEO: naam | url] shortcode
    def maak_video_knop(match):
        naam = match.group(1).strip()
        url  = match.group(2).strip()
        return (
            f'<a href="{url}" target="_blank" rel="noopener" '
            f'style="display:inline-flex;align-items:center;gap:6px;margin:4px 0;'
            f'padding:6px 14px;background:{KLEUR_TEAL_L};color:{KLEUR_TEAL};'
            f'border:1.5px solid {KLEUR_TEAL};border-radius:6px;'
            f'font-size:0.8rem;font-weight:600;text-decoration:none;">📹 {naam}</a>'
        )
    body = re.sub(r'\[VIDEO:\s*([^|\]]+)\|\s*(https?://[^\]]+)\]', maak_video_knop, body)

    # Opschonen lege tags
    body = re.sub(r'<span>\s*</span>', '', body)
    body = re.sub(r'<span>(.*?)</span>', r'\1', body)
    body = re.sub(r'<p>\s*</p>', '', body)
    body = re.sub(r'<div>\s*</div>', '', body)

    # Shortcodes verwerken
    body = verwerk_shortcodes(body)

    # Callout-divs die per ongeluk in een <p> gewikkeld zijn, uitpakken
    body = re.sub(r'<p>\s*(<div style="background:[^>]*>.*?</div>\s*</div>)\s*</p>',
                  r'\1', body, flags=re.DOTALL)

    return body.strip()


def extraheer_preview(body, max_alineas=4):
    body_schoon = opschonen_html(body)
    blokken = re.findall(r'<(p|h2|h3)[^>]*>.*?</\1>', body_schoon, re.DOTALL | re.IGNORECASE)
    blokken = [b for b in blokken if len(re.sub(r'<[^>]+>', '', b).strip()) > 10]
    return '\n'.join(blokken[:max_alineas])


# ─────────────────────────────────────────────────────────────
# GEDEELDE CSS
# ─────────────────────────────────────────────────────────────
def gedeelde_css():
    return f'''
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-300.woff2') format('woff2'); font-weight: 300; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-regular.woff2') format('woff2'); font-weight: 400; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-500.woff2') format('woff2'); font-weight: 500; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-600.woff2') format('woff2'); font-weight: 600; font-display: swap; }}
    @font-face {{ font-family: 'Inter'; src: url('../fonts/inter-v20-latin-700.woff2') format('woff2'); font-weight: 700; font-display: swap; }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --teal: {KLEUR_TEAL}; --teal-light: {KLEUR_TEAL_L}; --teal-dark: {KLEUR_TEAL_D};
      --navy: {KLEUR_NAVY}; --navy-dark: {KLEUR_NAVY_D};
      --grey-bg: {KLEUR_GREY_BG}; --grey-border: {KLEUR_GREY_B};
      --text: {KLEUR_NAVY}; --text-muted: #6B7A7E; --white: #FFFFFF;
    }}
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: 'Inter', sans-serif; font-size: 16px; color: var(--text); background: var(--grey-bg); line-height: 1.7; }}
    header {{ background: var(--white); border-bottom: 1px solid var(--grey-border); position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    .header-inner {{ max-width: 1000px; margin: 0 auto; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; height: 72px; }}
    .logo {{ display: flex; align-items: center; gap: 12px; text-decoration: none; }}
    .logo img {{ height: 48px; width: 48px; object-fit: contain; border-radius: 10px; }}
    .logo-text {{ font-weight: 700; font-size: 1rem; color: var(--navy); }}
    .logo-text span {{ color: var(--teal); }}
    nav a {{ color: var(--text-muted); text-decoration: none; font-size: 0.85rem; font-weight: 500; padding: 7px 12px; border-radius: 8px; transition: all 0.2s; }}
    nav a:hover {{ background: var(--grey-bg); color: var(--navy); }}
    nav a.cta {{ background: var(--teal); color: white; font-weight: 700; }}
    @media (max-width: 700px) {{ nav {{ display: none; }} }}
    .content {{ max-width: 780px; margin: 0 auto; padding: 40px 24px 80px; }}
    .content h1 {{ font-size: clamp(1.6rem,3.5vw,2.2rem); font-weight: 700; color: var(--navy); margin-bottom: 12px; line-height: 1.2; letter-spacing: -0.02em; }}
    .content h2 {{ font-size: 1.2rem; font-weight: 700; color: var(--navy); margin: 2em 0 0.6em; padding-bottom: 8px; border-bottom: 2px solid var(--teal-light); }}
    .content h3 {{ font-size: 1rem; font-weight: 700; color: var(--navy); margin: 1.4em 0 0.5em; }}
    .content h4 {{ font-size: 0.9rem; font-weight: 700; color: var(--text-muted); margin: 1em 0 0.3em; text-transform: uppercase; letter-spacing: 0.05em; }}
    .content p {{ margin-bottom: 1em; line-height: 1.75; }}
    .content ul, .content ol {{ margin: 0.5em 0 1em 1.5em; }}
    .content li {{ margin-bottom: 0.4em; line-height: 1.65; }}
    .content strong {{ font-weight: 700; color: var(--navy); }}
    .content em {{ font-style: italic; }}
    .content hr {{ border: none; border-top: 1px solid var(--grey-border); margin: 2em 0; }}
    .content a {{ color: var(--teal); }}
    .content a:hover {{ text-decoration: underline; }}
    footer {{ background: var(--navy-dark); color: rgba(255,255,255,0.4); text-align: center; padding: 28px 24px; font-size: 0.82rem; margin-top: 48px; }}
    footer a {{ color: rgba(255,255,255,0.6); text-decoration: none; }}
    '''


def header_html(teruglink_label='← Alle protocollen', teruglink_url='../protocollen.html', root_pad='../'):
    return f'''<header>
  <div class="header-inner">
    <a href="{root_pad}index.html" class="logo">
      <img src="{root_pad}{LOGO_BESTAND}" alt="{SITE_NAAM}" />
      <div class="logo-text"><span>Mentaal</span> Gezond</div>
    </a>
    <nav>
      <a href="{teruglink_url}">{teruglink_label}</a>
      <a href="{root_pad}index.html#zoeken">Zoeken</a>
      <a href="{root_pad}therapeut-aanmelden.html" class="cta">Aanmelden</a>
    </nav>
  </div>
</header>'''

def footer_html():
    return f'''<footer>
  <p>&copy; 2026 {SITE_NAAM} &nbsp;&middot;&nbsp;
  <a href="../index.html">Home</a> &nbsp;&middot;&nbsp;
  <a href="../protocollen.html">Protocollen</a> &nbsp;&middot;&nbsp;
  Onderdeel van het <a href="https://vindjefysio.net">VindJeFysio Netwerk</a></p>
</footer>'''


# ─────────────────────────────────────────────────────────────
# PAGINA-TEMPLATES
# ─────────────────────────────────────────────────────────────
def maak_pagina_makkelijk(protocol_naam, protocol_id, body_schoon, zone_id):
    zone_naam = ZONES.get(zone_id, zone_id.capitalize())
    zone_icon = ZONE_ICONS.get(zone_id, '🧠')

    extractor = TextExtractor()
    extractor.feed(body_schoon)
    tekst_preview = extractor.get_text()[:200].strip()
    description = f"{protocol_naam} — informatie voor patiënten en naasten. {tekst_preview}..."

    complex_link = f'../protocollen/{protocol_id}-complex.html'

    return f'''<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{protocol_naam} | {SITE_NAAM}</title>
  <meta name="description" content="{description}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{SITE_URL}/protocollen/{protocol_id}-makkelijk.html" />
  <meta property="og:title" content="{protocol_naam} | {SITE_NAAM}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:type" content="article" />
  <style>{gedeelde_css()}
    .artikel-header {{ background: var(--white); border-bottom: 1px solid var(--grey-border); padding: 40px 24px 32px; }}
    .artikel-header-inner {{ max-width: 780px; margin: 0 auto; }}
    .zone-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--teal); background: var(--teal-light); padding: 3px 12px; border-radius: 999px; margin-bottom: 14px; }}
    .artikel-meta {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 14px; font-size: 0.8rem; color: var(--text-muted); }}
    .niveau-badge {{ display: inline-flex; align-items: center; gap: 6px; background: #EDF7EE; color: #2e7d32; font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; }}
    .disclaimer {{ background: #FEF9E7; border: 1px solid rgba(243,156,18,0.35); border-radius: 10px; padding: 14px 18px; font-size: 0.82rem; color: #7d5a00; margin-bottom: 28px; line-height: 1.6; }}
    .naar-complex {{ background: var(--navy); color: white; border-radius: 14px; padding: 24px 28px; margin-top: 40px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }}
    .naar-complex h3 {{ font-size: 1rem; font-weight: 700; margin-bottom: 4px; }}
    .naar-complex p {{ font-size: 0.85rem; opacity: 0.8; }}
    .naar-complex a {{ display: inline-block; background: var(--teal); color: white; padding: 10px 20px; border-radius: 8px; font-weight: 700; font-size: 0.88rem; text-decoration: none; white-space: nowrap; }}
    .cta-blok {{ background: linear-gradient(135deg, {KLEUR_TEAL} 0%, #52B788 100%); border-radius: 14px; padding: 28px; margin-top: 40px; color: white; }}
    .cta-blok h3 {{ font-size: 1rem; font-weight: 700; margin-bottom: 8px; }}
    .cta-blok p {{ opacity: 0.9; font-size: 0.88rem; margin-bottom: 16px; }}
    .cta-blok a {{ display: inline-block; background: white; color: var(--teal); padding: 10px 20px; border-radius: 8px; font-weight: 700; font-size: 0.88rem; text-decoration: none; }}

    .voorleesbalk {{ display: flex; align-items: center; gap: 14px; background: var(--white); border: 1.5px solid var(--grey-border); border-radius: 12px; padding: 14px 18px; margin-bottom: 24px; flex-wrap: wrap; }}
    .voorlees-btn {{ display: flex; align-items: center; gap: 8px; background: var(--teal); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 700; font-size: 0.86rem; cursor: pointer; font-family: inherit; transition: background 0.2s; }}
    .voorlees-btn:hover {{ background: var(--teal-dark); }}
    .voorlees-btn.bezig {{ background: var(--navy); }}
    .voorlees-btn svg {{ width: 16px; height: 16px; flex-shrink: 0; }}
    .voorlees-snelheid {{ display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: var(--text-muted); }}
    .voorlees-snelheid select {{ border: 1px solid var(--grey-border); border-radius: 6px; padding: 4px 8px; font-family: inherit; font-size: 0.78rem; color: var(--navy); background: white; }}
    .voorlees-status {{ font-size: 0.78rem; color: var(--text-muted); margin-left: auto; }}
    .voorlees-niet-beschikbaar {{ display: none; font-size: 0.8rem; color: var(--text-muted); font-style: italic; }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "MedicalWebPage",
    "name": "{protocol_naam} | {SITE_NAAM}",
    "description": "{description}",
    "url": "{SITE_URL}/protocollen/{protocol_id}-makkelijk.html",
    "inLanguage": "nl",
    "isPartOf": {{"@type": "WebSite", "name": "{SITE_NAAM}", "url": "{SITE_URL}"}},
    "about": {{"@type": "MedicalCondition", "name": "{protocol_naam}"}}
  }}
  </script>
</head>
<body>

{header_html()}

<div class="artikel-header">
  <div class="artikel-header-inner">
    <div class="zone-badge">{zone_icon} {zone_naam}</div>
    <h1 class="content" style="padding:0;margin:0;border:none;">{protocol_naam}</h1>
    <div class="artikel-meta">
      <span class="niveau-badge">📗 Voor patiënten</span>
      <span>Voor patiënten en naasten</span>
      <span>Mentaal Gezond · {date.today().strftime("%B %Y")}</span>
    </div>
  </div>
</div>

<div class="content">

  <div class="voorleesbalk" id="voorleesbalk">
    <button class="voorlees-btn" id="voorlees-btn" onclick="voorlezenWisselen()">
      <svg viewBox="0 0 24 24" fill="currentColor" id="voorlees-icoon"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
      <span id="voorlees-label">Lees dit artikel voor</span>
    </button>
    <div class="voorlees-snelheid">
      Snelheid:
      <select id="voorlees-snelheid" onchange="snelheidAanpassen()">
        <option value="0.8">Langzaam</option>
        <option value="1" selected>Normaal</option>
        <option value="1.2">Snel</option>
      </select>
    </div>
    <div class="voorlees-status" id="voorlees-status"></div>
  </div>
  <p class="voorlees-niet-beschikbaar" id="voorlees-niet-beschikbaar">Voorlezen wordt niet ondersteund in deze browser.</p>

  <div class="disclaimer">
    ⚠️ Dit artikel is algemene informatie voor patiënten en naasten. Het vervangt geen persoonlijk advies van uw behandelaar, huisarts of neuroloog.
  </div>

  <div id="artikel-tekst">
  {body_schoon}
  </div>

  <div class="naar-complex">
    <div>
      <h3>Bent u fysiotherapeut of paramedicus?</h3>
      <p>Lees het uitgebreide klinische protocol met diagnostiek, behandeling en verwijscriteria.</p>
    </div>
    <a href="{complex_link}">Naar het klinisch protocol →</a>
  </div>

  <div class="cta-blok">
    <h3>Vind een specialist bij u in de buurt</h3>
    <p>Zoek een gespecialiseerde therapeut in de regio via Mentaal Gezond.</p>
    <a href="../index.html#zoeken">Zoek een therapeut →</a>
  </div>
</div>

<script>
  let voorlezenActief = false;
  let huidigeUtterance = null;

  function haalVoorleesbareTekst() {{
    const container = document.getElementById('artikel-tekst');
    const elementen = container.querySelectorAll('h2, h3, p, li, td, th');
    let zinnen = [];
    elementen.forEach(el => {{
      const t = el.textContent.trim();
      if (t.length > 0) zinnen.push(t);
    }});
    return zinnen;
  }}

  function voorlezenWisselen() {{
    if (!('speechSynthesis' in window)) {{
      document.getElementById('voorleesbalk').style.display = 'none';
      document.getElementById('voorlees-niet-beschikbaar').style.display = 'block';
      return;
    }}
    const btn = document.getElementById('voorlees-btn');
    const label = document.getElementById('voorlees-label');
    const status = document.getElementById('voorlees-status');
    if (voorlezenActief) {{
      window.speechSynthesis.cancel();
      voorlezenActief = false;
      btn.classList.remove('bezig');
      label.textContent = 'Lees dit artikel voor';
      status.textContent = '';
      return;
    }}
    const zinnen = haalVoorleesbareTekst();
    if (zinnen.length === 0) return;
    let index = 0;
    voorlezenActief = true;
    btn.classList.add('bezig');
    label.textContent = 'Stop met voorlezen';
    const snelheid = parseFloat(document.getElementById('voorlees-snelheid').value);
    function leesVolgendeZin() {{
      if (!voorlezenActief || index >= zinnen.length) {{
        voorlezenActief = false;
        btn.classList.remove('bezig');
        label.textContent = 'Lees dit artikel voor';
        status.textContent = '';
        return;
      }}
      status.textContent = `Zin ${{index + 1}} van ${{zinnen.length}}`;
      huidigeUtterance = new SpeechSynthesisUtterance(zinnen[index]);
      huidigeUtterance.lang = 'nl-NL';
      huidigeUtterance.rate = snelheid;
      huidigeUtterance.onend = () => {{ index++; leesVolgendeZin(); }};
      huidigeUtterance.onerror = () => {{ index++; leesVolgendeZin(); }};
      window.speechSynthesis.speak(huidigeUtterance);
    }}
    leesVolgendeZin();
  }}

  function snelheidAanpassen() {{
    if (voorlezenActief && huidigeUtterance) {{
      window.speechSynthesis.cancel();
      voorlezenActief = false;
      voorlezenWisselen();
    }}
  }}

  if (!('speechSynthesis' in window)) {{
    document.addEventListener('DOMContentLoaded', () => {{
      document.getElementById('voorleesbalk').style.display = 'none';
      document.getElementById('voorlees-niet-beschikbaar').style.display = 'block';
    }});
  }}
</script>

{footer_html()}
</body>
</html>'''


def maak_pagina_complex(protocol_naam, protocol_id, body_schoon, zone_id):
    zone_naam = ZONES.get(zone_id, zone_id.capitalize())
    zone_icon = ZONE_ICONS.get(zone_id, '🧠')

    extractor = TextExtractor()
    extractor.feed(body_schoon)
    tekst_preview = extractor.get_text()[:200].strip()
    description = f"Klinisch protocol {protocol_naam.lower()} voor fysiotherapeuten en paramedici. Diagnostiek, behandeling en verwijscriteria. {tekst_preview}..."

    makkelijk_link = f'../protocollen/{protocol_id}-makkelijk.html'

    return f'''<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{protocol_naam} – Klinisch protocol | {SITE_NAAM}</title>
  <meta name="description" content="{description}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{SITE_URL}/protocollen/{protocol_id}-complex.html" />
  <style>{gedeelde_css()}
    .protocol-header {{ background: linear-gradient(135deg, {KLEUR_NAVY} 0%, {KLEUR_TEAL_D} 100%); color: white; padding: 48px 24px 40px; position: relative; overflow: hidden; }}
    .protocol-header::before {{ content:''; position:absolute; inset:0; background:linear-gradient(135deg,rgba(42,157,143,0.15) 0%,rgba(82,183,136,0.08) 100%); }}
    .protocol-header-inner {{ max-width: 780px; margin: 0 auto; position: relative; z-index: 1; }}
    .zone-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255,255,255,0.9); background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); padding: 3px 12px; border-radius: 999px; margin-bottom: 14px; }}
    .protocol-header h1 {{ font-size: clamp(1.6rem,3.5vw,2.2rem); font-weight: 700; margin-bottom: 10px; line-height: 1.2; letter-spacing: -0.02em; }}
    .protocol-header p {{ opacity: 0.85; max-width: 640px; font-size: 0.95rem; margin-bottom: 18px; }}
    .protocol-meta {{ display: flex; flex-wrap: wrap; gap: 16px; font-size: 0.8rem; opacity: 0.75; }}
    .niveau-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: white; font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; }}
    .disclaimer {{ background: #FEF9E7; border: 1px solid rgba(243,156,18,0.35); border-radius: 10px; padding: 14px 18px; font-size: 0.82rem; color: #7d5a00; margin-bottom: 28px; line-height: 1.6; }}
    .naar-makkelijk {{ background: var(--grey-bg); border: 1px solid var(--grey-border); border-radius: 12px; padding: 18px 22px; margin-bottom: 28px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .naar-makkelijk p {{ font-size: 0.85rem; color: var(--text-muted); }}
    .naar-makkelijk a {{ font-size: 0.85rem; color: var(--teal); font-weight: 600; text-decoration: none; white-space: nowrap; }}
    .cta-blok {{ background: linear-gradient(135deg, {KLEUR_TEAL} 0%, #52B788 100%); border-radius: 14px; padding: 28px; margin-top: 40px; color: white; }}
    .cta-blok h3 {{ font-size: 1rem; font-weight: 700; margin-bottom: 8px; }}
    .cta-blok p {{ opacity: 0.9; font-size: 0.88rem; margin-bottom: 16px; }}
    .cta-blok a {{ display: inline-block; background: {KLEUR_NAVY}; color: white; padding: 10px 20px; border-radius: 8px; font-weight: 700; font-size: 0.88rem; text-decoration: none; }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "MedicalWebPage",
    "name": "{protocol_naam} – Klinisch protocol | {SITE_NAAM}",
    "description": "{description}",
    "url": "{SITE_URL}/protocollen/{protocol_id}-complex.html",
    "inLanguage": "nl",
    "isPartOf": {{"@type": "WebSite", "name": "{SITE_NAAM}", "url": "{SITE_URL}"}},
    "about": {{"@type": "MedicalCondition", "name": "{protocol_naam}"}},
    "audience": {{"@type": "MedicalAudience", "audienceType": "Clinician"}}
  }}
  </script>
</head>
<body>

{header_html()}

<div class="protocol-header">
  <div class="protocol-header-inner">
    <div class="zone-badge">{zone_icon} {zone_naam}</div>
    <h1>{protocol_naam}</h1>
    <p>Klinisch protocol voor fysiotherapeuten en paramedici — diagnostiek, behandeling en verwijscriteria.</p>
    <div class="protocol-meta">
      <span class="niveau-badge">📕 Voor therapeuten</span>
      <span>Voor fysiotherapeuten en paramedici</span>
      <span>Mentaal Gezond · {date.today().strftime("%B %Y")}</span>
    </div>
  </div>
</div>

<div class="content">
  <div class="naar-makkelijk">
    <p>📗 Er is ook een leesbare versie voor patiënten en naasten.</p>
    <a href="{makkelijk_link}">Bekijk het patiëntenartikel →</a>
  </div>

  <div class="disclaimer">
    ⚠️ Dit protocol is algemene informatie voor zorgverleners. Het vervangt geen klinisch oordeel en dient altijd toegepast te worden binnen de individuele patiëntcontext.
  </div>

  {body_schoon}

  <div class="cta-blok">
    <h3>Bent u nog niet aangesloten?</h3>
    <p>Meld uw praktijk aan bij Mentaal Gezond en word zichtbaar voor patiënten en verwijzers.</p>
    <a href="https://vindjefysio.net/aanmelden.html?via=mentaalgezond.net">Aanmelden als praktijk →</a>
  </div>
</div>

{footer_html()}
</body>
</html>'''


# ─────────────────────────────────────────────────────────────
# HOOFDLOOP
# ─────────────────────────────────────────────────────────────
os.makedirs('protocollen', exist_ok=True)
fouten = []
protocol_data = []

for protocol in config['protocollen']:
    protocol_teksten        = {}
    protocol_previews       = {}
    protocol_volledige_html = {}

    for niveau, doc_id in protocol['niveaus'].items():
        if not doc_id or doc_id in ('INVULLEN', ''):
            print(f"⏭  Overgeslagen: {protocol['id']} – {niveau} (geen doc_id)")
            continue

        url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
        bestandsnaam = f"protocollen/{protocol['id']}-{niveau}.html"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode('utf-8')

            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
            if not body_match:
                fouten.append(f"{bestandsnaam}: geen body gevonden")
                continue

            body        = body_match.group(1)
            body_schoon = opschonen_html(body)

            if niveau == 'makkelijk':
                pagina = maak_pagina_makkelijk(protocol['naam'], protocol['id'], body_schoon, protocol.get('zone', ''))
            elif niveau == 'complex':
                pagina = maak_pagina_complex(protocol['naam'], protocol['id'], body_schoon, protocol.get('zone', ''))
            else:
                print(f"⚠️  Onbekend niveau '{niveau}' voor {protocol['id']} — overgeslagen")
                continue

            with open(bestandsnaam, 'w', encoding='utf-8') as out:
                out.write(pagina)
            print(f"✓  {bestandsnaam}")

            extractor = TextExtractor()
            extractor.feed(body_schoon)
            protocol_teksten[niveau]        = extractor.get_text()[:2000]
            protocol_previews[niveau]       = extraheer_preview(body)
            protocol_volledige_html[niveau] = body_schoon

        except Exception as e:
            fouten.append(f"{bestandsnaam}: {e}")
            print(f"✗  Fout: {bestandsnaam}: {e}")

    if protocol_teksten:
        protocol_data.append({
            'id':       protocol['id'],
            'naam':     protocol['naam'],
            'zone':     protocol.get('zone', ''),
            'teksten':  protocol_teksten,
            'previews': protocol_previews,
        })


# ─────────────────────────────────────────────────────────────
# GENEREER protocollen.html
# ─────────────────────────────────────────────────────────────
print("\nGenereer protocollen.html...")

zone_filter_btns = f'<button class="zone-btn actief" onclick="filterZone(this,\'alle\')">Alle specialisaties</button>\n'
for zone_id, zone_naam in ZONES.items():
    icon = ZONE_ICONS.get(zone_id, '')
    zone_filter_btns += f'<button class="zone-btn" onclick="filterZone(this,\'{zone_id}\')">{icon} {zone_naam}</button>\n'

protocol_kaarten = ''
for p in protocol_data:
    zone_naam = ZONES.get(p['zone'], p['zone'].capitalize())
    zone_icon = ZONE_ICONS.get(p['zone'], '🧠')
    tekst_data = p['teksten'].get('makkelijk', p['teksten'].get('complex', ''))
    tekst_data = tekst_data[:500].lower().replace('"','').replace("'",'')

    preview_html = p['previews'].get('makkelijk', p['previews'].get('complex', '<p>Geen preview beschikbaar.</p>'))

    link_makkelijk = f'protocollen/{p["id"]}-makkelijk.html' if 'makkelijk' in p['teksten'] else None
    link_complex   = f'protocollen/{p["id"]}-complex.html'   if 'complex'   in p['teksten'] else None

    niveau_knoppen = ''
    if link_makkelijk:
        niveau_knoppen += f'<a href="{link_makkelijk}" class="niveau-btn makkelijk">📗 Voor patiënten</a>\n'
    if link_complex:
        niveau_knoppen += f'<a href="{link_complex}" class="niveau-btn complex">📕 Voor therapeuten</a>\n'

    protocol_kaarten += f'''<div class="protocol-kaart" data-naam="{p['naam'].lower()}" data-zone="{p['zone']}" data-tekst="{tekst_data}">
  <div class="zone-badge">{zone_icon} {zone_naam}</div>
  <h2 class="protocol-naam">{p['naam']}</h2>
  <div class="protocol-preview">{preview_html}</div>
  <div class="protocol-niveaus">{niveau_knoppen}</div>
</div>
'''

protocollen_html = f'''<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Behandelprotocollen – {SITE_NAAM}</title>
  <meta name="description" content="Overzicht van behandelprotocollen voor psychosomatische fysiotherapie: psychosomatische klachten, ademhaling, hyperventilatie en functionele neurologische stoornissen." />
  <style>
    {gedeelde_css()}
    .page-hero {{ background: linear-gradient(135deg, {KLEUR_TEAL} 0%, #52B788 40%, {KLEUR_NAVY} 100%); color: white; padding: 56px 24px 48px; text-align: center; position: relative; overflow: hidden; }}
    .page-hero::before {{ content:''; position:absolute; inset:0; background:rgba(0,0,0,0.3); }}
    .page-hero-inner {{ position: relative; z-index: 1; }}
    .page-hero h1 {{ font-size: clamp(1.8rem,4vw,2.4rem); font-weight: 700; margin-bottom: 10px; letter-spacing: -0.02em; text-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
    .page-hero p {{ opacity: 0.9; max-width: 560px; margin: 0 auto 28px; font-size: 0.95rem; }}
    .zoekbalk-wrap {{ max-width: 520px; margin: 0 auto; }}
    .zoekbalk {{ display: flex; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }}
    .zoekbalk input {{ flex: 1; padding: 14px 20px; border: none; outline: none; font-family: inherit; font-size: 1rem; color: {KLEUR_NAVY}; }}
    .zoekbalk button {{ padding: 14px 22px; background: {KLEUR_TEAL}; color: white; border: none; cursor: pointer; font-weight: 700; font-size: 0.9rem; transition: background 0.2s; }}
    .zoekbalk button:hover {{ background: {KLEUR_TEAL_D}; }}
    .filter-wrap {{ max-width: 1100px; margin: 28px auto 0; padding: 0 24px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .filter-label {{ font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-right: 4px; white-space: nowrap; }}
    .zone-btn {{ padding: 6px 14px; border-radius: 999px; border: 1.5px solid var(--grey-border); background: var(--white); color: var(--text-muted); font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: inherit; }}
    .zone-btn:hover, .zone-btn.actief {{ background: {KLEUR_TEAL}; border-color: {KLEUR_TEAL}; color: white; }}
    .container {{ max-width: 1100px; margin: 28px auto 64px; padding: 0 24px; }}
    .resultaat-info {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 20px; }}
    .protocollen-grid {{ display: flex; flex-direction: column; gap: 16px; }}
    .protocol-kaart {{ background: var(--white); border: 1px solid var(--grey-border); border-radius: 14px; padding: 26px 30px; transition: box-shadow 0.2s; }}
    .protocol-kaart:hover {{ box-shadow: 0 4px 20px rgba(38,70,83,0.10); }}
    .protocol-kaart.verborgen {{ display: none; }}
    .zone-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--teal); background: var(--teal-light); padding: 3px 12px; border-radius: 999px; margin-bottom: 12px; }}
    .protocol-naam {{ font-size: 1.05rem; font-weight: 700; color: var(--navy); margin-bottom: 12px; }}
    .protocol-preview {{ font-size: 0.85rem; color: var(--text-muted); line-height: 1.65; margin-bottom: 16px; max-height: 90px; overflow: hidden; position: relative; }}
    .protocol-preview::after {{ content:""; position:absolute; bottom:0; left:0; right:0; height:32px; background:linear-gradient(transparent,white); }}
    .protocol-preview h2, .protocol-preview h3 {{ color: var(--navy); font-size: 0.88rem; font-weight: 700; margin-bottom: 4px; }}
    .protocol-preview p {{ margin-bottom: 6px; }}
    .protocol-niveaus {{ display: flex; gap: 10px; flex-wrap: wrap; padding-top: 14px; border-top: 1px solid var(--grey-border); }}
    .niveau-btn {{ padding: 7px 16px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; text-decoration: none; transition: all 0.15s; }}
    .niveau-btn.makkelijk {{ background: #EDF7EE; color: #2e7d32; }}
    .niveau-btn.makkelijk:hover {{ background: #2e7d32; color: white; }}
    .niveau-btn.complex {{ background: {KLEUR_TEAL_L}; color: {KLEUR_TEAL_D}; }}
    .niveau-btn.complex:hover {{ background: {KLEUR_TEAL_D}; color: white; }}
    .geen-resultaten {{ text-align: center; padding: 64px 24px; color: var(--text-muted); display: none; }}
  </style>
</head>
<body>

{header_html('← Home', 'index.html', root_pad='')}

<div class="page-hero">
  <div class="page-hero-inner">
    <h1>Behandelprotocollen</h1>
    <p>Wetenschappelijk onderbouwde protocollen voor therapeuten en begrijpelijke informatie voor patiënten.</p>
    <div class="zoekbalk-wrap">
      <div class="zoekbalk">
        <input type="text" id="zoek-input" placeholder="Zoek bijv. FNS, hyperventilatie, burn-out..." oninput="zoek()" />
        <button onclick="zoek()">🔍 Zoeken</button>
      </div>
    </div>
  </div>
</div>

<div class="filter-wrap">
  <span class="filter-label">Specialisatie:</span>
  {zone_filter_btns}
</div>

<div class="container">
  <div class="resultaat-info" id="resultaat-info"></div>
  <div class="protocollen-grid" id="protocollen-grid">
    {protocol_kaarten}
  </div>
  <div class="geen-resultaten" id="geen-resultaten">
    <div style="font-size:3rem;margin-bottom:12px">🔍</div>
    <div>Geen protocollen gevonden voor deze zoekopdracht.</div>
  </div>
</div>

{footer_html()}

<script>
  let actieveZone = 'alle';
  function normaliseer(t) {{ return t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,''); }}
  function zoek() {{
    const term = normaliseer(document.getElementById('zoek-input').value);
    const kaarten = document.querySelectorAll('.protocol-kaart');
    let zichtbaar = 0;
    kaarten.forEach(k => {{
      const naam  = normaliseer(k.dataset.naam || '');
      const tekst = normaliseer(k.dataset.tekst || '');
      const zoneMatch = actieveZone === 'alle' || k.dataset.zone === actieveZone;
      const zoekMatch = !term || naam.includes(term) || tekst.includes(term);
      k.classList.toggle('verborgen', !(zoneMatch && zoekMatch));
      if (zoneMatch && zoekMatch) zichtbaar++;
    }});
    document.getElementById('resultaat-info').textContent =
      (term || actieveZone !== 'alle') ? zichtbaar + ' protocollen gevonden' : '';
    document.getElementById('geen-resultaten').style.display = zichtbaar === 0 ? 'block' : 'none';
  }}
  function filterZone(btn, zone) {{
    actieveZone = zone;
    document.querySelectorAll('.zone-btn').forEach(b => b.classList.remove('actief'));
    btn.classList.add('actief');
    zoek();
  }}
</script>
</body>
</html>'''

with open('protocollen.html', 'w', encoding='utf-8') as f:
    f.write(protocollen_html)
print(f"✓  protocollen.html gegenereerd met {len(protocol_data)} protocollen")

# ─────────────────────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────────────────────
vandaag = date.today().isoformat()
sitemap_urls = [
    f'  <url><loc>{SITE_URL}/</loc><changefreq>monthly</changefreq><priority>1.0</priority></url>',
    f'  <url><loc>{SITE_URL}/protocollen.html</loc><lastmod>{vandaag}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>',
]
for p in protocol_data:
    for niveau in p['teksten'].keys():
        sitemap_urls.append(
            f'  <url><loc>{SITE_URL}/protocollen/{p["id"]}-{niveau}.html</loc>'
            f'<lastmod>{vandaag}</lastmod><changefreq>monthly</changefreq>'
            f'<priority>{"0.9" if niveau=="makkelijk" else "0.8"}</priority></url>'
        )

with open('sitemap.xml', 'w', encoding='utf-8') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    f.write('\n'.join(sitemap_urls))
    f.write('\n</urlset>')
print(f"✓  sitemap.xml bijgewerkt")

if fouten:
    print(f"\n⚠️  {len(fouten)} fout(en):")
    for f in fouten: print(f"   – {f}")
else:
    print("\n✅ Klaar zonder fouten!")
