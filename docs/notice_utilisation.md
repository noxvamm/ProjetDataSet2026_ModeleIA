# Notice d'utilisation

Procédure complète, du démarrage du banc moteur jusqu'à la lecture d'une prédiction du modèle.

## 1. Préparation du banc

1. Brancher l'ESP32 sur le secteur via USB (ou batterie).
2. Brancher le microphone INMP441 (broches SCK = GPIO 14, WS = GPIO 25, SD = GPIO 32, VCC 3,3 V, GND).
3. Allumer le capteur de vibration WTVB01-BT50 (bouton latéral).
4. Connecter le moteur à l'alimentation à tension réglable, **alimentation à 0 V** au départ.
5. Démarrer le partage de connexion Wi-Fi du téléphone opérateur.
6. Sur le PC : vérifier la connexion au même Wi-Fi.

## 2. Démarrage logiciel

1. Lancer les deux serveurs Python (voir notice d'installation).
2. Lancer l'IHM Qt (`DataSet2026.exe` ou équivalent).
3. Attendre que l'IHM affiche « ESP32 connecté ».

## 3. Réalisation d'une capture

1. Dans l'IHM, sélectionner :
   - **Condition de charge** : `A_vide` (sans frein) ou `B_frein` (avec frein).
   - **Niveau de tension cible** en pourcentage (0 à 100, par pas de 10).
   - **Durée** : 15 secondes par défaut.
2. Régler l'alimentation à la tension correspondante (voir `docs/AIDE_MEMOIRE_VOLTAGES.md`).
3. Attendre 5 secondes que le moteur se stabilise.
4. Cliquer **Démarrer** dans l'IHM.
5. Pendant la capture (15 s), ne pas toucher au banc.
6. La capture s'arrête automatiquement à la fin du décompte. Les fichiers `son_N.csv` et `vib_N.csv` apparaissent dans `dist/data/records/`, et une nouvelle ligne s'ajoute à `metadata_captures_moteur.csv`.

## 4. Plan d'expérience complet

Réaliser **5 captures** par couple (condition, niveau). Voir `docs/plan_experience.md`. Au total : 11 niveaux × 2 conditions × 5 répétitions = **110 sessions**.

## 5. Entraînement du modèle

Après acquisition, lancer l'entraînement depuis le dossier des scripts Python :

```bash
python arch4_double_branche.py
```

L'entraînement produit deux fichiers `.keras` (checkpoint et modèle final) et un graphique `resultats_modele.png`.

## 6. Prédiction sur une nouvelle capture

```bash
python predire_tension.py --id 47 --condition A_vide
```

Le script affiche :

```
=== RÉSULTAT ===
  Capture        : son_47.csv + vib_47.csv
  Fenêtres son   : 29
  Tension prédite : 12.3 %
  → soit ~3.7 V (condition A_vide, max 30.3 V)
```

Pour un fichier hors index :

```bash
python predire_tension.py son_47.csv vib_47.csv --condition A_vide --reel 10
```

## 7. Arrêt

1. Couper l'alimentation moteur (ramener à 0 V).
2. Fermer l'IHM puis les fenêtres serveur Python.
3. Couper l'ESP32 et le capteur de vibration.
