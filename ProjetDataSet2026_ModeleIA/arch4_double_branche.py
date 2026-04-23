# =============================================================================
#  ARCHITECTURE 4 — DOUBLE BRANCHE (Son + Vibration séparés)
#  Projet BTS CIEL Dataset26 — Détection d'usure outil CNC
# =============================================================================
#
#  C'est l'architecture la plus adaptée à notre projet physiquement.
#
#  Dans les architectures 1, 2 et 3, on fusionnait le son et la vibration
#  en une seule image AVANT de les donner au réseau. Le problème :
#  les premières couches du réseau mélangeaient les deux signaux dès le départ,
#  sans distinction.
#
#  Ici, on respecte la nature physique des données :
#    → le son     vient d'un micro I2S    → phénomène ACOUSTIQUE
#    → la vibration vient d'un capteur BLE → phénomène MÉCANIQUE
#
#  Chaque capteur a sa propre "branche" CNN qui apprend indépendamment
#  les caractéristiques propres à son signal.
#  Les deux branches sont ensuite fusionnées à la fin pour la prédiction finale.
#
#  Structure :
#    [Spectrogramme Son]         [Spectrogramme Vibration]
#           ↓                              ↓
#      CNN Branche A               CNN Branche B
#           ↓                              ↓
#     Vecteur features A         Vecteur features B
#           └─────────── Fusion ───────────┘
#                            ↓
#                    Dense → Niveau d'usure (0-100%)
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
#
#  DIFFÉRENCE IMPORTANTE par rapport aux autres architectures :
#  On ne fusionne plus les deux spectrogrammes en une seule image.
#  On retourne DEUX tableaux séparés : un pour le son, un pour la vibration.
# =============================================================================

def charger_et_transformer(csv_path):

    df = pd.read_csv(csv_path)

    # Trois listes : images son, images vibration, et les niveaux d'usure
    X_son, X_vib, y = [], [], []

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Chargement des données"):
        try:
            sr_reelle = row['frequence_echantillonnage']

            # --- CHARGEMENT ET SPECTROGRAMME DU SON ---
            path_son = os.path.join(RECORDS_DIR, 'sons', row['fichier_son'])
            data_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=1)
            S_son    = librosa.feature.melspectrogram(y=data_son.astype(float), sr=sr_reelle, n_mels=64)
            S_son_dB = librosa.power_to_db(S_son, ref=np.max)

            # On redimensionne le spectrogramme son seul en 128x128
            img_son = tf.image.resize(np.expand_dims(S_son_dB, -1), IMG_SIZE).numpy()

            # --- CHARGEMENT ET SPECTROGRAMME DE LA VIBRATION ---
            path_vib  = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
            data_vibs = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(1, 2, 3))
            magnitude = np.sqrt(data_vibs[:,0]**2 + data_vibs[:,1]**2 + data_vibs[:,2]**2)
            S_vib     = librosa.feature.melspectrogram(y=magnitude.astype(float), sr=sr_reelle, n_mels=64)
            S_vib_dB  = librosa.power_to_db(S_vib, ref=np.max)

            # On redimensionne le spectrogramme vibration seul en 128x128
            img_vib = tf.image.resize(np.expand_dims(S_vib_dB, -1), IMG_SIZE).numpy()

            # On stocke les deux images séparément
            X_son.append(img_son)
            X_vib.append(img_vib)
            y.append(row['niveau_usure'])

        except Exception as e:
            print(f"Erreur ligne {index}: {e}")
            continue

    return np.array(X_son), np.array(X_vib), np.array(y)


# On récupère les deux tableaux d'images séparés
X_son, X_vib, y = charger_et_transformer(CSV_PATH)

if X_son is not None and len(X_son) > 0:
    print(f"\n{Fore.GREEN}Chargement terminé ! {len(y)} fichiers traités.{Style.RESET_ALL}")

    # Séparation train/test pour les deux entrées en même temps
    # On passe les 3 tableaux à train_test_split pour garder la correspondance
    X_son_train, X_son_test, \
    X_vib_train, X_vib_test, \
    y_train, y_test = train_test_split(X_son, X_vib, y, test_size=0.2, random_state=42)


    # =============================================================================
    #  ÉTAPE 2 — CONSTRUCTION DU MODÈLE DOUBLE BRANCHE
    #
    #  On utilise l'API fonctionnelle de Keras (pas Sequential) car notre modèle
    #  a deux entrées distinctes, ce qu'une pile linéaire ne peut pas faire.
    # =============================================================================

    # =========================================
    #  BRANCHE SON
    # =========================================

    # Entrée pour le spectrogramme du son (128x128, 1 canal)
    entree_son = layers.Input(shape=(128, 128, 1), name="entree_son")

    # 1er bloc convolutif : détecte les motifs de base dans le spectrogramme sonore
    x1 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_son)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.MaxPooling2D((2, 2))(x1)

    # 2ème bloc : détecte des patterns sonores plus complexes (harmoniques, transitoires)
    x1 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)
    x1 = layers.MaxPooling2D((2, 2))(x1)

    # 3ème bloc : patterns sonores abstraits liés à l'usure
    x1 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x1)
    x1 = layers.BatchNormalization()(x1)

    # GlobalAveragePooling2D : résume toutes les cartes de features en un vecteur compact
    # → vecteur de 128 valeurs représentant les caractéristiques sonores de la session
    x1 = layers.GlobalAveragePooling2D(name="features_son")(x1)

    # =========================================
    #  BRANCHE VIBRATION
    # =========================================

    # Entrée pour le spectrogramme de vibration (128x128, 1 canal)
    entree_vib = layers.Input(shape=(128, 128, 1), name="entree_vibration")

    # Mêmes 3 blocs que la branche son, mais avec des poids indépendants :
    # chaque branche apprend ses propres filtres adaptés à son type de signal
    x2 = layers.Conv2D(32, (3, 3), activation='relu', padding='same')(entree_vib)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)

    x2 = layers.Conv2D(64, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)
    x2 = layers.MaxPooling2D((2, 2))(x2)

    x2 = layers.Conv2D(128, (3, 3), activation='relu', padding='same')(x2)
    x2 = layers.BatchNormalization()(x2)

    # → vecteur de 128 valeurs représentant les caractéristiques vibratoires
    x2 = layers.GlobalAveragePooling2D(name="features_vibration")(x2)

    # =========================================
    #  FUSION DES DEUX BRANCHES
    # =========================================

    # Concatenate : on colle les deux vecteurs bout à bout
    # → vecteur final de 256 valeurs (128 son + 128 vibration)
    # Le réseau dispose maintenant de l'information complète des deux capteurs
    fusion = layers.Concatenate(name="fusion_son_vibration")([x1, x2])

    # Couche de décision : 64 neurones qui analysent la combinaison des deux signaux
    z = layers.Dense(64, activation='relu')(fusion)

    # Dropout pour éviter l'overfitting sur les données fusionnées
    z = layers.Dropout(0.3)(z)

    # Sortie : un neurone qui prédit le niveau d'usure de 0 à 100%
    sortie = layers.Dense(1, activation='linear', name="niveau_usure")(z)

    # On assemble le modèle avec ses DEUX entrées et sa sortie unique
    model = models.Model(
        inputs=[entree_son, entree_vib],
        outputs=sortie,
        name="arch4_double_branche"
    )


    # =============================================================================
    #  ÉTAPE 3 — COMPILATION
    # =============================================================================

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    model.summary()


    # =============================================================================
    #  ÉTAPE 4 — ENTRAÎNEMENT
    #
    #  DIFFÉRENCE IMPORTANTE : on passe une LISTE de deux tableaux en entrée
    #  [X_son_train, X_vib_train] pour alimenter les deux branches simultanément
    # =============================================================================

    print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")

    model.fit(
        [X_son_train, X_vib_train],   # ← les deux entrées du modèle
        y_train,
        epochs=15,
        batch_size=16,                 # batch plus petit car les données sont plus lourdes (2 images)
        validation_data=([X_son_test, X_vib_test], y_test)
    )

    model.save("modele_arch4_double_branche.keras")
    print(f"\n{Fore.GREEN}SUCCÈS : Le modèle 'modele_arch4_double_branche.keras' est prêt !{Style.RESET_ALL}")

else:
    print(f"{Fore.RED}ERREUR : Aucune donnée chargée. Vérifiez le dossier 'data/records'.{Style.RESET_ALL}")
