# Base de données — captures moteur

Ce dossier contient le **fichier maître** des métadonnées de capture.

## Fichiers ici

- `metadata_captures_moteur.csv` — index des sessions (id, horodatage, condition_charge, durée, fréquences, fichiers liés, niveau de tension)
- `metadata_captures_moteur_clean.csv` — version nettoyée (sessions invalides retirées) utilisée pour l'entraînement final

## Fichiers bruts (son et vibration)

Pour préserver les chemins relatifs utilisés par le pipeline d'entraînement, les fichiers bruts sont restés à leur emplacement d'origine :

```
ProjetDataSet2026_ModeleIA/dist/data/records/
├── sons/         son_1.csv … son_70.csv
└── vibrations/   vib_1.csv … vib_70.csv
```

## Conventions

- **condition_charge** : `A_vide` (sans frein, Umax = 30,3 V) ou `B_frein` (avec frein, Umax = 28,7 V).
- **niveau_tension** : pourcentage de la tension max de la condition (0 à 100), label appris par le modèle.
- **son_N.csv** : deux colonnes — Temps (ms), Amplitude (entier signé 32 bits). Fréquence nominale 16 kHz, effective ≈ 15,8 kHz après correction firmware.
- **vib_N.csv** : 14 colonnes — Timestamp, VX, VY, VZ, ADX, ADY, ADZ, TEMP, DX, DY, DZ, HZX, HZY, HZZ (cf. manuel WIT pour les unités).
