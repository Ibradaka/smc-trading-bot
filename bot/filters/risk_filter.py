"""
Filtre 3 — Risk management en temps réel.

Maintient l'état interne du bot (en mémoire, réinitialisé au redémarrage) :
  - Perte cumulée du jour (reset à 00:00 UTC)
  - Perte cumulée de la semaine (reset le lundi 00:00 UTC)
  - Nombre de trades actuellement ouverts
  - Timestamp de fin de pause weekly (si active)

Règles appliquées :
  1. MAX_TRADES_ATTEINT   → 4 trades simultanés ouverts (1 par marché)
  2. DAILY_DD_ATTEINT     → perte du jour ≥ 90 € (3% de 3000 €)
  3. WEEKLY_DD_ATTEINT    → perte de la semaine ≥ 180 € (6%) ou pause active

Note architecture : l'état est en mémoire pure (pas de DB).
Un redémarrage du bot réinitialise les compteurs.
Pour la production, persister dans un fichier JSON (évolution future).
"""

import logging
from datetime import datetime, timezone, timedelta

from config.settings import (
    MAX_TRADES,
    DAILY_DD_AMOUNT,
    WEEKLY_DD_AMOUNT,
    WEEKLY_PAUSE_HOURS,
    TRADEABLE_EVENTS,
)

logger = logging.getLogger(__name__)


class RiskState:
    """
    Singleton d'état du risk management.
    Instancié une seule fois au démarrage, partagé par toutes les requêtes.
    """

    def __init__(self) -> None:
        self._open_trades: int = 0
        self._daily_loss: float = 0.0
        self._weekly_loss: float = 0.0
        self._last_daily_reset: datetime = self._today_utc()
        self._last_weekly_reset: datetime = self._this_week_monday()
        self._weekly_pause_until: datetime | None = None

    # ------------------------------------------------------------------
    # Propriétés publiques (lecture seule depuis l'extérieur)
    # ------------------------------------------------------------------

    @property
    def open_trades(self) -> int:
        return self._open_trades

    @property
    def daily_loss(self) -> float:
        return self._daily_loss

    @property
    def weekly_loss(self) -> float:
        return self._weekly_loss

    @property
    def weekly_pause_active(self) -> bool:
        if self._weekly_pause_until is None:
            return False
        return datetime.now(timezone.utc) < self._weekly_pause_until

    @property
    def weekly_pause_until(self) -> datetime | None:
        return self._weekly_pause_until

    # ------------------------------------------------------------------
    # Reset automatique des compteurs
    # ------------------------------------------------------------------

    def _today_utc(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _this_week_monday(self) -> datetime:
        now = datetime.now(timezone.utc)
        monday = now - timedelta(days=now.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)

    def _maybe_reset(self) -> None:
        """Réinitialise les compteurs si on a changé de jour ou de semaine."""
        now = datetime.now(timezone.utc)

        today = self._today_utc()
        if today > self._last_daily_reset:
            logger.info(
                "Daily reset — perte précédente : %.2f €", self._daily_loss
            )
            self._daily_loss = 0.0
            self._last_daily_reset = today

        this_monday = self._this_week_monday()
        if this_monday > self._last_weekly_reset:
            logger.info(
                "Weekly reset — perte précédente : %.2f €", self._weekly_loss
            )
            self._weekly_loss = 0.0
            self._weekly_pause_until = None
            self._last_weekly_reset = this_monday

    # ------------------------------------------------------------------
    # Mise à jour de l'état (appelé par webhook.py après clôture trade)
    # ------------------------------------------------------------------

    def trade_opened(self) -> None:
        """Incrémenter le compteur de trades ouverts."""
        self._open_trades = self._open_trades + 1
        logger.info("Trade ouvert — trades actifs : %d", self._open_trades)

    def sync_open_trades(self, count: int) -> None:
        """
        Resynchronise le compteur sur la réalité MT5 (réconciliation).

        MT5 ne notifie pas le bot quand un trade se ferme (TP/SL touché) :
        sans ça le compteur ne redescend jamais et finit par bloquer tous
        les signaux. Appelé avant le filtre RISK avec le nombre réel de
        positions ouvertes (magic 13013) renvoyé par l'executor.
        """
        count = max(0, int(count))
        if count != self._open_trades:
            logger.info(
                "Réconciliation — trades ouverts : %d -> %d (réalité MT5)",
                self._open_trades, count,
            )
        self._open_trades = count

    def trade_closed(self, pnl_eur: float) -> None:
        """
        Enregistrer la clôture d'un trade.
        pnl_eur : positif = gain, négatif = perte.
        """
        self._maybe_reset()
        self._open_trades = max(self._open_trades - 1, 0)

        if pnl_eur < 0:
            loss = abs(pnl_eur)
            self._daily_loss += loss
            self._weekly_loss += loss
            logger.info(
                "Trade clôturé — PnL: %.2f € | Perte jour: %.2f € | Perte semaine: %.2f €",
                pnl_eur, self._daily_loss, self._weekly_loss,
            )

            # Déclencher pause weekly si seuil atteint
            if self._weekly_loss >= WEEKLY_DD_AMOUNT and not self.weekly_pause_active:
                self._weekly_pause_until = datetime.now(timezone.utc) + timedelta(
                    hours=WEEKLY_PAUSE_HOURS
                )
                logger.warning(
                    "Weekly DD atteint (%.2f €) — pause jusqu'à %s",
                    self._weekly_loss,
                    self._weekly_pause_until.strftime("%Y-%m-%d %H:%M UTC"),
                )
        else:
            logger.info("Trade clôturé — Gain: %.2f €", pnl_eur)

        logger.info("Trades actifs après clôture : %d", self._open_trades)

    # ------------------------------------------------------------------
    # Filtre principal
    # ------------------------------------------------------------------

    def check(self, signal: dict) -> tuple[bool, str]:
        """
        Vérifie toutes les règles de risk management.

        Returns:
            (True, "")           → filtre passé
            (False, detail_msg)  → filtre échoué, code de blocage inclus dans le msg
        """
        if signal.get("event_type") not in TRADEABLE_EVENTS:
            return True, ""

        self._maybe_reset()

        # 1. Trades simultanés
        if self._open_trades >= MAX_TRADES:
            return False, (
                f"{self._open_trades} trades déjà ouverts "
                f"(maximum autorisé : {MAX_TRADES})"
            )

        # 2. Daily drawdown
        if self._daily_loss >= DAILY_DD_AMOUNT:
            return False, (
                f"Perte du jour : {self._daily_loss:.2f} € — "
                f"limite atteinte ({DAILY_DD_AMOUNT} €). "
                f"Reprise : 00:00 UTC"
            )

        # 3. Weekly drawdown / pause
        if self.weekly_pause_active:
            resume = self._weekly_pause_until.strftime("%Y-%m-%d %H:%M")
            return False, (
                f"Pause weekly active — reprise le {resume} UTC "
                f"(perte semaine : {self._weekly_loss:.2f} € / {WEEKLY_DD_AMOUNT} €)"
            )

        if self._weekly_loss >= WEEKLY_DD_AMOUNT:
            return False, (
                f"Perte de la semaine : {self._weekly_loss:.2f} € — "
                f"limite atteinte ({WEEKLY_DD_AMOUNT} €)"
            )

        return True, ""

    def summary(self) -> dict:
        """Résumé de l'état courant — utilisé dans les logs et l'API /status."""
        self._maybe_reset()
        return {
            "open_trades": self._open_trades,
            "daily_loss_eur": round(self._daily_loss, 2),
            "daily_limit_eur": DAILY_DD_AMOUNT,
            "daily_remaining_eur": round(max(DAILY_DD_AMOUNT - self._daily_loss, 0), 2),
            "weekly_loss_eur": round(self._weekly_loss, 2),
            "weekly_limit_eur": WEEKLY_DD_AMOUNT,
            "weekly_remaining_eur": round(max(WEEKLY_DD_AMOUNT - self._weekly_loss, 0), 2),
            "weekly_pause_active": self.weekly_pause_active,
            "weekly_pause_until": (
                self._weekly_pause_until.strftime("%Y-%m-%d %H:%M UTC")
                if self._weekly_pause_until else None
            ),
        }


# Instance unique partagée par toute l'application
risk_state = RiskState()
