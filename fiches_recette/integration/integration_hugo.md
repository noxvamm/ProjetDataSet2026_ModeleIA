Chaîne d'acquisition logicielle complète + modèle IA : ESP32 (firmware corrigé) → clientUDP_données.py (port 9091) + serveurTCP_metadonnes_moteur.py (port 9090, métadonnées IHM Qt) → fichiers son_N.csv / vib_N.csv + index metadata_captures_moteur.csv → entraînement arch4_double_branche.py → inférence predire_tension.py.

Scénario d'intégration

Démarrage du serveur TCP de métadonnées.

Démarrage du client UDP de réception.

Saisie d'une session via l'IHM Qt et lancement de la capture.

Réception et écriture des fichiers son_N.csv et vib_N.csv.

Inférence du modèle sur la capture obtenue.

Critères d'acceptation

Chaque session validée produit un triplet cohérent : ligne dans le CSV maître + son_N.csv + vib_N.csv avec le même identifiant.

Fréquence d'échantillonnage son effective ≥ 95 % de la cible 16 kHz (mesurée ≈ 15,8 kHz après correction du firmware).

Le modèle entraîné sur le dataset atteint une MAE ≤ 15 points de % sur les captures de test (jamais vues à l'entraînement).

L'inférence predire_tension.py s'exécute sur une capture réelle et renvoie une estimation en %.

Résultat

Campagne d'acquisition du 21 mai 2026 : 59 sessions indexées (30 à vide / A_vide, 29 avec frein / B_frein), 11 niveaux de tension couverts (0 → 100 %). Les 59 lignes du CSV maître ont leur fichier son et vibration présents ; 57 sessions retenues après nettoyage pour l'entraînement.

Entraînement arch4_double_branche.py (30 epochs, split par capture anti-fuite, augmentation ×3 sur train uniquement) : MAE = 11,2 points de % sur les captures de test — cf. resultats_modele.png (courbes de loss + scatter prédictions vs réalité).

Modèles sauvegardés : modele_arch4_double_branche.keras et modele_arch4_best.keras (checkpoint val_mae).

Exécutables PyInstaller (serveurTCP_metadonnes_moteur.exe, clientUDP_données.exe) compilés et testés sur une capture témoin le 29 mai 2026.

Verdict

☑ Validé ☐ Non validé
