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
    if not os.path.exists(METADATA_FILE):
        header = [
            'id_session', 'time_session', 'duree', 'frequence_echantillonnage', 
            'matiere', 'vitesse_coupe', 'vitesse_avance', 'type_outil', 
            'pareur_outil', 'fichier_son', 'fichier_vibration', 'niveau_usure'
        ]
        with open(METADATA_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)

def get_next_id():
    """Calcule l'ID en fonction du nombre de lignes existantes"""
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            # On compte les lignes et on ajoute 1
            return sum(1 for line in f) 
    except FileNotFoundError:
        return 1

init_metadata()
print(f"Serveur d'indexation prêt (Port {PORT_APP})...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT_APP))
    s.listen()
    
    while True:
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024).decode('utf-8')
            if data:
                # Format reçu du C++ : "Duree,Freq,Matiere,Vc,Vf,TypeOutil,NomOperateur,Usure"
                parts = data.strip().split(',')
                
                if len(parts) == 8:
                    session_id = get_next_id()
                    
                    # GÉNÉRATION AUTOMATIQUE DES NOMS DE FICHIERS
                    # On crée les noms de fichiers basés sur l'ID pour la cohérence
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
                        nom_fichier_son, # Rajouté automatiquement
                        nom_fichier_vib, # Rajouté automatiquement
                        parts[7]        # niveau_usure (0 ou 1)
                    ]
                    
                    # Écriture de la ligne d'index dans le fichier global
                    with open(METADATA_FILE, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(nouvelle_ligne)
                    
                    print(f"Indexation réussie : Session {session_id}")
                    print(f" -> Liée aux fichiers : {nom_fichier_son} et {nom_fichier_vib}")
                else:
                    print(f"Erreur format : 8 valeurs attendues, reçu {len(parts)}")