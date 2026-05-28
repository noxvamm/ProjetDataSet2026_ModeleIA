# Notice d'installation

Procédure d'installation complète sur un poste opérateur Windows.

## Prérequis matériels

- Carte **ESP32** (testée avec DevKit V1) flashable via USB.
- Microphone numérique **INMP441** (I2S).
- Capteur de vibration **WTVB01-BT50** (BLE, constructeur WIT).
- Alimentation à tension réglable pour le moteur de test.
- PC sous Windows 10/11 avec port USB et Wi-Fi.

## Prérequis logiciels

- **Python 3.11** ou supérieur — [python.org](https://www.python.org/downloads/).
- **Visual Studio Community 2026** (pour ouvrir la solution `.slnx` et éditer le code Python).
- **Arduino IDE 2.x** (pour compiler et flasher le firmware ESP32) avec le board manager `esp32` de Espressif Systems.
- **Qt Creator** (uniquement si l'on veut recompiler l'IHM ; binaire fourni autrement).

## Installation pas à pas

### 1. Récupérer le code

```bash
git clone https://github.com/noxvamm/ProjetDataSet2026_ModeleIA.git
cd ProjetDataSet2026_ModeleIA
```

### 2. Environnement Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r code/python/requirements.txt
```

### 3. Configuration du firmware ESP32

Ouvrir `code/firmware_esp32/firmware_esp32_corrige.ino` dans Arduino IDE et remplacer :

```c
const char* ssid     = "<VOTRE_SSID_WIFI>";
const char* password = "<VOTRE_MOT_DE_PASSE>";
```

par votre réseau Wi-Fi. **Ne pas committer ces modifications.**

Bibliothèques requises (à installer via le gestionnaire Arduino) : `WiFi`, `BLEDevice`, `driver/i2s.h` (inclus avec le board ESP32).

Sélectionner la carte « ESP32 Dev Module », régler la vitesse du port série à 115 200 bauds, puis téléverser.

### 4. Configuration réseau

Le PC opérateur et l'ESP32 doivent être sur le **même réseau Wi-Fi** (typiquement un partage de connexion smartphone). Les ports utilisés :

- **TCP 9090** : métadonnées de session (IHM → serveur Python).
- **UDP 9091** : flux de données capteurs (ESP32 → client Python).

Ouvrir ces ports si un pare-feu est actif.

### 5. Lancer les serveurs

Depuis le dossier `ProjetDataSet2026_ModeleIA/` (où se trouvent les `.py`) :

```bash
python serveurTCP_metadonnes_moteur.py     # fenêtre 1
python clientUDP_données.py                # fenêtre 2
```

### 6. Lancer l'IHM Qt

Exécuter l'application compilée (à fournir par Hugo / Ege).

### 7. (Optionnel) Compiler les serveurs en exécutables autonomes

```bash
pip install pyinstaller
pyinstaller --onefile serveurTCP_metadonnes_moteur.py
pyinstaller --onefile clientUDP_données.py
```

Les exécutables sont générés dans `dist/`.

## Vérification

L'installation est considérée comme correcte lorsque :

1. L'ESP32 se connecte au Wi-Fi (LED interne stable + log série « WiFi connecté »).
2. Les deux serveurs Python tournent sans erreur.
3. Un déclenchement de capture depuis l'IHM produit un nouveau couple `son_N.csv` / `vib_N.csv` dans `dist/data/records/`.

En cas de problème, consulter le journal de bord dans `documentation_technique/`.
