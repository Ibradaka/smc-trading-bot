# SMC Trading Bot

> Système de trading algorithmique basé sur la méthodologie Smart Money Concepts (SMC), entièrement automatisé via webhook TradingView → MetaTrader 5.

---

## Architecture du pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE DE TRADING                          │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     webhook      ┌──────────────────┐
  │  TradingView │ ──────────────►  │   SMC Bot        │
  │  Pine Script │   JSON payload   │   Python/FastAPI │
  │  (capteur)   │                  │   (cerveau)      │
  └──────────────┘                  └────────┬─────────┘
                                             │
                                    validation + filtres
                                    risk management
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  PineConnector   │
                                   │  (exécuteur)     │
                                   └────────┬─────────┘
                                            │
                                   commande d'ordre
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  MetaTrader 5    │
                                   │  (terminal)      │
                                   └────────┬─────────┘
                                            │
                                   exécution marché
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │   AXI Broker     │
                                   │   (liquidité)    │
                                   └──────────────────┘
```

---

## Stack technique

| Couche | Technologie |
|---|---|
| Détection de signal | TradingView (Pine Script v5) |
| Serveur webhook | Python 3.11+ / FastAPI |
| Hébergement | VPS Linux |
| Exécution ordres | PineConnector |
| Terminal trading | MetaTrader 5 |
| Broker | AXI |
| Notifications | Telegram Bot API |
| Planification | APScheduler |

---

## Actifs cibles

| Symbole | Priorité | Session principale |
|---|---|---|
| EUR/USD | Haute | London + NY |
| NASDAQ (NAS100) | Moyenne | NY |
| Silver (XAGUSD) | Basse | London |

---

## Sessions tradées

| Session | Heure locale (France) | Heure UTC |
|---|---|---|
| London | 09h00 – 12h00 | 08h00 – 11h00 |
| New York | 15h30 – 18h00 | 14h30 – 17h00 |

> Aucun trade en dehors de ces fenêtres. Le bot bloque automatiquement les signaux hors session.

---

## Statut du projet

**Phase actuelle : Beta en cours**

- [x] Architecture définie
- [x] Documentation initiale
- [ ] Pine Script SMC detector v1
- [ ] Serveur FastAPI webhook
- [ ] Moteur de filtrage des signaux
- [ ] Intégration PineConnector
- [ ] Notifications Telegram
- [ ] Tests sur compte démo
- [ ] Passage en live

---

## Règles de risque (non négociables)

- **Capital initial** : 3 000 €
- **Risque par trade** : 1% → 30 € max
- **RR minimum** : 1:2
- **Max trades simultanés** : 2
- **Daily drawdown limit** : 3% → bot s'arrête
- **Weekly drawdown limit** : 6% → pause 48h forcée

---

## Lancement rapide

```bash
# Cloner et configurer
cp .env.example .env
# Remplir .env avec vos clés

# Installer les dépendances
pip install -r bot/requirements.txt

# Lancer le serveur
uvicorn bot.main:app --host 0.0.0.0 --port 8000
```
