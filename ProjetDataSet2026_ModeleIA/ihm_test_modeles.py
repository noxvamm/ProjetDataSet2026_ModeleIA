# =============================================================================
#  IHM_TEST_MODELES — Interface graphique de test des modèles
#  Projet BTS CIEL Dataset26 — Estimation du niveau de tension moteur
#
#  Permet de :
#   - Choisir un modèle .keras via l'explorateur de fichiers
#   - Choisir une capture (fichier son + fichier vibration) via l'explorateur
#   - Lancer la prédiction et afficher tension prédite / réelle / erreur
#     (la tension réelle est retrouvée automatiquement dans les CSV de
#      métadonnées si le fichier son sélectionné y est référencé)
#
#  Le préprocessing est repris de predire_tension.py. Si un fichier .txt
#  d'hyperparamètres accompagne le modèle (généré par arch4_double_branche.py),
#  les paramètres de préprocessing sont lus dedans — sinon valeurs par défaut.
#
#  Usage :  python ihm_test_modeles.py
# =============================================================================

import os
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
import librosa
import tensorflow as tf

# --- CHEMINS (relatifs au script) ---
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR       = os.path.join(SCRIPT_DIR, '..', 'modeles')
DATA_BASE        = os.path.join(SCRIPT_DIR, 'dist', 'data')
RECORDS_DIR      = os.path.join(DATA_BASE, 'records')        # captures TRAIN
RECORDS_DIR_TEST = os.path.join(DATA_BASE, 'records_test')   # captures TEST
CSV_TRAIN        = os.path.join(DATA_BASE, 'metadata_captures_moteur.csv')
CSV_TEST         = os.path.join(DATA_BASE, 'metadata_captures_test.csv')

# --- HYPERPARAMÈTRES PAR DÉFAUT (identiques à la baseline arch4) ---
# Écrasés par le .txt du modèle s'il existe.
HP_DEFAUT = {
    'IMG_SIZE':         (128, 128),
    'SON_N_MELS':       64,
    'VIB_N_FFT':        128,
    'VIB_HOP':          32,
    'VIB_N_MELS':       32,
    'WINDOW_DUREE_SON': 1.0,
    'WINDOW_OVERLAP':   0.5,
}

SR_SON_DEFAUT = 16000.0
SR_VIB_DEFAUT = 50.0
DUREE_DEFAUT  = 15.0

# Tension max mesurée par condition — pour convertir % -> volts
VOLTAGE_MAX = {'A_vide': 30.3, 'B_frein': 28.7}


# =============================================================================
#  LECTURE DES HYPERPARAMÈTRES DEPUIS LE .TXT DU MODÈLE
# =============================================================================

def charger_hyperparametres(chemin_modele):
    """Lit le .txt associé au modèle (même nom) et retourne un dict d'hyperparamètres.
       Les clés absentes du fichier gardent leur valeur par défaut."""
    hp = dict(HP_DEFAUT)
    chemin_txt = chemin_modele.replace('.keras', '.txt')
    if not os.path.exists(chemin_txt):
        return hp, False

    with open(chemin_txt, 'r', encoding='utf-8') as f:
        for ligne in f:
            if '=' not in ligne:
                continue
            nom, _, valeur = ligne.partition('=')
            nom = nom.strip()
            valeur = valeur.strip()
            if nom not in hp:
                continue
            if nom == 'IMG_SIZE':
                # Format "(128, 128)" -> tuple d'entiers
                nombres = valeur.strip('()').split(',')
                hp[nom] = (int(nombres[0]), int(nombres[1]))
            elif nom in ('WINDOW_DUREE_SON', 'WINDOW_OVERLAP'):
                hp[nom] = float(valeur)
            else:
                hp[nom] = int(valeur)
    return hp, True


# =============================================================================
#  PREPROCESSING — repris de predire_tension.py, paramétré par les hyperparamètres
# =============================================================================

def normaliser(spectrogramme):
    s_min = spectrogramme.min()
    s_max = spectrogramme.max()
    return (spectrogramme - s_min) / (s_max - s_min + 1e-9)


def tronquer_duree(arr, duree_s):
    """Garde les `duree_s` premières secondes (timestamps col 0 en ms)."""
    if arr.ndim == 1 or len(arr) == 0:
        return arr
    t = arr[:, 0]
    mask = (t - t[0]) <= (duree_s * 1000.0)
    if mask.sum() < 10:
        return arr
    return arr[mask]


def decouper_son_en_fenetres(signal, sr, duree_fenetre, overlap):
    taille_fen = int(duree_fenetre * sr)
    if len(signal) < taille_fen:
        return [signal]
    pas = max(1, int(taille_fen * (1 - overlap)))
    return [signal[d:d + taille_fen] for d in range(0, len(signal) - taille_fen + 1, pas)]


def signal_vers_mel_son(signal, sr, hp):
    S = librosa.feature.melspectrogram(y=signal.astype(float), sr=sr, n_mels=hp['SON_N_MELS'])
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)
    return tf.image.resize(np.expand_dims(S_dB, -1), hp['IMG_SIZE']).numpy()


def signal_vers_mel_vib(signal, sr, hp):
    n_fft = min(hp['VIB_N_FFT'], max(8, len(signal)))
    hop   = max(1, min(hp['VIB_HOP'], max(1, len(signal) // 4)))
    S = librosa.feature.melspectrogram(
        y=signal.astype(float), sr=sr, n_mels=hp['VIB_N_MELS'],
        n_fft=n_fft, hop_length=hop
    )
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)
    return tf.image.resize(np.expand_dims(S_dB, -1), hp['IMG_SIZE']).numpy()


def charger_capture(path_son, path_vib, duree=DUREE_DEFAUT):
    """Charge et tronque une capture. Retourne (signal_son, magnitude_vib)."""
    if not os.path.exists(path_son):
        raise FileNotFoundError(f"Fichier son introuvable : {path_son}")
    if not os.path.exists(path_vib):
        raise FileNotFoundError(f"Fichier vibration introuvable : {path_vib}")

    arr_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=(0, 1))
    arr_son = tronquer_duree(arr_son, duree)
    data_son = arr_son[:, 1].astype(float)

    arr_vib = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(0, 1, 2, 3))
    arr_vib = tronquer_duree(arr_vib, duree)
    data_vibs = arr_vib[:, 1:4]
    magnitude = np.abs(data_vibs[:, 2])      # Option A : |VZ| seul — identique à arch4

    if len(data_son) < 10:
        raise ValueError(f"Signal son trop court ({len(data_son)} points) — capture vide ?")
    return data_son, magnitude.astype(float)


def predire(model, data_son, magnitude, hp, sr_son=SR_SON_DEFAUT, sr_vib=SR_VIB_DEFAUT):
    """Inférence par capture : moyenne des prédictions de chaque fenêtre."""
    mel_vib = signal_vers_mel_vib(magnitude, sr_vib, hp)
    fenetres = decouper_son_en_fenetres(data_son, sr_son, hp['WINDOW_DUREE_SON'], hp['WINDOW_OVERLAP'])

    X_son, X_vib = [], []
    for f in fenetres:
        X_son.append(signal_vers_mel_son(f, sr_son, hp))
        X_vib.append(mel_vib)
    X_son = np.array(X_son)
    X_vib = np.array(X_vib)

    pred_segments = model.predict([X_son, X_vib], verbose=0).flatten()
    pred_capture = float(np.mean(pred_segments)) * 100.0   # sigmoïde [0,1] -> %
    return pred_capture, len(fenetres)


# =============================================================================
#  LECTURE DES CSV DE MÉTADONNÉES
# =============================================================================

def chercher_metadonnees(nom_fichier_son):
    """Cherche le fichier son dans les CSV de métadonnées (test puis train).
       Retourne la ligne correspondante (dict) ou None si introuvable."""
    for csv_path in (CSV_TEST, CSV_TRAIN):
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row.get('fichier_son') == nom_fichier_son:
                    return row
    return None


# =============================================================================
#  INTERFACE GRAPHIQUE
# =============================================================================

class Application(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Test des modèles — Tension moteur")
        self.geometry("560x440")
        self.resizable(False, False)

        self.model = None            # modèle Keras chargé
        self.chemin_modele = None    # chemin du modèle chargé (évite de recharger)
        self.hp = dict(HP_DEFAUT)    # hyperparamètres du modèle courant
        self.path_son = None         # fichier son sélectionné
        self.path_vib = None         # fichier vibration sélectionné

        self._construire_widgets()

    # ------------------------------------------------------------------
    #  Construction de l'interface
    # ------------------------------------------------------------------
    def _construire_widgets(self):
        pad = {'padx': 10, 'pady': 5}

        # --- Choix du modèle ---
        cadre_modele = ttk.LabelFrame(self, text="1. Modèle")
        cadre_modele.pack(fill='x', **pad)

        ttk.Button(cadre_modele, text="Choisir un modèle…",
                   command=self._choisir_modele).pack(side='left', padx=8, pady=8)
        self.lbl_modele = ttk.Label(cadre_modele, text="Aucun modèle sélectionné")
        self.lbl_modele.pack(side='left', padx=8)

        # --- Choix de la capture ---
        cadre_capture = ttk.LabelFrame(self, text="2. Capture à tester")
        cadre_capture.pack(fill='x', **pad)

        ttk.Button(cadre_capture, text="Fichier son…", width=18,
                   command=self._choisir_son).grid(row=0, column=0, padx=8, pady=4, sticky='w')
        self.lbl_son = ttk.Label(cadre_capture, text="Aucun fichier sélectionné")
        self.lbl_son.grid(row=0, column=1, sticky='w', padx=8)

        ttk.Button(cadre_capture, text="Fichier vibration…", width=18,
                   command=self._choisir_vib).grid(row=1, column=0, padx=8, pady=4, sticky='w')
        self.lbl_vib = ttk.Label(cadre_capture, text="Aucun fichier sélectionné")
        self.lbl_vib.grid(row=1, column=1, sticky='w', padx=8)

        # --- Bouton de prédiction ---
        self.btn_predire = ttk.Button(self, text="Prédire la tension", command=self._lancer_prediction)
        self.btn_predire.pack(fill='x', **pad)

        # --- Résultats ---
        cadre_resultat = ttk.LabelFrame(self, text="3. Résultat")
        cadre_resultat.pack(fill='both', expand=True, **pad)

        self.lbl_pred = ttk.Label(cadre_resultat, text="Tension prédite : —",
                                  font=('Segoe UI', 14, 'bold'))
        self.lbl_pred.pack(anchor='w', padx=10, pady=(10, 2))

        self.lbl_reel = ttk.Label(cadre_resultat, text="Tension réelle : —", font=('Segoe UI', 11))
        self.lbl_reel.pack(anchor='w', padx=10, pady=2)

        self.lbl_erreur = ttk.Label(cadre_resultat, text="Erreur : —", font=('Segoe UI', 11))
        self.lbl_erreur.pack(anchor='w', padx=10, pady=2)

        self.lbl_volts = ttk.Label(cadre_resultat, text="", font=('Segoe UI', 10))
        self.lbl_volts.pack(anchor='w', padx=10, pady=2)

        # --- Barre d'état ---
        self.lbl_statut = ttk.Label(self, text="Prêt.", relief='sunken', anchor='w')
        self.lbl_statut.pack(fill='x', side='bottom')

    # ------------------------------------------------------------------
    #  Sélection des fichiers via l'explorateur
    # ------------------------------------------------------------------
    def _choisir_modele(self):
        chemin = filedialog.askopenfilename(
            title="Choisir un modèle",
            initialdir=os.path.abspath(MODELS_DIR),
            filetypes=[("Modèles Keras", "*.keras"), ("Tous les fichiers", "*.*")],
        )
        if not chemin:
            return
        self.chemin_modele_choisi = chemin
        self.lbl_modele.config(text=os.path.basename(chemin))
        self._statut(f"Modèle sélectionné : {os.path.basename(chemin)} (chargé au 1er clic sur Prédire)")

    def _choisir_son(self):
        initial = os.path.join(RECORDS_DIR_TEST, 'sons')
        if not os.path.isdir(initial):
            initial = RECORDS_DIR
        chemin = filedialog.askopenfilename(
            title="Choisir le fichier son",
            initialdir=initial,
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if not chemin:
            return
        self.path_son = chemin
        self.lbl_son.config(text=os.path.basename(chemin))

    def _choisir_vib(self):
        initial = os.path.join(RECORDS_DIR_TEST, 'vibrations')
        if not os.path.isdir(initial):
            initial = RECORDS_DIR
        chemin = filedialog.askopenfilename(
            title="Choisir le fichier vibration",
            initialdir=initial,
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if not chemin:
            return
        self.path_vib = chemin
        self.lbl_vib.config(text=os.path.basename(chemin))

    # ------------------------------------------------------------------
    #  Prédiction
    # ------------------------------------------------------------------
    def _statut(self, texte):
        self.lbl_statut.config(text=texte)
        self.update_idletasks()

    def _charger_modele_si_besoin(self):
        """Charge le modèle sélectionné (et ses hyperparamètres) si pas déjà en mémoire."""
        chemin = getattr(self, 'chemin_modele_choisi', None)
        if not chemin:
            raise ValueError("Choisis d'abord un modèle (.keras).")
        if chemin == self.chemin_modele:
            return  # déjà chargé

        self._statut(f"Chargement du modèle {os.path.basename(chemin)}…")
        self.model = tf.keras.models.load_model(chemin)
        self.chemin_modele = chemin

        self.hp, txt_trouve = charger_hyperparametres(chemin)
        if not txt_trouve:
            self._statut("⚠ Pas de .txt d'hyperparamètres à côté du modèle — valeurs par défaut utilisées.")

    def _lancer_prediction(self):
        if not self.path_son or not self.path_vib:
            messagebox.showwarning("Capture", "Choisis d'abord un fichier son ET un fichier vibration.")
            return

        self.btn_predire.config(state='disabled')
        try:
            self._charger_modele_si_besoin()

            self._statut("Prédiction en cours…")
            data_son, magnitude = charger_capture(self.path_son, self.path_vib)
            pred, n_fen = predire(self.model, data_son, magnitude, self.hp)

            # --- Affichage ---
            self.lbl_pred.config(text=f"Tension prédite : {pred:.1f} %")

            # Recherche des métadonnées (tension réelle, condition) via le nom du fichier son
            session = chercher_metadonnees(os.path.basename(self.path_son))
            niveau_reel = session.get('niveau_tension') if session else None
            condition   = session.get('condition_charge') if session else None

            if niveau_reel:
                reel = float(niveau_reel)
                erreur = abs(pred - reel)
                self.lbl_reel.config(text=f"Tension réelle : {reel:.1f} %")
                self.lbl_erreur.config(text=f"Erreur : {erreur:.1f} points")
            else:
                self.lbl_reel.config(text="Tension réelle : inconnue (capture absente des CSV)")
                self.lbl_erreur.config(text="Erreur : —")

            if condition in VOLTAGE_MAX:
                vmax = VOLTAGE_MAX[condition]
                self.lbl_volts.config(
                    text=f"≈ {pred / 100.0 * vmax:.1f} V (condition {condition}, max {vmax} V)")
            else:
                self.lbl_volts.config(text="")

            self._statut(f"OK — {os.path.basename(self.chemin_modele)}, {n_fen} fenêtres son.")

        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            self._statut("Erreur — voir message.")
        finally:
            self.btn_predire.config(state='normal')


if __name__ == "__main__":
    app = Application()
    app.mainloop()
