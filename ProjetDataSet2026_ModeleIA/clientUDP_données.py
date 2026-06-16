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
#  --- Synchronisation avec le serveur TCP (anti-course) ---
#  L'ID de session est écrit dans current_session.txt par le serveur TCP,
#  mais seulement APRÈS que l'opérateur a répondu à la question TRAIN/TEST
#  sur sa console — soit plusieurs secondes après l'arrivée des premières
#  trames UDP. Pour ne pas écrire dans les fichiers de la session
#  précédente, le client met les trames en tampon (RAM) et n'écrit sur le
#  disque qu'une fois que le contenu de current_session.txt a CHANGÉ par
#  rapport à ce qu'il contenait au début de la capture. Si rien ne change
#  au bout de ATTENTE_SESSION_MAX secondes, on écrit quand même avec l'état
#  courant, en signalant clairement le problème.
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

# Dossiers TRAIN (captures d'entraînement)
VIB_DIR      = os.path.join(DATA_DIR, 'records/vibrations/')
SON_DIR      = os.path.join(DATA_DIR, 'records/sons/')

# Dossiers TEST (captures de validation du modèle)
VIB_DIR_TEST = os.path.join(DATA_DIR, 'records_test/vibrations/')
SON_DIR_TEST = os.path.join(DATA_DIR, 'records_test/sons/')

# Fichier d'état écrit par serveurTCP_metadonnes_moteur.py après chaque session.
# Contient "id_session,mode" (ex: "3,TEST").
SESSION_STATE_FILE = os.path.join(DATA_DIR, 'current_session.txt')

# Durée d'inactivité (en secondes) avant de considérer la capture terminée
TIMEOUT_PRESENCE = 3.0

# Temps maximum (en secondes) pendant lequel on garde les trames en tampon
# en attendant que le serveur TCP indexe la session (réponse TRAIN/TEST de
# l'opérateur). Au-delà, on écrit avec l'état courant + avertissement.
ATTENTE_SESSION_MAX = 15.0

# Intervalle (en secondes) entre deux relectures de current_session.txt
# pendant la phase de tampon
INTERVALLE_VERIF_ETAT = 0.2

# Fréquence d'échantillonnage du micro I2S sur l'ESP32
# Utilisée pour recalculer le timestamp individuel de chaque sample audio
SAMPLE_RATE_SON = 16000   # Hz

# Taille du buffer de réception UDP (8 Mo)
# Un buffer plus grand réduit les pertes de paquets lors des pics de débit
UDP_RCVBUF_SIZE = 8 * 1024 * 1024

# Nombre exact de champs attendus dans une trame vibration :
# "VIB" + Timestamp + VX,VY,VZ + ADX,ADY,ADZ + TEMP + DX,DY,DZ + HZX,HZY,HZZ = 15
VIB_FIELDS_EXPECTED = 15

HEADER_SON = ['Temps', 'Amplitude']
HEADER_VIB = ['Timestamp', 'VX', 'VY', 'VZ', 'ADX', 'ADY', 'ADZ',
              'TEMP', 'DX', 'DY', 'DZ', 'HZX', 'HZY', 'HZZ']

# Création automatique des dossiers de données s'ils n'existent pas encore
for d in [VIB_DIR, SON_DIR, VIB_DIR_TEST, SON_DIR_TEST]:
    if not os.path.exists(d):
        os.makedirs(d)


# =============================================================================
#  FONCTIONS UTILITAIRES
# =============================================================================

def lire_etat_brut():
    """
    Lit le contenu brut (première ligne) de current_session.txt.
    Retourne None si le fichier n'existe pas ou n'est pas lisible.
    """
    try:
        with open(SESSION_STATE_FILE, 'r', encoding='utf-8') as f:
            return f.readline().strip()
    except OSError:
        return None


def parser_etat(ligne):
    """
    Convertit une ligne d'état "id_session,mode" en tuple (id, mode).

    Retourne ("0", "TRAIN") si la ligne est vide, absente ou mal formée.
    """
    if not ligne:
        return "0", "TRAIN"

    if ',' in ligne:
        session_id, mode = ligne.split(',', 1)
        mode = mode.strip().upper()
        if mode not in ('TRAIN', 'TEST'):
            mode = 'TRAIN'
        return session_id.strip() or "0", mode

    # Ligne sans virgule → ancien format ou fichier corrompu
    print(f"  [!] {SESSION_STATE_FILE} : format inattendu ('{ligne}') — mode TRAIN par défaut.")
    return ligne.strip() or "0", "TRAIN"


def ecrire_csv(file_path, header, lignes):
    """
    Ajoute des lignes à un CSV, en créant le fichier avec son header
    si c'est la première écriture. Accepte une liste de lignes (tampon
    complet) ou une seule ligne dans une liste.
    """
    nouveau = not os.path.exists(file_path)
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if nouveau:
            writer.writerow(header)
        writer.writerows(lignes)


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
    client_actif         = False   # True dès qu'un premier paquet est reçu
    dernier_paquet_temps = 0       # Horodatage du dernier paquet reçu (pour le timeout)
    compteur_paquets     = 0       # Nombre total de paquets reçus sur la session
    compteur_son         = 0       # Nombre de samples audio reçus
    compteur_vib         = 0       # Nombre de lignes vibration reçues
    compteur_corrompus   = 0       # Nombre de trames rejetées (format invalide)
    session_id           = "0"     # ID de la session en cours
    session_mode         = "TRAIN" # Mode de la session (TRAIN ou TEST)
    derniere_session_id  = None    # ID de la session précédente (détection doublon)
    chemin_son           = None    # Chemin du CSV son une fois la session connue
    chemin_vib           = None    # Chemin du CSV vibration une fois la session connue

    # --- Variables de la phase de tampon (attente de l'indexation TCP) ---
    en_attente_session = False  # True tant que current_session.txt n'a pas changé
    etat_initial       = None   # Contenu du fichier d'état au début de la capture
    deadline_session   = 0      # Heure limite d'attente avant écriture forcée
    derniere_verif     = 0      # Heure de la dernière relecture du fichier d'état
    buffer_son         = []     # Lignes son en attente d'écriture
    buffer_vib         = []     # Lignes vibration en attente d'écriture

    def adopter_session(ligne_etat, raison):
        """
        Fige l'ID et le mode de la session, vide les tampons dans les bons
        fichiers CSV et passe en écriture directe pour la suite de la capture.
        """
        global session_id, session_mode, derniere_session_id
        global chemin_son, chemin_vib, en_attente_session
        global buffer_son, buffer_vib

        session_id, session_mode = parser_etat(ligne_etat)

        # Sélection des dossiers de sortie selon le mode TRAIN / TEST
        son_dir = SON_DIR_TEST if session_mode == 'TEST' else SON_DIR
        vib_dir = VIB_DIR_TEST if session_mode == 'TEST' else VIB_DIR

        # Avertissements sur les cas anormaux (visibles seulement si on a dû
        # forcer l'écriture sans que le serveur ait indexé la session)
        if session_id == "0":
            print(f"  [!!] session_id = 0 — le serveur TCP n'a jamais écrit "
                  f"{SESSION_STATE_FILE}. Vérifier qu'il est bien démarré.")
        elif session_id == derniere_session_id:
            print(f"  [!!] session_id identique à la capture précédente ({session_id}) — "
                  f"les nouveaux échantillons vont s'APPEND aux fichiers existants.")

        derniere_session_id = session_id
        chemin_son = f"{son_dir}son_{session_id}.csv"
        chemin_vib = f"{vib_dir}vib_{session_id}.csv"

        # Écriture du tampon accumulé pendant l'attente
        if buffer_son:
            ecrire_csv(chemin_son, HEADER_SON, buffer_son)
        if buffer_vib:
            ecrire_csv(chemin_vib, HEADER_VIB, buffer_vib)

        print(f"  [SESSION] id {session_id} [{session_mode}] adoptée ({raison}) — "
              f"{len(buffer_son)} samples son et {len(buffer_vib)} lignes vib "
              f"écrits depuis le tampon.")

        buffer_son = []
        buffer_vib = []
        en_attente_session = False

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
                # On mémorise l'état ACTUEL de current_session.txt : il décrit
                # la session PRÉCÉDENTE, puisque le serveur TCP n'écrira le
                # nouvel ID qu'après la réponse TRAIN/TEST de l'opérateur.
                # Toutes les trames partent en tampon jusqu'à ce que le
                # contenu du fichier change.
                if not client_actif:
                    client_actif       = True
                    en_attente_session = True
                    etat_initial       = lire_etat_brut()
                    deadline_session   = time.time() + ATTENTE_SESSION_MAX
                    derniere_verif     = 0
                    buffer_son         = []
                    buffer_vib         = []
                    compteur_paquets   = 0
                    compteur_son       = 0
                    compteur_vib       = 0
                    compteur_corrompus = 0

                    print(f"\n[DÉBUT] Capture démarrée (depuis {addr[0]})")
                    print(f"        Trames en tampon en attendant l'indexation "
                          f"TCP (réponse TRAIN/TEST sur la console du serveur)...")

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
                #  On reconstitue un timestamp individuel pour chaque sample en
                #  ajoutant i × (1000 / SR) ms au timestamp de base, puis chaque
                #  sample devient une ligne CSV (en tampon ou directement).
                # ==================================================================
                if parts[0] == 'SOUND' and len(parts) >= 3:
                    try:
                        ts_base = int(parts[1])
                    except ValueError:
                        print(f"  [!] Timestamp son invalide : {parts[1]}")
                        compteur_corrompus += 1
                        continue

                    amplitudes = parts[2:]          # Liste des N samples audio
                    dt_ms      = 1000.0 / SAMPLE_RATE_SON  # Intervalle entre deux samples (ms)

                    # Validation : chaque amplitude doit être un entier signé.
                    # Si un sample contient autre chose (ex: "-7116V" = trames
                    # fusionnées côté ESP32), on coupe la trame à cet endroit :
                    # tout ce qui suit appartient à un autre message.
                    lignes = []
                    for i, amp in enumerate(amplitudes):
                        if not amp.lstrip('-').isdigit():
                            print(f"  [!] Sample son invalide ('{amp}') — fin de trame ignorée")
                            compteur_corrompus += 1
                            break
                        lignes.append([f"{ts_base + i * dt_ms:.4f}", amp])

                    if en_attente_session:
                        buffer_son.extend(lignes)
                    else:
                        ecrire_csv(chemin_son, HEADER_SON, lignes)

                    compteur_son += len(lignes)

                # ==================================================================
                #  CAS 2 : TRAME VIBRATION
                #  Format ESP32 : "VIB,timestamp,VX,VY,VZ,ADX,ADY,ADZ,TEMP,DX,DY,DZ,HZX,HZY,HZZ"
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

                    if en_attente_session:
                        buffer_vib.append(parts[1:])
                    else:
                        ecrire_csv(chemin_vib, HEADER_VIB, [parts[1:]])

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
                    etat = "tampon" if en_attente_session else f"session {session_id}"
                    print(f"   >>> [{etat}] Son: {compteur_son} échant. "
                          f"| Vib: {compteur_vib} | Corrompus: {compteur_corrompus}", end='\r')

            except BlockingIOError:
                # Aucun paquet disponible dans la file UDP → on continue la boucle
                # pour vérifier l'état de session et le timeout de fin de capture
                pass

            # ==================================================================
            #  PHASE DE TAMPON — adoption de la session
            #  Toutes les INTERVALLE_VERIF_ETAT secondes, on relit le fichier
            #  d'état. Dès que son contenu diffère de celui du début de capture,
            #  le serveur TCP a indexé la session : on connaît le bon ID et on
            #  vide le tampon dans les bons fichiers.
            #  Si rien ne change avant deadline_session, on écrit quand même
            #  avec l'état courant (mode dégradé = comportement historique).
            # ==================================================================
            if client_actif and en_attente_session:
                maintenant = time.time()
                if maintenant - derniere_verif >= INTERVALLE_VERIF_ETAT:
                    derniere_verif = maintenant
                    contenu = lire_etat_brut()

                    if contenu is not None and contenu != etat_initial:
                        adopter_session(contenu, "serveur TCP a indexé la session")

                    elif maintenant > deadline_session:
                        print(f"  [!!] {ATTENTE_SESSION_MAX:.0f} s sans mise à jour de "
                              f"{SESSION_STATE_FILE} — écriture forcée avec l'état courant.")
                        adopter_session(contenu if contenu is not None else etat_initial,
                                        "délai d'attente dépassé")

            # ==================================================================
            #  DÉTECTION FIN DE CAPTURE
            #  Si aucun paquet n'a été reçu depuis TIMEOUT_PRESENCE secondes,
            #  on considère que l'ESP32 a arrêté d'envoyer (commande STOP ou
            #  déconnexion). Si la session n'a toujours pas été indexée
            #  (capture courte + opérateur lent), on continue d'attendre le
            #  serveur jusqu'à la deadline avant d'écrire le bilan.
            # ==================================================================
            if client_actif and (time.time() - dernier_paquet_temps > TIMEOUT_PRESENCE):

                if en_attente_session:
                    print(f"\n[ATTENTE] Fin de réception mais session pas encore "
                          f"indexée — attente du serveur TCP...")
                    while en_attente_session and time.time() <= deadline_session:
                        contenu = lire_etat_brut()
                        if contenu is not None and contenu != etat_initial:
                            adopter_session(contenu, "serveur TCP a indexé la session")
                            break
                        time.sleep(INTERVALLE_VERIF_ETAT)

                    if en_attente_session:
                        print(f"  [!!] Aucune mise à jour de {SESSION_STATE_FILE} — "
                              f"écriture forcée avec l'état courant.")
                        adopter_session(lire_etat_brut() or etat_initial,
                                        "délai d'attente dépassé")

                print(f"\n[STOP] Fin de réception.")
                print(f"       Paquets reçus     : {compteur_paquets}")
                print(f"       Son               : {compteur_son} échantillons")
                print(f"       Vibration         : {compteur_vib} lignes")
                print(f"       Corrompus/rejetés : {compteur_corrompus}")
                print(f"       Fichiers          : {chemin_son} | {chemin_vib}")

                # Estimation de la fréquence son effective
                # (chaque paquet SOUND contient ~128 samples → ~125 paquets/s attendus)
                duree_estimee = compteur_paquets / 125.0
                if compteur_son > 0 and duree_estimee > 0:
                    sr_effectif = compteur_son / duree_estimee
                    perte = 100 * (1 - sr_effectif / SAMPLE_RATE_SON)
                    print(f"       Fréq. son effective : ~{sr_effectif:.0f} Hz (perte {perte:.1f}%)")

                print("\nEn attente d'une nouvelle capture...")
                client_actif = False

            # Pause minimale pour céder la main à l'OS sans bloquer la boucle
            time.sleep(0.0001)

    except KeyboardInterrupt:
        # Arrêt propre via Ctrl+C : si une capture était en cours avec des
        # trames encore en tampon, on les écrit avant de quitter pour ne
        # rien perdre.
        if en_attente_session and (buffer_son or buffer_vib):
            print(f"\n[!] Interruption pendant la phase de tampon — "
                  f"écriture des données en attente...")
            adopter_session(lire_etat_brut() or etat_initial,
                            "interruption manuelle")

        print(f"\n[STOP] Capture terminée manuellement.")
        print(f"       Paquets reçus     : {compteur_paquets}")
        print(f"       Son               : {compteur_son} échantillons")
        print(f"       Vibration         : {compteur_vib} lignes")
        print(f"       Corrompus/rejetés : {compteur_corrompus}")
