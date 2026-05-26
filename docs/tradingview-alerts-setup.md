# TradingView Alerts Setup — SMC Detector v1

**Indicateur :** `smc_detector_v1.pine`  
**Symbole :** EURUSD 15M (ou autre)  
**Webhook URL :** `https://{VPS_HOST}:8000/webhook`  
**Logique :** Alignée sur SMC Strategy V7 (BOS longs / CHoCH shorts)

---

## 6 Alertconditions — Liste finale

| # | Titre TradingView | Condition Pine | Direction |
|---|-------------------|----------------|-----------|
| 1 | 🔴 SWEEP_HIGH — Signal Bear | `sweep_high_cond` | bear |
| 2 | 🟢 SWEEP_LOW — Signal Bull | `sweep_low_cond` | bull |
| 3 | 🔵 BOS_BULL — Break of Structure Haussier | `bos_bull_cond` | bull |
| 4 | ⚡ CHOCH_BEAR — Retournement baissier | `choch_bear` | bear |
| 5 | ⏰ SESSION_OPEN — Ouverture de session | `session_open_cond` | contextuel |
| 6 | 🟡 RANGE_BREAKOUT — Cassure de range | `range_bull_cond or range_bear_cond` | contextuel |

> **Note :** BOS_BEAR a été remplacé par CHOCH_BEAR (logique V7). CHOCH_BEAR exige un sweep récent (`sweep_high_cond` dans la fenêtre `bos_lookback`) — signal plus sélectif et aligné sur la stratégie réelle.

---

## Configuration pas-à-pas dans TradingView

1. Pine Editor → coller `smc_detector_v1.pine` → **Add to chart** sur EURUSD 15M
2. Cliquer sur l'icône **Alerte** (réveil) en haut à droite
3. **Condition** : `SMC Detector v1` → sélectionner l'événement voulu
4. **Options** : `Une fois par bougie` (évite les doublons intra-bougie)
5. **Notifications** : activer **Webhook URL**
6. **Webhook URL** : `https://{VPS_HOST}:8000/webhook`
7. **Message** : coller le payload JSON correspondant ci-dessous

Répéter pour chacun des 6 événements.

---

## Payloads JSON

> Remplacer `VOTRE_CLE_SECRETE` par la valeur de `WEBHOOK_SECRET_KEY` dans le `.env` VPS.

### 1. SWEEP_HIGH
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"SWEEP_HIGH","symbol":"{{ticker}}","timeframe":"{{interval}}","price":{{close}},"direction":"bear","timestamp":"{{timenow}}","sweep_level":{{plot_0}},"sl_pips":20,"tp_pips":50,"ema_50_value":{{plot_1}},"daily_bias":"bear","session":"active"}
```

### 2. SWEEP_LOW
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"SWEEP_LOW","symbol":"{{ticker}}","timeframe":"{{interval}}","price":{{close}},"direction":"bull","timestamp":"{{timenow}}","sweep_level":{{plot_4}},"sl_pips":20,"tp_pips":50,"ema_50_value":{{plot_1}},"daily_bias":"bull","session":"active"}
```

### 3. BOS_BULL
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"BOS_BULL","symbol":"{{ticker}}","timeframe":"{{interval}}","price":{{close}},"direction":"bull","timestamp":"{{timenow}}","sl_pips":15,"tp_pips":40,"ema_50_value":{{plot_1}},"daily_bias":"bull","session":"active"}
```

### 4. CHOCH_BEAR _(remplace BOS_BEAR depuis v1.1)_
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"CHOCH_BEAR","symbol":"{{ticker}}","timeframe":"{{interval}}","price":{{close}},"direction":"bear","timestamp":"{{timenow}}","sl_pips":15,"tp_pips":45,"ema_50_value":{{plot_1}},"daily_bias":"bear","session":"active"}
```

### 5. SESSION_OPEN
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"SESSION_OPEN","symbol":"{{ticker}}","timeframe":"4H","price":{{close}},"direction":"bull","timestamp":"{{timenow}}","ema_50_value":{{plot_1}},"daily_bias":"bull","session":"london"}
```

### 6. RANGE_BREAKOUT
```json
{"secret":"VOTRE_CLE_SECRETE","event_type":"RANGE_BREAKOUT","symbol":"{{ticker}}","timeframe":"{{interval}}","price":{{close}},"direction":"bull","timestamp":"{{timenow}}","range_high":{{plot_2}},"range_low":{{plot_3}},"sl_pips":25,"tp_pips":60,"ema_50_value":{{plot_1}},"daily_bias":"bull","session":"active"}
```

---

## Variables exportées `{{plot_N}}`

| Variable TradingView | Contenu | Utilisé dans |
|----------------------|---------|--------------|
| `{{plot_0}}` | `last_swing_high` | SWEEP_HIGH (`sweep_level`) |
| `{{plot_1}}` | `ema_50_4h` | Tous les payloads |
| `{{plot_2}}` | `range_high` | RANGE_BREAKOUT |
| `{{plot_3}}` | `range_low` | RANGE_BREAKOUT |
| `{{plot_4}}` | `last_swing_low` | SWEEP_LOW (`sweep_level`) |
| `{{plot_5}}` | Daily bias (1=bull / 0=bear) | Debug |

---

## Paramètres du détecteur (Section 1)

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `swing_lookback` | 10 | Pivot swing de chaque côté |
| `sweep_buffer_pips` | 2.0 | Tolérance dépassement sweep |
| `bos_lookback` | 20 | Fenêtre BOS / CHoCH |
| `min_sweep_quality` | **1** | Qualité sweep min (V7 : 1 = swing générique) |
| `range_bars` | 15 | Durée consolidation minimum |
| `range_min_pips` | 20 | Amplitude range minimum |

---

## Notes importantes

- **`session`** : `"active"` = dans 07:00–17:00 UTC / `"inactive"` = hors session. SESSION_OPEN garde `"london"` en valeur fixe.
- **CHOCH_BEAR vs BOS_BEAR** : CHOCH_BEAR requiert `sweep_high_cond` récent (`<= bos_lookback`) + `last_sweep_high_q >= min_sweep_quality`. Avec `min_sweep_quality=1` (défaut V7), tous les sweeps de swing valident.
- **`{{timenow}}`** : timestamp Unix ms — converti automatiquement en ISO 8601 UTC par le bot Python.
- **Qualité sweep** : le détecteur supporte uniquement les sweeps de swing (qualité 1). Pour PDH/ASR (qualité 2-3), utiliser la stratégie V7 directement.
