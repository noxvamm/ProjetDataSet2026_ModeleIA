import socket
import csv
import os
import time

# --- CONFIGURATION ---
HOST = '0.0.0.0'       # Ecoute sur toutes les interfaces
PORT_UDP = 9091
DATA_DIR = 'data/'
VIB_DIR = os.path.join(DATA_DIR, 'records/vibrations/')
SON_DIR = os.path.join(DATA_DIR, 'records/sons/')
TIMEOUT_PRESENCE = 3.0  # Secondes sans paquet = fin de capture

# Création des dossiers si inexistants
for d in [VIB_DIR, SON_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def get_current_session_id():
    """Récupère l'ID de session depuis le fichier metadata central"""
    try:
        with open('data/metadata_captures.csv', 'r', encoding='utf-8') as f:
            lines = list(csv.reader(f))
            return lines[-1][0] if len(lines) > 1 else "0"
    except:
        return "0"

# --- INITIALISATION SOCKET (mode passif) ---
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.bind((HOST, PORT_UDP))
    s.setblocking(False)

    print(f"Client en écoute passive sur le port {PORT_UDP}...")
    print("En attente du démarrage de la capture par l'opérateur...")

    client_actif = False
    dernier_paquet_temps = 0
    compteur_trames = 0
    compteur_son = 0
    compteur_vib = 0
    session_id = "0"

    try:
        while True:
            try:
                data, addr = s.recvfrom(1024)

                if not client_actif:
                    session_id = get_current_session_id()
                    print(f"\n[DÉBUT] Capture démarrée — Session {session_id} (depuis {addr[0]})")
                    client_actif = True
                    compteur_trames = 0
                    compteur_son = 0
                    compteur_vib = 0

                dernier_paquet_temps = time.time()
                compteur_trames += 1

                trame = data.decode('utf-8').strip()
                parts = trame.split(',')

                # --- LOGIQUE DE TRI (tolérante aux deux formats son) ---

                # Détection du SON : "SOUND,ts,amp" (nouveau format) OU "ts,amp" (ancien format)
                is_son = False
                ts_son, amp_son = None, None

                if parts[0] == 'SOUND' and len(parts) == 3:
                    ts_son, amp_son = parts[1], parts[2]
                    is_son = True
                elif len(parts) == 2:
                    # Vérification : les deux champs doivent être numériques
                    try:
                        int(parts[0])
                        int(parts[1])
                        ts_son, amp_son = parts[0], parts[1]
                        is_son = True
                    except ValueError:
                        is_son = False

                # CAS 1 : SON
                if is_son:
                    file_path = f"{SON_DIR}son_{session_id}.csv"
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            csv.writer(f).writerow(['Temps', 'Amplitude'])
                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow([ts_son, amp_son])
                    compteur_son += 1

                # CAS 2 : VIBRATION → "VIB,timestamp,VX,VY,VZ,..."
                elif parts[0] == 'VIB' and len(parts) >= 14:
                    file_path = f"{VIB_DIR}vib_{session_id}.csv"
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            header = ['Timestamp', 'VX', 'VY', 'VZ', 'ADX', 'ADY', 'ADZ',
                                      'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ']
                            csv.writer(f).writerow(header)
                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(parts[1:])  # on retire le préfixe "VIB"
                    compteur_vib += 1

                else:
                    print(f"  [!] Trame ignorée (format inattendu) : {trame}")

                # Affichage de progression
                if compteur_trames % 50 == 0:
                    print(f"   >>> Session {session_id} | Son: {compteur_son} | Vib: {compteur_vib}", end='\r')

            except BlockingIOError:
                pass

            # --- DÉTECTION FIN DE CAPTURE ---
            if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):
                print(f"\n[STOP] Fin de réception.")
                print(f"       Total : {compteur_trames} paquets | Son: {compteur_son} | Vib: {compteur_vib}")
                print(f"       Fichiers : {SON_DIR}son_{session_id}.csv | {VIB_DIR}vib_{session_id}.csv")
                print("\nEn attente d'une nouvelle capture...")
                client_actif = False

            time.sleep(0.0001)

    except KeyboardInterrupt:
        print(f"\n[STOP] Capture terminée manuellement.")
        print(f"       Total : {compteur_trames} paquets | Son: {compteur_son} | Vib: {compteur_vib}")