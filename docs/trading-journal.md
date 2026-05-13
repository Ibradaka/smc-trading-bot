# Journal de Trading — SMC Bot

> Chaque signal reçu par le bot est enregistré ici, qu'il soit exécuté ou bloqué. Ce journal est la source principale d'amélioration du système.

---

## Journal des signaux

| Date | Signal | Symbole | Direction | Filtre passé | Raison BLOCK | Résultat | RR réalisé | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

**Légende colonnes :**
- **Date** : Date et heure UTC du signal
- **Signal** : Type d'événement (SWEEP_HIGH, BOS_BULL, etc.)
- **Symbole** : Paire ou actif tradé
- **Direction** : Bull / Bear
- **Filtre passé** : ✅ ALLOW ou ❌ BLOCK
- **Raison BLOCK** : Code de blocage si applicable (voir webhook-contract.md)
- **Résultat** : WIN / LOSS / BREAKEVEN / EN COURS
- **RR réalisé** : Ratio effectif en sortie (ex: 2.3R)
- **Notes** : Observations manuelles, contexte marché

---

## Statistiques hebdomadaires

| Semaine | Signaux reçus | ALLOW | BLOCK | WIN | LOSS | BE | PnL € | RR moyen |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

---

## Observations hebdomadaires

### Semaine du __ / __ / ____

> *(à remplir chaque vendredi)*

**Ce qui a bien fonctionné :**
-

**Ce qui n'a pas fonctionné :**
-

**Ajustements envisagés :**
-

**Prochaines priorités :**
-

---

## Règles d'utilisation du journal

1. **Log automatique** : Le bot écrit dans `bot/logs/signals.log` à chaque signal.
2. **Mise à jour manuelle** : Les colonnes Résultat, RR réalisé et Notes sont remplies manuellement après clôture du trade.
3. **Review hebdomadaire** : Chaque vendredi, remplir la section Observations.
4. **Aucune modification rétroactive** : Ne jamais modifier les entrées passées. Ajouter une nouvelle ligne de correction si nécessaire.
