# Code Python

Le code Python (serveurs, modèle IA, inférence) se trouve historiquement dans le dossier Visual Studio :

```
ProjetDataSet2026_ModeleIA/
├── serveurTCP_metadonnes_moteur.py   # serveur TCP métadonnées, port 9090
├── clientUDP_données.py              # client UDP données capteurs, port 9091
├── arch4_double_branche.py           # entraînement modèle double branche
├── predire_tension.py                # inférence sur une capture
└── dist/data/                        # dataset (voir dataset/README.md)
```

Installation des dépendances :
```bash
pip install -r ../../code/python/requirements.txt
```
