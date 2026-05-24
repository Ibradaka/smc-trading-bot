# Suivi de la phase démo — SMC Trading Bot

> Phase d'observation : laisser le système tourner en démo **sans intervenir**.
> La démo est le vrai test out-of-sample — ne pas la fausser (pas de trade manuel,
> pas de modif de script tant qu'elle tourne).
>
> Échantillon utile pour juger : **~20-30 trades**. Avant ça, c'est du bruit.

---

## Checklist — à chaque trade ouvert (10 s dans MT5)

- [ ] **SL présent** — colonne S/L remplie. Si vide → couper à la main + debug executor.
- [ ] **Bon symbole** — XAUUSDs / EURUSDs / USTECs uniquement.
- [ ] **Volume cohérent** — ~1 % de risque, pas de lot anormalement gros.
- [ ] **Un signal = un seul ordre** — pas de position dupliquée à la même seconde.

## Checklist — tous les jours (1 min)

- [ ] Notifications Telegram reçues (ou silence cohérent : 0 trade = 0 notif).
- [ ] Coup d'œil aux 3 graphiques MT5 — positions cohérentes.

## Checklist — 2×/semaine (mardi / vendredi, routine keep-alive)

- [ ] Les 3 VPS répondent (RDP Windows, MT5 connecté, bot Linux up).
- [ ] In-trade management OK sur les trades clôturés (break-even / TP partiel / trailing).
- [ ] `MAX_TRADES = 4` respecté — jamais 5 positions simultanées.

## Signaux d'alarme

| Signal | Sens | Action |
|---|---|---|
| Position **sans SL** | Faille critique (cas B) | Couper à la main, debug executor avant tout autre trade |
| **Pic de signaux** (5+/sem.) | Doublon / marché anormal / filtre cassé | Investiguer |
| Ordre sur **mauvais symbole** | Bug de routage | Investiguer |
| Executor injoignable | Crash | Vérifier que le watchdog a relancé |
| **0 trade pendant 2-3 sem.** | ⚠️ NORMAL (~1,7 trade/sem. en moyenne irrégulière) | Rien — ne pas s'inquiéter |

---

## Relevé des trades

| # | Date | Marché | Sens | Résultat (€) | Management déclenché | Notes |
|---|------|--------|------|--------------|----------------------|-------|
| 1 |      |        |      |              |                      |       |
| 2 |      |        |      |              |                      |       |
| 3 |      |        |      |              |                      |       |
| 4 |      |        |      |              |                      |       |
| 5 |      |        |      |              |                      |       |
| 6 |      |        |      |              |                      |       |
| 7 |      |        |      |              |                      |       |
| 8 |      |        |      |              |                      |       |
| 9 |      |        |      |              |                      |       |
| 10|      |        |      |              |                      |       |

> « Management déclenché » : break-even / TP partiel / trailing / exit structure / aucun.
> Ce relevé alimentera l'étude d'ablation et la comparaison démo vs backtest.
