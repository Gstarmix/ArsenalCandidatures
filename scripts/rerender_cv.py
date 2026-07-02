import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import generate
from scripts.config import OFFRES, CV_OUT
from scripts.logger_setup import get_logger
log = get_logger()
def rerender(oids) -> None:
    profil = generate._profil()
    ok, echecs = 0, 0
    for oid in oids:
        plan_path = OFFRES / oid / "plan.json"
        if not plan_path.exists():
            log.error("Plan introuvable : %s", plan_path)
            echecs += 1
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        cv_dir = CV_OUT / oid
        cv_dir.mkdir(parents=True, exist_ok=True)
        cv_tex = cv_dir / f"CV_{oid}.tex"
        cv_tex.write_text(generate._rendre_cv(profil, plan), encoding="utf-8")
        if generate._compiler(cv_tex):
            log.info("CV re-rendu : %s", oid)
            ok += 1
        else:
            log.error("Compilation echouee : %s", oid)
            echecs += 1
    log.info("Termine : %d reussi(s), %d echec(s).", ok, echecs)
if __name__ == "__main__":
    rerender(sys.argv[1:])