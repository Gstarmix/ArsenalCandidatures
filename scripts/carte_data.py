import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from scripts.config import OFFRES, DATAS, SUIVI_PATH
CARTE_PATH = DATAS / "carte_lieux.json"
GEOCACHE_PATH = DATAS / "geocache.json"
CONTACTS_PATH = DATAS / "carte_contacts.json"
RENNES_CENTRE = {"lat": 48.1093, "lon": -1.6800}
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_UA = "ArsenalCandidatures/1.0 (carte candidatures perso; https://github.com/Gstarmix/Arsenal_Candidatures)"
_MOTS_ADRESSE = ("rue", "place", "boulevard", "bd", "quai", "mail", "allee",
                 "allée", "avenue", "esplanade", "cours", "impasse", "route",
                 "centre commercial", "gare", "chemin")
def _lire_json(path: Path, defaut):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut
def _ecrire_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                    encoding="utf-8")
def _adresse_exploitable(lieu: str) -> bool:
    if not lieu:
        return False
    bas = lieu.lower()
    if "rennes" not in bas and "35" not in bas:
        return False
    a_chiffre = bool(re.search(r"\d", lieu))
    a_mot = any(m in bas for m in _MOTS_ADRESSE)
    return a_mot or (a_chiffre and a_mot)
def _requete_geocode(adresse: str):
    requete = adresse if "rennes" in adresse.lower() else f"{adresse}, Rennes, France"
    params = urllib.parse.urlencode({
        "q": requete, "format": "json", "limit": 1,
        "countrycodes": "fr"})
    req = urllib.request.Request(f"{_NOMINATIM}?{params}",
                                 headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception:
        return None
    if not data:
        return None
    d = data[0]
    return float(d["lat"]), float(d["lon"]), d.get("display_name", "")
def _geocode(adresse: str, cache: dict):
    cle = adresse.strip().lower()
    if cle in cache:
        return cache[cle]
    res = _requete_geocode(adresse)
    time.sleep(1.1)
    if res is None:
        cache[cle] = None
        return None
    lat, lon, display = res
    cache[cle] = {"lat": lat, "lon": lon, "display": display}
    return cache[cle]
def _categorie(entreprise: str, poste: str) -> str:
    e, p = (entreprise or "").lower(), (poste or "").lower()
    blob = e + " " + p
    if "veilleur" in p or "nuit" in p or "hotel" in e or "hôtel" in e:
        return "hotel_nuit"
    if any(k in blob for k in ("proprete", "propreté", "entretien", "menage",
                               "ménage", "nettoyage", "agent de service",
                               "shiva", "samsic", "derichebourg", "gsf", "onet")):
        return "services"
    if any(k in blob for k in ("inventoriste", "inventaire", "rgis")):
        return "inventaire"
    if any(k in e for k in ("monoprix", "super u", "intermarche", "intermarché",
                            "carrefour", "franprix", "lidl", "leclerc")) \
            or any(k in p for k in ("libre-service", "libre service", "caisse",
                                    "rayon", "magasin", "employe de magasin",
                                    "employé de magasin")):
        return "commerce"
    if any(k in e for k in ("starbucks", "columbus")) or "barista" in p:
        return "cafe"
    if any(k in blob for k in ("manoeuvre", "manœuvre", "tp", "btp", "production",
                               "fabrication", "manutention", "preparateur",
                               "préparateur", "operateur", "opérateur",
                               "logistique", "etancheite", "interim", "intérim")):
        return "industrie_interim"
    return "restauration"
CAT_LABELS = {
    "restauration": "Restauration / fast-food",
    "cafe": "Café / barista",
    "commerce": "Commerce alimentaire",
    "hotel_nuit": "Hôtel / veilleur de nuit",
    "services": "Propreté / ménage à domicile",
    "inventaire": "Inventaire",
    "industrie_interim": "Industrie / intérim",
    "autre": "Autre",
}
def construire(verbose: bool = True) -> dict:
    suivi = _lire_json(SUIVI_PATH, {"candidatures": []})
    cache = _lire_json(GEOCACHE_PATH, {})
    contacts = _lire_json(CONTACTS_PATH, {})
    lieux = []
    sans_geo = []
    traites = []
    for cand in suivi.get("candidatures", []):
        oid = cand.get("id")
        if not oid:
            continue
        offre = _lire_json(OFFRES / oid / "offre.json", {})
        adresse = (offre.get("lieu") or cand.get("lieu") or "").strip()
        entreprise = offre.get("entreprise") or cand.get("entreprise") or ""
        poste = offre.get("titre_offre") or cand.get("titre") or ""
        url = offre.get("url") or cand.get("url") or ""
        contact = contacts.get(oid, {})
        if contact.get("masque"):
            traites.append({
                "id": oid,
                "entreprise": entreprise,
                "poste": poste,
                "adresse": adresse,
                "statut": cand.get("statut", ""),
                "date": cand.get("date_creation", ""),
                "date_envoi": cand.get("date_envoi"),
                "url": url,
                "note": contact.get("note", "") or cand.get("notes", ""),
                "has_cv": bool(cand.get("cv_pdf")),
                "has_lm": bool(cand.get("lettre_pdf") or cand.get("lettre_txt")),
            })
            continue
        lat = lon = None
        geocoded = False
        if contact.get("lat") and contact.get("lon"):
            lat, lon = contact["lat"], contact["lon"]
            geocoded = True
        elif _adresse_exploitable(adresse):
            g = _geocode(adresse, cache)
            if g:
                lat, lon, geocoded = g["lat"], g["lon"], True
        entree = {
            "id": oid,
            "entreprise": entreprise,
            "poste": poste,
            "adresse": adresse,
            "lat": lat,
            "lon": lon,
            "geocoded": geocoded,
            "categorie": _categorie(entreprise, poste),
            "statut": cand.get("statut", ""),
            "date": cand.get("date_creation", ""),
            "url": url,
            "tel": contact.get("tel", ""),
            "horaires": contact.get("horaires", ""),
            "site": contact.get("site", ""),
            "note": contact.get("note", "") or cand.get("notes", ""),
            "has_cv": bool(cand.get("cv_pdf")),
            "has_lm": bool(cand.get("lettre_pdf") or cand.get("lettre_txt")),
        }
        if geocoded:
            lieux.append(entree)
        else:
            sans_geo.append(entree)
        if verbose:
            etat = "OK " if geocoded else "-- "
            print(f"  [{etat}] {entreprise} | {adresse[:48]}")
    _ecrire_json(GEOCACHE_PATH, cache)
    sortie = {
        "generated_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "centre": RENNES_CENTRE,
        "cat_labels": CAT_LABELS,
        "count": len(lieux),
        "count_sans_geo": len(sans_geo),
        "count_traites": len(traites),
        "lieux": lieux,
        "sans_geo": sans_geo,
        "traites": traites,
    }
    _ecrire_json(CARTE_PATH, sortie)
    if verbose:
        print(f"\n{len(lieux)} lieux geolocalises, {len(sans_geo)} sans adresse "
              f"exploitable. -> {CARTE_PATH}")
    return sortie
if __name__ == "__main__":
    construire()