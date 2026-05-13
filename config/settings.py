"""
SMC Trading Bot — System Configuration
All constants are defined here. Never hardcode values elsewhere.
"""

from datetime import time

# ---------------------------------------------------------------------------
# Capital & Risk Parameters
# ---------------------------------------------------------------------------

INITIAL_CAPITAL = 3000.0       # EUR
RISK_PCT = 0.01                # 1% risk per trade
MAX_TRADES = 2                 # maximum simultaneous open trades
DAILY_DD_LIMIT = 0.03          # 3% daily drawdown → bot stops
WEEKLY_DD_LIMIT = 0.06         # 6% weekly drawdown → 48h forced pause
MIN_RR = 2.0                   # minimum risk/reward ratio accepted
MAX_LEVERAGE = 10              # maximum leverage allowed

# Derived values (do not edit)
RISK_AMOUNT = INITIAL_CAPITAL * RISK_PCT          # 30.0 EUR per trade
DAILY_DD_AMOUNT = INITIAL_CAPITAL * DAILY_DD_LIMIT    # 90.0 EUR
WEEKLY_DD_AMOUNT = INITIAL_CAPITAL * WEEKLY_DD_LIMIT  # 180.0 EUR
WEEKLY_PAUSE_HOURS = 48

# ---------------------------------------------------------------------------
# Trading Sessions (UTC)
# ---------------------------------------------------------------------------

SESSIONS = {
    "london": {
        "start": time(8, 0),    # 08:00 UTC → 09:00 FR winter / 10:00 FR summer
        "end":   time(11, 0),   # 11:00 UTC → 12:00 FR winter / 13:00 FR summer
    },
    "ny": {
        "start": time(14, 30),  # 14:30 UTC → 15:30 FR winter / 16:30 FR summer
        "end":   time(17, 0),   # 17:00 UTC → 18:00 FR winter / 19:00 FR summer
    },
}

# ---------------------------------------------------------------------------
# Allowed Assets
# ---------------------------------------------------------------------------

ALLOWED_SYMBOLS = {
    "EURUSD": {
        "priority": "high",
        "sessions": ["london", "ny"],
        "pip_value_per_lot": 10.0,   # USD per pip for 1 standard lot
    },
    "NAS100": {
        "priority": "medium",
        "sessions": ["ny"],
        "pip_value_per_lot": 1.0,
    },
    "XAGUSD": {
        "priority": "low",
        "sessions": ["london"],
        "pip_value_per_lot": 50.0,
    },
}

# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------

EMA_PERIOD = 50

# Timeframes
HTF = "4H"   # High TimeFrame — trend filter (EMA 50)
MTF = "15"   # Medium TimeFrame — structure detection
LTF = "5"    # Low TimeFrame — entry refinement

# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {
    "SWEEP_HIGH",
    "SWEEP_LOW",
    "BOS_BULL",
    "BOS_BEAR",
    "SESSION_OPEN",
    "EMA_FILTER",
    "RANGE_BREAKOUT",
}

TRADEABLE_EVENTS = {
    "SWEEP_HIGH",
    "SWEEP_LOW",
    "BOS_BULL",
    "BOS_BEAR",
    "RANGE_BREAKOUT",
}

# ---------------------------------------------------------------------------
# Block Reason Codes
# ---------------------------------------------------------------------------

BLOCK_REASONS = {
    "HORS_SESSION":             "Signal reçu en dehors des sessions autorisées",
    "EMA_CONTRAIRE":            "Prix du mauvais côté de l'EMA 50 HTF",
    "MAX_TRADES_ATTEINT":       "2 trades simultanés déjà ouverts",
    "DAILY_DD_ATTEINT":         "Daily drawdown limit de 3% atteint",
    "WEEKLY_DD_ATTEINT":        "Weekly drawdown limit de 6% atteint",
    "SYMBOLE_NON_AUTORISE":     "Symbole non dans la liste des actifs autorisés",
    "PAYLOAD_INVALIDE":         "Format JSON incorrect ou champs manquants",
    "AUTH_ECHEC":               "Clé secrète webhook invalide",
    "RR_INSUFFISANT":           "Ratio risque/rendement inférieur à 1:2",
    "CONFLUENCES_INSUFFISANTES": "Signal non confirmé par le timeframe supérieur",
    "ERREUR_TECHNIQUE":         "Erreur technique — trade bloqué par sécurité",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = "bot/logs"
SIGNALS_LOG = f"{LOG_DIR}/signals.log"
ERRORS_LOG = f"{LOG_DIR}/errors.log"
