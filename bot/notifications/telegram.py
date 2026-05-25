"""
Telegram notification client.
Sends structured alerts to the configured chat.
All public functions are async and fire-and-forget safe —
they catch their own exceptions so a Telegram failure never blocks a trade decision.
"""

import os
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 8.0  # seconds


def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]


def _chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


async def _send(text: str) -> None:
    """Low-level send. Raises on HTTP error — callers must catch."""
    url = TELEGRAM_API.format(token=_token())
    payload = {
        "chat_id": _chat_id(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()


async def _safe_send(text: str) -> None:
    """Send with silent failure — never raises, always logs."""
    try:
        await _send(text)
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

async def notify_allow(signal: dict, lot_size: float, pineconnector_cmd: str) -> None:
    """Signal ALLOW — trade envoyé à PineConnector."""
    direction_emoji = "🟢" if signal["direction"] == "bull" else "🔴"
    text = (
        f"{direction_emoji} <b>TRADE AUTORISÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Signal :</b> {signal['event_type']}\n"
        f"<b>Symbole :</b> {signal['symbol']}\n"
        f"<b>Direction :</b> {signal['direction'].upper()}\n"
        f"<b>Prix :</b> {signal['price']}\n"
        f"<b>SL :</b> {signal.get('sl_pips')} pips\n"
        f"<b>TP :</b> {signal.get('tp_pips')} pips\n"
        f"<b>Lot size :</b> {lot_size}\n"
        f"<b>Risque :</b> ~{round(float(signal.get('sl_pips', 0)) * lot_size * 10, 2)} €\n"
        f"<b>Commande :</b> <code>{pineconnector_cmd}</code>\n"
        f"<b>Heure :</b> {_now_utc()}"
    )
    await _safe_send(text)


async def notify_block(signal: dict, reason: str, detail: str) -> None:
    """Signal BLOCK — trade refusé par un filtre."""
    text = (
        f"⛔ <b>SIGNAL BLOQUÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Signal :</b> {signal.get('event_type', 'INCONNU')}\n"
        f"<b>Symbole :</b> {signal.get('symbol', '?')}\n"
        f"<b>Raison :</b> <code>{reason}</code>\n"
        f"<b>Détail :</b> {detail}\n"
        f"<b>Heure :</b> {_now_utc()}"
    )
    await _safe_send(text)


async def notify_daily_dd_hit(loss_eur: float, limit_eur: float) -> None:
    """Daily drawdown limit atteint — bot arrêté jusqu'à minuit UTC."""
    text = (
        f"🚨 <b>DAILY DRAWDOWN ATTEINT — BOT ARRÊTÉ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Perte du jour :</b> {round(loss_eur, 2)} €\n"
        f"<b>Limite :</b> {limit_eur} €\n"
        f"<b>Reprise :</b> 00:00 UTC\n"
        f"<b>Heure :</b> {_now_utc()}\n"
        f"Aucun nouveau trade jusqu'à demain."
    )
    await _safe_send(text)


async def notify_weekly_dd_hit(loss_eur: float, limit_eur: float, resume_at: str) -> None:
    """Weekly drawdown limit atteint — pause 48h forcée."""
    text = (
        f"🚨 <b>WEEKLY DRAWDOWN ATTEINT — PAUSE 48H</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Perte de la semaine :</b> {round(loss_eur, 2)} €\n"
        f"<b>Limite :</b> {limit_eur} €\n"
        f"<b>Reprise automatique :</b> {resume_at} UTC\n"
        f"<b>Heure :</b> {_now_utc()}"
    )
    await _safe_send(text)


async def notify_error(context: str, error: str) -> None:
    """Erreur technique — trade bloqué par sécurité."""
    text = (
        f"⚠️ <b>ERREUR TECHNIQUE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Contexte :</b> {context}\n"
        f"<b>Erreur :</b> <code>{error[:400]}</code>\n"
        f"<b>Heure :</b> {_now_utc()}\n"
        f"Trade bloqué par sécurité. Intervention manuelle requise."
    )
    await _safe_send(text)


async def notify_session_open(session: str, symbol: str, ema_value: float, direction: str) -> None:
    """Ouverture de session — résumé du contexte marché."""
    emoji = "🇬🇧" if session == "london" else "🇺🇸"
    bias_emoji = "📈" if direction == "bull" else "📉"
    text = (
        f"{emoji} <b>SESSION {session.upper()} OUVERTE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Symbole :</b> {symbol}\n"
        f"<b>EMA 50 (4H) :</b> {ema_value}\n"
        f"<b>Biais HTF :</b> {bias_emoji} {direction.upper()}\n"
        f"<b>Heure :</b> {_now_utc()}\n"
        f"Bot actif — filtres opérationnels."
    )
    await _safe_send(text)


async def notify_session_close(session: str, symbol: str) -> None:
    """Clôture de session — confirmation que le marché ferme sa fenêtre active."""
    emoji = "🇬🇧" if session == "london" else "🇺🇸"
    text = (
        f"{emoji} <b>SESSION {session.upper()} FERMÉE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Symbole :</b> {symbol}\n"
        f"<b>Heure :</b> {_now_utc()}\n"
        f"Bot toujours en écoute pour les sessions suivantes."
    )
    await _safe_send(text)


async def notify_trade_closed(
    trade_id: str,
    symbol: str,
    pnl_eur: float,
    risk_summary: dict,
) -> None:
    """Clôture de trade signalée par MT5 — résumé PnL + état drawdown."""
    if pnl_eur >= 0:
        emoji = "💰"
        pnl_label = f"+{pnl_eur:.2f} €"
    else:
        emoji = "📉"
        pnl_label = f"{pnl_eur:.2f} €"

    pause_line = ""
    if risk_summary.get("weekly_pause_active"):
        pause_line = f"\n⏸ <b>Pause weekly :</b> reprise {risk_summary['weekly_pause_until']}"

    text = (
        f"{emoji} <b>TRADE CLOTURE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>ID :</b> <code>{trade_id}</code>\n"
        f"<b>Symbole :</b> {symbol}\n"
        f"<b>PnL :</b> {pnl_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Trades ouverts :</b> {risk_summary['open_trades']}\n"
        f"<b>Perte jour :</b> {risk_summary['daily_loss_eur']:.2f} € "
        f"/ {risk_summary['daily_limit_eur']:.0f} € "
        f"(reste {risk_summary['daily_remaining_eur']:.2f} €)\n"
        f"<b>Perte semaine :</b> {risk_summary['weekly_loss_eur']:.2f} € "
        f"/ {risk_summary['weekly_limit_eur']:.0f} € "
        f"(reste {risk_summary['weekly_remaining_eur']:.2f} €)"
        f"{pause_line}\n"
        f"<b>Heure :</b> {_now_utc()}"
    )
    await _safe_send(text)


async def notify_startup() -> None:
    """Notification de démarrage du bot."""
    text = (
        f"✅ <b>SMC Bot démarré</b>\n"
        f"<b>Heure :</b> {_now_utc()}\n"
        f"Endpoint webhook actif. En attente de signaux."
    )
    await _safe_send(text)
