import shutil
from pathlib import Path
from scripts.config import ARCHIVES
from scripts.logger_setup import get_logger
log = get_logger()
CANDIDATURES_IGNOREES = ARCHIVES / "candidatures_ignorees"
_CHAMPS_FICHIERS = ("cv_pdf", "lettre_pdf", "lettre_txt")
def _dossiers_candidature(offre: dict) -> list:
    dossiers = []
    for champ in _CHAMPS_FICHIERS:
        chemin = offre.get(champ)
        if chemin:
            parent = Path(chemin).parent
            if parent not in dossiers:
                dossiers.append(parent)
    return dossiers
def _rechemins(offre: dict, correspondance: dict) -> dict:
    maj = {}
    for champ in _CHAMPS_FICHIERS:
        chemin = offre.get(champ)
        if chemin:
            ancien = str(Path(chemin).parent)
            if ancien in correspondance:
                maj[champ] = str(correspondance[ancien] / Path(chemin).name)
    return maj
def archiver(offre: dict) -> dict:
    deplacements, correspondance = [], {}
    for dossier in _dossiers_candidature(offre):
        if not dossier.exists():
            continue
        dst = CANDIDATURES_IGNOREES / dossier.parent.name / dossier.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(dossier), str(dst))
        deplacements.append([str(dossier), str(dst)])
        correspondance[str(dossier)] = dst
        log.info("Archivé : %s -> %s", dossier, dst)
    maj = _rechemins(offre, correspondance)
    maj["avancement"] = "rien"
    maj["archive"] = {
        "avancement": offre.get("avancement", "rien"),
        "dossiers": deplacements,
    }
    return maj
def restaurer(offre: dict) -> dict:
    trace = offre.get("archive") or {}
    correspondance = {}
    for original, archive in trace.get("dossiers", []):
        archive_p, original_p = Path(archive), Path(original)
        if archive_p.exists():
            original_p.parent.mkdir(parents=True, exist_ok=True)
            if original_p.exists():
                shutil.rmtree(original_p)
            shutil.move(str(archive_p), str(original_p))
            log.info("Restauré : %s -> %s", archive_p, original_p)
        correspondance[str(archive_p)] = original_p
    maj = _rechemins(offre, correspondance)
    maj["avancement"] = trace.get("avancement", "cv_genere")
    maj["archive"] = None
    return maj