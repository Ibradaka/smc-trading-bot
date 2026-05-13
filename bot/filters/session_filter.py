"""
Filtre 1 — Session de trading.

Règle : seuls les signaux reçus dans les fenêtres London ou NY sont autorisés.
  London : 08:00 – 11:00 UTC
  NY     : 14:30 – 17:00 UTC

Raison de blocage : HORS_SESSION

Le filtre vérifie également que le symbole est autorisé pour la session active.
  EURUSD  → London + NY
  NAS100  → NY uniquement
  XAGUSD  → London uniquement
"""

from datetime import datetime, timezone
from typing import Literal

from config.settings import SESSIONS, ALLOWED_SYMBOLS


SessionName = Literal["london", "ny", "none"]


def current_session(at: datetime | None = None) -> SessionName:
    """Retourne la session active à l'instant donné (UTC). 'none' si hors session."""
    now = at or datetime.now(timezone.utc)
    t = now.time().replace(second=0, microsecond=0)

    for name, window in SESSIONS.items():
        if window["start"] <= t < window["end"]:
            return name  # type: ignore[return-value]
    return "none"


def check(signal: dict) -> tuple[bool, str]:
    """
    Vérifie que le signal arrive dans une session active et autorisée pour ce symbole.

    Returns:
        (True, "")           → filtre passé
        (False, detail_msg)  → filtre échoué, message de blocage inclus
    """
    symbol = signal.get("symbol", "")
    session = current_session()

    if session == "none":
        now_utc = datetime.now(timezone.utc).strftime("%H:%M")
        return False, (
            f"Signal reçu à {now_utc} UTC — "
            f"hors fenêtre London (08:00-11:00) et NY (14:30-17:00)"
        )

    # Vérifier que le symbole est autorisé pour la session courante
    symbol_config = ALLOWED_SYMBOLS.get(symbol)
    if symbol_config and session not in symbol_config["sessions"]:
        allowed = " + ".join(symbol_config["sessions"])
        return False, (
            f"{symbol} n'est pas tradé en session {session.upper()} "
            f"(sessions autorisées : {allowed})"
        )

    return True, ""
