# =============================================================================
#  ARCHITECTURE 3 — TRANSFER LEARNING avec MobileNetV2
#  Projet BTS CIEL Dataset26 — Détection d'usure outil CNC
# =============================================================================
#
#  Le Transfer Learning (apprentissage par transfert) consiste à réutiliser
#  un réseau déjà entraîné sur des millions d'images pour en tirer profit
#  sur notre propre problème, même avec peu de données.
#
#  MobileNetV2 est un réseau entraîné sur ImageNet (1.2 million d'images,
#  1000 catégories). Il sait déjà reconnaître des textures, des formes, des bords.
#  Ces capacités sont directement utiles pour analyser nos spectrogrammes.
#
#  Fonctionnement :
#    1. On charge MobileNetV2 avec ses poids pré-entraînés
#    2. On gèle ses couches (on ne les réentraîne pas) → on garde son savoir
#    3. On ajoute nos propres couches de décision au-dessus
#    4. On entraîne uniquement nos couches sur nos données d'usure
#
#  Avantage clé : très efficace quand on a peu de données labellisées,
#  ce qui est notre cas en BTS (peu de sessions d'enregistrement).
#
#  Contrainte technique : MobileNetV2 attend des images à 3 canaux (RGB).
#  Nos spectrogrammes sont en 1 canal (niveaux de gris).
#  Solution : on duplique le canal 3 fois pour obtenir un "faux RGB".
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
#  (identique aux architectures 1 et 2)
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
            path_vib  = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
            data_vibs = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(1, 2, 3))
            magnitude = np.sqrt(data_vibs[:,0]**2 + data_vibs[:,1]**2 + data_vibs[:,2]**2)
            S_vib     = librosa.feature.melspectrogram(y=magnitude.astype(float), sr=sr_reelle, n_mels=64)
            S_vib_dB  = librosa.power_to_db(S_vib, ref=np.max)

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
    #  ÉTAPE 2 — CONSTRUCTION DU MODÈLE AVEC MOBILENETV2
    #
    #  On utilise l'API fonctionnelle de Keras (et non plus Sequential)
    #  car le modèle n'est plus une simple pile linéaire :
    #  on branche MobileNetV2 au milieu de notre architecture.
    # =============================================================================

    # --- ENTRÉE ---
    # Notre image arrive en 1 canal (niveaux de gris)
    entree = layers.Input(shape=(128, 128, 1), name="entree_spectrogramme")

    # --- CONVERSION 1 CANAL → 3 CANAUX ---
    # MobileNetV2 exige 3 canaux (Rouge, Vert, Bleu).
    # On duplique notre unique canal 3 fois pour créer un "faux RGB".
    # Le réseau verra la même information sur les 3 canaux,
    # mais il sera capable de traiter l'image avec ses filtres pré-entraînés.
    x = layers.Lambda(
        lambda image: tf.repeat(image, 3, axis=-1),
        name="conversion_gris_vers_rgb"
    )(entree)

    # --- BASE MOBILENETV2 PRÉ-ENTRAÎNÉE ---
    # On charge MobileNetV2 avec ses poids issus de l'entraînement sur ImageNet.
    # include_top=False : on ne prend pas les dernières couches de classification
    #                     d'ImageNet (qui classent 1000 catégories d'objets)
    #                     on prend uniquement la partie qui extrait les features
    base_mobilenet = tf.keras.applications.MobileNetV2(
        input_shape=(128, 128, 3),
        include_top=False,
        weights='imagenet'
    )

    # On gèle toutes les couches de MobileNetV2 :
    # leurs poids ne seront PAS modifiés pendant notre entraînement.
    # On conserve exactement ce que le réseau a appris sur ImageNet.
    base_mobilenet.trainable = False

    # On branche notre image sur MobileNetV2
    # training=False : indique que BatchNorm interne reste en mode inférence
    x = base_mobilenet(x, training=False)

    # --- RÉSUMÉ DES FEATURES ---
    # GlobalAveragePooling2D : au lieu de Flatten qui crée un très grand vecteur,
    # on prend la moyenne de chaque carte de features.
    # Résultat : un vecteur compact de 1280 valeurs (taille de sortie de MobileNetV2)
    # C'est plus léger et moins sujet à l'overfitting que Flatten.
    x = layers.GlobalAveragePooling2D(name="resume_features")(x)

    # --- COUCHE DE DÉCISION ---
    # On ajoute notre propre couche Dense qui va apprendre à relier
    # les 1280 features de MobileNetV2 à notre niveau d'usure
    x = layers.Dense(64, activation='relu', name="couche_decision")(x)

    # --- COUCHE DE SORTIE ---
    sortie = layers.Dense(1, activation='linear', name="niveau_usure")(x)

    # On assemble le modèle complet : de l'entrée jusqu'à la sortie
    model = models.Model(inputs=entree, outputs=sortie, name="arch3_MobileNetV2")


    # =============================================================================
    #  ÉTAPE 3 — COMPILATION
    # =============================================================================

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    model.summary()


    # =============================================================================
    #  ÉTAPE 4 — ENTRAÎNEMENT
    #
    #  Avec le Transfer Learning, on a besoin de moins d'époques
    #  car MobileNetV2 fournit déjà des features de qualité dès le départ.
    #  Seules nos deux couches Dense (64 + 1 neurones) apprennent vraiment.
    # =============================================================================

    print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")

    model.fit(
        X_train, y_train,
        epochs=10,
        batch_size=32,
        validation_data=(X_test, y_test)
    )

    model.save("modele_arch3_mobilenetv2.keras")
    print(f"\n{Fore.GREEN}SUCCÈS : Le modèle 'modele_arch3_mobilenetv2.keras' est prêt !{Style.RESET_ALL}")

else:
    print(f"{Fore.RED}ERREUR : Aucune donnée chargée. Vérifiez le dossier 'data/records'.{Style.RESET_ALL}")
