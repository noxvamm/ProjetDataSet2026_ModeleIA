# Tâches — Projet BTS 2026

> Liste vivante. Claude la lit chaque matin et la met à jour quand une tâche est terminée.

## En cours

- [ ] **[Projet]** Faire tourner `arch4_double_branche.py` de bout en bout — bloqué tant que `metadata_captures_moteur.csv` est vide et que les bugs IA listés ci-dessous ne sont pas corrigés.

## À faire — Bloquants

- [ ] **[Projet]** **Ajouter `voltage_v` au CSV** (mesure multimètre par session) — nécessite que l'IHM Qt envoie un 6ᵉ champ. À coordonner avec l'étudiant IHM.
- [x] **[Projet]** ~~Bug IA — `SR = 50` faux pour le son~~ : déjà ok dans le code actuel, SR son et vib lus séparément depuis le CSV.
- [x] **[Projet]** ~~Bug IA — pas de normalisation des spectrogrammes mel~~ : déjà fait, `normaliser()` appliqué aux deux branches.
- [x] **[Projet]** ~~Bug IA — label non normalisé~~ : déjà fait, `niveau_tension / 100.0` ligne 90.
- [ ] **[Projet]** **Réindexer les sessions 2 à 7 dans `metadata_captures_moteur.csv`** (le fichier ne contient que le header). Soit rejouer chaque capture via l'IHM, soit reconstruire le CSV à la main à partir des fichiers `son_*.csv` et `vib_*.csv` présents dans `dist/data/records/`.
- [ ] **[Projet]** **Sessions 4 et 5** : son présent mais vibration absente. Décider — soit rerejouer la capture pour récupérer les `vib_4.csv` / `vib_5.csv`, soit exclure ces deux sessions du dataset.
- [ ] **[Projet]** **Corriger `commande_compil_python_exe.txt`** : la commande référence `serveurUDP_vibration.py` qui a été supprimé. Remplacer par `serveurTCP_metadonnes_moteur.py` et `clientUDP_données.py`.
- [ ] **[Projet]** **Lancer les 110 sessions** du nouveau plan d'expérience : 11 niveaux × 2 conditions × 5 captures de 15 s. Phase A (sans frein, 55 captures, ~50 min) puis pause + vérif dataset, puis Phase B (avec frein, 55 captures, ~50 min).

## À faire — Avant les 110 captures

- [ ] **[Projet]** **Tester la chaîne complète sur 1 capture témoin** avant de lancer la campagne — éviter de découvrir un bug à la session 47.
- [ ] **[Projet]** **Imprimer l'aide-mémoire des voltages cibles** (tableau dans CLAUDE.md) et le poser près de l'alim.
- [ ] **[Projet]** **Décider** : enregistrer dans `voltage_v` la consigne de l'alim ou la mesure réelle au multimètre ? (mesure réelle préférable).
- [ ] **[Projet]** **Surveiller la dérive thermique du moteur** sur ~2 h de captures : pause régulière + contrôle température.
- [ ] **[Projet]** **Confirmer côté firmware ESP32** que le `abs()` qui dénaturait le signal son a bien été retiré (à vérifier avec l'équipe ESP32).

## À faire — Code IA & qualité

- [ ] **[Projet]** **Ajouter callbacks Keras** dans `arch4_double_branche.py` : `EarlyStopping`, `ReduceLROnPlateau`, `ModelCheckpoint`.
- [ ] **[Projet]** **Ajouter évaluation finale + visualisation** : scatter prédictions vs réel, courbes `loss` / `val_loss`, MAE en points de %.
- [ ] **[Projet]** **Comparer aux 3 autres archis** (CNN simple `arch1`, CNN+BatchNorm+Dropout `arch2`, Transfer Learning `arch3`) sur le même dataset moteur — pour justifier le choix de la double branche à l'oral.
- [ ] **[Projet]** **Ajouter le préprocessing dans `arch4_double_branche.py`** : retrait DC offset + normalisation amplitude. Le code est déjà écrit dans `ProjetDataSet2026_ModeleIA.py` (fonction `preprocess_signal`), à reporter.
- [x] **[Projet]** ~~Ajouter la data augmentation par bruit gaussien dans `arch4`~~ : fait (5 mai). Inclus aussi time shift et SpecAugment.
- [ ] **[Projet]** Gérer proprement le cas "fichier son ou vib manquant pour une ligne du CSV" — actuellement le `try/except` capture l'erreur mais sans log clair.
- [ ] **[Projet]** Clarifier les chemins de données : il y a deux dossiers `data/` (un à la racine du projet, un dans `dist/data/`). Choisir lequel fait foi et virer l'autre.
- [ ] **[Projet]** **Décider du sort de `ProjetDataSet2026_ModeleIA.py`** (ancien scope "analyse d'usure d'outil CNC"). Soit le supprimer, soit le déplacer dans un dossier `archives/`.
- [ ] **[Projet]** Idem pour `serveurTCP_metadonnes.py` (ancienne version 8 champs CNC) — à supprimer si plus utile.

## À faire — Compilation & livraison

- [ ] **[Projet]** **Compiler `serveurTCP_metadonnes_moteur.py` en .exe** avec PyInstaller (`python -m PyInstaller --onefile`).
- [ ] **[Projet]** **Compiler `clientUDP_données.py` en .exe** avec PyInstaller.
- [ ] **[Projet]** Tester les deux .exe sur une machine sans Python installé pour valider la portabilité.

## À faire — Git & versionning

- [ ] **[Projet]** **Faire un commit propre** : actuellement plein de fichiers modifiés/ajoutés non commités (`arch4_double_branche.py`, `serveurTCP_metadonnes_moteur.py`, `clientUDP_données.py`, suppressions de l'ancien `serveurUDP_vibration.py`, etc.).
- [ ] **[Projet]** Nettoyer le `.gitignore` : actuellement les dossiers `build/` et `dist/` sont versionnés (ce sont des artefacts PyInstaller, pas du code source).

## À faire — Documentation & oral E6

- [ ] **[Doc]** **Rédiger un README.md** à la racine du projet : objectif, architecture, dépendances, comment lancer chaque maillon (serveur TCP, client UDP, modèle IA).
- [ ] **[Doc]** **Schéma d'architecture** propre (capteurs → IHM Qt → TCP/UDP → CSV → IA) — à intégrer dans le dossier oral E6.
- [ ] **[E6]** Préparer le support de la **présentation orale du projet** (la fiche Notion existe : "Présentation orale du projet (E6)").
- [ ] **[E6]** Documenter le choix de l'archi double branche vs archis précédentes (arch1 → arch2 → arch3 → arch4) — utile pour justifier les décisions à l'oral.
- [ ] **[E6]** Préparer l'**argumentaire scientifique** pour la soutenance :
  - Pivot CNC → moteur (protocole reproductible, méthodo alignée datasets de référence MIMII / CWRU / MAFAULDA).
  - Régression vs classification (info plus riche, transitions douces, MAE interprétable).
  - Niveau de tension comme proxy de puissance (honnêteté scientifique, extension future avec mesure du courant).
  - Approche relative par condition (le modèle généralise à travers les charges).
  - Architecture double branche (respect de la nature physique distincte son/vibration).

## En attente (Waiting On)

- [ ] **Étudiant IHM** : confirmer que l'IHM Qt envoie bien le bon format CSV (4 champs : `duree, frequence_son, frequence_vibration, niveau_puissance`) au serveur TCP, et le marqueur `START`.
- [ ] **Hugo Cypré** : à voir avec lui si la couche réseau a évolué côté ESP32 / IHM.

## Idées / Backlog

- [ ] Tester d'autres représentations que le mel-spectrogramme (CWT, MFCC) sur la branche son.
- [ ] Ajouter une métrique métier sur la sortie : RMSE en % de puissance, pas juste MSE/MAE normalisés.
- [ ] Sauvegarder dans un log les warnings de fréquence effective vs déclarée (au lieu de juste les afficher en console).
- [ ] Visualiser quelques mel-spectrogrammes typiques (faible puissance, mi-puissance, forte puissance) pour vérifier que l'IA a bien matière à différencier.
- [ ] Étudier la robustesse du modèle au bruit ambiant (banc moteur dans environnement bruité vs silencieux).

## Révisions BTS — focus

- [ ] **[Révisions]** Rédiger fiche **"Cryptographie symétrique et asymétrique"** (Critique E5, lié au projet : chiffrement potentiel des trames TCP).
- [ ] **[Révisions]** Vérifier statut des autres fiches Critique non maîtrisées sur Notion (créer la vue filtrée côté Notion en priorité).

## Fait récemment

- [x] **[Projet]** **Firmware ESP32 corrigé** (5 mai 2026) — fichier `firmware_esp32_corrige.ino` à la racine du projet :
  - Son : remplacement `String +=` → `snprintf` dans buffer fixe O(n) au lieu d'O(n²) → bottleneck SR son levé.
  - BLE : `setMTU(247)` (au lieu de 64) pour recevoir la trame WIT en 1 chunk.
  - BLE : validation du header `0x55 0x61` avant parsing + garde-fou anti-buffer infini.
  - I2S : `use_apll = true` + `dma_buf_count = 8` pour stabilité d'horloge et marge anti-overflow.
  - Flag `DEBUG_DUMP_VIB_HEX` pour debug du parsing capteur.
  - **À tester** : reflasher l'ESP32 puis relancer une capture 50 % avec frein et vérifier (1) SR son ≈ 16 kHz (2) VX/VY plus constants à 271/1.
- [x] **[Projet]** **Refonte `arch4_double_branche.py`** (5 mai 2026) : window slicing 1 s × 50 % overlap, augmentation bruit gaussien + time shift + SpecAugment (×3 sur train, rien sur test), mel vibration adapté basse-fréquence (n_fft=128, hop=32), split par capture (anti-leakage), MAE par capture comme métrique principale, chemins relatifs au script, sortie renommée "tension".
- [x] **[Projet]** **Renommage `niveau_puissance` → `niveau_tension`** propagé dans `serveurTCP_metadonnes_moteur.py`, `arch4_double_branche.py` et le header `metadata_captures_moteur.csv`. (5 mai 2026)
- [x] **[Projet]** **Serveur TCP : passage à 5 champs IHM** — ajout de `condition_charge` (1ᵉʳ champ envoyé par l'IHM). Mapping `Aucune`/`A_vide`/`sans frein` → `A_vide` et `frein`/`avec frein`/`B_frein` → `B_frein` ajouté dans `normaliser_condition()`. Header CSV passé à 9 colonnes. (5 mai 2026)
- [x] **[Projet]** Migration du scope "analyse d'usure outil CNC" → "estimation de puissance moteur" (commit `80c191d` — "modif architecture").
- [x] **[Projet]** Mise en place de l'archi 4 (double branche son + vibration) avec fusion par concaténation des features.
- [x] **[Projet]** Ajout d'une vérification fréquence effective vs fréquence déclarée (warning si écart > 5 %).
- [x] **[Projet]** Renforcement du `clientUDP_données.py` : buffer UDP 2 MB, rejet strict des trames VIB fusionnées (15 champs attendus), tracé de qualité réception.
- [x] **[Révisions]** Fiche **"Adressage IP (IPv4, masques, sous-réseaux)"** rédigée dans Notion.

---

**Conventions**
- `[Projet]`, `[Révisions]`, `[Doc]`, `[E6]`, `[Admin]` en préfixe pour s'y retrouver.
- Date d'échéance entre parenthèses si pertinent : `(d'ici vendredi)`.
- Quand une tâche bascule en "Waiting On", noter qui on attend.
- **Claude met à jour cette liste automatiquement** quand on termine une tâche ensemble : il la déplace de "En cours" / "À faire" vers "Fait récemment".
