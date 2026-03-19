import tensorflow as tf
import numpy as np
import librosa

# 1. Charger le modèle que tu viens de créer
model = tf.keras.models.load_model("modele_usure_expert.keras")

def diagnostiquer(fichier_csv):
    # 2. Transformer le CSV en spectrogramme (exactement comme l'entraînement)
    data = np.loadtxt(fichier_csv, delimiter=',')
    S = librosa.feature.melspectrogram(y=data, sr=10000, n_mels=128)
    S_dB = librosa.power_to_db(S, ref=np.max)
    
    # 3. Adapter le format pour le CNN (Batch, Hauteur, Largeur, Canal)
    img = tf.image.resize(np.expand_dims(S_dB, -1), (128, 128)).numpy()
    img = np.expand_dims(img, 0) 

    # 4. Demander le verdict à l'IA
    prediction = model.predict(img)
    print(f"Scores bruts de l'IA : {prediction}")
    resultat = np.argmax(prediction)
    confiance = np.max(prediction) * 100

    print(f"\nAnalyse du fichier : {fichier_csv}")
    print(f"------------------------------------")
    if resultat == 1:
        print(f"RESULTAT : !!! OUTIL USÉ !!!")
    else:
        print(f"RESULTAT : OUTIL NEUF (OK)")
    print(f"Indice de confiance : {confiance:.2f}%")

# Lancer le test
diagnostiquer("records/tests_robustesse/test_05_casse_imminente.csv")