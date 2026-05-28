import socket
import csv
import os
from datetime import datetime

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT_APP = 9090
METADATA_FILE = 'data/metadata_captures.csv'

def init_metadata():
    """Crée le header si le fichier n'existe pas encore"""
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    if not os.path.exists(METADATA_FILE):
        header = [
            'id_session', 'time_session', 'duree', 'frequence_echantillonnage',
            'matiere', 'vitesse_coupe', 'vitesse_avance', 'type_outil',
            'pareur_outil', 'fichier_son', 'fichier_vibration', 'niveau_usure'
        ]
        with open(METADATA_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)

def get_next_id():
    """Récupère l'ID de la dernière ligne du CSV et retourne ID+1."""
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            lignes = list(csv.reader(f))
        # lignes[0] = header, lignes[1:] = données
        if len(lignes) <= 1:
            return 1  # fichier vide ou header seul → première session
        dernier_id = int(lignes[-1][0])
        return dernier_id + 1
    except (FileNotFoundError, ValueError, IndexError):
        return 1

def read_all(conn):
    """Lit tout le stream TCP jusqu'à la fermeture de la connexion"""
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

            # --- FILTRAGE : on ignore les lignes vides et le marqueur "START" ---
            lignes = [l.strip() for l in raw.splitlines() if l.strip() and l.strip() != "START"]

            if not lignes:
                print(f"[!] Reçu depuis {addr[0]} : aucune ligne CSV utile")
                continue

            # La ligne CSV est la première ligne non-vide non-START
            data_line = lignes[0]
            parts = data_line.split(',')

            if len(parts) == 8:
                session_id = get_next_id()

                nom_fichier_son = f"son_{session_id}.csv"
                nom_fichier_vib = f"vib_{session_id}.csv"

                nouvelle_ligne = [
                    session_id,
                    datetime.now().strftime("%Y-%m-%d_%H:%M"),
                    parts[0],       # duree
                    parts[1],       # frequence_echantillonnage
                    parts[2],       # matiere
                    parts[3],       # vitesse_coupe
                    parts[4],       # vitesse_avance
                    parts[5],       # type_outil
                    parts[6],       # pareur_outil
                    nom_fichier_son,
                    nom_fichier_vib,
                    parts[7]        # niveau_usure
                ]

                with open(METADATA_FILE, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(nouvelle_ligne)

                print(f"Indexation réussie : Session {session_id}")
                print(f" -> Liée aux fichiers : {nom_fichier_son} et {nom_fichier_vib}")
            else:
                print(f"[!] Erreur format : 8 valeurs attendues, reçu {len(parts)} — ligne = '{data_line}'")