import socket
import csv
import os
import time

# --- CONFIGURATION ---
HOST = '0.0.0.0'
PORT_UDP = 9091
DATA_DIR = 'data/'
VIB_DIR = os.path.join(DATA_DIR, 'records/vibrations/')
SON_DIR = os.path.join(DATA_DIR, 'records/sons/')
METADATA_FILE = os.path.join(DATA_DIR, 'metadata_captures_moteur.csv')
TIMEOUT_PRESENCE = 3.0
SAMPLE_RATE_SON = 16000
UDP_RCVBUF_SIZE = 8 * 1024 * 1024   # 8 MB pour éviter les pertes UDP

# Nombre exact de champs attendus pour une trame VIBRATION
# (Timestamp + 13 colonnes capteur = 14 champs après split)
VIB_FIELDS_EXPECTED = 15

# Création des dossiers si inexistants
for d in [VIB_DIR, SON_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def get_current_session_id():
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            lines = [l for l in csv.reader(f) if l]
        if len(lines) > 1:
            return lines[-1][0].strip()
        print(f"  [!] {METADATA_FILE} ne contient que le header — session_id forcé à '0'.")
        return "0"
    except FileNotFoundError:
        print(f"  [!] Fichier introuvable : {METADATA_FILE} — vérif du CWD ? (session_id = '0')")
        return "0"
    except Exception as e:
        print(f"  [!] Lecture metadata échouée ({type(e).__name__}: {e}) — session_id = '0'.")
        return "0"

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    # Buffer UDP agrandi pour réduire les pertes à haut débit
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF_SIZE)
    actual_bufsize = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

    s.bind((HOST, PORT_UDP))
    s.setblocking(False)

    print(f"Client en écoute passive sur le port {PORT_UDP}...")
    print(f"Buffer UDP : {actual_bufsize // 1024} KB")
    print("En attente du démarrage de la capture par l'opérateur...")

    client_actif = False
    dernier_paquet_temps = 0
    compteur_paquets = 0
    compteur_son = 0
    compteur_vib = 0
    compteur_corrompus = 0
    session_id = "0"
    derniere_session_id = None   # pour détecter un doublon

    try:
        while True:
            try:
                data, addr = s.recvfrom(4096)

                if not client_actif:
                    session_id = get_current_session_id()
                    if session_id == "0":
                        print(f"  [!!] session_id reçu = 0 — la metadata TCP n'a probablement "
                              f"pas été écrite avant l'arrivée des paquets UDP. Les fichiers "
                              f"son_0.csv / vib_0.csv vont être pollués.")
                    elif session_id == derniere_session_id:
                        print(f"  [!!] session_id identique à la capture précédente ({session_id}) — "
                              f"l'IHM n'a pas envoyé de nouvelles métadonnées TCP avant cette capture. "
                              f"Les nouveaux échantillons vont s'APPEND à son_{session_id}.csv / "
                              f"vib_{session_id}.csv.")
                    derniere_session_id = session_id
                    print(f"\n[DÉBUT] Capture démarrée — Session {session_id} (depuis {addr[0]})")
                    client_actif = True
                    compteur_paquets = 0
                    compteur_son = 0
                    compteur_vib = 0
                    compteur_corrompus = 0

                dernier_paquet_temps = time.time()
                compteur_paquets += 1

                trame = data.decode('utf-8', errors='replace').strip()
                parts = trame.split(',')

                # --- CAS 1 : SON → "SOUND,ts,amp1,amp2,...,ampN" (≥ 3 champs) ---
                if parts[0] == 'SOUND' and len(parts) >= 3:
                    try:
                        ts_base = int(parts[1])
                    except ValueError:
                        print(f"  [!] Timestamp son invalide : {parts[1]}")
                        compteur_corrompus += 1
                        continue

                    amplitudes = parts[2:]
                    n = len(amplitudes)
                    dt_ms = 1000.0 / SAMPLE_RATE_SON

                    file_path = f"{SON_DIR}son_{session_id}.csv"
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            csv.writer(f).writerow(['Temps', 'Amplitude'])

                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        for i, amp in enumerate(amplitudes):
                            ts_sample = ts_base + i * dt_ms
                            writer.writerow([f"{ts_sample:.4f}", amp])

                    compteur_son += n

                # --- CAS 2 : VIBRATION → "VIB,ts,VX,VY,VZ,..." (STRICTEMENT 14 champs) ---
                elif parts[0] == 'VIB':
                    # Rejet strict des trames fusionnées (défense en profondeur,
                    # même si le mutex ESP32 devrait déjà empêcher ça)
                    if len(parts) != VIB_FIELDS_EXPECTED:
                        print(f"  [!] Trame VIB corrompue ignorée ({len(parts)} champs au lieu de {VIB_FIELDS_EXPECTED})")
                        compteur_corrompus += 1
                        continue

                    file_path = f"{VIB_DIR}vib_{session_id}.csv"
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            header = ['Timestamp', 'VX', 'VY', 'VZ', 'ADX', 'ADY', 'ADZ',
                                      'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ']
                            csv.writer(f).writerow(header)
                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(parts[1:])
                    compteur_vib += 1

                else:
                    print(f"  [!] Trame ignorée (format inattendu) : {trame[:80]}...")
                    compteur_corrompus += 1

                # Affichage de progression (toutes les 50 trames)
                if compteur_paquets % 50 == 0:
                    print(f"   >>> Session {session_id} | Son: {compteur_son} échant. | Vib: {compteur_vib} | Corrompus: {compteur_corrompus}", end='\r')

            except BlockingIOError:
                pass

            # --- DÉTECTION FIN DE CAPTURE ---
            if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):
                print(f"\n[STOP] Fin de réception.")
                print(f"       Paquets reçus : {compteur_paquets}")
                print(f"       Son : {compteur_son} échantillons | Vib : {compteur_vib} lignes")
                print(f"       Paquets corrompus / rejetés : {compteur_corrompus}")
                print(f"       Fichiers : {SON_DIR}son_{session_id}.csv | {VIB_DIR}vib_{session_id}.csv")

                # Estimation qualité
                duree_estimee = compteur_paquets / 130.0
                if compteur_son > 0 and duree_estimee > 0:
                    sr_effectif = compteur_son / duree_estimee
                    perte = 100 * (1 - sr_effectif / SAMPLE_RATE_SON)
                    print(f"       Fréq. son effective : ~{sr_effectif:.0f} Hz (perte {perte:.1f}%)")

                print("\nEn attente d'une nouvelle capture...")
                client_actif = False

            time.sleep(0.0001)

    except KeyboardInterrupt:
        print(f"\n[STOP] Capture terminée manuellement.")
        print(f"       Paquets reçus : {compteur_paquets}")
        print(f"       Son : {compteur_son} échantillons | Vib : {compteur_vib} lignes")
        print(f"       Corrompus : {compteur_corrompus}")