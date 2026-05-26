# Changelog — SMC Trading Bot

---

## [Detector v1.2] — 2026-05-16

### `tradingview/smc_detector_v1.pine` — Alignement complet V7

**MOD 4 — min_sweep_quality (logique V7 exacte)**
- Ajout input `min_sweep_quality` (défaut=1, groupe GRP_BOS)
- Ajout tracking `last_sweep_high_q` et `last_sweep_low_q` (var int, initialisés à 0)
- Mis à jour quand `sweep_high_cond` / `sweep_low_cond` se déclenche (toujours q=1 car détecteur swing-only)
- `sweep_high_recent` mis à jour : `ta.barssince(sweep_high_cond) <= bos_lookback and last_sweep_high_q >= min_sweep_quality`
- Comportement identique à V7 avec `min_sweep_quality=1` (défaut)

**Correction header** : ÉVÉNEMENTS ÉMIS — `BOS_BEAR` → `CHOCH_BEAR` dans le commentaire de documentation

---

## [Detector v1.1] — 2026-05-16

### `tradingview/smc_detector_v1.pine`

**MOD 1 — Session continue 07:00–17:00 UTC**
- Remplacé `f_session()` (retournait "london"/"ny"/"none" sur 2 fenêtres séparées) par `f_in_session()` (booléen, 07:00→17:00 UTC sans gap)
- Tous les payloads JSON : champ `"session"` passe de valeur statique à `f_in_session() ? "active" : "inactive"`
- SESSION_OPEN conserve `"london"` en valeur fixe (déclenchement manuel en début de session)
- Correction CW10003 : `ta.highest(high, 10)` extrait à portée globale (`highest_10`)

**MOD 2 — CHoCH_BEAR (logique V7b)**
- Ajout `sweep_high_recent` : `ta.barssince(sweep_high_cond) <= bos_lookback`
- Ajout `struct_ref_low_choch` : `ta.lowest(low, 15)[1]`
- Ajout `choch_bear` : `sweep_high_recent and close < struct_ref_low_choch and close[1] >= struct_ref_low_choch and daily_bias_bear`
- Visuel mis à jour : ligne rouge + label "CHoCH ▼" (remplace ligne violette "BOS ▼")
- `plotshape` mis à jour : `choch_bear` en rouge (remplace `bos_bear_cond` en violet)

**MOD 3 — Remplacement BOS_BEAR → CHOCH_BEAR**
- `alertcondition(bos_bear_cond, ...)` → `alertcondition(choch_bear, ...)`
- Titre : `"🟣 BOS_BEAR — Break of Structure Baissier"` → `"⚡ CHOCH_BEAR — Retournement baissier"`
- `payload_bos_bear` → `payload_choch_bear`, `event_type` : `"BOS_BEAR"` → `"CHOCH_BEAR"`
- TP ajusté : `tp_pips` 40 → 45 dans le payload CHOCH_BEAR (RR supérieur)

**MOD 4 — Sweep quality >= 1**
- Déjà satisfait : `sweep_high_cond` et `sweep_low_cond` utilisaient `>= 1` — aucun changement requis

---

## [Strategy v7b-fix] — session précédente

### `tradingview/smc_strategy_v7b_fix.pine`
- Version de référence pour la logique V7b (BOS longs + CHoCH shorts)
- Session continue 07:00–17:00 UTC
- `f_in_session()` (booléen)
- `choch_bear` asymétrique pour les shorts

---

## [Strategy XAU Short v3] — session précédente

### `tradingview/smc_strategy_xau_short_v3.pine`
- Copie exacte de `smc_strategy_xau_v1.pine` avec `long_signal = false`
- Test isolé : shorts uniquement, sans aucun autre changement de logique

---

## [Strategy XAU Short v2] — session précédente

### `tradingview/smc_strategy_xau_short_v2.pine`
- Basée sur `smc_strategy_xau_v1.pine`, code LONG supprimé
- `f_bull_ob_bot()` et `f_bull_fvg_bot()` conservées (utilisées par `f_tp_short`)
- Correction breakeven SHORT : `entry + 1pip` (était `entry - 1pip`)
- Labels de debug sur entrée : `Entry / SL / TP`

---

## [Strategy XAU Short v1] — session précédente

### `tradingview/smc_strategy_xau_short_v1.pine`
- SHORT ONLY sur XAUUSD 15M
- Corrections CE10013 : ternaires → if/else dans `f_tp_short`, `f_sl_short_raw_pips`, section stats
- Correction CW10003 : `ta.highest(high, 10)` → variable globale `highest_10`
- Trailing stop actif : lock +1R après +2R de profit
- ATR filter : `ATR >= 90%` de la moyenne
- `min_rr_short = 4.0`, session London 07–12h + NY 13:30–17h
