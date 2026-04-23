# =============================================================================
#  ARCHITECTURE 1 — CNN SIMPLE (Baseline)
#  Projet BTS CIEL Dataset26 — Détection d'usure outil CNC
# =============================================================================
#
#  C'est l'architecture de départ, la plus basique.
#  Elle sert de référence : toutes les autres architectures seront comparées
#  à celle-ci pour savoir si elles font mieux.
#
#  Principe : on prend le spectrogramme fusionné (son + vibration empilés)
#  et on le fait passer dans deux blocs de convolution pour en extraire
#  les caractéristiques, puis on prédit le niveau d'usure (0 à 100%).
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
CSV_PATH    = "data/metadata_captures.csv"  # Fichier index du dataset (créé par Hugo)
RECORDS_DIR = "data/records"                # Dossier contenant les fichiers son et vib
IMG_SIZE    = (128, 128)                    # Taille finale du spectrogramme (hauteur x largeur)
SR          = 50                            # Fréquence d'échantillonnage de l'ESP32 (50 Hz)


# =============================================================================
#  ÉTAPE 1 — CHARGEMENT ET TRANSFORMATION DES DONNÉES
#  On lit chaque paire de fichiers (son + vibration) depuis le CSV index,
#  on les transforme en spectrogrammes, on les empile en une seule image 128x128
# =============================================================================

def charger_et_transformer(csv_path):

    # On lit le fichier CSV qui liste toutes les sessions d'enregistrement
    df = pd.read_csv(csv_path)

    # On prépare deux listes vides :
    # X contiendra les images (spectrogrammes), y contiendra les niveaux d'usure
    X, y = [], []

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Chargement des données"):
        try:
            # On récupère la fréquence d'échantillonnage réelle de cette session
            sr_reelle = row['frequence_echantillonnage']

            # --- CHARGEMENT DU SON ---
            # On construit le chemin vers le fichier son de cette session
            path_son = os.path.join(RECORDS_DIR, 'sons', row['fichier_son'])

            # On lit uniquement la colonne "Amplitude" (colonne numéro 1)
            data_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=1)

            # On transforme le signal audio brut en spectrogramme Mel
            # Le spectrogramme représente les fréquences présentes dans le son au fil du temps
            S_son = librosa.feature.melspectrogram(y=data_son.astype(float), sr=sr_reelle, n_mels=64)

            # On convertit en décibels pour que l'image soit plus lisible par le réseau
            S_son_dB = librosa.power_to_db(S_son, ref=np.max)

            # --- CHARGEMENT DE LA VIBRATION ---
            path_vib = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])

            # On lit les 3 axes de vitesse : VX (col 1), VY (col 2), VZ (col 3)
            data_vibs = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(1, 2, 3))

            # On calcule la magnitude : une seule valeur qui représente
            # la force totale de la vibration dans les 3 directions
            magnitude_vib = np.sqrt(data_vibs[:,0]**2 + data_vibs[:,1]**2 + data_vibs[:,2]**2)

            # Même traitement que pour le son : spectrogramme Mel puis décibels
            S_vib = librosa.feature.melspectrogram(y=magnitude_vib.astype(float), sr=sr_reelle, n_mels=64)
            S_vib_dB = librosa.power_to_db(S_vib, ref=np.max)

            # --- FUSION ---
            # On empile verticalement les deux spectrogrammes en une seule image :
            # - 64 lignes du haut = le son
            # - 64 lignes du bas  = la vibration
            # → image finale de 128 lignes
            fusion = np.vstack((S_son_dB, S_vib_dB))

            # On redimensionne l'image à exactement 128x128 pixels
            # et on ajoute une dimension pour le canal (comme une image en niveaux de gris)
            img = tf.image.resize(np.expand_dims(fusion, -1), IMG_SIZE).numpy()

            # On ajoute cette image et son label à nos listes
            X.append(img)
            y.append(row['niveau_usure'])

        except Exception as e:
            print(f"Erreur ligne {index}: {e}")
            continue

    return np.array(X), np.array(y)


# On lance le chargement
X, y = charger_et_transformer(CSV_PATH)

if X is not None and len(X) > 0:
    print(f"\n{Fore.GREEN}Chargement terminé ! {len(X)} fichiers traités.{Style.RESET_ALL}")

    # On sépare les données : 80% pour apprendre, 20% pour tester
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


    # =============================================================================
    #  ÉTAPE 2 — CONSTRUCTION DU MODÈLE CNN SIMPLE
    #
    #  Le modèle est "Sequential" : les couches sont empilées les unes après les autres,
    #  comme des filtres successifs qui extraient de plus en plus d'informations.
    # =============================================================================

    model = models.Sequential([

        # --- 1er BLOC DE CONVOLUTION ---
        # Conv2D : on applique 32 filtres (detecteurs de motifs) de taille 3x3 sur l'image
        # activation='relu' : les valeurs négatives sont mises à zéro (simplifie le calcul)
        # input_shape : on dit au modèle la forme de nos images (128x128, 1 canal)
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(128, 128, 1)),

        # MaxPooling2D : on réduit l'image par 2 (de 128x128 → 64x64)
        # On garde uniquement la valeur maximale dans chaque zone de 2x2 pixels
        # Cela rend le modèle moins sensible aux petites variations de position
        layers.MaxPooling2D((2, 2)),

        # --- 2ème BLOC DE CONVOLUTION ---
        # 64 filtres cette fois : on cherche des motifs plus complexes
        # en combinant les motifs simples trouvés par les 32 premiers filtres
        layers.Conv2D(64, (3, 3), activation='relu'),

        # Nouvelle réduction de taille (64x64 → 32x32)
        layers.MaxPooling2D((2, 2)),

        # --- MISE À PLAT ---
        # Flatten : on transforme la matrice 2D (image) en une liste de chiffres (vecteur)
        # C'est nécessaire pour pouvoir la connecter aux couches Dense ci-dessous
        layers.Flatten(),

        # --- COUCHE DE DÉCISION ---
        # Dense(64) : 64 neurones qui reçoivent toutes les caractéristiques extraites
        # et les croisent pour identifier des patterns liés à l'usure
        layers.Dense(64, activation='relu'),

        # --- COUCHE DE SORTIE ---
        # Dense(1) : un seul neurone de sortie qui donne le niveau d'usure prédit
        # activation='linear' : pas de limite, la valeur peut aller de 0 à 100 (et au-delà)
        layers.Dense(1, activation='linear')
    ])


    # =============================================================================
    #  ÉTAPE 3 — COMPILATION DU MODÈLE
    #
    #  On choisit :
    #  - optimizer='adam'  : algorithme qui ajuste les poids du réseau automatiquement
    #  - loss='mse'        : Mean Squared Error, mesure l'écart au carré entre
    #                        la prédiction et la vraie valeur d'usure
    #  - metrics=['mae']   : Mean Absolute Error, plus facile à interpréter :
    #                        si mae=5, le modèle se trompe en moyenne de 5 points d'usure
    # =============================================================================

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])

    # Affichage du résumé du modèle (nombre de paramètres, forme des couches)
    model.summary()


    # =============================================================================
    #  ÉTAPE 4 — ENTRAÎNEMENT
    #
    #  epochs=10    : le modèle voit l'ensemble des données 10 fois de suite
    #  batch_size=32: le modèle apprend sur des groupes de 32 images à la fois
    #  validation_data : à chaque époque, on mesure les performances sur les données de test
    # =============================================================================

    print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")

    model.fit(
        X_train, y_train,
        epochs=10,
        batch_size=32,
        validation_data=(X_test, y_test)
    )

    # Sauvegarde du modèle entraîné sur le disque
    model.save("modele_arch1_cnn_simple.keras")
    print(f"\n{Fore.GREEN}SUCCÈS : Le modèle 'modele_arch1_cnn_simple.keras' est prêt !{Style.RESET_ALL}")

else:
    print(f"{Fore.RED}ERREUR : Aucune donnée chargée. Vérifiez le dossier 'data/records'.{Style.RESET_ALL}")
