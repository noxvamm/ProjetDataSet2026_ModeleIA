# Mémoire de travail — Noa / Projet BTS 2026

> Fichier lu automatiquement par Claude. Sert de contexte permanent pour ne pas avoir à tout réexpliquer à chaque session.

## Personne

- **Noa Orand** — étudiante BTS CIEL option Informatique & Réseaux, promotion 2026.
- Email : noaorand95@gmail.com
- Outil de dev principal : **Visual Studio Community 2026**.

## Projet de BTS — `ProjetDataSet2026_ModeleIA`

**Objectif** : estimer le **niveau de tension appliqué au moteur électrique** (en % du max de la condition de charge) à partir des signaux son + vibration. Régression, pas classification.

> **Pivot historique** : le projet visait initialement la détection d'usure d'outil sur machine CNC. Périmètre réduit à un banc moteur électrique pour des raisons d'accès matériel (à mentionner à l'oral E6 comme une décision d'ingénierie reproductible).

### Banc d'essai

- **Source** : moteur électrique alimenté par alimentation à tension réglable.
- **Acquisition** : ESP32 (firmware existant — 16 kHz son réel, mutex FreeRTOS, format SOUND/VIB).
- **Pipeline logiciel** : client UDP Python (port 9091) + serveur TCP Python (port 9090) + IHM Qt + modèle IA Keras — toute la chaîne fonctionnelle.

### Capteurs

- **Microphone I2S** — son du moteur, échantillonnage **16 kHz** théorique. SR effective mesurée : **10,7 kHz** après correction du bug `String +=` du firmware ESP32 (5 mai 2026). Contenu utile sous 1 kHz → 10,7 kHz est largement suffisant pour ce projet (Nyquist = 5,4 kHz).
- **WTVB01-BT50** — capteur de vibration BLE, **50 Hz** déclaré (en pratique limité à ~10 Hz à cause du conflit radio BLE/WiFi sur l'ESP32 — non bloquant mais à mentionner).
  - ⚠️ **VX et VY bloqués à 271 et 1** dans notre configuration → axes perpendiculaires à la vibration dominante du moteur, valeurs = bruit MEMS sous seuil. Le manuel WIT confirme que la trame est correctement parsée (28 octets, ordre VX VY VZ ADX ADY ADZ TEMP DX DY DZ HZX HZY HZZ).
  - **Décision Option A (6 mai 2026)** : on n'utilise que `|VZ|` comme signal vibration, pas la magnitude 3-axes. Raison : la magnitude `√(VX²+VY²+VZ²)` aurait un plancher de ~271 (= √(271²+1²)) qui écrase la dynamique basse de VZ. Avec `|VZ|` seul on récupère la vraie variation. Implémentation dans `arch4_double_branche.py` (l'ancienne ligne est conservée en commentaire pour réversibilité). **Argument oral E6** : décision d'ingénierie justifiée par analyse statistique + manuel constructeur, pas un défaut hardware ignoré.

### Conditions de charge (2 retenues — la 3ᵉ avec frein + poids a été abandonnée pour reproductibilité)

| Condition | Tension max mesurée |
|---|---|
| **A — sans frein (à vide)** | 30,3 V |
| **B — avec frein** | 28,7 V |

### Label IA — `niveau_tension`

- Le label est le **niveau de tension** (et **pas** le niveau de puissance — le calcul P=U×I demanderait aussi le courant, hors matériel).
- La tension reste une fonction monotone de la puissance pour une charge fixée → c'est un **proxy de la puissance** suffisant pour l'apprentissage.
- Approche **relative par condition** : chaque condition a son propre 100 %.
  - `voltage_cible = pourcentage × (voltage_max_condition / 100)`
- À normaliser pour le réseau : `y / 100.0`.
- ⚠️ **Renommage à propager partout** : `niveau_puissance` → `niveau_tension` (CSV, serveur TCP, IHM Qt, code IA).

### Plan d'expérience

**11 niveaux × 2 conditions × 5 captures de 15 s = 110 sessions** (~1h50 de banc moteur, à faire en deux phases A puis B avec pause + vérif dataset entre les deux).

Aide-mémoire des voltages cibles (par pas de 10 %) à imprimer et poser près de l'alim :

| % | Sans frein (30,3 V) | Avec frein (28,7 V) |
|---|---|---|
| 0  | 0,0 | 0,0 |
| 10 | 3,0 | 2,9 |
| 20 | 6,1 | 5,7 |
| 30 | 9,1 | 8,6 |
| 40 | 12,1 | 11,5 |
| 50 | 15,2 | 14,4 |
| 60 | 18,2 | 17,2 |
| 70 | 21,2 | 20,1 |
| 80 | 24,2 | 23,0 |
| 90 | 27,3 | 25,8 |
| 100 | 30,3 | 28,7 |

### Format CSV cible (`metadata_captures_moteur.csv`)

```
id_session, time_session, duree, frequence_echantillonnage,
voltage_v,            # mesuré au multimètre (ex: 15.2)
niveau_tension,       # label IA en % [0, 100]
condition_charge,     # 'A_vide' ou 'B_frein'
fichier_son, fichier_vibration
```

> **Point en suspens** : décider si `voltage_v` est la consigne de l'alim ou la mesure réelle multimètre. Préférence = mesure réelle.

### Architecture (chaîne de traitement)

```
Capteurs (son 16 kHz + vibration 50 Hz)
    ↓
ESP32 (SOUND / VIB)
    ↓
clientUDP_données.py (port 9091) + serveurTCP_metadonnes_moteur.py (port 9090)
    ↓
IHM Qt (côté étudiant IHM)
    ↓
metadata_captures_moteur.csv + son_*.csv + vib_*.csv
    ↓
Modèle IA double branche : arch4_double_branche.py
    Branche 1 : CNN sur mel-spectrogramme du son
    Branche 2 : CNN sur mel-spectrogramme de la magnitude vibratoire √(VX²+VY²+VZ²)
    Fusion par concaténation → Dense → sortie régression (sigmoid ×100 ou linéaire), loss=mse, métrique=mae
```

### Dossier projet

`C:\Users\noaor\OneDrive\Bureau\Projet BTS 2026\ProjetDataSet2026_ModeleIA`

### Fichiers clés

- `serveurTCP_metadonnes_moteur.py` — serveur TCP, réception des données IHM.
- `arch4_double_branche.py` — modèle IA double branche (mel-spectrogrammes).
- `ProjetDataSet2026_ModeleIA.slnx` — solution Visual Studio.
- `commande_compil_python_exe.txt` — commandes de compilation Python → exécutable.
- `TASKS.md` — liste de tâches active.

## Équipe projet (4 membres)

- **Noa Orand** — IA (arch4 double branche) + pipeline d'acquisition (serveur TCP + client UDP + formats CSV).
- **Hugo Cypré** — hugocypre@gmail.com — dev IHM Qt / réseau.
- **Mederick** — membre équipe.
- **Ege** — membre équipe.

## Révisions BTS — Notion

- Base : **"Fiches de révision BTS CIEL"** — 42 fiches.
- URL : https://app.notion.com/p/c9a8da01dbdf41ac9b64d13742119c41
- Propriétés : `Statut` (À faire / En cours / Maîtrisé / À revoir), `Importance` (Critique / Important / Secondaire), `Matière`, `Épreuve` (E1 à E6), `Tags`.
- Fiche déjà rédigée : **"Adressage IP (IPv4, masques, sous-réseaux)"**.
- Vue filtrée à créer côté Notion : *"Critique non maîtrisée"* (Importance = Critique ET Statut ≠ Maîtrisé) — pour que Claude attaque la bonne fiche en priorité chaque matin.

## Épreuves BTS CIEL (rappel)

- **E1** Culture générale
- **E2** Anglais
- **E3** Maths / Sciences physiques
- **E4** CEJM
- **E5** Cybersécurité, Réseaux, Systèmes (matière forte du projet)
- **E6** Pratique professionnelle (oral du projet)

## Conventions de travail

- Réponses en français, ton naturel et concis.
- Pas de blabla d'introduction dans les briefs — direct au but.
- Pas de conseil d'investissement / financier (Noa est étudiante, pas demandeuse de conseils boursiers).
- Quand un sujet de cybersécurité touche un point du programme (cryptographie, pare-feu, vulnérabilités web, IoT/embedded, IA & sécurité, RGPD/NIS2/DORA), le signaler — utile pour l'oral E6.

## Mise à jour automatique de TASKS.md

Quand on termine une tâche ensemble dans une session (un bug fixé, un fichier compilé, une fiche de révision rédigée, un commit fait, etc.), Claude **met à jour `TASKS.md` immédiatement** sans attendre qu'on lui demande :

1. Repère la ligne correspondante dans `TASKS.md` (sections *En cours*, *À faire — Bloquants*, *À faire — Code & qualité*, etc.).
2. Coche la case `[ ]` → `[x]`.
3. Déplace la ligne dans la section **Fait récemment** en haut.
4. Si pertinent, ajoute une nouvelle tâche de suivi (ex : "tester en condition réelle").

Cette mise à jour est silencieuse — pas besoin d'annoncer "j'ai mis à jour TASKS.md", c'est juste fait. Si la tâche n'existait pas encore dans `TASKS.md`, l'ajouter directement dans **Fait récemment** avec une date approximative.

Pareil pour les nouvelles tâches qui émergent en cours de discussion : Claude les ajoute dans la bonne section sans attendre.

## Tâche planifiée active

- **`brief-matinal-noa`** — brief quotidien automatique : avancement projet (TASKS.md + Notion), 3-5 actus cybersécurité, état des marchés financiers.

## Rapport BTS — Dossier de projet 2026

**Échéances** :
- **22 mai 2026 à 15 h** : dépôt PDF sur Elea (1 seul fichier par équipe).
- **29 mai 2026 à 17 h** : version papier reliée à remettre au professeur (1 exemplaire).

**Plan imposé** :
1. Introduction (collective)
2. Mise en situation : présentation du projet, analyse (collective)
3. Partie physique (collective)
4. Développements unitaires (validés/non validés) + intégration validée — **partie individuelle**, 3 ou 4 sections selon taille équipe
5. Conclusion (collective)

**Annexes en ligne** (lien dans le PDF) :
- Codes source + base de données
- Fiches de recette unitaires + fiches de recette d'intégration
- Documentations (notice d'installation, notice d'utilisation)

## Pause projet — où on en est techniquement (à reprendre après rapport)

État au 18 mai 2026 — campagne 110 captures **non démarrée**. Avant de la lancer, points à trancher :
1. **Son** : ✅ SR effective remontée à **15 804 Hz** (99 % de la cible 16 kHz) après firmware corrigé (snprintf, APLL, dma_buf×8).
2. **Test "moteur off" du 18 mai** ambigu : `niveau_tension = 30` dans le CSV alors que "moteur ne tourne pas" → savoir si l'alim était débranchée du secteur ou juste à 0/30 %. À refaire avec alim physiquement débranchée pour avoir une vraie référence "silence".
3. **Signal son moteur OFF a la même RMS que moteur 50 %** (~8 800) avec énergie massivement concentrée sous 50 Hz → pickup électromagnétique probable. Ajouter un filtre passe-haut 50 Hz côté preprocessing IA.
4. **Vibration VZ : step de 256 dans les valeurs** (8738, 8994, 9250…) → l'octet bas VZL est bloqué à `0x22`, on n'a que 8 bits utiles de dynamique. Confirmer si c'est limitation capteur ou parsing.
5. **VZ moteur off (10 619) > VZ moteur 50 % (3 499)** → bizarre, à creuser. Soit vibration ambiante, soit comportement capteur dépendant de l'état moteur.
6. **Option A déjà appliquée** dans `arch4` : magnitude vibration = `|VZ|` (au lieu de √3-axes).
7. **À faire post-rapport** : refaire le test moteur réellement off, ajouter passe-haut 50 Hz, puis lancer Phase A des 110 captures.
