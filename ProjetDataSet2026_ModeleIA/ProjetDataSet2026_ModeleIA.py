"""
Pipeline IA Dataset26 — FS9/FS11/FS12
Étudiant 3 — Analyse d'usure d'outil CNC par son + vibration.

Chargement des sessions labellisées (metadata_captures.csv),
fusion son + vibration en spectrogrammes mel empilés,
entraînement d'un CNN de régression sur le niveau d'usure (0-100%).
"""

import os
import numpy as np
import pandas as pd
import librosa
import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.callbacks import EarlyStopping # Import ajouté pour l'arrêt précoce
from sklearn.model_selection import train_test_split
from tqdm import tqdm
import colorama
from colorama import Fore, Style
import matplotlib.pyplot as plt

colorama.init()

# --- CONFIGURATION ---
CSV_PATH = "data/metadata_captures.csv"
SONS_DIR = "data/records/sons"              
VIBRATIONS_DIR = "data/records/vibrations"  
SAVE_IMAGES_DIR = "visualisation_spectrogrammes"
MODEL_OUT = "modele_cnn_n1.keras"

# Paramètres spectrogramme
N_MELS = 64
TARGET_WIDTH = 128          
N_FFT = 64
HOP_LENGTH = 16

# Normalisation du label (FS7 : niveau_usure exprimé en 0-100%)
USURE_MIN = 0.0
USURE_MAX = 100.0

os.makedirs(SAVE_IMAGES_DIR, exist_ok=True)


def charger_signal(chemin, usecols):
    """Charge un signal CSV. Retourne None si fichier absent / vide / corrompu."""
    if not os.path.exists(chemin):
        print(f"  [WARN] Fichier absent : {chemin}")
        return None
    try:
        # Ajout de ndmin=1 pour éviter les erreurs si le fichier ne contient qu'une ligne
        data = np.loadtxt(chemin, delimiter=',', skiprows=1, usecols=usecols, ndmin=1)
        if data.size == 0:
            print(f"  [WARN] Fichier vide : {chemin}")
            return None
        return data
    except Exception as e:
        print(f"  [WARN] Lecture impossible {chemin} : {e}")
        return None


def preprocess_signal(signal):
    """
    Nettoie le signal : retire le DC offset et normalise l'amplitude.
    Crucial pour que le modèle se concentre sur la forme du signal et non son amplitude brute.
    """
    # 1. Retirer la composante continue (DC Offset)
    signal = signal - np.mean(signal)
    
    # 2. Normalisation entre -1 et 1 (ou proche) pour stabiliser l'entraînement
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        signal = signal / max_val
        
    return signal


def signal_vers_spectrogramme(signal, sr):
    """
    Convertit un signal 1D en spectrogramme mel (dB), redimensionné à (N_MELS, TARGET_WIDTH).
    """
    signal = signal.astype(np.float32)

    # Padding si le signal est plus court que la fenêtre FFT
    if len(signal) < N_FFT:
        signal = np.pad(signal, (0, N_FFT - len(signal)))

    S = librosa.feature.melspectrogram(
        y=signal, sr=sr, n_mels=N_MELS, n_fft=N_FFT, hop_length=HOP_LENGTH
    )
    S_dB = librosa.power_to_db(S, ref=np.max)

    # Redimensionnement à largeur fixe (N_MELS, TARGET_WIDTH)
    S_resized = tf.image.resize(
        np.expand_dims(S_dB, -1), (N_MELS, TARGET_WIDTH)
    ).numpy().squeeze(-1)
    return S_resized


def charger_et_transformer(csv_path):
    """
    Parcourt le CSV de métadonnées, retourne :
      X : tableau de spectrogrammes fusionnés, shape (N, 128, 128, 1)
      y : labels d'usure normalisés 0-1, shape (N,)
    """
    df = pd.read_csv(csv_path)
    X, y = [], []
    erreurs = 0

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Chargement sessions"):
        try:
            # CORRECTION CRITIQUE : Utilisation de la vraie fréquence du CSV
            sr_reelle = int(row['frequence_echantillonnage'])

            # 1. SON
            chemin_son = os.path.join(SONS_DIR, row['fichier_son'])
            data_son_raw = charger_signal(chemin_son, usecols=1)
            if data_son_raw is None:
                erreurs += 1
                continue
            # Pré-traitement du signal son
            data_son = preprocess_signal(data_son_raw)

            # 2. VIBRATION
            chemin_vib = os.path.join(VIBRATIONS_DIR, row['fichier_vibration'])
            data_vibs_raw = charger_signal(chemin_vib, usecols=(1, 2, 3))
            if data_vibs_raw is None or data_vibs_raw.ndim < 2:
                erreurs += 1
                continue
            
            # Calcul de la magnitude vectorielle
            magnitude_vib_raw = np.sqrt(
                data_vibs_raw[:, 0]**2 + data_vibs_raw[:, 1]**2 + data_vibs_raw[:, 2]**2
            )
            # Pré-traitement du signal vibration
            magnitude_vib = preprocess_signal(magnitude_vib_raw)

            # 3. Spectrogrammes mel
            S_son = signal_vers_spectrogramme(data_son, sr_reelle)
            S_vib = signal_vers_spectrogramme(magnitude_vib, sr_reelle)

            # 4. Fusion verticale : son au-dessus, vibration en-dessous
            fusion = np.vstack((S_son, S_vib))
            img = np.expand_dims(fusion, -1)  # canal unique pour le CNN

            # 5. Normalisation du label (0-100 → 0-1)
            label_norm = (float(row['niveau_usure']) - USURE_MIN) / (USURE_MAX - USURE_MIN)
            label_norm = np.clip(label_norm, 0.0, 1.0)

            # DATA AUGMENTATION (FS13/FS12)
            # On ajoute l'image originale
            X.append(img)
            y.append(label_norm)
            
            # Et on crée une version bruitée pour doubler artificiellement les données d'entraînement
            # Cela aide le modèle à être plus robuste aux variations de mesure
            noise = np.random.normal(0, 0.05, img.shape) 
            img_noisy = img + noise
            X.append(img_noisy)
            y.append(label_norm)

        except Exception as e:
            print(f"  [ERREUR] Ligne {index} ({row.get('fichier_son', '?')}) : {e}")
            erreurs += 1
            continue

    if erreurs > 0:
        print(f"{Fore.YELLOW}⚠ {erreurs} session(s) ignorée(s) sur {len(df)}.{Style.RESET_ALL}")

    return np.array(X), np.array(y)


def construire_modele():
    """
    CNN de régression — sortie linéaire dans [0, 1] (niveau d'usure normalisé).
    Architecture améliorée avec Dropout et BatchNormalization pour éviter le sur-apprentissage.
    """
    model = models.Sequential([
        layers.Input(shape=(128, 128, 1)),
        
        # Bloc 1
        layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25), # Régularisation

        # Bloc 2
        layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Classification / Régression
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dropout(0.5), # Fort dropout sur la couche dense
        layers.Dense(1, activation='linear') # Sortie continue (0-1)
    ])
    
    model.compile(optimizer='adam', 
                  loss='mse', 
                  metrics=['mae']) # MAE plus parlant pour l'erreur en %
    return model


def tracer_historique(history, chemin_sortie):
    """Trace les courbes loss et MAE train/val (livrable FS12)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(history.history['loss'], label='Train')
    axes[0].plot(history.history['val_loss'], label='Val')
    axes[0].set_title('Loss (MSE)')
    axes[0].set_xlabel('Epoch')
    axes[0].legend()
    axes[1].plot(history.history['mae'], label='Train')
    axes[1].plot(history.history['val_mae'], label='Val')
    axes[1].set_title('MAE (Erreur Moyenne)')
    axes[1].set_xlabel('Epoch')
    axes[1].legend()
    plt.tight_layout()
    plt.savefig(chemin_sortie)
    plt.close()


# --- EXÉCUTION ---
if __name__ == '__main__':
    print(f"{Fore.CYAN}Chargement des données depuis {CSV_PATH}...{Style.RESET_ALL}")
    X, y = charger_et_transformer(CSV_PATH)

    if len(X) == 0:
        print(f"{Fore.RED}ERREUR : aucune donnée chargée. "
              f"Vérifier {CSV_PATH}, {SONS_DIR}/, {VIBRATIONS_DIR}/.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}✓ {len(X)} échantillons générés (avec augmentation) — X.shape = {X.shape}{Style.RESET_ALL}")

        # Split 80 / 20
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"  Train : {len(X_train)}  |  Test : {len(X_test)}")

        model = construire_modele()
        model.summary()

        # Configuration de l'Early Stopping pour éviter le sur-apprentissage
        early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)

        print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")
        history = model.fit(
            X_train, y_train,
            epochs=50, # Augmenté car l'early stop coupera si nécessaire
            batch_size=16, # Réduit pour plus de stabilité avec peu de données
            validation_data=(X_test, y_test),
            callbacks=[early_stop]
        )

        # Évaluation finale (FS12)
        print(f"\n{Fore.CYAN}Évaluation finale :{Style.RESET_ALL}")
        loss, mae = model.evaluate(X_test, y_test, verbose=0)
        mae_pct = mae * (USURE_MAX - USURE_MIN)  # reconversion en points d'usure (%)
        print(f"  MSE test : {loss:.4f}")
        print(f"  MAE test : {mae:.4f}  (soit ± {mae_pct:.2f} points d'usure en %)")

        # Sauvegarde modèle + courbes
        model.save(MODEL_OUT)
        tracer_historique(history, os.path.join(SAVE_IMAGES_DIR, 'historique_entrainement.png'))
        print(f"\n{Fore.GREEN}✓ Modèle : {MODEL_OUT}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✓ Courbes : {SAVE_IMAGES_DIR}/historique_entrainement.png{Style.RESET_ALL}")