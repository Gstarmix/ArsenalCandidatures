import json
import re
from datetime import datetime
from scripts.config import OFFRES_STORE
from scripts.logger_setup import get_logger
log = get_logger()
INTERETS = ["nouveau", "interesse", "ignore"]
AVANCEMENTS = ["rien", "cv_genere", "envoye"]
STATUTS = ["nouveau", "interesse", "cv_genere", "envoye", "ignore"]
LIBELLES = {
    "nouveau": "Nouveau",
    "interesse": "Intéressé",
    "cv_genere": "CV généré",
    "envoye": "Envoyé",
    "ignore": "Ignoré",
}
MOTS_EXCLUS = [
    ("travaux publics", r"travaux public"),
    ("VRD", r"\bvrd\b"),
    ("canalisateur", r"canalisateur"),
    ("TP", r"\btp\b"),
    ("nacelle", r"nacelle"),
    ("voirie", r"voirie"),
]
_EXCLUS = [(lib, re.compile(motif, re.IGNORECASE)) for lib, motif in MOTS_EXCLUS]
def motif_exclu(titre: str) -> str:
    for libelle, regex in _EXCLUS:
        if regex.search(titre or ""):
            return libelle
    return ""
def appliquer_filtres(data: dict) -> int:
    n = 0
    for offre in data.get("offres", []):
        if (offre.get("interet") != "nouveau"
                or offre.get("avancement", "rien") != "rien"):
            continue
        motif = motif_exclu(offre.get("titre", ""))
        if motif:
            offre["interet"] = "ignore"
            offre["filtre_auto"] = motif
            offre["interet_le"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            n += 1
    return n
def statut_derive(offre: dict) -> str:
    avancement = offre.get("avancement", "rien")
    if avancement == "envoye":
        return "envoye"
    if avancement == "cv_genere":
        return "cv_genere"
    interet = offre.get("interet", "nouveau")
    if interet in ("interesse", "ignore"):
        return interet
    return "nouveau"
def cle_offre(offre: dict) -> str:
    return (offre.get("id") or offre.get("cle") or offre.get("url")
            or f"{offre.get('titre', '')}|{offre.get('lieu', '')}")
def _migrer(offre: dict) -> dict:
    if "interet" in offre and "avancement" in offre:
        return offre
    ancien = offre.pop("statut", "nouveau")
    table = {
        "nouveau": ("nouveau", "rien"),
        "interesse": ("interesse", "rien"),
        "ignore": ("ignore", "rien"),
        "cv_genere": ("interesse", "cv_genere"),
        "envoye": ("interesse", "envoye"),
    }
    interet, avancement = table.get(ancien, ("nouveau", "rien"))
    offre.setdefault("interet", interet)
    offre.setdefault("avancement", avancement)
    return offre
def charger() -> dict:
    if OFFRES_STORE.exists():
        try:
            data = json.loads(OFFRES_STORE.read_text(encoding="utf-8"))
            for offre in data.get("offres", []):
                _migrer(offre)
            return data
        except json.JSONDecodeError:
            log.warning("offres.json illisible : réinitialisation.")
    return {"meta": {}, "offres": []}
def sauver(data: dict) -> None:
    data.setdefault("meta", {})
    data["meta"]["derniere_maj"] = datetime.now().isoformat(timespec="seconds")
    data["meta"]["total"] = len(data.get("offres", []))
    OFFRES_STORE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def fusionner(offres_collectees: list, source: str) -> int:
    data = charger()
    index = {o.get("cle"): o for o in data["offres"]}
    ajouts = 0
    for brute in offres_collectees:
        cle = cle_offre(brute)
        if cle in index:
            existante = index[cle]
            for champ in ("titre", "entreprise", "lieu", "contrat", "url", "score"):
                if brute.get(champ):
                    existante[champ] = brute[champ]
        else:
            data["offres"].append({
                "cle": cle,
                "titre": brute.get("titre", ""),
                "entreprise": brute.get("entreprise", ""),
                "lieu": brute.get("lieu", ""),
                "contrat": brute.get("contrat", ""),
                "url": brute.get("url", ""),
                "score": brute.get("score", 0),
                "source": source,
                "interet": "nouveau",
                "avancement": "rien",
                "date_ajout": datetime.now().strftime("%Y-%m-%d"),
                "cv_pdf": None,
                "lettre_pdf": None,
                "lettre_txt": None,
                "notes": "",
            })
            index[cle] = data["offres"][-1]
            ajouts += 1
    auto = appliquer_filtres(data)
    if auto:
        log.info("Filtres : %d offre(s) auto-ignorée(s) (titre exclu).", auto)
    sauver(data)
    log.info("Magasin d'offres : %d ajout(s), %d offre(s) au total.",
             ajouts, len(data["offres"]))
    return ajouts
def maj_offre(cle: str, **champs) -> bool:
    data = charger()
    for offre in data["offres"]:
        if offre.get("cle") == cle:
            offre.update(champs)
            sauver(data)
            return True
    return False