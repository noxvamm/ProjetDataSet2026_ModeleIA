import socket
import csv
import os
import time

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT_VIB = 9091 
VIB_DIR = 'data/vibrations/'
TIMEOUT_PRESENCE = 3.0 

if not os.path.exists(VIB_DIR):
    os.makedirs(VIB_DIR)

def get_current_session_id():
    try:
        with open('data/metadata_captures.csv', 'r', encoding='utf-8') as f:
            lines = list(csv.reader(f))
            return lines[-1][0] if len(lines) > 1 else "0"
    except: return "0"

# --- INITIALISATION ---
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind((HOST, PORT_VIB))
    s.setblocking(False)
    
    print(f"✅ Serveur VIBRATIONS (UDP) prêt sur le port {PORT_VIB}...")
    
    dernier_paquet_temps = 0
    client_actif = False
    compteur_trames = 0 # Pour ne pas saturer l'affichage

    while True:
        try:
            data, addr = s.recvfrom(1024) 
            
            # Gestion de la connexion visuelle
            if not client_actif:
                print(f"\n📡 [DEBUT FLUX] Réception de l'ESP32 ({addr})")
                client_actif = True
                compteur_trames = 0
            
            dernier_paquet_temps = time.time()
            compteur_trames += 1
            
            # --- MESSAGE DE RECEPTION TOUTES LES 50 TRAMES ---
            if compteur_trames % 50 == 0:
                print(f"   >>> {compteur_trames} trames reçues... (Flux en cours)", end='\r')

            # --- ENREGISTREMENT ---
            trame = data.decode('utf-8').strip()
            session_id = get_current_session_id()
            file_path = f"{VIB_DIR}vib_{session_id}.csv"
            
            if not os.path.exists(file_path):
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow(['VX', 'VY', 'VZ', 'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ'])
            
            with open(file_path, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(trame.split(','))

        except BlockingIOError:
            pass

        # --- GESTION DE LA DECONNEXION ---
        if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):
            print(f"\n❌ [STOP] Flux interrompu après {compteur_trames} trames.")
            client_actif = False

        time.sleep(0.001) # Ultra rapide pour ne rater aucun paquet UDP