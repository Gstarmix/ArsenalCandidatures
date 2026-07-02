import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts import (offres_store, scraper, generate, ingest, suivi,
                     archivage)
from scripts.offres_store import LIBELLES, STATUTS, statut_derive
from scripts.logger_setup import get_logger
log = get_logger()
COULEURS = {
    "nouveau": "#FFFFFF",
    "interesse": "#D6EAF8",
    "cv_genere": "#D5F5E3",
    "envoye": "#ABEBC6",
    "ignore": "#E5E7E9",
}
SOURCE_LIBELLES = {
    "francetravail": "France Travail",
    "crous": "CROUS",
    "lagrorecrute": "lagrorecrute",
}
def _libelle_source(source: str) -> str:
    return SOURCE_LIBELLES.get(source, source or "(inconnue)")
def _fmt_horodatage(iso: str) -> str:
    if not iso:
        return ""
    for entree, sortie in (("%Y-%m-%d %H:%M", "%d/%m/%y %H:%M"),
                           ("%Y-%m-%d", "%d/%m/%y")):
        try:
            return datetime.strptime(iso, entree).strftime(sortie)
        except ValueError:
            continue
    return ""
def _horodatage_brut(offre: dict, statut: str) -> str:
    if statut == "envoye" and offre.get("envoye_le"):
        return offre["envoye_le"]
    if statut in ("cv_genere", "envoye"):
        iso = offre.get("cv_genere_le")
        if iso and len(iso) > 10:
            return iso
        pdf = offre.get("cv_pdf")
        if pdf and os.path.exists(pdf):
            try:
                return datetime.fromtimestamp(
                    os.path.getmtime(pdf)).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass
        return iso or ""
    if statut in ("interesse", "ignore"):
        return offre.get("interet_le") or offre.get("date_ajout") or ""
    if statut == "nouveau":
        return offre.get("date_ajout") or ""
    return ""
def _libelle_statut(offre: dict, statut: str) -> str:
    libelle = LIBELLES.get(statut, statut)
    if statut == "ignore" and offre.get("filtre_auto"):
        return f"{libelle} (filtré : {offre['filtre_auto']})"
    horodatage = _fmt_horodatage(_horodatage_brut(offre, statut))
    if horodatage:
        libelle = f"{libelle} ({horodatage})"
    return libelle
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.offres_affichees = []
        self.tri = ("ajoute", True)
        self.scraping = False
        self.generation_active = False
        self.file_generation = []
        self.verrou_generation = threading.Lock()
        root.title("Arsenal Candidatures")
        root.geometry("1120x660")
        root.minsize(900, 500)
        self._construire()
        self.rafraichir()
    def _construire(self) -> None:
        haut = ttk.Frame(self.root, padding=8)
        haut.pack(fill="x")
        self.btn_ft = ttk.Button(haut, text="Scraper France Travail",
                                 command=lambda: self._lancer_scraper("francetravail"))
        self.btn_ft.pack(side="left")
        self.btn_crous = ttk.Button(haut, text="Scraper CROUS (jobs étudiants)",
                                    command=lambda: self._lancer_scraper("crous"))
        self.btn_crous.pack(side="left", padx=4)
        ttk.Button(haut, text="Rafraîchir", command=self.rafraichir).pack(side="left")
        ttk.Label(haut, text="Statut :").pack(side="left", padx=(16, 2))
        self.filtre = ttk.Combobox(haut, state="readonly", width=13,
                                   values=["Tous"] + [LIBELLES[s] for s in STATUTS])
        self.filtre.set("Tous")
        self.filtre.pack(side="left")
        self.filtre.bind("<<ComboboxSelected>>", lambda e: self.rafraichir())
        ttk.Label(haut, text="Source :").pack(side="left", padx=(12, 2))
        self.filtre_source = ttk.Combobox(haut, state="readonly", width=14,
                                           values=["Toutes"])
        self.filtre_source.set("Toutes")
        self.filtre_source.pack(side="left")
        self.filtre_source.bind("<<ComboboxSelected>>", lambda e: self.rafraichir())
        self.lbl_compte = ttk.Label(haut, text="")
        self.lbl_compte.pack(side="right")
        cadre = ttk.Frame(self.root)
        cadre.pack(fill="both", expand=True, padx=8)
        self.cols = ("statut", "titre", "entreprise", "source", "lieu",
                     "contrat", "ajoute", "score")
        largeurs = {"statut": 165, "titre": 235, "entreprise": 150,
                    "source": 105, "lieu": 130, "contrat": 115,
                    "ajoute": 90, "score": 55}
        self.entetes = {"statut": "Statut", "titre": "Titre",
                        "entreprise": "Entreprise", "source": "Source",
                        "lieu": "Lieu", "contrat": "Contrat",
                        "ajoute": "Ajoutée le", "score": "Score"}
        self.tree = ttk.Treeview(cadre, columns=self.cols, show="headings",
                                 selectmode="extended")
        for c in self.cols:
            self.tree.heading(c, text=self.entetes[c],
                              command=lambda col=c: self._trier(col))
            self.tree.column(c, width=largeurs[c],
                             anchor="center" if c in ("score", "ajoute") else "w")
        sb = ttk.Scrollbar(cadre, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._sur_selection())
        self.tree.bind("<Control-c>", lambda e: self._copier_selection())
        self.tree.bind("<Control-C>", lambda e: self._copier_selection())
        for statut, couleur in COULEURS.items():
            self.tree.tag_configure(statut, background=couleur)
        bas = ttk.Frame(self.root, padding=8)
        bas.pack(fill="x")
        for i in range(9):
            bas.columnconfigure(i, weight=1)
        self.lbl_sel = ttk.Label(bas, text="Aucune offre sélectionnée.",
                                 font=("Segoe UI", 9, "bold"))
        self.lbl_sel.grid(row=0, column=0, columnspan=9, sticky="w", pady=(0, 6))
        self.boutons = {}
        actions = [
            ("interesse", "Intéressé", lambda: self._definir_interet("interesse")),
            ("ignore", "Ignorer", lambda: self._definir_interet("ignore")),
            ("generer", "Générer CV + lettre", self._generer_selection),
            ("envoye", "Marquer envoyé", lambda: self._definir_avancement("envoye")),
            ("url", "Ouvrir l'offre", lambda: self._ouvrir("url")),
            ("cv_pdf", "Ouvrir CV", lambda: self._ouvrir("cv_pdf")),
            ("lettre_pdf", "Ouvrir lettre PDF", lambda: self._ouvrir("lettre_pdf")),
            ("lettre_txt", "Ouvrir lettre texte", lambda: self._ouvrir("lettre_txt")),
            ("copier", "Copier (réf.)", self._copier_selection),
        ]
        for i, (cle, texte, commande) in enumerate(actions):
            bouton = ttk.Button(bas, text=texte, command=commande, state="disabled")
            bouton.grid(row=1, column=i, padx=2, sticky="ew")
            self.boutons[cle] = bouton
        self.btn_lot = ttk.Button(bas, text="Générer pour les « Intéressé » sans CV",
                                  command=self._generer_interesses)
        self.btn_lot.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(bas, text="Note :").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.note = ttk.Entry(bas)
        self.note.grid(row=3, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        self.btn_note = ttk.Button(bas, text="Enregistrer la note",
                                   command=self._enregistrer_note, state="disabled")
        self.btn_note.grid(row=3, column=6, columnspan=2, sticky="ew", pady=(8, 0))
        self.barre = ttk.Label(self.root, text="Prêt.", relief="sunken",
                               anchor="w", padding=4)
        self.barre.pack(fill="x", side="bottom")
    def rafraichir(self) -> None:
        data = offres_store.charger()
        toutes = data.get("offres", [])
        libelle = self.filtre.get()
        statut_filtre = next((s for s in STATUTS if LIBELLES[s] == libelle), None)
        sources = sorted({o.get("source", "") for o in toutes})
        valeurs_src = ["Toutes"] + [_libelle_source(s) for s in sources]
        if list(self.filtre_source["values"]) != valeurs_src:
            actuel = self.filtre_source.get()
            self.filtre_source["values"] = valeurs_src
            self.filtre_source.set(actuel if actuel in valeurs_src else "Toutes")
        libelle_src = self.filtre_source.get()
        source_filtre = next(
            (s for s in sources if _libelle_source(s) == libelle_src), None)
        self.offres_affichees = [
            o for o in toutes
            if (statut_filtre is None or statut_derive(o) == statut_filtre)
            and (source_filtre is None or o.get("source", "") == source_filtre)]
        col, reverse = self.tri
        self.offres_affichees.sort(key=lambda o: self._cle_tri(o, col),
                                   reverse=reverse)
        self._maj_entetes()
        self.tree.delete(*self.tree.get_children())
        for offre in self.offres_affichees:
            cle = offre.get("cle")
            if not cle:
                continue
            statut = statut_derive(offre)
            self.tree.insert("", "end", iid=cle, tags=(statut,), values=(
                _libelle_statut(offre, statut),
                offre.get("titre", ""),
                offre.get("entreprise", ""),
                _libelle_source(offre.get("source", "")),
                offre.get("lieu", ""),
                offre.get("contrat", ""),
                _fmt_horodatage(offre.get("date_ajout", "")),
                offre.get("score", 0),
            ))
        counts = {s: 0 for s in STATUTS}
        for o in toutes:
            counts[statut_derive(o)] += 1
        self.lbl_compte.config(text=f"{len(toutes)} offres   |   " + "   ".join(
            f"{LIBELLES[s]}: {counts[s]}" for s in STATUTS))
        self._sur_selection()
    def _cle_tri(self, offre: dict, col: str):
        if col == "score":
            return offre.get("score", 0) or 0
        if col == "ajoute":
            return (offre.get("date_ajout", "") or "", offre.get("score", 0) or 0)
        if col == "statut":
            return _horodatage_brut(offre, statut_derive(offre))
        return str(offre.get(col, "") or "").lower()
    def _trier(self, col: str) -> None:
        actuel, reverse = self.tri
        if col == actuel:
            reverse = not reverse
        else:
            reverse = col in ("score", "statut", "ajoute")
        self.tri = (col, reverse)
        self.rafraichir()
    def _maj_entetes(self) -> None:
        col_actif, reverse = self.tri
        for c in self.cols:
            texte = self.entetes[c]
            if c == col_actif:
                texte += "  ▼" if reverse else "  ▲"
            self.tree.heading(c, text=texte)
    def _offre_par_cle(self, cle: str):
        for offre in offres_store.charger().get("offres", []):
            if offre.get("cle") == cle:
                return offre
        return None
    def _selection(self) -> list:
        return list(self.tree.selection())
    def _sur_selection(self) -> None:
        sel = self._selection()
        multi = len(sel) >= 1
        unique = len(sel) == 1
        self.boutons["envoye"].config(
            state="normal" if multi and not self._occupe() else "disabled")
        self.boutons["generer"].config(
            state="normal" if multi and not self.scraping else "disabled")
        for cle in ("interesse", "ignore", "copier"):
            self.boutons[cle].config(state="normal" if multi else "disabled")
        offre = self._offre_par_cle(sel[0]) if unique else None
        for champ in ("url", "cv_pdf", "lettre_pdf", "lettre_txt"):
            ok = bool(offre and offre.get(champ))
            self.boutons[champ].config(state="normal" if ok else "disabled")
        self.btn_note.config(state="normal" if unique else "disabled")
        self.note.delete(0, "end")
        if unique and offre:
            self.note.insert(0, offre.get("notes", ""))
            self.lbl_sel.config(text=f"Sélection : {offre.get('titre', '')}")
        elif multi:
            self.lbl_sel.config(text=f"{len(sel)} offres sélectionnées.")
        else:
            self.lbl_sel.config(text="Aucune offre sélectionnée.")
    def _definir_interet(self, valeur: str) -> None:
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
        archives = restaures = 0
        for cle in self._selection():
            offre = self._offre_par_cle(cle)
            champs = {"interet": valeur, "interet_le": horodatage,
                      "filtre_auto": ""}
            try:
                if (offre and valeur == "ignore" and offre.get("cv_pdf")
                        and not offre.get("archive")):
                    champs.update(archivage.archiver(offre))
                    archives += 1
                elif offre and valeur == "interesse" and offre.get("archive"):
                    champs.update(archivage.restaurer(offre))
                    restaures += 1
            except OSError as e:
                log.error("Archivage/restauration impossible (%s) : %s", cle, e)
                messagebox.showerror(
                    "Déplacement impossible",
                    "Impossible de déplacer les fichiers. Le CV ou la lettre "
                    f"est peut-être ouvert dans un autre programme.\n\n{e}")
            offres_store.maj_offre(cle, **champs)
        self.rafraichir()
        message = f"Intérêt mis à jour : {LIBELLES.get(valeur, valeur)}."
        if archives:
            message += f" {archives} CV archivé(s)."
        if restaures:
            message += f" {restaures} CV restauré(s)."
        self.barre.config(text=message)
    def _definir_avancement(self, valeur: str) -> None:
        champs = {"avancement": valeur}
        if valeur == "envoye":
            champs["envoye_le"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        for cle in self._selection():
            offres_store.maj_offre(cle, **champs)
        self.rafraichir()
        self.barre.config(text="Avancement mis à jour.")
    def _ouvrir(self, champ: str) -> None:
        sel = self._selection()
        if not sel:
            return
        offre = self._offre_par_cle(sel[0])
        valeur = offre.get(champ) if offre else None
        if not valeur:
            return
        try:
            if champ == "url":
                webbrowser.open(valeur)
            else:
                os.startfile(valeur)
        except OSError as e:
            messagebox.showerror("Ouverture impossible", str(e))
    def _enregistrer_note(self) -> None:
        sel = self._selection()
        if len(sel) == 1:
            offres_store.maj_offre(sel[0], notes=self.note.get())
            self.barre.config(text="Note enregistrée.")
    def _copier_selection(self) -> None:
        lignes = []
        for cle in self._selection():
            o = self._offre_par_cle(cle)
            if not o:
                continue
            lignes.append(
                f"[réf {cle}] {o.get('titre', '')} | "
                f"{o.get('entreprise', '') or '?'} | {o.get('lieu', '')} | "
                f"{o.get('contrat', '')} | "
                f"source: {_libelle_source(o.get('source', ''))} | "
                f"statut: {LIBELLES.get(statut_derive(o), '')} | "
                f"{o.get('url', '')}")
        if not lignes:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lignes))
        self.barre.config(
            text=f"{len(lignes)} ligne(s) copiée(s) dans le presse-papier.")
    def _occupe(self) -> bool:
        return self.scraping or self.generation_active
    def _maj_boutons_lourds(self) -> None:
        etat = "disabled" if self._occupe() else "normal"
        for bouton in (self.btn_ft, self.btn_crous):
            bouton.config(state=etat)
        self.btn_lot.config(state="disabled" if self.scraping else "normal")
        self._sur_selection()
    def _async(self, message: str) -> None:
        self.root.after(0, lambda: self.barre.config(text=message))
    def _lancer_scraper(self, source: str) -> None:
        if self._occupe():
            return
        self.scraping = True
        self._maj_boutons_lourds()
        self.barre.config(text=f"Scraping ({source}) en cours...")
        def tache():
            try:
                res = scraper.scraper(source)
                self._async(f"Scraping terminé : {res['total']} offre(s).")
            except Exception as e:
                log.error("Scraper échoué : %s", e)
                self._async(f"Échec du scraping : {e}")
            self.root.after(0, self._fin_scraper)
        threading.Thread(target=tache, daemon=True).start()
    def _fin_scraper(self) -> None:
        self.scraping = False
        self._maj_boutons_lourds()
        self.rafraichir()
    def _generer_selection(self) -> None:
        sel = self._selection()
        if not sel:
            return
        deja = [c for c in sel
                if (self._offre_par_cle(c) or {}).get("cv_pdf")]
        a_generer = [c for c in sel if c not in deja]
        if deja:
            if len(deja) == len(sel):
                question = ("Le CV de cette offre a déjà été généré et l'offre "
                            "n'a pas changé. Le régénérer quand même ?")
            else:
                question = (f"{len(deja)} offre(s) sur {len(sel)} ont déjà un CV "
                            "généré.\n\nOui : tout régénérer.\nNon : ne générer "
                            "que les offres sans CV.")
            reponse = messagebox.askyesnocancel("Génération", question)
            if reponse is None:
                return
            if reponse:
                a_generer = sel
        if not a_generer:
            self.barre.config(text="Rien à générer : CV déjà existant(s).")
            return
        self._lancer_generation(a_generer)
    def _generer_interesses(self) -> None:
        cles = [o["cle"] for o in offres_store.charger().get("offres", [])
                if o.get("interet") == "interesse" and not o.get("cv_pdf")]
        if not cles:
            messagebox.showinfo("Génération en lot",
                                "Aucune offre « Intéressé » sans CV à générer.")
            return
        if messagebox.askyesno("Génération en lot",
                               f"Générer le CV et la lettre pour {len(cles)} "
                               f"offre(s) ? Cela peut prendre quelques minutes."):
            self._lancer_generation(cles)
    def _lancer_generation(self, cles: list) -> None:
        if not cles or self.scraping:
            return
        with self.verrou_generation:
            for cle in cles:
                if cle not in self.file_generation:
                    self.file_generation.append(cle)
            attente = len(self.file_generation)
            demarrer = not self.generation_active
            if demarrer:
                self.generation_active = True
        self._maj_boutons_lourds()
        if demarrer:
            threading.Thread(target=self._worker_generation,
                             daemon=True).start()
        else:
            self._async(f"Ajouté à la file de génération "
                        f"({attente} offre(s) en attente).")
    def _worker_generation(self) -> None:
        traite = 0
        while True:
            with self.verrou_generation:
                if not self.file_generation:
                    self.generation_active = False
                    break
                cle = self.file_generation.pop(0)
                restant = len(self.file_generation)
            offre = self._offre_par_cle(cle)
            if not offre:
                continue
            traite += 1
            suffixe = f" ({restant} en attente)" if restant else ""
            self._async(f"Génération : "
                        f"{offre.get('titre', '')[:50]}...{suffixe}")
            try:
                self._generer_une(cle, offre)
            except Exception as e:
                log.error("Génération échouée (%s) : %s", cle, e)
                self._async(f"Échec sur une offre : {e}")
        suivi.generer_tableau_de_bord()
        self._async(f"Génération terminée ({traite} offre(s)).")
        self.root.after(0, self._fin_generation)
    def _generer_une(self, cle: str, offre: dict) -> None:
        texte = scraper.charger_texte_offre(offre.get("url", ""))
        repli = (f"{offre.get('titre', '')} chez "
                 f"{offre.get('entreprise') or 'entreprise non précisée'}, "
                 f"{offre.get('lieu', '')}, contrat {offre.get('contrat', '')}.")
        offre_gen = {
            "titre_offre": offre.get("titre", ""),
            "entreprise": offre.get("entreprise", ""),
            "lieu": offre.get("lieu", ""),
            "type_contrat": offre.get("contrat", ""),
            "url": offre.get("url", ""),
            "description_structuree": "",
            "texte_page": texte or repli,
        }
        oid, dossier = ingest.creer_dossier_offre(offre_gen)
        resultat = generate.generer(offre_gen, oid, dossier)
        suivi.ajouter(oid, offre_gen, resultat)
        offres_store.maj_offre(
            cle, avancement="cv_genere",
            cv_genere_le=datetime.now().strftime("%Y-%m-%d %H:%M"),
            cv_pdf=resultat.get("cv_pdf"),
            lettre_pdf=resultat.get("lettre_pdf"),
            lettre_txt=resultat.get("lettre_txt"))
        a_jour = self._offre_par_cle(cle)
        if a_jour and a_jour.get("interet") == "ignore" \
                and not a_jour.get("archive"):
            try:
                offres_store.maj_offre(cle, **archivage.archiver(a_jour))
                self._async("Offre ignorée pendant la génération, CV archivé : "
                            f"{offre.get('titre', '')[:45]}")
            except OSError as e:
                log.error("Archivage post-génération impossible (%s) : %s",
                          cle, e)
    def _fin_generation(self) -> None:
        self._maj_boutons_lourds()
        self.rafraichir()
def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
if __name__ == "__main__":
    main()