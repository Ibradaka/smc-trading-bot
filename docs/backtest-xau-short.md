# Backtest Results — SMC XAU Short Only v1

**Symbole :** XAUUSD (Gold Spot)  
**Timeframe :** 15M  
**Source :** n'importe quel broker (OANDA, FX:XAUUSD)  
**Période :** Max disponible (5-6 mois)  
**Capital initial :** 3 000 $  
**Commission :** 0.40 $ par trade (spread Gold AXI)  
**Slippage :** 2 ticks  
**Direction :** SHORT ONLY

---

## Différences clés vs XAU v1

| Paramètre            | XAU v1                        | XAU Short v1                    |
|----------------------|-------------------------------|---------------------------------|
| Direction            | Long + Short                  | Short ONLY                      |
| Session              | Asian 01-06h + London 07-17h  | London 07-12h + NY 13:30-17h    |
| Sweep quality min    | q >= 1                        | q >= 2 (PDH ou ASR uniquement)  |
| SL range             | 20–60 pips                    | 25–80 pips                      |
| SL fallback          | 40 pips                       | 30 pips                         |
| min_rr_short         | 3.0                           | 4.0                             |
| Trailing stop        | Non                           | Oui — lock +1R après +2R profit |
| qty clamp            | 1–50 oz                       | 1–20 oz                         |
| ATR filter           | Non                           | Oui — ATR >= 90% moyenne        |
| Filtre EMA 4H        | Oui                           | Oui (close < ema_50_4h requis)  |

---

## Résultats XAU Short v1

| Métrique             | XAU Short v1 | Cible      |
|----------------------|--------------|------------|
| Trades total         | ?            | 15–40      |
| Winrate global       | ?            | > 20%      |
| Profit Factor        | ?            | > 1.3      |
| RR moyen réel        | ?            | > 4.0      |
| Net PnL              | ?            | positif    |
| Max Drawdown         | ?            | < 15%      |
| EV / trade           | ?            | > 0 $      |
| Trades trailing stop | ?            | —          |

*(À remplir après backtest TradingView)*

---

## Instructions TradingView

1. Pine Editor → coller `smc_strategy_xau_short_v1.pine`
2. "Add to chart" sur **XAUUSD 15M**
3. Période : **max disponible** (5-6 mois)
4. Strategy Tester → relever toutes les métriques
5. Paramètres par défaut :
   - `min_rr_short = 4.0`
   - `sl_min_pips = 25`
   - `sl_max_pips = 80`
   - `risk_usd = 20$`
   - `use_trailing = true`
   - `atr_mult_filter = 0.9`
   - `use_discount_filter = false`

---

## Notes d'analyse XAU Short v1

*(À remplir après backtest)*

- Le filtre ATR (>= 90% moyenne) réduit-il les faux signaux ou génère-t-il trop peu de trades ?
- Le RR minimum 4.0 est-il atteignable sur Gold 15M sans PDL lointain ?
- Le trailing stop (+1R après +2R) améliore-t-il le PnL ou coupe-t-il trop tôt ?
- La session London 07-12h + NY 13:30-17h est-elle plus efficace que le London 07-17h complet ?
- Les sweeps q>=2 (PDH/ASR uniquement) donnent-ils un winrate > 20% vs q>=1 ?

---

## Réglages si < 15 trades

1. `atr_mult_filter` : baisser à 0.7 (filtre ATR moins strict)
2. `sl_max_pips` : élargir à 100 (absorber plus de contextes)
3. `sweep_lookback` : augmenter à 40
4. `struct_lookback` : augmenter à 20
5. Session : envisager d'activer la session Asian (modifier manuellement dans le code)
6. `min_rr_short` : baisser à 3.5 (plus d'opportunités TP atteignable)

## Réglages si winrate < 20% (>= 15 trades)

1. `min_rr_short` : remonter à 4.5 (sélectionner uniquement les meilleurs setups)
2. `use_discount_filter` : activer = true (vendre depuis une zone de premium)
3. `ob_body_atr_mult` : augmenter à 0.8 (OB bear plus institutionnel)
4. `struct_lookback` : baisser à 8 (structures CHoCH plus fraîches)
5. `atr_mult_filter` : monter à 1.0 (uniquement pendant volatilité élevée)

## Réglages si PF < 1.3 (winrate ok mais pertes trop grandes)

1. `use_trailing` : vérifier que = true (activer trailing pour protéger les gagnants)
2. `sl_max_pips` : réduire à 60 (SL plus serré = pertes plus limitées)
3. `risk_usd` : maintenir à 20$ (ne pas augmenter avant PF > 1.3)

---

## Comparaison XAU v1 vs XAU Short v1 (Shorts uniquement)

| Métrique             | XAU v1 Shorts | XAU Short v1 | Delta |
|----------------------|---------------|--------------|-------|
| Trades               | ?             | ?            | ?     |
| Winrate              | ?             | ?            | ?     |
| Profit Factor        | ?             | ?            | ?     |
| RR réel moyen        | ?             | ?            | ?     |
| Net PnL              | ?             | ?            | ?     |

*(Comparer les shorts de XAU v1 vs cette version dédiée pour valider l'apport du filtre ATR + RR 4.0)*
