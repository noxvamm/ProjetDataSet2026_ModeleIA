import socket
import csv
import os
from datetime import datetime

# Configuration de base du serveur 
HOST = '0.0.0.0'
PORT_APP = 9090
METADATA_FILE = 'data/metadata_captures_moteur.csv'

def init_metadata():
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True) # Crée le header du fichier de métadonnées s'il n'existe pas déjà
    if not os.path.exists(METADATA_FILE):
        header = [
            'id_session', 'time_session',
            'condition_charge',
            'duree', 'frequence_son', 'frequence_vibration',
            'fichier_son', 'fichier_vibration',
            'niveau_tension'
        ]
        with open(METADATA_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)


# Mapping des conditions de charge possibles vers des catégories canoniques (A_vide ou B_frein).
CONDITION_MAP = {
    'aucune':    'A_vide',
    'a_vide':    'A_vide',
    'sans':      'A_vide',
    'sans frein':'A_vide',
    'a vide':    'A_vide',
    'avec':      'B_frein',
    'avec frein':'B_frein',
    'frein':     'B_frein',
    'b_frein':   'B_frein',
}


def normaliser_condition(valeur_brute):
    cle = valeur_brute.strip().lower() # Convertit le libellé envoyé par l'IHM en condition canonique.
    return CONDITION_MAP.get(cle, valeur_brute.strip())

# Cette fonction lit le fichier de métadonnées pour déterminer le prochain ID de session à utiliser en fonction du nombre de lignes existantes.
def get_next_id():
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return sum(1 for line in f)
    except FileNotFoundError:
        return 1

# Lit le stream TCP jusqu'a la fin de la transmission (indiquée par une fermeture de connexion) ou jusqu'à un timeout pour éviter de bloquer indéfiniment.
def read_all(conn):
    buffer = b""
    conn.settimeout(2.0)  # Au cas où la fermeture tarde
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            buffer += chunk
    except socket.timeout:
        pass
    return buffer.decode('utf-8')

init_metadata()
print(f"Serveur d'indexation prêt (Port {PORT_APP})...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT_APP))
    s.listen()

    while True:
        conn, addr = s.accept()
        with conn:
            raw = read_all(conn)
            if not raw:
                continue

            # On filtre les lignes vides et le marqueur START
            lignes = [l.strip() for l in raw.splitlines() if l.strip() and l.strip() != "START"]

            if not lignes:
                print(f"[!] Reçu depuis {addr[0]} : aucune ligne CSV utile")
                continue

            # La ligne CSV est la première ligne non-vide non-START
            data_line = lignes[0]
            parts = data_line.split(',')

            if len(parts) == 5:
                session_id = get_next_id()

                nom_fichier_son = f"son_{session_id}.csv"
                nom_fichier_vib = f"vib_{session_id}.csv"

                condition = normaliser_condition(parts[0])

                nouvelle_ligne = [
                    session_id,
                    datetime.now().strftime("%Y-%m-%d_%H:%M"),
                    condition,      # condition_charge (A_vide / B_frein)
                    parts[1],       # duree
                    parts[2],       # frequence_son
                    parts[3],       # frequence_vibration
                    nom_fichier_son, # chemin des fichiers sons
                    nom_fichier_vib, # chemin des fichiers vibrations
                    parts[4]        # niveau_tension
                ]

                with open(METADATA_FILE, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(nouvelle_ligne)

                print(f"Indexation réussie : Session {session_id} [{condition}]")
                print(f" -> Liée aux fichiers : {nom_fichier_son} et {nom_fichier_vib}")
            else:
                print(f"[!] Erreur format : 5 valeurs attendues (condition,duree,fSon,fVib,niveau), reçu {len(parts)} — ligne = '{data_line}'")