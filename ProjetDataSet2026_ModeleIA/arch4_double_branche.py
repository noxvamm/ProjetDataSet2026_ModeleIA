# =============================================================================
#  ARCHITECTURE 4 — DOUBLE BRANCHE (Son + Vibration séparés) — Version moteur
#  Projet BTS CIEL Dataset26 — Estimation du niveau de tension moteur (régression)
#
#  Ajouts par rapport à la v1 :
#   - Window slicing : chaque capture son de 15 s est découpée en fenêtres de 1 s
#     avec 50 % de recouvrement → ~29 segments d'entraînement par capture
#   - Augmentation TRAIN UNIQUEMENT : bruit gaussien + time shift + SpecAugment
#     (masquage temporel et fréquentiel sur le mel-spectrogramme)
#   - Mel vibration adapté à un signal basse-fréquence (n_fft, hop_length)
#   - Split TRAIN/TEST par capture (pas par segment) → pas de data leakage
#   - Évaluation : MAE moyennée par capture (1 prédiction = moyenne des segments)
#   - Vibration : |VZ| seul (au lieu de magnitude 3-axes) — voir CLAUDE.md (Option A)
# =============================================================================

import os
import numpy as np
import pandas as pd
import librosa
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tqdm import tqdm
import colorama
from colorama import Fore, Style

colorama.init()

# --- CHEMINS (relatifs au script pour ne plus dépendre du CWD) ---
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_BASE   = os.path.join(SCRIPT_DIR, 'dist', 'data')
CSV_PATH    = os.path.join(DATA_BASE, 'metadata_captures_moteur.csv')
RECORDS_DIR = os.path.join(DATA_BASE, 'records')

# --- HYPERPARAMÈTRES SIGNAL / MEL ---
IMG_SIZE        = (128, 128)
SEUIL_ECART     = 0.05      # 5 % d'écart max entre fréquence déclarée et effective avant warning

# Mel vibration (signal basse-fréquence : 50 Hz × 15 s = 750 pts en théorie)
VIB_N_FFT       = 128
VIB_HOP         = 32
VIB_N_MELS      = 32

# Mel son (16 kHz)
SON_N_MELS      = 64

# --- HYPERPARAMÈTRES WINDOW SLICING / AUGMENTATION ---
WINDOW_DUREE_SON     = 1.0   # secondes par fenêtre son
WINDOW_OVERLAP       = 0.5   # 50 % de recouvrement
N_AUGMENT_TRAIN      = 2     # copies augmentées par segment de train (en plus de la copie originale)
NOISE_SNR_DB         = 25
TIME_SHIFT_PCT       = 0.10
SPECAUG_TIME_FRAC    = 0.10
SPECAUG_FREQ_FRAC    = 0.10
SPECAUG_N_MASKS      = 2

# --- HYPERPARAMÈTRES ENTRAÎNEMENT ---
TEST_RATIO    = 0.2
EPOCHS        = 60
BATCH_SIZE    = 32
SEED          = 42

np.random.seed(SEED)
tf.random.set_seed(SEED)


# =============================================================================
#  UTILS SIGNAL
# =============================================================================

def normaliser(spectrogramme):
    """Normalise un spectrogramme dB entre 0 et 1."""
    s_min = spectrogramme.min()
    s_max = spectrogramme.max()
    return (spectrogramme - s_min) / (s_max - s_min + 1e-9)


def verifier_frequence_effective(nb_samples, duree, sr_declare, signal, session_id):
    """Compare fréquence effective (nb_samples / duree) à la fréquence déclarée IHM."""
    if duree <= 0:
        print(f"{Fore.YELLOW}⚠ Session {session_id} ({signal}) : durée invalide ({duree}s).{Style.RESET_ALL}")
        return 0.0
    sr_effective = nb_samples / duree
    ecart = abs(sr_effective - sr_declare) / sr_declare if sr_declare > 0 else 1.0
    if ecart > SEUIL_ECART:
        print(
            f"{Fore.YELLOW}⚠ Session {session_id} ({signal}) : "
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
    """Mel-spectrogramme du son normalisé puis redimensionné en IMG_SIZE."""
    S = librosa.feature.melspectrogram(y=signal.astype(float), sr=sr, n_mels=SON_N_MELS)
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)
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
# =============================================================================

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
            data_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=1)
            verifier_frequence_effective(len(data_son), duree, sr_son_declare, "son", session_id)

            path_vib  = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
            data_vibs = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(1, 2, 3))
            # NOTE (6 mai 2026) — Décision Option A : on n'utilise que l'axe Z.
            # Le capteur WTVB01-BT50 est monté tel que VX et VY sont perpendiculaires
            # à la direction principale de vibration du moteur → VX≈271 cst et VY≈1 cst
            # (bruit interne MEMS sous seuil). La magnitude 3-axes √(VX²+VY²+VZ²)
            # aurait un plancher de ~271 qui écrase la dynamique basse de VZ.
            # En prenant |VZ| seul, on récupère la vraie dynamique signal du moteur.
            # Réversible : décommenter la ligne du dessous pour revenir à la magnitude 3 axes.
            # magnitude = np.sqrt(data_vibs[:, 0] ** 2 + data_vibs[:, 1] ** 2 + data_vibs[:, 2] ** 2)
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
#  MODÈLE
# =============================================================================

def construire_modele():
    entree_son = layers.Input(shape=(IMG_SIZE[0], IMG_SIZE[1], 1), name="entree_son")
    x1 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_son)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.MaxPooling2D((2, 2))(x1)
    x1 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.MaxPooling2D((2, 2))(x1)
    x1 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.GlobalAveragePooling2D(name="features_son")(x1)

    entree_vib = layers.Input(shape=(IMG_SIZE[0], IMG_SIZE[1], 1), name="entree_vibration")
    x2 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_vib)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)
    x2 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)
    x2 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.GlobalAveragePooling2D(name="features_vibration")(x2)

    fusion = layers.Concatenate(name="fusion_son_vibration")([x1, x2])
    z = layers.Dense(64, activation='relu')(fusion)
    z = layers.Dropout(0.3)(z)
    sortie = layers.Dense(1, activation='sigmoid', name="tension")(z)

    model = models.Model(
        inputs=[entree_son, entree_vib], outputs=sortie,
        name="arch4_double_branche"
    )
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model


# =============================================================================
#  PIPELINE PRINCIPAL
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
    model.save("modele_arch4_smoke_test.keras")
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
        EarlyStopping(patience=8, restore_best_weights=True, monitor='val_loss'),
        ReduceLROnPlateau(patience=4, factor=0.5, monitor='val_loss', min_lr=1e-6),
        ModelCheckpoint('modele_arch4_best.keras', save_best_only=True, monitor='val_loss'),
    ]

    print(f"\n{Fore.MAGENTA}=== Entraînement ==={Style.RESET_ALL}")
    history = model.fit(
        [X_son_train, X_vib_train], y_train,
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        validation_data=([X_son_test, X_vib_test], y_test),
        callbacks=callbacks, verbose=1,
    )
    model.save("modele_arch4_double_branche.keras")
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
    plt.savefig("resultats_modele.png", dpi=120)
    plt.show()
