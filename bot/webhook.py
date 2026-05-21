"""
Webhook processing pipeline.

Reçoit le payload brut de TradingView et applique la chaîne de filtres
dans l'ordre défini dans docs/risk-rules.md :

  1. AUTH          — clé secrète valide
  2. VALIDATION    — payload JSON complet et cohérent
  3. SYMBOLE       — actif dans la liste autorisée
  4. SESSION       — signal dans la fenêtre London ou NY
  5. EMA           — prix du bon côté de l'EMA 50 HTF
  6. RR            — ratio risque/rendement ≥ 1:2
  7. RISK          — drawdown et trades simultanés OK

Si tous les filtres passent et que l'événement est tradeable → ALLOW + PineConnector.
Si un filtre échoue → BLOCK + log + Telegram.
SESSION_OPEN est toujours ALLOW (événement de gestion interne, non tradeable).
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from config.settings import (
    ALLOWED_SYMBOLS,
    TRADEABLE_EVENTS,
    VALID_EVENT_TYPES,
)
from bot.filters import session_filter, structure_filter
from bot.filters.risk_filter import risk_state
from bot.execution import pineconnector
from bot.notifications import telegram

logger = logging.getLogger(__name__)

# Mapping event_type → direction forcée (contrat webhook §4)
FORCED_DIRECTIONS: dict[str, str | None] = {
    "SWEEP_HIGH":     "bear",
    "SWEEP_LOW":      "bull",
    "BOS_BULL":       "bull",
    "BOS_BEAR":       "bear",
    "SESSION_OPEN":   None,   # libre
    "RANGE_BREAKOUT": None,   # libre
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _block(signal_id: str, signal: dict, reason: str, detail: str,
           filters_passed: list[str]) -> dict:
    logger.warning(
        "BLOCK | id=%s | %s | %s | reason=%s | %s",
        signal_id,
        signal.get("event_type", "?"),
        signal.get("symbol", "?"),
        reason,
        detail,
    )
    return {
        "status": "BLOCK",
        "signal_id": signal_id,
        "event_type": signal.get("event_type"),
        "symbol": signal.get("symbol"),
        "reason": reason,
        "detail": detail,
        "filters_passed": filters_passed,
        "filters_failed": [reason],
        "timestamp": _now_iso(),
    }


def _allow(signal_id: str, signal: dict, lot_size: float,
           cmd: str, filters_passed: list[str]) -> dict:
    rr = round(signal["tp_pips"] / signal["sl_pips"], 2)
    risk_eur = round(float(signal["sl_pips"]) * lot_size * 10, 2)
    logger.info(
        "ALLOW | id=%s | %s | %s | %s | lot=%.2f | cmd=%s",
        signal_id,
        signal["event_type"],
        signal["symbol"],
        signal["direction"].upper(),
        lot_size,
        cmd,
    )
    return {
        "status": "ALLOW",
        "signal_id": signal_id,
        "event_type": signal["event_type"],
        "symbol": signal["symbol"],
        "direction": signal["direction"],
        "lot_size": lot_size,
        "sl_pips": signal["sl_pips"],
        "tp_pips": signal["tp_pips"],
        "rr": rr,
        "risk_eur": risk_eur,
        "pineconnector_cmd": cmd,
        "filters_passed": filters_passed,
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Filtre 1 — Authentification
# ---------------------------------------------------------------------------

def _filter_auth(payload: dict) -> tuple[bool, str]:
    """
    Vérifie la clé secrète dans le payload (champ 'secret').
    TradingView ne supportant pas les headers custom, la clé est dans le JSON.
    """
    expected = os.environ.get("WEBHOOK_SECRET_KEY", "")
    received = payload.get("secret", "")

    if not expected:
        logger.error("WEBHOOK_SECRET_KEY non défini dans .env — auth impossible")
        return False, "WEBHOOK_SECRET_KEY non configuré sur le serveur"

    if received != expected:
        return False, "Clé secrète absente ou incorrecte"

    return True, ""


# ---------------------------------------------------------------------------
# Filtre 2 — Validation du payload
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["event_type", "symbol", "timeframe", "price", "direction", "timestamp"]
VALID_DIRECTIONS = {"bull", "bear"}
VALID_TIMEFRAMES = {"4H", "15", "5"}


def _filter_validation(payload: dict) -> tuple[bool, str]:
    """Vérifie la présence et la cohérence des champs obligatoires."""

    # Champs obligatoires
    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        return False, f"Champs manquants : {', '.join(missing)}"

    # Types
    if not isinstance(payload.get("price"), (int, float)):
        return False, f"price doit être un nombre, reçu : {type(payload['price']).__name__}"

    if payload.get("price", 0) <= 0:
        return False, f"price invalide : {payload['price']} (doit être > 0)"

    # Valeurs énumérées
    if payload.get("event_type") not in VALID_EVENT_TYPES:
        return False, (
            f"event_type inconnu : '{payload['event_type']}'. "
            f"Valeurs acceptées : {sorted(VALID_EVENT_TYPES)}"
        )

    if payload.get("direction") not in VALID_DIRECTIONS:
        return False, (
            f"direction invalide : '{payload['direction']}'. "
            f"Valeurs acceptées : bull, bear"
        )

    if payload.get("timeframe") not in VALID_TIMEFRAMES:
        return False, (
            f"timeframe invalide : '{payload['timeframe']}'. "
            f"Valeurs acceptées : 4H, 15, 5"
        )

    # Cohérence direction / event_type
    forced = FORCED_DIRECTIONS.get(payload["event_type"])
    if forced and payload["direction"] != forced:
        return False, (
            f"{payload['event_type']} requiert direction={forced}, "
            f"reçu : {payload['direction']}"
        )

    # SL/TP obligatoires et > 0 pour tout événement tradeable
    # (utilisés par le calcul RR, le lot size et PineConnector)
    if payload["event_type"] in TRADEABLE_EVENTS:
        for fld in ("sl_pips", "tp_pips"):
            val = payload.get(fld)
            if not isinstance(val, (int, float)) or val <= 0:
                return False, (
                    f"{fld} obligatoire et > 0 pour un événement tradeable "
                    f"({payload['event_type']}), reçu : {val}"
                )

    # Cohérence RANGE_BREAKOUT
    if payload["event_type"] == "RANGE_BREAKOUT":
        rh = payload.get("range_high")
        rl = payload.get("range_low")
        if rh is None or rl is None:
            return False, "RANGE_BREAKOUT requiert range_high et range_low"
        if rh <= rl:
            return False, f"range_high ({rh}) doit être > range_low ({rl})"
        amplitude_pips = round((rh - rl) / 0.0001, 1)
        if amplitude_pips < 20:
            return False, (
                f"Amplitude du range trop faible : {amplitude_pips} pips "
                f"(minimum : 20 pips)"
            )

    # Cohérence SWEEP
    if payload["event_type"] == "SWEEP_HIGH":
        sl = payload.get("sweep_level")
        if sl and payload["price"] <= sl:
            return False, (
                f"SWEEP_HIGH : price ({payload['price']}) "
                f"doit être > sweep_level ({sl})"
            )

    if payload["event_type"] == "SWEEP_LOW":
        sl = payload.get("sweep_level")
        if sl and payload["price"] >= sl:
            return False, (
                f"SWEEP_LOW : price ({payload['price']}) "
                f"doit être < sweep_level ({sl})"
            )

    return True, ""


# ---------------------------------------------------------------------------
# Filtre 3 — Symbole autorisé
# ---------------------------------------------------------------------------

def _filter_symbol(payload: dict) -> tuple[bool, str]:
    symbol = payload.get("symbol", "")
    if symbol not in ALLOWED_SYMBOLS:
        allowed = ", ".join(sorted(ALLOWED_SYMBOLS.keys()))
        return False, (
            f"Symbole '{symbol}' non autorisé. "
            f"Actifs acceptés : {allowed}"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

async def process(payload: dict) -> dict:
    """
    Exécute la chaîne de filtres complète et retourne la décision finale.

    Args:
        payload : dict brut reçu du webhook TradingView

    Returns:
        dict avec status=ALLOW ou BLOCK, et tous les champs du contrat webhook
    """
    signal_id = str(uuid.uuid4())
    filters_passed: list[str] = []

    # --- Filtre 1 : AUTH ---
    ok, detail = _filter_auth(payload)
    if not ok:
        return _block(signal_id, payload, "AUTH_ECHEC", detail, filters_passed)
    filters_passed.append("AUTH")

    # --- Filtre 2 : VALIDATION ---
    ok, detail = _filter_validation(payload)
    if not ok:
        return _block(signal_id, payload, "PAYLOAD_INVALIDE", detail, filters_passed)
    filters_passed.append("VALIDATION")

    signal = payload  # payload validé, on le traite comme le signal

    # --- Filtre 3 : SYMBOLE ---
    ok, detail = _filter_symbol(signal)
    if not ok:
        return _block(signal_id, signal, "SYMBOLE_NON_AUTORISE", detail, filters_passed)
    filters_passed.append("SYMBOLE")

    # --- SESSION_OPEN : traitement spécial (non tradeable) ---
    if signal["event_type"] == "SESSION_OPEN":
        logger.info(
            "SESSION_OPEN reçu — %s | session=%s | ema=%.5f | direction=%s",
            signal.get("symbol"),
            signal.get("session", "?"),
            signal.get("ema_50_value", 0),
            signal.get("direction"),
        )
        await telegram.notify_session_open(
            session=signal.get("session", "?"),
            symbol=signal.get("symbol", ""),
            ema_value=signal.get("ema_50_value", 0.0),
            direction=signal.get("direction", ""),
        )
        filters_passed.extend(["SESSION", "EMA", "RR", "RISK"])
        return {
            "status": "ALLOW",
            "signal_id": signal_id,
            "event_type": "SESSION_OPEN",
            "symbol": signal.get("symbol"),
            "detail": "Événement de gestion interne — aucun ordre envoyé",
            "filters_passed": filters_passed,
            "timestamp": _now_iso(),
        }

    # --- Mode pre-filtre ---------------------------------------------------
    # Si le payload porte "prefiltered": true, le signal vient d'une STRATEGIE
    # complete (Pine v13/v10) qui applique deja session + EMA HTF + RR en
    # interne. Le bot ne re-decide pas — il saute SESSION/EMA/RR et garde
    # uniquement la securite portefeuille (RISK).
    # Sinon : pipeline classique (ancien modele detecteur d'evenements).
    prefiltered = bool(signal.get("prefiltered", False))

    if prefiltered:
        logger.info(
            "Signal PRE-FILTRE | id=%s | %s | %s — SESSION/EMA/RR sautes "
            "(strategie complete), RISK conserve",
            signal_id, signal["event_type"], signal["symbol"],
        )
        filters_passed.extend(["SESSION", "EMA", "RR"])
    else:
        # --- Filtre 4 : SESSION ---
        ok, detail = session_filter.check(signal)
        if not ok:
            await telegram.notify_block(signal, "HORS_SESSION", detail)
            return _block(signal_id, signal, "HORS_SESSION", detail, filters_passed)
        filters_passed.append("SESSION")

        # --- Filtre 5 : EMA ---
        ok, detail = structure_filter.check_ema(signal)
        if not ok:
            await telegram.notify_block(signal, "EMA_CONTRAIRE", detail)
            return _block(signal_id, signal, "EMA_CONTRAIRE", detail, filters_passed)
        filters_passed.append("EMA")

        # --- Filtre 6 : RR ---
        ok, detail = structure_filter.check_rr(signal)
        if not ok:
            await telegram.notify_block(signal, "RR_INSUFFISANT", detail)
            return _block(signal_id, signal, "RR_INSUFFISANT", detail, filters_passed)
        filters_passed.append("RR")

    # --- Filtre 7 : RISK (drawdown + trades ouverts) ---
    ok, detail = risk_state.check(signal)
    if not ok:
        # Déterminer le bon code de blocage selon le contexte
        reason = (
            "MAX_TRADES_ATTEINT" if "trades" in detail.lower()
            else "DAILY_DD_ATTEINT" if "jour" in detail.lower()
            else "WEEKLY_DD_ATTEINT"
        )
        await telegram.notify_block(signal, reason, detail)
        return _block(signal_id, signal, reason, detail, filters_passed)
    filters_passed.append("RISK")

    # --- Tous les filtres passés → ALLOW ---
    success, cmd, lot_size, err = await pineconnector.send_order(signal)

    if not success:
        # Erreur technique PineConnector → bloquer par sécurité
        await telegram.notify_error(
            context=f"PineConnector — {signal['event_type']} {signal['symbol']}",
            error=err,
        )
        return _block(
            signal_id, signal, "ERREUR_TECHNIQUE",
            f"PineConnector n'a pas répondu correctement : {err}",
            filters_passed,
        )

    # Enregistrer le trade ouvert dans l'état risk
    risk_state.trade_opened()

    await telegram.notify_allow(signal, lot_size, cmd)

    return _allow(signal_id, signal, lot_size, cmd, filters_passed)
