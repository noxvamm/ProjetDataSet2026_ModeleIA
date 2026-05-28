# =============================================================================
#  Client UDP — Réception des données ESP32 (son + vibration)
#  Projet BTS CIEL Dataset26 — Maquette moteur
#
#  Ce programme tourne en continu sur le PC et écoute les paquets UDP
#  envoyés par l'ESP32 sur le port 9091.
#
#  Il reçoit deux types de trames :
#    - Son       : "SOUND,timestamp,amp1,amp2,...,ampN"
#    - Vibration : "VIB,timestamp,VX,VY,VZ,ADX,ADY,ADZ,TEMP,DX,DY,DZ,HZX,HZY,HZZ"
#
#  Chaque trame est triée et écrite dans le bon fichier CSV de la session
#  en cours (son_X.csv ou vib_X.csv, X = numéro de session).
#
#  L'ID de session est lu depuis metadata_captures_moteur.csv, qui est
#  rempli au préalable par serveurTCP_metadonnes.py.
# =============================================================================

import socket
import csv
import os
import time

# =============================================================================
#  CONFIGURATION
# =============================================================================

HOST     = '0.0.0.0'   # Écoute sur toutes les interfaces réseau disponibles
PORT_UDP = 9091         # Port UDP utilisé par l'ESP32 pour envoyer ses données

# Dossiers de sortie des fichiers CSV
DATA_DIR  = 'data/'
VIB_DIR   = os.path.join(DATA_DIR, 'records/vibrations/')
SON_DIR   = os.path.join(DATA_DIR, 'records/sons/')

# Fichier de métadonnées écrit par serveurTCP_metadonnes.py
# C'est ici que l'on récupère l'ID de la session en cours
METADATA_FILE = os.path.join(DATA_DIR, 'metadata_captures_moteur.csv')

# Durée d'inactivité (en secondes) avant de considérer la capture terminée
TIMEOUT_PRESENCE = 3.0

# Fréquence d'échantillonnage du micro I2S sur l'ESP32
# Utilisée pour recalculer le timestamp individuel de chaque sample audio
SAMPLE_RATE_SON = 16000   # Hz

# Taille du buffer de réception UDP (8 Mo)
# Un buffer plus grand réduit les pertes de paquets lors des pics de débit
UDP_RCVBUF_SIZE = 8 * 1024 * 1024

# Nombre exact de champs attendus dans une trame vibration :
# "VIB" + Timestamp + VX,VY,VZ + ADX,ADY,ADZ + TEMP + DX,DY,DZ + HZX,HZY,HZZ = 15
VIB_FIELDS_EXPECTED = 15

# Création automatique des dossiers de données s'ils n'existent pas encore
for d in [VIB_DIR, SON_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


# =============================================================================
#  FONCTION : get_current_session_id
# =============================================================================

def get_current_session_id():
    """
    Lit le fichier de métadonnées CSV et retourne l'ID de la dernière session
    enregistrée par serveurTCP_metadonnes.py.

    Principe :
      - La dernière ligne du CSV correspond à la session la plus récente.
      - La colonne 0 (id_session) contient son numéro.

    Retourne "0" si :
      - Le fichier n'existe pas encore (serveur TCP non démarré)
      - Le fichier ne contient que le header (aucune session enregistrée)
      - Une erreur de lecture inattendue survient
    """
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            # On filtre les lignes vides qui peuvent apparaître en fin de fichier
            lines = [l for l in csv.reader(f) if l]

        if len(lines) > 1:
            # lines[0] = header, lines[-1] = dernière session → colonne 0 = id
            return lines[-1][0].strip()

        print(f"  [!] {METADATA_FILE} ne contient que le header — session_id forcé à '0'.")
        return "0"

    except FileNotFoundError:
        print(f"  [!] Fichier introuvable : {METADATA_FILE} — vérif du CWD ? (session_id = '0')")
        return "0"

    except Exception as e:
        print(f"  [!] Lecture metadata échouée ({type(e).__name__}: {e}) — session_id = '0'.")
        return "0"


# =============================================================================
#  INITIALISATION DU SOCKET UDP
# =============================================================================

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:

    # Agrandissement du buffer de réception OS pour absorber les rafales de paquets
    # Sans ça, le noyau peut rejeter des paquets si le programme n'est pas assez rapide
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF_SIZE)
    actual_bufsize = s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

    # Liaison du socket à toutes les interfaces sur le port UDP défini
    s.bind((HOST, PORT_UDP))

    # Mode non-bloquant : recvfrom() lève BlockingIOError si aucun paquet n'est
    # disponible, au lieu de bloquer indéfiniment. Cela permet de continuer à
    # vérifier le timeout de fin de capture dans la même boucle.
    s.setblocking(False)

    print(f"Client en écoute passive sur le port {PORT_UDP}...")
    print(f"Buffer UDP : {actual_bufsize // 1024} KB")
    print("En attente du démarrage de la capture par l'opérateur...")

    # --- Variables d'état de la capture ---
    client_actif        = False   # True dès qu'un premier paquet est reçu
    dernier_paquet_temps = 0      # Horodatage du dernier paquet reçu (pour le timeout)
    compteur_paquets    = 0       # Nombre total de paquets reçus sur la session
    compteur_son        = 0       # Nombre de samples audio écrits
    compteur_vib        = 0       # Nombre de lignes vibration écrites
    compteur_corrompus  = 0       # Nombre de trames rejetées (format invalide)
    session_id          = "0"     # ID de la session en cours
    derniere_session_id = None    # ID de la session précédente (détection doublon)

    try:
        # ==========================================================================
        #  BOUCLE PRINCIPALE — tourne indéfiniment jusqu'à Ctrl+C
        # ==========================================================================
        while True:
            try:
                # Tentative de lecture d'un paquet UDP
                # Lève BlockingIOError si la file est vide → on passe au timeout check
                data, addr = s.recvfrom(4096)

                # --- Début d'une nouvelle capture ---
                # On initialise les compteurs et on récupère l'ID de session
                # uniquement sur le premier paquet reçu après un silence
                if not client_actif:
                    session_id = get_current_session_id()

                    # Avertissement si les métadonnées TCP n'ont pas encore été envoyées
                    if session_id == "0":
                        print(f"  [!!] session_id reçu = 0 — la metadata TCP n'a probablement "
                              f"pas été écrite avant l'arrivée des paquets UDP. Les fichiers "
                              f"son_0.csv / vib_0.csv vont être pollués.")

                    # Avertissement si l'ID n'a pas changé depuis la capture précédente
                    # (l'opérateur a oublié d'envoyer les métadonnées TCP avant de lancer)
                    elif session_id == derniere_session_id:
                        print(f"  [!!] session_id identique à la capture précédente ({session_id}) — "
                              f"l'IHM n'a pas envoyé de nouvelles métadonnées TCP avant cette capture. "
                              f"Les nouveaux échantillons vont s'APPEND à son_{session_id}.csv / "
                              f"vib_{session_id}.csv.")

                    derniere_session_id = session_id
                    print(f"\n[DÉBUT] Capture démarrée — Session {session_id} (depuis {addr[0]})")
                    client_actif     = True
                    compteur_paquets = 0
                    compteur_son     = 0
                    compteur_vib     = 0
                    compteur_corrompus = 0

                # Mise à jour du timestamp du dernier paquet reçu
                dernier_paquet_temps = time.time()
                compteur_paquets += 1

                # Décodage de la trame reçue en texte et découpage par virgule
                trame = data.decode('utf-8', errors='replace').strip()
                parts = trame.split(',')

                # ==================================================================
                #  CAS 1 : TRAME SON
                #  Format ESP32 : "SOUND,timestamp,amp1,amp2,...,ampN"
                #  - "SOUND"    : préfixe identifiant le type de trame
                #  - timestamp  : valeur millis() ESP32 au moment de la lecture I2S
                #  - amp1..ampN : N samples audio (N = BUFFER_LEN de l'ESP32, ex: 128)
                #
                #  Traitement :
                #    On reconstitue un timestamp individuel pour chaque sample en
                #    ajoutant i × (1000 / SR) ms au timestamp de base.
                #    Chaque sample est ensuite écrit sur une ligne séparée dans le CSV.
                # ==================================================================
                if parts[0] == 'SOUND' and len(parts) >= 3:
                    try:
                        ts_base = int(parts[1])
                    except ValueError:
                        print(f"  [!] Timestamp son invalide : {parts[1]}")
                        compteur_corrompus += 1
                        continue

                    amplitudes = parts[2:]          # Liste des N samples audio
                    n          = len(amplitudes)
                    dt_ms      = 1000.0 / SAMPLE_RATE_SON  # Intervalle entre deux samples (ms)

                    file_path = f"{SON_DIR}son_{session_id}.csv"

                    # Création du fichier avec son header si c'est la première écriture
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            csv.writer(f).writerow(['Temps', 'Amplitude'])

                    # Écriture d'une ligne par sample avec son timestamp reconstitué
                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        for i, amp in enumerate(amplitudes):
                            ts_sample = ts_base + i * dt_ms
                            writer.writerow([f"{ts_sample:.4f}", amp])

                    compteur_son += n

                # ==================================================================
                #  CAS 2 : TRAME VIBRATION
                #  Format ESP32 : "VIB,timestamp,VX,VY,VZ,ADX,ADY,ADZ,TEMP,DX,DY,DZ,HZX,HZY,HZZ"
                #  - "VIB"      : préfixe identifiant le type de trame
                #  - timestamp  : valeur millis() ESP32
                #  - VX,VY,VZ  : vitesse angulaire sur les 3 axes (capteur BLE WTVB01)
                #  - ADX,ADY,ADZ: accélération sur les 3 axes
                #  - TEMP       : température du capteur
                #  - DX,DY,DZ  : angle sur les 3 axes
                #  - HZX,HZY,HZZ: fréquence de vibration sur les 3 axes
                #
                #  On vérifie le nombre exact de champs pour rejeter toute trame
                #  fusionnée ou tronquée avant de l'écrire dans le CSV.
                # ==================================================================
                elif parts[0] == 'VIB':

                    # Rejet si le nombre de champs est incorrect
                    if len(parts) != VIB_FIELDS_EXPECTED:
                        print(f"  [!] Trame VIB corrompue ignorée ({len(parts)} champs au lieu de {VIB_FIELDS_EXPECTED})")
                        compteur_corrompus += 1
                        continue

                    file_path = f"{VIB_DIR}vib_{session_id}.csv"

                    # Création du fichier avec son header si c'est la première écriture
                    if not os.path.exists(file_path):
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            header = ['Timestamp', 'VX', 'VY', 'VZ', 'ADX', 'ADY', 'ADZ',
                                      'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ']
                            csv.writer(f).writerow(header)

                    # On écrit tous les champs sauf le préfixe "VIB" (parts[1:])
                    with open(file_path, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow(parts[1:])
                    compteur_vib += 1

                # ==================================================================
                #  CAS 3 : TRAME INCONNUE
                #  Préfixe non reconnu ou format inattendu → on rejette et on log
                # ==================================================================
                else:
                    print(f"  [!] Trame ignorée (format inattendu) : {trame[:80]}...")
                    compteur_corrompus += 1

                # Affichage de progression toutes les 50 trames
                if compteur_paquets % 50 == 0:
                    print(f"   >>> Session {session_id} | Son: {compteur_son} échant. "
                          f"| Vib: {compteur_vib} | Corrompus: {compteur_corrompus}", end='\r')

            except BlockingIOError:
                # Aucun paquet disponible dans la file UDP → on continue la boucle
                # pour vérifier le timeout de fin de capture
                pass

            # ==================================================================
            #  DÉTECTION FIN DE CAPTURE
            #  Si aucun paquet n'a été reçu depuis TIMEOUT_PRESENCE secondes,
            #  on considère que l'ESP32 a arrêté d'envoyer (commande STOP ou
            #  déconnexion). On affiche le bilan et on remet l'état à zéro
            #  pour être prêt à recevoir une nouvelle capture.
            # ==================================================================
            if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):
                print(f"\n[STOP] Fin de réception.")
                print(f"       Paquets reçus     : {compteur_paquets}")
                print(f"       Son               : {compteur_son} échantillons")
                print(f"       Vibration         : {compteur_vib} lignes")
                print(f"       Corrompus/rejetés : {compteur_corrompus}")
                print(f"       Fichiers          : {SON_DIR}son_{session_id}.csv "
                      f"| {VIB_DIR}vib_{session_id}.csv")

                # Estimation de la fréquence son effective
                # (chaque paquet SOUND contient ~128 samples → ~130 paquets/s attendus)
                duree_estimee = compteur_paquets / 130.0
                if compteur_son > 0 and duree_estimee > 0:
                    sr_effectif = compteur_son / duree_estimee
                    perte = 100 * (1 - sr_effectif / SAMPLE_RATE_SON)
                    print(f"       Fréq. son effective : ~{sr_effectif:.0f} Hz (perte {perte:.1f}%)")

                print("\nEn attente d'une nouvelle capture...")
                client_actif = False

            # Pause minimale pour céder la main à l'OS sans bloquer la boucle
            time.sleep(0.0001)

    except KeyboardInterrupt:
        # Arrêt propre via Ctrl+C : on affiche le bilan avant de quitter
        print(f"\n[STOP] Capture terminée manuellement.")
        print(f"       Paquets reçus     : {compteur_paquets}")
        print(f"       Son               : {compteur_son} échantillons")
        print(f"       Vibration         : {compteur_vib} lignes")
        print(f"       Corrompus/rejetés : {compteur_corrompus}")