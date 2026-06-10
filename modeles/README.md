# Modèles entraînés

Copies des fichiers `.keras` produits par `arch4_double_branche.py` (les originaux restent dans le dossier Visual Studio `ProjetDataSet2026_ModeleIA/`).

- `modele_arch4_double_branche.keras` — modèle final entraîné (architecture double branche son + vibration).
- `modele_arch4_best.keras` — meilleur checkpoint pendant l'entraînement (selon val_mae).

Pour réutiliser :
```python
import tensorflow as tf
model = tf.keras.models.load_model('modele_arch4_double_branche.keras')
```

Voir `code/python/predire_tension.py` pour un exemple d'inférence sur une capture réelle.
