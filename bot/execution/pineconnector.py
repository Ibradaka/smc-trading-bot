"""
PineConnector execution client.

Responsabilité : traduire une décision ALLOW en commande PineConnector
et l'envoyer à l'endpoint de l'EA MetaTrader 5.

Format de commande PineConnector :
  LICENSE_ID,action,symbol,risk=X,sl=X,tp=X

Documentation : https://pineconnector.net/docs

Calcul du lot size :
  Lot = Risque€ / (SL_pips × Pip_value_per_lot)
  Arrondi au lot minimum (0.01) vers le bas pour ne jamais sur-risquer.
"""

import os
import logging
import math

import httpx

from config.settings import (
    RISK_AMOUNT,
    ALLOWED_SYMBOLS,
    MAX_LEVERAGE,
    INITIAL_CAPITAL,
)

logger = logging.getLogger(__name__)

# PineConnector envoie les commandes via une requête GET ou POST
# vers l'endpoint de l'EA (configuré dans MT5 selon la doc PineConnector)
PINECONNECTOR_ENDPOINT = "https://pineconnector.net/api/order"
_TIMEOUT = 10.0  # secondes — au-delà, on bloque et on alerte


def _license_id() -> str:
    lid = os.environ.get("PINECONNECTOR_LICENSE_ID", "")
    if not lid:
        raise RuntimeError("PINECONNECTOR_LICENSE_ID manquant dans .env")
    return lid


def compute_lot_size(symbol: str, sl_pips: float) -> float:
    """
    Calcule le lot size pour risquer exactement RISK_AMOUNT € sur ce trade.

    Formule : lot = RISK_AMOUNT / (sl_pips × pip_value_per_lot)
    Arrondi vers le bas au 0.01 le plus proche (jamais sur-risquer).

    Returns:
        lot_size (float) — minimum 0.01
    """
    pip_value = ALLOWED_SYMBOLS.get(symbol, {}).get("pip_value_per_lot", 10.0)

    if sl_pips <= 0 or pip_value <= 0:
        logger.warning("sl_pips ou pip_value invalide — lot size forcé à 0.01")
        return 0.01

    raw_lot = RISK_AMOUNT / (sl_pips * pip_value)

    # Arrondi vers le bas à 2 décimales (pas de sur-risque)
    lot = math.floor(raw_lot * 100) / 100
    lot = max(lot, 0.01)

    logger.info(
        "Lot size calculé : %.2f (risque %.2f € / SL %s pips × pip_value %.2f)",
        lot, RISK_AMOUNT, sl_pips, pip_value,
    )
    return lot


def build_command(signal: dict, lot_size: float) -> str:
    """
    Construit la commande texte PineConnector.

    Format : LICENSE_ID,action,symbol,risk=X,sl=X,tp=X

    Note : PineConnector accepte 'risk=' en pourcentage du capital OU
    directement le lot size via 'contracts=X'. On utilise 'contracts'
    pour un contrôle précis basé sur notre propre calcul de lot.
    """
    action = "buy" if signal["direction"] == "bull" else "sell"
    symbol = signal["symbol"]
    sl = signal["sl_pips"]
    tp = signal["tp_pips"]

    cmd = (
        f"{_license_id()},{action},{symbol},"
        f"contracts={lot_size},"
        f"sl={sl},"
        f"tp={tp}"
    )
    return cmd


async def send_order(signal: dict) -> tuple[bool, str, float, str]:
    """
    Calcule le lot size, construit la commande et l'envoie à PineConnector.

    Returns:
        (success, pineconnector_cmd, lot_size, error_message)
        - success=True  → ordre envoyé
        - success=False → erreur technique, trade bloqué
    """
    symbol = signal["symbol"]
    sl_pips = float(signal["sl_pips"])

    lot_size = compute_lot_size(symbol, sl_pips)
    cmd = build_command(signal, lot_size)

    logger.info("Envoi commande PineConnector : %s", cmd)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # PineConnector attend la commande en query param ou body selon la config
            # Méthode standard : POST avec la commande en corps texte brut
            response = await client.post(
                PINECONNECTOR_ENDPOINT,
                content=cmd,
                headers={"Content-Type": "text/plain"},
            )

        if response.status_code == 200:
            logger.info(
                "PineConnector OK — %s | lot: %.2f | réponse: %s",
                cmd, lot_size, response.text[:200],
            )
            return True, cmd, lot_size, ""
        else:
            err = f"HTTP {response.status_code} — {response.text[:200]}"
            logger.error("PineConnector erreur : %s", err)
            return False, cmd, lot_size, err

    except httpx.TimeoutException:
        err = f"Timeout ({_TIMEOUT}s) — PineConnector ne répond pas"
        logger.error(err)
        return False, cmd, lot_size, err

    except Exception as exc:
        err = str(exc)
        logger.error("PineConnector exception : %s", err, exc_info=True)
        return False, cmd, lot_size, err
