import socket
import csv
import os
import time

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT_UDP = 9091 # Port unique pour l'ESP32
DATA_DIR = 'data/'
VIB_DIR = os.path.join(DATA_DIR, 'records/vibrations/')
SON_DIR = os.path.join(DATA_DIR, 'records/sons/')
TIMEOUT_PRESENCE = 3.0 

# Création des dossiers
for d in [VIB_DIR, SON_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def get_current_session_id():
    """Récupère l'ID de session depuis le fichier metadata central"""
    try:
        with open('data/metadata_captures.csv', 'r', encoding='utf-8') as f:
            lines = list(csv.reader(f))
            return lines[-1][0] if len(lines) > 1 else "0"
    except: return "0"

# --- INITIALISATION SOCKET ---
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind((HOST, PORT_UDP))
    s.setblocking(False)
    
    print(f"Serveur MIXTE (Vibrations/Sons) prêt sur le port {PORT_UDP}...")
    
    dernier_paquet_temps = 0
    client_actif = False
    compteur_trames = 0

    while True:
        try:
            data, addr = s.recvfrom(1024) 
            
            if not client_actif:
                print(f"\n[DEBUT FLUX] Réception de : {addr}")
                client_actif = True
                compteur_trames = 0
            
            dernier_paquet_temps = time.time()
            compteur_trames += 1
            
            # Décodage et séparation
            trame = data.decode('utf-8').strip()
            parts = trame.split(',')
            session_id = get_current_session_id()

            # --- LOGIQUE DE TRI (AIGUILLAGE) ---
            
            # CAS 1 : C'est du SON (2 colonnes)
            if len(parts) == 2:
                file_path = f"{SON_DIR}son_{session_id}.csv"
                if not os.path.exists(file_path):
                    with open(file_path, 'w', newline='') as f:
                        csv.writer(f).writerow(['Temps', 'Amplitude'])
                
                with open(file_path, 'a', newline='') as f:
                    csv.writer(f).writerow(parts)

            # CAS 2 : C'est de la VIBRATION (10 colonnes)
            elif len(parts) >= 10:
                file_path = f"{VIB_DIR}vib_{session_id}.csv"
                if not os.path.exists(file_path):
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        header = ['Timestamp', 'VX', 'VY', 'VZ', 'ADX', 'ADY', 'ADZ', 'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ']
                        csv.writer(f).writerow(header)
                
                with open(file_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(parts)

            # Affichage de progression
            if compteur_trames % 100 == 0:
                print(f"   >>> {compteur_trames} paquets traités (Session {session_id})", end='\r')

        except BlockingIOError:
            pass

        # --- GESTION DE LA DECONNEXION ---
        if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):
            print(f"\n[STOP] Fin de réception. {compteur_trames} paquets archivés.")
            client_actif = False

        time.sleep(0.0001) # Vitesse maximale