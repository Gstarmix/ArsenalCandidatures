import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import generate
from scripts.config import OFFRES
from scripts.logger_setup import get_logger
log = get_logger()
def regenerer(oids) -> None:
    ok, echecs = 0, 0
    total = len(oids)
    for n, oid in enumerate(oids, 1):
        dossier = OFFRES / oid
        offre_path = dossier / "offre.json"
        if not offre_path.exists():
            log.error("offre.json introuvable : %s", offre_path)
            echecs += 1
            continue
        offre = json.loads(offre_path.read_text(encoding="utf-8"))
        try:
            generate.generer(offre, oid, dossier)
            log.info("(%d/%d) Regeneree : %s", n, total, oid)
            ok += 1
        except Exception as e:
            log.error("(%d/%d) Echec sur %s : %s", n, total, oid, e)
            echecs += 1
    log.info("Termine : %d reussi(s), %d echec(s).", ok, echecs)
if __name__ == "__main__":
    regenerer(sys.argv[1:])