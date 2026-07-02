import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from scripts.config import (PROFIL_PATH, PHOTO_PATH, CV_TEMPLATE,
                            LETTRE_TEMPLATE, CV_OUT, LETTRES_OUT, XELATEX)
from scripts.claude_engine import call_claude
from scripts.logger_setup import get_logger
log = get_logger()
_TEX = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
}
_MARQUEURS = {
    "—": "-", "–": "-", "―": "-", "−": "-",
    "…": "...",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "•": "-",
    " ": " ", " ": " ", " ": " ",
}
def _nettoyer_marqueurs(texte) -> str:
    texte = str(texte or "")
    for marqueur, remplacement in _MARQUEURS.items():
        texte = texte.replace(marqueur, remplacement)
    return texte
def _assainir(obj):
    if isinstance(obj, str):
        return _nettoyer_marqueurs(obj)
    if isinstance(obj, list):
        return [_assainir(x) for x in obj]
    if isinstance(obj, dict):
        return {cle: _assainir(val) for cle, val in obj.items()}
    return obj
def tex(value) -> str:
    return "".join(_TEX.get(ch, ch) for ch in _nettoyer_marqueurs(value))
def _profil() -> dict:
    return json.loads(PROFIL_PATH.read_text(encoding="utf-8"))
def _prompt(profil: dict, offre: dict) -> str:
    offre_min = {k: offre.get(k) for k in (
        "titre_offre", "entreprise", "lieu", "type_contrat",
        "description_structuree", "texte_page")}
    return f"""Tu prépares une candidature CIBLÉE. Réponds en français.
PROFIL DU CANDIDAT (source de vérité) :
{json.dumps(profil, ensure_ascii=False, indent=2)}
OFFRE D'EMPLOI VISÉE :
{json.dumps(offre_min, ensure_ascii=False, indent=2)}
RÈGLE ABSOLUE D'INTÉGRITÉ : utilise UNIQUEMENT des faits présents dans le
PROFIL. N'invente jamais une expérience, un employeur, une compétence, une
date, un diplôme ni un chiffre. En cas de doute, omets. Le résultat doit être
défendable mot pour mot en entretien. Cette règle prime sur le ciblage : on ne
fabrique pas un fait pour coller à l'offre, on choisit et on reformule les vrais.
CIBLAGE (objectif principal) : la candidature ne doit PAS être générique. Avant
de rédiger, analyse le texte de l'offre et repère :
  - l'entreprise ou l'agence, et son secteur d'activité réel ;
  - les tâches concrètes du poste, ce qu'on fera vraiment au quotidien ;
  - les outils, l'environnement et les contraintes cités (cadences, froid,
    port de charges, normes d'hygiène, travail en équipe, horaires postés...) ;
  - le vocabulaire métier exact employé dans l'annonce.
Ensuite, RELIE le profil réel de Gaylord à ces éléments :
  - reprends le vocabulaire de l'offre pour décrire ce qu'il a réellement fait
    (une même tâche se nomme de façon générique ou avec les mots du métier visé) ;
  - mets en avant l'expérience, la formation ou la qualité du profil qui
    répond le plus directement à un besoin nommé dans l'offre ;
  - cite au moins un élément concret de l'offre (secteur, type de produit,
    contrainte, mission) dans l'accroche ET dans la lettre, pour montrer que la
    candidature a été pensée pour CE poste précis et non recopiée.
REFORMULATION DES EXPÉRIENCES : pour chaque expérience que tu mets en avant, tu
peux réécrire son champ "details" afin de reprendre le vocabulaire de l'offre,
via le champ "experiences_reformulees" (clé = indice de l'expérience SOUS FORME
DE TEXTE, valeur = nouveau "details"). RÈGLE STRICTE : c'est une reformulation,
pas un ajout. Chaque fait de la version reformulée doit déjà figurer dans le
"details" d'origine de cette expérience. N'ajoute aucune tâche, aucun outil,
aucun logiciel, aucun chiffre, aucune responsabilité ni aucun résultat absent de
l'original. Le poste, l'employeur et les dates ne sont jamais modifiables. Si une
expérience n'a pas besoin d'être reformulée, ne mets pas sa clé.
NON-RÉPÉTITION (important) : sur le CV, la barre latérale affiche déjà, telles
quelles, les "Atouts" du candidat, c'est-à-dire la liste profil["qualites"]
(dont "Bonne condition physique"). Ne répète donc PAS dans l'accroche ni dans
"competences_cles" une idée déjà présente dans ces qualités. En particulier,
n'emploie "condition physique" / "bonne condition physique" qu'à un seul endroit
(les Atouts) : ne la remets ni dans l'accroche, ni dans les compétences clés.
Pour "competences_cles", privilégie des savoir-faire opérationnels et concrets,
formulés avec le vocabulaire de l'offre (par exemple aptitude au travail debout
et au port de charges, tenue des cadences, respect des règles d'hygiène, service
et relationnel client, travail en équipe), sans doublonner les Atouts.
STYLE : rédige dans un français fluide et soigné, en reliant les idées par des
connecteurs logiques (ainsi, par ailleurs, en effet, de plus, c'est pourquoi,
dès lors). Reste naturel et sincère, sans tournures grandiloquentes ni mots
rares. N'utilise JAMAIS de tiret cadratin ni de tiret demi-cadratin :
emploie une virgule, un point ou un tiret simple (-). Pas de guillemets ni
d'apostrophes courbes, pas de points de suspension unicode.
POSITIONNEMENT : ne présente JAMAIS le candidat comme "étudiant" dans l'accroche
ni dans la lettre (ces candidatures visent un emploi ou des missions, pas une
alternance). Mets-le en avant par ses qualités, sa fiabilité, sa disponibilité
immédiate à temps plein et sa motivation, sans coller d'étiquette de statut.
Réponds UNIQUEMENT par un objet JSON valide (aucun autre texte, pas de balises de
code), de cette forme exacte :
{{
  "titre_cv": "intitulé court repris du poste réel de l'offre",
  "accroche": "2 phrases personnalisées citant le secteur ou la mission de l'offre et reliées à un fait réel du profil",
  "ordre_experiences": [indices des expériences du profil, classées de la plus récente à la plus ancienne (ordre chronologique inverse)],
  "experiences_reformulees": {{"0": "details de l'expérience 0 reformulé avec le vocabulaire de l'offre, sans aucun fait nouveau"}},
  "competences_cles": ["4 à 6 compétences RÉELLES du profil, formulées avec le vocabulaire de l'offre"],
  "lettre_objet": "objet de la lettre de motivation, reprenant l'intitulé du poste",
  "lettre_paragraphes": ["p1 : pourquoi ce poste et ce secteur précisément", "p2 : ce que le profil réel apporte aux besoins nommés dans l'offre", "p3 : disponibilité et souhait d'un entretien, SANS aucune formule de politesse finale (du type 'je vous prie d'agréer' ou 'salutations') : elle est déjà ajoutée automatiquement par le gabarit"]
}}
Les indices de "ordre_experiences" sont les positions dans profil["experiences"]
(0 = la première). Le profil liste DÉJÀ les expériences de la plus récente à la
plus ancienne : conserve donc cet ordre chronologique inverse (en général
[0, 1, 2, ...]), et ne réordonne pas par pertinence. N'inclus que des indices
valides.
UNIFORMITÉ DES DESCRIPTIONS : que tu reformules ou non, les "details" des
expériences mises en avant doivent suivre la MÊME logique d'une entrée à l'autre,
pour un rendu homogène sur le CV : une formulation qui pose d'abord le contexte
ou le rôle, puis enchaîne sur les tâches concrètes au vocabulaire de l'offre,
avec une longueur comparable (une à deux phrases). Ne répète pas l'intitulé du
poste dans le "details" (il figure déjà en titre)."""
def _extraire_json(reponse: str) -> dict:
    txt = re.sub(r"```(?:json)?", "", reponse).strip()
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Aucun JSON exploitable dans la réponse de claude.")
    return json.loads(txt[start:end + 1])
def _contient_tiret_cadratin(obj) -> bool:
    if isinstance(obj, str):
        return "—" in obj or "–" in obj
    if isinstance(obj, list):
        return any(_contient_tiret_cadratin(x) for x in obj)
    if isinstance(obj, dict):
        return any(_contient_tiret_cadratin(v) for v in obj.values())
    return False
def _reformuler_sans_tiret(plan: dict) -> dict:
    if not _contient_tiret_cadratin(plan):
        return plan
    log.info("Tiret cadratin détecté : demande de reformulation à claude.")
    demande = (
        "Le JSON ci-dessous contient un ou plusieurs tirets cadratins ou "
        "demi-cadratins. Réécris-le en REFORMULANT les phrases concernées "
        "dans un français naturel et fluide, sans aucun de ces tirets, et sans "
        "te contenter de les remplacer par un autre signe. Conserve le sens et "
        "exactement la même structure JSON. Réponds uniquement par le JSON "
        "corrigé.\n\n" + json.dumps(plan, ensure_ascii=False, indent=2)
    )
    try:
        corrige = _extraire_json(call_claude(demande))
        if isinstance(corrige, dict) and corrige:
            return corrige
    except Exception as e:
        log.warning("Reformulation impossible (%s).", e)
    return plan
def _bloc_experiences(profil: dict, ordre, reformulations=None) -> str:
    exps = profil.get("experiences", [])
    reform = reformulations if isinstance(reformulations, dict) else {}
    if not isinstance(ordre, list) or not ordre:
        ordre = list(range(len(exps)))
    lignes, vus = [], set()
    for i in ordre:
        if not isinstance(i, int) or i in vus or not (0 <= i < len(exps)):
            continue
        vus.add(i)
        e = exps[i]
        details = reform.get(str(i)) or reform.get(i) or e.get("details")
        lignes.append(r"\cventry{%s}{%s}{%s}{%s}" % (
            tex(e.get("poste")), tex(e.get("structure")),
            tex(e.get("periode")), tex(details)))
    return "\n".join(lignes)
def _bloc_formations(profil: dict) -> str:
    lignes = []
    for f in profil.get("formations", []):
        lignes.append(r"\cventry{%s}{%s}{%s}{%s}" % (
            tex(f.get("intitule")), tex(f.get("etablissement")),
            tex(f.get("periode")), tex(f.get("details"))))
    return "\n".join(lignes)
def _rendre(template: Path, remplacements: dict) -> str:
    txt = template.read_text(encoding="utf-8")
    for cle, valeur in remplacements.items():
        txt = txt.replace(f"<<<{cle}>>>", valeur)
    return txt
def _puces(items) -> str:
    return "\n".join(r"\textbullet\ %s\par" % tex(x) for x in items if x)
def _rendre_cv(profil: dict, plan: dict) -> str:
    ident = profil.get("identite", {})
    photo = ""
    if PHOTO_PATH.exists():
        chemin = str(PHOTO_PATH).replace("\\", "/")
        photo = (r"\includegraphics[width=3.5cm,height=3.5cm,"
                 r"keepaspectratio]{%s}" % chemin)
    coordonnees = [ident.get("ville"), ident.get("telephone"),
                   ident.get("email")]
    if ident.get("mobilite"):
        coordonnees.append(f"Mobilité : {ident['mobilite']}")
    lignes_contact = [tex(x) + r"\par" for x in coordonnees if x]
    portfolio = (ident.get("portfolio") or "").strip()
    if portfolio:
        libelle = re.sub(r"^https?://", "", portfolio).rstrip("/")
        lignes_contact.append(
            r"Portfolio : \href{%s}{%s}\par" % (portfolio, tex(libelle)))
    contact = "\n".join(lignes_contact)
    langues = [f"{l.get('langue')} ({l.get('niveau')})"
               for l in profil.get("langues", [])]
    return _rendre(CV_TEMPLATE, {
        "PHOTO": photo,
        "NOM": tex(f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()),
        "TITRE": tex(plan.get("titre_cv", "")),
        "DISPO": tex(profil.get("disponibilite", "")),
        "CONTACT": contact,
        "COMPETENCES": _puces(plan.get("competences_cles", [])),
        "QUALITES": _puces(profil.get("qualites", [])),
        "LANGUES": _puces(langues),
        "ACCROCHE": tex(plan.get("accroche", "")),
        "EXPERIENCES": _bloc_experiences(profil, plan.get("ordre_experiences"),
                                         plan.get("experiences_reformulees")),
        "FORMATIONS": _bloc_formations(profil),
    })
def _rendre_lettre(profil: dict, offre: dict, plan: dict) -> str:
    ident = profil.get("identite", {})
    coord = r" \\ ".join(filter(None, [
        tex(ident.get("ville")), tex(ident.get("telephone")),
        tex(ident.get("email"))]))
    corps = "\n\n".join(tex(p) for p in plan.get("lettre_paragraphes", []))
    ville = (ident.get("ville", "") or "").split("(")[0].strip() or "Rennes"
    return _rendre(LETTRE_TEMPLATE, {
        "NOM": tex(f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()),
        "COORD": coord,
        "ENTREPRISE": tex(offre.get("entreprise") or "Service recrutement"),
        "LIEU": tex(offre.get("lieu", "")),
        "VILLE_DATE": tex(f"{ville}, le {datetime.now():%d/%m/%Y}"),
        "OBJET": tex(plan.get("lettre_objet", "Candidature")),
        "CORPS": corps,
    })
def _rendre_lettre_txt(profil: dict, offre: dict, plan: dict) -> str:
    ident = profil.get("identite", {})
    nom = f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()
    ville = (ident.get("ville", "") or "").split("(")[0].strip() or "Rennes"
    lignes = [nom]
    for champ in (ident.get("ville"), ident.get("telephone"),
                  ident.get("email")):
        if champ:
            lignes.append(champ)
    lignes.append("")
    lignes.append(offre.get("entreprise") or "Service recrutement")
    if offre.get("lieu"):
        lignes.append(offre["lieu"])
    lignes += ["",
               f"{ville}, le {datetime.now():%d/%m/%Y}", "",
               f"Objet : {plan.get('lettre_objet', 'Candidature')}", "",
               "Madame, Monsieur,", ""]
    for paragraphe in plan.get("lettre_paragraphes", []):
        lignes.append(str(paragraphe).strip())
        lignes.append("")
    lignes.append("Je vous prie d'agréer, Madame, Monsieur, l'expression de "
                  "mes salutations distinguées.")
    lignes += ["", nom]
    return _nettoyer_marqueurs("\n".join(lignes)) + "\n"
def _compiler(tex_path: Path):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        for _ in range(2):
            subprocess.run(
                [XELATEX, "-interaction=nonstopmode", "-halt-on-error",
                 tex_path.name],
                cwd=tex_path.parent, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
                creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.error("XeLaTeX indisponible ou trop lent : %s", e)
        return None
    pdf = tex_path.with_suffix(".pdf")
    if pdf.exists():
        for ext in (".aux", ".log", ".out"):
            tex_path.with_suffix(ext).unlink(missing_ok=True)
        return pdf
    log.error("Compilation échouée : %s (voir le .log)", tex_path.name)
    return None
def generer(offre: dict, oid: str, dossier_offre: Path) -> dict:
    profil = _profil()
    log.info("Génération de la candidature : %s", oid)
    plan = _extraire_json(call_claude(_prompt(profil, offre)))
    plan = _reformuler_sans_tiret(plan)
    plan = _assainir(plan)
    (dossier_offre / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cv_dir = CV_OUT / oid
    cv_dir.mkdir(parents=True, exist_ok=True)
    lettre_dir = LETTRES_OUT / oid
    lettre_dir.mkdir(parents=True, exist_ok=True)
    cv_tex = cv_dir / f"CV_{oid}.tex"
    cv_tex.write_text(_rendre_cv(profil, plan), encoding="utf-8")
    cv_pdf = _compiler(cv_tex)
    lettre_tex = lettre_dir / f"LM_{oid}.tex"
    lettre_tex.write_text(_rendre_lettre(profil, offre, plan), encoding="utf-8")
    lettre_pdf = _compiler(lettre_tex)
    lettre_txt = lettre_dir / f"LM_{oid}.txt"
    lettre_txt.write_text(_rendre_lettre_txt(profil, offre, plan),
                          encoding="utf-8")
    return {
        "titre_cv": plan.get("titre_cv", ""),
        "cv_tex": str(cv_tex),
        "cv_pdf": str(cv_pdf) if cv_pdf else None,
        "lettre_tex": str(lettre_tex),
        "lettre_pdf": str(lettre_pdf) if lettre_pdf else None,
        "lettre_txt": str(lettre_txt),
    }