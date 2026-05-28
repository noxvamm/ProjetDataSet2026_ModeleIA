# Modèles entraînés

Liens symboliques vers les fichiers `.keras` produits par `arch4_double_branche.py`.

- `modele_arch4_double_branche.keras` — modèle final entraîné (architecture double branche son + vibration).
- `modele_arch4_best.keras` — meilleur checkpoint pendant l'entraînement (selon val_mae).

Pour réutiliser :
```python
import tensorflow as tf
model = tf.keras.models.load_model('modele_arch4_double_branche.keras')
```

Voir `code/python/predire_tension.py` pour un exemple d'inférence sur une capture réelle.
