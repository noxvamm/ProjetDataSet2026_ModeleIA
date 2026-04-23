# =============================================================================
#  ARCHITECTURE 2 — CNN + BATCHNORM + DROPOUT
#  Projet BTS CIEL Dataset26 — Détection d'usure outil CNC
# =============================================================================
#
#  C'est une version améliorée de l'architecture 1.
#  On ajoute deux mécanismes pour rendre l'apprentissage plus stable
#  et éviter que le modèle "apprenne par coeur" les données d'entraînement
#  sans être capable de généraliser sur de nouvelles données.
#
#  Améliorations par rapport à l'architecture 1 :
#    → BatchNormalization : normalise les valeurs entre chaque couche pour
#      stabiliser et accélérer l'apprentissage
#    → Dropout : désactive aléatoirement des neurones pendant l'entraînement
#      pour forcer le réseau à ne pas dépendre d'un seul chemin
#    → 3 blocs de convolution au lieu de 2 : détecte des motifs plus complexes
# =============================================================================

import os
import numpy as np
import pandas as pd
import librosa
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.model_selection import train_test_split
from tqdm import tqdm
import colorama
from colorama import Fore, Style

colorama.init()

# --- CONFIGURATION ---
CSV_PATH    = "data/metadata_captures.csv"
RECORDS_DIR = "data/records"
IMG_SIZE    = (128, 128)
SR          = 50


# =============================================================================
#  ÉTAPE 1 — CHARGEMENT ET TRANSFORMATION DES DONNÉES
#  (identique à l'architecture 1 : même pipeline de données)
# =============================================================================

def charger_et_transformer(csv_path):

    df = pd.read_csv(csv_path)
    X, y = [], []

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Chargement des données"):
        try:
            sr_reelle = row['frequence_echantillonnage']

            # --- CHARGEMENT DU SON ---
            path_son = os.path.join(RECORDS_DIR, 'sons', row['fichier_son'])
            data_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=1)
            S_son    = librosa.feature.melspectrogram(y=data_son.astype(float), sr=sr_reelle, n_mels=64)
            S_son_dB = librosa.power_to_db(S_son, ref=np.max)

            # --- CHARGEMENT DE LA VIBRATION ---
            path_vib    = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
            data_vibs   = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(1, 2, 3))
            magnitude   = np.sqrt(data_vibs[:,0]**2 + data_vibs[:,1]**2 + data_vibs[:,2]**2)
            S_vib       = librosa.feature.melspectrogram(y=magnitude.astype(float), sr=sr_reelle, n_mels=64)
            S_vib_dB    = librosa.power_to_db(S_vib, ref=np.max)

            # --- FUSION EN UNE SEULE IMAGE ---
            fusion = np.vstack((S_son_dB, S_vib_dB))
            img    = tf.image.resize(np.expand_dims(fusion, -1), IMG_SIZE).numpy()

            X.append(img)
            y.append(row['niveau_usure'])

        except Exception as e:
            print(f"Erreur ligne {index}: {e}")
            continue

    return np.array(X), np.array(y)


X, y = charger_et_transformer(CSV_PATH)

if X is not None and len(X) > 0:
    print(f"\n{Fore.GREEN}Chargement terminé ! {len(X)} fichiers traités.{Style.RESET_ALL}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


    # =============================================================================
    #  ÉTAPE 2 — CONSTRUCTION DU MODÈLE CNN + BATCHNORM + DROPOUT
    #
    #  3 blocs de convolution, chacun suivi d'une BatchNormalization.
    #  Un Dropout est ajouté avant la couche de sortie.
    # =============================================================================

    model = models.Sequential([

        # --- 1er BLOC ---
        # 32 filtres de taille 3x3 pour détecter les motifs de base
        # padding='same' : on garde la même taille d'image après la convolution
        layers.Conv2D(32, (3, 3), activation='relu', padding='same', input_shape=(128, 128, 1)),

        # BatchNormalization : normalise les sorties de la couche précédente
        # Cela évite que les valeurs deviennent trop grandes ou trop petites
        # et accélère la convergence du modèle lors de l'entraînement
        layers.BatchNormalization(),

        # Réduction de taille : 128x128 → 64x64
        layers.MaxPooling2D((2, 2)),

        # --- 2ème BLOC ---
        # 64 filtres : on cherche des combinaisons de motifs plus complexes
        layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        layers.BatchNormalization(),

        # Réduction de taille : 64x64 → 32x32
        layers.MaxPooling2D((2, 2)),

        # --- 3ème BLOC ---
        # 128 filtres : on cherche des motifs encore plus abstraits et spécifiques
        # à l'usure de l'outil (patterns de fréquences caractéristiques)
        layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
        layers.BatchNormalization(),

        # Réduction de taille : 32x32 → 16x16
        layers.MaxPooling2D((2, 2)),

        # --- MISE À PLAT ---
        layers.Flatten(),

        # --- COUCHE DE DÉCISION ---
        # 128 neurones (plus que l'architecture 1) pour exploiter
        # les 128 filtres du dernier bloc de convolution
        layers.Dense(128, activation='relu'),

        # Dropout : pendant l'entraînement, on désactive aléatoirement 40% des neurones
        # à chaque passage. Le réseau ne peut pas "mémoriser" les données,
        # il est forcé de trouver des règles générales → meilleure généralisation
        # (le dropout est automatiquement désactivé lors de la prédiction)
        layers.Dropout(0.4),

        # --- COUCHE DE SORTIE ---
        # Un seul neurone pour prédire le pourcentage d'usure (0 à 100)
        layers.Dense(1, activation='linear')
    ])


    # =============================================================================
    #  ÉTAPE 3 — COMPILATION
    # =============================================================================

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    model.summary()


    # =============================================================================
    #  ÉTAPE 4 — ENTRAÎNEMENT
    #
    #  On augmente légèrement le nombre d'époques par rapport à l'architecture 1
    #  car le Dropout et la BatchNorm ont besoin de plus d'itérations pour converger
    # =============================================================================

    print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")

    model.fit(
        X_train, y_train,
        epochs=15,
        batch_size=32,
        validation_data=(X_test, y_test)
    )

    model.save("modele_arch2_cnn_regularise.keras")
    print(f"\n{Fore.GREEN}SUCCÈS : Le modèle 'modele_arch2_cnn_regularise.keras' est prêt !{Style.RESET_ALL}")

else:
    print(f"{Fore.RED}ERREUR : Aucune donnée chargée. Vérifiez le dossier 'data/records'.{Style.RESET_ALL}")
