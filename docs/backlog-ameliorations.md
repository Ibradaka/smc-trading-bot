# Backlog améliorations — SMC Trading Bot

> Ordre = priorité réelle. Ne rien implémenter avant ~20-30 trades démo.
> La démo est notre vrai test out-of-sample : la fausser en bricolant tue les stats.

---

## 🟢 1. Étude d'ablation des filtres (priorité absolue)

**But** : identifier chiffre en main lequel des composants porte vraiment l'edge.
**Cible** : sessions / EMA / displacement / HTF (BOS H4) / ATR. Sweep = noyé dans `liq_bull/bear`, ablation nécessite petit refactor.

**Pourquoi en premier** : c'est de la mesure, pas du bricolage. Identifie le poids mort à virer → réduit l'overfitting honnêtement (au lieu de fusionner des fichiers pour rien).

**Effort** : ~0 (les interrupteurs `use_*` existent déjà dans `v13_gold.pine`). Procédure : baseline tout activé → désactiver 1 filtre → re-backtest → noter delta. Voir [docs/ablation-results.md](ablation-results.md) (à créer le moment venu).

**Quand** : après ~20-30 trades démo collectés.

### 🎓 Méthodologie ablation 1-variable validée (2026-05-24)

Le protocole rigoureux a été éprouvé pendant l'ajout de WTI (4e marché) :

1. **Baseline propre** (toutes options par défaut) → relever PF / WR / Net / DD / Outliers / Pire perte
2. **Une seule variable changée à la fois** ; reset to defaults entre chaque test
3. **Matrice de résultats** avec critères de décision DURS avant de modifier
4. **Hold-out test** sur fenêtre récente (3-6 mois jamais utilisée pour le tuning)
5. **Critères GO** : PF > 1.3 hors-échantillon + WR > 35% + ≥ 8 trades + 0 outlier dominant + DD < 5%

Ajout `use_date_filter` dans les scripts Pine (déjà fait sur `v15_oil.pine`) pour
faciliter les hold-out tests sans dépendre du plan TradingView payant.

### 📊 Résultats ablation `h4_bos_lb` (10 → 20) — 2026-05-24

| Marché | Avant | Après | Décision |
|---|---|---|---|
| WTI | PF 1.20 | PF 1.59 (in-S) / **2.05** (OOS) | ✅ Intégré v15.1 |
| NASDAQ | PF 2.28 | **PF 3.34** (1 loser filtré) | ✅ Intégré v13.1 |
| GOLD | PF 2.20 | dégradé | 🛑 Pas de changement |
| EURUSD | PF 2.4 | inchangé (échantillon 7 trades trop petit) | 🛑 Pas de changement |

**Insight clé** : `h4_bos_lb=20` aide les marchés à trend dominant (indices et
commodities reactives), neutre/dégrade sur gold qui a sa propre structure macro.
Pas universel, mais commun à 2/3 marchés tendanciels.

---

## 🟢 2. Filtre news (calendrier économique)

**But** : pas d'entrée 15-30 min avant NFP / CPI / FOMC / ECB / BoE. Ces news spike à travers les SL (slippage massif).

**Source recommandée** : **ForexFactory** (scrape CSV) — gratuit, fiable, JSON dispo via `investpy` Python.
Alternatives : Trading Economics API (75 $/mois), FRED API (US uniquement, gratuit).

**Implémentation** : ajouter un filtre `is_high_impact_news_window(symbol, now)` dans `bot/filters/` → nouvelle raison de blocage `NEWS_WINDOW`. Cron quotidien qui télécharge le calendrier de la semaine.

**Effort** : ~1 journée code + 1 journée re-backtest des 3 stratégies sans news pour valider que les chiffres restent OK.

**Caveat** : nos backtests ont été faits SANS ce filtre. Donc les chiffres du README (32 tr / 7 / 10) ne seront plus valides → re-backtester obligatoire. Risque secondaire : certains displacement / sweeps sont *causés* par la news — mal réglé, on coupe les meilleurs trades.

**Quand** : juste après l'ablation.

---

## 🟢 3. Régime de volatilité — VIX (et DXY)

**But** : adapter le comportement du bot au régime de marché courant.

**Hypothèses à tester** :
- VIX > 25 (peur) → désactiver les longs NASDAQ ; éventuellement durcir le RR mini sur shorts.
- VIX < 12 (complaisance) → réduire la taille de position (vol qui peut exploser).
- DXY trend haussier confirmé → favoriser les shorts EUR/USD ; XAU shorts plus fiables.
- Ces seuils sont des hypothèses, à valider par backtest.

**Source** : Yahoo Finance (gratuit), TradingView (déjà accessible via `request.security("CBOE:VIX")` en Pine).
DXY déjà partiellement intégré dans `v13_gold.pine` (`use_dxy_filter`, désactivé par défaut).

**Pourquoi c'est utile** : sortir / rentrer plus tôt sur les marchés selon le contexte macro court terme. Indicateur leading vs notre stratégie purement price-action.

**Effort** : 0.5 journée. Modifier les 3 scripts Pine pour lire le VIX en H1, ajouter un input `use_vix_regime` (off par défaut), backtester ON vs OFF.

**Quand** : après le filtre news. Avant : confirmer via ablation que ça apporte vraiment quelque chose vs régime sans.

---

## 🟡 4. Fusion code base partagé (maintenabilité, pas anti-overfit)

**But réel** : un seul code base avec presets par marché → fix un bug une fois, pas trois.

**À NE PAS vendre comme** « réduit l'overfitting » — c'est faux. Les différences entre v13 gold / v10 eurusd / v13 nasdaq reflètent des contraintes structurelles (pip value, sessions, direction) et pas du curve-fit.

**Effort** : ~2 journées (extraction logique commune, presets par marché, re-validation backtest).

**Quand** : éventuellement après l'ablation, si elle confirme que beaucoup de logique est commune.

---

## 🟡 5. GDELT — risk-off géopolitique (R&D)

**But** : détecter un événement macro / géopolitique soudain (guerre, crise bancaire, surprise centrale) → forcer le bot en mode défensif (flat, ou interdiction d'entrée X heures).

**Source** : **GDELT Project** (gdeltproject.org). Base mondiale d'événements & ton émotionnel, mise à jour toutes les 15 min, gratuite, 65+ langues. API : `https://api.gdeltproject.org/api/v2/doc/doc?query=...&format=json`.

**Pourquoi en R&D et pas tout de suite** : pour bien l'utiliser il faut du NLP / scoring de tonalité crédible. Sinon on s'expose au faux positif (panique sur un mot-clé sans contexte). C'est ambitieux pour notre setup.

**Effort** : ~1 semaine minimum pour un prototype crédible.

**Quand** : seulement quand l'ablation, le filtre news et le VIX sont validés et bien réglés. Probablement Q4 2026 au plus tôt.

---

## 🔴 6. Position sizing dynamique selon qualité du setup

**But théorique** : risquer plus sur les setups A+ (sweep PDH/PDL = sweep institutionnel) → améliorer expectancy.

**Pourquoi geler** : on touche au **risque par trade**, le bouton le plus dangereux. Aucune donnée encore ne prouve que la qualité du sweep prédit le winrate. Risque réel de curve-fitting : les gains d'expectancy backtest s'évaporent souvent out-of-sample.

**Si jamais implémenté** : plafond strict (jamais > 1.5 %), base 1 % conservée, validation walk-forward obligatoire.

**Quand** : seulement après ablation + démo qui montre une corrélation **stable** entre qualité du sweep et winrate. Pas avant.

---

## 🟡 7. Filtre de corrélation entre marchés

**But** : éviter d'avoir 3 shorts simultanés corrélés via USD (XAU + EUR + NASDAQ sur un spike DXY) qui ne sont pas 3 trades mais 1 pari ×3.

**Faible priorité car** : 4 marchés, ~3 trades/semaine, simultanéité rare. `MAX_TRADES=4` plafonne déjà l'exposition.

**Effort** : 1 journée (calcul corrélation glissante sur fenêtre 30j, blocage si 2+ trades déjà ouverts dans actifs >0.7 corrélés).

**Quand** : nice-to-have, jamais prioritaire tant qu'on n'a pas observé le cas en démo.

---

## 🔧 8. Cosmétique — surface du retcode MT5 réel dans l'erreur

**Quoi** : aujourd'hui quand le mode de remplissage supporté (IOC) retourne 10018 (marché fermé), l'executor essaie FOK + RETURN en fallback, qui retournent 10030 (unsupported). L'erreur finale remontée est `10030`, ce qui cache la vraie raison.

**Effort** : 30 min. Ajouter une logique dans `_filling_order` ou dans la boucle d'envoi : si une tentative retourne `10018`, breaker immédiatement et remonter `MARKET_CLOSED` plutôt que d'écraser avec le retcode de la dernière tentative.

**Impact** : aucun fonctionnel (l'ordre n'est pas placé dans les deux cas). Pure amélioration du debug / clarté du message d'erreur.

**Quand** : quand tu veux, c'est trivial.

---

## Règles de priorisation

- **Mesurer avant d'ajouter** (#1 avant tout le reste).
- **Re-backtester systématiquement** après chaque modif qui touche les filtres ou la logique d'entrée — sinon les chiffres du README mentent.
- **Ne jamais toucher au risque/trade** (1 % fixe) sans données démo qui prouvent le besoin.
- **Le `h4_bos` est le verrou de volume** — le desserrer détruit le WR. À ne pas toucher sans benchmark dur.

---

## Origine de ce backlog

Issu de l'échange du 2026-05-23 sur une analyse externe qui suggérait 5 améliorations
(news filter, corrélation, sizing dynamique, fusion v14, ablation). L'ablation a été
identifiée comme **la** suggestion vraiment utile — les autres ont été triées par
priorité réelle vs vente marketing. VIX/DXY/GDELT ajoutés sur demande utilisateur le
même jour.
