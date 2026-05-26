# Backtest Results — SMC Trading Bot

**Symbole :** EURUSD  
**Timeframe :** 15M  
**Période :** 12 mois (mai 2024 → mai 2025)  
**Capital initial :** 3 000 $  
**Commission :** 0.007% (V1–V7) / 0.70$ cash/ordre (V8.0)  
**Slippage :** 2 ticks  

---

## Résultats comparatifs

| Métrique         | V1        | V2b       | V3        | V4        | V5        | V6  | V6b | V7     | V7b | **V8.0** |
|------------------|-----------|-----------|-----------|-----------|-----------|-----|-----|--------|-----|----------|
| Lot size         | 0.02 fixe | 0.02 fixe | 1% equity | 1% equity | 1% equity | 1% equity | 1% equity | 1% equity | dynamique (risk 20$) | dynamique (risk 20$) |
| Winrate          | 30.12%    | 35%       | 33%       | 20%       | 20%       | ?   | ?   | 24%    | ?   | **?**    |
| Profit Factor    | 0.839     | négatif   | négatif   | négatif   | négatif   | ?   | ?   | ?      | ?   | **?**    |
| RR Moyen réel    | 1.946     | 1.73      | 1.70      | 3.68      | 3.22      | ?   | ?   | 3.65   | ?   | **?**    |
| Trades total     | 83        | 17        | 18        | 30        | 30        | ?   | ?   | 59     | ?   | **?**    |
| Net PnL          | négatif   | négatif   | négatif   | négatif   | négatif   | ?   | ?   | ~nul   | ?   | **?**    |
| Max Drawdown     | ?         | ?         | ?         | ?         | ?         | ?   | ?   | 0.02%  | ?   | **?**    |

**V4 détail (référence) :**
- Shorts seuls : winrate 25%, RR 5.95 → profitable si isolé
- Longs seuls  : winrate 18%, RR 2.50 → perdant
- Gap au breakeven mathématique : ~1.4% de winrate

---

## Historique des versions

### V1 — BOS seul (6 mois)
- SL : 15 pips fixe / TP : 35 pips fixe
- 83 trades — trop de faux signaux, winrate trop bas

### V2b — FVG+OB assoupli (6 mois)
- Lot 0.02 fixe (cassé), 17 trades — trop restrictif

### V3 — ICT/LuxAlgo (12 mois)
- 1% equity, OB institutionnel, sessions corrigées
- 18 trades, même problème de volume

### V4 — ICT Killzones + niveaux institutionnels (12 mois)
- PDH/PDL + Asian Range, sweep qualité >= 2
- Killzones : London 07-10h / NY 12-15h UTC
- 30 trades, RR 3.68 excellent — winrate 20% insuffisant
- min_rr = 3.0 trop strict pour les longs

### V5 — Breakeven + RR Asymétrique (12 mois)
- Breakeven automatique à +1R
- RR asymétrique : min_rr_long=2.0 / min_rr_short=3.0
- Résultats similaires à V4 — modèle d'entrée inchangé

### V6 — CHoCH + OTE Fibonacci 0.705 (12 mois)
- **CHoCH** : premier break de structure APRÈS le sweep
  = confirmation que la structure a inversé (vs BOS générique)
- **OTE** : entrée uniquement dans la zone Fibonacci 62%-79%
  du move sweep_low → choch_level
- **Confluence** : OTE doit coïncider avec FVG OU OB
- OB créé sur le CHoCH (plus précis que sur le BOS)
- TP inchangé : PDH/PDL > OB opposé > swing > RR × 2.5
- Breakeven conservé à +1R
- use_discount_filter = false (pour ne pas trop réduire les trades)

---

## Objectifs V6

| Métrique      | Cible    |
|---------------|----------|
| Winrate       | > 35%    |
| Profit Factor | > 1.2    |
| RR Moyen      | > 2.5    |
| Trades total  | 15 à 30  |
| Net PnL       | positif  |
| Max Drawdown  | < 15%    |

---

## Notes d'analyse V6

*(À remplir après backtest)*

- Le CHoCH améliore-t-il le winrate vs le BOS générique ?
- Combien de CHoCH sont générés sans retracement dans l'OTE ?
- La confluence OTE+FVG ou OTE+OB est-elle souvent remplie ?
- Quel est le RR réalisé avec l'OTE comme entrée ?

---

## Réglages si < 15 trades après V6

1. `min_sweep_quality` : baisser à 1 (sweeps génériques acceptés)
2. `choch_lookback` : augmenter de 15 → 25
3. `ote_fib_top` : élargir à 0.50 (zone OTE plus large)
4. `ote_fib_bot` : élargir à 0.88
5. `use_discount_filter` : déjà false — vérifier si activer aide

## Réglages si winrate < 35% après V6 (> 15 trades)

1. Réduire `sweep_lookback` à 20 (sweeps plus récents = plus frais)
2. Réduire `choch_lookback` à 10
3. Activer `use_discount_filter` = true
4. Augmenter `ob_body_atr_mult` à 0.8 (OB plus institutionnel)

---

### V7b — Sizing dynamique (base V7 exacte)
- Clone V7 avec **une seule modification** : sizing dynamique basé sur risque USD fixe
- `risk_usd = 20$` → `lot = risk_usd / (sl_pips × 10)` — clamp 0.01–0.50 lots
- Exemple : SL=15p → 0.13 lot → gain cible ~40$ à RR 2.0
- Objectif : traduire le winrate/RR de V7 en vrais dollars positifs
- Drawdown cible : < 5% (vs 0.02% sur 1% equity — les gains étaient microscopiques)

| Métrique        | V7     | V7b    |
|-----------------|--------|--------|
| Winrate         | 24%    | ?      |
| Trades          | 59     | ?      |
| RR moyen        | 3.65   | ?      |
| Gain moy/trade  | micro  | ~20$   |
| Drawdown        | 0.02%  | ?      |
| Net PnL         | ~nul   | ?      |

**Objectifs V7b :**
- Winrate stable ~24% (même logique = même signaux)
- Gain moyen par trade gagnant : 15–30 USD
- Drawdown max < 5%
- Net PnL positif en vrais dollars

---

### V6b — CHoCH comme unique confirmation (base V4 exacte)
- Clone V4 avec CHoCH remplaçant BOS (test contrôlé isolé)
- `min_sweep_quality` = 2, killzones London+NY, `min_rr` = 3.0
- Objectif : tester si CHoCH seul améliore le winrate sur base V4

### V8 — UT 30 min | SMA200 | Sizing dynamique | RSI+ATR
- **UT 30 min** : paramètres recalibrés (sweep=20, struct=10, swing=7, ob=10)
- **Session Londres** : 08:00-17:00 UTC uniquement (vs 07-17h V7)
- **SMA200** : filtre directionnel longs (close > SMA200) — shorts libres
- **Sizing dynamique** : `risk_usd=20$` → position = risk / (sl_pips × 0.0001)
  - Ex: SL=15p → 13 333 unités (0.13 lot) → gain cible ~40$ brut à RR 2.0
- **RSI(14)** : Long si RSI > 45 / Short si RSI < 55
- **ATR volatilité** : entrée si ATR > 80% de ATR moyen sur 50 bougies
- **Labels filtrés** : affiche raison du blocage sur le graphique
- `sl_max_pips` élargi à 35p pour absorber bruit UT30

### V7 — BOS (Longs) + CHoCH (Shorts) + Session 07-17h UTC
- **Session continue** : 07:00→17:00 UTC (London open → NY close)
- **Asymétrique** : Longs = BOS_BULL / Shorts = CHoCH_BEAR
- **Sweep quality** : min >= 1 (assoupli vs >= 2 dans V4/V6b)
- Breakeven à +1R + RR asymétrique Long=2.0 / Short=3.0
- Filtre EMA 50 4H ajouté aux signaux (close > EMA pour longs)
- OB Bull créé sur BOS+sweep / OB Bear créé sur CHoCH

## Objectifs V7

| Métrique         | Cible    |
|------------------|----------|
| Trades total     | > 40     |
| Winrate longs    | > 20%    |
| Winrate shorts   | > 30%    |
| Profit Factor    | > 1.1    |
| Net PnL          | positif  |
| Max Drawdown     | < 15%    |

## Réglages si < 40 trades après V7

1. `sweep_lookback` : augmenter à 40 (fenêtre plus large)
2. `struct_lookback` : augmenter à 25 (BOS/CHoCH plus larges)
3. `fvg_atr_mult` : baisser à 1.0 (FVG moins exigeants)
4. `ob_body_atr_mult` : baisser à 0.3

## Réglages si winrate < 25% après V7 (> 40 trades)

1. `min_sweep_quality` : remonter à 2 (PDH/PDL et ASR uniquement)
2. Activer `use_discount_filter` = true
3. `struct_lookback` : baisser à 10 (structures plus fraîches)

---

## V8.0 — Simplified & Reinforced

**Fichier :** `tradingview/smc_strategy_v8.pine`  
**Symbole de test :** EURUSD 15M OANDA  
**Période de test :** max disponible  
**Commission :** $0.70 cash/ordre (= ~0.007% sur 10 000 unités)  

### Différences clés vs V7

| Point | V7 | V8.0 |
|-------|----|------|
| Sweep quality | >= 1 (swing accepté) | >= 2 seulement (ASR + PDH/PDL) |
| Session | 07–17h UTC fixe | Configurable (défaut 07–17h) |
| Commission | % par trade | $0.70 cash par ordre |
| FVG / OB slots | 3 | 2 |
| Partial TP | Non | 50% à 1.5R |
| Trailing stop | Non | ATR×1.5 après breakeven |
| Structure exit | Non | `ta.lowest/highest(10)[1]` |
| Candle confirm | Non | Corps > 50% de la range |

### Configuration du backtest TradingView

```
use_atr_filter      = true   (ATR >= 80% moyenne 50)
use_candle_confirm  = true   (corps > 50%)
use_structure_exit  = true   (exit sur rupture 10 bougies)
use_discount_filter = false  (désactivé — trop restrictif)
use_partial_tp      = true   (50% à 1.5R)
use_breakeven       = true   (breakeven à +1R)
use_trailing        = true   (trailing ATR×1.5 après BE)
use_pwhl            = false  (PWH/PWL désactivés)
min_rr_long         = 2.0
min_rr_short        = 2.5
sl_min_pips         = 10
sl_max_pips         = 25
sweep_lookback      = 30
struct_lookback     = 15
```

### Résultats (à remplir après backtest)

| Métrique          | Résultat | Cible      |
|-------------------|----------|------------|
| Trades total      | ?        | 15 – 30    |
| Winrate global    | ?        | > 28%      |
| Winrate longs     | ?        | > 25%      |
| Winrate shorts    | ?        | > 30%      |
| Profit Factor     | ?        | > 1.3      |
| RR moyen réel     | ?        | > 2.0      |
| Partial TP pris   | ?        | —          |
| EV par trade      | ?        | > 0 $      |
| Net PnL           | ?        | positif    |
| Max Drawdown      | ?        | < 10%      |

### Réglages si < 15 trades après V8.0

1. `sweep_lookback` : augmenter à 40–50
2. `struct_lookback` : augmenter à 20–25
3. `fvg_atr_mult` : baisser à 1.0 (FVG moins exigeants)
4. `ob_body_atr_mult` : baisser à 0.3
5. `use_candle_confirm` : passer à false (filtre trop sélectif ?)

### Réglages si winrate < 28% (> 15 trades)

1. `use_discount_filter` : activer (true) — n'entrer qu'en zone favorable
2. `atr_mult` : augmenter à 1.0 (volatilité plus élevée = signaux plus propres)
3. `struct_lookback` : baisser à 10 (structures plus fraîches)
4. `ob_body_atr_mult` : augmenter à 0.8 (OB plus institutionnels)
