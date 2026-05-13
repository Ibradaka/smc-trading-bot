# Architecture du SMC Trading Bot

## Vue d'ensemble

Le système repose sur un pipeline linéaire à cinq couches, où chaque couche a une responsabilité unique et strictement délimitée. Le principe central : **séparer radicalement la détection du signal de la décision d'exécution**.

---

## Les cinq couches du pipeline

### 1. TradingView — Le capteur brut

**Rôle** : Observer les marchés en temps réel et émettre des événements bruts.

TradingView exécute le Pine Script SMC Detector sur les graphiques. Il ne prend aucune décision de trading. Il se contente d'identifier des structures de marché significatives (sweeps, BOS, ranges) et d'envoyer un webhook JSON au bot dès qu'un événement est détecté.

- Timeframes surveillés : 4H (HTF), 15M (MTF), 5M (LTF)
- Symboles : EURUSD, NAS100, XAGUSD
- Type de signal : événement, pas une recommandation

**Ce qu'il NE fait pas** : filtrer, décider, gérer le risque.

---

### 2. SMC Bot (Python / FastAPI) — Le cerveau

**Rôle** : Recevoir, valider, filtrer et décider si un signal mérite d'être exécuté.

C'est le cœur du système. Il tourne sur un VPS Linux et expose un endpoint HTTP qui reçoit les webhooks de TradingView. Pour chaque signal entrant, le bot applique une chaîne de filtres séquentiels :

1. **Authentification** : vérification de la clé secrète webhook
2. **Validation du payload** : format JSON correct, champs requis présents
3. **Filtre de session** : le signal arrive-t-il dans une fenêtre de trading autorisée ?
4. **Filtre EMA** : le prix est-il du bon côté de l'EMA 50 sur le HTF ?
5. **Filtre confluence** : le signal est-il confirmé par plusieurs timeframes ?
6. **Filtre de risque** : le daily drawdown limit est-il atteint ? Y a-t-il déjà 2 trades ouverts ?
7. **Calcul taille de position** : lot size basé sur 1% du capital et le SL en pips

Si tous les filtres passent → commande envoyée à PineConnector.
Si un filtre échoue → signal bloqué, motif logué, notification Telegram optionnelle.

**Ce qu'il NE fait pas** : exécuter directement des ordres sur MT5.

---

### 3. PineConnector — L'exécuteur

**Rôle** : Traduire les commandes du bot en ordres MetaTrader 5.

PineConnector est un service intermédiaire qui reçoit des commandes textuelles formatées (via webhook ou API) et les transmet à MetaTrader 5 via un Expert Advisor dédié. Il gère la communication avec le terminal MT5.

- Format de commande : `LICENSE_ID,buy,EURUSD,risk=1,sl=50,tp=100`
- Gère les ordres market, limit, stop
- Confirme l'exécution au bot

**Ce qu'il NE fait pas** : filtrer les signaux, gérer le risque global.

---

### 4. MetaTrader 5 — Le terminal

**Rôle** : Réceptionner et placer les ordres sur le compte de trading.

MT5 tourne en permanence (sur le VPS ou un PC dédié) avec l'EA PineConnector actif. Il reçoit les ordres, les valide côté broker, et les transmet à AXI pour exécution sur le marché.

- Gestion locale des ordres ouverts
- Application des SL/TP
- Reporting des trades pour le journal

**Ce qu'il NE fait pas** : filtrer, décider.

---

### 5. AXI Broker — La liquidité

**Rôle** : Fournir l'accès au marché interbancaire et exécuter les ordres.

AXI est le broker ECN/STP qui fournit la liquidité. Les ordres passent par MT5 → AXI → marché. AXI garantit l'exécution au meilleur prix disponible avec un spread compétitif sur les paires ciblées.

---

## Règles de design du système

### Séparation détection / décision
Le Pine Script ne décide jamais d'acheter ou vendre. Il détecte uniquement des structures. La décision appartient exclusivement au bot Python.

### Filtrage agressif
Le bot est conçu pour **bloquer** la majorité des signaux. Un signal non exécuté coûte 0€. Un mauvais trade peut coûter 30€ ou plus. Le biais par défaut est BLOCK.

### Qualité > Quantité
L'objectif n'est pas de trader souvent, mais de trader bien. 2-3 trades de qualité par semaine valent mieux que 20 trades aléatoires.

### Traçabilité totale
Chaque signal reçu — qu'il soit exécuté ou bloqué — est logué avec horodatage, motif, et état des filtres. Cela permet d'améliorer les règles au fil du temps.

### Fail-safe par défaut
En cas d'erreur (timeout PineConnector, réponse invalide, exception non gérée), le bot bloque le trade et notifie via Telegram. Il ne tente jamais de réessayer automatiquement sans supervision.
