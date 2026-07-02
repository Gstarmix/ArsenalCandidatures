# Arsenal_Candidatures

Outil personnel de **recherche d'emploi et de génération de candidatures ciblées**
pour Gaylord ABOEKA.

Le logiciel scrape les offres d'emploi, les rassemble dans un tableau de bord
(interface graphique), et génère pour chacune un **CV** et une **lettre de
motivation** adaptés, tout en suivant l'état de chaque candidature.

> Génération via le CLI `claude --print` (abonnement, pas d'API payante). Projet
> calqué sur l'écosystème `BotGSTAR/Arsenal_Arguments`.

---

## L'outil en images

Le tableau de bord : offres scrapées, filtres, score, et les actions (générer
CV + lettre, marquer envoyé, notes) :

![Tableau de bord](screenshots/tableau-de-bord.png)

La carte des candidatures (mini-CRM) : chaque point est un lieu de candidature,
coloré par statut, avec filtres et itinéraire depuis le téléphone :

![Carte des candidatures](screenshots/carte.png)

---

## Règle d'or : non négociable

Le générateur n'utilise **que** le contenu de `datas/profil_gaylord.json`. Il adapte la
*mise en avant* et la *formulation* à chaque offre, mais **n'invente jamais une
expérience, un diplôme ou une compétence**. Un CV doit toujours être 100 % vrai et
défendable en entretien.

---

## Arborescence

```
Arsenal_Candidatures/
├── 00_inbox_json/     Les JSON capturés par l'extension arrivent ici
├── 01_offres/         Offres traitées (un sous-dossier par offre)
├── 02_cv_generes/     CV générés (un sous-dossier horodaté par candidature)
├── 03_lettres/        Lettres de motivation (un sous-dossier horodaté par candidature)
├── 04_envoyes/        Candidatures réellement envoyées (archivage)
├── datas/
│   ├── profil_gaylord.json     SOURCE DE VÉRITÉ (à tenir à jour)
│   ├── offres.json             Magasin des offres et de leur statut
│   └── suivi_candidatures.json Suivi central de toutes les candidatures
├── templates/         Gabarits LaTeX (CV + lettre)
├── scripts/           Code Python (scraper, génération, suivi, magasin d'offres)
├── extension/         Extension Chrome/Edge de capture d'offres
├── _logs/             Journaux horodatés
├── _archives/         Anciennes versions ; CV et lettres des offres ignorées
├── gui.py                     Interface graphique (application principale)
├── run_candidatures.py        Orchestrateur en ligne de commande
├── start_gui.vbs              Lanceur de l'interface graphique (double-clic)
├── start_candidatures.vbs     Lanceur du traitement (double-clic)
└── start_scraper.vbs          Lanceur du scraper d'offres (double-clic)
```

## Le flux complet

1. **Collecte** : le scraper interroge France Travail (Rennes + 10 km) ou le
   Crous Rennes Bretagne (rubriques emploi étudiant) et remplit le magasin
   d'offres `datas/offres.json`. On peut aussi capturer une offre précise avec
   l'extension navigateur.
2. **Tri** : dans l'interface (`gui.py`), toutes les offres s'affichent dans un
   tableau triable (clic sur un en-tête de colonne) ; on marque celles qui
   intéressent, on ignore les autres. Ignorer une offre dont le CV est déjà
   généré archive ce CV et sa lettre ; remettre l'offre en « intéressé » les
   restaure.
3. **Génération** : pour une offre retenue, l'outil appelle `claude --print` avec
   le profil et l'offre, produit un CV et une lettre ciblés sur le secteur et le
   vocabulaire de l'annonce (PDF + texte) et les compile.
4. **Suivi** : l'offre passe au statut « CV généré », puis « Envoyé » une fois la
   candidature faite ; la date et l'heure de chaque étape sont affichées dans le
   tableau. `datas/suivi_candidatures.json` garde les dates et les rappels de
   relance (J+7).
5. **Tableau de bord** : `_logs/tableau_de_bord.md` liste les candidatures en cours,
   à relancer aujourd'hui, et sans réponse depuis trop longtemps.

## Installation

### 1. Ton profil

Copie `datas/profil_exemple.json` en `datas/profil_gaylord.json`, puis remplis-le avec
tes informations **réelles et vérifiables**. Ce fichier n'est pas versionné (données
personnelles).

### 2. Python (3.12)

```
pip install -r requirements.txt
```

XeLaTeX (MiKTeX) est requis pour compiler les PDF.

### 3. Extension Chrome / Edge

1. Ouvre `chrome://extensions` (ou `edge://extensions`).
2. Active le **Mode développeur**.
3. **Charger l'extension non empaquetée** → choisis le dossier `extension/`.
4. L'icône *Arsenal Candidatures* apparaît dans la barre d'outils.

## Utilisation

### Interface graphique (recommandé)

Double-clic sur **`start_gui.vbs`** (ou `python gui.py`). Tout se pilote depuis
cette fenêtre : scraper les offres, marquer celles qui intéressent, générer le
CV + la lettre (à l'unité ou en lot pour toutes les offres « Intéressé »), ouvrir
les fichiers produits et suivre les candidatures envoyées.

### En ligne de commande

- Lancer un traitement : double-clic sur `start_candidatures.vbs`
  (ou `python run_candidatures.py`).
- Chercher des offres : double-clic sur `start_scraper.vbs` (ou
  `python run_candidatures.py --scraper`). Par défaut : France Travail,
  Rennes + 10 km → `_logs/offres_francetravail.md`. Variante jobs étudiants du
  Crous : `python run_candidatures.py --scraper crous`.
- Voir l'état des candidatures : ouvre `_logs/tableau_de_bord.md`.
- Marquer une candidature comme envoyée :
  `python run_candidatures.py --envoyee <id_offre>`.

## Avertissement

L'extension lit **uniquement la page que tu consultes toi-même**, à ta demande
(au clic). C'est un outil personnel d'aide à la candidature, pas un robot d'aspiration
de masse.