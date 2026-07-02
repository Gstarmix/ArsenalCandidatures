import json
import urllib.parse
import urllib.request
from datetime import datetime
from scripts.config import SUIVI_PATH
from scripts import offres_store
from scripts.carte_data import (CARTE_PATH, CONTACTS_PATH, _ecrire_json,
                                _lire_json, _requete_geocode, construire)
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_UA = ("ArsenalCandidatures/1.0 (carte candidatures perso; "
       "https://github.com/Gstarmix/Arsenal_Candidatures)")
def _charger_suivi():
    return _lire_json(SUIVI_PATH, {"candidatures": []})
def _sauver_suivi(data):
    data.setdefault("meta", {})
    data["meta"]["derniere_maj"] = datetime.now().isoformat(timespec="seconds")
    _ecrire_json(SUIVI_PATH, data)
def _candidature(suivi, oid):
    return next((c for c in suivi.get("candidatures", [])
                 if c.get("id") == oid), None)
def _charger_contacts():
    return _lire_json(CONTACTS_PATH, {})
def _sauver_contacts(contacts):
    _ecrire_json(CONTACTS_PATH, contacts)
def _maj_contact(oid, **champs):
    contacts = _charger_contacts()
    entree = contacts.get(oid, {})
    entree.update(champs)
    contacts[oid] = entree
    _sauver_contacts(contacts)
def _sync_offre_par_url(url, **champs):
    if not url:
        return
    data = offres_store.charger()
    touche = False
    for offre in data.get("offres", []):
        if offre.get("url") and offre["url"] == url:
            offre.update(champs)
            touche = True
    if touche:
        offres_store.sauver(data)
def _recompter(carte):
    carte["count"] = len(carte.get("lieux", []))
    carte["count_sans_geo"] = len(carte.get("sans_geo", []))
def _patch_lieu(oid, **champs):
    carte = _lire_json(CARTE_PATH, None)
    if not carte:
        return
    for cle in ("lieux", "sans_geo"):
        for entree in carte.get(cle, []):
            if entree.get("id") == oid:
                entree.update(champs)
    _ecrire_json(CARTE_PATH, carte)
def _basculer_vers_traites(oid, cand, statut):
    carte = _lire_json(CARTE_PATH, None)
    if not carte:
        return
    src = None
    for cle in ("lieux", "sans_geo"):
        for e in carte.get(cle, []):
            if e.get("id") == oid:
                src = e
        carte[cle] = [e for e in carte.get(cle, []) if e.get("id") != oid]
    contact = _charger_contacts().get(oid, {})
    base = src or {}
    traite = {
        "id": oid,
        "entreprise": base.get("entreprise") or cand.get("entreprise", ""),
        "poste": base.get("poste") or cand.get("titre", ""),
        "adresse": base.get("adresse") or cand.get("lieu", ""),
        "statut": statut,
        "date": cand.get("date_creation", ""),
        "date_envoi": cand.get("date_envoi"),
        "url": cand.get("url", ""),
        "note": contact.get("note", "") or cand.get("notes", ""),
        "has_cv": bool(cand.get("cv_pdf")),
        "has_lm": bool(cand.get("lettre_pdf") or cand.get("lettre_txt")),
    }
    tr = [t for t in carte.get("traites", []) if t.get("id") != oid]
    tr.append(traite)
    carte["traites"] = tr
    carte["count_traites"] = len(tr)
    _recompter(carte)
    _ecrire_json(CARTE_PATH, carte)
def _promouvoir_lieu(oid, lat, lon, adresse):
    carte = _lire_json(CARTE_PATH, None)
    if not carte:
        return
    cible = None
    for cle in ("lieux", "sans_geo"):
        for entree in carte.get(cle, []):
            if entree.get("id") == oid:
                cible = entree
    if cible is None:
        return
    cible.update({"lat": lat, "lon": lon, "adresse": adresse, "geocoded": True})
    carte["sans_geo"] = [e for e in carte.get("sans_geo", [])
                         if e.get("id") != oid]
    if all(e.get("id") != oid for e in carte.get("lieux", [])):
        carte.setdefault("lieux", []).append(cible)
    _recompter(carte)
    _ecrire_json(CARTE_PATH, carte)
def marquer(oid, action):
    if action not in ("depose", "pas_interesse"):
        return {"ok": False, "erreur": "action inconnue"}
    suivi = _charger_suivi()
    cand = _candidature(suivi, oid)
    if not cand:
        return {"ok": False, "erreur": "candidature introuvable"}
    url = cand.get("url", "")
    if action == "depose":
        cand["statut"] = "envoye"
        cand["date_envoi"] = datetime.now().strftime("%Y-%m-%d")
        _sync_offre_par_url(url, avancement="envoye")
        statut = "envoye"
    else:
        cand["statut"] = "pas_interesse"
        _sync_offre_par_url(url, interet="ignore")
        statut = "pas_interesse"
    _sauver_suivi(suivi)
    _maj_contact(oid, masque=True)
    _basculer_vers_traites(oid, cand, statut)
    return {"ok": True, "statut": statut}
def restaurer(oid):
    suivi = _charger_suivi()
    cand = _candidature(suivi, oid)
    if not cand:
        return {"ok": False, "erreur": "candidature introuvable"}
    cand["statut"] = "a_envoyer"
    cand["date_envoi"] = None
    _sauver_suivi(suivi)
    _sync_offre_par_url(cand.get("url", ""), interet="nouveau", avancement="rien")
    _maj_contact(oid, masque=False)
    construire(verbose=False)
    return {"ok": True}
def maj_note(oid, note):
    note = (note or "").strip()
    suivi = _charger_suivi()
    cand = _candidature(suivi, oid)
    if not cand:
        return {"ok": False, "erreur": "candidature introuvable"}
    cand["notes"] = note
    _sauver_suivi(suivi)
    _maj_contact(oid, note=note)
    _patch_lieu(oid, note=note)
    return {"ok": True}
def maj_localisation(oid, adresse):
    adresse = (adresse or "").strip()
    if not adresse:
        return {"ok": False, "erreur": "adresse vide"}
    suivi = _charger_suivi()
    cand = _candidature(suivi, oid)
    if not cand:
        return {"ok": False, "erreur": "candidature introuvable"}
    res = _requete_geocode(adresse)
    if not res:
        return {"ok": False, "erreur": "adresse introuvable sur OpenStreetMap"}
    lat, lon, display = res
    cand["lieu"] = adresse
    _sauver_suivi(suivi)
    _maj_contact(oid, lat=lat, lon=lon)
    _promouvoir_lieu(oid, lat, lon, adresse)
    return {"ok": True, "lat": lat, "lon": lon, "display": display}
def _requete_osm_infos(nom, adresse):
    requete = " ".join(p for p in (nom, adresse) if p).strip()
    if not requete:
        return {}
    if "rennes" not in requete.lower():
        requete += ", Rennes, France"
    params = urllib.parse.urlencode({
        "q": requete, "format": "json", "limit": 1,
        "extratags": 1, "countrycodes": "fr"})
    req = urllib.request.Request(f"{_NOMINATIM}?{params}",
                                 headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception:
        return {}
    if not data:
        return {}
    extra = data[0].get("extratags") or {}
    site = (extra.get("website") or extra.get("contact:website")
            or extra.get("url") or "")
    horaires = extra.get("opening_hours") or ""
    out = {}
    if site:
        out["site"] = site
    if horaires:
        out["horaires"] = horaires
    return out
def enrichir(oid):
    suivi = _charger_suivi()
    cand = _candidature(suivi, oid)
    if not cand:
        return {"ok": False, "erreur": "candidature introuvable"}
    contacts = _charger_contacts()
    contact = contacts.get(oid, {})
    nom = cand.get("entreprise", "") or cand.get("titre", "")
    adresse = contact.get("adresse") or cand.get("lieu", "")
    infos = _requete_osm_infos(nom, adresse)
    if not infos:
        _maj_contact(oid, a_enrichir=True)
        return {"ok": True, "trouve": False, "site": contact.get("site", ""),
                "horaires": contact.get("horaires", "")}
    champs = {}
    if infos.get("site") and not contact.get("site"):
        champs["site"] = infos["site"]
    if infos.get("horaires") and not contact.get("horaires"):
        champs["horaires"] = infos["horaires"]
    champs["a_enrichir"] = False
    _maj_contact(oid, **champs)
    site = champs.get("site", contact.get("site", ""))
    horaires = champs.get("horaires", contact.get("horaires", ""))
    _patch_lieu(oid, site=site, horaires=horaires)
    return {"ok": True, "trouve": True, "site": site, "horaires": horaires}