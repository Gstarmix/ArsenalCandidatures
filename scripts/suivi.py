import json
from datetime import datetime, date, timedelta
from scripts.config import (SUIVI_PATH, DASHBOARD_PATH, RELANCE_JOURS)
from scripts.logger_setup import get_logger
log = get_logger()
def _charger() -> dict:
    if SUIVI_PATH.exists():
        try:
            return json.loads(SUIVI_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Suivi illisible : réinitialisation.")
    return {"meta": {}, "candidatures": []}
def _sauver(data: dict) -> None:
    data.setdefault("meta", {})
    data["meta"]["derniere_maj"] = datetime.now().isoformat(timespec="seconds")
    data["meta"]["total"] = len(data.get("candidatures", []))
    SUIVI_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def _jours_depuis(iso) -> int:
    try:
        return (date.today() - date.fromisoformat(iso)).days
    except (ValueError, TypeError):
        return 0
def ajouter(oid: str, offre: dict, resultat: dict) -> None:
    data = _charger()
    if any(c.get("id") == oid for c in data["candidatures"]):
        return
    today = date.today()
    data["candidatures"].append({
        "id": oid,
        "titre": resultat.get("titre_cv") or offre.get("titre_offre", ""),
        "entreprise": offre.get("entreprise", "") or "(entreprise inconnue)",
        "lieu": offre.get("lieu", ""),
        "url": offre.get("url", ""),
        "statut": "a_envoyer",
        "date_creation": today.isoformat(),
        "date_envoi": None,
        "date_relance_prevue": (today + timedelta(days=RELANCE_JOURS)).isoformat(),
        "cv_pdf": resultat.get("cv_pdf"),
        "lettre_pdf": resultat.get("lettre_pdf"),
        "lettre_txt": resultat.get("lettre_txt"),
        "notes": "",
    })
    _sauver(data)
    log.info("Suivi : candidature ajoutée (%s)", oid)
def marquer_envoyee(oid: str) -> bool:
    data = _charger()
    for c in data["candidatures"]:
        if c.get("id") == oid or oid in c.get("id", ""):
            c["statut"] = "envoyee"
            c["date_envoi"] = date.today().isoformat()
            c["date_relance_prevue"] = (
                date.today() + timedelta(days=RELANCE_JOURS)).isoformat()
            _sauver(data)
            log.info("Suivi : %s marquée envoyée.", c["id"])
            return True
    log.warning("Suivi : aucune candidature correspondant à '%s'.", oid)
    return False
def generer_tableau_de_bord() -> None:
    data = _charger()
    cands = data.get("candidatures", [])
    today = date.today()
    a_envoyer, a_relancer, en_cours, closes = [], [], [], []
    for c in cands:
        st = c.get("statut")
        if st == "a_envoyer":
            a_envoyer.append(c)
        elif st in ("refus", "acceptee"):
            closes.append(c)
        else:
            rel = c.get("date_relance_prevue")
            try:
                due = rel and date.fromisoformat(rel) <= today
            except ValueError:
                due = False
            (a_relancer if due and st in ("envoyee", "relance") else en_cours).append(c)
    out = [
        "# Tableau de bord des candidatures\n",
        f"_Mis à jour le {datetime.now():%d/%m/%Y à %H:%M}_\n",
        f"**Total : {len(cands)}** · à envoyer : {len(a_envoyer)} · "
        f"en cours : {len(en_cours)} · à relancer : {len(a_relancer)} · "
        f"clôturées : {len(closes)}\n",
    ]
    def section(titre, items, ligne):
        out.append(f"\n## {titre} ({len(items)})\n")
        if not items:
            out.append("_Rien pour le moment._\n")
        for c in items:
            out.append(ligne(c))
    section("⚠️ À RELANCER maintenant", a_relancer, lambda c:
            f"- **{c['entreprise']}** : {c['titre']} "
            f"(envoyée il y a {_jours_depuis(c.get('date_envoi'))} j) "
            f"({c.get('url', '')})")
    section("✉️ À envoyer", a_envoyer, lambda c:
            f"- **{c['entreprise']}** : {c['titre']}\n"
            f"  - CV : `{c.get('cv_pdf') or 'n.c.'}`\n"
            f"  - Lettre PDF : `{c.get('lettre_pdf') or 'n.c.'}`\n"
            f"  - Lettre texte : `{c.get('lettre_txt') or 'n.c.'}`")
    section("⏳ En cours", en_cours, lambda c:
            f"- **{c['entreprise']}** : {c['titre']} "
            f"(statut : {c['statut']}, relance prévue : "
            f"{c.get('date_relance_prevue', 'n.c.')})")
    section("📁 Clôturées", closes, lambda c:
            f"- **{c['entreprise']}** : {c['titre']} ({c['statut']})")
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    log.info("Tableau de bord régénéré : %s", DASHBOARD_PATH)