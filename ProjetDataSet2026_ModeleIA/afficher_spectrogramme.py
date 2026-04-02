import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

def generate_spectrogram(csv_file, column_name, title, sample_rate):
    # Chargement des données
    df = pd.read_csv(csv_file)
    data = df[column_name].values
    
    # Nettoyage (enlever la moyenne pour éviter une ligne énorme à 0Hz)
    data = data - np.mean(data)
    
    # Calcul du spectrogramme
    # nperseg définit la précision (plus c'est haut, plus c'est précis en fréquence)
    frequencies, times, spectrogram = signal.spectrogram(data, fs=sample_rate, nperseg=128)

    # Affichage
    plt.figure(figsize=(10, 5))
    plt.pcolormesh(times, frequencies, 10 * np.log10(spectrogram + 1e-10), shading='gouraud', cmap='magma')
    plt.title(title)
    plt.ylabel('Fréquence [Hz]')
    plt.xlabel('Temps [sec]')
    plt.colorbar(label='Intensité [dB]')
    plt.tight_layout()
    plt.show()

# --- EXÉCUTION ---

# Pour le SON : tes données sont espacées de 20ms -> 50 Hz
generate_spectrogram('son_1.csv', 'Amplitude', 'Spectrogramme Acoustique (Son)', sample_rate=50)

# Pour la VIBRATION : on prend l'axe VX (Vitesse X) par exemple
generate_spectrogram('vib_1.csv', 'VX', 'Spectrogramme Vibratoire (Axe VX)', sample_rate=50)