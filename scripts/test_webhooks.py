# -*- coding: utf-8 -*-
"""
SMC Trading Bot - Test suite des filtres webhook.

Teste chaque filtre de la chaine sequentiellement sans FastAPI ni VPS.
Appelle directement les fonctions Python du bot.

Lancement :
  cd smc-trading-bot
  python scripts/test_webhooks.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

# Ajouter la racine du projet au PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Variables d'environnement minimales pour les tests
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test-secret-key-smc")
os.environ.setdefault("PINECONNECTOR_LICENSE_ID", "TEST-LICENSE-123")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0000000000:TEST_TOKEN_PLACEHOLDER")
os.environ.setdefault("TELEGRAM_CHAT_ID", "0")
os.environ.setdefault("LOG_LEVEL", "WARNING")   # silencer les logs pendant les tests

from bot import webhook
from bot.filters.risk_filter import risk_state

# ---------------------------------------------------------------------------
# Couleurs terminal (Windows 10+ et Linux)
# ---------------------------------------------------------------------------

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# Payload de base valide - EURUSD SWEEP_HIGH London
#
# Logique EMA pour SWEEP_HIGH (bear) :
#   - direction=bear => price DOIT etre < ema (sous-tendance bearish)
#   - sweep_level : le high swept. SWEEP_HIGH => price > sweep_level
#     (le prix a monte au-dessus du swing high puis est redescendu,
#      le signal est envoye quand close < open et close < sweep_level,
#      mais APRES que price a depasse sweep_level)
#
# Note : la validation webhook.py teste payload["price"] > sweep_level
# => le payload du signal est envoye avec le prix du moment du sweep,
#    qui EST superieur au sweep_level.
# ---------------------------------------------------------------------------

BASE_VALID_PAYLOAD = {
    "secret":       "test-secret-key-smc",
    "event_type":   "SWEEP_HIGH",
    "symbol":       "EURUSDs",
    "timeframe":    "15",
    "price":        1.08500,       # prix SOUS l'EMA (1.09000) => bear OK
    "direction":    "bear",        # SWEEP_HIGH => forcément bear
    "timestamp":    "2024-01-15T09:15:00Z",
    "sl_pips":      20.0,
    "tp_pips":      50.0,          # RR = 50/20 = 2.5
    "ema_50_value": 1.09000,       # price (1.08500) < EMA (1.09000) => bear valide
    "session":      "london",
    "sweep_level":  1.08400,       # price (1.08500) > sweep_level (1.08400) => valide
}

BASE_VALID_BOS = {
    "secret":       "test-secret-key-smc",
    "event_type":   "BOS_BULL",
    "symbol":       "EURUSDs",
    "timeframe":    "15",
    "price":        1.09500,       # prix AU-DESSUS de l'EMA (1.09000) => bull OK
    "direction":    "bull",        # BOS_BULL => forcément bull
    "timestamp":    "2024-01-15T09:30:00Z",
    "sl_pips":      15.0,
    "tp_pips":      40.0,          # RR = 40/15 = 2.67
    "ema_50_value": 1.09000,       # price (1.09500) > EMA (1.09000) => bull valide
    "session":      "london",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_risk_state():
    """Remet a zero le singleton RiskState + le cache anti-doublon entre les tests."""
    risk_state._open_trades        = 0
    risk_state._daily_loss         = 0.0
    risk_state._weekly_loss        = 0.0
    risk_state._weekly_pause_until = None
    # Vide le cache anti-doublon : sinon la reutilisation des payloads de test
    # (memes symbol/event/direction/timestamp) declencherait le filtre DOUBLON.
    webhook._processed_signals.clear()


def _make_london_time():
    """Datetime UTC dans la session London (09:00 UTC)."""
    return datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)


def _make_offhours_time():
    """Datetime UTC hors session (03:00 UTC)."""
    return datetime(2024, 1, 15, 3, 0, 0, tzinfo=timezone.utc)


class TestResult:
    def __init__(self):
        self.passed  = 0
        self.failed  = 0
        self.details = []

    def record(self, name: str, ok: bool, info: str = ""):
        if ok:
            self.passed += 1
            self.details.append((name, True, info))
            print(f"  {GREEN}[PASS]{RESET}  {name}")
        else:
            self.failed += 1
            self.details.append((name, False, info))
            print(f"  {RED}[FAIL]{RESET}  {name}")
            if info:
                print(f"         {YELLOW}>> {info}{RESET}")

    @property
    def total(self):
        return self.passed + self.failed


# ---------------------------------------------------------------------------
# Appel du pipeline avec mocks heure + Telegram + PineConnector
# ---------------------------------------------------------------------------

async def run_test(
    payload: dict,
    *,
    mock_time: datetime | None = None,
    mock_pineconnector: bool = True,
) -> dict:
    """
    Appelle webhook.process() avec Telegram et PineConnector mockes.
    Reinitialise le risk_state avant chaque appel.
    """
    _reset_risk_state()
    return await _run_pipeline(payload, mock_time=mock_time, mock_pineconnector=mock_pineconnector)


async def _run_pipeline(
    payload: dict,
    *,
    mock_time: datetime | None = None,
    mock_pineconnector: bool = True,
) -> dict:
    """Pipeline brut sans reset du risk_state (pour tester max_trades / daily_dd)."""
    patches = [
        patch("bot.notifications.telegram._safe_send", new=AsyncMock(return_value=None)),
    ]
    if mock_pineconnector:
        # Le bot route desormais via mt5_forwarder (PineConnector abandonne).
        patches.append(patch(
            "bot.execution.mt5_forwarder.send_order",
            new=AsyncMock(return_value=(True, "MT5 buy EURUSD lot=0.15 ticket=123", 0.15, "")),
        ))
    if mock_time is not None:
        patches.append(patch(
            "bot.filters.session_filter.datetime",
            **{"now.return_value": mock_time},
        ))

    for p in patches:
        p.start()
    try:
        result = await webhook.process(payload)
    finally:
        for p in patches:
            p.stop()
    return result


# ---------------------------------------------------------------------------
# SUITE DE TESTS
# ---------------------------------------------------------------------------

async def run_all_tests() -> TestResult:
    results = TestResult()

    print(f"\n{BOLD}{CYAN}==================================================={RESET}")
    print(f"{BOLD}{CYAN}  SMC Trading Bot - Test suite des filtres webhook   {RESET}")
    print(f"{BOLD}{CYAN}==================================================={RESET}\n")

    # -----------------------------------------------------------------------
    # SECTION 1 - MUST PASS (ALLOW)
    # -----------------------------------------------------------------------
    print(f"{BOLD}-- MUST PASS (ALLOW) --------------------------------------{RESET}")

    # Test 1 : SWEEP_HIGH valide - tous filtres passent
    payload = dict(BASE_VALID_PAYLOAD)
    result  = await run_test(payload, mock_time=_make_london_time())
    ok      = result["status"] == "ALLOW" and result.get("event_type") == "SWEEP_HIGH"
    info    = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("SWEEP_HIGH EURUSD London - RR 2.5 - doit etre ALLOW", ok, info)

    # Test 2 : BOS_BULL valide - tous filtres passent
    payload = dict(BASE_VALID_BOS)
    result  = await run_test(payload, mock_time=_make_london_time())
    ok      = result["status"] == "ALLOW" and result.get("event_type") == "BOS_BULL"
    info    = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("BOS_BULL EURUSD London - RR 2.67 - doit etre ALLOW", ok, info)

    print()

    # -----------------------------------------------------------------------
    # SECTION 2 - MUST BLOCK
    # -----------------------------------------------------------------------
    print(f"{BOLD}-- MUST BLOCK ---------------------------------------------{RESET}")

    # Test 3 : Mauvaise cle secrete -> AUTH_ECHEC
    payload = dict(BASE_VALID_PAYLOAD)
    payload["secret"] = "mauvaise-cle"
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "AUTH_ECHEC"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("Mauvaise cle secrete -> BLOCK AUTH_ECHEC", ok, info)

    # Test 4 : Symbole non autorise (GBPUSD) -> SYMBOLE_NON_AUTORISE
    payload = dict(BASE_VALID_PAYLOAD)
    payload["symbol"] = "GBPUSD"
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "SYMBOLE_NON_AUTORISE"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("Symbole GBPUSD non autorise -> BLOCK SYMBOLE_NON_AUTORISE", ok, info)

    # Test 5 : Heure hors session (03:00 UTC) -> HORS_SESSION
    payload = dict(BASE_VALID_PAYLOAD)
    result  = await run_test(payload, mock_time=_make_offhours_time())
    ok      = result["status"] == "BLOCK" and result.get("reason") == "HORS_SESSION"
    info    = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("Signal a 03:00 UTC (hors session) -> BLOCK HORS_SESSION", ok, info)

    # Test 6 : Signal BULL avec prix sous EMA -> EMA_CONTRAIRE
    payload          = dict(BASE_VALID_BOS)
    payload["price"] = 1.08500        # SOUS l'EMA (1.09000) alors que direction=bull
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "EMA_CONTRAIRE"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("BOS_BULL prix sous EMA 4H -> BLOCK EMA_CONTRAIRE", ok, info)

    # Test 7 : RR = 1.2 (sous le minimum 2.0) -> RR_INSUFFISANT
    payload             = dict(BASE_VALID_BOS)
    payload["tp_pips"]  = 18.0        # RR = 18/15 = 1.2 < 2.0
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "RR_INSUFFISANT"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("RR = 1.2 (minimum 2.0) -> BLOCK RR_INSUFFISANT", ok, info)

    # Test 8 : 2 trades deja ouverts -> MAX_TRADES_ATTEINT
    # Ne pas appeler run_test() (qui fait _reset_risk_state), injecter directement
    _reset_risk_state()
    risk_state._open_trades = 2
    payload = dict(BASE_VALID_PAYLOAD)
    result  = await _run_pipeline(payload, mock_time=_make_london_time())
    ok      = result["status"] == "BLOCK" and result.get("reason") == "MAX_TRADES_ATTEINT"
    info    = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("2 trades deja ouverts -> BLOCK MAX_TRADES_ATTEINT", ok, info)

    # Test 9 : Drawdown jour = 95 EUR (depasse limite 90 EUR) -> DAILY_DD_ATTEINT
    _reset_risk_state()
    risk_state._daily_loss = 95.0
    payload = dict(BASE_VALID_PAYLOAD)
    result  = await _run_pipeline(payload, mock_time=_make_london_time())
    ok      = result["status"] == "BLOCK" and result.get("reason") == "DAILY_DD_ATTEINT"
    info    = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("Drawdown jour 95 EUR > limite 90 EUR -> BLOCK DAILY_DD_ATTEINT", ok, info)

    # -----------------------------------------------------------------------
    # BONUS - Validation payload
    # -----------------------------------------------------------------------
    print()
    print(f"{BOLD}-- BONUS -- Validation payload ----------------------------{RESET}")

    # Test 10 : Champ obligatoire manquant (price absent) -> PAYLOAD_INVALIDE
    payload = dict(BASE_VALID_PAYLOAD)
    del payload["price"]
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "PAYLOAD_INVALIDE"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("Champ 'price' absent -> BLOCK PAYLOAD_INVALIDE", ok, info)

    # Test 11 : event_type inconnu -> PAYLOAD_INVALIDE
    payload               = dict(BASE_VALID_PAYLOAD)
    payload["event_type"] = "SIGNAL_INCONNU"
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "PAYLOAD_INVALIDE"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("event_type 'SIGNAL_INCONNU' -> BLOCK PAYLOAD_INVALIDE", ok, info)

    # Test 12 : SWEEP_HIGH avec direction=bull (incoherence) -> PAYLOAD_INVALIDE
    payload               = dict(BASE_VALID_PAYLOAD)
    payload["direction"]  = "bull"    # SWEEP_HIGH requiert bear
    result = await run_test(payload, mock_time=_make_london_time())
    ok     = result["status"] == "BLOCK" and result.get("reason") == "PAYLOAD_INVALIDE"
    info   = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("SWEEP_HIGH avec direction=bull (incoherence) -> BLOCK PAYLOAD_INVALIDE", ok, info)

    # Test 13 : SESSION_OPEN -> ALLOW special (aucun ordre envoye)
    payload = {
        "secret":       "test-secret-key-smc",
        "event_type":   "SESSION_OPEN",
        "symbol":       "EURUSDs",
        "timeframe":    "15",
        "price":        1.09400,
        "direction":    "bull",
        "timestamp":    "2024-01-15T08:00:00Z",
        "session":      "london",
        "ema_50_value": 1.09000,
    }
    result = await run_test(payload, mock_time=_make_london_time())
    ok = (
        result["status"] == "ALLOW"
        and result.get("event_type") == "SESSION_OPEN"
        and "aucun ordre" in result.get("detail", "").lower()
    )
    info = f"status={result['status']} detail={result.get('detail', '-')}" if not ok else ""
    results.record("SESSION_OPEN -> ALLOW sans trade (evenement de gestion)", ok, info)

    # -----------------------------------------------------------------------
    # ANTI-DOUBLON & CLOTURE
    # -----------------------------------------------------------------------
    print()
    print(f"{BOLD}-- ANTI-DOUBLON & CLOTURE ---------------------------------{RESET}")

    # Test 14 : meme webhook envoye 2x -> 2e = BLOCK DOUBLON
    _reset_risk_state()
    payload = dict(BASE_VALID_BOS)
    first   = await _run_pipeline(payload, mock_time=_make_london_time())
    second  = await _run_pipeline(payload, mock_time=_make_london_time())
    ok = (
        first["status"] == "ALLOW"
        and second["status"] == "BLOCK"
        and second.get("reason") == "DOUBLON"
    )
    info = (f"1er={first['status']} 2e={second['status']}/{second.get('reason', '-')}"
            if not ok else "")
    results.record("Webhook duplique -> 1er ALLOW, 2e BLOCK DOUBLON", ok, info)

    # Test 15 : event CLOSE -> ALLOW (cloture forcee, flat anti-gap)
    _reset_risk_state()
    close_payload = {
        "secret":     "test-secret-key-smc",
        "event_type": "CLOSE",
        "symbol":     "USTECs",
        "timeframe":  "15",
        "price":      20000.0,
        "direction":  "bear",
        "timestamp":  "2024-01-15T20:45:00Z",
    }
    with patch("bot.notifications.telegram._safe_send",
               new=AsyncMock(return_value=None)), \
         patch("bot.execution.mt5_forwarder.send_close",
               new=AsyncMock(return_value=(True, "MT5 close USTECs - 1 position fermee", ""))):
        result = await webhook.process(close_payload)
    ok = result["status"] == "ALLOW" and result.get("event_type") == "CLOSE"
    info = f"status={result['status']} reason={result.get('reason', '-')}" if not ok else ""
    results.record("event CLOSE -> ALLOW (cloture forcee)", ok, info)

    # -----------------------------------------------------------------------
    # SCORE FINAL
    # -----------------------------------------------------------------------
    _reset_risk_state()

    print(f"\n{BOLD}==================================================={RESET}")
    score_color = GREEN if results.failed == 0 else (YELLOW if results.failed <= 2 else RED)
    print(
        f"{BOLD}   SCORE FINAL : "
        f"{score_color}{results.passed}/{results.total}{RESET}{BOLD} tests passes{RESET}"
    )
    if results.failed == 0:
        print(f"   {GREEN}{BOLD}Tous les filtres fonctionnent correctement. OK{RESET}")
        print(f"   {GREEN}Le bot est pret pour le deploiement VPS.{RESET}")
    else:
        print(f"   {RED}{BOLD}{results.failed} test(s) echoue(s) - corriger avant deploiement.{RESET}")
        print(f"\n{YELLOW}Tests echoues :{RESET}")
        for name, ok, info in results.details:
            if not ok:
                print(f"   {RED}> {name}{RESET}")
                if info:
                    print(f"     {YELLOW}{info}{RESET}")
    print(f"{BOLD}==================================================={RESET}\n")

    return results


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        results = asyncio.run(run_all_tests())
        sys.exit(0 if results.failed == 0 else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrompus.{RESET}")
        sys.exit(2)
