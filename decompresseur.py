"""
Décompresseur de contexte (format "blinder") — v2
----------------------------------------------------
Interface graphique moderne avec glisser-déposer : tu déposes (ou sélectionnes)
un fichier .txt généré par le compresseur (auto_context_sync / blinder), et le
programme reconstruit un fichier .zip contenant l'arborescence complète des
dossiers/sous-dossiers et le contenu intégral de chaque fichier.

Dépendance :
    pip install tkinterdnd2

Si tkinterdnd2 n'est pas installé, le programme fonctionne quand même
(juste sans le glisser-déposer, avec le bouton "Choisir un fichier").

Lancement :
    python decompresseur_gui_v2.py
"""

import os
import re
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_DISPONIBLE = True
except ImportError:
    DND_DISPONIBLE = False

# ---------------------------------------------------------------------------
# Palette / thème
# ---------------------------------------------------------------------------
COULEUR_FOND = "#14151a"
COULEUR_PANNEAU = "#1c1e26"
COULEUR_PANNEAU_CLAIR = "#242631"
COULEUR_BORDURE = "#2f3140"
COULEUR_ACCENT = "#7c5cff"
COULEUR_ACCENT_HOVER = "#8f72ff"
COULEUR_TEXTE = "#eceef5"
COULEUR_TEXTE_ATTENUE = "#8b8da3"
COULEUR_SUCCES = "#4ade80"
COULEUR_ERREUR = "#f87171"

# ---------------------------------------------------------------------------
# Parsing du fichier bundle
# ---------------------------------------------------------------------------
DOSSIER_RE = re.compile(r"^\[DOSSIER\]\s+(.+?)\s*$", re.MULTILINE)
FICHIER_RE = re.compile(
    r"--- DEBUT FICHIER: (.*?) ---\r?\n(.*?)\r?\n--- FIN FICHIER: \1 ---",
    re.DOTALL,
)


def normaliser_chemin(chemin: str) -> str:
    return chemin.replace("\\", "/")


def extraire_projets(texte: str):
    projets = [normaliser_chemin(m.group(1)) for m in DOSSIER_RE.finditer(texte)]
    return sorted(set(projets), key=len, reverse=True)


def chemin_relatif(chemin_fichier: str, projets: list) -> str:
    chemin_norm = normaliser_chemin(chemin_fichier)
    for base in projets:
        base_norm = base.rstrip("/") + "/"
        if chemin_norm.startswith(base_norm):
            return chemin_norm[len(base_norm):]
        if chemin_norm == base.rstrip("/"):
            return os.path.basename(chemin_norm)
    m = re.match(r"^[A-Za-z]:/(.*)$", chemin_norm)
    if m:
        return m.group(1)
    return chemin_norm.lstrip("/")


def parser_bundle(texte: str):
    projets = extraire_projets(texte)
    resultats = []
    for match in FICHIER_RE.finditer(texte):
        chemin_original = match.group(1).strip()
        contenu = match.group(2)
        rel = chemin_relatif(chemin_original, projets)
        rel = rel.replace("..", "").lstrip("/")
        if not rel:
            rel = os.path.basename(normaliser_chemin(chemin_original)) or "fichier_sans_nom.txt"
        resultats.append((rel, contenu))
    return resultats, projets


def taille_lisible(n: int) -> str:
    taille = float(n)
    for unite in ("o", "Ko", "Mo"):
        if taille < 1024:
            return f"{taille:.0f} {unite}" if unite == "o" else f"{taille:.1f} {unite}"
        taille /= 1024
    return f"{taille:.1f} Go"


# ---------------------------------------------------------------------------
# Petits widgets réutilisables au look "moderne"
# ---------------------------------------------------------------------------
class BoutonModerne(tk.Label):
    """Un bouton stylé maison (Label cliquable) car ttk est limité côté design."""

    def __init__(self, parent, texte, commande, primaire=True, **kwargs):
        self.commande = commande
        self.primaire = primaire
        bg = COULEUR_ACCENT if primaire else COULEUR_PANNEAU_CLAIR
        fg = "#ffffff" if primaire else COULEUR_TEXTE
        super().__init__(
            parent, text=texte, bg=bg, fg=fg,
            font=("Segoe UI", 10, "bold"), padx=18, pady=10,
            cursor="hand2", **kwargs,
        )
        self.bg_normal = bg
        self.bg_hover = COULEUR_ACCENT_HOVER if primaire else COULEUR_BORDURE
        self.bind("<Button-1>", lambda e: self._on_click())
        self.bind("<Enter>", lambda e: self.config(bg=self.bg_hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg_normal))

    def _on_click(self):
        if self["state"] != "disabled" and self.commande:
            self.commande()

    def desactiver(self):
        self["state"] = "disabled"
        self.config(bg=COULEUR_PANNEAU, fg=COULEUR_TEXTE_ATTENUE, cursor="arrow")

    def activer(self):
        self["state"] = "normal"
        self.config(bg=self.bg_normal, fg="#ffffff" if self.primaire else COULEUR_TEXTE, cursor="hand2")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class DecompresseurApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Décompresseur de contexte")
        self.root.geometry("680x560")
        self.root.minsize(600, 480)
        self.root.configure(bg=COULEUR_FOND)

        self.fichiers_parses = []
        self.projets_detectes = []
        self.chemin_source = ""

        self._construire_interface()

        if DND_DISPONIBLE:
            self.zone_drop.drop_target_register(DND_FILES)
            self.zone_drop.dnd_bind("<<Drop>>", self._on_drop)

    # -- Construction UI -----------------------------------------------
    def _construire_interface(self):
        conteneur = tk.Frame(self.root, bg=COULEUR_FOND)
        conteneur.pack(fill="both", expand=True, padx=24, pady=22)

        # En-tête
        titre = tk.Label(
            conteneur, text="Décompresseur de contexte",
            bg=COULEUR_FOND, fg=COULEUR_TEXTE, font=("Segoe UI", 18, "bold"),
        )
        titre.pack(anchor="w")

        sous_titre = tk.Label(
            conteneur,
            text="Dépose ton fichier bundle (.txt) pour reconstruire le projet en .zip",
            bg=COULEUR_FOND, fg=COULEUR_TEXTE_ATTENUE, font=("Segoe UI", 10),
        )
        sous_titre.pack(anchor="w", pady=(2, 18))

        # Zone de dépôt
        self.zone_drop = tk.Frame(
            conteneur, bg=COULEUR_PANNEAU, highlightthickness=2,
            highlightbackground=COULEUR_BORDURE, highlightcolor=COULEUR_ACCENT,
        )
        self.zone_drop.pack(fill="x", pady=(0, 18))
        self.zone_drop.pack_propagate(False)
        self.zone_drop.configure(height=140)

        icone_txt = "⬇" if DND_DISPONIBLE else "📄"
        self.label_icone = tk.Label(
            self.zone_drop, text=icone_txt, bg=COULEUR_PANNEAU,
            fg=COULEUR_ACCENT, font=("Segoe UI", 26),
        )
        self.label_icone.pack(pady=(20, 4))

        texte_zone = (
            "Glisse ton fichier .txt ici" if DND_DISPONIBLE
            else "Glisser-déposer indisponible (installe tkinterdnd2)"
        )
        self.label_zone = tk.Label(
            self.zone_drop, text=texte_zone, bg=COULEUR_PANNEAU,
            fg=COULEUR_TEXTE, font=("Segoe UI", 11, "bold"),
        )
        self.label_zone.pack()

        self.label_ou = tk.Label(
            self.zone_drop, text="ou clique pour parcourir tes fichiers",
            bg=COULEUR_PANNEAU, fg=COULEUR_ACCENT, font=("Segoe UI", 9, "underline"),
            cursor="hand2",
        )
        self.label_ou.pack(pady=(4, 0))

        for widget in (self.zone_drop, self.label_icone, self.label_zone, self.label_ou):
            widget.bind("<Button-1>", lambda e: self.choisir_fichier())

        # Ligne fichier sélectionné
        self.label_fichier = tk.Label(
            conteneur, text="Aucun fichier sélectionné.",
            bg=COULEUR_FOND, fg=COULEUR_TEXTE_ATTENUE, font=("Segoe UI", 9),
            anchor="w",
        )
        self.label_fichier.pack(fill="x")

        # Aperçu
        cadre_apercu = tk.Frame(conteneur, bg=COULEUR_PANNEAU, highlightthickness=1, highlightbackground=COULEUR_BORDURE)
        cadre_apercu.pack(fill="both", expand=True, pady=(14, 14))

        tk.Label(
            cadre_apercu, text="FICHIERS DÉTECTÉS", bg=COULEUR_PANNEAU,
            fg=COULEUR_TEXTE_ATTENUE, font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))

        cadre_liste = tk.Frame(cadre_apercu, bg=COULEUR_PANNEAU)
        cadre_liste.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        scrollbar = tk.Scrollbar(cadre_liste)
        scrollbar.pack(side="right", fill="y")

        self.liste_fichiers = tk.Listbox(
            cadre_liste, bg=COULEUR_PANNEAU, fg=COULEUR_TEXTE,
            font=("Consolas", 9), borderwidth=0, highlightthickness=0,
            selectbackground=COULEUR_ACCENT, activestyle="none",
            yscrollcommand=scrollbar.set,
        )
        self.liste_fichiers.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.liste_fichiers.yview)

        # Pied de page : statut + bouton générer
        pied = tk.Frame(conteneur, bg=COULEUR_FOND)
        pied.pack(fill="x")

        self.label_statut = tk.Label(
            pied, text="En attente d'un fichier...", bg=COULEUR_FOND,
            fg=COULEUR_TEXTE_ATTENUE, font=("Segoe UI", 9), anchor="w",
        )
        self.label_statut.pack(side="left", fill="x", expand=True)

        self.bouton_generer = BoutonModerne(pied, "Générer le ZIP", self.generer_zip, primaire=True)
        self.bouton_generer.pack(side="right")
        self.bouton_generer.desactiver()

    # -- Gestion des fichiers -------------------------------------------
    def _on_drop(self, event):
        chemin = self._nettoyer_chemin_drop(event.data)
        if chemin:
            self._charger_fichier(chemin)

    @staticmethod
    def _nettoyer_chemin_drop(data: str) -> str:
        data = data.strip()
        if data.startswith("{") and data.endswith("}"):
            data = data[1:-1]
        return data

    def choisir_fichier(self):
        chemin = filedialog.askopenfilename(
            title="Sélectionne le fichier bundle (.txt)",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
        )
        if chemin:
            self._charger_fichier(chemin)

    def _charger_fichier(self, chemin: str):
        if not os.path.isfile(chemin):
            messagebox.showerror("Erreur", "Fichier introuvable.")
            return

        try:
            with open(chemin, "r", encoding="utf-8", errors="replace") as f:
                texte = f.read()
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier :\n{e}")
            return

        fichiers, projets = parser_bundle(texte)

        if not fichiers:
            messagebox.showwarning(
                "Aucun fichier détecté",
                "Ce fichier ne contient aucun bloc DEBUT/FIN FICHIER reconnu.\n"
                "Vérifie que c'est bien un bundle généré par le compresseur.",
            )
            return

        self.chemin_source = chemin
        self.fichiers_parses = fichiers
        self.projets_detectes = projets

        self.label_fichier.config(text=f"Fichier chargé : {os.path.basename(chemin)}")
        self._afficher_apercu()
        self.bouton_generer.activer()
        self.label_statut.config(
            text=f"{len(fichiers)} fichier(s) détecté(s) — prêt à générer le zip.",
            fg=COULEUR_SUCCES,
        )
        self.zone_drop.config(highlightbackground=COULEUR_SUCCES)
        self.label_zone.config(text="Fichier chargé ✓")

    def _afficher_apercu(self):
        self.liste_fichiers.delete(0, "end")
        for rel, contenu in self.fichiers_parses:
            taille = len(contenu.encode("utf-8", errors="replace"))
            self.liste_fichiers.insert("end", f"  {rel}    ·  {taille_lisible(taille)}")

    def generer_zip(self):
        if not self.fichiers_parses:
            return

        nom_defaut = "projet_reconstruit.zip"
        if self.projets_detectes:
            base = os.path.basename(self.projets_detectes[0].rstrip("/"))
            if base:
                nom_defaut = f"{base}.zip"

        chemin_sortie = filedialog.asksaveasfilename(
            title="Enregistrer le zip généré",
            defaultextension=".zip",
            initialfile=nom_defaut,
            filetypes=[("Archive ZIP", "*.zip")],
        )
        if not chemin_sortie:
            return

        try:
            with zipfile.ZipFile(chemin_sortie, "w", zipfile.ZIP_DEFLATED) as zf:
                chemins_utilises = set()
                for rel, contenu in self.fichiers_parses:
                    rel_final = rel
                    compteur = 1
                    while rel_final in chemins_utilises:
                        racine, ext = os.path.splitext(rel)
                        rel_final = f"{racine} ({compteur}){ext}"
                        compteur += 1
                    chemins_utilises.add(rel_final)
                    zf.writestr(rel_final, contenu)
        except OSError as e:
            self.label_statut.config(text=f"Échec de l'écriture du zip : {e}", fg=COULEUR_ERREUR)
            messagebox.showerror("Erreur", f"Impossible d'écrire le zip :\n{e}")
            return

        self.label_statut.config(text=f"Zip généré : {chemin_sortie}", fg=COULEUR_SUCCES)
        messagebox.showinfo(
            "Terminé",
            f"Le zip a été généré avec succès :\n{chemin_sortie}\n\n"
            f"{len(self.fichiers_parses)} fichier(s) reconstitué(s).",
        )


def main():
    if DND_DISPONIBLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    try:
        tkfont.nametofont("TkDefaultFont").configure(family="Segoe UI", size=10)
    except tk.TclError:
        pass

    DecompresseurApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
