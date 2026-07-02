import argparse
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts import ingest, generate, suivi
from scripts.config import ARCHIVES
from scripts.logger_setup import get_logger
log = get_logger()
def traiter() -> None:
    fichiers = ingest.collecter_inbox()
    if not fichiers:
        log.info("Aucune offre à traiter dans l'inbox.")
        suivi.generer_tableau_de_bord()
        return
    log.info("%d offre(s) à traiter.", len(fichiers))
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    ok, echecs = 0, 0
    for fichier in fichiers:
        offre = ingest.charger_offre(fichier)
        if not offre:
            echecs += 1
            continue
        try:
            oid, dossier = ingest.creer_dossier_offre(offre)
            resultat = generate.generer(offre, oid, dossier)
            suivi.ajouter(oid, offre, resultat)
            dest = ARCHIVES / fichier.name
            if dest.exists():
                dest = ARCHIVES / f"{fichier.stem}_{oid}{fichier.suffix}"
            shutil.move(str(fichier), str(dest))
            log.info("Candidature prête : %s", oid)
            ok += 1
        except Exception as e:
            log.error("Échec sur %s : %s", fichier.name, e)
            echecs += 1
    suivi.generer_tableau_de_bord()
    log.info("Terminé : %d réussie(s), %d échec(s).", ok, echecs)
def main() -> None:
    parser = argparse.ArgumentParser(description="Arsenal_Candidatures")
    parser.add_argument("--suivi", action="store_true",
                        help="régénère seulement le tableau de bord")
    parser.add_argument("--envoyee", metavar="ID",
                        help="marque une candidature comme envoyée")
    parser.add_argument("--scraper", nargs="?", const="francetravail",
                        choices=["francetravail", "crous"], metavar="SOURCE",
                        help="scrape les offres (francetravail par défaut, ou crous)")
    args = parser.parse_args()
    if args.envoyee:
        ok = suivi.marquer_envoyee(args.envoyee)
        suivi.generer_tableau_de_bord()
        sys.exit(0 if ok else 1)
    if args.scraper:
        from scripts import scraper as scraper_module
        try:
            res = scraper_module.scraper(args.scraper)
            log.info("Scraper terminé : %d offre(s) trouvée(s).", res["total"])
        except Exception as e:
            log.error("Scraper échoué : %s", e)
            sys.exit(1)
        return
    if args.suivi:
        suivi.generer_tableau_de_bord()
        return
    traiter()
if __name__ == "__main__":
    main()