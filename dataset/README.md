# Base de données — captures moteur

Ce dossier contient le **fichier maître** des métadonnées de capture.

## Fichiers ici

- `metadata_captures_moteur.csv` — index des sessions (id, horodatage, condition_charge, durée, fréquences, fichiers liés, niveau de tension)
- `metadata_captures_moteur_clean.csv` — version nettoyée (sessions invalides retirées) utilisée pour l'entraînement final

## Fichiers bruts (son et vibration)

Pour préserver les chemins relatifs utilisés par le pipeline d'entraînement, les fichiers bruts sont restés à leur emplacement d'origine :

```
ProjetDataSet2026_ModeleIA/dist/data/records/
├── sons/         son_N.csv
└── vibrations/   vib_N.csv
```

> **Numérotation non continue** : `N` va de 1 à 70 avec des trous. L'IHM incrémente
> l'identifiant à chaque tentative de capture ; les captures ratées ou interrompues
> (fichier incomplet, frame perdue, fausse manipulation) ont été supprimées et leur
> numéro n'a pas été réutilisé. Seules les sessions listées dans le CSV maître font
> partie du dataset. Exception : `son_15.csv` / `vib_15.csv` existent encore sur disque
> mais la session 15 est absente de l'index (capture non retenue) ; les fichiers sont
> conservés pour traçabilité.

## Conventions

- **condition_charge** : `A_vide` (sans frein, Umax = 30,3 V) ou `B_frein` (avec frein, Umax = 28,7 V).
- **niveau_tension** : pourcentage de la tension max de la condition (0 à 100), label appris par le modèle.
- **son_N.csv** : deux colonnes — Temps (ms), Amplitude (entier signé 32 bits). Fréquence nominale 16 kHz, effective ≈ 15,8 kHz après correction firmware.
- **vib_N.csv** : 14 colonnes — Timestamp, VX, VY, VZ, ADX, ADY, ADZ, TEMP, DX, DY, DZ, HZX, HZY, HZZ (cf. manuel WIT pour les unités).
