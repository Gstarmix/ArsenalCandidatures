import json
import re
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from scripts.config import LOGS
from scripts.logger_setup import get_logger
from scripts import offres_store
log = get_logger()
FT_BASE = "https://candidat.francetravail.fr"
FT_RECHERCHE = (FT_BASE + "/offres/recherche?lieux=35238&rayon=10"
                "&offresPartenaires=true&motsCles=")
FT_MOTS_CLES = [
    "manutention",
    "préparateur de commande",
    "employé libre service",
    "mise en rayon",
    "caissier",
    "agent d'entretien",
    "agent de production",
    "équipier restauration",
    "plongeur",
    "déménagement",
    "manœuvre",
]
CROUS_RENNES_URL = "https://www.crous-rennes.fr/offres-emploi/"
CROUS_TYPES_GARDES = {"emploi-etudiant"}
MOTS_PRIORITAIRES = [
    "ouvrier", "opérateur", "operateur", "préparateur", "preparateur",
    "manutention", "agent de production", "agent de fabrication",
    "conditionnement", "production", "emballage", "saisonnier", "abattoir",
    "découpe", "decoupe", "cariste", "magasinier", "manœuvre", "manoeuvre",
    "polyvalent", "polyvalente", "manutentionnaire", "employé", "employe",
    "équipier", "equipier", "agent d'entretien", "nettoyage", "rayon",
    "déménageur", "demenageur", "plonge", "commis",
]
PENALITES = ("alternance", "apprentissage", "stage")
def _clean(texte) -> str:
    return re.sub(r"\s+", " ", (texte or "").replace("\xa0", " ")).strip()
def _charger_pages(urls, wait_until="domcontentloaded", apres_ms=2000,
                   scrolls=0, bouton_plus=None, clics_plus=0) -> dict:
    from playwright.sync_api import sync_playwright
    resultats = {}
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page()
        for url in urls:
            try:
                page.goto(url, wait_until=wait_until, timeout=60000)
                page.wait_for_timeout(apres_ms)
                for _ in range(scrolls):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1100)
                for _ in range(clics_plus):
                    if not bouton_plus:
                        break
                    try:
                        page.click(bouton_plus, timeout=5000)
                        page.wait_for_timeout(2000)
                    except Exception:
                        break
                resultats[url] = page.content()
            except Exception as e:
                log.warning("Échec de chargement (%s) : %s", url, e)
                resultats[url] = ""
        navigateur.close()
    return resultats
def charger_texte_offre(url: str) -> str:
    if not url:
        return ""
    try:
        html = _charger_pages([url]).get(url, "")
        if not html:
            return ""
        return _clean(BeautifulSoup(html, "html.parser").get_text(" "))[:8000]
    except Exception as e:
        log.warning("Texte d'offre non récupéré (%s) : %s", url, e)
        return ""
def _score(offre: dict) -> int:
    titre = offre.get("titre", "").lower()
    contrat = offre.get("contrat", "").lower()
    contexte = contrat + " " + titre
    score = 0
    if any(mot in titre for mot in MOTS_PRIORITAIRES):
        score += 10
    if "rennes" in offre.get("lieu", "").lower():
        score += 5
    if "saison" in contexte:
        score += 4
    if "intérim" in contrat or "interim" in contrat:
        score += 3
    if "insertion" in contrat:
        score -= 6
    elif "cdd" in contrat:
        score += 2
    if "cdi" in contrat:
        score -= 6
    if any(c in contexte for c in PENALITES):
        score -= 8
    return score
def _parser_ft(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    offres = []
    for li in soup.select("li.result[data-id-offre]"):
        oid = li.get("data-id-offre", "")
        titre_el = li.select_one("h2 .media-heading-title") or li.select_one("h2")
        titre = _clean(titre_el.get_text()) if titre_el else ""
        if not titre or not oid:
            continue
        sub = li.select_one("p.subtext")
        entreprise, lieu = "", ""
        if sub:
            span = sub.find("span")
            lieu = _clean(span.get_text()) if span else ""
            entreprise = _clean(sub.get_text(" "))
            if lieu:
                entreprise = entreprise.replace(lieu, "")
            entreprise = entreprise.strip(" -–\xa0").strip()
        contrat_el = (li.select_one("div.media-right p.contrat")
                      or li.select_one("p.contrat"))
        contrat = _clean(contrat_el.get_text(" ")) if contrat_el else ""
        offres.append({
            "id": oid, "titre": titre, "entreprise": entreprise,
            "lieu": lieu, "contrat": contrat,
            "url": f"{FT_BASE}/offres/recherche/detail/{oid}",
        })
    return offres
def scraper_francetravail() -> dict:
    urls = [FT_RECHERCHE + urllib.parse.quote(kw) for kw in FT_MOTS_CLES]
    log.info("France Travail : %d recherches (Rennes + 10 km, 2 pages).",
             len(urls))
    pages = _charger_pages(urls, bouton_plus="text=/offres suivantes/i",
                           clics_plus=1)
    par_id = {}
    for html in pages.values():
        for offre in _parser_ft(html):
            par_id.setdefault(offre["id"], offre)
    offres = list(par_id.values())
    for offre in offres:
        offre["score"] = _score(offre)
    offres.sort(key=lambda o: o["score"], reverse=True)
    log.info("France Travail : %d offre(s) uniques.", len(offres))
    _ecrire("France Travail : Rennes et environs (10 km)",
            "offres_francetravail", offres)
    offres_store.fusionner(offres, "francetravail")
    return {"total": len(offres), "offres": offres}
def _parser_crous(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    offres = []
    for art in soup.select("article"):
        classes = art.get("class", [])
        slug = next((c[len("type-offre-"):] for c in classes
                     if c.startswith("type-offre-")), "")
        if slug not in CROUS_TYPES_GARDES:
            continue
        titre_el = art.find(["h3", "h2"])
        titre = _clean(titre_el.get_text()) if titre_el else ""
        lien = art.find("a")
        url = lien.get("href", "") if lien else ""
        if not titre or not url:
            continue
        cat = art.select_one("ul.post-categories a")
        type_offre = _clean(cat.get_text()) if cat else ""
        offres.append({
            "titre": titre,
            "entreprise": "Crous Bretagne",
            "lieu": "Rennes (35)",
            "contrat": type_offre,
            "url": url,
        })
    return offres
def scraper_crous() -> dict:
    log.info("Crous Rennes : %s", CROUS_RENNES_URL)
    pages = _charger_pages([CROUS_RENNES_URL])
    offres = _parser_crous(pages.get(CROUS_RENNES_URL, ""))
    for offre in offres:
        offre["score"] = _score(offre)
    offres.sort(key=lambda o: o["score"], reverse=True)
    log.info("Crous Rennes : %d rubrique(s) emploi étudiant.", len(offres))
    _ecrire("Crous Rennes Bretagne : emploi étudiant", "offres_crous", offres)
    offres_store.fusionner(offres, "crous")
    return {"total": len(offres), "offres": offres}
def _ecrire(titre_source: str, nom_fichier: str, offres: list) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{nom_fichier}.json").write_text(
        json.dumps(offres, ensure_ascii=False, indent=2), encoding="utf-8")
    prioritaires = [o for o in offres if o.get("score", 0) >= 10]
    autres = [o for o in offres if o.get("score", 0) < 10]
    def ligne(o: dict) -> str:
        base = (f"- **{o['titre']}** · {o.get('lieu') or 'lieu n.c.'}"
                f" · {o.get('contrat') or 'contrat n.c.'}")
        if o.get("entreprise"):
            base += f" · _{o['entreprise']}_"
        return base + (f"\n  - {o['url']}" if o.get("url") else "")
    out = [
        f"# Offres : {titre_source}",
        f"\n_Scrapé le {datetime.now():%d/%m/%Y à %H:%M}, "
        f"{len(offres)} offre(s)_\n",
        f"\n## ⭐ À viser en priorité ({len(prioritaires)})",
        "_Postes sans qualification, classés par pertinence._\n",
    ]
    out += [ligne(o) for o in prioritaires] or ["_Aucune pour le moment._"]
    out += [f"\n## Autres offres ({len(autres)})\n"]
    out += [ligne(o) for o in autres] or ["_Aucune._"]
    (LOGS / f"{nom_fichier}.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    log.info("Liste écrite -> %s", LOGS / f"{nom_fichier}.md")
def scraper(source: str = "francetravail") -> dict:
    if source == "crous":
        return scraper_crous()
    return scraper_francetravail()