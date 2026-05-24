# SMC Trading Bot

> Système de trading algorithmique basé sur la méthodologie **Smart Money Concepts (SMC)**, entièrement automatisé : TradingView → webhook → bot Python → MetaTrader 5 → broker. Sans intermédiaire payant.

---

## Architecture du pipeline

```
┌────────────────┐   webhook JSON    ┌─────────────────────┐
│  TradingView   │ ────────────────► │   SMC Bot           │
│  Pine Script   │                   │   Python / FastAPI  │
│  (stratégies)  │                   │   VPS Linux         │
└────────────────┘                   └──────────┬──────────┘
                                                 │  filtres : auth, validation,
                                                 │  anti-doublon, symbole, risk,
                                                 │  réconciliation des positions
                                                 ▼
                                      ┌─────────────────────┐
                                      │   mt5_forwarder     │
                                      │   (HTTP interne)    │
                                      └──────────┬──────────┘
                                                 │  ordre / gestion
                                                 ▼
                                      ┌─────────────────────┐
                                      │  mt5_executor       │
                                      │  FastAPI + package  │
                                      │  MetaTrader5        │
                                      │  VPS Windows        │
                                      └──────────┬──────────┘
                                                 ▼
                                      ┌─────────────────────┐
                                      │  MetaTrader 5       │
                                      │  → Switch Markets   │
                                      └─────────────────────┘
```

Deux machines :
- **VPS Linux** (Hostinger) — le bot FastAPI (cerveau : filtres, risque, décision).
- **VPS Windows** (Switch Markets) — MetaTrader 5 + l'executor (bras : place et gère les ordres).

---

## Stack technique

| Couche | Technologie |
|---|---|
| Détection de signal | TradingView — Pine Script v6 |
| Serveur webhook | Python 3.11+ / FastAPI |
| Hébergement bot | VPS Linux (Hostinger) |
| Exécution ordres | Package officiel `MetaTrader5` (Python) — pas de PineConnector |
| Terminal trading | MetaTrader 5 sur VPS Windows |
| Broker | Switch Markets |
| Notifications | Telegram Bot API |

---

## Stratégies de production

Quatre stratégies, une par marché, chacune sur son chart TradingView 15M avec sa propre alerte.

| Marché | Fichier Pine | Symbole broker | Sens | Backtest (réf.) |
|---|---|---|---|---|
| **Or** | `tradingview/smc_strategy_v13_gold.pine` | `XAUUSDs` | longs + shorts | 32 tr · WR 53% · +577 $ · PF 2.2 |
| **EUR/USD** | `tradingview/smc_strategy_v10.pine` | `EURUSDs` | shorts | 7 tr · WR 57% · +114 $ · PF 2.4 |
| **NASDAQ** (v13.1) | `tradingview/smc_strategy_v13_nasdaq.pine` | `USTECs` | shorts | 9 tr · WR 78% · +132 $ · **PF 3.34** |
| **Pétrole WTI** (v15.1) | `tradingview/smc_strategy_v15_oil.pine` | `WTIs` | longs + shorts | 29 tr · WR 48% · +236 $ · **PF 1.59** (in-S) / **2.05** (OOS) |

> Système **short-biased de retournement** : les longs ne sont rentables que sur
> un marché qui trende proprement (l'or et le pétrole). Sélectif par design —
> ~3 signaux / semaine tous marchés confondus.
>
> Évolution 2026-05-24 : ajout du **pétrole WTI** (4e marché) + tuning **NASDAQ**
> via ablation `h4_bos_lb` 10→20. Méthodologie : ablation 1-variable + hold-out
> test sur la période récente. Voir `docs/backlog-ameliorations.md` pour la
> roadmap complète.

Chaque script porte un groupe d'inputs **Webhook** (clé secrète, symbole broker,
timeframe) et émet un payload JSON via `alert()`.

---

## Logique SMC

1. **Liquidité** — EQH/EQL, sweeps, PDH/PDL, Asian Range
2. **Structure 15M** — BOS, CHoCH
3. **Filtre HTF (H4)** — BOS H4 obligatoire, alignement EMA 50/200
4. **Zones de réaction** — Fair Value Gap, Order Block
5. **Sessions** — killzones London / New York
6. **Confirmations** — BOS/CHoCH + 2 parmi 3 (FVG / OB / Liquidité)
7. **Impulsion** — displacement candle
8. **Risque** — SL structurel validé, RR minimum
9. **Gestion de position** — break-even, TP partiel, trailing ATR, sortie structure

---

## Contrat webhook

Le bot reçoit un JSON sur `POST /webhook`. Types d'événements :

| event_type | Rôle |
|---|---|
| `BOS_BULL` / `BOS_BEAR` | Entrée en position (achat / vente) |
| `SWEEP_HIGH` / `SWEEP_LOW` / `RANGE_BREAKOUT` | Entrées (ancien modèle détecteur) |
| `SESSION_OPEN` | Événement de gestion interne — aucun ordre |
| `CLOSE` | Clôture forcée d'une position |
| `BREAK_EVEN` | SL ramené au prix d'entrée |
| `TRAIL_SL` | SL suiveur (trailing) |
| `PARTIAL_CLOSE` | Clôture partielle (TP partiel) |

Les valeurs de gestion sont **relatives** (distances en pips), jamais des prix
absolus — pour rester insensible à l'écart de prix entre TradingView et le broker.

---

## Filtres du bot (dans l'ordre)

1. **AUTH** — clé secrète valide
2. **VALIDATION** — payload complet et cohérent
3. **ANTI-DOUBLON** — un webhook dupliqué par TradingView est ignoré
4. **SYMBOLE** — actif autorisé
5. **SESSION / EMA / RR** — sautés si le signal vient d'une stratégie complète (`prefiltered: true`)
6. **RÉCONCILIATION** — resynchronise le compteur de trades ouverts sur la réalité MT5
7. **RISK** — drawdown jour/semaine, max trades simultanés

---

## Règles de risque

| Paramètre | Valeur |
|---|---|
| Capital initial | 3 000 € |
| Risque par trade | 1 % → 30 € |
| Max trades simultanés | 3 (4 marchés disponibles, 3 positions max actives) |
| Daily drawdown limit | 3 % → arrêt |
| Weekly drawdown limit | 6 % → pause 48 h |

---

## Robustesse

- **Anti-doublon** — cache des signaux traités (TTL 1 h).
- **Réconciliation des positions** — le bot interroge l'executor pour la vérité MT5.
- **Anti-gap NASDAQ** — flat du vendredi soir (évite le gap de week-end).
- **Gestion en cours de trade en live** — break-even, trailing ATR, TP partiel,
  sortie structure répliqués du backtest vers le live.
- **Watchdog executor** — tâche planifiée toutes les 5 min : relance MT5 +
  l'executor en cas de crash / reboot / coupure. Auto-logon Windows actif.

---

## Structure du dépôt

```
bot/
  main.py                       FastAPI — endpoints /webhook /status /health /trade/close
  webhook.py                    Pipeline de filtres + routage des événements
  filters/                      session, structure, risk
  execution/
    mt5_forwarder.py            Relais bot → executor (ordres + gestion)
    mt5_executor_service.py     Service FastAPI sur le VPS Windows (package MetaTrader5)
  notifications/telegram.py     Alertes Telegram
config/settings.py              Constantes : capital, risque, symboles, événements
tradingview/                    Scripts Pine des 3 stratégies de production
scripts/
  test_webhooks.py              Suite de tests des filtres (20/20)
  start_executor.ps1            Lanceur executor (VPS Windows)
  executor_watchdog.ps1         Watchdog executor (VPS Windows)
requirements-executor.txt       Dépendances de l'executor (machine Windows)
```

---

## Déploiement

**VPS Linux — le bot**
```bash
cd /opt/smc-trading-bot
git pull
systemctl restart smc-bot
```

**VPS Windows — l'executor**
```powershell
# Télécharger la dernière version de l'executor depuis GitHub, puis :
Stop-Process -Name python -Force
Start-ScheduledTask -TaskName "SMC Executor"
```

**TradingView** — 3 alertes (une par stratégie), condition « appels de la
fonction alerte() uniquement », URL webhook du bot.

---

## Tests

```bash
python scripts/test_webhooks.py      # 20/20 — filtres, anti-doublon, gestion
```
