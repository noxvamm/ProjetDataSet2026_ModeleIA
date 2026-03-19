# Permet d'interagir avec le système d'exploitation (créer des dossiers, vérifier si un fichier existe)
import os

# Bibliothèque de calcul mathématique pour manipuler les données sous forme de tableaux (matrices)
import numpy as np

# Outil spécialisé dans la lecture et l'analyse de fichiers de données comme ton fichier CSV
import pandas as pd

# Bibliothèque d'analyse audio pour transformer tes signaux bruts en spectrogrammes
import librosa

# Le moteur principal d'Intelligence Artificielle de Google pour créer et entraîner des modèles
import tensorflow as tf

# Importe les briques de construction de l'IA (couches de neurones et structure du modèle)
from tensorflow.keras import layers, models

# Outil qui sépare automatiquement tes données en deux groupes : un pour apprendre et un pour tester
from sklearn.model_selection import train_test_split

# Ajoute une barre de progression visuelle dans la console pendant les longs calculs
from tqdm import tqdm

# Bibliothèque qui permet d'afficher du texte en couleur dans le terminal
import colorama

# Importe les fonctions spécifiques pour choisir la couleur (Fore) et réinitialiser le style (Style)
from colorama import Fore, Style

# Initialisation des couleurs
colorama.init()

# --- CONFIGURATION ---
CSV_PATH = "data/metadata_10000.csv" # chemin vers le fichier dataset
RECORDS_DIR = "records" # chemin vers les fichiers de son et de vibration       
IMG_SIZE = (128, 128) # taille du spectrogramme
SR = 10000 # frequence d'échantillonnage


# fonction pour charger et transformer les données de son et de vibration en spectrogrammes
def charger_et_transformer(csv_path):
    # gestion de l'erreur dans le cas ou le fichier CSV est introuvable
    if not os.path.exists(csv_path):
        print(f"{Fore.RED}ERREUR : Le fichier {csv_path} est introuvable !{Style.RESET_ALL}")
        return None, None

    # lecture du csv
    df = pd.read_csv(csv_path)
    
    # vérification du contenu du dataset
    nb_neufs = len(df[df['niveau_usure'] == 0])
    nb_uses = len(df[df['niveau_usure'] == 1])
    
    print(f"\n{Fore.CYAN}=== ANALYSE DU DATASET ==={Style.RESET_ALL}")
    print(f"Fichiers NEUFS (0) : {nb_neufs}")
    print(f"Fichiers USÉS  (1) : {nb_uses}")
    
    X, y = [], [] # X contient les images, y contient les labels
    print(f"\n{Fore.YELLOW}Transformation des données en spectrogrammes...{Style.RESET_ALL}")

    # boucle pour parcourir chaque ligne du dataset et transformer les fichiers de son et de vibration en spectrogrammes avec affichage de la progression 

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Traitement", unit="fich"):
        nom_fichier = row['fichier_son']
        chemin_complet = os.path.join(RECORDS_DIR, nom_fichier)
        label = row['niveau_usure']

        try:
            if not os.path.exists(chemin_complet):
                continue

            # chargement du signal
            data = np.loadtxt(chemin_complet, delimiter=',')
            
            # transformation (Spectrogramme)
            S = librosa.feature.melspectrogram(y=data, sr=SR, n_mels=128)
            S_dB = librosa.power_to_db(S, ref=np.max)
            
            # redimensionnement (128x128 pour le CNN)
            img = tf.image.resize(np.expand_dims(S_dB, -1), IMG_SIZE).numpy()
            
            X.append(img)
            y.append(label)

        except Exception as e:
            continue

    return np.array(X), np.array(y)

# on éxecute la fonction de chargement et de transformation des données
X, y = charger_et_transformer(CSV_PATH)

if X is not None and len(X) > 0:
    print(f"\n{Fore.GREEN}Chargement terminé ! {len(X)} fichiers traités.{Style.RESET_ALL}")
    
    # on sépare les données en gardant 80% pour l'entraînement et 20% pour les tests
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # création du modèle CNN 

    # sequential signifie que le modele est composé de couches empilées les unes sur les autres, dans un ordre linéaire.
    model = models.Sequential([ 
        # 1ère convolution : Détecte 32 motifs de base (traits, bords) sur l'image 128x128
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=(128, 128, 1)),
        # Réduit la taille de l'image par 2 pour ne garder que les informations les plus fortes
        layers.MaxPooling2D((2, 2)),
        # 2ème convolution : Détecte 64 motifs plus complexes en combinant les premiers
        layers.Conv2D(64, (3, 3), activation='relu'),
        # Nouvelle réduction de taille pour simplifier le calcul et éviter le sur-apprentissage
        layers.MaxPooling2D((2, 2)),
        # Transforme la matrice 2D (image) en une liste de chiffres plate (vecteur)
        layers.Flatten(),
        # Couche de 64 neurones qui croisent toutes les caractéristiques pour "réfléchir"
        layers.Dense(64, activation='relu'),
        # Sortie finale : Donne la probabilité entre les 2 classes (0: Neuf, 1: Usé)
        layers.Dense(2, activation='softmax')
    ])

    # compilation du modèle avec l'optimiseur Adam, la fonction de perte adaptée pour la classification binaire et la métrique d'exactitude
    model.compile(optimizer='adam',
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])


    # --- ENTRAÎNEMENT ---
    print(f"\n{Fore.MAGENTA}Lancement de l'apprentissage...{Style.RESET_ALL}")
    model.fit(X_train, y_train, epochs=10, batch_size=32, validation_data=(X_test, y_test))

    # Sauvegarde finale
    model.save("modele_usure_expert.keras")
    print(f"\n{Fore.GREEN}SUCCÈS : Le modèle 'modele_usure_expert.keras' est prêt !{Style.RESET_ALL}")
else:
    print(f"{Fore.RED}ERREUR : Aucune donnée n'a été chargée. Vérifiez le dossier 'records'.{Style.RESET_ALL}")
