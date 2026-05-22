"""
MT5 Forwarder
=============
Remplace PineConnector. Transmet les decisions ALLOW du bot a l'executor MT5
(`mt5_executor_service.py`) qui tourne sur la machine Windows hebergeant MT5.

Garde la meme interface que l'ancien `pineconnector.send_order()` :
    send_order(signal) -> (success, description, lot_size, error)

VARIABLES D'ENVIRONNEMENT (sur le VPS du bot) :
    MT5_EXECUTOR_URL    : ex. http://<IP_VPS_WINDOWS>:9000/order
    MT5_EXECUTOR_SECRET : cle partagee avec l'executor
"""

import logging
import math
import os

import httpx

from config.settings import RISK_AMOUNT, ALLOWED_SYMBOLS

logger = logging.getLogger(__name__)

MT5_EXECUTOR_URL    = os.environ.get("MT5_EXECUTOR_URL", "")
MT5_EXECUTOR_SECRET = os.environ.get("MT5_EXECUTOR_SECRET", "")
_TIMEOUT = 10.0  # secondes — au-dela, on bloque et on alerte


def compute_lot_size(symbol: str, sl_pips: float) -> float:
    """
    Lot pour risquer exactement RISK_AMOUNT sur ce trade.

    lot = RISK_AMOUNT / (sl_pips x pip_value_per_lot), arrondi vers le bas
    au 0.01 le plus proche (jamais sur-risquer).
    """
    pip_value = ALLOWED_SYMBOLS.get(symbol, {}).get("pip_value_per_lot", 10.0)
    if sl_pips <= 0 or pip_value <= 0:
        logger.warning("sl_pips/pip_value invalide — lot force a 0.01")
        return 0.01
    raw_lot = RISK_AMOUNT / (sl_pips * pip_value)
    lot = math.floor(raw_lot * 100) / 100
    return max(lot, 0.01)


async def send_order(signal: dict) -> tuple[bool, str, float, str]:
    """
    Calcule le lot et transmet l'ordre a l'executor MT5.

    Returns:
        (success, description, lot_size, error_message)
        - success=True  -> ordre place sur MT5
        - success=False -> erreur, trade bloque
    """
    symbol   = signal["symbol"]
    sl_pips  = float(signal["sl_pips"])
    tp_pips  = float(signal["tp_pips"])
    lot_size = compute_lot_size(symbol, sl_pips)

    if not MT5_EXECUTOR_URL:
        return False, "", lot_size, "MT5_EXECUTOR_URL non configure dans le .env"

    payload = {
        "secret":    MT5_EXECUTOR_SECRET,
        "symbol":    symbol,
        "direction": signal["direction"],
        "lot":       lot_size,
        "sl_pips":   sl_pips,
        "tp_pips":   tp_pips,
        "comment":   f"SMC {signal.get('event_type', '')}"[:31],
    }

    logger.info("Transmission ordre a l'executor MT5 : %s %s lot=%.2f",
                signal["direction"].upper(), symbol, lot_size)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(MT5_EXECUTOR_URL, json=payload)
        data = resp.json()
    except httpx.TimeoutException:
        return False, "", lot_size, f"Timeout ({_TIMEOUT}s) — executor MT5 ne repond pas"
    except Exception as exc:
        logger.error("Erreur appel executor MT5 : %s", exc, exc_info=True)
        return False, "", lot_size, str(exc)

    if resp.status_code == 200 and data.get("success"):
        cmd = (f"MT5 {signal['direction']} {symbol} lot={lot_size} "
               f"ticket={data.get('ticket')} @ {data.get('price')}")
        logger.info("Executor MT5 OK — %s", cmd)
        return True, cmd, lot_size, ""

    err = data.get("error", f"HTTP {resp.status_code}")
    logger.error("Executor MT5 a refuse l'ordre : %s", err)
    return False, "", lot_size, err


async def send_close(signal: dict) -> tuple[bool, str, str]:
    """
    Demande a l'executor MT5 de fermer toute position du bot (magic 13013)
    sur ce symbole. Utilise pour le flat de fin de session (anti-gap NASDAQ).

    Fermer une position deja close (TP/SL deja touche) renvoie success avec
    closed=0 — c'est normal, l'objectif "etre flat" est atteint.

    Returns:
        (success, description, error_message)
    """
    symbol = signal["symbol"]

    if not MT5_EXECUTOR_URL:
        return False, "", "MT5_EXECUTOR_URL non configure dans le .env"

    close_url = MT5_EXECUTOR_URL.replace("/order", "/close")
    payload = {"secret": MT5_EXECUTOR_SECRET, "symbol": symbol}

    logger.info("Demande de cloture a l'executor MT5 : %s", symbol)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(close_url, json=payload)
        data = resp.json()
    except httpx.TimeoutException:
        return False, "", f"Timeout ({_TIMEOUT}s) — executor MT5 ne repond pas"
    except Exception as exc:
        logger.error("Erreur appel /close executor MT5 : %s", exc, exc_info=True)
        return False, "", str(exc)

    if resp.status_code == 200 and data.get("success"):
        closed = data.get("closed", 0)
        desc = f"MT5 close {symbol} — {closed} position(s) fermee(s)"
        logger.info("Executor MT5 OK — %s", desc)
        return True, desc, ""

    err = data.get("error", f"HTTP {resp.status_code}")
    logger.error("Executor MT5 a refuse la cloture : %s", err)
    return False, "", err


async def get_open_positions() -> int | None:
    """
    Nombre de positions actuellement ouvertes par le bot (magic 13013) sur MT5.

    Sert a la reconciliation : MT5 ne notifie pas la cloture d'un trade, donc
    le compteur interne du bot ne redescend pas seul. On interroge l'executor
    pour la verite avant le filtre RISK.

    Returns:
        le nombre de positions (int), ou None si l'executor est injoignable
        (dans ce cas le bot garde son compteur interne).
    """
    if not MT5_EXECUTOR_URL:
        return None

    positions_url = MT5_EXECUTOR_URL.replace("/order", "/positions")
    payload = {"secret": MT5_EXECUTOR_SECRET}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(positions_url, json=payload)
        data = resp.json()
    except Exception as exc:
        logger.warning("Reconciliation : executor injoignable (%s)", exc)
        return None

    if resp.status_code == 200 and data.get("success"):
        return int(data.get("count", 0))

    logger.warning("Reconciliation : reponse executor invalide — %s",
                   data.get("error", f"HTTP {resp.status_code}"))
    return None
