# =============================================================================
#  GÉNÉRATION DE MEL-SPECTROGRAMMES COMPARATIFS — pour la démo de soutenance
#
#  Réutilise EXACTEMENT la chaîne de calcul du modèle (arch4_double_branche.py) :
#  mêmes n_mels, n_fft, hop_length, power_to_db, normalisation min-max, et la
#  décision d'ingénierie |VZ| seul côté vibration (Option A).
#
#  Produit 3 planches PNG dans le dossier spectrogrammes_demo/ :
#    1. comparatif_son_tension.png   — son, tension croissante (effet du label)
#    2. comparatif_vib_tension.png   — vibration, tension croissante
#    3. comparatif_charge.png        — A_vide vs B_frein à tension fixe
#
#  Lancer :  python generer_spectrogrammes_demo.py
# =============================================================================

import os
import numpy as np
import pandas as pd
import librosa
import librosa.display
import matplotlib.pyplot as plt

# --- Paramètres signal/mel : IDENTIQUES au modèle arch4 ---
SON_N_MELS = 64
VIB_N_FFT  = 128
VIB_HOP    = 32
VIB_N_MELS = 32

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_BASE   = os.path.join(SCRIPT_DIR, 'dist', 'data')
CSV_PATH    = os.path.join(DATA_BASE, 'metadata_captures_moteur.csv')
RECORDS_DIR = os.path.join(DATA_BASE, 'records')
OUT_DIR     = os.path.join(SCRIPT_DIR, 'spectrogrammes_demo')
os.makedirs(OUT_DIR, exist_ok=True)


def normaliser(spec):
    """Normalise un spectrogramme dB entre 0 et 1 (identique au modèle)."""
    s_min, s_max = spec.min(), spec.max()
    return (spec - s_min) / (s_max - s_min + 1e-9)


def tronquer_duree(arr, duree_s):
    """Garde les `duree_s` premières secondes (garde-fou fichiers concaténés)."""
    if arr.ndim == 1 or len(arr) == 0:
        return arr
    t = arr[:, 0]
    mask = (t - t[0]) <= (duree_s * 1000.0)
    if mask.sum() < 10:
        return arr
    return arr[mask]


def _charger_csv_numerique(path, n_cols):
    """Charge les n_cols premières colonnes d'un CSV en float, en ignorant les
    lignes mal formées (cellules vides issues du bug de concaténation)."""
    df = pd.read_csv(path, header=0, usecols=range(n_cols))
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    return df.to_numpy(dtype=float)


def charger_capture(row):
    """Charge le son (amplitude) et la vibration (|VZ|) d'une ligne du CSV."""
    duree = float(row['duree'])
    path_son = os.path.join(RECORDS_DIR, 'sons', row['fichier_son'])
    arr_son = _charger_csv_numerique(path_son, 2)
    arr_son = tronquer_duree(arr_son, duree)
    data_son = arr_son[:, 1]

    path_vib = os.path.join(RECORDS_DIR, 'vibrations', row['fichier_vibration'])
    arr_vib = _charger_csv_numerique(path_vib, 4)
    arr_vib = tronquer_duree(arr_vib, duree)
    # Option A : axe Z seul (cf. arch4 — VX/VY figés sous le seuil MEMS)
    vib_vz = np.abs(arr_vib[:, 3])
    return data_son, float(row['frequence_son']), vib_vz, float(row['frequence_vibration'])


def mel_son_db(signal, sr):
    """Mel-spectrogramme son en dB normalisé (sans resize, axes physiques)."""
    S = librosa.feature.melspectrogram(y=signal, sr=sr, n_mels=SON_N_MELS)
    return normaliser(librosa.power_to_db(S, ref=np.max))


def mel_vib_db(signal, sr):
    """Mel-spectrogramme vibration en dB normalisé (params basse fréquence)."""
    n_fft = min(VIB_N_FFT, max(8, len(signal)))
    hop = max(1, min(VIB_HOP, max(1, len(signal) // 4)))
    S = librosa.feature.melspectrogram(y=signal, sr=sr, n_mels=VIB_N_MELS,
                                       n_fft=n_fft, hop_length=hop)
    return normaliser(librosa.power_to_db(S, ref=np.max))


def fenetre_1s_centre(signal, sr):
    """Extrait 1 s au centre du signal (comme le window slicing du modèle)."""
    taille = int(sr)
    if len(signal) <= taille:
        return signal
    debut = (len(signal) - taille) // 2
    return signal[debut:debut + taille]


def trouver(df, condition, niveau):
    """Première capture correspondant à (condition, niveau_tension)."""
    sel = df[(df['condition_charge'] == condition) & (df['niveau_tension'] == niveau)]
    return sel.iloc[0] if len(sel) else None


# =============================================================================
#  PLANCHE 1 & 2 — Évolution de la signature avec la tension (condition A_vide)
# =============================================================================

def planche_tension(df, modalite):
    """modalite = 'son' ou 'vib'. Grille de mels à tension croissante."""
    niveaux = [0, 20, 40, 60, 80, 100]
    condition = 'A_vide'
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    axes = axes.flatten()
    titre_mod = "acoustique (son)" if modalite == 'son' else "vibratoire (|VZ|)"
    fig.suptitle(f"Signature {titre_mod} selon le niveau de tension — condition {condition}",
                 fontsize=15, fontweight='bold')

    for ax, niveau in zip(axes, niveaux):
        row = trouver(df, condition, niveau)
        if row is None:
            ax.set_title(f"{niveau} % — absent"); ax.axis('off'); continue
        son, sr_son, vib, sr_vib = charger_capture(row)
        if modalite == 'son':
            mel = mel_son_db(fenetre_1s_centre(son, sr_son), sr_son)
            sr, hop = sr_son, 512
        else:
            mel = mel_vib_db(vib, sr_vib)
            sr, hop = sr_vib, VIB_HOP
        img = librosa.display.specshow(mel, sr=sr, hop_length=hop,
                                       x_axis='time', y_axis='mel', ax=ax, cmap='magma')
        ax.set_title(f"{niveau} % de tension", fontsize=12, fontweight='bold')
        ax.set_xlabel('Temps (s)'); ax.set_ylabel('Fréquence (Hz)')

    fig.colorbar(img, ax=axes, fraction=0.025, pad=0.02, label='Intensité normalisée')
    out = os.path.join(OUT_DIR, f"comparatif_{modalite}_tension.png")
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  [OK] {out}")


# =============================================================================
#  PLANCHE 3 — Effet de la charge : A_vide vs B_frein à tension fixe
# =============================================================================

def planche_charge(df, niveau=50):
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    fig.suptitle(f"Effet de la charge sur la signature — tension {niveau} %",
                 fontsize=15, fontweight='bold')

    for col, condition in enumerate(['A_vide', 'B_frein']):
        row = trouver(df, condition, niveau)
        if row is None:
            for r in range(2):
                axes[r, col].set_title(f"{condition} — absent"); axes[r, col].axis('off')
            continue
        son, sr_son, vib, sr_vib = charger_capture(row)
        mel_s = mel_son_db(fenetre_1s_centre(son, sr_son), sr_son)
        mel_v = mel_vib_db(vib, sr_vib)
        librosa.display.specshow(mel_s, sr=sr_son, hop_length=512,
                                 x_axis='time', y_axis='mel', ax=axes[0, col], cmap='magma')
        axes[0, col].set_title(f"{condition} — son", fontsize=12, fontweight='bold')
        axes[0, col].set_xlabel('Temps (s)'); axes[0, col].set_ylabel('Fréquence (Hz)')
        librosa.display.specshow(mel_v, sr=sr_vib, hop_length=VIB_HOP,
                                 x_axis='time', y_axis='mel', ax=axes[1, col], cmap='viridis')
        axes[1, col].set_title(f"{condition} — vibration |VZ|", fontsize=12, fontweight='bold')
        axes[1, col].set_xlabel('Temps (s)'); axes[1, col].set_ylabel('Fréquence (Hz)')

    out = os.path.join(OUT_DIR, "comparatif_charge.png")
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  [OK] {out}")


if __name__ == '__main__':
    df = pd.read_csv(CSV_PATH)
    # Déduplique sur (condition, niveau) en gardant la 1re occurrence
    print("Génération des planches comparatives...")
    planche_tension(df, 'son')
    planche_tension(df, 'vib')
    planche_charge(df, niveau=50)
    print(f"\nTerminé. Images dans : {OUT_DIR}")
