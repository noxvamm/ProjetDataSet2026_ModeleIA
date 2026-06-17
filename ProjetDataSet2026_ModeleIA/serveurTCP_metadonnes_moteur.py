import socket
import csv
import os
from datetime import datetime

# =============================================================================
#  Serveur TCP — Indexation des métadonnées de capture (maquette moteur)
#
#  RÔLE DANS LA CHAÎNE : ce programme reçoit de l'IHM les INFOS d'une capture
#  (condition, durée, fréquences, niveau de tension) — pas les données capteur
#  elles-mêmes, qui partent en UDP vers le client. Il leur attribue un numéro
#  de session, les enregistre dans un CSV, et écrit un petit fichier d'état
#  (current_session.txt) qui dit au client UDP sous quel nom ranger ses fichiers.
#
#  POURQUOI TCP (et pas UDP) : TCP est un canal FIABLE — chaque octet envoyé est
#  garanti d'arriver, dans l'ordre. C'est ce qu'il faut pour des métadonnées
#  (perdre la fiche d'une capture serait grave). Le son/vibration, eux, passent
#  en UDP : plus rapide, mais sans garantie de livraison — perdre quelques
#  échantillons sur des milliers n'est pas gênant.
#
#  Deux destinations possibles pour chaque capture :
#    TRAIN → metadata_captures_moteur.csv  /  son_X.csv       / vib_X.csv
#    TEST  → metadata_captures_test.csv    /  son_test_X.csv  / vib_test_X.csv
#
#  À chaque nouvelle capture reçue, le serveur demande à l'opérateur
#  sur la console : "TRAIN ou TEST ?"
#  La dernière réponse est mémorisée comme valeur par défaut.
# =============================================================================

# --- CONFIGURATION ---
HOST     = '0.0.0.0'   # '0.0.0.0' = écoute sur TOUTES les cartes réseau du PC
PORT_APP = 9090        # port où l'IHM vient se connecter (doit être identique côté IHM)

METADATA_FILE_TRAIN = 'data/metadata_captures_moteur.csv'
METADATA_FILE_TEST  = 'data/metadata_captures_test.csv'

# Fichier d'état écrit après chaque session pour indiquer au client UDP
# quel dossier utiliser (records/ ou records_test/) et quel ID de session
SESSION_STATE_FILE  = 'data/current_session.txt'

CSV_HEADER = [
    'id_session', 'time_session',
    'condition_charge',
    'duree', 'frequence_son', 'frequence_vibration',
    'fichier_son', 'fichier_vibration',
    'niveau_tension'
]

# Mapping des conditions de charge vers des catégories canoniques
CONDITION_MAP = {
    'aucune':     'A_vide',
    'a_vide':     'A_vide',
    'sans':       'A_vide',
    'sans frein': 'A_vide',
    'a vide':     'A_vide',
    'avec':       'B_frein',
    'avec frein': 'B_frein',
    'frein':      'B_frein',
    'b_frein':    'B_frein',
}


# =============================================================================
#  FONCTIONS UTILITAIRES
# =============================================================================

def init_metadata(fichier):
    """Crée le fichier CSV avec son header s'il n'existe pas encore."""
    os.makedirs(os.path.dirname(fichier), exist_ok=True)
    if not os.path.exists(fichier):
        with open(fichier, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(CSV_HEADER)
        print(f"  Fichier créé : {fichier}")


def get_next_id(fichier):
    """
    Retourne max(id) + 1 sur l'ensemble du fichier CSV.
    Chaque fichier (train / test) a son propre compteur indépendant.

    On prend le MAXIMUM et non la dernière ligne : le fichier n'est pas
    forcément trié par ID (des recaptures ont déjà été appendées hors
    ordre pendant la campagne de mai), et repartir de la dernière ligne
    réattribuait des ID existants — les nouvelles données s'appendaient
    alors dans les fichiers son/vib d'anciennes sessions.
    """
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            lignes = list(csv.reader(f))
        ids = [int(l[0]) for l in lignes[1:] if l and l[0].strip().isdigit()]
        if not ids:
            return 1
        return max(ids) + 1
    except (FileNotFoundError, ValueError, IndexError):
        return 1


def normaliser_condition(valeur_brute):
    """Convertit le libellé brut de l'IHM en condition canonique."""
    cle = valeur_brute.strip().lower()
    return CONDITION_MAP.get(cle, valeur_brute.strip())


def read_all(conn):
    """Lit tout le message TCP envoyé par l'IHM, jusqu'à fermeture ou timeout.

    En TCP les données arrivent en « flux » (stream) : un même message peut être
    découpé en plusieurs morceaux (chunks). On boucle donc pour tout rassembler."""
    buffer = b""                     # accumulateur d'octets bruts (b"" = bytes vides)
    conn.settimeout(2.0)             # abandonne la lecture si rien n'arrive pendant 2 s
    try:
        while True:
            chunk = conn.recv(1024)  # recv : lit jusqu'à 1024 octets sur la connexion
            if not chunk:            # morceau vide = l'IHM a fermé la connexion
                break
            buffer += chunk
    except socket.timeout:
        pass
    return buffer.decode('utf-8')    # transforme les octets reçus en texte


def demander_mode(dernier_mode):
    """
    Demande à l'opérateur sur la console si la capture va en TRAIN ou TEST.
    Affiche le dernier mode utilisé comme valeur par défaut (appui Entrée = même mode).
    Boucle jusqu'à recevoir une réponse valide.
    """
    while True:
        reponse = input(f"\n  → Destination ? [TRAIN / TEST]  (défaut : {dernier_mode}) : ").strip().upper()

        if reponse == '':
            # Entrée vide = on garde le dernier mode
            return dernier_mode
        if reponse in ('TRAIN', 'TEST'):
            return reponse

        print("  [!] Réponse invalide. Tapez TRAIN ou TEST (ou Entrée pour garder le mode actuel).")


# =============================================================================
#  INITIALISATION
# =============================================================================

init_metadata(METADATA_FILE_TRAIN)
init_metadata(METADATA_FILE_TEST)
os.makedirs(os.path.dirname(SESSION_STATE_FILE), exist_ok=True)

print("=" * 60)
print(f"  Serveur d'indexation prêt  —  Port {PORT_APP}")
print(f"  TRAIN → {METADATA_FILE_TRAIN}")
print(f"  TEST  → {METADATA_FILE_TEST}")
print("=" * 60)

# Mémorise le dernier mode choisi pour le proposer par défaut au prochain coup
dernier_mode = 'TRAIN'


# =============================================================================
#  BOUCLE PRINCIPALE — attend une IHM, indexe la capture, répond
#
#  Tourne indéfiniment : pour chaque connexion de l'IHM, on lit la ligne de
#  métadonnées, on demande TRAIN/TEST, on calcule le numéro de session, on écrit
#  le CSV + le fichier d'état current_session.txt, puis on confirme à l'IHM.
# =============================================================================

# socket(AF_INET, SOCK_STREAM) : crée une « prise » réseau en mode TCP.
#   AF_INET = adressage IPv4 ; SOCK_STREAM = TCP (flux fiable et ordonné).
#   Le « with » garantit que la prise se referme proprement à la fin.
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT_APP))   # bind : réserve l'adresse + le port pour ce programme
    s.listen()                 # listen : passe en mode « serveur », prêt à recevoir
    print("\nEn attente d'une connexion IHM...\n")

    while True:
        # accept : met le programme EN PAUSE jusqu'à ce qu'une IHM se connecte.
        #   Retourne une connexion dédiée (conn) + l'adresse du client (addr).
        conn, addr = s.accept()
        with conn:
            raw = read_all(conn)
            if not raw:
                continue

            # Filtre les lignes vides et le marqueur START
            lignes = [l.strip() for l in raw.splitlines() if l.strip() and l.strip() != "START"]

            if not lignes:
                print(f"[!] Reçu depuis {addr[0]} : aucune ligne utile")
                continue

            data_line = lignes[0]
            parts     = data_line.split(',')

            # ------------------------------------------------------------------
            #  ENREGISTREMENT D'UNE SESSION (5 champs attendus)
            # ------------------------------------------------------------------
            if len(parts) == 5:
                condition = normaliser_condition(parts[0])

                # Affichage du résumé de la capture reçue
                print(f"┌─ Nouvelle capture reçue depuis {addr[0]}")
                print(f"│  Condition : {condition}")
                print(f"│  Durée     : {parts[1]} s")
                print(f"│  Fréq. son : {parts[2]} Hz  |  Fréq. vib : {parts[3]} Hz")
                print(f"│  Tension   : {parts[4]} %")

                # Demande à l'opérateur sur la console
                mode_choisi = demander_mode(dernier_mode)
                dernier_mode = mode_choisi

                # Sélection du fichier CSV selon le mode
                # Les fichiers son/vib sont toujours nommés son_<id>.csv / vib_<id>.csv
                # c'est le dossier (records/ ou records_test/) qui distingue TRAIN et TEST
                if mode_choisi == 'TEST':
                    fichier_csv = METADATA_FILE_TEST
                else:
                    fichier_csv = METADATA_FILE_TRAIN

                session_id      = get_next_id(fichier_csv)
                nom_fichier_son = f"son_{session_id}.csv"
                nom_fichier_vib = f"vib_{session_id}.csv"

                nouvelle_ligne = [
                    session_id,
                    datetime.now().strftime("%Y-%m-%d_%H:%M"),
                    condition,
                    parts[1],           # duree
                    parts[2],           # frequence_son
                    parts[3],           # frequence_vibration
                    nom_fichier_son,
                    nom_fichier_vib,
                    parts[4]            # niveau_tension
                ]

                with open(fichier_csv, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(nouvelle_ligne)

                # Écriture du fichier d'état pour le client UDP
                # Format : "id_session,mode"  (ex: "3,TEST" ou "5,TRAIN")
                with open(SESSION_STATE_FILE, 'w', encoding='utf-8') as f:
                    f.write(f"{session_id},{mode_choisi}\n")

                print(f"└─ [{mode_choisi}] Session {session_id} indexée")
                print(f"   Fichiers : {nom_fichier_son}  |  {nom_fichier_vib}")
                print(f"   CSV      : {fichier_csv}\n")

                # Réponse au client pour confirmation
                try:
                    conn.sendall(f"OK id={session_id} mode={mode_choisi}\n".encode('utf-8'))
                except Exception:
                    pass

            else:
                print(f"[!] Format invalide : 5 valeurs attendues, reçu {len(parts)} — '{data_line}'")
                try:
                    conn.sendall(b"ERREUR: format invalide (condition,duree,fSon,fVib,niveau)\n")
                except Exception:
                    pass
