# Projet BTS CIEL 2026 — Estimation du niveau de tension d'un moteur par IA

Dépôt des annexes techniques du dossier de projet de **BTS Cybersécurité, Informatique et Réseaux, Électronique** (CIEL) — option Informatique et Réseaux, session 2026.

## Sujet

Estimer, par apprentissage profond, le **niveau de tension** appliqué à un moteur électrique (en % de la tension maximale d'une condition de charge donnée), à partir de deux signaux physiques :

- Son acoustique du moteur, capté par un microphone I2S à 16 kHz.
- Vibration mécanique du moteur, captée par un module BLE 3 axes (WTVB01-BT50).

Le pipeline complet va du capteur jusqu'au modèle convolutif à double branche, en passant par l'acquisition réseau (UDP/TCP), le stockage CSV et l'entraînement supervisé.

## Équipe

- **Noa Orand** — pipeline d'acquisition logicielle (serveur TCP métadonnées, client UDP données) + modèle IA double branche.
- **Hugo Cypré** — qualité des données, optimisation et versionnage des modèles.
- **Mederick Mopty** — firmware embarqué ESP32, capture audio I2S, communication réseau.
- **Ege Yildirim** — IHM Qt (saisie opérateur, supervision des enregistrements, génération du CSV).

## Structure du dépôt

```
ProjetDataSet2026_ModeleIA/
├── README.md                        ← ce fichier
├── docs/
│   ├── AIDE_MEMOIRE_VOLTAGES.md     tableau des tensions cibles
│   ├── notice_installation.md
│   ├── notice_utilisation.md
│   ├── plan_experience.md
│   └── rapport/                     PDF / DOCX du dossier de projet
├── code/
│   ├── python/                      serveurs, modèle, inférence (requirements + README)
│   └── firmware_esp32/              firmware Arduino IDE
├── modeles/                         modèles .keras entraînés
├── dataset/                         fichier maître + conventions (raw CSV dans dist/data)
├── fiches_recette/
│   ├── unitaires/                   U1 à U5
│   └── integration/                 fiches d'intégration par membre
├── diagrammes/                      séquence, déploiement (PNG)
├── documentation_technique/         figures d'analyse, schémas, datasheets
└── ProjetDataSet2026_ModeleIA/      solution Visual Studio (code Python + dist/data)
```

## Démarrage rapide

Installation : voir [docs/notice_installation.md](docs/notice_installation.md).

Utilisation côté opérateur : voir [docs/notice_utilisation.md](docs/notice_utilisation.md).

Exemple d'inférence sur une capture réelle :

```bash
cd ProjetDataSet2026_ModeleIA/
python predire_tension.py --id 47 --condition A_vide
```

## Annexes exigées par le rapport

| Annexe | Emplacement |
|---|---|
| Code source Python (serveurs, modèle, inférence) | `code/python/` (pointeurs) + `ProjetDataSet2026_ModeleIA/*.py` |
| Firmware ESP32 | `code/firmware_esp32/` |
| Modèles entraînés (.keras) | `modeles/` |
| Base de données (CSV maître + son/vib) | `dataset/` (maître) + `ProjetDataSet2026_ModeleIA/dist/data/records/` (bruts) |
| Fiches de recette unitaires | `fiches_recette/unitaires/` (U1 à U5) |
| Fiches de recette d'intégration | `fiches_recette/integration/` |
| Diagrammes UML et de déploiement | `diagrammes/` |
| Notice d'installation | `docs/notice_installation.md` |
| Notice d'utilisation | `docs/notice_utilisation.md` |
| Plan d'expérience | `docs/plan_experience.md` |
| Documentation technique complémentaire | `documentation_technique/` |

## Sécurité et hygiène du dépôt

- Aucun identifiant (SSID / mot de passe Wi-Fi) ne doit être committé. Le firmware utilise des placeholders `<VOTRE_SSID_WIFI>` et `<VOTRE_MOT_DE_PASSE>` à remplacer **localement avant flash** et jamais dans un commit.
- Le `.gitignore` exclut les fichiers de travail internes et les caches éditeur.

## Licence

Projet pédagogique BTS CIEL — session 2026. Utilisation libre dans un cadre éducatif, avec mention de l'équipe.
