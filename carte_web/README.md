# Carte des candidatures (Rennes)

Une carte interactive de tous les lieux où Gaylord a une candidature préparée :
filtrable, géolocalisable depuis le téléphone, avec itinéraire vélo vers Google
Maps. Pensée pour être utilisée sur Android pendant une tournée.

## Lancer

```powershell
# Depuis la racine du projet :
.\start_carte.ps1            # serveur local seul (http://127.0.0.1:5681)
.\start_carte.ps1 -Serve     # + HTTPS tailnet-only (téléphone via Tailscale)
.\start_carte.ps1 -Public    # + HTTPS PUBLIC via Tailscale Funnel (4G/5G)
.\start_carte.ps1 -Off       # coupe Serve et Funnel
```

- **PC** : http://127.0.0.1:5681
- **Téléphone (recommandé)** : `.\start_carte.ps1 -Serve`, active Tailscale sur le
  tel, puis ouvre l'**URL HTTPS** `https://<host>.tail<id>.ts.net` affichée.
- **Téléphone en 4G/5G sans Tailscale** : `.\start_carte.ps1 -Public` (URL Funnel
  publique, protégée par le Basic Auth).

> ⚠ Le bouton **« Près de moi »** (géolocalisation) exige du **HTTPS** : passe par
> une URL `https://...ts.net` (`-Serve` ou `-Public`), pas par `http://<ip>:5681`.
> Sur l'URL HTTPS, accepte la demande de localisation du navigateur.

Identifiants Basic Auth : `_secrets\remote_access.json` (jamais versionné).

## Ce qu'on peut faire

- **Filtrer** par date d'ajout (ex. « 07/06 »), catégorie (restauration, café,
  commerce, hôtel/nuit, intérim) et statut (à envoyer, envoyé…), ou rechercher
  par texte (enseigne, poste, rue).
- **📍 Près de moi** : géolocalise et propose d'aller au lieu le plus proche
  (ouvre l'itinéraire **vélo** dans Google Maps).
- **Popups** : adresse, téléphone (cliquable), horaires, note, et liens vers le
  **CV** et la **lettre** PDF de cette candidature.
- **☰ Liste** : tous les lieux triés (par distance si localisé), plus la liste
  des candidatures « sans adresse précise » (missions intérim « 35 - Rennes »)
  qui ne peuvent pas être placées sur la carte.
- **⟳ Mettre à jour** : régénère les données (relit le suivi, géocode les
  nouvelles adresses).

## Comment ça marche

- `scripts/carte_data.py` lit `datas/suivi_candidatures.json` + les
  `01_offres/<id>/offre.json`, géocode les adresses via OpenStreetMap (Nominatim,
  cache dans `datas/geocache.json`) et écrit `datas/carte_lieux.json`.
- `datas/carte_contacts.json` ajoute à la main les téléphones / horaires / notes,
  et permet de **forcer des coordonnées** (`lat`/`lon`) quand le géocodage échoue.
- `scripts/carte_app.py` est le serveur Flask (port 5681, Basic Auth) qui sert la
  carte et l'API.

### Ajouter / corriger un lieu

- Les nouvelles candidatures générées par le pipeline apparaissent
  automatiquement après un **⟳ Mettre à jour** (ou au prochain lancement).
- Pour un téléphone, des horaires ou une adresse mal géocodée : éditer
  `datas/carte_contacts.json` (clé = id de la candidature), puis ⟳.