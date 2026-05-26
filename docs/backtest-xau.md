# Backtest Results — SMC Strategy XAU v1

**Symbole :** XAUUSD (Gold Spot)  
**Timeframe :** 15M  
**Source :** n'importe quel broker (OANDA, FX:XAUUSD)  
**Période :** Max disponible (5-6 mois)  
**Capital initial :** 3 000 $  
**Commission :** 0.40 $ par trade (spread Gold AXI)  
**Slippage :** 2 ticks  

---

## Différences clés vs V7b EURUSD

| Paramètre         | V7b EURUSD        | XAU v1            |
|-------------------|-------------------|-------------------|
| pip_value/unit    | 0.0001 $/pip/unit | 0.10 $/pip/oz     |
| qty clamp         | 1–50 oz           | 1–50 oz           |
| SL min            | 10 pips           | 20 pips           |
| SL max            | 25 pips           | 60 pips           |
| Commission        | 0.007% par trade  | 0.40$ par trade   |
| Session           | London 07-17h UTC | Asian 01-06h + London 07-17h UTC |
| min_rr_long       | 2.0               | 2.5               |
| min_rr_short      | 3.0               | 3.0               |
| SL fallback       | 20 pips           | 40 pips           |

---

## Résultats XAU v1

| Métrique         | XAU v1 | Cible     |
|------------------|--------|-----------|
| Trades total     | ?      | > 40      |
| Winrate global   | ?      | > 35%     |
| Profit Factor    | ?      | > 1.3     |
| RR moyen réel    | ?      | > 2.5     |
| Net PnL          | ?      | positif   |
| Max Drawdown     | ?      | < 15%     |
| Longs trades     | ?      | —         |
| Longs winrate    | ?      | > 35%     |
| Longs RR réel    | ?      | > 2.5     |
| Shorts trades    | ?      | —         |
| Shorts winrate   | ?      | > 35%     |
| Shorts RR réel   | ?      | > 3.0     |

*(À remplir après backtest TradingView)*

---

## Instructions TradingView

1. Pine Editor → coller `smc_strategy_xau_v1.pine`
2. "Add to chart" sur **XAUUSD 15M**
3. Période : **max disponible** (5-6 mois)
4. Strategy Tester → relever toutes les métriques
5. Paramètres par défaut :
   - `min_rr_long = 2.5`
   - `min_rr_short = 3.0`
   - `sl_min_pips = 20`
   - `sl_max_pips = 60`
   - `risk_usd = 20$`
   - `use_discount_filter = false`

---

## Notes d'analyse XAU v1

*(À remplir après backtest)*

- Le Gold génère-t-il plus de sweeps de qualité que EURUSD ?
- La session Asian 01-06h UTC ajoute-t-elle des trades pertinents ?
- Le SL 20-60 pips absorbe-t-il correctement le bruit Gold 15M ?
- Le winrate est-il supérieur à EURUSD (24%) grâce aux mouvements plus directionnels ?

---

## Réglages si < 20 trades

1. `min_sweep_quality` : baisser à 1 (déjà à 1 — vérifier si `use_pwhl=true` aide)
2. `sweep_lookback` : augmenter à 40
3. `struct_lookback` : augmenter à 20
4. `sl_max_pips` : élargir à 80 (bruit Gold plus ample)
5. `fvg_atr_mult` : baisser à 1.0

## Réglages si winrate < 35% (> 20 trades)

1. `min_sweep_quality` : remonter à 2 (ASR + PDH/PDL uniquement)
2. `use_discount_filter` : activer = true
3. `struct_lookback` : baisser à 10 (structures plus fraîches)
4. `ob_body_atr_mult` : augmenter à 0.8 (OB plus institutionnel)
