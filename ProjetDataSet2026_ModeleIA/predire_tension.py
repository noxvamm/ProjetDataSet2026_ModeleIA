# =============================================================================
#  PREDIRE_TENSION — Test du modèle arch4 sur des données réelles
#  Projet BTS CIEL Dataset26 — Estimation du niveau de tension moteur
#
#  Prend une capture (fichier son + fichier vibration) et prédit le niveau
#  de tension en %. Le PREPROCESSING est strictement identique à celui de
#  l'entraînement (arch4_double_branche.py) — sinon les prédictions sont fausses.
#
#  Usage :
#    python predire_tension.py son_X.csv vib_X.csv
#    python predire_tension.py son_X.csv vib_X.csv --condition A_vide
#    python predire_tension.py son_X.csv vib_X.csv --condition B_frein --reel 60
#
#    # Par ID dans le CSV d'entraînement (défaut)
#    python predire_tension.py --id 3
#
#    # Par ID dans le CSV de test
#    python predire_tension.py --id 1 --csv test
#
#    # Chemin complet vers n'importe quel CSV de métadonnées
#    python predire_tension.py --id 2 --csv dist/data/metadata_captures_test.csv
# =============================================================================

import os
import sys
import argparse
import numpy as np
import librosa
import tensorflow as tf

# --- CHEMINS (relatifs au script) ---
SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_BASE         = os.path.join(SCRIPT_DIR, 'data')
RECORDS_DIR       = os.path.join(DATA_BASE, 'records')       # captures TRAIN
RECORDS_DIR_TEST  = os.path.join(DATA_BASE, 'records_test')  # captures TEST

# Fichiers CSV de métadonnées disponibles
CSV_TRAIN = os.path.join(DATA_BASE, 'metadata_captures_moteur.csv')
CSV_TEST  = os.path.join(DATA_BASE, 'metadata_captures_test.csv')

# --- HYPERPARAMÈTRES (DOIVENT être identiques à arch4_double_branche.py) ---
IMG_SIZE         = (128, 128)
SON_N_MELS       = 64
VIB_N_FFT        = 128
VIB_HOP          = 32
VIB_N_MELS       = 32
WINDOW_DUREE_SON = 1.0
WINDOW_OVERLAP   = 0.5
SR_SON_DEFAUT    = 16000.0   # fréquence déclarée utilisée à l'entraînement
SR_VIB_DEFAUT    = 50.0
DUREE_DEFAUT     = 15.0

# Tension max mesurée par condition (cf. CLAUDE.md) — pour convertir % -> volts
VOLTAGE_MAX = {'A_vide': 30.3, 'B_frein': 28.7}

# Noms possibles du modèle entraîné, par ordre de préférence
MODELES = [
    'modele_arch4_double_branche.keras',
    'modele_arch4_best.keras',
    'modele_arch4_smoke_test.keras',
]


# =============================================================================
#  PREPROCESSING — copie conforme d'arch4_double_branche.py
# =============================================================================

def normaliser(spectrogramme):
    s_min = spectrogramme.min()
    s_max = spectrogramme.max()
    return (spectrogramme - s_min) / (s_max - s_min + 1e-9)


def tronquer_duree(arr, duree_s):
    """Garde les `duree_s` premières secondes (timestamps col 0 en ms)."""
    if arr.ndim == 1 or len(arr) == 0:
        return arr
    t = arr[:, 0]
    mask = (t - t[0]) <= (duree_s * 1000.0)
    if mask.sum() < 10:
        return arr
    return arr[mask]


def decouper_son_en_fenetres(signal, sr, duree_fenetre, overlap):
    taille_fen = int(duree_fenetre * sr)
    if len(signal) < taille_fen:
        return [signal]
    pas = max(1, int(taille_fen * (1 - overlap)))
    return [signal[d:d + taille_fen] for d in range(0, len(signal) - taille_fen + 1, pas)]


def signal_vers_mel_son(signal, sr):
    S = librosa.feature.melspectrogram(y=signal.astype(float), sr=sr, n_mels=SON_N_MELS)
    S_dB = librosa.power_to_db(S, ref=np.max)
    S_dB = normaliser(S_dB)
    return tf.image.resize(np.expand_dims(S_dB, -1), IMG_SIZE).numpy()


def signal_vers_mel_vib(signal, sr):
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
#  CHARGEMENT D'UNE CAPTURE + PRÉDICTION
# =============================================================================

def charger_capture(path_son, path_vib, duree=DUREE_DEFAUT):
    """Charge et tronque une capture. Retourne (signal_son, magnitude_vib)."""
    if not os.path.exists(path_son):
        raise FileNotFoundError(f"Fichier son introuvable : {path_son}")
    if not os.path.exists(path_vib):
        raise FileNotFoundError(f"Fichier vibration introuvable : {path_vib}")

    arr_son = np.loadtxt(path_son, delimiter=',', skiprows=1, usecols=(0, 1))
    arr_son = tronquer_duree(arr_son, duree)
    data_son = arr_son[:, 1].astype(float)

    arr_vib = np.loadtxt(path_vib, delimiter=',', skiprows=1, usecols=(0, 1, 2, 3))
    arr_vib = tronquer_duree(arr_vib, duree)
    data_vibs = arr_vib[:, 1:4]              # [VX, VY, VZ] (on retire le timestamp)
    magnitude = np.abs(data_vibs[:, 2])      # Option A : |VZ| seul — identique à arch4

    if len(data_son) < 10:
        raise ValueError(f"Signal son trop court ({len(data_son)} points) — capture vide ?")
    return data_son, magnitude.astype(float)


def predire(model, data_son, magnitude, sr_son=SR_SON_DEFAUT, sr_vib=SR_VIB_DEFAUT):
    """Reproduit l'inférence par capture : moyenne des prédictions de chaque fenêtre."""
    mel_vib = signal_vers_mel_vib(magnitude, sr_vib)
    fenetres = decouper_son_en_fenetres(data_son, sr_son, WINDOW_DUREE_SON, WINDOW_OVERLAP)

    X_son, X_vib = [], []
    for f in fenetres:
        X_son.append(signal_vers_mel_son(f, sr_son))
        X_vib.append(mel_vib)
    X_son = np.array(X_son)
    X_vib = np.array(X_vib)

    pred_segments = model.predict([X_son, X_vib], verbose=0).flatten()
    pred_capture = float(np.mean(pred_segments)) * 100.0   # sigmoïde [0,1] -> %
    return pred_capture, len(fenetres), pred_segments * 100.0


def trouver_modele():
    for nom in MODELES:
        for base in (SCRIPT_DIR, os.getcwd()):
            chemin = os.path.join(base, nom)
            if os.path.exists(chemin):
                return chemin
    return None


def resoudre_csv(valeur):
    """
    Traduit l'argument --csv en chemin absolu vers le fichier de métadonnées.

    Valeurs acceptées :
      'train'          → metadata_captures_moteur.csv  (données d'entraînement)
      'test'           → metadata_captures_test.csv    (données de validation)
      chemin quelconque → utilisé tel quel
    """
    if valeur is None or valeur.lower() == 'train':
        return CSV_TRAIN
    if valeur.lower() == 'test':
        return CSV_TEST
    # Chemin personnalisé fourni directement
    return valeur


def chercher_session_dans_csv(csv_path, session_id):
    """
    Cherche la ligne correspondant à session_id dans le CSV de métadonnées.
    Retourne un dict avec les noms de fichiers et les métadonnées de la session,
    ou None si l'ID n'existe pas dans le fichier.
    """
    import csv as csv_module
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV introuvable : {csv_path}")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            try:
                if int(row['id_session']) == session_id:
                    return row
            except (ValueError, KeyError):
                continue
    return None


# =============================================================================
#  CLI
# =============================================================================

def main():
    p = argparse.ArgumentParser(
        description="Prédit le niveau de tension moteur sur une capture réelle.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument('son', nargs='?', help="Fichier son CSV (ex: son_1.csv ou chemin complet)")
    p.add_argument('vib', nargs='?', help="Fichier vibration CSV (ex: vib_1.csv)")
    p.add_argument('--id',  type=int, help="Numéro de session à chercher dans le CSV de métadonnées")
    p.add_argument('--csv', default='train',
                   help=(
                       "Fichier de métadonnées à utiliser avec --id :\n"
                       "  'train' (défaut) → metadata_captures_moteur.csv\n"
                       "  'test'           → metadata_captures_test.csv\n"
                       "  chemin complet   → n'importe quel autre CSV"
                   ))
    p.add_argument('--condition', choices=['A_vide', 'B_frein'], help="Condition de charge (pour estimer les volts)")
    p.add_argument('--reel',   type=float, help="Niveau de tension réel en %% (pour calculer l'erreur)")
    p.add_argument('--duree',  type=float, default=DUREE_DEFAUT, help="Durée à conserver (s), défaut 15")
    p.add_argument('--modele', help="Chemin du modèle .keras (sinon recherche automatique)")
    args = p.parse_args()

    # ------------------------------------------------------------------
    #  Résolution des chemins son / vib
    # ------------------------------------------------------------------
    condition_csv = None  # condition lue depuis le CSV si disponible
    niveau_reel_csv = None  # niveau de tension lu depuis le CSV

    if args.id is not None:
        # Lecture des vrais noms de fichiers depuis le CSV de métadonnées
        csv_path = resoudre_csv(args.csv)
        print(f"CSV utilisé : {csv_path}")

        session = chercher_session_dans_csv(csv_path, args.id)
        if session is None:
            print(f"ERREUR : session {args.id} introuvable dans {csv_path}")
            sys.exit(1)

        # Sélection du dossier records selon le mode (--csv test → records_test/)
        base_records = RECORDS_DIR_TEST if (args.csv or '').lower() == 'test' else RECORDS_DIR
        path_son = os.path.join(base_records, 'sons',       session['fichier_son'])
        path_vib = os.path.join(base_records, 'vibrations', session['fichier_vibration'])

        # Récupération des métadonnées de la session pour l'affichage
        condition_csv   = session.get('condition_charge')
        niveau_reel_csv = session.get('niveau_tension')
        print(f"Session {args.id} : {session['fichier_son']} | {session['fichier_vibration']}"
              f" | condition={condition_csv} | tension={niveau_reel_csv}%")

    elif args.son and args.vib:
        # Chemins fournis directement — résolution relative au dossier records
        def resoudre(nom, sous_dossier):
            if os.path.exists(nom):
                return nom
            cand = os.path.join(RECORDS_DIR, sous_dossier, nom)
            return cand if os.path.exists(cand) else nom
        path_son = resoudre(args.son, 'sons')
        path_vib = resoudre(args.vib, 'vibrations')

    else:
        p.error("Fournis soit deux fichiers (son vib), soit --id <numero> [--csv train|test].")

    # ------------------------------------------------------------------
    #  Chargement du modèle
    # ------------------------------------------------------------------
    chemin_modele = args.modele or trouver_modele()
    if not chemin_modele or not os.path.exists(chemin_modele):
        print("ERREUR : modèle introuvable. Entraîne d'abord arch4 ou passe --modele <chemin>.")
        print(f"  Cherché : {MODELES}")
        sys.exit(1)
    print(f"Modèle : {chemin_modele}")
    model = tf.keras.models.load_model(chemin_modele)

    # ------------------------------------------------------------------
    #  Chargement de la capture + prédiction
    # ------------------------------------------------------------------
    data_son, magnitude = charger_capture(path_son, path_vib, duree=args.duree)
    pred, n_fen, _ = predire(model, data_son, magnitude)

    # ------------------------------------------------------------------
    #  Affichage du résultat
    # ------------------------------------------------------------------

    # La condition et le niveau réel peuvent venir du CSV ou des arguments
    condition   = args.condition or condition_csv
    niveau_reel = args.reel or (float(niveau_reel_csv) if niveau_reel_csv else None)

    print("\n=== RÉSULTAT ===")
    print(f"  Capture         : {os.path.basename(path_son)} + {os.path.basename(path_vib)}")
    print(f"  Fenêtres son    : {n_fen}")
    print(f"  Tension prédite : {pred:.1f} %")
    if condition and condition in VOLTAGE_MAX:
        vmax = VOLTAGE_MAX[condition]
        print(f"  → soit ~{pred / 100.0 * vmax:.1f} V  (condition {condition}, max {vmax} V)")
    if niveau_reel is not None:
        print(f"  Tension réelle  : {niveau_reel:.1f} %")
        print(f"  Erreur absolue  : {abs(pred - niveau_reel):.1f} points")


if __name__ == "__main__":
    main()
