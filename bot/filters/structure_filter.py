"""
Filtre 2 — Structure de marché.

Contient deux sous-filtres appliqués séquentiellement :

  A. Filtre EMA 50 HTF (4H)
     - bull → price > ema_50_value  (sinon BLOCK : EMA_CONTRAIRE)
     - bear → price < ema_50_value  (sinon BLOCK : EMA_CONTRAIRE)
     - Si ema_50_value absent du payload → BLOCK (donnée requise)

  B. Filtre RR minimum 1:2
     - tp_pips / sl_pips >= MIN_RR  (sinon BLOCK : RR_INSUFFISANT)
     - Si sl_pips ou tp_pips absents → BLOCK

SESSION_OPEN et EMA_FILTER contournent ces filtres (non tradeables).
"""

from config.settings import MIN_RR, TRADEABLE_EVENTS


def check_ema(signal: dict) -> tuple[bool, str]:
    """
    Vérifie la cohérence prix / EMA 50 HTF.

    Returns:
        (True, "")           → filtre passé
        (False, detail_msg)  → filtre échoué
    """
    if signal.get("event_type") not in TRADEABLE_EVENTS:
        return True, ""

    ema = signal.get("ema_50_value")
    price = signal.get("price")
    direction = signal.get("direction")

    if ema is None:
        return False, (
            "Champ ema_50_value absent — impossible de valider le filtre HTF. "
            "Vérifier la configuration de l'alerte TradingView."
        )

    if direction == "bull" and price <= ema:
        return False, (
            f"Signal BULL mais prix ({price}) est sous l'EMA 50 HTF ({ema:.5f}) — "
            f"contre-tendance 4H"
        )

    if direction == "bear" and price >= ema:
        return False, (
            f"Signal BEAR mais prix ({price}) est au-dessus de l'EMA 50 HTF ({ema:.5f}) — "
            f"contre-tendance 4H"
        )

    return True, ""


def check_rr(signal: dict) -> tuple[bool, str]:
    """
    Vérifie que le ratio risque/rendement atteint le minimum requis.

    Returns:
        (True, "")           → filtre passé
        (False, detail_msg)  → filtre échoué
    """
    if signal.get("event_type") not in TRADEABLE_EVENTS:
        return True, ""

    sl = signal.get("sl_pips")
    tp = signal.get("tp_pips")

    if sl is None or tp is None:
        return False, (
            f"sl_pips ou tp_pips absent du payload — "
            f"impossible de calculer le RR (minimum requis : 1:{MIN_RR})"
        )

    if sl <= 0:
        return False, f"sl_pips invalide ({sl}) — doit être > 0"

    rr = round(tp / sl, 2)
    if rr < MIN_RR:
        return False, (
            f"RR insuffisant : {rr:.2f} "
            f"(TP={tp} pips / SL={sl} pips) — minimum requis : 1:{MIN_RR}"
        )

    return True, ""
