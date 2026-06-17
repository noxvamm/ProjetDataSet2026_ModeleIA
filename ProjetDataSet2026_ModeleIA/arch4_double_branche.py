import os
import numpy as np                # calcul numérique (tableaux, maths)
import pandas as pd               # lecture du CSV de métadonnées
import librosa                    # traitement du signal audio (mel-spectrogrammes)
import matplotlib.pyplot as plt   # tracé des graphiques de résultats
import tensorflow as tf           # bibliothèque de deep learning (le réseau de neurones)
from tensorflow.keras import layers, models   # briques pour construire le modèle
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau  # outils de pilotage de l'entraînement
from tqdm import tqdm             # barre de progression dans la console
import colorama
from colorama import Fore, Style  # couleurs du texte dans la console

colorama.init()

# --- CHEMINS (relatifs au script pour ne plus dépendre du CWD) ---
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR  = os.path.join(SCRIPT_DIR, '..', 'modeles')
DATA_BASE   = os.path.join(SCRIPT_DIR, 'dist', 'data')
CSV_PATH    = os.path.join(DATA_BASE, 'metadata_captures_moteur.csv')
RECORDS_DIR = os.path.join(DATA_BASE, 'records')

# =============================================================================
#  HYPERPARAMÈTRES — SIGNAL / MEL
#
#  Rôle : réglages qui contrôlent la transformation des signaux en images
#  (mel-spectrogrammes). Un « hyperparamètre » est une valeur fixée à la main
#  AVANT l'entraînement — à ne pas confondre avec les « poids » du réseau, que
#  le modèle apprend tout seul pendant l'entraînement.
# =============================================================================

# Taille finale de chaque spectrogramme donné au CNN (hauteur × largeur en pixels).
# Une image plus grande préserve plus de détails mais augmente la mémoire
# et le temps d'entraînement. Doit être un multiple de 2 (ex: 64, 128, 256).
IMG_SIZE = (128, 128)

# Écart relatif max toléré entre la fréquence déclarée dans le CSV et la fréquence
# effective calculée depuis le nombre de samples / durée.
# Au-delà de ce seuil un warning s'affiche pour signaler une erreur de saisie.
# Ex: 0.05 = un avertissement si l'écart dépasse 5 %.
SEUIL_ECART = 0.05

# --- Mel vibration (signal basse-fréquence : sr = 50 Hz) ---

# Taille de la fenêtre FFT pour la vibration.
# À 50 Hz, la fréquence max analysable est 25 Hz (Nyquist).
# → Plus VIB_N_FFT est grand : meilleure résolution fréquentielle (Hz/bin).
# → Ne pas dépasser 128–256 avec sr=50 Hz (au-delà les bins sont vides).
# Résolution actuelle : 50 / 128 ≈ 0.4 Hz/bin.
# Valeurs conseillées : 64 (grossier), 128 (standard), 256 (fin)
VIB_N_FFT  = 128

# Décalage entre deux fenêtres FFT consécutives pour la vibration.
# → Plus VIB_HOP est petit : plus de frames dans le spectrogramme (image plus large).
# → Règle habituelle : VIB_HOP = VIB_N_FFT / 4
# Valeurs conseillées : 16 (détaillé), 32 (standard), 64 (rapide)
VIB_HOP    = 32

# Nombre de bandes de fréquence Mel pour la vibration.
# Avec sr=50 Hz on ne couvre que 0–25 Hz → peu de bandes utiles.
# Valeurs conseillées : 16 (compact), 32 (standard)
VIB_N_MELS = 32

# --- Mel son (sr = 16 000 Hz) ---

# Nombre de bandes de fréquence Mel pour le son.
# → Plus il y en a : image plus haute, plus de détails fréquentiels visibles.
# Valeurs conseillées : 32 (rapide), 64 (standard), 128 (détaillé)
SON_N_MELS = 64

# =============================================================================
#  HYPERPARAMÈTRES — WINDOW SLICING & AUGMENTATION
#
#  Rôle : réglages pour FABRIQUER PLUS de données d'entraînement à partir d'un
#  petit dataset. Le « window slicing » découpe chaque capture en fenêtres ;
#  l'« augmentation de données » crée des variantes légèrement modifiées (bruit,
#  décalage temporel, masquage) pour forcer le modèle à généraliser au lieu de
#  mémoriser par cœur les quelques captures disponibles.
# =============================================================================

# Durée de chaque fenêtre de découpage du signal son (en secondes).
# → Plus courte : plus de segments générés par capture (plus de données),
#   mais chaque segment contient moins d'information.
# → Plus longue : moins de segments, mais chaque image est plus riche.
# Valeurs conseillées : 0.5 s (beaucoup de segments), 1.0 s (standard), 2.0 s (peu de segments)
WINDOW_DUREE_SON = 1.0

# Fraction de recouvrement entre deux fenêtres consécutives (0.0 à <1.0).
# → 0.5 = chaque fenêtre partage 50 % de son contenu avec la suivante.
# → Plus le recouvrement est grand : plus de segments générés.
# → 0.0 = fenêtres sans recouvrement (moins de données mais plus indépendantes).
# Valeurs conseillées : 0.0 (indépendant), 0.5 (standard), 0.75 (beaucoup de segments)
WINDOW_OVERLAP = 0.75

# Nombre de copies augmentées créées par segment d'entraînement.
# → 2 = chaque segment original génère 2 copies supplémentaires → ×3 de données au total.
# → Augmenter si le dataset est très petit. Réduire si l'entraînement est trop long.
# Valeurs conseillées : 1 (modéré), 2 (standard), 4 (agressif)
N_AUGMENT_TRAIN = 4

# Rapport signal/bruit cible pour l'augmentation par bruit gaussien (en dB).
# → Plus SNR est bas : plus de bruit ajouté → apprentissage plus robuste aux bruits de mesure.
# → Trop bas (< 10 dB) : le signal est noyé dans le bruit, le modèle ne peut plus apprendre.
# Valeurs conseillées : 30 dB (léger), 25 dB (standard), 15 dB (fort)
NOISE_SNR_DB = 25

# Fraction max du signal décalée lors du time shift (décalage temporel circulaire).
# → 0.10 = le signal peut être décalé de ±10 % de sa longueur.
# → Rend le modèle insensible au moment précis du début de capture.
# Valeurs conseillées : 0.05 (léger), 0.10 (standard), 0.20 (fort)
TIME_SHIFT_PCT = 0.10

# SpecAugment : fraction de colonnes (temps) masquées à zéro sur le spectrogramme.
# → Oblige le modèle à ne pas trop dépendre d'un instant particulier.
# Valeurs conseillées : 0.05 (léger), 0.10 (standard), 0.20 (fort)
SPECAUG_TIME_FRAC = 0.10

# SpecAugment : fraction de lignes (fréquences) masquées à zéro sur le spectrogramme.
# → Oblige le modèle à ne pas trop dépendre d'une fréquence particulière.
# Valeurs conseillées : 0.05 (léger), 0.10 (standard), 0.20 (fort)
SPECAUG_FREQ_FRAC = 0.10

# Nombre de masques appliqués (temporels + fréquentiels) par image augmentée.
# → Plus il y en a : augmentation plus agressive.
# Valeurs conseillées : 1 (léger), 2 (standard), 3 (fort)
SPECAUG_N_MASKS = 2

# =============================================================================
#  HYPERPARAMÈTRES — ENTRAÎNEMENT
#
#  Rôle : réglages qui pilotent l'apprentissage lui-même — quelle part des
#  données réserver au test, combien de fois revoir les données (époques), par
#  quels paquets (batch), et la graine aléatoire pour des résultats reproductibles.
# =============================================================================

# Proportion des captures réservée à l'évaluation finale (pas à l'entraînement).
# → 0.2 = 20 % des captures en test, 80 % en train.
# → Avec peu de captures (< 10), réduire à 0.1 pour garder plus de données en train.
TEST_RATIO = 0.2

# Nombre maximum d'époques (passages complets sur les données d'entraînement).
# L'EarlyStopping arrêtera avant si le modèle converge.
# Augmenter si l'entraînement est encore en cours quand il s'arrête.
EPOCHS = 60

# Nombre de segments traités simultanément avant chaque mise à jour des poids.
# → Petit (8–16) : plus stable avec peu de données, mais entraînement plus lent.
# → Grand (32–64) : plus rapide, mais moins précis avec peu de données.
BATCH_SIZE = 16

# Graine aléatoire pour la reproductibilité (split, initialisation, augmentation).
# Changer cette valeur pour tester différentes répartitions train/test.
SEED = 42

np.random.seed(SEED)
tf.random.set_seed(SEED)


# =============================================================================
#  UTILS SIGNAL — Boîte à outils de traitement du signal
#
#  Rôle : toutes les fonctions qui préparent les signaux bruts (son, vibration)
#  avant de les donner au modèle : normalisation, découpage en fenêtres,
#  augmentation (bruit, décalage, SpecAugment) et conversion en mel-spectrogrammes.
#  Ces fonctions ne font AUCUN apprentissage : elles ne font que transformer des
#  données. C'est l'équivalent de la « préparation des ingrédients » avant cuisson.
# =============================================================================

def sauvegarder_hyperparametres(chemin_modele):
    """Enregistre les hyperparamètres dans un .txt du même nom que le modèle."""
    chemin_txt = chemin_modele.replace(".keras", ".txt")
    with open(chemin_txt, "w", encoding="utf-8") as f:
        f.write("=== HYPERPARAMÈTRES ===\n\n")
        f.write("-- Signal / Mel --\n")
        f.write(f"IMG_SIZE           = {IMG_SIZE}\n")
        f.write(f"SON_N_MELS         = {SON_N_MELS}\n")
        f.write(f"VIB_N_FFT          = {VIB_N_FFT}\n")
        f.write(f"VIB_HOP            = {VIB_HOP}\n")
        f.write(f"VIB_N_MELS         = {VIB_N_MELS}\n\n")
        f.write("-- Window slicing & Augmentation --\n")
        f.write(f"WINDOW_DUREE_SON   = {WINDOW_DUREE_SON}\n")
        f.write(f"WINDOW_OVERLAP     = {WINDOW_OVERLAP}\n")
        f.write(f"N_AUGMENT_TRAIN    = {N_AUGMENT_TRAIN}\n")
        f.write(f"NOISE_SNR_DB       = {NOISE_SNR_DB}\n")
        f.write(f"TIME_SHIFT_PCT     = {TIME_SHIFT_PCT}\n")
        f.write(f"SPECAUG_TIME_FRAC  = {SPECAUG_TIME_FRAC}\n")
        f.write(f"SPECAUG_FREQ_FRAC  = {SPECAUG_FREQ_FRAC}\n")
        f.write(f"SPECAUG_N_MASKS    = {SPECAUG_N_MASKS}\n\n")
        f.write("-- Entraînement --\n")
        f.write(f"TEST_RATIO         = {TEST_RATIO}\n")
        f.write(f"EPOCHS             = {EPOCHS}\n")
        f.write(f"BATCH_SIZE         = {BATCH_SIZE}\n")
        f.write(f"SEED               = {SEED}\n")
    print(f"{Fore.CYAN}Hyperparamètres sauvegardés : {chemin_txt}{Style.RESET_ALL}")


def normaliser(spectrogramme):
    """Normalise un spectrogramme dB entre 0 et 1."""
    s_min = spectrogramme.min()
    s_max = spectrogramme.max()
    return (spectrogramme - s_min) / (s_max - s_min + 1e-9)


def verifier_frequence_effective(nb_samples, duree, sr_declare, signal, session_id):
    """Compare fréquence effective (nb_samples / duree) à la fréquence déclarée IHM."""
    if duree <= 0:
        print(f"{Fore.YELLOW}Session {session_id} ({signal}) : durée invalide ({duree}s).{Style.RESET_ALL}")
        return 0.0
    sr_effective = nb_samples / duree
    ecart = abs(sr_effective - sr_declare) / sr_declare if sr_declare > 0 else 1.0
    if ecart > SEUIL_ECART:
        print(
            f"{Fore.YELLOW} Session {session_id} ({signal}) : "
            f"fréquence effective {sr_effective:.1f} Hz vs déclarée {sr_declare:.0f} Hz "
            f"(écart {ecart * 100:.1f} %){Style.RESET_ALL}"
        )
    return sr_effective


def decouper_son_en_fenetres(signal, sr, duree_fenetre, overlap):
    """Découpe un signal en fenêtres avec recouvrement. Retourne une liste d'arrays."""
    taille_fen = int(duree_fenetre * sr)
    if len(signal) < taille_fen:
        # Signal trop court : on retourne tel quel (zero-padding implicite côté librosa)
        return [signal]
    pas = max(1, int(taille_fen * (1 - overlap)))
    return [signal[d:d + taille_fen] for d in range(0, len(signal) - taille_fen + 1, pas)]


def ajouter_bruit_gaussien(signal, snr_db):
    """Ajoute un bruit gaussien selon un SNR cible (en dB)."""
    puissance_signal = np.mean(signal ** 2)
    if puissance_signal <= 0:
        return signal
    snr_lineaire = 10 ** (snr_db / 10)
    puissance_bruit = puissance_signal / snr_lineaire
    bruit = np.random.normal(0, np.sqrt(puissance_bruit), size=signal.shape)
    return signal + bruit


def time_shift(signal, max_shift_pct):
    """Décalage temporel circulaire (max_shift_pct de la longueur)."""
    n = len(signal)
    if n == 0:
        return signal
    max_shift = max(1, int(n * max_shift_pct))
    shift = np.random.randint(-max_shift, max_shift + 1)
    return np.roll(signal, shift)


def spec_augment(mel_2d, time_mask_frac, freq_mask_frac, n_masks):
    """Masquage temporel + fréquentiel d'un mel-spectrogramme 2D (SpecAugment)."""
    mel = mel_2d.copy()
    n_freq, n_time = mel.shape
    for _ in range(n_masks):
        # Masque temporel
        t_max = max(1, int(n_time * time_mask_frac))
        t = np.random.randint(0, t_max + 1)
        if t > 0 and n_time - t > 0:
            t0 = np.random.randint(0, n_time - t)
            mel[:, t0:t0 + t] = 0.0
        # Masque fréquentiel
        f_max = max(1, int(n_freq * freq_mask_frac))
        f = np.random.randint(0, f_max + 1)
        if f > 0 and n_freq - f > 0:
            f0 = np.random.randint(0, n_freq - f)
            mel[f0:f0 + f, :] = 0.0
    return mel


def signal_vers_mel_son(signal, sr):
    """Transforme un signal sonore (1D) en image 2D (mel-spectrogramme) pour le CNN.

    Un mel-spectrogramme est une « photo » du son : l'axe horizontal est le
    temps, l'axe vertical la fréquence, et la couleur l'intensité. L'échelle
    'mel' imite l'oreille humaine (plus fine dans les graves que dans les aigus)."""
    # melspectrogram : découpe le son en petites tranches de temps et calcule,
    #   pour chacune, l'énergie présente dans chaque bande de fréquence.
    S = librosa.feature.melspectrogram(y=signal.astype(float), sr=sr, n_mels=SON_N_MELS)
    # power_to_db : convertit l'énergie en décibels (échelle logarithmique),
    #   comme la perçoit l'oreille. Fait ressortir les détails de faible intensité.
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)                          # ramène les valeurs entre 0 et 1
    # tf.image.resize : force toutes les images à la même taille IMG_SIZE,
    #   car le CNN exige une entrée de dimensions fixes.
    return tf.image.resize(np.expand_dims(S_dB, -1), IMG_SIZE).numpy()


def signal_vers_mel_vib(signal, sr):
    """Mel-spectrogramme adapté à un signal basse-fréquence (vibration)."""
    n_fft = min(VIB_N_FFT, max(8, len(signal)))
    hop   = max(1, min(VIB_HOP, max(1, len(signal) // 4)))
    S = librosa.feature.melspectrogram(
        y=signal.astype(float), sr=sr, n_mels=VIB_N_MELS,
        n_fft=n_fft, hop_length=hop
    )
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)
    return tf.image.resize(np.expand_dims(S_dB, -1), IMG_SIZE).numpy()


# =============================================================================
#  CHARGEMENT + CONSTRUCTION DES SEGMENTS
#
#  Rôle : lire les fichiers CSV de captures (son + vibration), les nettoyer, et
#  les transformer en « segments » prêts pour le modèle — c'est-à-dire en couples
#  d'images (mel_son, mel_vib) accompagnés du label de tension à prédire.
# =============================================================================

def tronquer_duree(arr, duree_s):
    """Coupe un tableau [temps_ms, ...] à ses `duree_s` premières secondes.
       Garde-fou contre les fichiers concaténés (bug d'incrémentation session_id)
       qui contiennent plusieurs captures collées : on ne conserve que la 1ère.
       Les timestamps (col 0) sont en millisecondes (son 'Temps', vib 'Timestamp')."""
    if arr.ndim == 1 or len(arr) == 0:
        return arr
    t = arr[:, 0]
    mask = (t - t[0]) <= (duree_s * 1000.0)
    if mask.sum() < 10:          # timestamps inattendus → on ne tronque pas
        return arr
    return arr[mask]


def charger_sessions(csv_path):
    """Lit le CSV et retourne une liste de dicts (signaux bruts par capture)."""
    df = pd.read_csv(csv_path)
    sessions = []
    for index, row in tqdm(df.iterrows(), total=len(df), desc="Chargement"):
        try:
            sr_son_declare = float(row['frequence_son'])
            sr_vib_declare = float(row['frequence_vibration'])
            duree          = float(row['duree'])
            session_id     = int(row.get('id_session', index))
            niveau         = float(row['niveau_tension']) / 100.0

            path_son = os.path.join(RECORDS_DIR, 'sons', row['fichier_son'])
            arr_son  = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=(0, 1))
            arr_son  = tronquer_duree(arr_son, duree)   # garde les `duree` 1ères secondes
            data_son = arr_son[:, 1]
            verifier_frequence_effective(len(data_son), duree, sr_son_declare, "son", session_id)

            path_vib  = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
            arr_vib   = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(0, 1, 2, 3))
            arr_vib   = tronquer_duree(arr_vib, duree)
            data_vibs = arr_vib[:, 1:4]
            magnitude = np.abs(data_vibs[:, 2])
            verifier_frequence_effective(len(magnitude), duree, sr_vib_declare, "vibration", session_id)

            sessions.append({
                'id_session': session_id,
                'son':        data_son.astype(float),
                'sr_son':     sr_son_declare,
                'vib_mag':    magnitude.astype(float),
                'sr_vib':     sr_vib_declare,
                'niveau':     niveau,
            })
        except Exception as e:
            print(f"{Fore.RED}Erreur ligne {index}: {e}{Style.RESET_ALL}")
            continue
    return sessions


def construire_segments(sessions, augmenter=False):
    """Génère les couples (mel_son, mel_vib) à partir des signaux bruts.
       - 1 mel vibration par capture (signal trop court pour slicer utilement)
       - N mels son par capture via window slicing
       - Si augmenter=True : ajoute N_AUGMENT_TRAIN copies augmentées par segment
       Retourne 4 arrays : X_son, X_vib, y, ids_capture (pour regrouper à l'éval)."""
    X_son, X_vib, y, ids = [], [], [], []
    for s in tqdm(sessions, desc="Segments " + ("(train+aug)" if augmenter else "(test)")):
        mel_vib = signal_vers_mel_vib(s['vib_mag'], s['sr_vib'])
        fenetres = decouper_son_en_fenetres(s['son'], s['sr_son'], WINDOW_DUREE_SON, WINDOW_OVERLAP)

        for f in fenetres:
            # Original
            mel_son = signal_vers_mel_son(f, s['sr_son'])
            X_son.append(mel_son);  X_vib.append(mel_vib)
            y.append(s['niveau']);  ids.append(s['id_session'])

            if augmenter:
                for _ in range(N_AUGMENT_TRAIN):
                    f_aug = ajouter_bruit_gaussien(time_shift(f, TIME_SHIFT_PCT), NOISE_SNR_DB)
                    mel_son_aug = signal_vers_mel_son(f_aug, s['sr_son'])
                    # SpecAugment sur l'image 2D
                    mel_son_aug_2d = mel_son_aug.squeeze(-1)
                    mel_son_aug_2d = spec_augment(
                        mel_son_aug_2d, SPECAUG_TIME_FRAC, SPECAUG_FREQ_FRAC, SPECAUG_N_MASKS
                    )
                    mel_son_aug = np.expand_dims(mel_son_aug_2d, -1)
                    X_son.append(mel_son_aug);  X_vib.append(mel_vib)
                    y.append(s['niveau']);      ids.append(s['id_session'])

    return (np.array(X_son), np.array(X_vib),
            np.array(y, dtype=np.float32), np.array(ids))


# =============================================================================
#  MODÈLE — Réseau de neurones convolutif (CNN) à double branche
#
#  Rôle : définir l'architecture qui transforme les deux spectrogrammes
#  (son + vibration) en une seule prédiction de tension.
#
#  Principe « double branche » : le son et la vibration sont deux signaux de
#  nature physique différente. Chaque branche est un mini-CNN indépendant qui
#  apprend ses propres filtres ; les deux ne se rejoignent qu'à la fin, juste
#  avant la décision. Un CNN (réseau convolutif) est spécialisé dans l'analyse
#  d'images : il empile des couches qui repèrent des motifs de plus en plus
#  abstraits — ici, sur les spectrogrammes vus comme des images.
# =============================================================================

def construire_modele():
    # --- BRANCHE SON ---
    # Input : porte d'entrée de la branche. shape = (128, 128, 1) = une image en
    #   niveaux de gris de 128×128 pixels (le « 1 » = un seul canal de couleur).
    entree_son = layers.Input(shape=(IMG_SIZE[0], IMG_SIZE[1], 1), name="entree_son")

    # Bloc 1 — Détection des motifs de base (harmoniques simples, bordures)
    # Conv2D : couche de convolution. Elle fait glisser de petits filtres sur
    #   l'image (le spectrogramme) pour y repérer des motifs locaux.
    # 32 : nombre de filtres. Plus il y en a, plus le réseau détecte de motifs différents.
    # Doubler (→ 64) augmente la capacité mais aussi le temps de calcul.
    # (3, 3) : taille du filtre. 3×3 est standard. 5×5 capte des motifs plus larges.
    # activation='relu' : garde les valeurs positives et met les négatives à zéro.
    #   Cette « non-linéarité » est indispensable pour apprendre des relations
    #   complexes (sans elle, le réseau ne saurait faire que des additions simples).
    # padding='same' : ajoute une bordure de zéros pour que l'image garde la même
    #   taille après la convolution (sinon elle rétrécirait à chaque couche).
    x1 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_son)
    # BatchNormalization : recentre et remet à l'échelle les valeurs entre deux
    #   couches → stabilise et accélère nettement l'entraînement.
    x1 = layers.BatchNormalization()(x1)
    # MaxPooling2D : réduit l'image par 2 en ne gardant que la valeur maximale de
    #   chaque carré 2×2 → résume l'info et rend le modèle insensible aux petits décalages.
    x1 = layers.MaxPooling2D((2, 2))(x1)

    # Bloc 2 — Détection de motifs plus complexes (combinaisons de fréquences)
    x1 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.MaxPooling2D((2, 2))(x1)

    # Bloc 3 — Motifs très abstraits liés au niveau de tension
    # 128 : niveau d'abstraction maximal. Augmenter à 256 pour plus de capacité
    # (nécessite plus de données pour éviter l'overfitting).
    x1 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)
    # Remplace Flatten : calcule la moyenne de chaque carte de features.
    # Produit un vecteur compact de 128 valeurs résumant le spectrogramme son.
    x1 = layers.GlobalAveragePooling2D(name="features_son")(x1)

    # --- BRANCHE VIBRATION ---
    # Structure identique à la branche son, poids indépendants :
    # chaque branche apprend ses propres filtres adaptés à son type de signal.
    entree_vib = layers.Input(shape=(IMG_SIZE[0], IMG_SIZE[1], 1), name="entree_vibration")

    # Bloc 1 vibration
    x2 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_vib)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)

    # Bloc 2 vibration
    x2 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)

    # Bloc 3 vibration — produit un vecteur compact de 128 valeurs
    x2 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.GlobalAveragePooling2D(name="features_vibration")(x2)

    # --- FUSION ---
    # Concatène les deux vecteurs → 256 valeurs (128 son + 128 vib).
    fusion = layers.Concatenate(name="fusion_son_vibration")([x1, x2])

    # Dense : couche « entièrement connectée » où chaque neurone voit TOUTES les
    #   valeurs précédentes (au contraire de Conv2D qui ne regarde que localement).
    #   C'est la couche de décision : 64 neurones analysent la combinaison
    #   son + vibration. Augmenter à 128/256 si le modèle peine à trouver la règle.
    z = layers.Dense(64, activation='relu')(fusion)

    # Dropout : désactive aléatoirement X % des neurones pendant l'entraînement.
    # → Empêche le modèle de mémoriser les données au lieu d'apprendre des règles générales.
    # → Augmenter (→ 0.5) si val_loss remonte alors que train_loss continue de descendre.
    # → Réduire (→ 0.1) si le modèle apprend trop lentement.
    z = layers.Dropout(0.3)(z)

    # Sortie sigmoïde : contraint la prédiction entre 0 et 1 (tension normalisée).
    # Cohérent avec les labels normalisés niveau_tension / 100.
    sortie = layers.Dense(1, activation='sigmoid', name="tension")(z)

    model = models.Model(
        inputs=[entree_son, entree_vib], outputs=sortie,
        name="arch4_double_branche"
    )
    # compile : configure COMMENT le modèle va apprendre.
    # optimizer='adam' : l'algorithme qui ajuste les poids du réseau à chaque
    #   étape. Adam est le choix standard, robuste et rapide. Remplacer par
    #   Adam(learning_rate=0.0005) pour un réglage plus fin si le modèle oscille.
    # loss='mse' : erreur quadratique moyenne — la quantité que le modèle cherche
    #   à minimiser. Le carré pénalise très fortement les grosses erreurs.
    # metrics=['mae'] : erreur absolue moyenne, affichée pour SUIVRE l'entraînement.
    #   Plus lisible que la MSE car exprimée dans l'unité du label (points de %).
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model


# =============================================================================
#  PIPELINE PRINCIPAL — Déroulé complet de l'entraînement
#
#  Rôle : le « chef d'orchestre » exécuté quand on lance le script. Il enchaîne :
#  chargement des sessions → découpage train/test PAR CAPTURE (pour éviter le
#  « data leakage », c.-à-d. qu'un même enregistrement se retrouve à la fois en
#  entraînement et en test, ce qui fausserait le score) → construction des
#  segments → entraînement → évaluation (MAE) → graphiques de résultats.
# =============================================================================

print(f"\n{Fore.CYAN}=== Chargement des sessions ==={Style.RESET_ALL}")
sessions = charger_sessions(CSV_PATH)
print(f"{Fore.GREEN}{len(sessions)} sessions chargées.{Style.RESET_ALL}")

if len(sessions) == 0:
    print(f"{Fore.RED}ERREUR : aucune donnée chargée. Vérifie le CSV et les fichiers son/vib.{Style.RESET_ALL}")
elif len(sessions) < 5:
    print(f"{Fore.YELLOW}⚠ Trop peu de sessions pour un split train/test fiable ({len(sessions)} < 5). "
          f"On entraîne sur tout sans validation pour vérifier le pipeline.{Style.RESET_ALL}")
    X_son, X_vib, y, ids = construire_segments(sessions, augmenter=True)
    print(f"  Segments générés : {len(y)}")
    model = construire_modele()
    model.summary()
    history = model.fit([X_son, X_vib], y, epochs=EPOCHS, batch_size=BATCH_SIZE, verbose=1)
    chemin = os.path.join(MODELS_DIR, "modele_arch4_smoke_test.keras")
    model.save(chemin)
    sauvegarder_hyperparametres(chemin)
    print(f"{Fore.GREEN}Smoke test OK — pipeline fonctionnel.{Style.RESET_ALL}")
else:
    # Split par capture (pas par segment !) pour éviter le data leakage
    rng = np.random.default_rng(SEED)
    indices = np.arange(len(sessions))
    rng.shuffle(indices)
    n_test = max(1, int(len(sessions) * TEST_RATIO))
    sessions_test  = [sessions[i] for i in indices[:n_test]]
    sessions_train = [sessions[i] for i in indices[n_test:]]
    print(f"  Train : {len(sessions_train)} captures")
    print(f"  Test  : {len(sessions_test)} captures")

    X_son_train, X_vib_train, y_train, ids_train = construire_segments(sessions_train, augmenter=True)
    X_son_test,  X_vib_test,  y_test,  ids_test  = construire_segments(sessions_test,  augmenter=False)
    print(f"  Segments train : {len(y_train)} (avec augmentation ×{1 + N_AUGMENT_TRAIN})")
    print(f"  Segments test  : {len(y_test)}")

    model = construire_modele()
    model.summary()

    callbacks = [
        # Arrête l'entraînement si val_loss ne s'améliore pas pendant N époques.
        # patience=8 : on attend 8 époques sans progrès avant d'arrêter.
        #   → Augmenter (→ 12) si le modèle a besoin de temps pour sortir d'un plateau.
        #   → Réduire (→ 5) pour un arrêt plus rapide et économiser du temps.
        # restore_best_weights : recharge les poids de la meilleure époque à la fin.
        EarlyStopping(patience=8, restore_best_weights=True, monitor='val_loss'),

        # Divise le learning rate par `factor` si val_loss stagne pendant `patience` époques.
        # → Permet de "zoomer" sur le minimum quand le modèle ne progresse plus.
        # patience=4 : réduit le LR après 4 époques sans amélioration.
        # factor=0.5 : divise le LR par 2 à chaque déclenchement (ex: 0.001 → 0.0005).
        # min_lr=1e-6 : plancher en dessous duquel le LR ne descend plus.
        ReduceLROnPlateau(patience=4, factor=0.5, monitor='val_loss', min_lr=1e-6),

    ]

    print(f"\n{Fore.MAGENTA}=== Entraînement ==={Style.RESET_ALL}")
    history = model.fit(
        [X_son_train, X_vib_train], y_train,
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        validation_data=([X_son_test, X_vib_test], y_test),
        callbacks=callbacks, verbose=1,
    )
    chemin = os.path.join(MODELS_DIR, "modele_arch4_v4_renforce.keras")
    model.save(chemin)
    sauvegarder_hyperparametres(chemin)
    print(f"{Fore.GREEN}Modèle sauvegardé.{Style.RESET_ALL}")

    # ============ ÉVALUATION : segment + capture ============
    loss, mae = model.evaluate([X_son_test, X_vib_test], y_test, verbose=0)
    y_pred_seg = model.predict([X_son_test, X_vib_test], verbose=0).flatten()

    # Agrégation par capture (1 prédiction = moyenne des segments d'une même capture)
    captures_uniques = np.unique(ids_test)
    y_true_capture = np.array([y_test[ids_test == cid].mean()    for cid in captures_uniques])
    y_pred_capture = np.array([y_pred_seg[ids_test == cid].mean() for cid in captures_uniques])
    mae_capture = float(np.mean(np.abs(y_true_capture - y_pred_capture)))

    print(f"\n{Fore.CYAN}=== ÉVALUATION FINALE ==={Style.RESET_ALL}")
    print(f"  MSE par segment    : {loss:.4f}")
    print(f"  MAE par segment    : {mae * 100:.2f} % de tension")
    print(f"  MAE par capture    : {mae_capture * 100:.2f} % de tension  (← métrique principale)")

    # ============ VISUALISATION ============
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].plot(history.history['loss'], label='Train')
    axes[0].plot(history.history['val_loss'], label='Validation')
    axes[0].set_title("Loss au cours de l'entraînement")
    axes[0].set_xlabel('Epoch'); axes[0].set_ylabel('MSE')
    axes[0].legend(); axes[0].grid()

    axes[1].scatter(y_true_capture * 100, y_pred_capture * 100, alpha=0.7, s=80, label='Captures')
    axes[1].plot([0, 100], [0, 100], 'r--', label="Prédiction parfaite")
    axes[1].set_xlabel("Tension réelle (%)")
    axes[1].set_ylabel("Tension prédite (%)")
    axes[1].set_title(f"Prédictions vs réalité — MAE = {mae_capture*100:.1f} %")
    axes[1].legend(); axes[1].grid()
    axes[1].set_xlim(-5, 105); axes[1].set_ylim(-5, 105)

    plt.tight_layout()
    plt.savefig(os.path.join(MODELS_DIR, "resultats_modele_renforce.png"), dpi=120)
    plt.show()
