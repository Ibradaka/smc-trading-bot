# Règles de Risque — SMC Trading Bot

> Ces règles sont **non négociables**. Elles sont codées en dur dans le système et ne peuvent pas être contournées par un signal, quelle qu'en soit la qualité perçue.

---

## Capital & Risque par trade

| Paramètre | Valeur |
|---|---|
| Capital initial | 3 000 € |
| Risque par trade | **1%** = 30 € maximum |
| RR minimum accepté | **1:2** (risque 30€ → cible 60€ minimum) |
| Levier maximum | **1:10** |

**Calcul du lot size** :
```
Risque € = Capital × 1%
Lot size = Risque € / (SL en pips × Pip value)
```

Le bot calcule automatiquement le lot size à chaque signal ALLOW. Il ne se base jamais sur un lot size fixe.

---

## Limites de drawdown

### Daily Drawdown Limit — 3% (90 €)

- Si les pertes cumulées du jour atteignent **90 €**, le bot s'arrête immédiatement.
- Aucun nouveau trade n'est autorisé jusqu'à la réinitialisation du jour suivant (00h00 UTC).
- Une notification Telegram est envoyée dès le déclenchement.
- Les trades déjà ouverts restent gérés normalement (SL/TP en place).

### Weekly Drawdown Limit — 6% (180 €)

- Si les pertes cumulées de la semaine atteignent **180 €**, le bot entre en **pause forcée de 48 heures**.
- La pause démarre au moment du déclenchement, pas en fin de journée.
- Reprise automatique après 48h si le daily DD n'est pas atteint.
- Notification Telegram avec heure de reprise estimée.

### Tableau de référence

| Limite | Seuil | Action bot | Durée |
|---|---|---|---|
| Daily Drawdown | 3% = 90 € | Arrêt total | Jusqu'à 00h00 UTC |
| Weekly Drawdown | 6% = 180 € | Pause forcée | 48 heures |

---

## Gestion des trades simultanés

- **Maximum 2 trades ouverts simultanément**, toutes paires confondues.
- Si 2 trades sont déjà ouverts, tout nouveau signal est automatiquement bloqué avec le code `MAX_TRADES_ATTEINT`.
- Cette règle s'applique même si les deux trades sont sur des symboles différents.
- Aucune exception.

---

## Sessions de trading autorisées

Seuls les signaux reçus dans ces fenêtres horaires sont traités :

| Session | Heure UTC | Heure France (été) | Heure France (hiver) |
|---|---|---|---|
| London | 08h00 – 11h00 | 10h00 – 13h00 | 09h00 – 12h00 |
| New York | 14h30 – 17h00 | 16h30 – 19h00 | 15h30 – 18h00 |

> Les signaux reçus en dehors de ces fenêtres sont bloqués avec le code `HORS_SESSION`, même s'ils sont techniquement valides.

---

## Actifs autorisés

| Symbole | Priorité | Sessions |
|---|---|---|
| EURUSD | Haute | London + NY |
| NAS100 | Moyenne | NY uniquement |
| XAGUSD | Basse | London |

Tout signal sur un symbole non listé est bloqué avec le code `SYMBOLE_NON_AUTORISE`.

---

## Filtre EMA 50 (HTF 4H)

- Pour un signal **bull** : le prix doit être **au-dessus** de l'EMA 50 sur le 4H.
- Pour un signal **bear** : le prix doit être **en dessous** de l'EMA 50 sur le 4H.
- Un signal contre l'EMA HTF est bloqué avec le code `EMA_CONTRAIRE`.

---

## Ratio Risque/Rendement minimum

- Chaque signal doit proposer un RR d'au moins **1:2**.
- Si `tp_pips / sl_pips < 2.0`, le signal est bloqué avec le code `RR_INSUFFISANT`.
- En l'absence de `sl_pips` ou `tp_pips` dans le payload, le signal est bloqué.

---

## Règle de comportement en cas d'erreur

En cas d'erreur technique (timeout, réponse invalide de PineConnector, exception non gérée) :

1. Le trade est **bloqué** (pas tenté).
2. L'erreur est loguée avec traceback complet.
3. Une alerte Telegram est envoyée immédiatement.
4. Aucune tentative automatique de réessai.
5. Intervention manuelle requise avant de reprendre.

---

## Récapitulatif des règles en une ligne

```
1% risque | RR min 1:2 | max 2 trades | DD jour 3% stop | DD semaine 6% pause 48h | levier max 1:10 | sessions London+NY uniquement
```
