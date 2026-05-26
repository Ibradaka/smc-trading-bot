# Liquidity Hunter v1 — Stop Hunt Reversal

> **Strategy Pine v6 dédiée BTCUSD 5M — Projet R&D séparé du système SMC production (gold / EUR / NAS / WTI).**

Fichier : [tradingview/liquidity_hunter_v1.pine](../tradingview/liquidity_hunter_v1.pine)

## Concept

Stratégie **de retournement** basée sur le **liquidity sweep** (stop hunt).
Les institutions chassent les stops retail au-delà des swing highs/lows
évidents (multi-touch), puis renversent dans la vraie direction.

L'idée centrale : **un breakout léger qui ferme de retour dans le range
n'est PAS un breakout** — c'est une prise de liquidité, et le marché est
sur le point d'aller dans le sens opposé.

## Séquence d'un trade

1. **Identifier** un swing high/low **multi-touch** sur 15M
   (au moins 2 touches dans `zone_max_age` bougies 5M, dans une bande
   de `price_tolerance` % de prix).
2. **Détecter le sweep** : le prix dépasse le niveau de
   `sweep_min_pips` à `sweep_max_pips` % (ni trop peu = bruit,
   ni trop = vrai breakout).
3. **Confirmer le reversal** : la même bougie ferme **de retour**
   sous/sur le niveau, **mèche dominante** (`wick_ratio`),
   bougie de direction inverse (bear pour sweep high).
4. **Attendre la confirmation** (optionnel mais recommandé) :
   la bougie suivante doit confirmer le retournement.
5. **Vérifier le filtre EMA 1H directionnel** (optionnel mais recommandé) :
   shorts uniquement sous EMA 50 H1, longs au-dessus.
6. **Entrée** au close de la bougie de confirmation.
   - **SL** au-delà de l'extrême du sweep + `sl_buffer_pct` %.
   - **TP1** à `tp1_rr` × SL (par défaut 1.5R) → 50 % de la position fermée.
   - **TP2** à `tp2_rr` × SL (par défaut 2.5R) → 50 % restants.
   - **Breakeven** automatique après TP1 touché (si `use_breakeven`).

## Paramètres et rôle

### Détection swings (15M)

| Param | Défaut | Rôle |
|---|---|---|
| `swing_lookback` | 10 | Lookback ta.pivothigh/low sur le HTF 15M |
| `min_touches` | 2 | Niveau invalide si touché moins de N fois |
| `price_tolerance` | 0.05 % | % du prix pour grouper niveaux similaires |
| `zone_max_age` | 200 bougies 5M | Vieillissement avant suppression |

### Sweep

| Param | Défaut | Rôle |
|---|---|---|
| `sweep_min_pips` | 0.03 % | Dépassement minimum (sinon = bruit) |
| `sweep_max_pips` | 0.15 % | Dépassement maximum (sinon = vrai breakout) |
| `wick_ratio` | 0.5 | Mèche du sweep > 50 % de la range totale |

### Entry

| Param | Défaut | Rôle |
|---|---|---|
| `use_confirmation` | true | Attendre 1 bougie supplémentaire |
| `use_ema_filter` | true | Filtre EMA 50 H1 directionnel |
| `ema_period_h1` | 50 | Période EMA HTF |

### Session

| Param | Défaut | Rôle |
|---|---|---|
| `session_start` | 7 UTC | Début fenêtre active (London open) |
| `session_end` | 17 UTC | Fin fenêtre active (NY close) |

### Risk

| Param | Défaut | Rôle |
|---|---|---|
| `risk_pct` | 1 % equity | Risque par trade |
| `sl_buffer_pct` | 0.02 % | Buffer au-delà du sweep |
| `tp1_rr` | 1.5 | Premier TP, 50 % de la position |
| `tp2_rr` | 2.5 | Second TP, 50 % restants |
| `use_breakeven` | true | BE après TP1 touché |
| `max_trades_day` | 6 | Stop trading après N trades |
| `max_consec_loss` | 2 | Stop trading après N pertes consécutives |

### Safety

| Param | Défaut | Rôle |
|---|---|---|
| `use_news_filter` | true | Bloque 13:00-14:00 et 14:30-15:30 UTC |
| `double_sweep_cooldown` | 30 bougies | Cooldown après sweep échoué |

## Règles d'entrée

```
LONG:
  - sweep_low_detected (= bougie courante balaie un swing low multi-touch
    de 0.03-0.15 %, ferme au-dessus du niveau, bullish, mèche dominante)
  - SI use_confirmation: bougie suivante haussière
  - close > EMA 50 H1
  - in_session ET not news_blocked
  - trades_today < max_trades_day
  - consec_losses < max_consec_loss
  - bar_index - last_failed_sweep_bar > double_sweep_cooldown
  - position_size == 0 (pas déjà en trade)

SHORT: symétrique
```

## Règles de sortie

| Niveau | Action |
|---|---|
| **SL** (= extrême du sweep + buffer) | 100 % fermé |
| **TP1** (= entry ± SL_distance × 1.5) | 50 % fermé |
| **TP2** (= entry ± SL_distance × 2.5) | 50 % restants fermés |
| **Breakeven** (après TP1 touché, si activé) | SL repositionné à entry + petit buffer |

## Affichage

- **Boxes** semi-transparentes autour de chaque niveau de liquidité actif
  - Jaune si ≥ 3 touches (haute qualité)
  - Bleu si 2 touches (qualité moyenne)
  - Vert si nombre rond (confluence)
- **Labels** « 2x » / « 3x » à droite de chaque zone (= nombre de touches)
- **Labels** « ⚡ SWEEP HIGH » (rouge) / « ⚡ SWEEP LOW » (vert) sur les bougies de sweep détectées
- **EMA 50 H1** plottée en orange
- **Tableau stats** top-right : trades, WR, PF, RR moyen, EV, net, DD, zones actives, etc.

## Objectifs cibles

| Métrique | Objectif |
|---|---|
| Winrate | > 55 % |
| Profit Factor | > 1.5 |
| RR moyen réalisé | > 1:1.5 |
| Nombre de trades (période max) | > 50 |
| Max Drawdown | < 12 % |

## Pièges à éviter

### 🚫 Ne pas confondre sweep et breakout réel
Si le prix dépasse le niveau de **plus de 0.15 %** sans retour, c'est probablement un vrai breakout. Le paramètre `sweep_max_pips` filtre ça.

### 🚫 Ne pas trader sur 1 seule touche
Un swing high/low touché 1 seule fois n'est pas un niveau de liquidité significatif. `min_touches = 2` par défaut.

### 🚫 Attention au double sweep
Si on prend un sweep et qu'il échoue (SL touché), le marché est très probablement dans un vrai breakout. Le `double_sweep_cooldown` empêche de re-trader pendant N bougies.

### 🚫 Ne pas trader pendant les news
NFP, CPI, FOMC créent des spikes qui simulent des sweeps mais sont en réalité des breakouts violents. Le `use_news_filter` bloque les zones mortes 13:00-14:00 et 14:30-15:30 UTC.

### 🚫 Filtre EMA contre-tendance
Sans `use_ema_filter`, on prendrait des longs en plein downtrend H1. Le filtre empêche les contre-tendances majeures.

## Test recommandé

1. **TradingView** → ouvrir un chart **BTCUSD 5M** (Binance, Bitstamp ou Bitfinex, le plus liquide possible)
2. Pine Editor → coller le contenu de `liquidity_hunter_v1.pine`
3. **Ajouter au graphique**
4. **Strategy Tester** → onglet « Performance » → relever :
   - Total trades, Winrate, Profit Factor
   - RR moyen, Net PnL, Max Drawdown
5. **Régler** progressivement si nécessaire :
   - Si trop peu de trades (< 20) : abaisser `min_touches` à 1 ou élargir `zone_max_age` ou `price_tolerance`
   - Si WR trop bas (< 45 %) : restreindre `sweep_min_pips` à 0.05 % ou activer `use_confirmation`
   - Si DD trop haut (> 15 %) : baisser `risk_pct` à 0.5 %, ou activer `use_news_filter`

## Différences avec le système SMC production

| Aspect | Liquidity Hunter v1 | SMC Production (v13 / v15 / v10) |
|---|---|---|
| Marché | BTCUSD (crypto, 24/7) | Forex / commodities / indices |
| TF | 5M | 15M |
| Logique | Reversal sur sweep multi-touch | BOS / CHoCH + sweep + displacement |
| Filtre HTF | EMA 50 H1 | BOS H4 + EMA 200 H4 + alignement |
| TP | 50 % à 1.5R + 50 % à 2.5R | TP fixe + trailing ATR (gold/NAS) |
| News | Plage horaire hardcodée | Aucun (à backloguer) |
| Intégration bot | ❌ Non — TradingView only | ✅ Webhook → bot → MT5 |

## Statut

🔬 **R&D — pas branché au bot**. Le script émet des `alertcondition()` génériques mais n'envoie pas de webhook formaté au bot SMC. Si la stratégie s'avère rentable sur BTC 5M, on pourra l'intégrer ensuite (ajout BTCUSD broker côté MT5, payload webhook compatible avec le bot, etc.).

## Historique

- **v1.0** (2026-05-25) : version initiale. Détection multi-touch 15M, sweep + reversal, TP partiel + BE, filtre news + double sweep cooldown.
