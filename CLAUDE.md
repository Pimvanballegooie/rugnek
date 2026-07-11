# VindJeFysio Netwerk — rugnek.net

Deze repo is één "spoke" in een hub-and-spoke netwerk van gespecialiseerde fysiotherapie-subsites. De hub is vindjefysio.net; spokes zijn o.a. enkelvoet, beenklachten, kansrijkopgroeien, mentaalgezond, chronischezorg, armklachten en deze (rugnek).

## Architectuur
- Statische HTML/CSS/vanilla JS op GitHub Pages, custom domein via CNAME.
- Gedeelde Supabase-backend, project islujznszevdynguhjdc, met anon key in de frontend.
- Gedeelde tabellen: therapeuten, praktijken, therapeut_subcategorieen, therapeut_praktijken, subcategorieen, categorieen.
- Elke spoke deelt dezelfde structuur en bestanden: index.html, therapeut-aanmelden.html, mijn-profiel.html, therapeuten.html, privacy.html, protocollen.html (gegenereerd), sync_protocollen.py, .github/workflows/sync.yml, protocollen-config.json.

## Belangrijke conventies
- therapeut-aanmelden.html linkt ALTIJD relatief/lokaal binnen de eigen subsite (nooit naar vindjefysio.net).
- Praktijk/locatie-aanmelden loopt WEL centraal via vindjefysio.net/aanmelden.html?via=<domein>.
- Mails lopen via info@vindjefysio.net.
- Therapeut-registratie zet aangemeld_via op het eigen subsite-domein en actief=false (wacht op goedkeuring).
- Deze site: palet primair #1BA098 (teal), navy #22384A. Structuur = gebieden (nek, borst/ribben, lage rug, bekken) + thema's (houding/scoliose, revalidatie, voorbereiding operatie, sport). Lage rug (36) en bekken (38) vereisen aansluiting Lage Rugnetwerk.

## Sync-pipeline
- sync_protocollen.py haalt protocollen op uit publiek gedeelde Google Docs (export-link, geen API-key), zet markdown om naar HTML, genereert protocollen/<id>-makkelijk.html (patiënt) en -complex.html (therapeut) + protocollen.html + sitemap.xml.
- De workflow git-add regel moet zijn: git add protocollen/ protocollen.html sitemap.xml (op één regel).
- Google Docs moeten op "iedereen met de link kan bekijken" staan.
