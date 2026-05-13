# Contrat Webhook — TradingView → SMC Bot

> Document de référence. Toute modification ici doit être répercutée dans `config/settings.py` et dans le Pine Script.

---

## 1. Endpoint

```
POST https://{VPS_HOST}:8000/webhook
Content-Type: application/json
X-Secret-Key: {WEBHOOK_SECRET_KEY}
```

- La clé secrète est définie dans `.env` → `WEBHOOK_SECRET_KEY`
- Toute requête sans ce header, ou avec une valeur incorrecte, reçoit un `401` immédiat
- Le bot répond toujours avec un JSON structuré, même en cas d'erreur

---

## 2. Schéma du payload entrant

### 2.1 Champs obligatoires

| Champ | Type | Valeurs acceptées | Description |
|---|---|---|---|
| `event_type` | string | Voir §3 | Type d'événement SMC |
| `symbol` | string | `EURUSD`, `NAS100`, `XAGUSD` | Symbole au format broker MT5 |
| `timeframe` | string | `4H`, `15`, `5` | Timeframe d'origine du signal |
| `price` | float | > 0 | Prix de clôture de la bougie déclenchante |
| `direction` | string | `bull`, `bear` | Biais directionnel du signal |
| `timestamp` | string | ISO 8601 UTC | Ex : `2025-01-15T09:32:00Z` |

### 2.2 Champs optionnels

| Champ | Type | Valeurs acceptées | Requis pour |
|---|---|---|---|
| `sl_pips` | float | > 0 | Tous les événements tradeables |
| `tp_pips` | float | > 0 | Tous les événements tradeables |
| `ema_50_value` | float | > 0 | Filtre EMA — envoyé si disponible |
| `session` | string | `london`, `ny` | Tous les événements |
| `sweep_level` | float | > 0 | `SWEEP_HIGH`, `SWEEP_LOW` |
| `range_high` | float | > 0 | `RANGE_BREAKOUT` |
| `range_low` | float | > 0, < `range_high` | `RANGE_BREAKOUT` |
| `notes` | string | max 200 caractères | Libre |

> **Règle pratique** : pour les événements tradeables (hors `SESSION_OPEN`, `EMA_FILTER`), `sl_pips` et `tp_pips` sont techniquement optionnels mais leur absence entraîne un blocage automatique `RR_INSUFFISANT`.

---

## 3. Types d'événements

### 3.1 `SWEEP_HIGH`

**Définition** : le prix dépasse temporairement un swing high précédent pour chasser les stop-loss des positions longues, puis revient en dessous — signal de retournement baissier potentiel.

**Direction attendue** : `bear`
**Timeframes** : `15`, `5`

```json
{
  "event_type": "SWEEP_HIGH",
  "symbol": "EURUSD",
  "timeframe": "15",
  "price": 1.08542,
  "direction": "bear",
  "timestamp": "2025-01-15T09:32:00Z",
  "sweep_level": 1.08510,
  "sl_pips": 18,
  "tp_pips": 40,
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Règles de validation spécifiques** :
- `price` doit être > `sweep_level` (le prix a bien dépassé le niveau)
- `direction` doit être `bear`
- `sl_pips` et `tp_pips` obligatoires pour être tradeable

---

### 3.2 `SWEEP_LOW`

**Définition** : le prix dépasse temporairement un swing low précédent pour chasser les stop-loss des positions courtes, puis remonte — signal de retournement haussier potentiel.

**Direction attendue** : `bull`
**Timeframes** : `15`, `5`

```json
{
  "event_type": "SWEEP_LOW",
  "symbol": "EURUSD",
  "timeframe": "15",
  "price": 1.08180,
  "direction": "bull",
  "timestamp": "2025-01-15T10:15:00Z",
  "sweep_level": 1.08210,
  "sl_pips": 15,
  "tp_pips": 35,
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Règles de validation spécifiques** :
- `price` doit être < `sweep_level` (le prix a bien cassé en dessous)
- `direction` doit être `bull`
- `sl_pips` et `tp_pips` obligatoires pour être tradeable

---

### 3.3 `BOS_BULL`

**Définition** : Break of Structure haussier — le prix clôture au-dessus d'un swing high intermédiaire, confirmant un changement de structure de marché vers le haut (Higher High).

**Direction attendue** : `bull`
**Timeframes** : `5` (confirmation d'entrée après setup sur `15`)

```json
{
  "event_type": "BOS_BULL",
  "symbol": "EURUSD",
  "timeframe": "5",
  "price": 1.08620,
  "direction": "bull",
  "timestamp": "2025-01-15T09:45:00Z",
  "sl_pips": 12,
  "tp_pips": 30,
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Règles de validation spécifiques** :
- `direction` doit être `bull`
- `price` > `ema_50_value` requis si `ema_50_value` est fourni (filtre EMA)
- Généralement utilisé en confirmation d'un `SWEEP_LOW` précédent

---

### 3.4 `BOS_BEAR`

**Définition** : Break of Structure baissier — le prix clôture en dessous d'un swing low intermédiaire, confirmant un changement de structure vers le bas (Lower Low).

**Direction attendue** : `bear`
**Timeframes** : `5` (confirmation d'entrée après setup sur `15`)

```json
{
  "event_type": "BOS_BEAR",
  "symbol": "EURUSD",
  "timeframe": "5",
  "price": 1.08150,
  "direction": "bear",
  "timestamp": "2025-01-15T10:22:00Z",
  "sl_pips": 14,
  "tp_pips": 32,
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Règles de validation spécifiques** :
- `direction` doit être `bear`
- `price` < `ema_50_value` requis si `ema_50_value` est fourni (filtre EMA)
- Généralement utilisé en confirmation d'un `SWEEP_HIGH` précédent

---

### 3.5 `SESSION_OPEN`

**Définition** : Notification d'ouverture de session de trading. Utilisé par le bot pour réinitialiser les compteurs intraday et mettre à jour le contexte de session. Non tradeable directement.

**Direction** : biais contextuel (`bull` si prix > EMA 50, `bear` sinon)
**Timeframes** : `4H`

```json
{
  "event_type": "SESSION_OPEN",
  "symbol": "EURUSD",
  "timeframe": "4H",
  "price": 1.08420,
  "direction": "bull",
  "timestamp": "2025-01-15T08:00:00Z",
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Comportement bot** : réponse `ALLOW` systématique (événement de gestion interne), aucun ordre envoyé à PineConnector.

---

### 3.6 `RANGE_BREAKOUT`

**Définition** : cassure directionnelle d'une zone de consolidation identifiée sur le MTF. Le prix sort du range avec momentum — signal d'expansion potentielle dans la direction de la cassure.

**Direction** : `bull` (cassure haussière) ou `bear` (cassure baissière)
**Timeframes** : `15`

```json
{
  "event_type": "RANGE_BREAKOUT",
  "symbol": "EURUSD",
  "timeframe": "15",
  "price": 1.08680,
  "direction": "bull",
  "timestamp": "2025-01-15T09:55:00Z",
  "range_high": 1.08620,
  "range_low": 1.08380,
  "sl_pips": 22,
  "tp_pips": 50,
  "ema_50_value": 1.08390,
  "session": "london"
}
```

**Règles de validation spécifiques** :
- `range_high` et `range_low` obligatoires
- `range_high` > `range_low` (sinon payload invalide)
- Pour `bull` : `price` > `range_high`
- Pour `bear` : `price` < `range_low`
- Amplitude minimum du range : 20 pips (filtre anti-micro-range)

---

## 4. Règles de validation globales

### Types et formats

| Règle | Détail |
|---|---|
| `price`, `sl_pips`, `tp_pips` | Float strictement positif (> 0) |
| `timestamp` | Format ISO 8601 avec suffixe `Z` (UTC obligatoire) |
| `symbol` | Exactement l'un de : `EURUSD`, `NAS100`, `XAGUSD` |
| `event_type` | Exactement l'un des 6 types listés au §3 |
| `direction` | Exactement `bull` ou `bear` (minuscules) |
| `timeframe` | Exactement `4H`, `15` ou `5` |
| `session` | Exactement `london` ou `ny` si fourni |
| `notes` | String ≤ 200 caractères si fourni |

### Cohérence directionnelle

| event_type | direction forcée |
|---|---|
| `SWEEP_HIGH` | `bear` |
| `SWEEP_LOW` | `bull` |
| `BOS_BULL` | `bull` |
| `BOS_BEAR` | `bear` |
| `SESSION_OPEN` | libre |
| `RANGE_BREAKOUT` | libre |

Une incohérence direction/event_type entraîne un blocage `PAYLOAD_INVALIDE`.

### Ratio RR

```
tp_pips / sl_pips >= 2.0   →  signal traitable
tp_pips / sl_pips < 2.0    →  BLOCK : RR_INSUFFISANT
```

### Filtre EMA (si `ema_50_value` fourni)

```
bull  →  price > ema_50_value   (sinon BLOCK : EMA_CONTRAIRE)
bear  →  price < ema_50_value   (sinon BLOCK : EMA_CONTRAIRE)
```

---

## 5. Réponses du bot

### 5.1 Signal autorisé — `ALLOW`

HTTP `200 OK`

```json
{
  "status": "ALLOW",
  "signal_id": "3f2a1b4c-8e7d-4a2f-b1c3-9d0e5f6a7b8c",
  "event_type": "SWEEP_HIGH",
  "symbol": "EURUSD",
  "direction": "bear",
  "lot_size": 0.03,
  "sl_pips": 18,
  "tp_pips": 40,
  "rr": 2.22,
  "risk_eur": 29.70,
  "pineconnector_cmd": "LICENSE_ID,sell,EURUSD,risk=1,sl=18,tp=40",
  "filters_passed": ["AUTH", "SESSION", "SYMBOL", "RR", "EMA", "RISK_LIMITS"],
  "timestamp": "2025-01-15T09:32:05Z"
}
```

### 5.2 Signal bloqué — `BLOCK`

HTTP `200 OK` (pas un 4xx — TradingView doit recevoir un 200 pour ne pas retenter)

```json
{
  "status": "BLOCK",
  "signal_id": "7a9c2d1e-3f4b-5c6d-8e9f-0a1b2c3d4e5f",
  "event_type": "SWEEP_HIGH",
  "symbol": "EURUSD",
  "reason": "HORS_SESSION",
  "detail": "Signal reçu à 12:45 UTC — hors fenêtre London (08:00-11:00) et NY (14:30-17:00)",
  "filters_passed": ["AUTH", "SYMBOL"],
  "filters_failed": ["SESSION"],
  "timestamp": "2025-01-15T12:45:10Z"
}
```

### 5.3 Erreur d'authentification

HTTP `401 Unauthorized`

```json
{
  "status": "BLOCK",
  "reason": "AUTH_ECHEC",
  "detail": "Header X-Secret-Key absent ou invalide",
  "timestamp": "2025-01-15T09:32:01Z"
}
```

### 5.4 Payload invalide

HTTP `422 Unprocessable Entity`

```json
{
  "status": "BLOCK",
  "reason": "PAYLOAD_INVALIDE",
  "detail": "Champ manquant : sl_pips. Incohérence détectée : SWEEP_HIGH requiert direction=bear, reçu bull.",
  "timestamp": "2025-01-15T09:32:01Z"
}
```

---

## 6. Codes de raison de blocage

| Code | Filtre | Description |
|---|---|---|
| `AUTH_ECHEC` | 1 — Auth | Header `X-Secret-Key` absent ou invalide |
| `PAYLOAD_INVALIDE` | 2 — Validation | Champ manquant, type incorrect, incohérence |
| `SYMBOLE_NON_AUTORISE` | 3 — Symbol | Symbole hors liste `EURUSD / NAS100 / XAGUSD` |
| `HORS_SESSION` | 4 — Session | Signal hors fenêtre London ou NY |
| `EMA_CONTRAIRE` | 5 — EMA | Prix du mauvais côté de l'EMA 50 HTF |
| `RR_INSUFFISANT` | 6 — RR | `tp_pips / sl_pips < 2.0` |
| `MAX_TRADES_ATTEINT` | 7 — Risk | 2 trades simultanés déjà ouverts |
| `DAILY_DD_ATTEINT` | 7 — Risk | Perte du jour ≥ 90 € (3% du capital) |
| `WEEKLY_DD_ATTEINT` | 7 — Risk | Perte de la semaine ≥ 180 € (6% du capital) |
| `CONFLUENCES_INSUFFISANTES` | 8 — Confluence | Signal LTF sans setup MTF correspondant |
| `ERREUR_TECHNIQUE` | — | Exception non gérée — trade bloqué par sécurité |

Les filtres sont appliqués dans l'ordre numéroté. Le premier filtre échoué arrête la chaîne.

---

## 7. Notes d'implémentation

- Le `signal_id` est un UUID v4 généré côté bot à la réception, avant tout traitement.
- Tous les timestamps sont en UTC avec suffixe `Z`.
- Chaque signal (ALLOW ou BLOCK) est écrit dans `bot/logs/signals.log` avec tous ses champs.
- TradingView reçoit toujours un HTTP `200` pour les décisions ALLOW/BLOCK (évite les retry automatiques). Seules les erreurs techniques retournent `401` ou `422`.
- Le champ `filters_passed` dans la réponse permet de déboguer facilement quel filtre a bloqué.
