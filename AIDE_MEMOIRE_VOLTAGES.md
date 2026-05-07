# Aide-mémoire — Plan de captures moteur

> À imprimer et coller à côté de l'alim. Une feuille par condition.

---

## Phase A — Sans frein (à vide) — Vmax = **30,30 V**

| Niveau | Tension cible (V) | Capture 1 | Capture 2 | Capture 3 | Capture 4 | Capture 5 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 0 %   | 0,00  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 %  | 3,03  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 20 %  | 6,06  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 30 %  | 9,09  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 40 %  | 12,12 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 50 %  | 15,15 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 60 %  | 18,18 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 70 %  | 21,21 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 80 %  | 24,24 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 90 %  | 27,27 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 100 % | 30,30 | ☐ | ☐ | ☐ | ☐ | ☐ |

**Sous-total Phase A** : 55 captures (~50 min de banc).

---

## Phase B — Avec frein — Vmax = **28,70 V**

| Niveau | Tension cible (V) | Capture 1 | Capture 2 | Capture 3 | Capture 4 | Capture 5 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 0 %   | 0,00  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 10 %  | 2,87  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 20 %  | 5,74  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 30 %  | 8,61  | ☐ | ☐ | ☐ | ☐ | ☐ |
| 40 %  | 11,48 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 50 %  | 14,35 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 60 %  | 17,22 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 70 %  | 20,09 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 80 %  | 22,96 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 90 %  | 25,83 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 100 % | 28,70 | ☐ | ☐ | ☐ | ☐ | ☐ |

**Sous-total Phase B** : 55 captures (~50 min de banc).

---

## Total : 110 sessions × 15 s (~1h50 hors temps de mise en route)

## Procédure rapide

1. **Régler l'alim** sur la tension cible (vérif au multimètre, tolérance ±0,1 V).
2. **Vérifier la condition de charge** dans l'IHM : *Sans* (Phase A) ou *Avec* (Phase B).
3. **Vérifier le niveau de tension saisi** dans l'IHM : 0, 10, 20… 100.
4. **Lancer la capture** (15 s).
5. **Vérifier dans la console serveur** : `Indexation réussie : Session N [A_vide|B_frein]`.
6. **Cocher la case** correspondante.

## Points d'attention

- Faire une **pause de 5 min** au milieu de chaque phase (toutes les ~25 captures) → contrôle température moteur.
- **Pause + vérif dataset entre Phase A et Phase B** : compter les fichiers `son_*.csv` et `vib_*.csv` (doit y avoir 55 de chaque), inspecter `metadata_captures_moteur.csv` (55 lignes A_vide).
- En cas de doute sur une capture (parasite, mauvaise tension), **noter le numéro de session** pour exclusion future plutôt que de la rejouer.
- Convention de nommage automatique : `son_N.csv` / `vib_N.csv` (N = id_session, généré côté serveur).
